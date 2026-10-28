"""UI-independent services for uploads, schedule views, edits, validation, and exports."""
from __future__ import annotations
import csv, io, json, zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from core.data_loader import DataValidationError, problem_from_dict
from core.models import ProblemData, Placement, Schedule
from core.validator import validate_timetable
from core.scoring import score_schedule


def problem_to_raw(problem: ProblemData) -> dict[str, Any]:
    slot=lambda s:{'day':s.day,'period':s.period}
    return {'schema_version':'1.0','subjects':[{'code':s.code,'name':s.name,'kind':s.kind,'session_length':s.session_length} for s in problem.subjects],
      'teachers':[{'name':t.name,'qualified_subjects':sorted(t.qualified_subjects),'unavailable_slots':[slot(x) for x in sorted(t.unavailable_slots)],'preferred_slots':[slot(x) for x in sorted(t.preferred_slots)],'max_weekly_load':t.max_weekly_load} for t in problem.teachers],
      'classes':[{'name':c.name,'strength':c.strength,'subject_periods':c.subject_periods,'lunch_period':c.lunch_period} for c in problem.classes],
      'rooms':[{'name':r.name,'capacity':r.capacity,'kind':r.kind} for r in problem.rooms],
      'time':{'working_days':list(problem.time.working_days),'periods_per_day':problem.time.periods_per_day,'break_slots':[slot(x) for x in sorted(problem.time.break_slots)]},'soft_weights':problem.soft_weights}


def _csv_records(zf, filename):
    try: text=zf.read(filename).decode('utf-8-sig')
    except KeyError: return []
    return list(csv.DictReader(io.StringIO(text)))

def load_csv_bundle(data: bytes) -> ProblemData:
    """Read a ZIP of normalized CSV tables: subjects.csv, teachers.csv, classes.csv, rooms.csv, time.csv.
    Nested/list fields are JSON encoded in cells. teachers may include availability/preference fields.
    time.csv is one row: working_days (JSON list), periods_per_day, break_slots (JSON list).
    """
    try: zf=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e: raise DataValidationError(['CSV input must be a ZIP bundle containing normalized CSV tables.']) from e
    required=['subjects.csv','teachers.csv','classes.csv','rooms.csv','time.csv']
    missing=[x for x in required if x not in zf.namelist()]
    if missing: raise DataValidationError(['CSV bundle missing: '+', '.join(missing)])
    def val(x, default=None):
        if x is None or x=='': return default
        try: return json.loads(x)
        except (json.JSONDecodeError,TypeError): return x
    subjects=[]
    for x in _csv_records(zf,'subjects.csv'): subjects.append({'code':x['code'],'name':x['name'],'kind':x['kind'],'session_length':int(x.get('session_length') or 1)})
    teachers=[]
    for x in _csv_records(zf,'teachers.csv'):
        teachers.append({'name':x['name'],'qualified_subjects':val(x.get('qualified_subjects'),'[]'),'unavailable_slots':val(x.get('unavailable_slots'),'[]'),'preferred_slots':val(x.get('preferred_slots'),'[]'),'max_weekly_load':int(x.get('max_weekly_load') or 30)})
    classes=[]
    for x in _csv_records(zf,'classes.csv'): classes.append({'name':x['name'],'strength':int(x['strength']),'subject_periods':val(x['subject_periods'],'{}'),'lunch_period':int(x['lunch_period'])})
    rooms=[{'name':x['name'],'capacity':int(x['capacity']),'kind':x['kind']} for x in _csv_records(zf,'rooms.csv')]
    tr=_csv_records(zf,'time.csv')
    if len(tr)!=1: raise DataValidationError(['time.csv must contain exactly one data row.'])
    time={'working_days':val(tr[0]['working_days'],'[]'),'periods_per_day':int(tr[0]['periods_per_day']),'break_slots':val(tr[0].get('break_slots'),'[]')}
    raw={'schema_version':'1.0','subjects':subjects,'teachers':teachers,'classes':classes,'rooms':rooms,'time':time}
    return problem_from_dict(raw)


def load_uploaded_problem(filename: str, data: bytes) -> ProblemData:
    suffix=Path(filename).suffix.lower()
    if suffix=='.json':
        try: raw=json.loads(data.decode('utf-8-sig'))
        except (UnicodeDecodeError,json.JSONDecodeError) as e: raise DataValidationError([f'Invalid JSON upload: {e}']) from e
        # Ignore dataset-only witness metadata; problem_from_dict ignores unknown top-level fields.
        return problem_from_dict(raw)
    if suffix=='.zip': return load_csv_bundle(data)
    if suffix=='.csv': raise DataValidationError(['A single CSV cannot represent the full problem safely. Upload a ZIP containing subjects.csv, teachers.csv, classes.csv, rooms.csv, and time.csv.'])
    raise DataValidationError(['Supported inputs: .json or .zip of CSV tables.'])


