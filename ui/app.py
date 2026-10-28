"""Streamlit front end. Search algorithms remain in the algorithms package."""
from __future__ import annotations
import json
from pathlib import Path
import streamlit as st
from core.data_loader import DataValidationError, problem_from_dict, load_problem
from core.models import Schedule
from core.validator import validate_timetable
from algorithms import solve_backtracking, solve_improved_backtracking, solve_min_conflicts
from ui.services import (problem_to_dict, parse_problem_upload, view_rows, edit_placement,
                         schedule_report, export_csv, export_xlsx, problem_to_csv, ScheduleEditHistory)

ROOT=Path(__file__).resolve().parents[1]
SAMPLES={'Small dataset':'data/small_dataset.json','Large dataset':'data/large_dataset.json'}
st.set_page_config(page_title='College Timetable Generator',page_icon='🗓️',layout='wide')
st.title('AI-Based College Timetable Generator')
st.caption('Constraint-based scheduling with independently validated results')

if 'problem_raw' not in st.session_state:
    st.session_state.problem_raw=problem_to_dict(load_problem(ROOT/'data/small_dataset.json'))
if 'schedule' not in st.session_state: st.session_state.schedule=None
if 'history' not in st.session_state: st.session_state.history=ScheduleEditHistory()
if 'generation' not in st.session_state: st.session_state.generation=None


def set_problem(raw):
    problem=problem_from_dict(raw)
    st.session_state.problem_raw=problem_to_dict(problem)
    st.session_state.schedule=None; st.session_state.history=ScheduleEditHistory(); st.session_state.generation=None

with st.sidebar:
    st.header('Input data')
    selected=st.selectbox('Sample dataset',list(SAMPLES))
    if st.button('Load selected sample',use_container_width=True):
        try: set_problem(problem_to_dict(load_problem(ROOT/SAMPLES[selected]))); st.success('Sample loaded and validated.')
        except Exception as e: st.error(str(e))
    upload=st.file_uploader('Upload problem (.json or supported .csv)',type=['json','csv'])
    if upload and st.button('Validate and load upload',use_container_width=True):
        try: set_problem(problem_to_dict(parse_problem_upload(upload.name,upload.getvalue()))); st.success('Upload validated and loaded.')
        except Exception as e: st.error(str(e))
    st.download_button('Download current problem JSON',json.dumps(st.session_state.problem_raw,indent=2),file_name='timetable_problem.json',mime='application/json',use_container_width=True)
    try:
        _p=problem_from_dict(st.session_state.problem_raw)
        st.download_button('Download current problem CSV',problem_to_csv(_p),file_name='timetable_problem.csv',mime='text/csv',use_container_width=True)
    except Exception: pass

