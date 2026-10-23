import json
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hollow import cli
from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.vault import Vault
from hollow.adapters.web.app import create_app
from hollow.application.agents import AgentDesk, AgentError
from hollow.application.vault_sync import VaultSync
from hollow.config import Settings
from hollow.domain.activities import Track
from hollow.domain.architect import (
    LEARN_SOULS,
    LEARN_WORDS,
    LORDS,
    PROVE_SOULS,
    REGION_BY_ID,
    REGIONS,
    TOPICS,
    exam_score,
    region_topics,
)
from hollow.domain.events import AgentResult, NoteWritten
from hollow.domain.world import WorldState, replay
from tests.conftest import FakeClock
from tests.test_world import CAL

HX = {"HX-Request": "true"}
MVCC = "02 - Data Depths/MVCC and Isolation Levels.md"
M = "mvcc-and-isolation-levels"
GIL = "concurrency-choices-threads-processes-async"
TEMPLATE = "## You should be able to\n- [ ] Explain it\n\n## Exam questions\n- Why?\n\n" \
    "## My notes\nWrite in your own words. Only this section counts.\n"  # fmt: skip


def state(store: SqlEventStore, clock: FakeClock) -> WorldState:
    return replay(store.all(), CAL, CAL.day_of(clock.now()))


def write_vault(root: Path, notes: dict[str, str]) -> None:
    for i in range(10):  # enough notes for the template lines to be recognised
        path = root / "filler" / f"Note {i}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Note {i}\n\n{TEMPLATE}", encoding="utf-8")
    for rel, own in notes.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n\n{TEMPLATE}\n{own}\n", encoding="utf-8")
    (root / ".obsidian").mkdir(exist_ok=True)
    (root / ".obsidian" / "skip.md").write_text("ignored", encoding="utf-8")


class FakeVault:
    def __init__(self, words: dict[str, int], available: bool = True) -> None:
        self.words, self._available = words, available

    def available(self) -> bool:
        return self._available

    def own_words(self, notes: list[str]) -> dict[str, int]:
        return {n: w for n, w in self.words.items() if n in notes}


# --- atlas --------------------------------------------------------------------


def test_eight_regions_hold_every_topic_once() -> None:
    assert len(REGIONS) == 8 and len(LORDS) == 9
    notes = [t.note for t in TOPICS.values()]
    assert len(notes) == len(set(notes)) == len(TOPICS) == 82
    assert sum(len(region_topics(r.id)) for r in REGIONS) == len(TOPICS)
    assert all(r in REGION_BY_ID for lord in LORDS for r in lord.regions)
    abyss = len(region_topics("distributed-abyss"))
    assert abyss == max(len(region_topics(r.id)) for r in REGIONS)
    assert Counter(t.title for t in TOPICS.values()).most_common(1)[0][1] == 1


# --- vault --------------------------------------------------------------------


def test_only_your_own_words_count(tmp_path: Path) -> None:
    write_vault(tmp_path, {MVCC: "Readers never block writers: each row keeps versions."})
    (tmp_path / "old.md").write_text("# Old\nSome archived words here\n", encoding="utf-8")
    words = Vault(tmp_path).own_words([MVCC, "old.md", "missing.md"])
    assert words == {MVCC: 8, "old.md": 4}
    assert not Vault(tmp_path / "nope").available()


def test_only_the_my_notes_section_counts(tmp_path: Path) -> None:
    write_vault(tmp_path, {})
    (tmp_path / "note.md").write_text(
        "# T\n> Why this matters: lots of words before\n## My notes\n"
        "Write in your own words. Only this section counts.\nfour words of mine\n"
        "## Later section\nnot counted at all\n",
        encoding="utf-8",
    )
    assert Vault(tmp_path).own_words(["note.md"]) == {"note.md": 4}


def test_unreadable_notes_are_skipped(tmp_path: Path) -> None:
    write_vault(tmp_path, {})
    (tmp_path / "broken.md").write_bytes(b"\xff\xfe\xfa")
    assert Vault(tmp_path).own_words(["broken.md"]) == {}


