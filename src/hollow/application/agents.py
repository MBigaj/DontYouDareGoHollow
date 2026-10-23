"""The handoff between the game and its agents (Claude, in a session).

`inbox` exports what the game is waiting for, with the context each task needs.
`submit` validates an agent's JSON against its playbook (agents/*.md) and the game's own
rules, then stores it as an AgentResult. Nothing here awards anything: the replay does.
"""

import json
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from hollow.application.ports import Clock, EventStore, next_moment
from hollow.domain.activities import ActivityKind
from hollow.domain.architect import PROVE_MARK, REGION_BY_ID, TOPICS
from hollow.domain.architect import REGIONS as ARCHITECT_REGIONS
from hollow.domain.armory import MATERIAL_NAMES, WEAPONS
from hollow.domain.atlas import REGIONS
from hollow.domain.bosses import BOSSES, question
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import (
    AgentResult,
    LessonCompleted,
    Material,
    StudyLogged,
    WordLearned,
)
from hollow.domain.lessons import LESSONS
from hollow.domain.quests import issued
from hollow.domain.vocabulary import known_verbs
from hollow.domain.world import WorldState, replay

WEAK_DAYS = 14
LORE_PER_ROUND = 3


class AgentError(ValueError):
    """A result that does not match its playbook or the game's rules. Nothing was saved."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Quest Master -------------------------------------------------------------


class LessonCheck(Strict):
    kind: Literal["lesson"]
    lesson_id: str
    min_score: float = Field(0.8, ge=0, le=1)


class AnkiCheck(Strict):
    kind: Literal["anki"]
    reviews: int = Field(0, ge=0, le=500)
    new_cards: int = Field(0, ge=0, le=100)


class StudyCheck(Strict):
    kind: Literal["study"]
    activity: ActivityKind
    amount: int = Field(ge=1, le=600)


class BossCheck(Strict):
    kind: Literal["boss"]
    boss_id: str
    phase: int = Field(ge=1, le=5)


class JudgedCheck(Strict):
    kind: Literal["judged"]
    judge: Literal["sensei", "tech-lead"]
    rubric: str = Field(max_length=200)


Check = Annotated[
    LessonCheck | AnkiCheck | StudyCheck | BossCheck | JudgedCheck, Field(discriminator="kind")
]


class QuestIn(Strict):
    id: str = Field(max_length=40)
    title: str = Field(max_length=80)
    why: str = Field("", max_length=200)
    check: Check
    bonus_souls: int = Field(ge=0, le=1000)


class QuestMaster(Strict):
    agent: Literal["quest-master"]
    day: date
    quests: list[QuestIn] = Field(min_length=1, max_length=3)
    roulette: QuestIn | None = None


# --- Sensei -------------------------------------------------------------------

Reading = tuple[str, str]


class NewWord(Strict):
    word: str
    kana: str
    meaning: str


class Turn(Strict):
    prompt: str = Field(max_length=200)
    readings: list[Reading] = []
    reply: str = Field(max_length=200)
    ok: bool


class Correction(Strict):
    wrote: str = Field(max_length=100)
    better: str = Field(max_length=100)
    why: str = Field(max_length=200)


class Sensei(Strict):
    agent: Literal["sensei"]
    task: str = Field(pattern=r"^(quest:[\w-]+|boss:[\w-]+:[\w-]+:phase-\d)$")
    passed: bool
    score: float | None = Field(None, ge=0, le=1)
    submission: str = Field("", max_length=1000)
    """What you wrote, for the journal."""
    turns: list[Turn] = Field([], max_length=8)
    corrections: list[Correction] = Field([], max_length=3)
    new_word: NewWord | None = None


# --- Lorekeeper ---------------------------------------------------------------


class LoreText(Strict):
    target: str = Field(pattern=r"^(weapon|material|region):[\w-]+$")
    ja: str = Field(max_length=160)
    readings: list[Reading] = []
    en: str = Field(max_length=300)
    new_word: NewWord | None = None


class Lorekeeper(Strict):
    agent: Literal["lorekeeper"]
    texts: list[LoreText] = Field(min_length=1, max_length=5)


# --- Tech Lead ----------------------------------------------------------------


class Issue(Strict):
    file: str = Field(max_length=200)
    line: int | None = None
    severity: Literal["blocker", "major", "minor"]
    note: str = Field(max_length=400)


class ExamQuestion(Strict):
    q: str = Field(max_length=400)
    answer: str = Field(max_length=4000)
    score: int = Field(ge=0, le=3)
    rubric: str = Field(max_length=400)


class TechLead(Strict):
    agent: Literal["tech-lead"]
    task: str = Field(pattern=r"^(review:[\w./-]+#\d+|exam:[\w-]+|placement:[\w-]+)$")
    verdict: Literal["pass", "changes"] | None = None
    strengths: list[str] = Field([], max_length=5)
    issues: list[Issue] = Field([], max_length=5)
    questions: list[str | ExamQuestion] = Field([], max_length=10)
    total: float | None = Field(None, ge=0, le=1)
    follow_up: str = Field("", max_length=400)
    cleared: list[str] = Field([], max_length=60)
    """Placement trials only: topic ids answered well enough to skip."""


Submission = Annotated[QuestMaster | Sensei | Lorekeeper | TechLead, Field(discriminator="agent")]
SUBMISSION: TypeAdapter[Submission] = TypeAdapter(Submission)


def lore_targets() -> dict[str, str]:
    """Everything the Lorekeeper can write about, with a display name."""
    targets = {f"weapon:{w.id}": w.name for w in WEAPONS.values()}
    targets |= {f"material:{m.value}": MATERIAL_NAMES[m] for m in Material}
    targets |= {f"region:{r.id}": r.name for r in REGIONS}
    return targets


class AgentDesk:
    def __init__(self, store: EventStore, clock: Clock, calendar: GameCalendar) -> None:
        self._store = store
        self._clock = clock
        self._calendar = calendar

    def state(self) -> WorldState:
        return replay(self._store.all(), self._calendar, self._calendar.day_of(self._clock.now()))

    # --- submit ---------------------------------------------------------------

    def submit(self, raw: str | bytes | dict[str, Any]) -> list[AgentResult]:
        """Validates one agent result and stores it. Raises AgentError, saving nothing."""
        try:
            data = json.loads(raw) if isinstance(raw, str | bytes) else raw
            result = SUBMISSION.validate_python(data)
        except (ValidationError, json.JSONDecodeError) as error:
            raise AgentError(f"The result does not match its playbook:\n{error}") from None
        state = self.state()
        events = self._store.all()
        now = next_moment(self._store, self._clock)
        payload = result.model_dump(mode="json")
        if isinstance(result, QuestMaster):
            self._check_quests(result, state, events)
            saved = [AgentResult(now, "quest-master", f"quests:{result.day}", payload)]
        elif isinstance(result, Sensei):
            self._check_judgement(result, state)
            saved = [AgentResult(now, "sensei", result.task, payload)]
        elif isinstance(result, Lorekeeper):
            targets = lore_targets()
            unknown = [t.target for t in result.texts if t.target not in targets]
            if unknown:
                raise AgentError(f"Unknown lore targets: {', '.join(unknown)}.")
            saved = [
                AgentResult(now, "lorekeeper", text.target, text.model_dump(mode="json"))
                for text in result.texts
            ]
        else:
            self._check_tech_lead(result, state)
            saved = [AgentResult(now, "tech-lead", result.task, payload)]
        for event in saved:
            self._store.append(event)
        return saved

    def _check_quests(self, result: QuestMaster, state: WorldState, events: Any) -> None:
        if result.day != state.today:
            raise AgentError(f"Quests are for today ({state.today}), not {result.day}.")
        if state.today in issued(events):
            raise AgentError("Today's quests were already issued.")
        quests = [*result.quests, *([result.roulette] if result.roulette else [])]
        ids = [q.id for q in quests]
        if len(set(ids)) != len(ids):
            raise AgentError("Quest ids must be unique.")
        for q in quests:
            check = q.check
            if isinstance(check, LessonCheck) and check.lesson_id not in LESSONS:
                raise AgentError(f"No lesson called {check.lesson_id}.")
            if isinstance(check, BossCheck) and check.boss_id not in BOSSES:
                raise AgentError(f"No boss called {check.boss_id}.")

    @staticmethod
    def _check_tech_lead(result: TechLead, state: WorldState) -> None:
        kind, _, key = result.task.partition(":")
        if kind == "exam" and key not in TOPICS:
            raise AgentError(f"No Architect topic called {key}; use a topic id from the inbox.")
        if kind == "placement":
            if key not in REGION_BY_ID:
                raise AgentError(f"No Architect region called {key}.")
            if key in state.architect.placed_regions:
                raise AgentError(f"{REGION_BY_ID[key].name} already had its placement trial.")
            outside = [t for t in result.cleared if t not in TOPICS or TOPICS[t].region != key]
            if outside:
                raise AgentError(f"Not topics of {key}: {', '.join(outside)}.")
        elif result.cleared:
            raise AgentError("Only placement trials can clear topics directly.")

    def _check_judgement(self, result: Sensei, state: WorldState) -> None:
        if not result.task.startswith("quest:"):
            raise AgentError("Boss phase 3 is not built yet; only quest judgements are saved.")
        quest_id = result.task.removeprefix("quest:")
        judged = {s.quest.id: s for s in state.quests if s.quest.judged}
        if quest_id not in judged:
            raise AgentError(f"No judged quest {quest_id} today.")
        if judged[quest_id].done:
            raise AgentError(f"Quest {quest_id} is already passed.")

    # --- inbox ----------------------------------------------------------------

    def inbox(self) -> dict[str, Any]:
        """Pending agent tasks and the context they need, as plain JSON."""
        events = list(self._store.all())
        state = self.state()
        today = state.today
        tasks: list[dict[str, Any]] = []
        if today not in issued(events):
            tasks.append({"agent": "quest-master", "task": f"quests:{today}",
                          "do": "Issue today's quests (agents/quest-master.md)."})  # fmt: skip
        for status in state.quests:
            if status.quest.judged and not status.done:
                tasks.append({
                    "agent": status.quest.check.get("judge", "sensei"),
                    "task": f"quest:{status.quest.id}",
                    "do": f"Judge when the player submits: {status.quest.title}",
                    "rubric": status.quest.check.get("rubric", ""),
                })  # fmt: skip
        written = {e.task for e in events if isinstance(e, AgentResult) and e.agent == "lorekeeper"}
        wanted = [f"weapon:{w}" for w in state.armory.levels] + [
            f"material:{m.value}" for m, n in state.armory.materials.items() if n
        ]
        for target in [t for t in wanted if t not in written][:LORE_PER_ROUND]:
            tasks.append({"agent": "lorekeeper", "task": target, "name": lore_targets()[target],
                          "do": "Write its lore (agents/lorekeeper.md)."})  # fmt: skip
        reviewed = {e.task for e in events if isinstance(e, AgentResult) and e.agent == "tech-lead"}
        for pr in self._pull_requests(events):
            task = f"review:{pr['ref']}"
            if task not in reviewed:
                tasks.append({"agent": "tech-lead", "task": task, "title": pr["title"],
                              "do": "Review it with gh pr view and gh pr diff."})  # fmt: skip
        arch = state.architect
        unplaced = [r for r in ARCHITECT_REGIONS if r.id not in arch.placed_regions]
        if unplaced:
            region = unplaced[0]
            tasks.append({"agent": "tech-lead", "task": f"placement:{region.id}",
                          "name": region.name,
                          "do": "Optional, when the player has 30 minutes: this region's "
                                "placement trial (agents/tech-lead.md)."})  # fmt: skip
        ready = [s for s in arch.topics.values() if s.learned and not s.proved][:3]
        for topic_state in ready:
            tasks.append({"agent": "tech-lead", "task": f"exam:{topic_state.topic.id}",
                          "name": topic_state.topic.title,
                          "do": "Notes written: offer the Prove exam."})  # fmt: skip
        return {
            "generated_at": self._clock.now().isoformat(),
            "today": today.isoformat(),
            "tasks": tasks,
            "context": self._context(events, state),
        }

    @staticmethod
    def _pull_requests(events: list[Any]) -> list[dict[str, str]]:
        prs = []
        for e in events:
            if isinstance(e, StudyLogged) and e.kind is ActivityKind.PULL_REQUEST and "#" in e.note:
                ref, _, title = e.note.partition(" ")
                prs.append({"ref": ref, "title": title, "merged": e.occurred_at.isoformat()})
        return prs

    @staticmethod
    def _weak_verbs(events: list[Any], state: WorldState, since: datetime) -> list[dict[str, Any]]:
        """Verbs missed most in lessons and fights since `since`."""
        misses: Counter[str] = Counter()
        for e in events:
            if isinstance(e, LessonCompleted) and e.occurred_at >= since:
                misses.update(e.missed)
        verbs = known_verbs(events)
        for record in state.bosses.values():
            for t in record.log:
                if not t.correct and t.at >= since:
                    asked = question(record.boss, t.phase, t.seed, t.turn, verbs)
                    misses.update(v.written for v in asked.verbs)
        kana = {v.written: v.kana for v in verbs}
        top = misses.most_common(8)
        return [{"written": w, "kana": kana.get(w, ""), "misses": n} for w, n in top]

    def _context(self, events: list[Any], state: WorldState) -> dict[str, Any]:
        today = state.today
        since = datetime.combine(today - timedelta(days=WEAK_DAYS), datetime.min.time()).replace(
            tzinfo=self._calendar.timezone
        )
        week = [today - timedelta(days=n) for n in range(7)]
        anki: dict[str, dict[str, int]] = {
            d.isoformat(): {"reviews": 0, "new_cards": 0} for d in week
        }
        for e in events:
            if isinstance(e, StudyLogged) and e.kind in (
                ActivityKind.ANKI_REVIEWS,
                ActivityKind.ANKI_NEW_CARDS,
            ):
                d = self._calendar.day_of(e.occurred_at).isoformat()
                if d in anki:
                    key = "reviews" if e.kind is ActivityKind.ANKI_REVIEWS else "new_cards"
                    anki[d][key] += e.quantity
        lessons = []
        for spec in LESSONS.values():
            p = state.lessons.get(spec.id)
            lessons.append({
                "id": spec.id, "title": spec.title,
                "cleared": bool(p and p.cleared), "best": round(p.best, 2) if p else 0,
                "due_on": p.due_on.isoformat() if p and p.due_on else None,
                "due_today": bool(p and p.is_due(today)),
            })  # fmt: skip
        bosses = {
            b: {"felled": r.defeated, "deaths": r.deaths, "furthest_phase": r.furthest_phase + 1,
                "in_fight": r.current is not None}
            for b, r in state.bosses.items()
        }  # fmt: skip
        words = [
            {"written": e.written, "kana": e.kana, "meaning": e.meaning, "pos": e.part_of_speech}
            for e in events
            if isinstance(e, WordLearned)
        ]
        return {
            "time_budget_minutes": [45, 60],
            "bonfire_lit": state.lit_today,
            "souls": state.souls,
            "recent_days": [
                {"day": d.day.isoformat(), "lit": d.lit, "died": d.died, "spared": d.spared}
                for d in state.recent_days
            ],
            "region": REGIONS[0].name,
            "grammar": REGIONS[0].topics,
            "lessons": lessons,
            "bosses": bosses,
            "weak_verbs": self._weak_verbs(events, state, since),
            "anki_last_7_days": anki,
            "today_totals": {k.value: v for k, v in state.today_totals.items()},
            "quests_today": [
                {"id": s.quest.id, "title": s.quest.title, "done": s.done} for s in state.quests
            ],
            "known_words": words,
            "architect": self._architect(state),
        }

    @staticmethod
    def _architect(state: WorldState) -> dict[str, Any]:
        arch = state.architect
        regions = []
        for r in ARCHITECT_REGIONS:
            topics = [
                {"id": s.topic.id, "title": s.topic.title, "note": s.topic.note,
                 "words": s.words, "learned": s.learned, "proved": s.proved, "best": s.best}
                for s in arch.region(r.id)
            ]  # fmt: skip
            regions.append({
                "id": r.id, "name": r.name, "covers": r.covers,
                "placed": r.id in arch.placed_regions,
                "cleared_share": round(arch.cleared_share(r.id), 2), "topics": topics,
            })  # fmt: skip
        return {"prove_mark": PROVE_MARK, "regions": regions}