problem_tab,generate_tab,views_tab,edit_tab=st.tabs(['Problem editor','Generate','Timetable views','Edit & export'])
with problem_tab:
    st.subheader('Entity forms')
    st.info('Use the forms to add or update an entity by its unique code/name. Changes are validated before they replace the active problem. The advanced JSON editor supports bulk edits, availability slots, and the complete time structure.')
    raw=st.session_state.problem_raw
    with st.expander('Add or update subject'):
        with st.form('subject_form'):
            code=st.text_input('Subject code'); name=st.text_input('Subject name'); kind=st.selectbox('Type',['theory','lab']); length=st.number_input('Session length (periods)',1,8,1)
            if st.form_submit_button('Save subject'):
                new=dict(code=code.strip(),name=name.strip(),kind=kind,session_length=int(length)); values=[x for x in raw['subjects'] if x['code']!=new['code']]+[new]
                try: set_problem({**raw,'subjects':values}); st.success('Subject saved; problem validated.')
                except Exception as e: st.error(str(e))
    with st.expander('Add or update teacher'):
        with st.form('teacher_form'):
            tname=st.text_input('Teacher name'); quals=st.multiselect('Qualified subjects',[s['code'] for s in raw['subjects']]); maxload=st.number_input('Maximum weekly load',0,100,25); unavail=st.text_input('Unavailable slots (JSON list)',value='[]'); preferred=st.text_input('Preferred slots (JSON list)',value='[]')
            if st.form_submit_button('Save teacher'):
                try:
                    item={'name':tname.strip(),'qualified_subjects':quals,'max_weekly_load':int(maxload),'unavailable_slots':json.loads(unavail),'preferred_slots':json.loads(preferred)}
                    set_problem({**raw,'teachers':[x for x in raw['teachers'] if x['name']!=item['name']]+[item]}); st.success('Teacher saved; problem validated.')
                except Exception as e: st.error(str(e))
    with st.expander('Add or update class'):
        with st.form('class_form'):
            cname=st.text_input('Class name'); strength=st.number_input('Class strength',1,500,30); required=st.text_area('Subject periods as JSON',value='{}'); lunch=st.number_input('Lunch period (zero-based)',0,30,3)
            if st.form_submit_button('Save class'):
                try:
                    item={'name':cname.strip(),'strength':int(strength),'subject_periods':json.loads(required),'lunch_period':int(lunch)}
                    set_problem({**raw,'classes':[x for x in raw['classes'] if x['name']!=item['name']]+[item]}); st.success('Class saved; problem validated.')
                except Exception as e: st.error(str(e))
    with st.expander('Add or update room'):
        with st.form('room_form'):
            rname=st.text_input('Room name'); capacity=st.number_input('Capacity',1,1000,40); rkind=st.selectbox('Room type',['classroom','lab'])
            if st.form_submit_button('Save room'):
                try:
                    item={'name':rname.strip(),'capacity':int(capacity),'kind':rkind}; set_problem({**raw,'rooms':[x for x in raw['rooms'] if x['name']!=item['name']]+[item]}); st.success('Room saved; problem validated.')
                except Exception as e: st.error(str(e))
    with st.expander('Edit availability and time structure (advanced JSON)'):
        st.caption('Edit the time object and teacher unavailable_slots/preferred_slots here. Slot period indices are zero-based.')
        current=json.dumps({'time':raw['time'],'teachers':raw['teachers'],'soft_weights':raw.get('soft_weights',{})},indent=2)
        edited=st.text_area('Time and teacher availability JSON',value=current,height=260,key='availability_json')
        if st.button('Apply availability/time changes'):
            try:
                part=json.loads(edited); set_problem({**raw,'time':part['time'],'teachers':part['teachers'],'soft_weights':part.get('soft_weights',raw.get('soft_weights'))}); st.success('Availability and time structure validated.')
            except Exception as e: st.error(str(e))
    with st.expander('Advanced full problem JSON'):
        full=st.text_area('Full problem JSON',json.dumps(st.session_state.problem_raw,indent=2),height=360,key='full_problem_json')
        if st.button('Validate and apply full JSON'):
            try: set_problem(json.loads(full)); st.success('Full problem validated and applied.')
            except Exception as e: st.error(str(e))
    try:
        p=problem_from_dict(st.session_state.problem_raw)
        st.caption(f"Active input: {len(p.classes)} classes · {len(p.teachers)} teachers · {len(p.rooms)} rooms · {len(p.time.working_days)} days × {p.time.periods_per_day} periods")
    except Exception as e: st.error(str(e))

with generate_tab:
    st.subheader('Search configuration')
    alg=st.selectbox('Algorithm',['Plain Backtracking CSP','Improved Backtracking CSP (MRV + Degree + Forward Checking)','Min-Conflicts'])
    c1,c2,c3=st.columns(3)
    time_limit=c1.number_input('Time limit (seconds)',min_value=0.1,max_value=600.0,value=10.0,step=1.0)
    node_limit=c2.number_input('Node limit (CSP algorithms)',min_value=1,max_value=5_000_000,value=100_000,step=1000)
    seed=c3.number_input('Random seed',min_value=0,max_value=2_147_483_647,value=0,step=1)
    iterations=st.number_input('Min-Conflicts iteration limit',min_value=1,max_value=1_000_000,value=2000,step=100)
    if st.button('Generate timetable',type='primary'):
        try:
            p=problem_from_dict(st.session_state.problem_raw)
            with st.spinner('Searching and independently validating the result...'):
                if alg.startswith('Plain'): result=solve_backtracking(p,time_limit_seconds=float(time_limit),node_limit=int(node_limit))
                elif alg.startswith('Improved'): result=solve_improved_backtracking(p,time_limit_seconds=float(time_limit),node_limit=int(node_limit))
                else: result=solve_min_conflicts(p,max_iterations=int(iterations),seed=int(seed))
            st.session_state.generation=result
            st.session_state.schedule=result.schedule
            st.session_state.history=ScheduleEditHistory()
        except Exception as e: st.error(f'Generation failed: {e}')
    result=st.session_state.generation
    if result:
        report=schedule_report(problem_from_dict(st.session_state.problem_raw),result.schedule) if result.schedule else None
        st.markdown(f"**Termination:** `{result.status}` — {result.termination_reason}")
        a,b,c,d=st.columns(4); a.metric('Runtime',f'{result.runtime_seconds:.3f} s'); b.metric('Nodes / iterations',result.nodes_expanded if result.algorithm!='min_conflicts' else result.iterations); c.metric('Backtracks',result.backtracks); d.metric('Domain deletions',result.domain_deletions)
        if result.schedule:
            st.success('Feasible timetable independently validated.')
            a,b,c=st.columns(3); a.metric('Hard violations',report['hard_violations']); b.metric('Soft penalty',report['soft_penalty_score']); c.metric('Cost',report['cost'])
        else:
            st.error('No feasible timetable was returned. This is not a feasible schedule.')
            if result.status=='inconclusive' or result.status=='iteration_limit': st.warning('Search stopped at a limit; infeasibility is not proven.')
        if result.cost_history: st.line_chart({'cost':result.cost_history})

