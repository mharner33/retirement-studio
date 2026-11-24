from pathlib import Path

from fastapi import FastAPI

from backend import db, settings


def create_app(data_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Retirement Studio")
    app.state.data_dir = data_dir or settings.data_dir()
    db.connect(app.state.data_dir / "studio.db").close()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
