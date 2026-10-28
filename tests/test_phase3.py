import csv, io, json, unittest, zipfile
from pathlib import Path
from core.data_loader import load_problem
from core.models import Schedule
from core.validator import validate_timetable
from algorithms import solve_improved_backtracking
from algorithms.simulated_annealing import solve_simulated_annealing
from algorithms.hybrid_csp_sa import solve_hybrid_csp_sa
from ui.services import (load_uploaded_problem, problem_to_raw, schedule_rows, timetable_view,
    move_placement, export_csv, export_excel, read_export_csv, read_export_excel, undo_last)

ROOT=Path(__file__).resolve().parents[1]

class Phase3ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.problem=load_problem(ROOT/'data/small_dataset.json')
        cls.result=solve_improved_backtracking(cls.problem,time_limit_seconds=10,node_limit=100000)
        if not cls.result.feasible: raise RuntimeError('small fixture did not yield feasible schedule')
        cls.schedule=cls.result.schedule

    def test_json_upload(self):
        data=(ROOT/'data/small_dataset.json').read_bytes()
        p=load_uploaded_problem('small.json',data)
        self.assertEqual(len(p.classes),3)

    def test_csv_bundle_upload(self):
        raw=problem_to_raw(self.problem); buffer=io.BytesIO()
        def write(z,name,rows,fields):
            s=io.StringIO(newline=''); w=csv.DictWriter(s,fieldnames=fields); w.writeheader(); w.writerows(rows); z.writestr(name,s.getvalue())
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            write(z,'subjects.csv',raw['subjects'],['code','name','kind','session_length'])
            write(z,'teachers.csv',[{**t,'qualified_subjects':json.dumps(t['qualified_subjects']),'unavailable_slots':json.dumps(t['unavailable_slots']),'preferred_slots':json.dumps(t['preferred_slots'])} for t in raw['teachers']],['name','qualified_subjects','unavailable_slots','preferred_slots','max_weekly_load'])
            write(z,'classes.csv',[{**c,'subject_periods':json.dumps(c['subject_periods'])} for c in raw['classes']],['name','strength','subject_periods','lunch_period'])
            write(z,'rooms.csv',raw['rooms'],['name','capacity','kind'])
            write(z,'time.csv',[{'working_days':json.dumps(raw['time']['working_days']),'periods_per_day':raw['time']['periods_per_day'],'break_slots':json.dumps(raw['time']['break_slots'])}],['working_days','periods_per_day','break_slots'])
        p=load_uploaded_problem('input.zip',buffer.getvalue())
        self.assertEqual(len(p.subjects),len(self.problem.subjects))

    def test_views_have_class_teacher_room_keys(self):
        self.assertEqual(len(timetable_view(self.problem,self.schedule,'class')),len(self.problem.classes))
        self.assertEqual(len(timetable_view(self.problem,self.schedule,'teacher')),len(self.problem.teachers))
        self.assertEqual(len(timetable_view(self.problem,self.schedule,'room')),len(self.problem.rooms))

    def test_manual_edit_immediate_validation_and_unrelated_unchanged(self):
        p=self.schedule.placements[0]
        moved,issues,new=move_placement(self.problem,self.schedule,p.session_id,day=p.day,start_period=p.start_period,room_name=p.room_name)
        self.assertEqual(len(moved.placements),len(self.schedule.placements))
        self.assertEqual(len(issues),0); self.assertEqual(new,[])
        for before,after in zip(self.schedule.placements,moved.placements):
            if before.session_id!=p.session_id: self.assertEqual(before,after)

    def test_conflicting_edit_highlighted(self):
        p=self.schedule.placements[0]
        # Move to same class/day period occupied by another placement, if one exists.
        conflict=next((x for x in self.schedule.placements if x.session_id!=p.session_id and x.class_name==p.class_name and x.day==p.day),None)
        if conflict is None: self.skipTest('fixture has no same-day class pair')
        moved,issues,new=move_placement(self.problem,self.schedule,p.session_id,day=conflict.day,start_period=conflict.start_period,room_name=p.room_name)
        self.assertTrue(issues); self.assertTrue(new); self.assertEqual(len(moved.placements),len(self.schedule.placements))

    def test_undo_restores_previous_schedule_snapshot(self):
        history=[self.schedule]
        restored=undo_last(history)
        self.assertIs(restored,self.schedule)
        self.assertEqual(history,[])
        with self.assertRaises(ValueError): undo_last(history)

    def test_lab_move_preserves_atomic_duration(self):
        lab=next(p for p in self.schedule.placements if p.duration>1)
        next_day=next(d for d in self.problem.time.working_days if d!=lab.day)
        moved,issues,new=move_placement(self.problem,self.schedule,lab.session_id,day=next_day,start_period=lab.start_period,room_name=lab.room_name)
        moved_lab=next(p for p in moved.placements if p.session_id==lab.session_id)
        self.assertEqual(moved_lab.duration,lab.duration)
        self.assertEqual(len(moved_lab.occupied_slots()),lab.duration)
        # Whether a collision occurs depends on the target slot; it is always reported, not hidden.
        self.assertEqual(len(moved.placements),len(self.schedule.placements))

    def test_csv_export_roundtrip(self):
        data=export_csv(self.problem,self.schedule); rows=read_export_csv(data)
        self.assertEqual(len(rows),len(self.schedule.placements)); self.assertIn('occupied_periods',rows[0]); self.assertEqual(rows[0]['validation_status'],'FEASIBLE')

    def test_excel_export_roundtrip(self):
        data=export_excel(self.problem,self.schedule); rows=read_export_excel(data)
        self.assertEqual(len(rows),len(self.schedule.placements)); self.assertIn('duration_periods',rows[0])

    def test_sa_rejects_infeasible_start(self):
        result=solve_simulated_annealing(self.problem,Schedule([]),max_iterations=2)
        self.assertFalse(result.feasible); self.assertIsNone(result.schedule)

    def test_sa_returns_independently_feasible_schedule(self):
        result=solve_simulated_annealing(self.problem,self.schedule,max_iterations=10,seed=4)
        self.assertTrue(result.feasible); self.assertEqual(validate_timetable(self.problem,result.schedule),[])

    def test_hybrid_returns_feasible_schedule_or_honest_failure(self):
        result=solve_hybrid_csp_sa(self.problem,time_limit_seconds=10,node_limit=100000,sa_iterations=10,seed=4)
        if result.feasible: self.assertEqual(validate_timetable(self.problem,result.schedule),[])
        else: self.assertIn(result.status,{'inconclusive','proven_infeasible'})

if __name__=='__main__': unittest.main()
