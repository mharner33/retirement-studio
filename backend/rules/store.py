import re
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from backend.rules.models import TaxRules

SEED_DIR = Path(__file__).resolve().parent / "seed"
SEED_FILENAME = "retirement_rules_2026-01-01.md"
JSON_BLOCK = re.compile(r"^```json\n(.*?)^```", re.DOTALL | re.MULTILINE)


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


def current_rules(conn: sqlite3.Connection, data_dir: Path) -> tuple[TaxRules, str]:
    row = conn.execute(
        "SELECT filename FROM rules WHERE status = 'accepted' "
        "ORDER BY filename DESC LIMIT 1"
    ).fetchone()
    if row:
        filename = row[0]
        path = data_dir / "rules" / filename
    else:
        filename = SEED_FILENAME
        path = SEED_DIR / filename
    return parse_rules(path.read_text()), filename
