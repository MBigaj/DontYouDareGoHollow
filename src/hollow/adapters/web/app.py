"""FastAPI + Jinja + HTMX. Every form works without JavaScript; HTMX swaps the world panel."""

import secrets
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hollow.adapters.db.store import SqlEventStore, make_engine
from hollow.application.bonfire import BonfireService
from hollow.application.ports import Clock, EventStore, SystemClock
from hollow.config import Settings
from hollow.domain.activities import ACTIVITIES, ActivityKind, Track
from hollow.domain.world import MAX_HOLLOWING, WorldState

HERE = Path(__file__).parent


def create_app(
    settings: Settings | None = None,
    store: EventStore | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    settings = settings or Settings()
    store = store or SqlEventStore(make_engine(settings.database_url))
    service = BonfireService(store, clock or SystemClock(), settings.calendar())
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
            "activities": list(ACTIVITIES.values()),
            "ronin_kinds": [s for s in ACTIVITIES.values() if s.track is Track.RONIN],
            "architect_kinds": [s for s in ACTIVITIES.values() if s.track is Track.ARCHITECT],
            **extra,
        }

    def respond(request: Request, state: WorldState, flash: str | None = None) -> Response:
        if request.headers.get("HX-Request"):
            return templates.TemplateResponse(
                request, "partials/_world.html", context(state, flash=flash)
            )
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> Response:
        return templates.TemplateResponse(request, "index.html", context(service.state()))

    @app.post("/light")
    def light(request: Request) -> Response:
        return respond(request, service.light(), flash="The bonfire is lit.")

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
