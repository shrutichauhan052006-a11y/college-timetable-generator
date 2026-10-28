"""Shared session expansion, domains, and result contracts for Phase 2."""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import product
from time import perf_counter
from typing import Callable

from core.constraints import check_placements
from core.data_loader import validate_problem
from core.models import Placement, ProblemData, Schedule, Slot, Violation
from core.validator import validate_timetable

@dataclass(frozen=True)
class SessionVariable:
    session_id: str
    class_name: str
    subject_code: str
    duration: int
    domain: tuple[Placement, ...]

@dataclass
class AlgorithmResult:
    algorithm: str
    status: str  # feasible | proven_infeasible | inconclusive | iteration_limit
    schedule: Schedule | None
    nodes_expanded: int = 0
    backtracks: int = 0
    domain_deletions: int = 0
    iterations: int = 0
    runtime_seconds: float = 0.0
    termination_reason: str = ""
    cost_history: list[int] = field(default_factory=list)
    best_candidate: Schedule | None = None
    violations: list[Violation] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return self.schedule is not None and self.status == "feasible"


def _unary_valid(problem: ProblemData, p: Placement) -> bool:
    subjects = {s.code: s for s in problem.subjects}
    teachers = {t.name: t for t in problem.teachers}
    classes = {c.name: c for c in problem.classes}
    rooms = {r.name: r for r in problem.rooms}
    sub, teacher, cls, room = subjects[p.subject_code], teachers[p.teacher_name], classes[p.class_name], rooms[p.room_name]
    if sub.code not in teacher.qualified_subjects or teacher.max_weekly_load < p.duration:
        return False
    if room.kind != ("lab" if sub.kind == "lab" else "classroom") or room.capacity < cls.strength:
        return False
    if p.day not in problem.time.working_days or p.start_period < 0 or p.start_period + p.duration > problem.time.periods_per_day:
        return False
    for slot in p.occupied_slots():
        if slot in problem.time.break_slots or slot.period == cls.lunch_period or slot in teacher.unavailable_slots:
            return False
    return True


def build_variables(problem: ProblemData, *, allow_fallback: bool = False) -> list[SessionVariable]:
    """Expand exact weekly teaching periods into atomic sessions and placement domains."""
    errors = validate_problem(problem)
    if errors:
        raise ValueError("Invalid problem data: " + "; ".join(errors))
    teachers = sorted(problem.teachers, key=lambda x: x.name)
    rooms = sorted(problem.rooms, key=lambda x: x.name)
    variables: list[SessionVariable] = []
    for cls in sorted(problem.classes, key=lambda x: x.name):
        for code, periods in sorted(cls.subject_periods.items()):
            sub = next(s for s in problem.subjects if s.code == code)
            count = periods // sub.session_length
            for i in range(count):
                sid = f"{cls.name}::{code}::{i + 1:03d}"
                candidates: list[Placement] = []
                for day in problem.time.working_days:
                    for start in range(problem.time.periods_per_day - sub.session_length + 1):
                        for teacher, room in product(teachers, rooms):
                            p = Placement(sid, cls.name, code, teacher.name, room.name, day, start, sub.session_length)
                            if _unary_valid(problem, p):
                                candidates.append(p)
                if not candidates and allow_fallback:
                    # Preserve the required variable even when unary constraints make it impossible.
                    # Such placements are diagnostic only and can never be returned as feasible.
                    for day in problem.time.working_days:
                        for start in range(problem.time.periods_per_day - sub.session_length + 1):
                            for teacher, room in product(teachers, rooms):
                                candidates.append(Placement(sid, cls.name, code, teacher.name, room.name, day, start, sub.session_length))
                variables.append(SessionVariable(sid, cls.name, code, sub.session_length, tuple(candidates)))
    return variables


def schedule_is_feasible(problem: ProblemData, placements: list[Placement]) -> tuple[bool, list[Violation]]:
    """Use only the independent final validator for a final feasibility decision."""
    issues = validate_timetable(problem, Schedule(list(placements)))
    return not issues, issues


def incremental_ok(problem: ProblemData, placements: list[Placement]) -> bool:
    return not check_placements(problem, placements)


def make_result(algorithm: str, status: str, placements: list[Placement] | None, started: float, **kwargs) -> AlgorithmResult:
    elapsed = perf_counter() - started
    schedule = Schedule(list(placements)) if placements is not None else None
    violations = validate_timetable(kwargs.pop("problem"), schedule) if schedule is not None else []
    if schedule is not None and violations:
        # Fail closed: never expose an invalid candidate as the successful schedule.
        schedule = None
        status = "inconclusive" if status == "feasible" else status
    return AlgorithmResult(algorithm=algorithm, status=status, schedule=schedule, runtime_seconds=elapsed,
                           violations=violations, **kwargs)
