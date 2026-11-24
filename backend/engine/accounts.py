"""Account balances as a projection runs, and the order money is drawn."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from backend.profile.models import Account

Kind = Literal["pretax", "roth", "taxable", "cash", "hsa"]
Owner = Literal["self", "spouse"]
WithdrawalOrder = Literal["taxable_first", "pretax_first", "proportional"]

KINDS: tuple[Kind, ...] = ("cash", "taxable", "pretax", "roth", "hsa")
OWNERS: tuple[Owner, ...] = ("self", "spouse")
ORDERS: dict[WithdrawalOrder, tuple[tuple[Kind, ...], ...]] = {
    "taxable_first": (("cash",), ("taxable",), ("pretax",), ("roth",), ("hsa",)),
    "pretax_first": (("cash",), ("pretax",), ("taxable",), ("roth",), ("hsa",)),
    "proportional": (("cash",), ("taxable", "pretax", "roth"), ("hsa",)),
}
CENT = 0.005


@dataclass
class Holding:
    kind: Kind
    owner: Owner
    balance: float
    basis: float = 0.0


@dataclass(frozen=True)
class Draw:
    """Planned withdrawals by holding index, and what could not be covered."""

    amounts: Mapping[int, float]
    shortfall: float


class Portfolio:
    def __init__(self, accounts: Iterable[Account]) -> None:
        self.holdings = [
            Holding(a.kind, a.owner, a.balance, a.cost_basis) for a in accounts
        ]

    def index(self, kind: Kind, owner: Owner) -> int:
        """First holding of `kind` for `owner`, added empty when there is none."""
        for i, h in enumerate(self.holdings):
            if h.kind == kind and h.owner == owner:
                return i
        self.holdings.append(Holding(kind, owner, 0.0))
        return len(self.holdings) - 1

    def roll_over(self, living: tuple[Owner, ...]) -> None:
        """Accounts of someone who has died pass to the survivor."""
        for h in self.holdings:
            if living and h.owner not in living:
                h.owner = living[0]

    def pretax_balance(self, owner: Owner) -> float:
        return sum(
            h.balance for h in self.holdings if h.kind == "pretax" and h.owner == owner
        )

    def pretax_split(
        self, amount: float, owners: tuple[Owner, ...]
    ) -> dict[int, float]:
        """Take `amount` from pretax holdings, the first owner's before the
        next, pro rata across one owner's holdings."""
        out: dict[int, float] = {}
        for owner in owners:
            idx = [
                i
                for i, h in enumerate(self.holdings)
                if h.kind == "pretax" and h.owner == owner
            ]
            out |= _pro_rata(min(amount, self.pretax_balance(owner)), idx, self._bal())
            amount -= sum(out[i] for i in idx if i in out)
        return out

    def plan(
        self, need: float, order: WithdrawalOrder, reserved: Mapping[int, float]
    ) -> Draw:
        """Withdrawals covering `need`, group by group in `order`, pro rata by
        balance within a group, from balances less `reserved`."""
        avail = [b - reserved.get(i, 0.0) for i, b in enumerate(self._bal())]
        amounts: dict[int, float] = {}
        remaining = max(0.0, need)
        for group in ORDERS[order]:
            idx = [i for i, h in enumerate(self.holdings) if h.kind in group]
            take = min(remaining, sum(avail[i] for i in idx))
            amounts |= _pro_rata(take, idx, avail)
            remaining -= take
        return Draw(amounts, remaining if remaining > CENT else 0.0)

    def gains(self, amounts: Mapping[int, float]) -> float:
        """Long-term gain realized by taxable withdrawals, pro rata to basis."""
        return sum(
            amt * self._gain_share(self.holdings[i])
            for i, amt in amounts.items()
            if self.holdings[i].kind == "taxable"
        )

    def by_owner(self, amounts: Mapping[int, float], kind: Kind) -> dict[Owner, float]:
        out: dict[Owner, float] = dict.fromkeys(OWNERS, 0.0)
        for i, amt in amounts.items():
            h = self.holdings[i]
            if h.kind == kind:
                out[h.owner] += amt
        return out

    def by_kind(self, amounts: Mapping[int, float] | None = None) -> dict[str, float]:
        out: dict[str, float] = dict.fromkeys(KINDS, 0.0)
        for i, h in enumerate(self.holdings):
            out[h.kind] += h.balance if amounts is None else amounts.get(i, 0.0)
        return out

    def withdraw(self, amounts: Mapping[int, float]) -> None:
        for i, amt in amounts.items():
            h = self.holdings[i]
            if h.balance > 0:
                h.basis *= max(0.0, 1 - amt / h.balance)
            h.balance = max(0.0, h.balance - amt)

    def convert(self, amounts: Mapping[int, float]) -> None:
        """Move pretax money into the same owner's Roth."""
        moved = self.by_owner(amounts, "pretax")
        self.withdraw(amounts)
        for owner, amt in moved.items():
            if amt > 0:
                self.holdings[self.index("roth", owner)].balance += amt

    def deposit(self, kind: Kind, owner: Owner, amount: float) -> None:
        self.holdings[self.index(kind, owner)].balance += amount

    def grow(self, rate: float, cash_rate: float) -> None:
        for h in self.holdings:
            h.balance *= 1 + (cash_rate if h.kind == "cash" else rate)

    def _bal(self) -> list[float]:
        return [h.balance for h in self.holdings]

    @staticmethod
    def _gain_share(h: Holding) -> float:
        return 0.0 if h.balance <= 0 else max(0.0, 1 - h.basis / h.balance)


def _pro_rata(amount: float, idx: list[int], balances: list[float]) -> dict[int, float]:
    total = sum(balances[i] for i in idx)
    if amount <= 0 or total <= 0:
        return {}
    return {i: amount * balances[i] / total for i in idx if balances[i] > 0}
