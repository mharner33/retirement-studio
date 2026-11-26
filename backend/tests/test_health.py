from fastapi.testclient import TestClient

from backend import db
from backend.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_connect_creates_tables(tmp_path) -> None:
    conn = db.connect(tmp_path / "t.db")
    names = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert names == {
        "profile",
        "statements",
        "rules",
        "chat_messages",
        "chat_changes",
        "chat_turn",
    }


def test_serves_dashboard_when_built(tmp_path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<div id="root"></div>')
    client = TestClient(create_app(tmp_path, dist_dir=dist))
    assert client.get("/").text == '<div id="root"></div>'
    assert client.get("/api/health").json() == {"status": "ok"}


def test_no_dashboard_route_when_not_built(tmp_path) -> None:
    client = TestClient(create_app(tmp_path, dist_dir=tmp_path / "missing"))
    assert client.get("/").status_code == 404
