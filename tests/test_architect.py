from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.agents import AgentDesk, AgentError
from hollow.application.architect_lessons import ArchitectLessons, QuizRun
from hollow.application.fights import FightError, FightService
from hollow.application.lessons import LessonError
from hollow.curriculum import load
from hollow.domain.activities import Track
from hollow.domain.architect import (
    LORDS,
    PROVE_SOULS,
    REGION_BY_ID,
    REGIONS,
    TOPICS,
    ArchitectState,
    exam_score,
    lesson_id,
    region_topics,
)
from hollow.domain.atlas import ARCH_POINTS, ARCH_REGION_MAPS, FORGE, NodeKind
from hollow.domain.bosses import GOLEM, ChoiceQuestion, Outcome, choice
from hollow.domain.curriculum import MIN_QUIZ, CurriculumError, parse_region, parse_topic
from hollow.domain.events import AgentResult, LessonCompleted
from hollow.domain.world import WorldState, replay
from tests.conftest import FakeClock
from tests.test_world import CAL

HX = {"HX-Request": "true"}
MYPY = "mypy-strict-in-practice"
GIL = "concurrency-choices-threads-processes-async"
MVCC = "mvcc-and-isolation-levels"
FORGE_STEPS = [t.id for t in region_topics("forge")]
UNWRITTEN = region_topics("api-citadel")[0].id


def state(store: SqlEventStore, clock: FakeClock) -> WorldState:
    return replay(store.all(), CAL, CAL.day_of(clock.now()))


def clear(store: SqlEventStore, clock: FakeClock, topic_ids: list[str]) -> None:
    for topic_id in topic_ids:
        store.append(LessonCompleted(clock.now(), lesson_id(topic_id), 6, 6))
        clock.advance(seconds=1)


def right(run: QuizRun) -> list[str]:
    """The shown position of every right answer in a run."""
    return [str(run.order(n).index(q.answer)) for n, q in enumerate(run.questions)]


# --- the curriculum in the repo ---------------------------------------------------


def test_eight_regions_hold_every_step_once() -> None:
    assert len(REGIONS) == 8 and len(LORDS) == 9
    assert [r.number for r in REGIONS] == list(range(1, 9))
    assert len(TOPICS) == sum(len(r.topics) for r in REGIONS) == 82
    assert len(region_topics("distributed-abyss")) == max(len(r.topics) for r in REGIONS)
    assert all(r in REGION_BY_ID for lord in LORDS for r in lord.regions)
    assert all(t.why and t.abilities and t.exam for t in TOPICS.values())
    assert all(r.boss and r.start and r.blurb for r in REGIONS)


def test_the_forge_and_data_depths_are_written_and_the_rest_is_fog() -> None:
    assert [r.id for r in REGIONS[:2]] == ["forge", "data-depths"]
    assert all(r.written for r in REGIONS[:2])
    assert all(len(t.quiz) >= MIN_QUIZ for r in REGIONS[:2] for t in r.topics)
    assert not any(r.written for r in REGIONS[2:])
    for q in (q for t in TOPICS.values() for q in t.quiz):
        assert 0 <= q.answer < len(q.options) and q.explanation


def test_maps_and_boss_cover_the_curriculum() -> None:
    assert list(ARCH_POINTS) == [r.id for r in REGIONS]
    assert [n.lesson_id for n in FORGE if n.kind is NodeKind.LESSON] == FORGE_STEPS
    assert set(ARCH_REGION_MAPS) == {"forge"}
    phases = [t for p in GOLEM.phases for t in p.topics]
    assert sorted(phases) == sorted(FORGE_STEPS)


STEP = """# A Step: With Colons
> **Why this matters for you:** Because.

## You should be able to
- Do `one` thing

## Lesson
Some **text**.

```python
x = 1
```

## Quiz
### First?
- [ ] no
- [x] yes

Because yes.

### Second?
- [x] a
- [ ] b

## Exam questions
- Why?
"""


def test_a_step_file_parses() -> None:
    topic = parse_topic(STEP, "forge", 3, "x.md")
    assert (topic.id, topic.number, topic.title) == ("a-step-with-colons", 3, "A Step: With Colons")
    assert topic.why == "Because." and topic.abilities == ("Do `one` thing",)
    assert "```python\nx = 1\n```" in topic.lesson
    assert [q.answer for q in topic.quiz] == [1, 0]
    assert (
        topic.quiz[0].explanation == "Because yes." and topic.quiz[0].id == "a-step-with-colons#1"
    )
    assert topic.exam == ("Why?",)
    assert not topic.playable  # only two quiz questions


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no title", "no '# Title'"),
        ("# T\n## Quiz\n### Q?\n- [x] a\n- [x] b\n", "two right answers"),
        ("# T\n## Quiz\n### Q?\n- [ ] a\n- [ ] b\n", "one marked"),
    ],
)
def test_broken_step_files_are_refused(text: str, message: str) -> None:
    with pytest.raises(CurriculumError, match=message):
        parse_topic(text, "forge", 1, "x.md")