def test_vault_sync_records_notes_that_grew(store: SqlEventStore, clock: FakeClock) -> None:
    vault = FakeVault({MVCC: 10})
    sync = VaultSync(store, vault, clock)
    assert sync.run() == 0  # under the 20-word step
    vault.words[MVCC] = 140
    assert sync.run() == 1
    vault.words[MVCC] = 150  # crosses the Learn mark: recorded even though +10
    assert sync.run() == 1
    assert sync.run() == 0
    assert [e.words for e in store.all() if isinstance(e, NoteWritten)] == [140, 150]
    assert VaultSync(store, FakeVault({}, available=False), clock).run() == 0


# --- gates --------------------------------------------------------------------


def test_learn_and_prove_pay_once_and_feed_the_architect(
    store: SqlEventStore, clock: FakeClock
) -> None:
    store.append(NoteWritten(clock.now(), M, LEARN_WORDS))
    store.append(NoteWritten(clock.now(), M, LEARN_WORDS + 40))
    exam = {"total": 0.6}
    store.append(AgentResult(clock.now(), "tech-lead", f"exam:{M}", exam))
    world = state(store, clock)
    topic = world.architect.topics[M]
    assert (topic.learned, topic.proved, topic.best) == (True, False, 0.6)
    assert world.lit_today
    store.append(AgentResult(clock.now(), "tech-lead", f"exam:{M}", {"total": 0.9}))
    store.append(AgentResult(clock.now(), "tech-lead", f"exam:{M}", {"total": 1.0}))
    world = state(store, clock)
    assert world.architect.topics[M].proved
    assert world.souls == LEARN_SOULS + PROVE_SOULS
    assert world.jobs[Track.ARCHITECT].xp == LEARN_SOULS + PROVE_SOULS


def test_placement_clears_known_topics_without_souls(
    store: SqlEventStore, clock: FakeClock
) -> None:
    store.append(AgentResult(clock.now(), "tech-lead", "placement:forge",
                             {"cleared": [GIL, M, "nope"]}))  # fmt: skip
    world = state(store, clock)
    assert world.architect.topics[GIL].placed
    assert not world.architect.topics[M].proved  # not a Forge topic
    assert "forge" in world.architect.placed_regions
    assert world.souls == 0


def test_regions_clear_at_80_percent_and_open_lords(store: SqlEventStore, clock: FakeClock) -> None:
    ids = [t.id for t in region_topics("data-depths")]
    store.append(AgentResult(clock.now(), "tech-lead", "placement:data-depths",
                             {"cleared": ids[: int(len(ids) * 0.8) + 1]}))  # fmt: skip
    arch = state(store, clock).architect
    assert arch.region_cleared("data-depths")
    by_name = {lord.name: lord for lord in LORDS}
    assert arch.lord_open(by_name["Rate Limiter"])
    assert not arch.lord_open(by_name["URL Shortener"])  # also needs the API Citadel


def test_exam_scores_come_from_rubric_points() -> None:
    questions = [{"q": "a", "answer": "b", "score": 3, "rubric": "r"},
                 {"q": "c", "answer": "d", "score": 1, "rubric": "r"}]  # fmt: skip
    assert exam_score({"questions": questions}) == pytest.approx(4 / 6)
    assert exam_score({"questions": ["just text"]}) == 0.0


# --- agents -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ({"task": "exam:nope", "total": 1.0}, "No Architect topic"),
        ({"task": "placement:nope", "cleared": []}, "No Architect region"),
        ({"task": "placement:forge", "cleared": [M]}, "Not topics of forge"),
        ({"task": f"exam:{M}", "total": 1.0, "cleared": [M]}, "Only placement"),
    ],
)
def test_tech_lead_results_are_checked(
    store: SqlEventStore, clock: FakeClock, result: dict[str, object], message: str
) -> None:
    with pytest.raises(AgentError, match=message):
        AgentDesk(store, clock, CAL).submit({"agent": "tech-lead", **result})


