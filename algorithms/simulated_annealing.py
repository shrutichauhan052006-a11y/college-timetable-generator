"""Optional SA: single-session relocation; only independently feasible neighbours are accepted."""
from __future__ import annotations
import math, random
from time import perf_counter
from .common import AlgorithmResult, build_variables
from core.models import Placement, ProblemData, Schedule
from core.scoring import score_schedule
from core.validator import validate_timetable


def solve_simulated_annealing(problem: ProblemData, initial_schedule: Schedule, *,
    max_iterations: int = 2000, initial_temperature: float = 10.0,
    cooling_rate: float = 0.995, minimum_temperature: float = 0.01, seed: int = 0) -> AlgorithmResult:
    """Neighbour: relocate one session (day/start/teacher/room) from its unary-valid domain.
    Geometric cooling T <- T*cooling_rate. Accept improvements, otherwise exp(-delta/T).
    Infeasible neighbours are rejected, so every current/best state remains feasible.
    Stops on iteration cap or minimum temperature. Requires a feasible starting schedule.
    """
    if max_iterations < 0 or initial_temperature <= 0 or not 0 < cooling_rate < 1 or minimum_temperature <= 0:
        raise ValueError('Invalid simulated-annealing parameters.')
    started=perf_counter(); rng=random.Random(seed)
    initial_issues=validate_timetable(problem, initial_schedule)
    if initial_issues:
        return AlgorithmResult('simulated_annealing','inconclusive',None,runtime_seconds=perf_counter()-started,
            termination_reason='Initial schedule is not independently feasible; SA requires a feasible start.',violations=initial_issues)
    variables=build_variables(problem)
    domains={v.session_id:list(v.domain) for v in variables}
    current=list(initial_schedule.placements); current_by={p.session_id:p for p in current}
    def soft(placements): return score_schedule(problem,placements)['soft_penalty_score']
    current_score=soft(current); best=list(current); best_score=current_score; history=[current_score]
    temperature=initial_temperature; iterations=0
    while iterations < max_iterations and temperature > minimum_temperature and variables:
        var=rng.choice(variables); options=[p for p in domains[var.session_id] if p != current_by[var.session_id]]
        if options:
            candidate=rng.choice(options)
            trial_by=dict(current_by); trial_by[var.session_id]=candidate
            trial=[trial_by[v.session_id] for v in variables]
            if not validate_timetable(problem,Schedule(trial)):
                candidate_score=soft(trial); delta=candidate_score-current_score
                if delta <= 0 or rng.random() < math.exp(-delta/temperature):
                    current_by=trial_by; current=trial; current_score=candidate_score
                    if current_score < best_score: best=list(current); best_score=current_score
        iterations += 1; history.append(current_score); temperature *= cooling_rate
    status='feasible'
    reason='Minimum temperature reached.' if temperature <= minimum_temperature else 'Iteration limit reached.'
    best_schedule=Schedule(best); issues=validate_timetable(problem,best_schedule)
    if issues: return AlgorithmResult('simulated_annealing','inconclusive',None,iterations=iterations,
        runtime_seconds=perf_counter()-started,termination_reason='Final validation failed.',violations=issues,cost_history=history)
    return AlgorithmResult('simulated_annealing',status,best_schedule,iterations=iterations,
        runtime_seconds=perf_counter()-started,termination_reason=reason,cost_history=history)