def test_region_files_need_their_front_matter() -> None:
    with pytest.raises(CurriculumError, match="front matter"):
        parse_region("# Nope", 1, (), "r.md")
    with pytest.raises(CurriculumError, match="missing boss"):
        parse_region("---\nid: a\nname: A\ncovers: c\nstart: s\nboss_blurb: b\nbuild: b\n---\n",
                     1, (), "r.md")  # fmt: skip


def test_load_reads_folders_in_order(tmp_path: Path) -> None:
    folder = tmp_path / "01-only"
    folder.mkdir()
    (folder / "README.md").write_text(
        "---\nid: only\nname: Only\ncovers: c\nstart: s: here\nboss: B\nboss_blurb: bb\n"
        "build: b\n---\n# 1. Only\n\nThe blurb.\n\nMore.\n",
        encoding="utf-8",
    )
    (folder / "01-step.md").write_text(STEP, encoding="utf-8")
    (tmp_path / "notes").mkdir()  # not numbered: ignored
    (region,) = load(tmp_path)
    assert (region.id, region.start, region.blurb) == ("only", "s: here", "The blurb.")
    assert region.topics[0].path.endswith("01-only/01-step.md")
    (tmp_path / "02-empty").mkdir()
    with pytest.raises(CurriculumError, match="no README"):
        load(tmp_path)


# --- progress -----------------------------------------------------------------------


def test_a_cleared_quiz_clears_the_step_for_the_architect(
    store: SqlEventStore, clock: FakeClock
) -> None:
    clear(store, clock, [MYPY])
    world = state(store, clock)
    step = world.architect.topics[MYPY]
    assert step.cleared and not step.proved
    assert world.lit_today
    assert world.jobs[Track.ARCHITECT].xp == 30 and world.jobs[Track.RONIN].xp == 0


