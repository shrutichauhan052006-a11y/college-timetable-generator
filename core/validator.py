"""Independent final validation; does not call the incremental constraint engine."""
from collections import Counter
from .models import ProblemData, Schedule, Slot, Violation

def validate_timetable(problem: ProblemData, schedule: Schedule) -> list[Violation]:
    out=[]; subs={s.code:s for s in problem.subjects}; teachers={t.name:t for t in problem.teachers}
    classes={c.name:c for c in problem.classes}; rooms={r.name:r for r in problem.rooms}; days=set(problem.time.working_days)
    occupied=set(); ids=set(); actual=Counter(); loads=Counter()
    for p in schedule.placements:
        if p.session_id in ids: out.append(Violation('DUPLICATE_SESSION_ID',f'Repeated session ID {p.session_id}.',session_id=p.session_id))
        ids.add(p.session_id)
        sub,cls,t,r=subs.get(p.subject_code),classes.get(p.class_name),teachers.get(p.teacher_name),rooms.get(p.room_name)
        if not all((sub,cls,t,r)):
            out.append(Violation('UNKNOWN_REFERENCE',f'{p.session_id}: unknown entity reference.',session_id=p.session_id)); continue
        if p.day not in days or p.start_period<0 or p.duration<1 or p.start_period+p.duration>problem.time.periods_per_day:
            out.append(Violation('OUT_OF_RANGE',f'{p.session_id}: invalid day/period range.',session_id=p.session_id)); continue
        if p.duration!=sub.session_length: out.append(Violation('LAB_DURATION',f'{p.session_id}: incorrect duration for {sub.code}.',session_id=p.session_id))
        if sub.code not in t.qualified_subjects: out.append(Violation('QUALIFICATION',f'{p.session_id}: teacher lacks qualification.',session_id=p.session_id))
        if r.kind!=('lab' if sub.kind=='lab' else 'classroom'): out.append(Violation('ROOM_TYPE',f'{p.session_id}: wrong room kind.',session_id=p.session_id))
        if r.capacity<cls.strength: out.append(Violation('ROOM_CAPACITY',f'{p.session_id}: room too small.',session_id=p.session_id))
        for period in range(p.start_period,p.start_period+p.duration):
            slot=Slot(p.day,period)
            if slot in problem.time.break_slots: out.append(Violation('BREAK',f'{p.session_id}: overlaps break.',session_id=p.session_id))
            if period==cls.lunch_period: out.append(Violation('LUNCH',f'{p.session_id}: overlaps class lunch.',session_id=p.session_id))
            if slot in t.unavailable_slots: out.append(Violation('UNAVAILABLE',f'{p.session_id}: teacher unavailable.',session_id=p.session_id))
            for typ,name,code in [('teacher',t.name,'H1_TEACHER_COLLISION'),('class',cls.name,'H2_CLASS_COLLISION'),('room',r.name,'H3_ROOM_COLLISION')]:
                key=(typ,name,slot)
                if key in occupied: out.append(Violation(code,f'{p.session_id}: {typ} collision at {slot}.',session_id=p.session_id))
                occupied.add(key)
            actual[(cls.name,sub.code)]+=1; loads[t.name]+=1
    for cls in problem.classes:
        for code,required in cls.subject_periods.items():
            got=actual[(cls.name,code)]
            if got!=required: out.append(Violation('WEEKLY_HOURS',f'{cls.name}/{code}: scheduled {got} periods, required {required}.'))
            if code not in subs: out.append(Violation('UNKNOWN_SUBJECT',f'{cls.name} requires unknown subject {code}.'))
    for t in problem.teachers:
        if loads[t.name]>t.max_weekly_load: out.append(Violation('WORKLOAD',f'{t.name}: load {loads[t.name]} exceeds {t.max_weekly_load}.'))
    return out

def is_feasible(problem: ProblemData, schedule: Schedule) -> bool:
    return not validate_timetable(problem,schedule)
