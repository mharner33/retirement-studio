from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import db, settings

DEFAULT_DIST = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


def create_app(data_dir: Path | None = None, dist_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Retirement Studio")
    app.state.data_dir = data_dir or settings.data_dir()
    db.connect(app.state.data_dir / "studio.db").close()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    dist = dist_dir or DEFAULT_DIST
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")

    return app


app = create_app()
