from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.profile.models import Household, OneTime, PlanToAgeError

Kind = Literal["money", "age", "rate"]


class FieldInfo(BaseModel):
    label: str
    kind: Kind


class SetField(BaseModel):
    op: Literal["set"]
    path: str
    value: float | int | None


class AddOneTime(BaseModel):
    op: Literal["add_one_time"]
    item: OneTime


class RemoveOneTime(BaseModel):
    op: Literal["remove_one_time"]
    index: int


ProfileChange = Annotated[
    SetField | AddOneTime | RemoveOneTime, Field(discriminator="op")
]

_PERSON_FIELDS: dict[str, tuple[str, Kind]] = {
    "retirement_age": ("Retirement age", "age"),
    "plan_to_age": ("Plan to age", "age"),
    "ss_claim_age": ("Social Security claim age", "age"),
    "wages": ("Wages", "money"),
    "contribution_401k": ("401(k) contribution", "money"),
    "pension_annual": ("Pension per year", "money"),
    "pension_start_age": ("Pension start age", "age"),
}

FIELDS: dict[str, FieldInfo] = {
    **{
        f"{role}.{key}": FieldInfo(label=f"{label} ({who})", kind=kind)
        for role, who in (("self", "you"), ("spouse", "spouse"))
        for key, (label, kind) in _PERSON_FIELDS.items()
    },
    "spending.essential": FieldInfo(label="Essential spending per year", kind="money"),
    "spending.discretionary": FieldInfo(
        label="Discretionary spending per year", kind="money"
    ),
    "spending.cobra_monthly": FieldInfo(label="COBRA per month", kind="money"),
    "spending.bridge_monthly": FieldInfo(
        label="Bridge insurance per month", kind="money"
    ),
    "assumptions.return_rate": FieldInfo(label="Return rate", kind="rate"),
    "assumptions.inflation": FieldInfo(label="Inflation", kind="rate"),
    "assumptions.ss_cola": FieldInfo(label="Social Security COLA", kind="rate"),
    "assumptions.volatility": FieldInfo(label="Volatility", kind="rate"),
    "assumptions.heir_tax_rate": FieldInfo(label="Heir tax rate", kind="rate"),
}


class ChangeError(ValueError):
    pass


class ChangeLine(BaseModel):
    label: str
    kind: Kind
    old: float | None
    new: float | None


def _check_path(h: Household, path: str) -> FieldInfo:
    info = FIELDS.get(path)
    if info is None:
        raise ChangeError(f"{path} cannot be changed")
    if path.startswith("spouse.") and h.spouse is None:
        raise ChangeError("There is no spouse in the profile")
    return info


def _one_time_label(item: OneTime) -> str:
    return f"One-time expense {item.year}: {item.label}"


def apply_changes(h: Household, changes: list[ProfileChange]) -> Household:
    data: dict[str, Any] = h.model_dump(mode="json", by_alias=True)
    one_time: list[dict[str, Any]] = data["spending"]["one_time"]
    for change in changes:
        if isinstance(change, SetField):
            _check_path(h, change.path)
            section, key = change.path.split(".")
            data[section][key] = change.value
        elif isinstance(change, AddOneTime):
            one_time.append(change.item.model_dump(mode="json"))
        elif 0 <= change.index < len(one_time):
            del one_time[change.index]
        else:
            raise ChangeError(f"There is no one-time expense number {change.index}")
    try:
        updated = Household.model_validate(data)
        updated.check_plan_to_age()
    except ValidationError as e:
        first = e.errors()[0]
        field = ".".join(str(p) for p in first["loc"])
        raise ChangeError(f"{field}: {first['msg']}") from e
    except PlanToAgeError as e:
        raise ChangeError(f"{e.role}.plan_to_age: {e}") from e
    return updated


def _current(h: Household, path: str) -> float | None:
    section, key = path.split(".")
    owner = h.self_ if section == "self" else getattr(h, section)
    value: float | None = getattr(owner, key)
    return value


def describe(h: Household, changes: list[ProfileChange]) -> list[ChangeLine]:
    lines: list[ChangeLine] = []
    for change in changes:
        lines.append(_line(h, change))
        h = apply_changes(h, [change])
    return lines


def _line(h: Household, change: ProfileChange) -> ChangeLine:
    if isinstance(change, SetField):
        info = _check_path(h, change.path)
        return ChangeLine(
            label=info.label,
            kind=info.kind,
            old=_current(h, change.path),
            new=change.value,
        )
    if isinstance(change, AddOneTime):
        return ChangeLine(
            label=_one_time_label(change.item),
            kind="money",
            old=None,
            new=change.item.amount,
        )
    items = h.spending.one_time
    if not 0 <= change.index < len(items):
        raise ChangeError(f"There is no one-time expense number {change.index}")
    item = items[change.index]
    return ChangeLine(
        label=_one_time_label(item), kind="money", old=item.amount, new=None
    )
