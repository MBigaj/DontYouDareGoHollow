import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hollow import cli
from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.web.app import with_readings
from hollow.application.agents import AgentDesk, AgentError
from hollow.domain.activities import ActivityKind
from hollow.domain.events import (
    AgentResult,
    FightAction,
    FightStarted,
    FightTurn,
    LessonCompleted,
    StudyLogged,
)
from hollow.domain.world import replay
from tests.conftest import FakeClock
from tests.test_web_lessons import learn
from tests.test_world import CAL

HX = {"HX-Request": "true"}
TODAY = date(2026, 10, 20)


def desk(store: SqlEventStore, clock: FakeClock) -> AgentDesk:
    return AgentDesk(store, clock, CAL)


def quests(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "agent": "quest-master",
        "day": TODAY.isoformat(),
        "quests": [
            {"id": "q1", "title": "Clear る-verbs", "why": "Due.", "bonus_souls": 60,
             "check": {"kind": "lesson", "lesson_id": "te-ru", "min_score": 0.9}},
            {"id": "q2", "title": "20 reviews", "bonus_souls": 500,
             "check": {"kind": "anki", "reviews": 20}},
            {"id": "q3", "title": "10 minutes of dev study", "bonus_souls": 100,
             "check": {"kind": "study", "activity": "dev_study", "amount": 10}},
        ],
        "roulette": {"id": "r", "title": "3 requests", "bonus_souls": 80,
                     "check": {"kind": "judged", "judge": "sensei", "rubric": "3 〜てください"}},
    }  # fmt: skip
    data.update(overrides)
    return data


def statuses(store: SqlEventStore, clock: FakeClock) -> dict[str, tuple[bool, int]]:
    state = replay(store.all(), CAL, CAL.day_of(clock.now()))
    return {s.quest.id: (s.done, s.bonus) for s in state.quests}


# --- submitting ---------------------------------------------------------------


def test_quests_are_checked_by_code_and_capped(store: SqlEventStore, clock: FakeClock) -> None:
    desk(store, clock).submit(json.dumps(quests()))
    assert statuses(store, clock) == {"q1": (False, 0), "q2": (False, 0), "q3": (False, 0),
                                      "r": (False, 0)}  # fmt: skip
    store.append(StudyLogged(clock.now(), ActivityKind.ANKI_REVIEWS, 25))
    store.append(StudyLogged(clock.now(), ActivityKind.DEV_STUDY, 10))
    clock.advance(seconds=1)
    store.append(LessonCompleted(clock.now(), "te-ru", 9, 10))
    done = statuses(store, clock)
    assert done["q1"] == (True, 60)
    assert done["q2"] == (True, 100)  # the agent asked for 500; quests pay at most 100
    assert done["q3"] == (True, 90)  # 250 souls a day at most
    state = replay(store.all(), CAL, CAL.day_of(clock.now()))
    assert state.souls == 50 + 20 + 45 + 250


