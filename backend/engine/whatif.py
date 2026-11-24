"""What-if success rate over seeded random yearly returns."""

from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import get_context
from statistics import NormalDist

from backend.engine.projection import Strategy, project
from backend.profile.models import Household
from backend.rules.models import TaxRules

PATHS = 1000
SEED = 7
CHUNK = 25
CONTEXT = get_context("forkserver")
CONTEXT.set_forkserver_preload(["backend.engine.whatif"])


def return_paths(
    h: Household, start_year: int, paths: int = PATHS, seed: int = SEED
) -> list[list[float]]:
    """`paths` lists of normal(return_rate, volatility) yearly returns, one
    per plan year, drawn from `random.Random(seed)`."""
    last = max(p.birth_date.year + p.plan_to_age for p in (h.self_, h.spouse) if p)
    years = last - start_year + 1
    dist = NormalDist(h.assumptions.return_rate, h.assumptions.volatility)
    draws = dist.samples(paths * years, seed=seed)
    return [draws[i : i + years] for i in range(0, len(draws), years)]


def _lasts(
    h: Household, s: Strategy, rules: TaxRules, start_year: int, returns: list[float]
) -> bool:
    return project(h, s, rules, start_year, returns).shortfall_year is None


def success_rate(
    h: Household,
    s: Strategy,
    rules: TaxRules,
    start_year: int,
    paths: list[list[float]] | None = None,
) -> float:
    """Share of return paths (default: 1,000 with seed 7) with no shortfall.
    Paths run across worker processes (forkserver, since the API calls this
    from a thread)."""
    paths = paths or return_paths(h, start_year)
    run = partial(_lasts, h, s, rules, start_year)
    with ProcessPoolExecutor(mp_context=CONTEXT) as pool:
        lasted = sum(pool.map(run, paths, chunksize=CHUNK))
    return lasted / len(paths)
