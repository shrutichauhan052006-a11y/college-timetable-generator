"""Algorithm A: plain recursive CSP backtracking; deliberately no variable/value heuristics."""
from __future__ import annotations
from time import perf_counter
from .common import AlgorithmResult, build_variables, incremental_ok, schedule_is_feasible
from core.models import Placement, ProblemData, Schedule


def solve_backtracking(problem: ProblemData, *, time_limit_seconds: float | None = 10.0,
                       node_limit: int | None = 100_000) -> AlgorithmResult:
    """Solve in fixed variable order and domain order. Limits yield inconclusive, never infeasible."""
    started = perf_counter()
    if node_limit is not None and node_limit < 0: raise ValueError("node_limit must be nonnegative or None")
    if time_limit_seconds is not None and time_limit_seconds < 0: raise ValueError("time_limit_seconds must be nonnegative or None")
    variables = build_variables(problem)
    if any(not v.domain for v in variables):
        return AlgorithmResult("backtracking", "proven_infeasible", None, runtime_seconds=perf_counter()-started,
                              termination_reason="At least one required session has an empty unary-valid domain.")
    assigned: list[Placement] = []
    nodes = backtracks = 0
    cutoff: str | None = None
    solution: list[Placement] | None = None

    def visit(index: int) -> bool:
        nonlocal nodes, backtracks, cutoff, solution
        if cutoff: return False
        if time_limit_seconds is not None and perf_counter() - started >= time_limit_seconds:
            cutoff = "time_limit"; return False
        if node_limit is not None and nodes >= node_limit:
            cutoff = "node_limit"; return False
        nodes += 1
        if index == len(variables):
            ok, _ = schedule_is_feasible(problem, assigned)
            if ok: solution = list(assigned); return True
            return False
        var = variables[index]
        for candidate in var.domain:
            if cutoff: return False
            trial = assigned + [candidate]
            if not incremental_ok(problem, trial):
                continue
            assigned.append(candidate)
            if visit(index + 1): return True
            assigned.pop()
        if not cutoff: backtracks += 1
        return False

    visit(0)
    if solution is not None:
        return AlgorithmResult("backtracking", "feasible", Schedule(solution), nodes, backtracks,
                               runtime_seconds=perf_counter()-started, termination_reason="Complete schedule independently validated.")
    status = "inconclusive" if cutoff else "proven_infeasible"
    reason = f"Search stopped at {cutoff}; no feasible schedule found." if cutoff else "Exhausted the complete search tree."
    return AlgorithmResult("backtracking", status, None, nodes, backtracks,
                           runtime_seconds=perf_counter()-started, termination_reason=reason)
