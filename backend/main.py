from contextlib import closing
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import db, settings
from backend.chat.api import fail_working_turn
from backend.chat.api import router as chat_router
from backend.plan.api import router as plan_router
from backend.profile.api import router as profile_router
from backend.rules.api import router as rules_router
from backend.statements.api import router as statements_router

DEFAULT_DIST = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


def create_app(data_dir: Path | None = None, dist_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Retirement Studio")
    app.state.data_dir = data_dir or settings.data_dir()
    with closing(db.connect(settings.db_path(app.state.data_dir))) as conn:
        fail_working_turn(conn)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(profile_router)
    app.include_router(chat_router)
    app.include_router(plan_router)
    app.include_router(rules_router)
    app.include_router(statements_router)

    dist = dist_dir or DEFAULT_DIST
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")

    return app


app = create_app()