def test_one_placement_trial_per_region(store: SqlEventStore, clock: FakeClock) -> None:
    desk = AgentDesk(store, clock, CAL)
    desk.submit({"agent": "tech-lead", "task": "placement:forge", "cleared": [GIL]})
    with pytest.raises(AgentError, match="already had its placement"):
        desk.submit({"agent": "tech-lead", "task": "placement:forge", "cleared": []})
    desk.submit({"agent": "tech-lead", "task": f"exam:{M}", "total": 0.85})
    assert state(store, clock).architect.topics[M].proved


def test_inbox_offers_placements_and_exams(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(NoteWritten(clock.now(), M, 200))
    inbox = AgentDesk(store, clock, CAL).inbox()
    tasks = {t["task"] for t in inbox["tasks"]}
    assert {"placement:forge", f"exam:{M}"} <= tasks
    regions = {r["id"]: r for r in inbox["context"]["architect"]["regions"]}
    mvcc = next(t for t in regions["data-depths"]["topics"] if t["id"] == M)
    assert mvcc == {"id": M, "title": "MVCC and Isolation Levels", "note": MVCC, "words": 200,
                    "learned": True, "proved": False, "best": None}  # fmt: skip


# --- pages --------------------------------------------------------------------


def test_architect_pages(client: TestClient, store: SqlEventStore, clock: FakeClock) -> None:
    store.append(NoteWritten(clock.now(), M, 90))
    page = client.get("/architect").text
    assert 'href="/architect" aria-current="page"' in page
    assert "The Distributed Abyss" in page and "0 of 82 topics proved" in page
    assert "Needs Data Depths, The API Citadel" in page
    region = client.get("/architect/data-depths").text
    assert "90 / 150 words in My notes" in region
    assert (
        "obsidian://open?vault=Senior%20Backend%20Roadmap&amp;file=02%20-%20Data%20Depths" in region
    )
    assert "you model and query PostgreSQL" in region
    assert client.get("/architect/nope").status_code == 404


def test_vault_syncs_in_the_background(store: SqlEventStore, clock: FakeClock) -> None:
    settings = Settings(database_url="sqlite://", vault_path="D:/Vaults/Roadmap", _env_file=None)
    vault = FakeVault({MVCC: 160})
    with TestClient(create_app(settings, store=store, clock=clock, vault=vault)) as client:
        assert 'hx-post="/sync?page=bonfire"' in client.get("/").text
        assert "Vault: 1 note updated." in client.post("/sync", headers=HX).text
        assert "vault=Roadmap" in client.get("/architect/data-depths").text


def test_settings_build_a_real_vault(
    store: SqlEventStore, clock: FakeClock, tmp_path: Path
) -> None:
    write_vault(tmp_path, {MVCC: " ".join(["word"] * 30)})
    settings = Settings(database_url="sqlite://", vault_path=str(tmp_path), _env_file=None)
    with TestClient(create_app(settings, store=store, clock=clock)) as client:
        assert "Vault: 1 note updated." in client.post("/sync", headers=HX).text


def test_inbox_command_scans_the_vault_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    vault = tmp_path / "vault"
    write_vault(vault, {MVCC: " ".join(["word"] * 200)})
    monkeypatch.setenv("HOLLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'hollow.db'}")
    monkeypatch.setenv("HOLLOW_VAULT_PATH", str(vault))
    command.upgrade(Config(str(root / "alembic.ini")), "head")
    monkeypatch.chdir(tmp_path)
    assert cli.agent_inbox([str(tmp_path / "inbox.json")]) == 0
    assert "Vault scanned: 1 note updated." in capsys.readouterr().out
    inbox = json.loads((tmp_path / "inbox.json").read_text(encoding="utf-8"))
    assert f"exam:{M}" in {t["task"] for t in inbox["tasks"]}
