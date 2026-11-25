import pytest

from backend.plan.changes import (
    AddOneTime,
    ChangeError,
    ChangeLine,
    ProfileChange,
    RemoveOneTime,
    SetField,
    apply_changes,
    describe,
)
from backend.profile.models import Household, OneTime
from backend.tests.conftest import build_sample_household


def _set(path: str, value: float | None) -> SetField:
    return SetField(op="set", path=path, value=value)


def test_set_retirement_age_returns_new_household(sample_household: Household) -> None:
    changed = apply_changes(sample_household, [_set("self.retirement_age", 65)])
    assert changed.self_.retirement_age == 65
    assert sample_household.self_.retirement_age == 63


def test_unknown_path_rejected(sample_household: Household) -> None:
    with pytest.raises(ChangeError):
        apply_changes(sample_household, [_set("self.first_name", 1)])


def test_spouse_path_without_spouse_rejected(sample_household: Household) -> None:
    sample_household.spouse = None
    with pytest.raises(ChangeError, match="spouse"):
        apply_changes(sample_household, [_set("spouse.wages", 1)])


def test_claim_age_out_of_range_rejected(sample_household: Household) -> None:
    with pytest.raises(ChangeError, match="ss_claim_age"):
        apply_changes(sample_household, [_set("self.ss_claim_age", 75)])


def test_plan_to_age_below_current_age_rejected(sample_household: Household) -> None:
    with pytest.raises(ChangeError, match="plan_to_age"):
        apply_changes(sample_household, [_set("self.plan_to_age", 40)])


def test_add_and_remove_one_time(sample_household: Household) -> None:
    item = OneTime(year=2030, amount=25_000, label="Roof")
    added = apply_changes(sample_household, [AddOneTime(op="add_one_time", item=item)])
    assert added.spending.one_time == [item]
    removed = apply_changes(added, [RemoveOneTime(op="remove_one_time", index=0)])
    assert removed.spending.one_time == []
    with pytest.raises(ChangeError):
        apply_changes(removed, [RemoveOneTime(op="remove_one_time", index=0)])


def test_describe_lines() -> None:
    h = build_sample_household()
    item = OneTime(year=2030, amount=25_000, label="Roof")
    with_item = apply_changes(h, [AddOneTime(op="add_one_time", item=item)])
    changes: list[ProfileChange] = [
        _set("spending.essential", 70_000),
        AddOneTime(op="add_one_time", item=item),
    ]
    assert describe(h, changes) == [
        ChangeLine(
            label="Essential spending per year", kind="money", old=60_000, new=70_000
        ),
        ChangeLine(
            label="One-time expense 2030: Roof", kind="money", old=None, new=25_000
        ),
    ]
    assert describe(with_item, [RemoveOneTime(op="remove_one_time", index=0)]) == [
        ChangeLine(
            label="One-time expense 2030: Roof", kind="money", old=25_000, new=None
        )
    ]
    with pytest.raises(ChangeError):
        describe(h, [RemoveOneTime(op="remove_one_time", index=3)])
