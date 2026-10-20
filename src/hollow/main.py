"""ASGI entry point: `uvicorn hollow.main:app`."""

from hollow.adapters.web.app import create_app

app = create_app()
