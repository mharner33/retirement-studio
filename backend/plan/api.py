from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

from backend.engine.projection import Projection, Strategy, project
from backend.engine.search import RankedStrategy, rank
from backend.engine.spending import safe_extra
from backend.engine.whatif import return_paths, success_rate
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


@dataclass(frozen=True)
class _Context:
    household: Household
    rules: TaxRules
    start_year: int
    paths: list[list[float]]

    def option(self, r: RankedStrategy) -> PlanOption:
        """Success rate at base spending, on the shared seeded paths."""
        h, rules, year = self.household, self.rules, self.start_year
        p = r.projection
        return PlanOption(
            strategy=r.strategy,
            label=r.strategy.label(),
            lifetime_tax=p.lifetime_tax,
            after_tax_end=p.after_tax_end,
            shortfall_year=p.shortfall_year,
            success_rate=success_rate(h, r.strategy, rules, year, self.paths),
            safe_extra=safe_extra(h, r.strategy, rules, year),
        )


@router.get("")
def plan(conn: Conn, request: Request) -> PlanResult:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    rules, filename = current_rules(conn, request.app.state.data_dir)
    today = date.today()
    ranked = rank(household, rules, today.year)
    baseline = next(r for r in ranked if r.strategy.conversion_target == "none")
    ctx = _Context(household, rules, today.year, return_paths(household, today.year))
    return PlanResult(
        rules_file=filename,
        rules_stale=rules_stale(filename, today),
        top=[ctx.option(r) for r in ranked[:TOP]],
        baseline=ctx.option(baseline),
        best_rows=ranked[0].projection.rows,
    )


@router.post("/project")
def project_plan(strategy: Strategy, conn: Conn, request: Request) -> Projection:
    household = load_household(conn)
    if household is None:
        raise HTTPException(409, "No profile saved")
    rules, _ = current_rules(conn, request.app.state.data_dir)
    return project(household, strategy, rules, date.today().year)
