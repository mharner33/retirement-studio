from pathlib import Path

import pytest

from backend import db, settings
from backend.rules import store
from backend.rules.store import RulesFormatError

SEED = store.SEED_DIR / store.SEED_FILENAME


def test_seed_parses() -> None:
    rules = store.parse_rules(SEED.read_text())
    assert rules.year == 2026
    mfj = rules.federal_brackets["mfj"]
    limits = [b.up_to or 0 for b in mfj[:-1]]
    assert all(limit > 0 for limit in limits)
    assert limits == sorted(limits)
    assert mfj[-1].up_to is None
    assert rules.uniform_lifetime_table[73] == 26.5
    assert all(isinstance(age, int) for age in rules.uniform_lifetime_table)
    assert rules.ss_taxation_thresholds["mfj"] == (32_000, 44_000)


def test_missing_json_block_raises() -> None:
    with pytest.raises(RulesFormatError):
        store.parse_rules("# Rules\n\nNo figures here.\n")


def test_invalid_json_block_raises() -> None:
    with pytest.raises(RulesFormatError):
        store.parse_rules('```json\n{"year": 2026}\n```\n')


def test_two_json_blocks_raise() -> None:
    block = SEED.read_text().split("```json", 1)[1]
    with pytest.raises(RulesFormatError):
        store.parse_rules(f"```json{block}\n```json{block}")


def test_current_rules_falls_back_to_seed(tmp_path: Path) -> None:
    conn = db.connect(settings.db_path(tmp_path))
    rules, filename = store.current_rules(conn, tmp_path)
    assert filename == store.SEED_FILENAME
    assert rules.year == 2026


def write_rules(data_dir: Path, filename: str, year: int) -> None:
    text = SEED.read_text().replace('"year": 2026', f'"year": {year}')
    (data_dir / "rules").mkdir(exist_ok=True)
    (data_dir / "rules" / filename).write_text(text)


def test_current_rules_prefers_newest_accepted(tmp_path: Path) -> None:
    conn = db.connect(settings.db_path(tmp_path))
    write_rules(tmp_path, "retirement_rules_2027-01-01.md", 2027)
    write_rules(tmp_path, "retirement_rules_2027-06-01.md", 2028)
    write_rules(tmp_path, "retirement_rules_2027-09-01.md", 2029)
    conn.executemany(
        "INSERT INTO rules (filename, status, created_at) VALUES (?, ?, ?)",
        [
            ("retirement_rules_2027-01-01.md", "accepted", "2027-01-01"),
            ("retirement_rules_2027-06-01.md", "accepted", "2027-06-01"),
            ("retirement_rules_2027-09-01.md", "pending", "2027-09-01"),
        ],
    )
    conn.commit()
    rules, filename = store.current_rules(conn, tmp_path)
    assert filename == "retirement_rules_2027-06-01.md"
    assert rules.year == 2028
