"""Algorithm C: complete-assignment Min-Conflicts with seeded tie-breaking and plateau escape."""
from __future__ import annotations
import random
from time import perf_counter
from .common import AlgorithmResult, build_variables
from core.models import Placement, ProblemData, Schedule
from core.scoring import score_schedule
from core.validator import validate_timetable


def solve_min_conflicts(problem: ProblemData, *, max_iterations: int = 2_000, seed: int = 0,
                        random_walk_probability: float = 0.08, restart_after: int = 100,
                        max_restarts: int = 3) -> AlgorithmResult:
    """Use complete assignments; random restarts escape plateaus. Never claims proof of infeasibility."""
    if max_iterations < 0: raise ValueError("max_iterations must be nonnegative")
    if not 0 <= random_walk_probability <= 1: raise ValueError("random_walk_probability must be in [0, 1]")
    if restart_after < 1 or max_restarts < 0: raise ValueError("restart_after must be >=1 and max_restarts >=0")
    started = perf_counter(); rng = random.Random(seed); variables = build_variables(problem, allow_fallback=True)
    if not variables:
        issues = validate_timetable(problem, Schedule([]))
        if not issues:
            return AlgorithmResult("min_conflicts", "feasible", Schedule([]), runtime_seconds=perf_counter()-started,
                                   termination_reason="Empty requirement set independently validated.")
    domains = {v.session_id: list(v.domain) for v in variables}
    if any(not d for d in domains.values()):
        return AlgorithmResult("min_conflicts", "inconclusive", None, runtime_seconds=perf_counter()-started,
                               termination_reason="No representable placement exists for at least one required session.")

    def random_assignment():
        return {v.session_id: rng.choice(domains[v.session_id]) for v in variables}
    def ordered(assign): return [assign[v.session_id] for v in variables]
    def measure(assign):
        placements = ordered(assign); report = score_schedule(problem, placements)
        return report["hard_violations"], report["soft_penalty_score"], report["cost"]
    current = random_assignment(); best_feasible = None; best_candidate = None; best_key = None
    history: list[int] = []; stale = 0; restarts = 0; iterations = 0
    for _ in range(max_iterations + 1):
        placements = ordered(current); report = score_schedule(problem, placements)
        key = (report["hard_violations"], report["soft_penalty_score"])
        history.append(report["cost"])
        # Independent final validation is authoritative, not the incremental objective alone.
        issues = validate_timetable(problem, Schedule(placements))
        if not issues:
            if best_feasible is None or key < best_key:
                best_feasible = Schedule(placements); best_key = key
            return AlgorithmResult("min_conflicts", "feasible", best_feasible, iterations=iterations,
                                   runtime_seconds=perf_counter()-started, termination_reason="Complete assignment independently validated.",
                                   cost_history=history, best_candidate=Schedule(placements))
        if best_candidate is None or key < measure({p.session_id:p for p in best_candidate.placements})[:2]:
            best_candidate = Schedule(placements)
        if iterations >= max_iterations: break
        implicated = {v.session_id for v in issues if v.session_id}
        conflicted = [v for v in variables if v.session_id in implicated]
        if not conflicted: conflicted = list(variables)
        # Strategy: choose the variable with most validator violations; seeded random tie-break.
        counts = {v.session_id: sum(1 for issue in issues if issue.session_id == v.session_id) for v in conflicted}
        max_count = max(counts.values(), default=0)
        tied = [v for v in conflicted if counts[v.session_id] == max_count]
        var = rng.choice(tied)
        old_key = measure(current)[:2]
        candidates = domains[var.session_id]
        if rng.random() < random_walk_probability:
            selected = rng.choice(candidates)
        else:
            scored = []
            for candidate in candidates:
                trial = dict(current); trial[var.session_id] = candidate
                scored.append((measure(trial)[:2], candidate))
            best_score = min(x[0] for x in scored)
            tied_values = [p for score, p in scored if score == best_score]
            selected = rng.choice(tied_values)  # reproducible because RNG is locally seeded
        current[var.session_id] = selected; iterations += 1
        if measure(current)[:2] < old_key: stale = 0
        else: stale += 1
        if stale >= restart_after and restarts < max_restarts:
            current = random_assignment(); restarts += 1; stale = 0
    return AlgorithmResult("min_conflicts", "iteration_limit", best_feasible, iterations=iterations,
                           runtime_seconds=perf_counter()-started,
                           termination_reason="Iteration limit reached; Min-Conflicts cannot prove infeasibility.",
                           cost_history=history, best_candidate=best_candidate)
