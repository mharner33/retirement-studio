from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.profile.models import (
    Account,
    Assumptions,
    Household,
    Person,
    Spending,
)
from backend.rules import store
from backend.rules.models import TaxRules


def build_sample_household() -> Household:
    as_of = date(2026, 11, 1)
    me = Person(
        first_name="Alex",
        birth_date=date(1963, 6, 15),
        retirement_age=63,
        wages=120_000,
        contribution_401k=20_000,
        ss_at_62=2_200,
        ss_at_fra=3_100,
        ss_at_70=3_900,
    )
    return Household.model_validate(
        {
            "self": me,
            "spouse": Person(
                first_name="Sam",
                birth_date=date(1965, 3, 1),
                retirement_age=62,
                ss_at_62=1_400,
                ss_at_fra=2_000,
                ss_at_70=2_500,
            ),
            "accounts": [
                Account(
                    id="a1",
                    kind="pretax",
                    owner="self",
                    label="401(k)",
                    balance=900_000,
                    last4="1234",
                    as_of=as_of,
                ),
                Account(
                    id="a2",
                    kind="roth",
                    owner="self",
                    label="Roth IRA",
                    balance=60_000,
                    last4="5678",
                    as_of=as_of,
                ),
                Account(
                    id="a3",
                    kind="taxable",
                    owner="self",
                    label="Brokerage",
                    balance=250_000,
                    cost_basis=150_000,
                    last4="9012",
                    as_of=as_of,
                ),
                Account(
                    id="a4",
                    kind="cash",
                    owner="self",
                    label="Savings",
                    balance=40_000,
                    as_of=as_of,
                ),
            ],
            "spending": Spending(
                essential=60_000, discretionary=15_000, cobra_monthly=1_800
            ),
            "assumptions": Assumptions(),
        }
    )


@pytest.fixture
def sample_household() -> Household:
    return build_sample_household()


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


@pytest.fixture(scope="session")
def rules() -> TaxRules:
    return store.parse_rules((store.SEED_DIR / store.SEED_FILENAME).read_text())
