import sys
import types
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db, settings
from backend.main import create_app
from backend.rules import api as rules_api
from backend.rules import store

SEED_TEXT = (store.SEED_DIR / store.SEED_FILENAME).read_text()
NEW_NAME = f"retirement_rules_{date.today().isoformat()}.md"


@pytest.fixture
def new_text() -> str:
    mfj = SEED_TEXT.index('"mfj": [')
    head, tail = SEED_TEXT[:mfj], SEED_TEXT[mfj:]
    text = head + tail.replace('"up_to": 100800', '"up_to": 100900', 1)
    assert text != SEED_TEXT
    return text


def test_post_valid_rules_is_pending_not_current(
    client: TestClient, new_text: str
) -> None:
    res = client.post("/api/rules", json={"markdown": new_text})
    assert res.status_code == 200
    assert res.json() == {"filename": NEW_NAME}
    status = client.get("/api/rules/status").json()
    assert status["current_file"] == store.SEED_FILENAME
    assert status["pending_file"] == NEW_NAME
    assert client.get(f"/api/rules/{NEW_NAME}").text == new_text


def test_post_malformed_rules_422_keeps_current(
    client: TestClient, tmp_path: Path
) -> None:
    res = client.post("/api/rules", json={"markdown": "# nothing here"})
    assert res.status_code == 422
    status = client.get("/api/rules/status").json()
    assert status["current_file"] == store.SEED_FILENAME
    assert status["pending_file"] is None
    assert not (tmp_path / "rules").exists()


def test_accept_makes_current(
    client: TestClient, new_text: str, tmp_path: Path
) -> None:
    client.post("/api/rules", json={"markdown": new_text})
    res = client.post(f"/api/rules/{NEW_NAME}/accept")
    assert res.status_code == 200
    assert res.json()["current_file"] == NEW_NAME
    assert res.json()["pending_file"] is None
    rules, filename = store.current_rules(
        db.connect(settings.db_path(tmp_path)), tmp_path
    )
    assert filename == NEW_NAME
    assert rules.federal_brackets["mfj"][1].up_to == 100_900


def test_accept_unknown_404_and_invalid_file_422(
    client: TestClient, tmp_path: Path
) -> None:
    assert client.post("/api/rules/nope.md/accept").status_code == 404
    assert client.get("/api/rules/nope.md").status_code == 404
    conn = db.connect(settings.db_path(tmp_path))
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "retirement_rules_2027-01-01.md").write_text("broken")
    conn.execute(
        "INSERT INTO rules VALUES ('retirement_rules_2027-01-01.md','pending','x')"
    )
    conn.commit()
    res = client.post("/api/rules/retirement_rules_2027-01-01.md/accept")
    assert res.status_code == 422
    row = conn.execute("SELECT status FROM rules").fetchone()
    assert row[0] == "pending"


def test_diff_lists_changed_bracket(client: TestClient, new_text: str) -> None:
    client.post("/api/rules", json={"markdown": new_text})
    changes = client.get("/api/rules/status").json()["changes"]
    assert changes == [
        {
            "path": "federal_brackets.mfj.1.up_to",
            "old": "100800",
            "new": "100900",
        }
    ]


def test_diff_added_and_removed_paths() -> None:
    old = store.parse_rules(SEED_TEXT)
    new = old.model_copy(deep=True)
    new.federal_brackets["mfj"].pop()
    new.colorado.rate = 0.04
    got = {c.path: (c.old, c.new) for c in store.diff(old, new)}
    last = len(old.federal_brackets["mfj"]) - 1
    assert got[f"federal_brackets.mfj.{last}.rate"][1] == ""
    assert got["colorado.rate"][1] == "0.04"


def test_stale_after_90_days(tmp_path: Path) -> None:
    conn = db.connect(settings.db_path(tmp_path))
    seed_day = date(2026, 1, 1)
    fresh = store.status(conn, tmp_path, date(2026, 4, 1))
    assert (fresh.age_days, fresh.stale) == (90, False)
    old = store.status(conn, tmp_path, date(2026, 4, 2))
    assert (old.age_days, old.stale, old.current_date) == (91, True, seed_day)


