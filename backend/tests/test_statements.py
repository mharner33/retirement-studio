import sys
import types
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.profile.models import Household
from backend.statements import api as statements_api
from backend.statements import pdf
from backend.tests.conftest import build_sample_household


def make_pdf(text: str | None = "Statement balance 1,000") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    else:
        page.draw_rect(pymupdf.Rect(50, 50, 200, 200), fill=(0, 0, 0))
    return doc.tobytes()


def upload(client: TestClient, *files: tuple[str, bytes]):
    return client.post(
        "/api/statements",
        files=[("files", (name, content)) for name, content in files],
    )


def put_profile(client: TestClient, household: Household | None = None) -> None:
    household = household or build_sample_household()
    res = client.put(
        "/api/profile", json=household.model_dump(mode="json", by_alias=True)
    )
    assert res.status_code == 200


def account_doc(**overrides: object) -> dict:
    account = {
        "kind": "pretax",
        "owner_hint": "Alex",
        "owner": "self",
        "label": "401(k)",
        "balance": 950_000,
        "cost_basis": None,
        "last4": "1234",
    }
    account.update(overrides)
    return {
        "doc_type": "account",
        "institution": "Example Bank",
        "statement_date": "2026-11-20",
        "accounts": [account],
    }


def ss_doc(person: str | None) -> dict:
    return {
        "doc_type": "social_security",
        "statement_date": "2026-10-01",
        "person": person,
        "monthly_at_62": 1_450,
        "monthly_at_fra": 2_100,
        "fra_age": "67",
        "monthly_at_70": 2_650,
    }


def new_statement(client: TestClient, name: str = "a.pdf") -> int:
    return upload(client, (name, make_pdf())).json()[0]["id"]


def test_extract_text_from_generated_pdf(tmp_path: Path) -> None:
    path = tmp_path / "s.pdf"
    path.write_bytes(make_pdf("Hello retirement"))
    assert "Hello retirement" in pdf.extract_text(path)


def test_mask_account_numbers_keeps_last4() -> None:
    assert pdf.mask("Account 1234-5678-9012", []) == "Account ****9012"


def test_mask_ssn_keeps_last4() -> None:
    assert pdf.mask("SSN 123-45-6789", []) == "SSN ****6789"


def test_mask_leaves_dollar_amounts() -> None:
    text = "Balance $1,234,567.89"
    assert pdf.mask(text, []) == text


@pytest.mark.parametrize("text", ["As of 2026-11-24", "As of 11/24/2026"])
def test_mask_leaves_dates(text: str) -> None:
    assert pdf.mask(text, []) == text


def test_mask_terms_case_insensitive() -> None:
    out = pdf.mask("Alex SMITH met alex smith", ["Alex Smith", ""])
    assert out == "[MASKED] met [MASKED]"


def test_image_only_pdf_sets_no_text(client: TestClient) -> None:
    sid = upload(client, ("scan.pdf", make_pdf(None))).json()[0]["id"]
    assert client.get(f"/api/statements/{sid}/text").status_code == 422
    statuses = {s["id"]: s["status"] for s in client.get("/api/statements").json()}
    assert statuses[sid] == "no_text"


def test_text_is_masked_with_profile_terms(client: TestClient) -> None:
    put_profile(
        client, build_sample_household().model_copy(update={"mask_terms": ["Alex"]})
    )
    sid = upload(client, ("a.pdf", make_pdf("Alex acct 1234-5678-9012"))).json()[0][
        "id"
    ]
    text = client.get(f"/api/statements/{sid}/text").text
    assert "[MASKED]" in text
    assert "****9012" in text
    assert "5678" not in text


def test_upload_multiple_files_returns_one_result_each(client: TestClient) -> None:
    res = upload(client, ("a.pdf", make_pdf()), ("b.pdf", make_pdf()))
    results = res.json()
    assert [r["filename"] for r in results] == ["a.pdf", "b.pdf"]
    assert all(r["id"] and r["error"] is None for r in results)
    assert len(client.get("/api/statements").json()) == 2


