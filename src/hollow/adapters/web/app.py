"""FastAPI + Jinja + HTMX. Every form works without JavaScript; HTMX swaps the world panel."""

import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hollow.adapters.anki_connect import AnkiConnect
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
from hollow.application.ports import Clock, EventStore, SystemClock
from hollow.config import Settings
from hollow.domain.activities import ACTIVITIES, ActivityKind, Track
from hollow.domain.progression import STATS, Stat
from hollow.domain.world import EFFIGIES_PER_WEEK, MAX_HOLLOWING, WorldState

HERE = Path(__file__).parent
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
    if anki is None and settings.anki_enabled:
        anki = AnkiConnect(settings.anki_url, settings.anki_deck_names())
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
                state, page="character", equipment=equipment(state), flash=flash, warning=warning
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
        if result.total:
            return f"From Anki: {result.reviews} reviews, {result.new_cards} new cards."
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
        found, warnings = sync(force=False)
        state = service.state()
        return templates.TemplateResponse(
            request,
            "index.html",
            context(
                state,
                page="bonfire",
                flash=summary(found, state),
                warning=" ".join(warnings) or None,
            ),
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
        found, warnings = sync(force=False)
        state = service.state()
        return character_page(
            request, state, flash=summary(found, state), warning=" ".join(warnings) or None
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