def test_exams_prove_steps_and_pay_once(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(AgentResult(clock.now(), "tech-lead", f"exam:{MYPY}", {"total": 0.6}))
    topic = state(store, clock).architect.topics[MYPY]
    assert (topic.proved, topic.best, topic.cleared) == (False, 0.6, False)
    store.append(AgentResult(clock.now(), "tech-lead", f"exam:{MYPY}", {"total": 0.9}))
    store.append(AgentResult(clock.now(), "tech-lead", f"exam:{MYPY}", {"total": 1.0}))
    world = state(store, clock)
    assert world.architect.topics[MYPY].cleared
    assert world.souls == PROVE_SOULS == world.jobs[Track.ARCHITECT].xp


def test_placement_clears_known_steps_without_souls(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(AgentResult(clock.now(), "tech-lead", "placement:forge",
                             {"cleared": [GIL, MVCC, "nope"]}))  # fmt: skip
    world = state(store, clock)
    assert world.architect.topics[GIL].placed and world.architect.topics[GIL].cleared
    assert not world.architect.topics[MVCC].proved  # not a Forge step
    assert world.souls == 0


def test_only_the_forge_is_open_until_its_boss_falls(
    store: SqlEventStore, clock: FakeClock
) -> None:
    arch = state(store, clock).architect
    assert arch.region_open("forge")
    assert not arch.region_open("data-depths")  # the Golem still stands
    assert not arch.region_ready("forge")
    clear(store, clock, FORGE_STEPS)
    assert state(store, clock).architect.region_ready("forge")


def test_a_written_region_waits_for_its_map() -> None:
    golem_down = ArchitectState({}, set(), [], {"forge"})
    assert REGION_BY_ID["data-depths"].written and "data-depths" not in ARCH_REGION_MAPS
    assert not golem_down.region_open("data-depths")  # no map to walk yet


def test_lords_open_when_their_regions_bosses_fall() -> None:
    by_name = {lord.name: lord for lord in LORDS}
    arch = ArchitectState({}, set(), [], {"data-depths"})
    assert arch.lord_open(by_name["Rate Limiter"])
    assert not arch.lord_open(by_name["URL Shortener"])  # also needs the API Citadel


def test_exam_scores_come_from_rubric_points() -> None:
    questions = [{"q": "a", "answer": "b", "score": 3, "rubric": "r"},
                 {"q": "c", "answer": "d", "score": 1, "rubric": "r"}]  # fmt: skip
    assert exam_score({"questions": questions}) == pytest.approx(4 / 6)
    assert exam_score({"questions": ["just text"]}) == 0.0


# --- lessons ------------------------------------------------------------------------


def test_a_quiz_run_grades_shown_positions(store: SqlEventStore, clock: FakeClock) -> None:
    service = ArchitectLessons(store, clock, CAL)
    run = service.start(MYPY)
    assert sorted(q.id for q in run.questions) == sorted(q.id for q in TOPICS[MYPY].quiz)
    again = service.resume(MYPY, str(run.id), [q.id for q in run.questions])
    assert again.order(0) == run.order(0)  # the order comes from the run id
    answers = right(run)
    assert all(run.grade(answers)) and not run.accepts(0, "x") and not run.accepts(0, "9")
    wrong = ["0" if a != "0" else "1" for a in answers]
    assert not any(run.grade(wrong))
    outcome, _, world = service.finish(run, answers, roll=0.99)
    assert outcome.passed and world.architect.topics[MYPY].cleared
    service.finish(run, answers, roll=0.99)  # a resubmit records nothing new
    assert len(world.lessons[lesson_id(MYPY)].history) == 1


@pytest.mark.parametrize(
    ("topic", "asked", "message"),
    [
        ("nope", [f"{MYPY}#1"], "no Architect step"),
        (UNWRITTEN, [f"{UNWRITTEN}#1"], "has no lesson yet"),
        (MVCC, [f"{MVCC}#1"], "Data Depths is still in the fog"),
        (MYPY, [f"{GIL}#1"], "does not match"),
        (MYPY, [f"{MYPY}#1", f"{MYPY}#1"], "does not match"),
    ],
)
def test_tampered_or_closed_quizzes_are_refused(
    store: SqlEventStore, clock: FakeClock, topic: str, asked: list[str], message: str
) -> None:
    with pytest.raises(LessonError, match=message):
        ArchitectLessons(store, clock, CAL).resume(topic, str(uuid4()), asked)


def test_finishing_needs_every_answer(store: SqlEventStore, clock: FakeClock) -> None:
    service = ArchitectLessons(store, clock, CAL)
    with pytest.raises(LessonError, match="Answer every question"):
        service.finish(service.start(MYPY), ["0"])
    with pytest.raises(LessonError, match="broken"):
        service.resume(MYPY, "not-a-uuid", [f"{MYPY}#1"])


# --- the Strict Golem ---------------------------------------------------------------


def test_choice_questions_are_stable_and_walk_the_pool() -> None:
    phase = GOLEM.phases[0]
    asked = [choice(phase, 7, turn).question_id for turn in range(24)]
    assert asked == [choice(phase, 7, turn).question_id for turn in range(24)]
    assert len(set(asked)) == 24  # every question once before any repeats
    q = choice(phase, 7, 0)
    assert q.accepts(str(q.order.index(q.quiz.answer)))
    assert not q.accepts("nope") and q.topic and q.answers[0] in q.options


def test_the_golem_waits_for_every_forge_step(store: SqlEventStore, clock: FakeClock) -> None:
    fights = FightService(store, clock, CAL)
    assert not fights.ready(GOLEM.id)
    with pytest.raises(FightError, match="every step of the Forge"):
        fights.enter(GOLEM.id)
    clear(store, clock, FORGE_STEPS)
    assert fights.ready(GOLEM.id)


def test_felling_the_golem_pays_the_architect(store: SqlEventStore, clock: FakeClock) -> None:
    clear(store, clock, FORGE_STEPS)
    fights = FightService(store, clock, CAL)
    view = fights.enter(GOLEM.id)
    while view.record.current is not None:
        attempt, ask = view.record.current, view.question
        assert isinstance(ask, ChoiceQuestion)
        view = fights.answer(GOLEM.id, str(attempt.id), attempt.turns,
                             str(ask.order.index(ask.quiz.answer)))  # fmt: skip
    assert view.record.last is not None and view.record.last.outcome is Outcome.WON
    world = view.state
    assert "forge" in world.architect.felled
    assert world.armory.owns("golem-fist")
    assert world.jobs[Track.ARCHITECT].xp > world.jobs[Track.RONIN].xp == 0


# --- agents ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ({"task": "exam:nope", "total": 1.0}, "No Architect topic"),
        ({"task": "placement:nope", "cleared": []}, "No Architect region"),
        ({"task": "placement:forge", "cleared": [MVCC]}, "Not topics of forge"),
        ({"task": f"exam:{MYPY}", "total": 1.0, "cleared": [MYPY]}, "Only placement"),
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


def test_inbox_offers_open_placements_and_exams(store: SqlEventStore, clock: FakeClock) -> None:
    clear(store, clock, [MYPY])
    inbox = AgentDesk(store, clock, CAL).inbox()
    tasks = {t["task"] for t in inbox["tasks"]}
    assert {"placement:forge", f"exam:{MYPY}"} <= tasks
    assert "placement:data-depths" not in tasks  # still in the fog
    regions = {r["id"]: r for r in inbox["context"]["architect"]["regions"]}
    assert regions["forge"]["open"] and not regions["data-depths"]["open"]
    step = next(t for t in regions["forge"]["topics"] if t["id"] == MYPY)
    assert step["lesson_cleared"] and step["file"].endswith("01-mypy-strict-in-practice.md")


# --- pages ----------------------------------------------------------------------------


def test_the_map_has_two_roads(client: TestClient) -> None:
    ronin = client.get("/map")
    assert 'class="road ronin" href="/map?road=ronin" aria-current="page"' in ronin.text
    assert "Firelink Shrine" in ronin.text
    arch = client.get("/map?road=architect")
    assert arch.cookies.get("hollow_road") == "architect"
    page = arch.text
    assert "map_architect.png" in page and "road-architect" in page
    assert 'href="/map/architect/forge" data-action' in page
    assert "In the fog: its lessons are not written yet." in page  # the API Citadel
    assert "In the fog: its paths are not charted yet." in page  # Data Depths
    assert "Needs Data Depths, The API Citadel" in page and "Needs every region" in page
    assert "map_architect.png" in client.get("/map").text  # the cookie remembers the road
    assert 'href="/architect"' not in page  # the old tab is gone
    assert client.get("/architect", follow_redirects=False).headers["location"] == (
        "/map?road=architect"
    )


def test_the_forge_map(client: TestClient, store: SqlEventStore, clock: FakeClock) -> None:
    clear(store, clock, [MYPY])
    page = client.get("/map/architect/forge").text
    assert "region_forge.png" in page and "Region 1 · The Forge · 12% explored" in page
    assert f'href="/lessons/arch/{GIL}" data-action>Read the lesson' in page
    assert "Step 1 · The Forge" in page and "Cleared. Back as a refresher" in page
    assert "It parts when every step here is cleared (1 of 8)." in page
    gone = client.get("/map/architect/data-depths", follow_redirects=False)
    assert gone.status_code == 303 and "at=data-depths" in gone.headers["location"]
    assert client.get("/map/architect/nope").status_code == 404


def test_a_lesson_page_and_a_whole_quiz(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    page = client.get(f"/lessons/arch/{MYPY}").text
    assert "<code>list[Child]</code>" in page and "<pre><code" in page
    assert "Take the quiz" in page and f"exam on <code>{MYPY}</code>" in page
    start = client.post(f"/lessons/arch/{MYPY}/start", headers=HX).text
    assert 'name="answer" value="0"' in start and "data-choices" in start
    run_id = start.split('name="run" value="')[1].split('"')[0]
    asked = [chunk.split('"')[0] for chunk in start.split('name="q" value="')[1:]]
    run = ArchitectLessons(store, clock, CAL).resume(MYPY, run_id, asked)
    answers = right(run)
    form = {"run": run_id, "q": asked, "a": answers[:-1], "answer": answers[-1]}
    assert "Correct" in client.post(f"/lessons/arch/{MYPY}/answer", data=form, headers=HX).text
    form = {"run": run_id, "q": asked, "a": answers}
    done = client.post(f"/lessons/arch/{MYPY}/finish", data=form, headers=HX).text
    assert "Step cleared" in done and "+30 souls" in done
    lessons = client.get("/lessons").text
    assert "Architect · Region 1 · The Forge" in lessons and "Back " in lessons
    assert "Lesson · mypy --strict in Practice: 6/6" in client.get("/").text


def test_quiz_pages_refuse_bad_runs(client: TestClient) -> None:
    bad = {"run": str(uuid4()), "q": [f"{GIL}#1"], "answer": "0"}
    assert client.post(f"/lessons/arch/{MYPY}/answer", data=bad).status_code == 422
    assert client.post("/lessons/arch/nope/start").status_code == 422
    assert "has no lesson yet" in client.get(f"/lessons/arch/{UNWRITTEN}").text
    assert "Data Depths is still in the fog" in client.get(f"/lessons/arch/{MVCC}").text


def test_the_golem_gate(client: TestClient, store: SqlEventStore, clock: FakeClock) -> None:
    page = client.get(f"/boss/{GOLEM.id}").text
    assert "Fog gate · the Forge" in page and "golem_body.png" in page
    assert "every step of the Forge is cleared" in page
    clear(store, clock, FORGE_STEPS)
    clock.advance(seconds=1)
    fight = client.post(f"/boss/{GOLEM.id}/enter", headers=HX).text
    assert 'name="answer" value="0"' in fight and "road-architect" in fight
