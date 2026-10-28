from __future__ import annotations
import json
from pathlib import Path
from .models import ProblemData, Subject, Teacher, ClassGroup, Room, TimeStructure, Slot

class DataValidationError(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__('Invalid timetable input:\n- ' + '\n- '.join(self.errors))

def _slot(x): return Slot(str(x['day']), int(x['period']))

def validate_problem(p: ProblemData) -> list[str]:
    errors=[]
    def unique(items, key, label):
        vals=[key(x) for x in items]
        if len(vals)!=len(set(vals)): errors.append(f'Duplicate {label}.')
    unique(p.subjects,lambda x:x.code,'subject code'); unique(p.teachers,lambda x:x.name,'teacher name')
    unique(p.classes,lambda x:x.name,'class name'); unique(p.rooms,lambda x:x.name,'room name')
    subs={s.code:s for s in p.subjects}; days=set(p.time.working_days)
    if not p.subjects or not p.teachers or not p.classes or not p.rooms: errors.append('subjects, teachers, classes, and rooms must be non-empty.')
    if not days or len(days)!=len(p.time.working_days): errors.append('working_days must be non-empty and unique.')
    if p.time.periods_per_day<1: errors.append('periods_per_day must be positive.')
    def valid_slot(s): return s.day in days and 0<=s.period<p.time.periods_per_day
    for t in p.teachers:
        if t.max_weekly_load<0: errors.append(f'{t.name}: max_weekly_load cannot be negative.')
        for code in t.qualified_subjects:
            if code not in subs: errors.append(f'{t.name}: unknown qualified subject {code}.')
        for s in t.unavailable_slots|t.preferred_slots:
            if not valid_slot(s): errors.append(f'{t.name}: slot {s} outside timetable.')
    for r in p.rooms:
        if r.capacity<1 or r.kind not in {'classroom','lab'}: errors.append(f'{r.name}: invalid capacity or room kind.')
    for c in p.classes:
        if c.strength<1: errors.append(f'{c.name}: strength must be positive.')
        if not 0<=c.lunch_period<p.time.periods_per_day: errors.append(f'{c.name}: lunch period outside timetable.')
        for code,n in c.subject_periods.items():
            if code not in subs: errors.append(f'{c.name}: unknown subject {code}.')
            elif n<0 or n%subs[code].session_length: errors.append(f'{c.name}: periods for {code} must be nonnegative and divisible by session length.')
    for s in p.time.break_slots:
        if not valid_slot(s): errors.append(f'Break slot {s} outside timetable.')
    if set(p.soft_weights)!={'S1','S2','S3','S4','S5'}: errors.append('soft_weights must define exactly S1-S5.')
    elif any(v<0 for v in p.soft_weights.values()): errors.append('soft weights must be nonnegative.')
    return errors

def problem_from_dict(raw: dict) -> ProblemData:
    if not isinstance(raw,dict): raise DataValidationError(['JSON root must be an object.'])
    missing={'schema_version','subjects','teachers','classes','rooms','time'}-set(raw)
    if missing: raise DataValidationError([f'Missing top-level fields: {", ".join(sorted(missing))}'])
    if raw['schema_version']!='1.0': raise DataValidationError(["schema_version must be '1.0'."])
    try:
        p=ProblemData(
          tuple(Subject(str(x['code']),str(x['name']),str(x['kind']),int(x.get('session_length',1))) for x in raw['subjects']),
          tuple(Teacher(str(x['name']),frozenset(x['qualified_subjects']),frozenset(_slot(s) for s in x.get('unavailable_slots',[])),int(x['max_weekly_load']),frozenset(_slot(s) for s in x.get('preferred_slots',[]))) for x in raw['teachers']),
          tuple(ClassGroup(str(x['name']),int(x['strength']),{str(k):int(v) for k,v in x['subject_periods'].items()},int(x['lunch_period'])) for x in raw['classes']),
          tuple(Room(str(x['name']),int(x['capacity']),str(x['kind'])) for x in raw['rooms']),
          TimeStructure(tuple(raw['time']['working_days']),int(raw['time']['periods_per_day']),frozenset(_slot(s) for s in raw['time'].get('break_slots',[]))),
          {str(k):int(v) for k,v in raw.get('soft_weights',{'S1':2,'S2':3,'S3':10,'S4':1,'S5':1}).items()})
    except (KeyError,TypeError,ValueError,AttributeError) as e: raise DataValidationError([f'Malformed field or value: {e}']) from e
    errors=validate_problem(p)
    if errors: raise DataValidationError(errors)
    return p

def load_problem(path: str|Path) -> ProblemData:
    try: raw=json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError as e: raise DataValidationError([f'File not found: {path}']) from e
    except json.JSONDecodeError as e: raise DataValidationError([f'Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}']) from e
    return problem_from_dict(raw)
