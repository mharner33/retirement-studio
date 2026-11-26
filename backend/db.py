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
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY,
    role TEXT,
    text TEXT,
    sources TEXT,
    tool_results TEXT,
    unchecked INTEGER,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS chat_changes (
    id INTEGER PRIMARY KEY,
    message_id INTEGER,
    changes TEXT,
    reason TEXT,
    status TEXT,
    lines TEXT
);
CREATE TABLE IF NOT EXISTS chat_turn (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT,
    step TEXT
);
INSERT OR IGNORE INTO chat_turn (id, status) VALUES (1, 'idle');
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn
