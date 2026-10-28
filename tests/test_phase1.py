import json, unittest
from pathlib import Path
from core.models import *
from core.constraints import check_placements
from core.validator import validate_timetable, is_feasible
from core.scoring import soft_penalties, score_schedule
from core.data_loader import problem_from_dict, load_problem, DataValidationError

def fixture():
    return ProblemData((Subject('T','Theory','theory'),Subject('L','Lab','lab',2)),
      (Teacher('A',frozenset({'T'}),frozenset({Slot('Mon',5)}),10,frozenset({Slot('Mon',0),Slot('Tue',0)})),Teacher('B',frozenset({'L'}),max_weekly_load=10)),
      (ClassGroup('C',20,{'T':2,'L':2},3),),(Room('R',30,'classroom'),Room('LabR',25,'lab')),TimeStructure(('Mon','Tue','Wed'),6))
def valid():
    return Schedule([Placement('t1','C','T','A','R','Mon',0,1),Placement('t2','C','T','A','R','Tue',0,1),Placement('l1','C','L','B','LabR','Mon',1,2)])
class Tests(unittest.TestCase):
    def codes(self,p,placements): return {v.code for v in check_placements(p,placements)}
    def test_valid_schedule(self):
        p,s=fixture(),valid(); self.assertEqual(check_placements(p,s.placements),[]); self.assertEqual(validate_timetable(p,s),[]); self.assertTrue(is_feasible(p,s))
    def test_h1_teacher_collision(self):
        p=fixture(); ps=valid().placements+[Placement('x','C','T','A','R','Mon',0,1)]; self.assertIn('H1_TEACHER_COLLISION',self.codes(p,ps))
    def test_h2_class_collision(self):
        p=fixture(); ps=valid().placements+[Placement('x','C','T','A','R','Mon',0,1)]; self.assertIn('H2_CLASS_COLLISION',self.codes(p,ps))
    def test_h3_room_collision(self):
        p=fixture(); p=ProblemData(p.subjects,p.teachers+(Teacher('D',frozenset({'T'}),max_weekly_load=10),),p.classes+(ClassGroup('C2',15,{'T':1},3),),p.rooms,p.time)
        ps=[Placement('a','C','T','A','R','Mon',0,1),Placement('b','C2','T','D','R','Mon',0,1)]; self.assertIn('H3_ROOM_COLLISION',self.codes(p,ps))
    def test_h4_capacity(self):
        p=fixture(); p=ProblemData(p.subjects,p.teachers,p.classes,(Room('R',10,'classroom'),p.rooms[1]),p.time); self.assertIn('ROOM_CAPACITY',self.codes(p,valid().placements))
    def test_h5_room_type(self): self.assertIn('ROOM_TYPE',self.codes(fixture(),[Placement('x','C','T','A','LabR','Mon',0,1)]))
    def test_h6_unavailable(self): self.assertIn('UNAVAILABLE',self.codes(fixture(),[Placement('x','C','T','A','R','Mon',5,1)]))
    def test_h7_missing_or_extra(self):
        p=fixture(); self.assertIn('WEEKLY_HOURS',{v.code for v in validate_timetable(p,Schedule(valid().placements[:-1]))})
        self.assertIn('WEEKLY_HOURS',{v.code for v in validate_timetable(p,Schedule(valid().placements+[Placement('x','C','T','A','R','Wed',0,1)]))})
    def test_h8_workload(self):
        p=fixture(); p=ProblemData(p.subjects,(Teacher('A',frozenset({'T'}),max_weekly_load=1),p.teachers[1]),p.classes,p.rooms,p.time); self.assertIn('WORKLOAD',self.codes(p,valid().placements))
    def test_h9_lunch(self): self.assertIn('LUNCH',self.codes(fixture(),[Placement('x','C','T','A','R','Mon',3,1)]))
    def test_duplicate_session(self):
        ps=valid().placements+[Placement('t1','C','T','A','R','Wed',0,1)]; self.assertIn('DUPLICATE_SESSION_ID',{v.code for v in validate_timetable(fixture(),Schedule(ps))})
    def test_consecutive_lab_duration(self): self.assertIn('LAB_DURATION',self.codes(fixture(),[Placement('l','C','L','B','LabR','Mon',1,1)]))
    def test_s1_gap(self): self.assertEqual(soft_penalties(fixture(),[Placement('a','C','T','A','R','Mon',0,1),Placement('b','C','T','A','R','Mon',2,1)])['S1'],1)
    def test_s1_lunch_is_not_counted_as_a_gap(self): self.assertEqual(soft_penalties(fixture(),[Placement('a','C','T','A','R','Mon',2,1),Placement('b','C','T','A','R','Mon',4,1)])['S1'],0)
    def test_s2_theory_repeat_same_day(self): self.assertEqual(soft_penalties(fixture(),[Placement('a','C','T','A','R','Mon',0,1),Placement('b','C','T','A','R','Mon',1,1)])['S2'],1)
    def test_s3_malformed_lab(self): self.assertEqual(soft_penalties(fixture(),[Placement('l','C','L','B','LabR','Mon',1,1)])['S3'],1)
    def test_s4_preference(self): self.assertEqual(soft_penalties(fixture(),[Placement('a','C','T','A','R','Mon',2,1)])['S4'],1)
    def test_s5_last_period(self): self.assertEqual(soft_penalties(fixture(),[Placement('a','C','T','A','R','Mon',5,1)])['S5'],1)
    def test_cost_formula(self):
        p=fixture(); r=score_schedule(p,[Placement('x','C','T','A','R','Mon',3,1)]); self.assertEqual(r['cost'],1000*r['hard_violations']+r['soft_penalty_score'])
    def test_cost_includes_missing_required_sessions(self):
        p=fixture(); r=score_schedule(p,valid().placements[:-1]); self.assertGreaterEqual(r['hard_violations'],1); self.assertGreaterEqual(r['cost'],1000)
    def test_invalid_input(self):
        with self.assertRaises(DataValidationError): problem_from_dict({'schema_version':'1.0'})
    def test_datasets_have_independently_validated_witnesses(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('small_dataset','large_dataset'):
            raw=json.loads((root/'data'/f'{name}.json').read_text(encoding='utf-8')); p=load_problem(root/'data'/f'{name}.json')
            s=Schedule([Placement(**x) for x in raw['verification_witness']]); self.assertEqual(validate_timetable(p,s),[],name); self.assertTrue(is_feasible(p,s),name)
if __name__=='__main__': unittest.main()
