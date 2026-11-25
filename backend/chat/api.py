import importlib
import logging
import sqlite3
from contextlib import closing
from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from backend import db, settings
from backend.chat import store
from backend.chat.benchmark import Benchmark
from backend.chat.benchmark import benchmark as spending_benchmark
from backend.chat.masking import mask_for_model, unmask
from backend.chat.models import (
    ChangeCard,
    ChatState,
    ContextMessage,
    Reply,
    Step,
    UserMessage,
)
from backend.plan.api import _context, plan_for
from backend.plan.changes import (
    ChangeError,
    ChangeLine,
    ProfileChange,
    apply_changes,
    describe,
)
from backend.profile.api import Conn, load_household, save_household
from backend.profile.models import Household

router = APIRouter(prefix="/api/chat")
logger = logging.getLogger(__name__)


def run_chat() -> None:
    """Start the chat agent. Imported lazily so the backend does not need the
    agent stack, and so tests can patch this function."""
    try:
        importlib.import_module("agent.chat").respond()
    except Exception:
        logger.exception("chat reply failed")
    with closing(db.connect(settings.db_path(settings.data_dir()))) as conn:
        if store.turn_status(conn) == "working":
            store.set_turn(conn, "failed")


def fail_working_turn(conn: sqlite3.Connection) -> None:
    if store.turn_status(conn) == "working":
        store.set_turn(conn, "failed")


def require_profile(conn: sqlite3.Connection) -> Household:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    return household


@router.get("")
def get_chat(conn: Conn) -> ChatState:
    household = load_household(conn)
    messages = store.messages(conn)
    if household:
        for m in messages:
            m.text = unmask(m.text, household)
            for c in m.changes:
                c.reason = unmask(c.reason, household)
    return ChatState(
        status=store.turn_status(conn),  # type: ignore[arg-type]
        step=store.turn_step(conn),
        messages=messages,
    )


@router.post("/messages", status_code=202)
def post_message(
    body: UserMessage, conn: Conn, background: BackgroundTasks
) -> dict[str, str]:
    if not body.text.strip():
        raise HTTPException(422, "Message is empty")
    household = require_profile(conn)
    if store.turn_status(conn) == "working":
        raise HTTPException(409, "A reply is in progress")
    store.add_message(conn, "user", mask_for_model(body.text.strip(), household))
    store.set_turn(conn, "working")
    background.add_task(run_chat)
    return {"status": "started"}


def change_card(conn: sqlite3.Connection, change_id: int) -> ChangeCard:
    return store.card(store.get_change(conn, change_id))  # type: ignore[arg-type]


def proposed_change(conn: sqlite3.Connection, change_id: int) -> tuple:
    row = store.get_change(conn, change_id)
    if row is None:
        raise HTTPException(404, "Unknown change")
    if row[2] != "proposed":
        raise HTTPException(409, f"Already {row[2]}")
    return row


@router.post("/changes/check")
def check_changes(changes: list[ProfileChange], conn: Conn) -> list[ChangeLine]:
    household = require_profile(conn)
    try:
        lines = describe(household, changes)
    except ChangeError as e:
        raise HTTPException(422, str(e)) from e
    for line in lines:
        line.label = mask_for_model(line.label, household)
    return lines


@router.post("/changes/{change_id}/apply")
def apply_change(change_id: int, conn: Conn) -> ChangeCard:
    row = proposed_change(conn, change_id)
    household = require_profile(conn)
    try:
        updated = apply_changes(household, store.changes_adapter.validate_json(row[4]))
    except ChangeError as e:
        raise HTTPException(422, str(e)) from e
    save_household(conn, updated)
    store.set_change_status(conn, change_id, "applied")
    conn.commit()
    return change_card(conn, change_id)


@router.post("/changes/{change_id}/dismiss")
def dismiss_change(change_id: int, conn: Conn) -> ChangeCard:
    proposed_change(conn, change_id)
    store.set_change_status(conn, change_id, "dismissed")
    conn.commit()
    return change_card(conn, change_id)


@router.delete("", status_code=204)
def delete_chat(conn: Conn) -> Response:
    if store.turn_status(conn) == "working":
        raise HTTPException(409, "A reply is in progress")
    store.clear(conn)
    return Response(status_code=204)


@router.get("/context")
def get_context(conn: Conn) -> list[ContextMessage]:
    return store.context(conn)


@router.get("/profile")
def get_profile_text(conn: Conn) -> PlainTextResponse:
    household = load_household(conn)
    if household is None:
        raise HTTPException(404, "No profile saved")
    text = household.model_dump_json(by_alias=True, indent=2)
    return PlainTextResponse(mask_for_model(text, household))


@router.put("/step", status_code=204)
def put_step(body: Step, conn: Conn) -> Response:
    conn.execute("UPDATE chat_turn SET step = ?", (body.text,))
    conn.commit()
    return Response(status_code=204)


@router.post("/reply")
def post_reply(reply: Reply, conn: Conn) -> dict[str, str]:
    household = require_profile(conn)
    try:
        described = [(p, describe(household, p.changes)) for p in reply.proposals]
    except ChangeError as e:
        raise HTTPException(422, str(e)) from e
    message_id = store.add_message(conn, "assistant", reply.text, reply)
    for proposal, lines in described:
        store.add_change(conn, message_id, proposal, lines)
    store.set_turn(conn, "idle")
    return {"status": "stored"}


@router.get("/benchmark")
def get_benchmark(conn: Conn, request: Request) -> Benchmark:
    household, rules, filename, stale = _context(conn, request)
    plan = plan_for(household, rules, filename, date.today().year, stale)
    return spending_benchmark(household, plan)