def test_upload_mixed_batch_saves_pdfs_and_reports_non_pdf(
    client: TestClient, tmp_path: Path
) -> None:
    results = upload(
        client, ("a.pdf", make_pdf()), ("notes.txt", b"hi"), ("b.pdf", make_pdf())
    ).json()
    assert [r["id"] is not None for r in results] == [True, False, True]
    assert results[1]["error"] == "Only PDF files are accepted"
    assert (tmp_path / "statements" / "a.pdf").exists()
    assert not (tmp_path / "statements" / "notes.txt").exists()


def test_upload_rejects_pdf_name_without_magic_bytes(client: TestClient) -> None:
    result = upload(client, ("fake.pdf", b"not a pdf")).json()[0]
    assert result["error"] == "Only PDF files are accepted"


def test_upload_duplicate_filename(client: TestClient) -> None:
    upload(client, ("a.pdf", make_pdf()))
    result = upload(client, ("a.pdf", make_pdf())).json()[0]
    assert result["id"] is None
    assert result["error"] == "Already uploaded"


def test_upload_path_traversal_stays_in_statements(
    client: TestClient, tmp_path: Path
) -> None:
    result = upload(client, ("../../evil.pdf", make_pdf())).json()[0]
    assert result["filename"] == "evil.pdf"
    assert (tmp_path / "statements" / "evil.pdf").exists()
    assert not (tmp_path.parent / "evil.pdf").exists()
    assert not (tmp_path.parent.parent / "evil.pdf").exists()