with views_tab:
    st.subheader('Timetable views')
    if st.session_state.schedule is None: st.info('Generate a feasible timetable first. Unsuccessful candidates are not displayed as valid schedules.')
    else:
        p=problem_from_dict(st.session_state.problem_raw); schedule=st.session_state.schedule; issues=validate_timetable(p,schedule)
        if issues: st.error(f'Conflicting candidate: {len(issues)} hard validation findings. It is not marked feasible.')
        else: st.success('Feasible — current schedule passes the independent validator.')
        dimension=st.radio('View by',['Class','Teacher','Room'],horizontal=True)
        rows=view_rows(p,schedule,dimension.lower())
        entities=sorted({r['entity'] for r in rows})
        selected_entity=st.selectbox(f'{dimension} selection',entities) if entities else None
        days=list(p.time.working_days)
        if selected_entity:
            filtered=[r for r in rows if r['entity']==selected_entity]
            for day in days:
                st.markdown(f'**{day}**')
                dayrows=[r for r in filtered if r['day']==day]
                byperiod={r['period']:r for r in dayrows}
                grid=[]
                for period in range(p.time.periods_per_day):
                    if any(s.day==day and s.period==period for s in p.time.break_slots): label='BREAK'
                    elif dimension=='Class' and period==next((x.lunch_period for x in p.classes if x.name==selected_entity),-1): label='LUNCH'
                    elif period+1 not in byperiod: label='FREE'
                    else:
                        x=byperiod[period+1]; label=f"{x['subject']}\n{x['teacher']}\n{x['room']}"+(f"\nLab {x['lab_duration']} periods" if x['lab_duration'] else '')
                    grid.append({'Period':period+1,'Schedule':label})
                st.dataframe(grid,use_container_width=True,hide_index=True)

with edit_tab:
    st.subheader('Manual move, validation, and undo')
    if st.session_state.schedule is None: st.info('Generate a feasible timetable before editing.')
    else:
        p=problem_from_dict(st.session_state.problem_raw); schedule=st.session_state.schedule
        st.caption('A move changes only the selected session. Labs move as one atomic multi-period placement. Conflicting edits are retained visibly for correction; unrelated sessions are never moved automatically.')
        options={f"{x.session_id} · {x.subject_code} · {x.day} P{x.start_period+1} · {x.room_name}":x.session_id for x in schedule.placements}
        label=st.selectbox('Session to move',list(options))
        selected_session=next(x for x in schedule.placements if x.session_id==options[label])
        subject=next(x for x in p.subjects if x.code==selected_session.subject_code)
        cls=next(x for x in p.classes if x.name==selected_session.class_name)
        compatible_rooms=[r.name for r in p.rooms if r.kind==('lab' if subject.kind=='lab' else 'classroom') and r.capacity>=cls.strength]
        with st.form('move_form'):
            day=st.selectbox('New day',list(p.time.working_days),index=p.time.working_days.index(selected_session.day))
            start=st.number_input('New start period (1-based)',1,p.time.periods_per_day,selected_session.start_period+1)
            room=st.selectbox('Compatible room',compatible_rooms if compatible_rooms else [selected_session.room_name],index=(compatible_rooms.index(selected_session.room_name) if selected_session.room_name in compatible_rooms else 0))
            submit=st.form_submit_button('Apply move and validate')
        if submit:
            sid=options[label]; before=schedule; moved,issues=edit_placement(p,before,sid,day=day,start_period=int(start)-1,room_name=room)
            if issues:
                st.error(f'Edit rejected: it would introduce or retain {len(issues)} hard validation finding(s). The last accepted schedule is unchanged.')
                st.dataframe([v.to_dict() for v in issues],use_container_width=True,hide_index=True)
            else:
                st.session_state.history.accept(before,moved); st.session_state.schedule=moved
                st.success('Edit accepted: full schedule passes the independent validator.')
                st.rerun()
        if st.button('Undo last accepted edit',disabled=not st.session_state.history.can_undo()):
            st.session_state.schedule=st.session_state.history.undo(st.session_state.schedule); st.rerun()
        current=st.session_state.schedule; current_issues=validate_timetable(p,current)
        if current_issues: st.error(f'Current schedule is conflicting ({len(current_issues)} findings). Resolve conflicts before treating it as feasible.')
        else: st.success('Current edited schedule is feasible.')
        st.download_button('Export schedule CSV',export_csv(p,current),file_name='timetable.csv',mime='text/csv',disabled=(not current.placements or bool(current_issues)))
        try: xlsx=export_xlsx(p,current); st.download_button('Export schedule Excel (.xlsx)',xlsx,file_name='timetable.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',disabled=(not current.placements or bool(current_issues)))
        except Exception as e: st.warning(f'Excel export unavailable: {e}. Install requirements.txt dependencies.')
