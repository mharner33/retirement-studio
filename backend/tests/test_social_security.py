from datetime import date

import pytest

from backend.engine.social_security import (
    full_retirement_age,
    monthly_benefit,
    spousal_topup,
)
from backend.profile.models import Person
from backend.rules import store
from backend.rules.models import TaxRules


@pytest.fixture(scope="module")
def rules() -> TaxRules:
    return store.parse_rules((store.SEED_DIR / store.SEED_FILENAME).read_text())


def person(born: int, at_62: float, at_fra: float, at_70: float) -> Person:
    return Person(
        first_name="P",
        birth_date=date(born, 6, 1),
        retirement_age=62,
        ss_at_62=at_62,
        ss_at_fra=at_fra,
        ss_at_70=at_70,
    )


def test_full_retirement_age_by_birth_year() -> None:
    assert full_retirement_age(1950) == 66
    assert full_retirement_age(1955) == pytest.approx(66 + 2 / 12)
    assert full_retirement_age(1959) == pytest.approx(66 + 10 / 12)
    assert full_retirement_age(1963) == 67


def test_monthly_benefit_interpolates() -> None:
    p = person(1963, 2_200, 3_100, 3_900)
    # 65 is 3/5 of the way from 62 to 67: 2,200 + 0.6 * 900 = 2,740
    assert monthly_benefit(p, 65) == pytest.approx(2_740)
    assert monthly_benefit(p, 62) == pytest.approx(2_200)
    assert monthly_benefit(p, 67) == pytest.approx(3_100)
    # 69 is 2/3 of the way from 67 to 70: 3,100 + 2/3 * 800
    assert monthly_benefit(p, 69) == pytest.approx(3_100 + 800 * 2 / 3)
    assert monthly_benefit(p, 70) == pytest.approx(3_900)


def test_spousal_topup_when_low_own_benefit(rules: TaxRules) -> None:
    low = person(1965, 500, 700, 900)
    high = person(1963, 2_200, 3_100, 3_900)
    # 0.5 * 3,100 - 700 = 850 at FRA
    assert spousal_topup(low, high, 67, rules) == pytest.approx(850)
    # 24 months early: 24 * 25/36 % = 16.67% off
    assert spousal_topup(low, high, 65, rules) == pytest.approx(
        850 * (1 - 24 / 36 / 100 * 25)
    )
    # 60 months early: 36 * 25/36 % + 24 * 5/12 % = 35% off
    assert spousal_topup(low, high, 62, rules) == pytest.approx(850 * 0.65)
    # no delayed credits on the spousal part
    assert spousal_topup(low, high, 70, rules) == pytest.approx(850)


def test_spousal_topup_zero_when_own_high(rules: TaxRules) -> None:
    a = person(1963, 2_200, 3_100, 3_900)
    b = person(1965, 1_400, 2_000, 2_500)
    assert spousal_topup(b, a, 67, rules) == 0
    assert spousal_topup(a, b, 67, rules) == 0
