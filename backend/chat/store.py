import sqlite3
from datetime import UTC, datetime
from typing import cast

from pydantic import TypeAdapter

from backend.chat.models import (
    ChangeCard,
    ChatMessage,
    ContextMessage,
    Proposal,
    Reply,
    Source,
)
from backend.plan.changes import ChangeLine, ProfileChange

CONTEXT_LIMIT = 20

changes_adapter = TypeAdapter(list[ProfileChange])
lines_adapter = TypeAdapter(list[ChangeLine])
sources_adapter = TypeAdapter(list[Source])
strings_adapter = TypeAdapter(list[str])


def turn_status(conn: sqlite3.Connection) -> str:
    return cast(str, conn.execute("SELECT status FROM chat_turn").fetchone()[0])


def turn_step(conn: sqlite3.Connection) -> str | None:
    return cast("str | None", conn.execute("SELECT step FROM chat_turn").fetchone()[0])


def set_turn(conn: sqlite3.Connection, status: str, step: str | None = None) -> None:
    conn.execute("UPDATE chat_turn SET status = ?, step = ?", (status, step))
    conn.commit()


def add_message(
    conn: sqlite3.Connection, role: str, text: str, reply: Reply | None = None
) -> int:
    sources = reply.sources if reply else []
    tool_results = reply.tool_results if reply else []
    cursor = conn.execute(
        "INSERT INTO chat_messages "
        "(role, text, sources, tool_results, unchecked, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            role,
            text,
            sources_adapter.dump_json(sources).decode(),
            strings_adapter.dump_json(tool_results).decode(),
            int(reply.unchecked) if reply else 0,
            datetime.now(UTC).isoformat(),
        ),
    )
    return cast(int, cursor.lastrowid)


def add_change(
    conn: sqlite3.Connection,
    message_id: int,
    proposal: Proposal,
    lines: list[ChangeLine],
) -> None:
    conn.execute(
        "INSERT INTO chat_changes (message_id, changes, reason, status, lines) "
        "VALUES (?, ?, ?, 'proposed', ?)",
        (
            message_id,
            changes_adapter.dump_json(proposal.changes).decode(),
            proposal.reason,
            lines_adapter.dump_json(lines).decode(),
        ),
    )


def card(row: tuple) -> ChangeCard:
    return ChangeCard(
        id=row[0],
        reason=row[1],
        status=row[2],
        lines=lines_adapter.validate_json(row[3]),
    )


def get_change(conn: sqlite3.Connection, change_id: int) -> tuple | None:
    return conn.execute(
        "SELECT id, reason, status, lines, changes FROM chat_changes WHERE id = ?",
        (change_id,),
    ).fetchone()


def set_change_status(conn: sqlite3.Connection, change_id: int, status: str) -> None:
    conn.execute("UPDATE chat_changes SET status = ? WHERE id = ?", (status, change_id))


def messages(conn: sqlite3.Connection) -> list[ChatMessage]:
    cards: dict[int, list[ChangeCard]] = {}
    for row in conn.execute(
        "SELECT id, reason, status, lines, message_id FROM chat_changes ORDER BY id"
    ):
        cards.setdefault(row[4], []).append(card(row))
    rows = conn.execute(
        "SELECT id, role, text, sources, unchecked FROM chat_messages ORDER BY id"
    ).fetchall()
    return [
        ChatMessage(
            id=r[0],
            role=r[1],
            text=r[2],
            sources=sources_adapter.validate_json(r[3]),
            unchecked=bool(r[4]),
            changes=cards.get(r[0], []),
        )
        for r in rows
    ]


def context(conn: sqlite3.Connection) -> list[ContextMessage]:
    rows = conn.execute(
        "SELECT role, text, tool_results FROM chat_messages ORDER BY id DESC LIMIT ?",
        (CONTEXT_LIMIT,),
    ).fetchall()
    return [
        ContextMessage(
            role=r[0], text=r[1], tool_results=strings_adapter.validate_json(r[2])
        )
        for r in reversed(rows)
    ]


def clear(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM chat_changes")
    conn.execute("DELETE FROM chat_messages")
    conn.execute("UPDATE chat_turn SET status = 'idle', step = NULL")
    conn.commit()
