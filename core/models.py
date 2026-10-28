from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, order=True)
class Slot:
    day: str
    period: int  # zero-based

@dataclass(frozen=True)
class Subject:
    code: str
    name: str
    kind: str  # theory | lab
    session_length: int = 1
    def __post_init__(self):
        if self.kind not in {'theory', 'lab'}: raise ValueError('kind must be theory or lab')
        if self.session_length < 1: raise ValueError('session_length must be positive')
        if self.kind == 'theory' and self.session_length != 1: raise ValueError('theory length must be 1')

@dataclass(frozen=True)
class Teacher:
    name: str
    qualified_subjects: frozenset[str]
    unavailable_slots: frozenset[Slot] = frozenset()
    max_weekly_load: int = 30
    preferred_slots: frozenset[Slot] = frozenset()

@dataclass(frozen=True)
class ClassGroup:
    name: str
    strength: int
    subject_periods: dict[str, int]
    lunch_period: int

@dataclass(frozen=True)
class Room:
    name: str
    capacity: int
    kind: str  # classroom | lab

@dataclass(frozen=True)
class TimeStructure:
    working_days: tuple[str, ...]
    periods_per_day: int
    break_slots: frozenset[Slot] = frozenset()

@dataclass(frozen=True)
class ProblemData:
    subjects: tuple[Subject, ...]
    teachers: tuple[Teacher, ...]
    classes: tuple[ClassGroup, ...]
    rooms: tuple[Room, ...]
    time: TimeStructure
    soft_weights: dict[str, int] = field(default_factory=lambda: {'S1':2,'S2':3,'S3':10,'S4':1,'S5':1})

@dataclass(frozen=True)
class Placement:
    session_id: str
    class_name: str
    subject_code: str
    teacher_name: str
    room_name: str
    day: str
    start_period: int
    duration: int
    def occupied_slots(self) -> tuple[Slot, ...]:
        return tuple(Slot(self.day, p) for p in range(self.start_period, self.start_period + self.duration))

@dataclass
class Schedule:
    placements: list[Placement] = field(default_factory=list)

@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    hard: bool = True
    session_id: str | None = None
    count: int = 1
    def to_dict(self):
        return {'code':self.code,'message':self.message,'hard':self.hard,'session_id':self.session_id,'count':self.count}