def schedule_rows(problem: ProblemData, schedule: Schedule) -> list[dict]:
    subjects={s.code:s for s in problem.subjects}; out=[]
    for p in sorted(schedule.placements,key=lambda x:(problem.time.working_days.index(x.day),x.start_period,x.class_name,x.session_id)):
        out.append({'session_id':p.session_id,'class':p.class_name,'subject_code':p.subject_code,'subject':subjects[p.subject_code].name if p.subject_code in subjects else p.subject_code,
            'teacher':p.teacher_name,'room':p.room_name,'day':p.day,'start_period':p.start_period+1,'end_period':p.start_period+p.duration,
            'duration_periods':p.duration,'lab':bool(subjects.get(p.subject_code) and subjects[p.subject_code].kind=='lab'),
            'occupied_periods':','.join(str(x+1) for x in range(p.start_period,p.start_period+p.duration))})
    return out


def timetable_view(problem: ProblemData, schedule: Schedule, dimension: str) -> dict[str, list[list[str]]]:
    if dimension not in {'class','teacher','room'}: raise ValueError('dimension must be class, teacher, or room')
    key={'class':'class_name','teacher':'teacher_name','room':'room_name'}[dimension]
    entities={'class':[x.name for x in problem.classes],'teacher':[x.name for x in problem.teachers],'room':[x.name for x in problem.rooms]}[dimension]
    result={}
    for entity in entities:
        grid=[[('LUNCH' if dimension=='class' and period==next(c.lunch_period for c in problem.classes if c.name==entity) else 'BREAK' if any(s.day==day and s.period==period for s in problem.time.break_slots) else 'FREE') for period in range(problem.time.periods_per_day)] for day in problem.time.working_days]
        for p in schedule.placements:
            if getattr(p,key)!=entity: continue
            label=f'{p.subject_code}\n{p.teacher_name}\n{p.room_name}'
            for period in range(p.start_period,p.start_period+p.duration):
                if p.day in problem.time.working_days and 0<=period<problem.time.periods_per_day:
                    grid[problem.time.working_days.index(p.day)][period]=label+(f' (lab {period-p.start_period+1}/{p.duration})' if p.duration>1 else '')
        result[entity]=grid
    return result


def move_placement(problem: ProblemData, schedule: Schedule, session_id: str, *, day: str, start_period: int, room_name: str|None=None) -> tuple[Schedule,list, list]:
    """Move exactly one session; returns (candidate, all issues, newly introduced issue signatures)."""
    before=validate_timetable(problem,schedule)
    found=[p for p in schedule.placements if p.session_id==session_id]
    if len(found)!=1: raise ValueError(f'Expected exactly one session with id {session_id!r}.')
    old=found[0]
    moved=Placement(old.session_id,old.class_name,old.subject_code,old.teacher_name,room_name or old.room_name,day,int(start_period),old.duration)
    candidate=Schedule([moved if p.session_id==session_id else p for p in schedule.placements])
    after=validate_timetable(problem,candidate)
    sig=lambda v:(v.code,v.message,v.session_id,v.count)
    prior={sig(v) for v in before}; new=[v for v in after if sig(v) not in prior]
    return candidate,after,new


def export_csv(problem: ProblemData, schedule: Schedule) -> bytes:
    rows=schedule_rows(problem,schedule); stream=io.StringIO(newline='')
    fields=list(rows[0].keys()) if rows else ['session_id','class','subject_code','subject','teacher','room','day','start_period','end_period','duration_periods','lab','occupied_periods']
    report=score_schedule(problem,schedule.placements)
    fields += ['validation_status','hard_violations','soft_penalty_score','cost']
    for row in rows:
        row.update({'validation_status':'FEASIBLE' if report['hard_violations']==0 else 'CONFLICTING',
                    'hard_violations':report['hard_violations'],'soft_penalty_score':report['soft_penalty_score'],'cost':report['cost']})
    w=csv.DictWriter(stream,fieldnames=fields); w.writeheader(); w.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def export_excel(problem: ProblemData, schedule: Schedule) -> bytes:
    try: import pandas as pd
    except ImportError as e: raise RuntimeError('Excel export requires pandas and openpyxl.') from e
    rows=schedule_rows(problem,schedule); stream=io.BytesIO()
    with pd.ExcelWriter(stream,engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer,index=False,sheet_name='Timetable')
        report=score_schedule(problem,schedule.placements)
        pd.DataFrame([{'hard_violations':report['hard_violations'],'soft_penalty_score':report['soft_penalty_score'],'cost':report['cost']}]).to_excel(writer,index=False,sheet_name='Validation')
    return stream.getvalue()


def read_export_csv(data: bytes) -> list[dict]: return list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
def read_export_excel(data: bytes) -> list[dict]:
    import pandas as pd
    return pd.read_excel(io.BytesIO(data),sheet_name='Timetable').fillna('').to_dict('records')


def undo_last(history: list[Schedule]) -> Schedule:
    """Pop the most recent immutable-by-convention schedule snapshot for UI undo."""
    if not history: raise ValueError('There is no edit to undo.')
    return history.pop()
