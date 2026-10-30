"""FastAPI + Jinja + HTMX. Every form works without JavaScript; HTMX swaps the world panel."""

import hashlib
import secrets
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markupsafe import Markup, escape

from hollow.adapters.anki_connect import connect
from hollow.adapters.db.store import SqlEventStore, make_engine
from hollow.adapters.github_api import GitHubApi
from hollow.application.anki_sync import AnkiSource, AnkiSync, AnkiUnavailable, SyncResult
from hollow.application.architect_lessons import ArchitectLessons, QuizRun
from hollow.application.blacksmith import Blacksmith, BlacksmithError
from hollow.application.bonfire import BonfireService, CannotLevelUp
from hollow.application.fights import FightError, FightService, FightView
from hollow.application.github_sync import (
    GitHubResult,
    GitHubSource,
    GitHubSync,
    GitHubUnavailable,
)
from hollow.application.lessons import LessonError, LessonService
from hollow.application.lessons import Run as LessonRun
from hollow.application.ports import Clock, EventStore, SystemClock
from hollow.config import Settings
from hollow.domain.activities import ACTIVITIES, ActivityKind, Track
from hollow.domain.architect import (
    LORDS,
    PROVE_MARK,
    PROVE_SOULS,
    TopicState,
    boss_id,
    topic_of,
)
from hollow.domain.architect import REGION_BY_ID as ARCH_REGION_BY_ID
from hollow.domain.architect import REGIONS as ARCH_REGIONS
from hollow.domain.armory import (
    BOSS_MATERIALS,
    BOSS_WEAPONS,
    MATERIAL_NAMES,
    SKILLS,
    WEAPONS,
    upgrade_cost,
)
from hollow.domain.atlas import (
    ARCH_AREAS,
    ARCH_POINTS,
    ARCH_REGION_MAPS,
    ARCH_WORLD_SIZE,
    FIRELINK,
    FIRELINK_SIZE,
    REGIONS,
    WORLD_SIZE,
    NodeKind,
)
from hollow.domain.bosses import (
    BOSSES,
    ESTUS_HEAL,
    FIRST_TRY_BONUS,
    VICTORY_SOULS,
    WARDEN,
    Boss,
    Outcome,
    architect_foe,
)
from hollow.domain.conjugation import Ending, Verb
from hollow.domain.events import AgentResult, Material
from hollow.domain.lessons import LESSONS, LessonProgress, Run, grade
from hollow.domain.progression import STATS, Stat
from hollow.domain.world import EFFIGIES_PER_WEEK, MAX_HOLLOWING, WorldState

HERE = Path(__file__).parent
STATIC = HERE / "static"
ROADS = ("ronin", "architect")
YEAR = 31_536_000
MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")


def markdown(text: str) -> Markup:
    """Renders a lesson from the repo's curriculum (raw HTML in it is escaped)."""
    return Markup(MARKDOWN.render(text))


def inline_markdown(text: str) -> Markup:
    return Markup(MARKDOWN.renderInline(text))


def lesson_title(lesson_id: str) -> str:
    topic = topic_of(lesson_id)
    if topic is not None:
        return topic.title
    spec = LESSONS.get(lesson_id)
    return spec.title if spec else lesson_id


def step_status(state: TopicState, today: date) -> str:
    """new, due or cleared, for a step's map node and lesson card."""
    progress = state.lesson
    if progress is None or not progress.cleared:
        return "cleared" if state.proved else "new"
    return "due" if progress.is_due(today) else "cleared"


class FreshStaticFiles(StaticFiles):
    """Static files the browser re-checks before reuse, so a changed sprite always shows."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


@lru_cache(maxsize=256)
def _fingerprint(path: str, mtime_ns: int) -> str:
    return hashlib.sha1((STATIC / path).read_bytes()).hexdigest()[:10]


def with_readings(ja: str, readings: list[list[str]] | list[tuple[str, str]]) -> Markup:
    """Japanese text with a hiragana tooltip on every word that has a reading."""
    marked = ja
    pairs = sorted(
        ((str(w), str(k)) for w, k in readings if w and k and w != k), key=lambda p: -len(p[0])
    )
    for n, (written, _) in enumerate(pairs):
        marked = marked.replace(written, f"\x00{n}\x00", 1)
    html = str(escape(marked))
    for n, (written, kana) in enumerate(pairs):
        tip = (
            f'<span class="ja" tabindex="0" data-reading="{escape(kana)}">{escape(written)}'
            f'<span class="visually-hidden"> ({escape(kana)})</span></span>'
        )
        html = html.replace(f"\x00{n}\x00", tip)
    return Markup(html)


def asset(path: str) -> str:
    """A static file's URL with a content fingerprint: new content, new URL, no stale cache."""
    file = STATIC / path
    version = _fingerprint(path, file.stat().st_mtime_ns) if file.is_file() else "0"
    return f"/static/{path}?v={version}"


def sounds() -> dict[str, str]:
    """Every sound effect's fingerprinted URL by name (static/sounds/, made by
    tools/sounds/sounds.py). The page plays them by name; see js/sound.js."""
    return {p.stem: asset(f"sounds/{p.name}") for p in sorted((STATIC / "sounds").glob("*.mp3"))}


WORN_WEAPONS = {"golem-fist"}
"""Weapons worn rather than held: the hero's fingers are not drawn over them."""

RUN_LABELS = {Run.FIRST: "New lesson", Run.REFRESHER: "Refresher", Run.PRACTICE: "Practice"}
HINTS = {
    Ending.RU_VERB: "る-verb: drop る, add て.",
    Ending.TSU: "う・つ・る become って.",
    Ending.NDE: "む・ぶ・ぬ become んで.",
    Ending.ITE: "く becomes いて, ぐ becomes いで. 行く is the exception: 行って.",
    Ending.SHITE: "す becomes して.",
    Ending.IRREGULAR: "Irregular: する → して, 来る → 来て (きて).",
}


