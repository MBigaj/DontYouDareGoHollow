"""FastAPI + Jinja + HTMX. Every form works without JavaScript; HTMX swaps the world panel."""

import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hollow.adapters.anki_connect import connect
from hollow.adapters.db.store import SqlEventStore, make_engine
from hollow.adapters.github_api import GitHubApi
from hollow.application.anki_sync import AnkiSource, AnkiSync, AnkiUnavailable, SyncResult
from hollow.application.bonfire import BonfireService, CannotLevelUp
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
from hollow.domain.conjugation import Ending, Verb
from hollow.domain.lessons import LESSONS, Run, grade
from hollow.domain.progression import STATS, Stat
from hollow.domain.world import EFFIGIES_PER_WEEK, MAX_HOLLOWING, WorldState

HERE = Path(__file__).parent
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
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

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
            **extra,
        }

    def equipment(state: WorldState) -> list[dict[str, Any]]:
        rings = 2 if state.stats[Stat.INTELLIGENCE] >= 10 else 1
        return [
            {
                "name": "Ronin weapon",
                "sprite": "item_katana.png",
                "item": None,
                "note": "Deals damage in Japanese fights.",
            },
            {
                "name": "Architect weapon",
                "sprite": "item_hammer.png",
                "item": None,
                "note": "Deals damage in dev fights.",
            },
            {
                "name": f"Rings · {rings} slot{'s' if rings > 1 else ''}",
                "sprite": "item_ring.png",
                "item": None,
                "note": "Passive bonuses. Intelligence 10 opens a second slot.",
            },
            {
                "name": "Titanite",
                "sprite": "item_titanite.png",
                "item": "None yet",
                "empty": True,
                "note": "Drops from lessons, refreshers and bosses.",
            },
        ]

    def character_page(
        request: Request, state: WorldState, flash: str | None = None, warning: str | None = None
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
            ),
        )

    def respond(
        request: Request, state: WorldState, flash: str | None = None, warning: str | None = None
    ) -> Response:
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                request, "partials/_world.html", context(state, flash=flash, warning=warning)
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
            return respond(request, service.light(), flash="The bonfire is lit.")
        found, warnings = sync(force=True)
        state = service.state()
        return respond(
            request, state, flash=summary(found, state), warning=" ".join(warnings) or None
        )

    @app.post("/log")
    def log(
        request: Request,
        kind: Annotated[ActivityKind, Form()],
        quantity: Annotated[int, Form()],
        note: Annotated[str, Form()] = "",
    ) -> Response:
        try:
            state = service.log_study(kind, quantity, note)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        spec = ACTIVITIES[kind]
        return respond(request, state, flash=f"Logged {quantity} {spec.unit} of {spec.label}.")

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
        )

    @app.get("/lessons", response_class=HTMLResponse)
    def lesson_list(request: Request, warning: str | None = None) -> Response:
        return templates.TemplateResponse(
            request,
            "lessons.html",
            context(
                service.state(),
                page="lessons",
                cards=lessons.overview(),
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
            outcome, state = lessons.finish(current, answers)
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
            request, current, answers, "result", outcome=outcome, misses=misses, state=state
        )

    @app.post("/message")
    def message(request: Request, text: Annotated[str, Form()]) -> Response:
        try:
            state = service.leave_message(text)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return respond(request, state, flash="Message left for tomorrow's you.")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
