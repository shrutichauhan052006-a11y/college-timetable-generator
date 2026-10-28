"""Algorithm B: MRV + Degree tie-break + forward checking with reversible domain pruning."""
from __future__ import annotations
from time import perf_counter
from .common import AlgorithmResult, build_variables, incremental_ok, schedule_is_feasible
from core.models import Placement, ProblemData, Schedule


def _neighbors(variables):
    result = {v.session_id: set() for v in variables}
    for i, a in enumerate(variables):
        a_teachers = {p.teacher_name for p in a.domain}; a_rooms = {p.room_name for p in a.domain}
        for b in variables[i+1:]:
            related = (a.class_name == b.class_name or bool(a_teachers & {p.teacher_name for p in b.domain})
                       or bool(a_rooms & {p.room_name for p in b.domain}))
            if related:
                result[a.session_id].add(b.session_id); result[b.session_id].add(a.session_id)
    return result


def solve_improved_backtracking(problem: ProblemData, *, time_limit_seconds: float | None = 10.0,
                                node_limit: int | None = 100_000) -> AlgorithmResult:
    started = perf_counter()
    if node_limit is not None and node_limit < 0: raise ValueError("node_limit must be nonnegative or None")
    if time_limit_seconds is not None and time_limit_seconds < 0: raise ValueError("time_limit_seconds must be nonnegative or None")
    variables = build_variables(problem)
    if any(not v.domain for v in variables):
        return AlgorithmResult("improved_backtracking", "proven_infeasible", None, runtime_seconds=perf_counter()-started,
                              termination_reason="At least one required session has an empty unary-valid domain.")
    by_id = {v.session_id: v for v in variables}; domains = {v.session_id: list(v.domain) for v in variables}
    degree = _neighbors(variables); assigned: list[Placement] = []; assigned_ids: set[str] = set()
    nodes = backtracks = deletions = 0; cutoff = None; solution = None

    def visit() -> bool:
        nonlocal nodes, backtracks, deletions, cutoff, solution
        if cutoff: return False
        if time_limit_seconds is not None and perf_counter()-started >= time_limit_seconds:
            cutoff = "time_limit"; return False
        if node_limit is not None and nodes >= node_limit:
            cutoff = "node_limit"; return False
        nodes += 1
        if len(assigned_ids) == len(variables):
            ok, _ = schedule_is_feasible(problem, assigned)
            if ok: solution = list(assigned); return True
            return False
        remaining = [v for v in variables if v.session_id not in assigned_ids]
        # MRV first; Degree chooses the variable connected to most remaining variables on ties.
        var = min(remaining, key=lambda v: (len(domains[v.session_id]),
                    -sum(1 for n in degree[v.session_id] if n not in assigned_ids), v.session_id))
        if not domains[var.session_id]:
            backtracks += 1; return False
        for candidate in list(domains[var.session_id]):
            if cutoff: return False
            if not incremental_ok(problem, assigned + [candidate]): continue
            assigned.append(candidate); assigned_ids.add(var.session_id)
            trail: list[tuple[str, Placement]] = []
            failed = False
            for other in variables:
                oid = other.session_id
                if oid in assigned_ids: continue
                old = domains[oid]
                kept = []
                for value in old:
                    if incremental_ok(problem, assigned + [value]):
                        kept.append(value)
                    else:
                        trail.append((oid, value)); deletions += 1
                domains[oid] = kept
                if not kept: failed = True; break
            if not failed and visit(): return True
            # Reversible pruning: restore all values deleted below this decision.
            for oid, value in reversed(trail): domains[oid].append(value)
            assigned_ids.remove(var.session_id); assigned.pop()
            if cutoff: return False
        backtracks += 1
        return False

    visit()
    if solution is not None:
        return AlgorithmResult("improved_backtracking", "feasible", Schedule(solution), nodes, backtracks, deletions,
                               runtime_seconds=perf_counter()-started, termination_reason="Complete schedule independently validated.")
    status = "inconclusive" if cutoff else "proven_infeasible"
    reason = f"Search stopped at {cutoff}; no feasible schedule found." if cutoff else "Exhausted the complete search tree."
    return AlgorithmResult("improved_backtracking", status, None, nodes, backtracks, deletions,
                           runtime_seconds=perf_counter()-started, termination_reason=reason)
