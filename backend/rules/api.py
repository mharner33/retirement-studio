import importlib
import logging
from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.profile.api import Conn
from backend.rules import store

router = APIRouter(prefix="/api/rules")
logger = logging.getLogger(__name__)


class RulesUpload(BaseModel):
    markdown: str


class Saved(BaseModel):
    filename: str


def run_refresh() -> None:
    """Start the research agent. Imported lazily so the backend does not need
    the agent stack, and so tests can patch this function."""
    try:
        research = importlib.import_module("agent.rules_research")
        make_client = importlib.import_module("agent.backend_client").make_client
        make_model = importlib.import_module("agent.model").make_model
        with make_client() as client:
            research.refresh(client, make_model())
    except Exception:
        logger.exception("rules refresh failed")


@router.get("/status")
def get_status(conn: Conn, request: Request) -> store.RulesStatus:
    return store.status(conn, request.app.state.data_dir, date.today())


@router.post("")
def post_rules(body: RulesUpload, conn: Conn, request: Request) -> Saved:
    try:
        filename = store.save_pending(
            conn, request.app.state.data_dir, body.markdown, date.today()
        )
    except store.RulesFormatError as e:
        raise HTTPException(422, str(e)) from e
    return Saved(filename=filename)


@router.post("/refresh", status_code=202)
def refresh(background: BackgroundTasks) -> dict[str, str]:
    background.add_task(run_refresh)
    return {"status": "started"}


@router.get("/{filename}")
def get_markdown(filename: str, conn: Conn, request: Request) -> PlainTextResponse:
    try:
        text = store.read_markdown(conn, request.app.state.data_dir, filename)
    except store.RulesNotFoundError as e:
        raise HTTPException(404, "Unknown rules file") from e
    return PlainTextResponse(text, media_type="text/markdown")


@router.post("/{filename}/accept")
def accept(filename: str, conn: Conn, request: Request) -> store.RulesStatus:
    data_dir = request.app.state.data_dir
    try:
        store.accept(conn, data_dir, filename)
    except store.RulesNotFoundError as e:
        raise HTTPException(404, "Unknown rules file") from e
    except store.RulesStateError as e:
        raise HTTPException(409, str(e)) from e
    except store.RulesFormatError as e:
        raise HTTPException(422, str(e)) from e
    return store.status(conn, data_dir, date.today())
