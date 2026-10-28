# Phase 2 search algorithms

## Public API

```python
from algorithms import solve_backtracking, solve_improved_backtracking, solve_min_conflicts

plain = solve_backtracking(problem, time_limit_seconds=10.0, node_limit=100_000)
improved = solve_improved_backtracking(problem, time_limit_seconds=10.0, node_limit=100_000)
local = solve_min_conflicts(problem, max_iterations=2_000, seed=0,
                            random_walk_probability=0.08, restart_after=100, max_restarts=3)
```

All return `AlgorithmResult` from `algorithms.common`. `status` is `feasible`, `proven_infeasible`, `inconclusive`, or `iteration_limit`. A `schedule` is present only when the independent final validator accepts it. `best_candidate` in Min-Conflicts is diagnostic and may be conflicting; it is never returned as `schedule` unless independently valid.

## Shared representation

`build_variables()` expands each class/subject weekly requirement into atomic sessions. Theory has duration 1; a lab is a single variable whose placement occupies `session_length` consecutive periods. Every placement has a stable session ID. Domains filter unary constraints (qualification, room type/capacity, lunch/break, teacher availability, time bounds, and individual load). Pairwise/resource conflicts and cumulative teacher load are checked against the Phase 1 incremental constraint engine. Every completed candidate is then checked independently by `core.validator.validate_timetable`.

## Algorithm A — plain backtracking

Fixed class/subject/session order and fixed domain order. It uses recursive assignment and ordinary consistency checks against assigned placements. It does **not** select variables with MRV or Degree, and does not prune future domains. `nodes_expanded`, `backtracks`, elapsed time, and termination reason are recorded. Exhausting all valid branches proves infeasibility; a node/time cutoff without a solution is `inconclusive`.

## Algorithm B — improved CSP backtracking

MRV selects the remaining variable with the smallest current domain. Ties use the Degree heuristic: the variable connected to the largest number of still-unassigned variables wins; stable session ID is the final tie-break. After each assignment, Forward Checking removes values from each unassigned variable that conflict with the current partial assignment. A trail records each removed value and restores it when that branch is abandoned. `domain_deletions` counts every value removed, including values later restored.

These heuristics do not change the solution set: MRV and Degree only reorder variables; Forward Checking removes only values inconsistent with the already assigned partial solution. Thus a solution is not discarded if it can extend that partial solution. If all branches are exhausted, infeasibility is proven.

## Algorithm C — Min-Conflicts

Starts with exactly one placement for every required session, so no session is silently dropped. It selects a session named in validator violations with the largest number of associated violations; seeded random choice breaks ties. With probability `random_walk_probability`, it takes a seeded random domain value; otherwise it chooses the value minimizing `(hard violation count, soft penalty score)`, with seeded random tie-breaking. After `restart_after` non-improving moves, it can make up to `max_restarts` random complete restarts. `cost_history` records the Phase 1 weighted cost at each inspected assignment. It is incomplete and cannot prove infeasibility; an exhausted iteration budget is `iteration_limit`.

## Correctness notes and limits

- `feasible` always means the independent final validator returned zero violations.
- A timeout or node cap is never labeled `proven_infeasible`.
- Empty unary-valid domains prove infeasibility for CSP search because every placement for that required session violates at least one unary hard constraint.
- The CSP solvers are complete relative to their generated unary-valid domains, provided they finish without limits.
- Min-Conflicts is a stochastic local-search method: it may fail to find an existing solution within its iteration/restart budget.
- The baseline remains intentionally simple; do not add heuristics to `backtracking.py`.