def test_the_sensei_judges_quests_and_the_game_pays(store: SqlEventStore, clock: FakeClock) -> None:
    agents = desk(store, clock)
    agents.submit(quests())
    with pytest.raises(AgentError, match="No judged quest q1"):
        agents.submit({"agent": "sensei", "task": "quest:q1", "passed": True})
    with pytest.raises(AgentError, match="No conversation is waiting"):
        agents.submit({"agent": "sensei", "task": "boss:te-warden:x:phase-3", "passed": True})
    agents.submit({"agent": "sensei", "task": "quest:r", "passed": False,
                   "corrections": [{"wrote": "飲むでください", "better": "飲んでください",
                                    "why": "む becomes んで."}]})  # fmt: skip
    assert statuses(store, clock)["r"] == (False, 0)
    clock.advance(seconds=1)
    agents.submit(
        {"agent": "sensei", "task": "quest:r", "passed": True, "submission": "待ってください"}
    )
    assert statuses(store, clock)["r"] == (True, 80)
    with pytest.raises(AgentError, match="already passed"):
        agents.submit({"agent": "sensei", "task": "quest:r", "passed": True})


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (quests(day="2026-10-21"), "for today"),
        (quests(extra="field"), "playbook"),
        (quests(quests=[]), "playbook"),
        (
            quests(
                roulette={
                    "id": "q1",
                    "title": "x",
                    "bonus_souls": 1,
                    "check": {"kind": "anki", "reviews": 1},
                }
            ),
            "unique",
        ),
        (
            quests(
                quests=[
                    {
                        "id": "a",
                        "title": "x",
                        "bonus_souls": 1,
                        "check": {"kind": "lesson", "lesson_id": "nope"},
                    }
                ]
            ),
            "No lesson",
        ),
        (
            quests(
                quests=[
                    {
                        "id": "a",
                        "title": "x",
                        "bonus_souls": 1,
                        "check": {"kind": "boss", "boss_id": "nope", "phase": 1},
                    }
                ]
            ),
            "No boss",
        ),
        (
            {
                "agent": "lorekeeper",
                "texts": [{"target": "weapon:excalibur", "ja": "剣", "en": "x"}],
            },
            "Unknown lore",
        ),
        ({"agent": "nobody"}, "playbook"),
        ("not json", "playbook"),
    ],
)
def test_bad_results_are_rejected_whole(
    store: SqlEventStore, clock: FakeClock, data: Any, message: str
) -> None:
    with pytest.raises(AgentError, match=message):
        desk(store, clock).submit(data if isinstance(data, str) else json.dumps(data))
    assert store.all() == []


def test_quests_are_issued_once_a_day(store: SqlEventStore, clock: FakeClock) -> None:
    desk(store, clock).submit(quests())
    with pytest.raises(AgentError, match="already issued"):
        desk(store, clock).submit(quests())


def test_boss_quests_count_phases_reached_today(store: SqlEventStore, clock: FakeClock) -> None:
    boss = {"kind": "boss", "boss_id": "te-warden", "phase": 2}
    reach = {"id": "b", "title": "Reach phase 2", "bonus_souls": 50, "check": boss}
    desk(store, clock).submit(quests(quests=[reach], roulette=None))
    clock.advance(seconds=1)
    fight = FightStarted(clock.now(), "te-warden", 1, 100, 35, 16)
    store.append(fight)
    for _ in range(8):
        clock.advance(seconds=1)
        store.append(FightTurn(clock.now(), fight.id, FightAction.ANSWER, True))
    assert statuses(store, clock)["b"] == (True, 50)


