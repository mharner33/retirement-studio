import sqlite3
from collections import OrderedDict
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from backend.engine.projection import Projection, Strategy, project
from backend.engine.search import RankedStrategy, rank
from backend.engine.spending import safe_extra
from backend.engine.whatif import success_rates
from backend.plan.changes import ChangeError, ProfileChange, apply_changes, describe
from backend.plan.models import PlanOption, PlanResult, WhatIfResult
from backend.profile.api import Conn, load_household
from backend.profile.models import Household
from backend.rules import store
from backend.rules.models import TaxRules

router = APIRouter(prefix="/api/plan")

TOP = 5


def _options(
    h: Household, rules: TaxRules, start_year: int, chosen: list[RankedStrategy]
) -> list[PlanOption]:
    """Success rate at base spending, all strategies on the same seeded paths
    in one process pool."""
    strategies = [r.strategy for r in chosen]
    rates = success_rates(h, strategies, rules, start_year)
    return [
        PlanOption(
            strategy=r.strategy,
            label=r.strategy.label(),
            lifetime_tax=r.projection.lifetime_tax,
            after_tax_end=r.projection.after_tax_end,
            shortfall_year=r.projection.shortfall_year,
            success_rate=rate,
            safe_extra=safe_extra(h, r.strategy, rules, start_year),
        )
        for r, rate in zip(chosen, rates, strict=True)
    ]


_CACHE_SIZE = 8
_cache: OrderedDict[tuple[str, str, int, bool], PlanResult] = OrderedDict()


def plan_for(
    h: Household, rules: TaxRules, rules_file: str, start_year: int, stale: bool
) -> PlanResult:
    key = (h.model_dump_json(by_alias=True), rules_file, start_year, stale)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    ranked = rank(h, rules, start_year)
    top = ranked[:TOP]
    baseline = next(r for r in ranked if r.strategy.conversion_target == "none")
    chosen = top if baseline in top else [*top, baseline]
    options = _options(h, rules, start_year, chosen)
    result = PlanResult(
        rules_file=rules_file,
        rules_stale=stale,
        top=options[:TOP],
        baseline=options[chosen.index(baseline)],
        best_rows=ranked[0].projection.rows,
    )
    _cache[key] = result
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return result


def _context(
    conn: sqlite3.Connection, request: Request
) -> tuple[Household, TaxRules, str, bool]:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    data_dir = request.app.state.data_dir
    rules, filename = store.current_rules(conn, data_dir)
    stale = store.status(conn, data_dir, date.today()).stale
    return household, rules, filename, stale


@router.get("")
def plan(conn: Conn, request: Request) -> PlanResult:
    household, rules, filename, stale = _context(conn, request)
    return plan_for(household, rules, filename, date.today().year, stale)


@router.post("/whatif")
def whatif(changes: list[ProfileChange], conn: Conn, request: Request) -> WhatIfResult:
    household, rules, filename, stale = _context(conn, request)
    try:
        changed = apply_changes(household, changes)
        lines = describe(household, changes)
    except ChangeError as e:
        raise HTTPException(422, str(e)) from e
    year = date.today().year
    return WhatIfResult(
        current=plan_for(household, rules, filename, year, stale),
        whatif=plan_for(changed, rules, filename, year, stale),
        changes=lines,
    )


@router.post("/project")
def project_plan(strategy: Strategy, conn: Conn, request: Request) -> Projection:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    rules, _ = store.current_rules(conn, request.app.state.data_dir)
    return project(household, strategy, rules, date.today().year)
