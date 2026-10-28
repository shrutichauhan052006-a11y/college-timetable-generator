"""Streamlit front end for the timetable CSP project. Run: streamlit run app.py"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from core.data_loader import DataValidationError, problem_from_dict, load_problem
from core.models import Schedule
from core.scoring import score_schedule
from core.validator import validate_timetable
from algorithms import solve_backtracking, solve_improved_backtracking, solve_min_conflicts
from algorithms.simulated_annealing import solve_simulated_annealing
from algorithms.hybrid_csp_sa import solve_hybrid_csp_sa
from ui.services import (problem_to_raw, load_uploaded_problem, schedule_rows, timetable_view,
    move_placement, export_csv, export_excel, undo_last)

ROOT=Path(__file__).parent
SAMPLES={'Small dataset':'data/small_dataset.json','Large dataset':'data/large_dataset.json'}
st.set_page_config(page_title='College Timetable Generator',page_icon='🗓️',layout='wide')
st.title('AI-Based College Timetable Generator')
st.caption('Constraint-based scheduling · Three required search algorithms · Optional Simulated Annealing')

if 'problem' not in st.session_state:
    st.session_state.problem=load_problem(ROOT/'data/small_dataset.json')
    st.session_state.problem_raw=problem_to_raw(st.session_state.problem)
if 'schedule' not in st.session_state: st.session_state.schedule=None
if 'result' not in st.session_state: st.session_state.result=None
if 'undo_stack' not in st.session_state: st.session_state.undo_stack=[]
if 'last_issues' not in st.session_state: st.session_state.last_issues=[]

with st.sidebar:
    st.header('Input data')
    sample=st.selectbox('Sample dataset',list(SAMPLES))
    if st.button('Load selected sample',use_container_width=True):
        p=load_problem(ROOT/SAMPLES[sample]); st.session_state.problem=p; st.session_state.problem_raw=problem_to_raw(p)
        st.session_state.schedule=None; st.session_state.result=None; st.session_state.undo_stack=[]; st.success(f'Loaded {sample}.')
    uploaded=st.file_uploader('Upload problem JSON or CSV bundle ZIP',type=['json','zip'],help='CSV must be a ZIP containing subjects.csv, teachers.csv, classes.csv, rooms.csv, and time.csv.')
    if uploaded is not None and st.button('Load uploaded input',use_container_width=True):
        try:
            p=load_uploaded_problem(uploaded.name,uploaded.getvalue()); st.session_state.problem=p; st.session_state.problem_raw=problem_to_raw(p)
            st.session_state.schedule=None; st.session_state.result=None; st.session_state.undo_stack=[]; st.success('Input validated and loaded.')
        except Exception as exc: st.error(str(exc))

problem=st.session_state.problem
raw=st.session_state.problem_raw

st.subheader('Problem editor')
st.info('Edit the tables below, then press **Validate and save changes**. Availability, preferred slots, working days, and break slots use JSON arrays in their cells. Period indices in input are zero-based; timetable displays use human-friendly period numbers.')
with st.form('problem_editor'):
    edit_tabs=st.tabs(['Subjects','Teachers & availability','Classes & requirements','Rooms','Time structure','Soft weights'])
    with edit_tabs[0]:
        df_subjects=pd.DataFrame(raw['subjects'])
        edited_subjects=st.data_editor(df_subjects,num_rows='dynamic',key='ed_subjects',use_container_width=True)
        st.caption('Columns: code, name, kind (theory/lab), session_length. Labs occupy consecutive periods atomically.')
    with edit_tabs[1]:
        tdf=pd.DataFrame([{**t,'qualified_subjects':json.dumps(t['qualified_subjects']),'unavailable_slots':json.dumps(t['unavailable_slots']),'preferred_slots':json.dumps(t['preferred_slots'])} for t in raw['teachers']])
        edited_teachers=st.data_editor(tdf,num_rows='dynamic',key='ed_teachers',use_container_width=True)
        st.caption('qualified_subjects, unavailable_slots, preferred_slots are JSON arrays; slots use {"day":"Mon","period":0}.')
    with edit_tabs[2]:
        cdf=pd.DataFrame([{**c,'subject_periods':json.dumps(c['subject_periods'])} for c in raw['classes']])
        edited_classes=st.data_editor(cdf,num_rows='dynamic',key='ed_classes',use_container_width=True)
        st.caption('subject_periods is a JSON object such as {"MTH":2,"PHY":4}. lunch_period is zero-based.')
    with edit_tabs[3]: edited_rooms=st.data_editor(pd.DataFrame(raw['rooms']),num_rows='dynamic',key='ed_rooms',use_container_width=True)
    with edit_tabs[4]:
        days_text=st.text_input('Working days (comma separated)',','.join(raw['time']['working_days']))
        periods_day=st.number_input('Periods per day',min_value=1,max_value=20,value=int(raw['time']['periods_per_day']))
        breaks_text=st.text_area('Break slots (JSON array)',json.dumps(raw['time']['break_slots']))
    with edit_tabs[5]:
        wdf=pd.DataFrame([{'constraint':k,'weight':v} for k,v in raw.get('soft_weights',{}).items()])
        edited_weights=st.data_editor(wdf,num_rows='fixed',key='ed_weights',use_container_width=True)
    save_problem=st.form_submit_button('Validate and save changes',type='primary')

if save_problem:
    try:
        def records(df): return df.where(pd.notna(df),None).to_dict('records')
        subjects=[{'code':str(x['code']),'name':str(x['name']),'kind':str(x['kind']),'session_length':int(x.get('session_length') or 1)} for x in records(edited_subjects)]
        teachers=[]
        for x in records(edited_teachers):
            teachers.append({'name':str(x['name']),'qualified_subjects':json.loads(x['qualified_subjects'] or '[]'),'unavailable_slots':json.loads(x['unavailable_slots'] or '[]'),'preferred_slots':json.loads(x['preferred_slots'] or '[]'),'max_weekly_load':int(x['max_weekly_load'])})
        classes=[]
        for x in records(edited_classes): classes.append({'name':str(x['name']),'strength':int(x['strength']),'subject_periods':json.loads(x['subject_periods']),'lunch_period':int(x['lunch_period'])})
        rooms=[{'name':str(x['name']),'capacity':int(x['capacity']),'kind':str(x['kind'])} for x in records(edited_rooms)]
        weights={str(x['constraint']):int(x['weight']) for x in records(edited_weights)}
        candidate={'schema_version':'1.0','subjects':subjects,'teachers':teachers,'classes':classes,'rooms':rooms,
            'time':{'working_days':[x.strip() for x in days_text.split(',') if x.strip()],'periods_per_day':int(periods_day),'break_slots':json.loads(breaks_text)},'soft_weights':weights}
        p=problem_from_dict(candidate); st.session_state.problem=p; st.session_state.problem_raw=problem_to_raw(p)
        st.session_state.schedule=None; st.session_state.result=None; st.session_state.undo_stack=[]
        st.success('Problem changes saved after validation. Existing timetable cleared because its input changed.')
    except Exception as exc: st.error(f'Could not save input: {exc}')

st.divider(); st.subheader('Generate timetable')
with st.form('generation_form'):
    algorithm=st.selectbox('Algorithm',['Plain Backtracking CSP','Improved Backtracking CSP','Min-Conflicts','Simulated Annealing (bonus)','Hybrid CSP + SA (bonus)'])
    col1,col2,col3=st.columns(3)
    with col1: time_limit=st.number_input('Time limit (seconds)',min_value=0.0,max_value=600.0,value=10.0,step=1.0); node_limit=st.number_input('Node limit (CSP)',min_value=0,max_value=5_000_000,value=100000,step=1000)
    with col2: iterations=st.number_input('Iteration limit',min_value=0,max_value=1_000_000,value=2000,step=100); seed=st.number_input('Random seed',min_value=0,max_value=2_147_483_647,value=0)
    with col3: temperature=st.number_input('SA initial temperature',min_value=0.01,value=10.0); cooling=st.slider('SA cooling rate',min_value=0.90,max_value=0.999,value=0.995,step=0.001)
    generate=st.form_submit_button('Generate',type='primary')

if generate:
    with st.spinner('Searching for a complete timetable…'):
        if algorithm=='Plain Backtracking CSP': result=solve_backtracking(problem,time_limit_seconds=time_limit,node_limit=int(node_limit))
        elif algorithm=='Improved Backtracking CSP': result=solve_improved_backtracking(problem,time_limit_seconds=time_limit,node_limit=int(node_limit))
        elif algorithm=='Min-Conflicts': result=solve_min_conflicts(problem,max_iterations=int(iterations),seed=int(seed))
        elif algorithm=='Simulated Annealing (bonus)':
            initial=solve_improved_backtracking(problem,time_limit_seconds=time_limit,node_limit=int(node_limit))
            result=solve_simulated_annealing(problem,initial.schedule,max_iterations=int(iterations),initial_temperature=temperature,cooling_rate=cooling,seed=int(seed)) if initial.feasible else initial
            if not initial.feasible: result.termination_reason='Feasible CSP seed unavailable; SA was not started. '+result.termination_reason
        else: result=solve_hybrid_csp_sa(problem,time_limit_seconds=time_limit,node_limit=int(node_limit),sa_iterations=int(iterations),seed=int(seed),initial_temperature=temperature,cooling_rate=cooling)
    st.session_state.result=result
    if result.feasible:
        st.session_state.schedule=result.schedule; st.session_state.undo_stack=[]; st.session_state.last_issues=validate_timetable(problem,result.schedule)
    else:
        st.session_state.schedule=None

result=st.session_state.result
if result:
    st.subheader('Search result')
    if result.feasible: st.success('FEASIBLE — the complete timetable passed the independent validator.')
    else: st.error(f'NO FEASIBLE TIMETABLE RETURNED — status: {result.status}. This does not imply infeasibility unless proven_infeasible is explicitly reported.')
    report=score_schedule(problem,result.schedule.placements) if result.feasible else None
    metrics=st.columns(5)
    metrics[0].metric('Runtime',f'{result.runtime_seconds:.3f} s')
    metrics[1].metric('Nodes / iterations',str(result.nodes_expanded if result.nodes_expanded else result.iterations))
    metrics[2].metric('Hard violations',str(report['hard_violations'] if report else 'N/A'))
    metrics[3].metric('Soft penalty',str(report['soft_penalty_score'] if report else 'N/A'))
    metrics[4].metric('Cost',str(report['cost'] if report else 'N/A'))
    st.write(f'**Algorithm:** {result.algorithm} · **Termination:** {result.status} · **Reason:** {result.termination_reason}')
    if result.backtracks or result.domain_deletions: st.caption(f'Backtracks: {result.backtracks} · Domain deletions: {result.domain_deletions}')
    if result.violations: st.dataframe(pd.DataFrame([v.to_dict() for v in result.violations]),use_container_width=True)

schedule=st.session_state.schedule
if schedule:
    st.divider(); st.subheader('Timetable views')
    dimension=st.radio('View by',['Class','Teacher','Room'],horizontal=True)
    grids=timetable_view(problem,schedule,dimension.lower())
    selected_entity=st.selectbox(f'{dimension} to display',list(grids))
    grid=grids[selected_entity]
    labels=[f'Period {i+1}' for i in range(problem.time.periods_per_day)]
    st.dataframe(pd.DataFrame(grid,index=problem.time.working_days,columns=labels),use_container_width=True)
    st.caption('FREE = unoccupied period; LUNCH and BREAK are explicit. Lab cells show their position within the atomic multi-period session.')
    st.subheader('Manual edit')
    choices={f"{p.session_id} — {p.class_name} / {p.subject_code} / {p.day} P{p.start_period+1}":p for p in schedule.placements}
    with st.form('edit_session'):
        chosen_label=st.selectbox('Session to move',list(choices)); old=choices[chosen_label]
        compatible_rooms=[r.name for r in problem.rooms if r.kind==next(s.kind for s in problem.subjects if s.code==old.subject_code) and r.capacity>=next(c.strength for c in problem.classes if c.name==old.class_name)]
        ec1,ec2,ec3=st.columns(3)
        with ec1: new_day=st.selectbox('New day',problem.time.working_days,index=problem.time.working_days.index(old.day))
        with ec2: new_period=st.number_input('New start period (1-based)',min_value=1,max_value=problem.time.periods_per_day,value=old.start_period+1)
        with ec3:
            if compatible_rooms:
                room_index=compatible_rooms.index(old.room_name) if old.room_name in compatible_rooms else 0
                new_room=st.selectbox('Compatible room',compatible_rooms,index=room_index)
            else:
                new_room=None; st.warning('No room is compatible with this session under the current input constraints.')
        apply_edit=st.form_submit_button('Apply move and validate',disabled=not compatible_rooms)
    if apply_edit:
        try:
            candidate,issues,new_issues=move_placement(problem,schedule,old.session_id,day=new_day,start_period=int(new_period)-1,room_name=new_room)
            st.session_state.undo_stack.append(schedule); st.session_state.schedule=candidate; st.session_state.last_issues=issues
            if issues: st.error(f'Edit introduces or retains {len(issues)} hard violation(s). Newly introduced: {len(new_issues)}. Other sessions were not changed.')
            else: st.success('Edit accepted: timetable remains feasible.')
            if new_issues: st.dataframe(pd.DataFrame([v.to_dict() for v in new_issues]),use_container_width=True)
            st.rerun()
        except Exception as exc: st.error(f'Edit failed: {exc}')
    undo_col,validation_col=st.columns(2)
    with undo_col:
        if st.button('Undo last edit',disabled=not st.session_state.undo_stack):
            st.session_state.schedule=undo_last(st.session_state.undo_stack); st.session_state.last_issues=validate_timetable(problem,st.session_state.schedule); st.rerun()
    with validation_col:
        current_issues=validate_timetable(problem,st.session_state.schedule)
        current_report=score_schedule(problem,st.session_state.schedule.placements)
        if current_issues: st.error(f'Current edited schedule has {len(current_issues)} hard violation(s); export remains available but is labelled conflicting.')
        else: st.success('Current edited schedule passes independent validation.')
        cm=st.columns(3)
        cm[0].metric('Current hard violations',current_report['hard_violations'])
        cm[1].metric('Current soft penalty',current_report['soft_penalty_score'])
        cm[2].metric('Current cost',current_report['cost'])
    st.subheader('Export')
    csv_data=export_csv(problem,st.session_state.schedule); xlsx_data=export_excel(problem,st.session_state.schedule)
    st.download_button('Download timetable CSV',csv_data,file_name='timetable.csv',mime='text/csv')
    st.download_button('Download timetable Excel',xlsx_data,file_name='timetable.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.dataframe(pd.DataFrame(schedule_rows(problem,st.session_state.schedule)),use_container_width=True)
else:
    st.info('Generate a feasible timetable to enable views, editing, undo, and exports. Unsuccessful candidates are never shown as accepted schedules.')
