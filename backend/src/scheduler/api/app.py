"""FastAPI application factory (04-backend-api).

Only the health route exists at F-02; routers arrive with BE-01.
"""

from __future__ import annotations

from fastapi import FastAPI

from scheduler import __version__


def create_app() -> FastAPI:
    app = FastAPI(
        title="Tartib API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
