"""What-if success rate over seeded random yearly returns.

Paths run in a forkserver process pool (the API calls this from a thread).
Forkserver re-imports `__main__` in its workers, so any script entry point
that calls into here needs an `if __name__ == "__main__":` guard.
"""

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from multiprocessing import get_context
from statistics import NormalDist

from backend.engine.projection import Strategy, plan_years, project
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
    years = plan_years(h, start_year)
    dist = NormalDist(h.assumptions.return_rate, h.assumptions.volatility)
    draws = dist.samples(paths * years, seed=seed)
    return [draws[i : i + years] for i in range(0, len(draws), years)]


def _lasts(
    h: Household, rules: TaxRules, start_year: int, s: Strategy, returns: list[float]
) -> bool:
    return project(h, s, rules, start_year, returns).shortfall_year is None


def success_rates(
    h: Household,
    strategies: Sequence[Strategy],
    rules: TaxRules,
    start_year: int,
    paths: list[list[float]] | None = None,
) -> list[float]:
    """Each strategy's share of return paths (default: 1,000 with seed 7)
    with no shortfall, all run through one process pool."""
    if paths is None:
        paths = return_paths(h, start_year)
    run = partial(_lasts, h, rules, start_year)
    jobs = [s for s in strategies for _ in paths]
    returns = [r for _ in strategies for r in paths]
    workers = len(os.sched_getaffinity(0))
    with ProcessPoolExecutor(workers, mp_context=CONTEXT) as pool:
        lasted = list(pool.map(run, jobs, returns, chunksize=CHUNK))
    n = len(paths)
    return [sum(lasted[i * n : (i + 1) * n]) / n for i in range(len(strategies))]


def success_rate(
    h: Household,
    s: Strategy,
    rules: TaxRules,
    start_year: int,
    paths: list[list[float]] | None = None,
) -> float:
    return success_rates(h, [s], rules, start_year, paths)[0]
