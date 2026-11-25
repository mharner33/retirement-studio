import importlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import TypeAdapter

from backend.profile.api import Conn, load_household, save_household
from backend.profile.models import Account, Household
from backend.statements import pdf
from backend.statements.models import (
    ExtractedDocument,
    ExtractedSsStatement,
    ExtractedStatement,
    StatementRow,
    UploadResult,
)

router = APIRouter(prefix="/api/statements")
logger = logging.getLogger(__name__)

MAX_BYTES = 20 * 1024 * 1024
document_adapter = TypeAdapter(ExtractedDocument)


def run_extract(statement_id: int) -> None:
    """Start the extraction agent. Imported lazily so the backend does not need
    the agent stack, and so tests can patch this function."""
    try:
        importlib.import_module("agent.extraction").extract(statement_id)
    except Exception:
        logger.exception("statement extraction failed")


def statements_dir(request: Request) -> Path:
    return request.app.state.data_dir / "statements"


def register(conn: sqlite3.Connection, filename: str) -> int:
    cursor = conn.execute(
        "INSERT INTO statements (filename, status, created_at) "
        "VALUES (?, 'uploaded', ?)",
        (filename, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return cast(int, cursor.lastrowid)


def known(conn: sqlite3.Connection, filename: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM statements WHERE filename = ?", (filename,)
        ).fetchone()
        is not None
    )


def save_one(
    conn: sqlite3.Connection, folder: Path, upload: UploadFile
) -> UploadResult:
    filename = Path((upload.filename or "").replace("\\", "/")).name
    result = UploadResult(filename=filename)
    content = upload.file.read(MAX_BYTES + 1)
    if not filename.lower().endswith(".pdf") or not content.startswith(b"%PDF"):
        result.error = "Only PDF files are accepted"
    elif len(content) > MAX_BYTES:
        result.error = "File is larger than 20 MB"
    elif known(conn, filename) or (folder / filename).exists():
        result.error = "Already uploaded"
    else:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(content)
        result.id = register(conn, filename)
    return result


@router.post("")
def upload_statements(
    files: list[UploadFile], conn: Conn, request: Request
) -> list[UploadResult]:
    folder = statements_dir(request)
    return [save_one(conn, folder, f) for f in files]


@router.post("/scan")
def scan(conn: Conn, request: Request) -> list[UploadResult]:
    folder = statements_dir(request)
    results = []
    for path in sorted(folder.glob("*")) if folder.is_dir() else []:
        if path.suffix.lower() != ".pdf" or known(conn, path.name):
            continue
        if path.read_bytes()[:4] == b"%PDF":
            results.append(
                UploadResult(filename=path.name, id=register(conn, path.name))
            )
        else:
            results.append(
                UploadResult(filename=path.name, error="Only PDF files are accepted")
            )
    return results


def row_to_model(row: tuple) -> StatementRow:
    extracted = document_adapter.validate_json(row[3]) if row[3] else None
    return StatementRow(
        id=row[0],
        filename=row[1],
        status=row[2],
        extracted=extracted,
        created_at=row[4],
    )


def get_row(conn: sqlite3.Connection, statement_id: int) -> tuple:
    row = conn.execute(
        "SELECT id, filename, status, extracted, created_at "
        "FROM statements WHERE id = ?",
        (statement_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Unknown statement")
    return row


def set_status(conn: sqlite3.Connection, statement_id: int, status: str) -> None:
    conn.execute(
        "UPDATE statements SET status = ? WHERE id = ?", (status, statement_id)
    )
    conn.commit()


@router.get("")
def list_statements(conn: Conn) -> list[StatementRow]:
    rows = conn.execute(
        "SELECT id, filename, status, extracted, created_at FROM statements ORDER BY id"
    ).fetchall()
    return [row_to_model(r) for r in rows]


@router.get("/{statement_id}/text")
def get_text(statement_id: int, conn: Conn, request: Request) -> PlainTextResponse:
    row = get_row(conn, statement_id)
    text = pdf.extract_text(statements_dir(request) / row[1])
    if not text.strip():
        set_status(conn, statement_id, "no_text")
        raise HTTPException(422, "No text found in this PDF")
    household = load_household(conn)
    terms = household.mask_terms if household else []
    return PlainTextResponse(pdf.mask(text, terms))


def store_extraction(
    conn: sqlite3.Connection,
    statement_id: int,
    document: ExtractedDocument,
    status: str,
) -> None:
    conn.execute(
        "UPDATE statements SET extracted = ?, status = ? WHERE id = ?",
        (document_adapter.dump_json(document).decode(), status, statement_id),
    )
    conn.commit()


@router.put("/{statement_id}/extraction")
def put_extraction(
    statement_id: int, document: ExtractedDocument, conn: Conn
) -> StatementRow:
    get_row(conn, statement_id)
    store_extraction(conn, statement_id, document, "pending_review")
    return row_to_model(get_row(conn, statement_id))


def apply_accounts(household: Household, document: ExtractedStatement) -> None:
    for item in document.accounts:
        match = next(
            (
                a
                for a in household.accounts
                if item.last4
                and (a.kind, a.owner, a.last4) == (item.kind, item.owner, item.last4)
            ),
            None,
        )
        if match:
            match.balance = item.balance
            if item.cost_basis is not None:
                match.cost_basis = item.cost_basis
            match.as_of = document.statement_date
        else:
            suffix = item.last4 or len(household.accounts) + 1
            household.accounts.append(
                Account(
                    id=f"{item.kind}-{item.owner}-{suffix}",
                    kind=item.kind,
                    owner=item.owner,
                    label=item.label,
                    balance=item.balance,
                    cost_basis=item.cost_basis or 0,
                    last4=item.last4,
                    as_of=document.statement_date,
                )
            )


def apply_social_security(household: Household, document: ExtractedSsStatement) -> None:
    if document.person is None:
        raise body_error("person", "Choose whose statement this is")
    person = household.spouse if document.person == "spouse" else household.self_
    if person is None:
        raise body_error("person", "The profile has no spouse")
    person.ss_at_62 = document.monthly_at_62
    person.ss_at_fra = document.monthly_at_fra
    person.ss_at_70 = document.monthly_at_70


def body_error(field: str, msg: str) -> HTTPException:
    detail = [{"loc": ["body", field], "msg": msg, "type": "value_error"}]
    return HTTPException(422, detail)


@router.post("/{statement_id}/accept")
def accept(statement_id: int, document: ExtractedDocument, conn: Conn) -> StatementRow:
    get_row(conn, statement_id)
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "Complete your profile first")
    if isinstance(document, ExtractedStatement):
        apply_accounts(household, document)
    else:
        apply_social_security(household, document)
    save_household(conn, household)
    store_extraction(conn, statement_id, document, "accepted")
    return row_to_model(get_row(conn, statement_id))


@router.post("/{statement_id}/extract", status_code=202)
def extract(
    statement_id: int, conn: Conn, background: BackgroundTasks
) -> dict[str, str]:
    get_row(conn, statement_id)
    set_status(conn, statement_id, "reading")
    background.add_task(run_extract, statement_id)
    return {"status": "started"}
