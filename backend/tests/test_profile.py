from datetime import date

from fastapi.testclient import TestClient

from backend.profile.models import Household
from backend.tests.conftest import build_sample_household


def body(household: Household) -> dict:
    return household.model_dump(mode="json", by_alias=True)


def test_put_then_get_roundtrip(
    client: TestClient, sample_household: Household
) -> None:
    sent = body(sample_household)
    assert "self" in sent
    put = client.put("/api/profile", json=sent)
    assert put.status_code == 200
    got = client.get("/api/profile")
    assert got.status_code == 200
    assert got.json() == sent
    assert Household.model_validate(got.json()) == sample_household


def test_get_without_profile_404(client: TestClient) -> None:
    assert client.get("/api/profile").status_code == 404


def test_negative_balance_422(client: TestClient, sample_household: Household) -> None:
    sent = body(sample_household)
    sent["accounts"][0]["balance"] = -1
    assert client.put("/api/profile", json=sent).status_code == 422


def test_plan_to_age_not_above_current_age_422(
    client: TestClient, sample_household: Household
) -> None:
    today = date.today()
    sent = body(sample_household)
    sent["self"]["birth_date"] = date(today.year - 60, 1, 1).isoformat()
    sent["self"]["plan_to_age"] = 60
    assert client.put("/api/profile", json=sent).status_code == 422
    sent["self"]["plan_to_age"] = 61
    assert client.put("/api/profile", json=sent).status_code == 200


def test_filing_status_follows_spouse() -> None:
    household = build_sample_household()
    assert household.filing_status == "mfj"
    assert household.model_copy(update={"spouse": None}).filing_status == "single"
