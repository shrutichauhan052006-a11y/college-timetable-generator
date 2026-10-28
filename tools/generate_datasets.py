"""Deterministic synthetic-data/witness builder; not a production search algorithm."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DAYS=['Mon','Tue','Wed','Thu','Fri']

def build(large):
    nc,nt,np=(8,15,7) if large else (3,6,6)
    subjects=[{'code':'MTH','name':'Mathematics','kind':'theory','session_length':1},
      {'code':'PRG','name':'Programming','kind':'theory','session_length':1},
      {'code':'DBS','name':'Database Systems','kind':'theory','session_length':1},
      {'code':'PHY','name':'Physics Lab','kind':'lab','session_length':2},
      {'code':'CSE','name':'Computer Lab','kind':'lab','session_length':2}]
    codes=[s['code'] for s in subjects]
    teachers=[]
    for i in range(nt):
        quals={codes[i%5]}
        if i+5<nt: quals.add(codes[(i+2)%5])
        teachers.append({'name':f'Teacher {i+1:02d}','qualified_subjects':sorted(quals),
          'unavailable_slots':[{'day':DAYS[(i+1)%5],'period':np-1}],
          'preferred_slots':[{'day':DAYS[i%5],'period':0}], 'max_weekly_load':24 if large else 25})
    classes=[{'name':f'Class {i+1:02d}','strength':28+(i%4)*4,
      'subject_periods':{c:2 for c in codes},'lunch_period':3} for i in range(nc)]
    rooms=[{'name':f'Room {i+1:02d}','capacity':60,'kind':'classroom'} for i in range((8 if large else 4)-2)]
    rooms += [{'name':'Lab Room 01','capacity':40,'kind':'lab'},{'name':'Lab Room 02','capacity':40,'kind':'lab'}]
    room_by_kind={'theory':[r for r in rooms if r['kind']=='classroom'],'lab':[r for r in rooms if r['kind']=='lab']}
    load={t['name']:0 for t in teachers}; used=set(); witness=[]; sid=0
    # Lab placements first; each lab is a single atomic 2-period placement.
    req=[]
    for ci in range(nc):
        for code in ('PHY','CSE'): req.append((ci,code,2))
    for ci in range(nc):
        for code in ('MTH','PRG','DBS'):
            req.extend([(ci,code,1),(ci,code,1)])
    # Deterministic greedy fixture placement; independent validator proves the witness.
    req.sort(key=lambda x:(0 if x[2]==2 else 1,x[0],x[1]))
    for ci,code,dur in req:
        cls=classes[ci]; sub=next(s for s in subjects if s['code']==code); kind=sub['kind']; placed=False
        for day in DAYS:
            for start in range(np-dur+1):
                slots=[(day,p) for p in range(start,start+dur)]
                if any(p==cls['lunch_period'] for _,p in slots): continue
                if any(('class',cls['name'],d,p) in used for d,p in slots): continue
                for t in [x for x in teachers if code in x['qualified_subjects']]:
                    if load[t['name']]+dur>t['max_weekly_load']: continue
                    if any(any(s['day']==d and s['period']==p for s in t['unavailable_slots']) for d,p in slots): continue
                    if any(('teacher',t['name'],d,p) in used for d,p in slots): continue
                    for r in room_by_kind['theory' if kind=='theory' else 'lab']:
                        if r['capacity']<cls['strength'] or any(('room',r['name'],d,p) in used for d,p in slots): continue
                        sid+=1; witness.append({'session_id':f'S{sid:04d}','class_name':cls['name'],'subject_code':code,
                          'teacher_name':t['name'],'room_name':r['name'],'day':day,'start_period':start,'duration':dur})
                        for d,p in slots:
                            used.add(('class',cls['name'],d,p)); used.add(('teacher',t['name'],d,p)); used.add(('room',r['name'],d,p))
                        load[t['name']]+=dur; placed=True; break
                    if placed: break
                if placed: break
            if placed: break
        if not placed: raise RuntimeError(f'Could not place witness: {cls["name"]}/{code}/{dur}')
    return {'schema_version':'1.0','description':'Synthetic example dataset with a deterministic reference timetable witness.',
      'subjects':subjects,'teachers':teachers,'classes':classes,'rooms':rooms,
      'time':{'working_days':DAYS,'periods_per_day':np,'break_slots':[]},
      'soft_weights':{'S1':2,'S2':3,'S3':10,'S4':1,'S5':1},'verification_witness':witness}

def main():
    for large,name in [(False,'small_dataset.json'),(True,'large_dataset.json')]:
        data=build(large); (ROOT/'data'/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
        print(f'Wrote {name}: classes={len(data["classes"])} teachers={len(data["teachers"])} rooms={len(data["rooms"])} placements={len(data["verification_witness"])}')
if __name__=='__main__': main()
