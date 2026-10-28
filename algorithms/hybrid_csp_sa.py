"""Optional hybrid: improved CSP obtains feasibility; SA improves soft score without leaving feasibility."""
from __future__ import annotations
from .common import AlgorithmResult
from .improved_backtracking import solve_improved_backtracking
from .simulated_annealing import solve_simulated_annealing
from core.models import ProblemData


def solve_hybrid_csp_sa(problem: ProblemData, *, time_limit_seconds: float = 10.0,
    node_limit: int = 100_000, sa_iterations: int = 2000, seed: int = 0,
    initial_temperature: float = 10.0, cooling_rate: float = 0.995) -> AlgorithmResult:
    csp=solve_improved_backtracking(problem,time_limit_seconds=time_limit_seconds,node_limit=node_limit)
    if not csp.feasible:
        csp.algorithm='hybrid_csp_sa'
        csp.termination_reason='CSP stage did not find a feasible schedule; SA was not started. '+csp.termination_reason
        return csp
    sa=solve_simulated_annealing(problem,csp.schedule,max_iterations=sa_iterations,
        initial_temperature=initial_temperature,cooling_rate=cooling_rate,seed=seed)
    sa.algorithm='hybrid_csp_sa'; sa.nodes_expanded=csp.nodes_expanded; sa.backtracks=csp.backtracks
    sa.domain_deletions=csp.domain_deletions; sa.runtime_seconds += csp.runtime_seconds
    sa.termination_reason='CSP feasibility stage succeeded; '+sa.termination_reason
    return sa