def test_unparseable_filename_date_is_stale(tmp_path: Path) -> None:
    conn = db.connect(settings.db_path(tmp_path))
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "retirement_rules_2026-13-45.md").write_text(SEED_TEXT)
    conn.execute(
        "INSERT INTO rules VALUES ('retirement_rules_2026-13-45.md','accepted','x')"
    )
    conn.commit()
    status = store.status(conn, tmp_path, date(2026, 2, 1))
    assert status.current_file == "retirement_rules_2026-13-45.md"
    assert status.stale
    assert status.age_days is None


def test_same_day_pending_overwritten_accepted_gets_suffix(tmp_path: Path) -> None:
    conn = db.connect(settings.db_path(tmp_path))
    today = date(2026, 11, 24)
    first = store.save_pending(conn, tmp_path, SEED_TEXT, today)

    edited = SEED_TEXT.replace("Seed rules file", "Edited rules file", 1)
    assert edited != SEED_TEXT
    again = store.save_pending(conn, tmp_path, edited, today)
    assert (tmp_path / "rules" / again).read_text() == edited
    assert first == again == "retirement_rules_2026-11-24.md"
    assert conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0] == 1
    store.accept(conn, tmp_path, first)
    second = store.save_pending(conn, tmp_path, SEED_TEXT, today)
    assert second == "retirement_rules_2026-11-24-2.md"
    store.accept(conn, tmp_path, second)
    assert store.current_rules(conn, tmp_path)[1] == second
    assert store.file_date(second) == today


def test_refresh_returns_202(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(rules_api, "run_refresh", lambda: calls.append("ran"))
    res = client.post("/api/rules/refresh")
    assert res.status_code == 202
    assert calls == ["ran"]


class FakeClient(str):
    def __new__(cls) -> "FakeClient":
        return super().__new__(cls, "client")

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_run_refresh_calls_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[object, object]] = []
    fake = types.ModuleType("agent.rules_research")
    fake.refresh = lambda client, model: seen.append((client, model))  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent.rules_research", fake)
    monkeypatch.setattr("agent.model.make_model", lambda: "model")
    monkeypatch.setattr("agent.backend_client.make_client", FakeClient)
    rules_api.run_refresh()
    assert len(seen) == 1
    assert seen[0] == ("client", "model")


def test_app_factory_runs(tmp_path: Path) -> None:
    assert create_app(tmp_path) is not None


def test_refresh_agent_failure_does_not_propagate(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    research = types.ModuleType("agent.rules_research")

    def boom(client: object, model: object) -> None:
        raise RuntimeError("model down")

    research.refresh = boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent.rules_research", research)
    monkeypatch.setattr("agent.model.make_model", lambda: "model")
    monkeypatch.setattr("agent.backend_client.make_client", FakeClient)
    rules_api.run_refresh()
    assert "rules refresh failed" in caplog.text


def test_refresh_missing_agent_module_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setitem(sys.modules, "agent.rules_research", None)
    rules_api.run_refresh()
    assert "rules refresh failed" in caplog.text


def test_traversal_and_unknown_names_are_404(client: TestClient) -> None:
    evil = "..%2F..%2Fetc%2Fpasswd"
    assert client.get(f"/api/rules/{evil}").status_code == 404
    assert client.post(f"/api/rules/{evil}/accept").status_code == 404


def test_file_on_disk_but_not_in_db_is_refused(
    client: TestClient, tmp_path: Path
) -> None:
    (tmp_path / "rules").mkdir()
    name = "retirement_rules_2027-01-01.md"
    (tmp_path / "rules" / name).write_text(SEED_TEXT)
    assert client.get(f"/api/rules/{name}").status_code == 404
    assert client.post(f"/api/rules/{name}/accept").status_code == 404


def test_accept_seed_404_and_already_accepted_409(
    client: TestClient, new_text: str
) -> None:
    assert client.post(f"/api/rules/{store.SEED_FILENAME}/accept").status_code == 404
    client.post("/api/rules", json={"markdown": new_text})
    assert client.post(f"/api/rules/{NEW_NAME}/accept").status_code == 200
    assert client.post(f"/api/rules/{NEW_NAME}/accept").status_code == 409
