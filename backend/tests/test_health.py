from fastapi.testclient import TestClient

from backend import db


def test_health_returns_ok(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_connect_creates_tables(tmp_path) -> None:
    conn = db.connect(tmp_path / "t.db")
    names = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert names == {"profile", "statements", "rules"}