def test_upload_too_large(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(statements_api, "MAX_BYTES", 100)
    result = upload(client, ("big.pdf", make_pdf())).json()[0]
    assert result["id"] is None
    assert result["error"] == "File is larger than 20 MB"


def test_scan_registers_new_pdfs_only(client: TestClient, tmp_path: Path) -> None:
    upload(client, ("a.pdf", make_pdf()))
    (tmp_path / "statements" / "dropped.pdf").write_bytes(make_pdf())
    results = client.post("/api/statements/scan").json()
    assert [r["filename"] for r in results] == ["dropped.pdf"]
    assert results[0]["id"] is not None
    assert client.post("/api/statements/scan").json() == []
    assert len(client.get("/api/statements").json()) == 2


def test_put_extraction_sets_pending_review(client: TestClient) -> None:
    sid = new_statement(client)
    assert (
        client.put(f"/api/statements/{sid}/extraction", json=account_doc()).status_code
        == 200
    )
    row = client.get("/api/statements").json()[0]
    assert row["status"] == "pending_review"
    assert row["extracted"]["institution"] == "Example Bank"


def test_unknown_statement_404(client: TestClient) -> None:
    assert client.get("/api/statements/99/text").status_code == 404
    assert (
        client.post("/api/statements/99/accept", json=account_doc()).status_code == 404
    )
    assert client.post("/api/statements/99/extract").status_code == 404


def test_accept_updates_matching_account_balance(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    res = client.post(f"/api/statements/{sid}/accept", json=account_doc())
    assert res.status_code == 200
    accounts = client.get("/api/profile").json()["accounts"]
    a1 = next(a for a in accounts if a["id"] == "a1")
    assert a1["balance"] == 950_000
    assert a1["as_of"] == "2026-11-20"
    assert a1["cost_basis"] == 0
    assert len(accounts) == 4
    assert client.get("/api/statements").json()[0]["status"] == "accepted"


def test_accept_updates_cost_basis_when_given(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    doc = account_doc(
        kind="taxable", label="Brokerage", last4="9012", cost_basis=160_000
    )
    client.post(f"/api/statements/{sid}/accept", json=doc)
    a3 = next(
        a for a in client.get("/api/profile").json()["accounts"] if a["id"] == "a3"
    )
    assert a3["cost_basis"] == 160_000


def test_accept_appends_new_account(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    doc = account_doc(
        kind="roth", owner="spouse", label="Roth", last4="4321", balance=5_000
    )
    client.post(f"/api/statements/{sid}/accept", json=doc)
    accounts = client.get("/api/profile").json()["accounts"]
    assert len(accounts) == 5
    assert accounts[-1]["id"] == "roth-spouse-4321"
    assert accounts[-1]["owner"] == "spouse"


def test_accept_new_account_without_last4_uses_count(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    client.post(f"/api/statements/{sid}/accept", json=account_doc(last4=None))
    assert client.get("/api/profile").json()["accounts"][-1]["id"] == "pretax-self-5"


def test_accept_account_without_profile_409(client: TestClient) -> None:
    sid = new_statement(client)
    res = client.post(f"/api/statements/{sid}/accept", json=account_doc())
    assert res.status_code == 409
    assert res.json()["detail"] == "Complete your profile first"


def test_accept_ss_statement_sets_spouse_estimates(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    assert (
        client.post(f"/api/statements/{sid}/accept", json=ss_doc("spouse")).status_code
        == 200
    )
    profile = client.get("/api/profile").json()
    assert profile["spouse"]["ss_at_62"] == 1_450
    assert profile["spouse"]["ss_at_fra"] == 2_100
    assert profile["spouse"]["ss_at_70"] == 2_650
    assert profile["self"]["ss_at_62"] == 2_200


def test_accept_ss_statement_without_person_422(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    res = client.post(f"/api/statements/{sid}/accept", json=ss_doc(None))
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "person"]


def test_accept_ss_spouse_without_spouse_422(client: TestClient) -> None:
    put_profile(client, build_sample_household().model_copy(update={"spouse": None}))
    sid = new_statement(client)
    res = client.post(f"/api/statements/{sid}/accept", json=ss_doc("spouse"))
    assert res.status_code == 422
    assert client.get("/api/statements").json()[0]["status"] == "uploaded"


def test_extract_runs_agent_in_background(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(statements_api, "run_extract", calls.append)
    sid = new_statement(client)
    res = client.post(f"/api/statements/{sid}/extract")
    assert res.status_code == 202
    assert calls == [sid]
    assert client.get("/api/statements").json()[0]["status"] == "reading"


def fake_extraction(monkeypatch: pytest.MonkeyPatch, extract: object) -> None:
    module = types.ModuleType("agent.extraction")
    module.extract = extract  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent.extraction", module)


def test_run_extract_logs_failure_and_resets_status(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def boom(_id: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fake_extraction(monkeypatch, boom)
    sid = new_statement(client)
    client.post(f"/api/statements/{sid}/extract")
    assert "statement extraction failed" in caplog.text
    assert client.get("/api/statements").json()[0]["status"] == "uploaded"


def test_run_extract_none_resets_reading_but_keeps_no_text(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fake_extraction(monkeypatch, lambda _id: None)
    sid = new_statement(client)
    client.post(f"/api/statements/{sid}/extract")
    assert client.get("/api/statements").json()[0]["status"] == "uploaded"
    blank = upload(client, ("blank.pdf", make_pdf(None))).json()[0]["id"]
    client.get(f"/api/statements/{blank}/text")
    statements_api.run_extract(blank)
    assert client.get("/api/statements").json()[1]["status"] == "no_text"


def test_run_extract_calls_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fake_extraction(monkeypatch, lambda i: calls.append(i) or object())
    statements_api.run_extract(7)
    assert calls == [7]


def test_scan_reports_pdf_name_without_magic_bytes(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "statements"
    folder.mkdir()
    (folder / "fake.pdf").write_bytes(b"nope")
    (folder / "readme.txt").write_text("x")
    results = client.post("/api/statements/scan").json()
    assert results == [
        {"filename": "fake.pdf", "id": None, "error": "Only PDF files are accepted"}
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Ending balance 125000.00",
        "Value 1234567.89",
        "Shares 123456.789",
        "Total 250,000.00",
        "Market Value 125,000.00 1234567.89",
        "2026 100000.00 200000.00",
    ],
)
def test_mask_keeps_balances_without_separators(text: str) -> None:
    assert pdf.mask(text, []) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("SSN 123–45–6789", "SSN ****6789"),
        ("SSN 123—45—6789", "SSN ****6789"),
        ("Acct 1234 5678 9012", "Acct ****9012"),
        ("Acct 1234  5678  9012", "Acct ****9012"),
        ("Acct 1234·5678·9012", "Acct ****9012"),
        ("Acct 123456789", "Acct ****6789"),
        ("Acct 1234 5678 9012 3456", "Acct ****3456"),
        ("Routing 021000021", "Routing ****0021"),
    ],
)
def test_mask_catches_separator_variants(text: str, expected: str) -> None:
    assert pdf.mask(text, []) == expected


def test_mask_terms_span_whitespace_and_respect_word_edges() -> None:
    out = pdf.mask("Alex\n  Smith and Alexander", ["Alex Smith", "Alex"])
    assert out == "[MASKED] and Alexander"


def test_mask_through_real_pdf_pipeline(tmp_path: Path) -> None:
    path = tmp_path / "s.pdf"
    path.write_bytes(make_pdf("SSN 123–45–6789\nAcct 1234 5678 9012\nAlex\nSmith"))
    out = pdf.mask(pdf.extract_text(path), ["Alex Smith"])
    assert "6789" in out
    assert "123" not in out
    assert "5678" not in out
    assert "Smith" not in out


def test_accept_twice_is_409_and_does_not_duplicate(client: TestClient) -> None:
    put_profile(client)
    sid = new_statement(client)
    doc = account_doc(last4=None)
    assert client.post(f"/api/statements/{sid}/accept", json=doc).status_code == 200
    res = client.post(f"/api/statements/{sid}/accept", json=doc)
    assert res.status_code == 409
    assert res.json()["detail"] == "Already accepted"
    assert len(client.get("/api/profile").json()["accounts"]) == 5


def test_accept_matches_last4_less_account_by_label(client: TestClient) -> None:
    put_profile(client)
    first = new_statement(client, "a.pdf")
    second = new_statement(client, "b.pdf")
    client.post(f"/api/statements/{first}/accept", json=account_doc(last4=None))
    doc = account_doc(last4=None, balance=1_000)
    client.post(f"/api/statements/{second}/accept", json=doc)
    accounts = client.get("/api/profile").json()["accounts"]
    assert len(accounts) == 5
    assert accounts[-1]["balance"] == 1_000


def test_new_account_id_is_never_reused(client: TestClient) -> None:
    put_profile(client)
    first = new_statement(client, "a.pdf")
    second = new_statement(client, "b.pdf")
    client.post(f"/api/statements/{first}/accept", json=account_doc(last4=None))
    other = account_doc(last4=None, label="Other 401(k)")
    client.post(f"/api/statements/{second}/accept", json=other)
    ids = [a["id"] for a in client.get("/api/profile").json()["accounts"]]
    assert len(ids) == len(set(ids)) == 6


def test_text_of_corrupt_or_missing_pdf_is_422(
    client: TestClient, tmp_path: Path
) -> None:
    first = new_statement(client, "a.pdf")
    second = new_statement(client, "b.pdf")
    (tmp_path / "statements" / "a.pdf").write_bytes(b"%PDF-1.4 garbage")
    (tmp_path / "statements" / "b.pdf").unlink()
    for sid in (first, second):
        res = client.get(f"/api/statements/{sid}/text")
        assert res.status_code == 422
        assert res.json()["detail"] == "Could not read this PDF"


@pytest.mark.parametrize("name", [".pdf", "..pdf", ".hidden.pdf"])
def test_upload_rejects_empty_or_hidden_stem(client: TestClient, name: str) -> None:
    assert upload(client, (name, make_pdf())).json()[0]["id"] is None


def test_extraction_rejects_full_account_number_and_negative_amounts(
    client: TestClient,
) -> None:
    sid = new_statement(client)
    url = f"/api/statements/{sid}/extraction"
    assert client.put(url, json=account_doc(last4="123456789")).status_code == 422
    assert client.put(url, json=account_doc(cost_basis=-1)).status_code == 422
    bad_ss = ss_doc("self") | {"monthly_at_70": -1}
    assert client.put(url, json=bad_ss).status_code == 422
