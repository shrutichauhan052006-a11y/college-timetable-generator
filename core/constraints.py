from __future__ import annotations
from collections import Counter
from .models import ProblemData, Placement, Slot, Violation
from .data_loader import validate_problem

def check_placements(problem: ProblemData, placements: list[Placement]) -> list[Violation]:
    """Incremental H1-H6/H8-H9 checks. H7 completeness is schedule-level."""
    issues=[Violation('INPUT',e) for e in validate_problem(problem)]
    if issues: return issues
    subjects={s.code:s for s in problem.subjects}; teachers={t.name:t for t in problem.teachers}
    classes={c.name:c for c in problem.classes}; rooms={r.name:r for r in problem.rooms}
    occupied={}; loads=Counter(); ids=set()
    for p in placements:
        if p.session_id in ids: issues.append(Violation('DUPLICATE_SESSION_ID',f'Duplicate session ID {p.session_id}.',session_id=p.session_id))
        ids.add(p.session_id)
        sub,cls,t,r=subjects.get(p.subject_code),classes.get(p.class_name),teachers.get(p.teacher_name),rooms.get(p.room_name)
        if not all((sub,cls,t,r)):
            issues.append(Violation('UNKNOWN_REFERENCE',f'{p.session_id}: unknown subject/class/teacher/room.',session_id=p.session_id)); continue
        if p.duration!=sub.session_length: issues.append(Violation('LAB_DURATION',f'{p.session_id}: duration {p.duration}; expected {sub.session_length}.',session_id=p.session_id))
        if p.day not in problem.time.working_days or p.start_period<0 or p.duration<1 or p.start_period+p.duration>problem.time.periods_per_day:
            issues.append(Violation('OUT_OF_RANGE',f'{p.session_id}: outside valid day/period bounds.',session_id=p.session_id)); continue
        if sub.code not in t.qualified_subjects: issues.append(Violation('QUALIFICATION',f'{p.session_id}: {t.name} not qualified for {sub.code}.',session_id=p.session_id))
        want='lab' if sub.kind=='lab' else 'classroom'
        if r.kind!=want: issues.append(Violation('ROOM_TYPE',f'{p.session_id}: {sub.kind} requires room kind {want}.',session_id=p.session_id))
        if r.capacity<cls.strength: issues.append(Violation('ROOM_CAPACITY',f'{p.session_id}: room capacity {r.capacity} below class strength {cls.strength}.',session_id=p.session_id))
        for slot in p.occupied_slots():
            if slot in problem.time.break_slots: issues.append(Violation('BREAK',f'{p.session_id}: occupies break {slot}.',session_id=p.session_id))
            if slot.period==cls.lunch_period: issues.append(Violation('LUNCH',f'{p.session_id}: occupies lunch for {cls.name} at {slot}.',session_id=p.session_id))
            if slot in t.unavailable_slots: issues.append(Violation('UNAVAILABLE',f'{p.session_id}: teacher {t.name} unavailable at {slot}.',session_id=p.session_id))
            for typ,name,code in [('teacher',t.name,'H1_TEACHER_COLLISION'),('class',cls.name,'H2_CLASS_COLLISION'),('room',r.name,'H3_ROOM_COLLISION')]:
                key=(typ,name,slot)
                if key in occupied: issues.append(Violation(code,f'{p.session_id}: {typ} {name} collides at {slot} with {occupied[key]}.',session_id=p.session_id))
                else: occupied[key]=p.session_id
        loads[t.name]+=p.duration
    for name,n in loads.items():
        if n>teachers[name].max_weekly_load: issues.append(Violation('WORKLOAD',f'Teacher {name} load {n} exceeds maximum {teachers[name].max_weekly_load}.'))
    return issues
