import re
import sqlite3
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ValidationError

from backend.rules.models import TaxRules

SEED_DIR = Path(__file__).resolve().parent / "seed"
SEED_FILENAME = "retirement_rules_2026-01-01.md"
JSON_BLOCK = re.compile(
    r"^```json[ \t]*\r?\n(.*?)^```", re.DOTALL | re.MULTILINE | re.IGNORECASE
)
FILE_DATE = re.compile(r"^retirement_rules_(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.md$")
STALE_AFTER_DAYS = 90


class RulesFormatError(ValueError):
    pass


def parse_rules(markdown: str) -> TaxRules:
    blocks = JSON_BLOCK.findall(markdown)
    if len(blocks) != 1:
        raise RulesFormatError(f"expected one json block, found {len(blocks)}")
    try:
        return TaxRules.model_validate_json(blocks[0])
    except ValidationError as e:
        raise RulesFormatError(str(e)) from e


class Change(BaseModel):
    path: str
    old: str
    new: str


class RulesStatus(BaseModel):
    current_file: str
    current_date: date | None
    age_days: int | None
    stale: bool
    pending_file: str | None
    changes: list[Change]


def file_date(filename: str) -> date | None:
    """Date prefix of `retirement_rules_YYYY-MM-DD[-N].md`, None if unparseable."""
    match = FILE_DATE.match(filename)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _sort_key(filename: str) -> tuple[date, int]:
    match = FILE_DATE.match(filename)
    when = file_date(filename) or date.min
    return when, int(match.group(2) or 1) if match else 0


def _filenames(conn: sqlite3.Connection, status: str) -> list[str]:
    rows = conn.execute("SELECT filename FROM rules WHERE status = ?", (status,))
    return sorted((r[0] for r in rows), key=_sort_key, reverse=True)


def _load(data_dir: Path, filename: str) -> TaxRules | None:
    try:
        return parse_rules((data_dir / "rules" / filename).read_text())
    except (OSError, RulesFormatError):
        return None


def current_rules(conn: sqlite3.Connection, data_dir: Path) -> tuple[TaxRules, str]:
    """Newest accepted file that still exists and parses, else the seed."""
    for filename in _filenames(conn, "accepted"):
        rules = _load(data_dir, filename)
        if rules is not None:
            return rules, filename
    return parse_rules((SEED_DIR / SEED_FILENAME).read_text()), SEED_FILENAME


def save_pending(
    conn: sqlite3.Connection, data_dir: Path, markdown: str, today: date
) -> str:
    """Write a pending rules file. The same day's pending file is overwritten;
    if that day's file is already accepted, a `-2`, `-3`... suffix is used."""
    parse_rules(markdown)
    base = f"retirement_rules_{today.isoformat()}"
    filename, n = f"{base}.md", 1
    while True:
        row = conn.execute(
            "SELECT status FROM rules WHERE filename = ?", (filename,)
        ).fetchone()
        if row is None or row[0] == "pending":
            break
        n += 1
        filename = f"{base}-{n}.md"
    folder = data_dir / "rules"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_text(markdown)
    conn.execute(
        "INSERT INTO rules (filename, status, created_at) VALUES (?, 'pending', ?) "
        "ON CONFLICT(filename) DO UPDATE SET created_at = excluded.created_at",
        (filename, today.isoformat()),
    )
    conn.commit()
    return filename


class RulesNotFoundError(LookupError):
    pass


def read_markdown(conn: sqlite3.Connection, data_dir: Path, filename: str) -> str:
    if filename == SEED_FILENAME:
        return (SEED_DIR / filename).read_text()
    known = conn.execute(
        "SELECT 1 FROM rules WHERE filename = ?", (filename,)
    ).fetchone()
    if known is None:
        raise RulesNotFoundError(filename)
    try:
        return (data_dir / "rules" / filename).read_text()
    except OSError as e:
        raise RulesNotFoundError(filename) from e


class RulesStateError(ValueError):
    pass


def accept(conn: sqlite3.Connection, data_dir: Path, filename: str) -> None:
    """Re-parse a pending file and mark it accepted. Raises RulesNotFoundError
    (not in the table, so also the seed), RulesStateError (not pending) or
    RulesFormatError, leaving the row unchanged."""
    row = conn.execute(
        "SELECT status FROM rules WHERE filename = ?", (filename,)
    ).fetchone()
    if row is None:
        raise RulesNotFoundError(filename)
    if row[0] != "pending":
        raise RulesStateError(f"{filename} is already {row[0]}")
    parse_rules(read_markdown(conn, data_dir, filename))
    conn.execute("UPDATE rules SET status = 'accepted' WHERE filename = ?", (filename,))
    conn.commit()


def _flatten(value: object, prefix: str = "") -> dict[str, str]:
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, (list, tuple)):
        items = enumerate(value)
    elif isinstance(value, float) and value.is_integer():
        return {prefix: str(int(value))}
    else:
        return {prefix: "" if value is None else str(value)}
    flat: dict[str, str] = {}
    for key, child in items:
        flat.update(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
    return flat


def diff(old: TaxRules, new: TaxRules) -> list[Change]:
    before = _flatten(old.model_dump())
    after = _flatten(new.model_dump())
    return [
        Change(path=p, old=before.get(p, ""), new=after.get(p, ""))
        for p in [*before, *(k for k in after if k not in before)]
        if before.get(p) != after.get(p)
    ]


def status(conn: sqlite3.Connection, data_dir: Path, today: date) -> RulesStatus:
    rules, current_file = current_rules(conn, data_dir)
    current_date = file_date(current_file)
    age = (today - current_date).days if current_date else None
    pending_file, changes = None, []
    for candidate in _filenames(conn, "pending"):
        pending = _load(data_dir, candidate)
        if pending is not None:
            pending_file, changes = candidate, diff(rules, pending)
            break
    return RulesStatus(
        current_file=current_file,
        current_date=current_date,
        age_days=age,
        stale=age is None or age > STALE_AFTER_DAYS,
        pending_file=pending_file,
        changes=changes,
    )
