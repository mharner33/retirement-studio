from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

from backend.engine.projection import Projection, Strategy, project
from backend.engine.search import RankedStrategy, rank
from backend.engine.spending import safe_extra
from backend.engine.whatif import success_rates
from backend.plan.models import PlanOption, PlanResult
from backend.profile.api import Conn, load_household
from backend.profile.models import Household
from backend.rules.models import TaxRules
from backend.rules.store import current_rules

router = APIRouter(prefix="/api/plan")

TOP = 5
STALE_AFTER = timedelta(days=90)


def rules_stale(filename: str, today: date) -> bool:
    """`filename` is `retirement_rules_YYYY-MM-DD.md`."""
    dated = date.fromisoformat(filename.removesuffix(".md").rsplit("_", 1)[1])
    return today - dated > STALE_AFTER


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


@router.get("")
def plan(conn: Conn, request: Request) -> PlanResult:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    rules, filename = current_rules(conn, request.app.state.data_dir)
    today = date.today()
    ranked = rank(household, rules, today.year)
    top = ranked[:TOP]
    baseline = next(r for r in ranked if r.strategy.conversion_target == "none")
    chosen = top if baseline in top else [*top, baseline]
    options = _options(household, rules, today.year, chosen)
    return PlanResult(
        rules_file=filename,
        rules_stale=rules_stale(filename, today),
        top=options[:TOP],
        baseline=options[chosen.index(baseline)],
        best_rows=ranked[0].projection.rows,
    )


@router.post("/project")
def project_plan(strategy: Strategy, conn: Conn, request: Request) -> Projection:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    rules, _ = current_rules(conn, request.app.state.data_dir)
    return project(household, strategy, rules, date.today().year)