def test_lore_tech_lead_and_journal(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    agents = desk(store, clock)
    saved = agents.submit({"agent": "lorekeeper", "texts": [
        {"target": "weapon:rusted-katana", "ja": "古い刀。まだ切れる。",
         "readings": [["古い", "ふるい"], ["刀", "かたな"], ["切れる", "きれる"]],
         "en": "An old katana. It still cuts.", "new_word": None},
        {"target": "region:firelink", "ja": "火が消えない。", "readings": [["火", "ひ"]],
         "en": "The fire."},
    ]})  # fmt: skip
    assert [e.task for e in saved] == ["weapon:rusted-katana", "region:firelink"]
    review = "review:MBigaj/hollow-trials#4"
    agents.submit({"agent": "tech-lead", "task": review, "verdict": "changes",
                   "strengths": ["Clean ports."],
                   "issues": [{"file": "app/repo.py", "line": 42, "severity": "major",
                               "note": "N+1 query."}]})  # fmt: skip
    forge = client.get("/blacksmith").text
    assert 'data-reading="かたな">刀' in forge and "An old katana." in forge
    assert 'data-reading="ひ">火' in client.get("/map").text
    page = client.get("/journal").text
    assert "Changes requested" in page and "app/repo.py:42" in page and "古い" in page


def test_journal_and_quest_panel_when_empty(client: TestClient) -> None:
    assert "Ask Claude for an agent round." in client.get("/journal").text
    assert "No quests yet today." in client.get("/").text


def test_quest_panel_on_the_bonfire(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    desk(store, clock).submit(quests())
    page = client.get("/").text
    assert "Clear る-verbs" in page and "Roulette" in page
    assert "Write it in your next Claude session; the Sensei judges it." in page
    assert "+100" in page  # capped in the display too


def test_readings_are_tooltips_and_text_is_escaped() -> None:
    html = str(with_readings("<b>刀</b>と刀", [["刀", "かたな"], ["と", "と"]]))
    assert html.startswith('&lt;b&gt;<span class="ja"')
    assert html.count('data-reading="かたな"') == 1


# --- inbox --------------------------------------------------------------------


def test_inbox_lists_tasks_and_context(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    store.append(StudyLogged(clock.now(), ActivityKind.PULL_REQUEST, 1,
                             note="MBigaj/hollow-trials#4 Add a cache"))  # fmt: skip
    store.append(StudyLogged(clock.now(), ActivityKind.ANKI_REVIEWS, 12))
    store.append(StudyLogged(clock.now() - timedelta(days=30), ActivityKind.ANKI_NEW_CARDS, 3))
    clock.advance(seconds=1)
    store.append(LessonCompleted(clock.now(), "te-tsu", 3, 5, missed=("帰る", "入る")))
    clock.advance(seconds=1)
    store.append(LessonCompleted(clock.now(), "te-tsu", 4, 5, missed=("帰る",)))
    inbox = desk(store, clock).inbox()
    tasks = {(t["agent"], t["task"]) for t in inbox["tasks"]}
    assert ("quest-master", "quests:2026-10-20") in tasks
    assert ("lorekeeper", "weapon:rusted-katana") in tasks
    assert ("tech-lead", "review:MBigaj/hollow-trials#4") in tasks
    context = inbox["context"]
    assert context["weak_verbs"][0] == {"written": "帰る", "kana": "かえる", "misses": 2}
    assert len(context["known_words"]) == 17
    assert context["anki_last_7_days"]["2026-10-20"] == {"reviews": 12, "new_cards": 0}
    assert {lesson["id"] for lesson in context["lessons"]} >= {"te-ru", "te-mixed"}


def test_inbox_after_quests_waits_for_judgement(store: SqlEventStore, clock: FakeClock) -> None:
    desk(store, clock).submit(quests())
    inbox = desk(store, clock).inbox()
    agents = [(t["agent"], t["task"]) for t in inbox["tasks"]]
    assert ("quest-master", "quests:2026-10-20") not in agents
    assert ("sensei", "quest:r") in agents
    assert inbox["context"]["quests_today"][0]["id"] == "q1"


def test_inbox_counts_fight_misses(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    fight = FightStarted(clock.now() + timedelta(seconds=1), "te-warden", 3, 100, 35)
    store.append(fight)
    store.append(FightTurn(clock.now() + timedelta(seconds=2), fight.id, FightAction.ANSWER, False))
    store.append(FightTurn(clock.now() + timedelta(seconds=3), fight.id, FightAction.ESTUS))
    weak = desk(store, clock).inbox()["context"]["weak_verbs"]
    assert len(weak) == 1 and weak[0]["misses"] == 1


def test_agent_results_round_trip_through_the_store(store: SqlEventStore, clock: FakeClock) -> None:
    event = AgentResult(clock.now(), "sensei", "quest:r", {"passed": True, "nested": {"a": [1]}})
    store.append(event)
    assert store.all() == [event]
    with pytest.raises(ValueError, match="timezone"):
        AgentResult(clock.now().replace(tzinfo=None), "x", "y", {})


# --- commands -----------------------------------------------------------------


@pytest.fixture
def agent_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("HOLLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'hollow.db'}")
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_inbox_and_submit_commands(agent_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.agent_inbox([]) == 0
    out = capsys.readouterr().out
    assert "Inbox written to agents" in out and "- quest-master: quests:" in out
    inbox_file = next((agent_db / "agents" / "inbox").glob("*.json"))
    today = json.loads(inbox_file.read_text(encoding="utf-8"))["today"]
    result = agent_db / "quests.json"
    result.write_text(json.dumps(quests(day=today)), encoding="utf-8")
    assert cli.agent_submit([str(result)]) == 0
    assert "Saved quest-master result for quests:" in capsys.readouterr().out
    assert cli.agent_submit([str(result)]) == 1
    assert "already issued" in capsys.readouterr().err
    assert cli.agent_submit([]) == 2
    assert cli.agent_submit(["missing.json"]) == 1
    assert cli.agent_inbox([str(agent_db / "custom.json")]) == 0
    assert "Nothing is waiting" not in capsys.readouterr().out