def hint(verb: Verb) -> str:
    if (
        verb.ending is Ending.TSU
        and verb.kana.endswith("る")
        and verb.kana[-2] in "いきしちにひみりえけせてねへめれげべでぜじぎびぢ"
    ):
        return f"{verb.written} looks like a る-verb but is not: る becomes って."
    return HINTS[verb.ending]


ANKI_KINDS = {ActivityKind.ANKI_REVIEWS, ActivityKind.ANKI_NEW_CARDS}
"""Logged automatically once Anki sync is on, so they leave the manual form."""


def create_app(
    settings: Settings | None = None,
    store: EventStore | None = None,
    clock: Clock | None = None,
    anki: AnkiSource | None = None,
    github: GitHubSource | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = store or SqlEventStore(make_engine(settings.database_url))
    clock = clock or SystemClock()
    service = BonfireService(store, clock, settings.calendar())
    lessons = LessonService(store, clock, settings.calendar())
    arch = ArchitectLessons(store, clock, settings.calendar())
    fights = FightService(store, clock, settings.calendar())
    smith = Blacksmith(store, clock, settings.calendar())
    if anki is None and settings.anki_enabled:
        anki = connect(settings)
    anki_sync = AnkiSync(store, anki, clock, settings.calendar()) if anki else None
    if github is None and settings.github_enabled:
        token = settings.github_token.get_secret_value() if settings.github_token else None
        github = GitHubApi(token)
    github_sync = (
        GitHubSync(
            store,
            github,
            clock,
            settings.calendar(),
            settings.github_repo_names(),
            settings.github_author,
        )
        if github
        else None
    )
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.globals["asset"] = asset
    templates.env.globals["sounds"] = sounds
    templates.env.globals["with_readings"] = with_readings
    templates.env.globals["lesson_title"] = lesson_title
    templates.env.filters["markdown"] = markdown
    templates.env.filters["inline_md"] = inline_markdown

    def lore() -> dict[str, dict[str, Any]]:
        """The newest lore text for each target."""
        texts: dict[str, dict[str, Any]] = {}
        for event in store.all():
            if isinstance(event, AgentResult) and event.agent == "lorekeeper":
                texts[event.task] = event.payload
        return texts

    templates.env.globals["lore"] = lore
    syncing = anki_sync is not None or github_sync is not None
    """Pages only ask for a background sync when there is something to sync."""
    basic = HTTPBasic(auto_error=False)

    def require_password(
        credentials: Annotated[HTTPBasicCredentials | None, Depends(basic)],
    ) -> None:
        if settings.password is None:
            return
        expected = settings.password.get_secret_value().encode()
        given = credentials.password.encode() if credentials else b""
        if not secrets.compare_digest(given, expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})

    app = FastAPI(title="DontYouDareGoHollow", dependencies=[Depends(require_password)])
    app.mount("/static", FreshStaticFiles(directory=STATIC), name="static")

    def context(state: WorldState, **extra: Any) -> dict[str, Any]:
        return {
            "state": state,
            "max_hollowing": MAX_HOLLOWING,
            "effigies_per_week": EFFIGIES_PER_WEEK,
            "lessons": LESSONS,
            "run_labels": RUN_LABELS,
            "stat_specs": list(STATS.values()),
            "activities": list(ACTIVITIES.values()),
            "ronin_kinds": [
                s
                for s in ACTIVITIES.values()
                if s.track is Track.RONIN and not (anki_sync and s.kind in ANKI_KINDS)
            ],
            "architect_kinds": [
                s
                for s in ACTIVITIES.values()
                if s.track is Track.ARCHITECT
                and not (github_sync and s.kind is ActivityKind.PULL_REQUEST)
            ],
            "anki_enabled": anki_sync is not None,
            "heroes": heroes(state),
            **extra,
        }

    def heroes(state: WorldState) -> dict[str, dict[str, Any]]:
        """What the hero holds on each road: the weapon equipped for it."""
        kits = {}
        for track in (Track.RONIN, Track.ARCHITECT):
            weapon, _ = state.armory.weapon(track)
            kits[track.value] = {
                "weapon": weapon.id,
                "name": weapon.name,
                "hand": weapon.id not in WORN_WEAPONS,
            }
        return kits

    def equipment(state: WorldState) -> list[dict[str, Any]]:
        rings = 2 if state.stats[Stat.INTELLIGENCE] >= 10 else 1
        slots: list[dict[str, Any]] = []
        for track in (Track.RONIN, Track.ARCHITECT):
            weapon, level = state.armory.weapon(track)
            foe = WARDEN if track is Track.RONIN else architect_foe(state.architect.felled)
            note = f"{weapon.damage(level, foe.recommended)} damage per hit against {foe.name}."
            slots.append(
                {
                    "name": f"{'Ronin' if track is Track.RONIN else 'Architect'} weapon",
                    "sprite": weapon.sprite,
                    "size": 72,
                    "item": f"{weapon.name} +{level}",
                    "note": note + (f" {SKILLS[weapon.skill]}." if weapon.skill else ""),
                }
            )
        mats = state.armory.materials
        total = sum(mats.values())
        slots += [
            {
                "name": f"Rings · {rings} slot{'s' if rings > 1 else ''}",
                "sprite": "item_ring.png",
                "item": None,
                "note": "Passive bonuses. Intelligence 10 opens a second slot.",
            },
            {
                "name": "Titanite",
                "sprite": "item_titanite_shard.png",
                "item": ", ".join(f"{n} {MATERIAL_NAMES[m]}" for m, n in mats.items() if n)
                or "None yet",
                "empty": total == 0,
                "note": "Reinforce weapons at the blacksmith.",
            },
        ]
        return slots

    def character_page(
        request: Request,
        state: WorldState,
        flash: str | None = None,
        warning: str | None = None,
        sfx: str | None = None,
    ) -> Response:
        name = "partials/_character.html" if request.headers.get("HX-Request") else "character.html"
        return templates.TemplateResponse(
            request,
            name,
            context(
                state,
                page="character",
                equipment=equipment(state),
                syncing=syncing,
                flash=flash,
                warning=warning,
                sfx=sfx,
            ),
        )

    def respond(
        request: Request,
        state: WorldState,
        flash: str | None = None,
        warning: str | None = None,
        sfx: str | None = None,
    ) -> Response:
        """The home panel after an action. `sfx` names the sounds the action makes (js/sound.js
        plays them when the panel swaps in)."""
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                request,
                "partials/_world.html",
                context(state, flash=flash, warning=warning, sfx=sfx),
            )
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    def sync(force: bool) -> tuple[list[str], list[str]]:
        """Runs every enabled import. Returns what was found and any warnings."""
        found: list[str] = []
        warnings: list[str] = []
        if anki_sync is not None:
            try:
                anki = anki_sync.run()
            except AnkiUnavailable:
                warnings.append(
                    "Anki is not reachable. Open Anki (with AnkiConnect) and sync again."
                )
            else:
                found.append(describe_anki(anki, quiet=not force))
        if github_sync is not None:
            try:
                github = github_sync.run(force=force)
            except GitHubUnavailable as error:
                warnings.append(f"GitHub sync failed: {error}.")
            else:
                found.append(describe_github(github))
        return [line for line in found if line], warnings

    def describe_anki(result: SyncResult, quiet: bool) -> str:
        words = ""
        if result.words:
            plural = "s" if result.words != 1 else ""
            words = f" {result.words} newly learned word{plural} for lessons."
        if result.total:
            return f"From Anki: {result.reviews} reviews, {result.new_cards} new cards.{words}"
        if words:
            return words.strip()
        return "" if quiet else "No new Anki reviews."

    def describe_github(result: GitHubResult | None) -> str:
        if result is None:
            return ""
        parts = []
        if result.merged:
            plural = "s" if result.merged != 1 else ""
            parts.append(f"From GitHub: {result.merged} merged PR{plural}.")
        if result.waiting:
            plural = "s" if result.waiting != 1 else ""
            parts.append(f"{result.waiting} merged PR{plural} still waiting for CI.")
        return " ".join(parts)

    def summary(found: list[str], state: WorldState) -> str | None:
        if not found:
            return None
        if state.lit_today:
            return " ".join([*found, "The bonfire is lit."])
        return " ".join([*found, "10 reviews or 5 new cards today will light it."])

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> Response:
        """Renders straight from the event log; the page then calls /sync in the background."""
        return templates.TemplateResponse(
            request, "index.html", context(service.state(), page="bonfire", syncing=syncing)
        )

    @app.post("/light")
    def light(request: Request) -> Response:
        if anki_sync is None and github_sync is None:
            return respond(request, service.light(), flash="The bonfire is lit.", sfx="bonfire")
        found, warnings = sync(force=True)
        state = service.state()
        return respond(
            request,
            state,
            flash=summary(found, state),
            warning=" ".join(warnings) or None,
            sfx="bonfire" if state.lit_today else None,
        )

    @app.post("/log")
    def log(
        request: Request,
        kind: Annotated[ActivityKind, Form()],
        quantity: Annotated[int, Form()],
        note: Annotated[str, Form()] = "",
    ) -> Response:
        was_lit = service.state().lit_today
        try:
            state = service.log_study(kind, quantity, note)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        spec = ACTIVITIES[kind]
        return respond(
            request,
            state,
            flash=f"Logged {quantity} {spec.unit} of {spec.label}.",
            sfx="souls bonfire" if state.lit_today and not was_lit else "souls",
        )

    @app.get("/character", response_class=HTMLResponse)
    def character(request: Request) -> Response:
        return character_page(request, service.state())

    @app.post("/sync")
    def background_sync(request: Request, page: str = "bonfire") -> Response:
        """Called by each page right after it loads. Answers 204 (nothing to redraw) unless
        the sync brought something new or failed, in which case it returns the page's panel."""
        found, warnings = sync(force=False)
        if not found and not warnings:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        state = service.state()
        flash = summary(found, state)
        warning = " ".join(warnings) or None
        if page == "character":
            return character_page(request, state, flash=flash, warning=warning)
        return templates.TemplateResponse(
            request, "partials/_world.html", context(state, flash=flash, warning=warning)
        )

    @app.post("/level")
    def level(request: Request, stat: Annotated[Stat, Form()]) -> Response:
        before = service.state()
        try:
            state = service.level_up(stat)
        except CannotLevelUp as error:
            if not request.headers.get("HX-Request"):
                return RedirectResponse("/character", status_code=status.HTTP_303_SEE_OTHER)
            return character_page(request, before, warning=str(error))
        if not request.headers.get("HX-Request"):
            return RedirectResponse("/character", status_code=status.HTTP_303_SEE_OTHER)
        spec = STATS[stat]
        return character_page(
            request,
            state,
            flash=(
                f"{spec.label} rose to {state.stats[stat]}. "
                f"{before.level_cost:,} souls spent at the bonfire."
            ),
            sfx="level",
        )

    @app.get("/lessons", response_class=HTMLResponse)
    def lesson_list(request: Request, warning: str | None = None) -> Response:
        state = service.state()
        steps = [
            {"region": r, "steps": [
                {"state": s, "status": step_status(s, state.today)}
                for s in state.architect.region(r.id)
            ]}
            for r in ARCH_REGIONS
            if state.architect.region_open(r.id)
        ]  # fmt: skip
        return templates.TemplateResponse(
            request,
            "lessons.html",
            context(
                state,
                page="lessons",
                cards=lessons.overview(),
                arch_regions=steps,
                verb_count=len(lessons.verbs()) - 1,
                warning=warning,
            ),
        )

    def lesson_page(
        request: Request, run: LessonRun, answers: list[str], mode: str, **extra: Any
    ) -> Response:
        state = extra.pop("state", None) or service.state()
        progress = state.lessons.get(run.spec.id)
        run_kind = progress.run_on(state.today) if progress else Run.FIRST
        name = "partials/_lesson.html" if request.headers.get("HX-Request") else "lesson.html"
        marks = grade(run.questions[: len(answers)], answers)
        return templates.TemplateResponse(
            request,
            name,
            context(
                state,
                page="lessons",
                spec=run.spec,
                run_id=str(run.id),
                questions=run.questions,
                answers=answers,
                marks=marks,
                mode=mode,
                run_kind=run_kind,
                progress=progress,
                **extra,
            ),
        )

    @app.get("/lessons/{lesson_id}", response_class=HTMLResponse)
    def lesson_start(request: Request, lesson_id: str) -> Response:
        try:
            run = lessons.start(lesson_id)
        except LessonError as error:
            return lesson_list(request, warning=str(error))
        return lesson_page(request, run, [], "question")

    def resume(lesson_id: str, run_id: str, q: list[str]) -> LessonRun:
        try:
            return lessons.resume(lesson_id, run_id, q)
        except LessonError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/lessons/{lesson_id}/answer")
    def lesson_answer(
        request: Request,
        lesson_id: str,
        run: Annotated[str, Form()],
        q: Annotated[list[str], Form()],
        answer: Annotated[str, Form()],
        a: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        current = resume(lesson_id, run, q)
        answers = [*(a or []), answer.strip()[:40]]
        if len(answers) > len(current.questions):
            raise HTTPException(422, "Every question is already answered.")
        verb = current.questions[len(answers) - 1]
        return lesson_page(
            request,
            current,
            answers,
            "feedback",
            correct=verb.te_form.accepts(answer),
            hint=hint(verb),
        )

    @app.post("/lessons/{lesson_id}/next")
    def lesson_next(
        request: Request,
        lesson_id: str,
        run: Annotated[str, Form()],
        q: Annotated[list[str], Form()],
        a: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        current = resume(lesson_id, run, q)
        answers = list(a or [])
        if len(answers) >= len(current.questions):
            raise HTTPException(422, "Every question is already answered.")
        return lesson_page(request, current, answers, "question")

    @app.post("/lessons/{lesson_id}/finish")
    def lesson_finish(
        request: Request,
        lesson_id: str,
        run: Annotated[str, Form()],
        q: Annotated[list[str], Form()],
        a: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        current = resume(lesson_id, run, q)
        answers = list(a or [])
        try:
            outcome, drop, state = lessons.finish(current, answers)
        except LessonError as error:
            raise HTTPException(422, str(error)) from error
        misses = [
            (verb, given)
            for verb, given, ok in zip(
                current.questions, answers, grade(current.questions, answers), strict=True
            )
            if not ok
        ]
        return lesson_page(
            request,
            current,
            answers,
            "result",
            outcome=outcome,
            misses=misses,
            state=state,
            drop={"material": drop.value, "name": MATERIAL_NAMES[drop]} if drop else None,
        )

    def explored() -> int:
        cards = lessons.overview()
        cleared = sum(1 for c in cards if c.progress is not None and c.progress.cleared)
        return round(100 * cleared / len(cards))

    def percent(point: tuple[int, int], size: tuple[int, int]) -> tuple[float, float]:
        return round(100 * point[0] / size[0], 2), round(100 * point[1] / size[1], 2)

    def landmark(map_id: str, place: str, area: tuple[tuple[int, int], ...]) -> dict[str, str]:
        """A place painted into the map: its outline to hover and click, and its overlays."""
        if not area:
            return {}
        return {
            "area": " ".join(f"{x},{y}" for x, y in area),
            "glow": f"sprites/spot_{map_id}_{place}.png",
            "veil": f"sprites/veil_{map_id}_{place}.png"
            if map_id in ("world", "architect")
            else "",
        }

    def chosen_road(request: Request, road: str | None) -> str:
        pick = road if road in ROADS else request.cookies.get("hollow_road", "ronin")
        return pick if pick in ROADS else "ronin"

    def remember(response: Response, road: str) -> Response:
        response.set_cookie("hollow_road", road, max_age=YEAR, samesite="lax")
        return response

    @app.get("/map", response_class=HTMLResponse)
    def world_map(request: Request, at: str | None = None, road: str | None = None) -> Response:
        pick = chosen_road(request, road)
        page = architect_world(request, at) if pick == "architect" else ronin_world(request, at)
        return remember(page, pick)

    def ronin_world(request: Request, at: str | None) -> Response:
        ids = [r.id for r in REGIONS]
        here = at if at in ids else request.cookies.get("hollow_at_world", "firelink")
        points = []
        for r in REGIONS:
            x, y = percent(r.point, WORLD_SIZE)
            kind = "bonfire" if r.open else "world"
            point: dict[str, Any] = {
                "id": r.id,
                "name": r.name,
                "kind": kind,
                "status": "open" if r.open else "fog",
                "x": x,
                "y": y,
            }
            points.append(point | landmark("world", r.id, r.area))
        return templates.TemplateResponse(
            request,
            "map_world.html",
            context(
                service.state(),
                page="map",
                road="ronin",
                map_id="world",
                size=WORLD_SIZE,
                art="map_bg.png",
                points=points,
                regions=REGIONS,
                at=here if here in ids else "firelink",
                explored=explored(),
            ),
        )

    def architect_world(request: Request, at: str | None) -> Response:
        state = service.state()
        progress = state.architect
        ids = [r.id for r in ARCH_REGIONS]
        here = at if at in ids else request.cookies.get("hollow_at_architect", "forge")
        points, panels = [], []
        for r in ARCH_REGIONS:
            x, y = percent(ARCH_POINTS[r.id], ARCH_WORLD_SIZE)
            is_open = progress.region_open(r.id)
            felled = r.id in progress.felled
            steps = progress.region(r.id)
            before = ARCH_REGIONS[r.number - 2] if r.number > 1 else None
            if is_open:
                note = None
            elif not r.written:
                note = "In the fog: its lessons are not written yet."
            elif r.id not in ARCH_REGION_MAPS:
                note = "In the fog: its paths are not charted yet."
            else:
                assert before is not None
                note = f"Unavailable for now. It opens when {before.boss} falls."
            region_point: dict[str, Any] = {
                "id": r.id, "name": r.name, "x": x, "y": y,
                "kind": "bonfire" if is_open else "world",
                "status": "cleared" if felled else ("open" if is_open else "fog"),
            }  # fmt: skip
            points.append(region_point | landmark("architect", r.id, ARCH_AREAS.get(r.id, ())))
            panels.append({
                "region": r, "open": is_open, "felled": felled, "note": note,
                "cleared": sum(s.cleared for s in steps), "proved": sum(s.proved for s in steps),
                "total": len(steps),
            })  # fmt: skip
        lords = [
            {"lord": lord, "open": progress.lord_open(lord),
             "needs": "every region" if len(lord.regions) == len(ARCH_REGIONS)
             else ", ".join(ARCH_REGION_BY_ID[r].name for r in lord.regions)}
            for lord in LORDS
        ]  # fmt: skip
        return templates.TemplateResponse(
            request,
            "map_architect.html",
            context(
                state,
                page="map",
                road="architect",
                map_id="architect",
                size=ARCH_WORLD_SIZE,
                art="map_architect.png",
                points=points,
                panels=panels,
                lords=lords,
                at=here if here in ids else "forge",
            ),
        )

    def boss_point(boss: Boss, ready: bool, waiting: str) -> dict[str, Any]:
        record = fights.view(boss.id).record
        if not ready:
            return {
                "name": "Fog gate",
                "status": "fog",
                "caption": "Boss · unavailable",
                "detail": f"{boss.name} waits beyond the fog. {waiting}",
            }
        if record.current is not None:
            label, detail = "Resume the fight", "Your fight is waiting, as you left it."
        elif record.defeated:
            label, detail = "Fight again", "Felled. Fight again for practice."
        else:
            label, detail = "Enter the fog", f"{boss.name} waits beyond. {boss.intro}"
        return {
            "name": "Fog gate",
            "status": "cleared" if record.defeated else "due",
            "caption": f"Boss · {boss.name}",
            "detail": detail,
            "action": (label, f"/boss/{boss.id}"),
        }

    def bonfire_point(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "status": "open",
            "caption": "Bonfire",
            "detail": "Rest here: your souls, streak, Effigies and level.",
            "action": ("Rest at the bonfire", "/"),
            "extra": ("Visit the blacksmith", "/blacksmith"),
        }

    @app.get("/map/firelink", response_class=HTMLResponse)
    def firelink(request: Request, at: str | None = None) -> Response:
        ids = [n.id for n in FIRELINK]
        here = at if at in ids else request.cookies.get("hollow_at_firelink", "bonfire")
        cards = {c.spec.id: c for c in lessons.overview()}
        points = []
        for number, node in enumerate(FIRELINK):
            x, y = percent(node.point, FIRELINK_SIZE)
            point: dict[str, Any] = {"id": node.id, "kind": node.kind.value, "x": x, "y": y}
            point |= landmark("firelink", node.id, node.area)
            if node.kind is NodeKind.BONFIRE:
                point |= bonfire_point("Firelink bonfire")
            elif node.kind is NodeKind.BOSS:
                point |= boss_point(
                    WARDEN,
                    fights.ready(WARDEN.id),
                    f"It will not part until you know {WARDEN.min_verbs} verbs.",
                )
            else:
                assert node.lesson_id is not None
                card = cards[node.lesson_id]
                status = card.status.value
                labels = {"new": "Start", "due": "Refresh", "waiting": "Practise"}
                if status == "locked":
                    missing = card.spec.min_verbs - card.verbs
                    detail = (
                        f"Unavailable: learn {missing} more verb{'s' if missing != 1 else ''} "
                        "of this kind in Anki to open it."
                    )
                elif status == "waiting" and card.progress and card.progress.due_on:
                    detail = (
                        f"Cleared. Back as a refresher on {card.progress.due_on:%A %d %B}; "
                        "practice now pays 25%."
                    )
                elif status == "due":
                    detail = "A refresher is due: 60% souls, and the next interval if you get 90%."
                else:
                    detail = f"{card.questions} questions from {card.verbs} of your verbs."
                point |= {
                    "name": card.spec.title,
                    "status": "cleared" if status == "waiting" else status,
                    "caption": f"Lesson {number} · て-form",
                    "example": card.spec.example,
                    "detail": detail,
                    "action": (
                        (labels[status], f"/lessons/{card.spec.id}") if status in labels else None
                    ),
                }
            points.append(point)
        return templates.TemplateResponse(
            request,
            "map_region.html",
            context(
                service.state(),
                page="map",
                road="ronin",
                map_id="firelink",
                size=FIRELINK_SIZE,
                art="region_firelink.png",
                points=points,
                region=REGIONS[0],
                at=here if here in ids else "bonfire",
                explored=explored(),
            ),
        )

    def step_detail(s: TopicState, status: str, today: date) -> str:
        progress = s.lesson
        questions = len(s.topic.quiz)
        if status == "due":
            return "A refresher is due: 60% souls, and the next interval if you get 90%."
        if status == "new":
            return f"Read the lesson, then {questions} quiz questions. Clear at 80%."
        if progress is not None and progress.cleared and progress.due_on:
            return (
                f"Cleared. Back as a refresher on {progress.due_on:%A %d %B}; "
                "practice now pays 25%."
            )
        return "Cleared in the placement trial. Practise whenever you like."

    @app.get("/map/architect/{region_id}", response_class=HTMLResponse)
    def architect_region(request: Request, region_id: str, at: str | None = None) -> Response:
        if region_id not in ARCH_REGION_BY_ID:
            raise HTTPException(404, f"No Architect region called {region_id}.")
        state = service.state()
        progress = state.architect
        if region_id not in ARCH_REGION_MAPS or not progress.region_open(region_id):
            return RedirectResponse(
                f"/map?road=architect&at={region_id}", status_code=status.HTTP_303_SEE_OTHER
            )
        region = ARCH_REGION_BY_ID[region_id]
        nodes, size, art = ARCH_REGION_MAPS[region_id]
        ids = [n.id for n in nodes]
        here = at if at in ids else request.cookies.get(f"hollow_at_{region_id}", "bonfire")
        steps = progress.region(region_id)
        cleared = sum(s.cleared for s in steps)
        labels = {"new": "Read the lesson", "due": "Refresh", "cleared": "Practise"}
        points = []
        for node in nodes:
            x, y = percent(node.point, size)
            point: dict[str, Any] = {"id": node.id, "kind": node.kind.value, "x": x, "y": y}
            point |= landmark(region_id, node.id, node.area)
            if node.kind is NodeKind.BONFIRE:
                point |= bonfire_point(f"{region.name} bonfire")
            elif node.kind is NodeKind.BOSS:
                boss = BOSSES[boss_id(region_id)]
                point |= boss_point(
                    boss,
                    fights.ready(boss.id),
                    f"It parts when every step here is cleared ({cleared} of {len(steps)}).",
                )
            else:
                assert node.lesson_id is not None
                s = progress.topics[node.lesson_id]
                status_ = step_status(s, state.today)
                mark = None
                if s.placed:
                    mark = "Cleared in the placement trial"
                elif s.proved:
                    mark = f"Proved: the Tech Lead's exam, best {round((s.best or 0) * 100)}%"
                point |= {
                    "name": s.topic.title,
                    "status": status_,
                    "caption": f"Step {s.topic.number} · {region.name}",
                    "lead": s.topic.why,
                    "detail": step_detail(s, status_, state.today),
                    "mark": mark,
                    "action": (labels[status_], f"/lessons/arch/{s.topic.id}"),
                }
            points.append(point)
        return templates.TemplateResponse(
            request,
            "map_region.html",
            context(
                state,
                page="map",
                road="architect",
                map_id=region_id,
                size=size,
                art=art,
                points=points,
                region=region,
                at=here if here in ids else "bonfire",
                explored=round(100 * cleared / len(steps)),
            ),
        )

    @app.get("/architect")
    def architect_redirect() -> Response:
        """The old Architect page: the road now lives on the map."""
        return RedirectResponse("/map?road=architect", status_code=status.HTTP_303_SEE_OTHER)

    # --- Architect lessons --------------------------------------------------------

    def arch_progress(topic_id: str) -> tuple[WorldState, TopicState]:
        state = service.state()
        return state, state.architect.topics[topic_id]

    @app.get("/lessons/arch/{topic_id}", response_class=HTMLResponse)
    def arch_lesson(request: Request, topic_id: str) -> Response:
        try:
            topic = arch.topic(topic_id)
        except LessonError as error:
            return lesson_list(request, warning=str(error))
        state, s = arch_progress(topic.id)
        return templates.TemplateResponse(
            request,
            "arch_lesson.html",
            context(
                state,
                page="lessons",
                topic=topic,
                region=ARCH_REGION_BY_ID[topic.region],
                step=s,
                status=step_status(s, state.today),
                run_kind=s.lesson.run_on(state.today) if s.lesson else Run.FIRST,
                prove_souls=PROVE_SOULS,
                prove_mark=PROVE_MARK,
            ),
        )

    def quiz_page(
        request: Request, run: QuizRun, answers: list[str], mode: str, **extra: Any
    ) -> Response:
        state = extra.pop("state", None) or service.state()
        progress: LessonProgress | None = state.architect.topics[run.topic.id].lesson
        name = "partials/_arch_quiz.html" if request.headers.get("HX-Request") else "arch_quiz.html"
        return templates.TemplateResponse(
            request,
            name,
            context(
                state,
                page="lessons",
                run=run,
                topic=run.topic,
                answers=answers,
                marks=run.grade(answers),
                mode=mode,
                run_kind=progress.run_on(state.today) if progress else Run.FIRST,
                progress=progress,
                **extra,
            ),
        )

    def arch_resume(topic_id: str, run_id: str, q: list[str]) -> QuizRun:
        try:
            return arch.resume(topic_id, run_id, q)
        except LessonError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/lessons/arch/{topic_id}/start")
    def arch_start(request: Request, topic_id: str) -> Response:
        try:
            run = arch.start(topic_id)
        except LessonError as error:
            raise HTTPException(422, str(error)) from error
        return quiz_page(request, run, [], "question")

    @app.post("/lessons/arch/{topic_id}/answer")
    def arch_answer(
        request: Request,
        topic_id: str,
        run: Annotated[str, Form()],
        q: Annotated[list[str], Form()],
        answer: Annotated[str, Form()],
        a: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        current = arch_resume(topic_id, run, q)
        answers = [*(a or []), answer.strip()[:3]]
        if len(answers) > len(current.questions):
            raise HTTPException(422, "Every question is already answered.")
        n = len(answers) - 1
        return quiz_page(
            request, current, answers, "feedback", correct=current.accepts(n, answers[-1])
        )

    @app.post("/lessons/arch/{topic_id}/next")
    def arch_next(
        request: Request,
        topic_id: str,
        run: Annotated[str, Form()],
        q: Annotated[list[str], Form()],
        a: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        current = arch_resume(topic_id, run, q)
        answers = list(a or [])
        if len(answers) >= len(current.questions):
            raise HTTPException(422, "Every question is already answered.")
        return quiz_page(request, current, answers, "question")

    @app.post("/lessons/arch/{topic_id}/finish")
    def arch_finish(
        request: Request,
        topic_id: str,
        run: Annotated[str, Form()],
        q: Annotated[list[str], Form()],
        a: Annotated[list[str] | None, Form()] = None,
    ) -> Response:
        current = arch_resume(topic_id, run, q)
        answers = list(a or [])
        try:
            outcome, drop, state = arch.finish(current, answers)
        except LessonError as error:
            raise HTTPException(422, str(error)) from error
        marks = current.grade(answers)
        misses = [current.questions[n] for n, ok in enumerate(marks) if not ok]
        ready = BOSSES.get(boss_id(current.topic.region))
        return quiz_page(
            request,
            current,
            answers,
            "result",
            outcome=outcome,
            misses=misses,
            state=state,
            drop={"material": drop.value, "name": MATERIAL_NAMES[drop]} if drop else None,
            boss_ready=ready is not None
            and state.architect.region_ready(current.topic.region)
            and not state.bosses[ready.id].defeated,
            boss=ready,
        )

    def boss_drops(boss_id: str) -> str:
        parts = [WEAPONS[BOSS_WEAPONS[boss_id]].name] if boss_id in BOSS_WEAPONS else []
        for material, count in BOSS_MATERIALS.get(boss_id, ()):
            plural = "s" if count != 1 else ""
            parts.append(f"{count} {MATERIAL_NAMES[material]}{plural}")
        return ", ".join(parts)

    def weapon_line(view: FightView) -> str:
        weapon, level = view.state.armory.weapon(view.boss.track)
        damage = FightService.damage(view.boss, view.state)
        return f"Your {weapon.name} +{level} deals {damage} per hit here."

    def fight_page(request: Request, view: FightView, gate: bool = False) -> Response:
        attempt = view.attempt
        wins = sum(1 for a in view.record.attempts if a.outcome is Outcome.WON)
        name = "partials/_fight.html" if request.headers.get("HX-Request") else "boss.html"
        return templates.TemplateResponse(
            request,
            name,
            context(
                view.state,
                page="map",
                view=view,
                gate=gate,
                ready=fights.ready(view.boss.id),
                requirement=fights.requirement(view.boss.id),
                damage=attempt.damage if attempt is not None else 0,
                heal=ESTUS_HEAL,
                first_win=wins == 1 and attempt is not None and attempt.outcome is Outcome.WON,
                boss_drops=boss_drops(view.boss.id),
                weapon=weapon_line(view),
                victory_souls=VICTORY_SOULS
                + (FIRST_TRY_BONUS if attempt is not None and attempt.number == 1 else 0),
            ),
        )

    @app.get("/boss/{boss_id}", response_class=HTMLResponse)
    def boss_page(request: Request, boss_id: str) -> Response:
        try:
            view = fights.view(boss_id)
        except FightError as error:
            raise HTTPException(404, str(error)) from error
        return fight_page(request, view, gate=view.record.current is None)

    def fight_response(request: Request, boss_id: str, view: FightView) -> Response:
        if not request.headers.get("HX-Request"):
            return RedirectResponse(f"/boss/{boss_id}", status_code=status.HTTP_303_SEE_OTHER)
        return fight_page(request, view, gate=False)

    @app.post("/boss/{boss_id}/enter")
    def boss_enter(request: Request, boss_id: str) -> Response:
        try:
            view = fights.enter(boss_id)
        except FightError as error:
            raise HTTPException(422, str(error)) from error
        return fight_response(request, boss_id, view)

    @app.post("/boss/{boss_id}/answer")
    def boss_answer(
        request: Request,
        boss_id: str,
        attempt: Annotated[str, Form()],
        turn: Annotated[int, Form()],
        answer: Annotated[str, Form()] = "",
    ) -> Response:
        try:
            view = fights.answer(boss_id, attempt, turn, answer)
        except FightError:
            view = fights.view(boss_id)
        return fight_response(request, boss_id, view)

    @app.post("/boss/{boss_id}/estus")
    def boss_estus(request: Request, boss_id: str, attempt: Annotated[str, Form()]) -> Response:
        try:
            view = fights.drink(boss_id, attempt)
        except FightError:
            view = fights.view(boss_id)
        return fight_response(request, boss_id, view)

    MATERIAL_INFO = (
        (Material.SHARD, "+1 to +3", "perfect lessons and refreshers"),
        (Material.LARGE_SHARD, "+4 to +6", "refreshers from 7 days on, bosses"),
        (Material.CHUNK, "+7 to +9", "bosses, merged PRs, every 100 new cards"),
        (Material.SLAB, "+10", "bosses, your first merged PR"),
    )

    def describe_source(source: str) -> str:
        if source.startswith("lesson:"):
            return "a lesson"
        if source.startswith("boss:"):
            boss_id = source.removeprefix("boss:")
            return BOSSES[boss_id].name if boss_id in BOSSES else "a boss"
        if source == "pull-request":
            return "a merged pull request"
        if source.startswith("milestone:"):
            return source.removeprefix("milestone:").replace("-", " ")
        return source

    def forge_page(
        request: Request,
        state: WorldState,
        flash: str | None = None,
        warning: str | None = None,
        sfx: str | None = None,
    ) -> Response:
        arm = state.armory
        tracks = []
        for track, title, subject in (
            (Track.RONIN, "Ronin", "Japanese fights"),
            (Track.ARCHITECT, "Architect", "dev fights"),
        ):
            weapons = []
            for spec in WEAPONS.values():
                if spec.track is not track:
                    continue
                owned = arm.owns(spec.id)
                level = arm.levels.get(spec.id, 0)
                cost = upgrade_cost(min(level + 1, spec.max_level))
                vs = WARDEN if track is Track.RONIN else architect_foe(state.architect.felled)
                source = next(
                    (BOSSES[b].name for b, w in BOSS_WEAPONS.items() if w == spec.id), "a boss"
                )
                weapons.append(
                    {
                        "spec": spec,
                        "owned": owned,
                        "level": level,
                        "equipped": arm.equipped.get(track) == spec.id,
                        "skill": SKILLS[spec.skill] if spec.skill else None,
                        "damage": spec.damage(level, vs.recommended) if vs else None,
                        "next_damage": spec.damage(level + 1, vs.recommended) if vs else None,
                        "vs": vs.name if vs else "",
                        "cost": cost,
                        "cost_name": MATERIAL_NAMES[cost[1]]
                        + ("s" if cost[2] != 1 and not cost[1].value.endswith("slab") else ""),
                        "can_upgrade": owned
                        and level < spec.max_level
                        and state.souls >= cost[0]
                        and arm.materials[cost[1]] >= cost[2],
                        "source": f"Dropped by {source}.",
                    }
                )
            tracks.append({"title": title, "subject": subject, "weapons": weapons})
        recent = [
            {
                "count": d.count,
                "name": MATERIAL_NAMES[d.material],
                "source": describe_source(d.source),
                "when": settings.calendar().day_of(d.at).strftime("%a %d %b"),
            }
            for d in reversed(arm.drops[-8:])
        ]
        materials = [
            {"material": m, "name": MATERIAL_NAMES[m], "levels": lv, "source": src}
            for m, lv, src in MATERIAL_INFO
        ]
        name = "partials/_forge.html" if request.headers.get("HX-Request") else "blacksmith.html"
        return templates.TemplateResponse(
            request,
            name,
            context(
                state,
                page="blacksmith",
                tracks=tracks,
                recent=recent,
                materials=materials,
                flash=flash,
                warning=warning,
                sfx=sfx,
            ),
        )

    @app.get("/blacksmith", response_class=HTMLResponse)
    def blacksmith(request: Request) -> Response:
        return forge_page(request, service.state())

    def forge_action(request: Request, action: str, weapon: str) -> Response:
        try:
            if action == "buy":
                state = smith.buy(weapon)
                flash = f"Bought the {WEAPONS[weapon].name}."
            elif action == "upgrade":
                state = smith.upgrade(weapon)
                level = state.armory.levels[weapon]
                flash = f"The {WEAPONS[weapon].name} is now +{level}."
            else:
                state = smith.equip(weapon)
                flash = f"The {WEAPONS[weapon].name} is in your hand."
        except BlacksmithError as error:
            if not request.headers.get("HX-Request"):
                return RedirectResponse("/blacksmith", status_code=status.HTTP_303_SEE_OTHER)
            return forge_page(request, service.state(), warning=str(error))
        if not request.headers.get("HX-Request"):
            return RedirectResponse("/blacksmith", status_code=status.HTTP_303_SEE_OTHER)
        cue = {"buy": "coins", "upgrade": "anvil", "equip": "equip"}[action]
        return forge_page(request, state, flash=flash, sfx=cue)

    @app.post("/blacksmith/{action}")
    def blacksmith_action(
        request: Request, action: str, weapon: Annotated[str, Form()]
    ) -> Response:
        if action not in ("buy", "upgrade", "equip"):
            raise HTTPException(404, "The blacksmith does not do that.")
        return forge_action(request, action, weapon)

    @app.get("/journal", response_class=HTMLResponse)
    def journal(request: Request) -> Response:
        results = [e for e in store.all() if isinstance(e, AgentResult)]
        results.sort(key=lambda e: e.occurred_at, reverse=True)
        calendar = settings.calendar()
        entries = [
            {"agent": e.agent, "task": e.task, "data": e.payload,
             "day": calendar.day_of(e.occurred_at).strftime("%a %d %b")}
            for e in results
        ]  # fmt: skip
        return templates.TemplateResponse(
            request, "journal.html", context(service.state(), page="journal", entries=entries)
        )

    @app.post("/message")
    def message(request: Request, text: Annotated[str, Form()]) -> Response:
        try:
            state = service.leave_message(text)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return respond(request, state, flash="Message left for tomorrow's you.", sfx="message")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
