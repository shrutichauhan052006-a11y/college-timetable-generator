from collections import defaultdict
from .models import ProblemData, Placement, Slot
from .constraints import check_placements
from .validator import validate_timetable
from .data_loader import validate_problem
from .models import Schedule, Violation

def soft_penalties(problem: ProblemData, placements: list[Placement]) -> dict[str,int]:
    """Raw penalty units. S4-S5 are provisional interpretations documented in README."""
    class_day=defaultdict(set); theory_days=defaultdict(set); theory_count=defaultdict(int)
    s3=s4=s5=0; teachers={t.name:t for t in problem.teachers}; subs={s.code:s for s in problem.subjects}
    for p in placements:
        for slot in p.occupied_slots(): class_day[(p.class_name,p.day)].add(slot.period)
        sub=subs.get(p.subject_code)
        if sub and sub.kind=='theory':
            k=(p.class_name,p.subject_code); theory_days[k].add(p.day); theory_count[k]+=1
        t=teachers.get(p.teacher_name)
        if t and t.preferred_slots: s4+=sum(slot not in t.preferred_slots for slot in p.occupied_slots())
        if p.start_period==problem.time.periods_per_day-1: s5+=1
        if sub and sub.kind=='lab' and p.duration!=sub.session_length: s3+=1
    class_by_name={c.name:c for c in problem.classes}
    s1=0
    for (class_name, day), periods in class_day.items():
        if not periods: continue
        lunch=class_by_name[class_name].lunch_period
        for period in range(min(periods), max(periods)+1):
            if period not in periods and period != lunch and Slot(day, period) not in problem.time.break_slots:
                s1 += 1
    s2=sum(max(0,n-len(theory_days[k])) for k,n in theory_count.items())
    return {'S1':s1,'S2':s2,'S3':s3,'S4':s4,'S5':s5}

def score_schedule(problem: ProblemData, placements: list[Placement]) -> dict:
    # Final-validator findings are canonical for scoring so H7 incompleteness is included.
    # Also surface invalid problem data; callers should normally load via load_problem first.
    input_issues=[Violation('INPUT', e) for e in validate_problem(problem)]
    final_issues=validate_timetable(problem, Schedule(list(placements)))
    violations=input_issues + final_issues
    penalties=soft_penalties(problem,placements)
    hard_count=sum(v.count for v in violations)
    soft=sum(problem.soft_weights[k]*v for k,v in penalties.items())
    return {'hard_violations':hard_count,'violations':[v.to_dict() for v in violations],
            'soft_penalties':penalties,'soft_penalty_score':soft,'cost':1000*hard_count+soft}
