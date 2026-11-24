import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    body TEXT
);
CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    status TEXT,
    extracted TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS rules (
    filename TEXT PRIMARY KEY,
    status TEXT,
    created_at TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn
