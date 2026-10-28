import unittest
from pathlib import Path

from algorithms import solve_backtracking, solve_improved_backtracking, solve_min_conflicts
from core.data_loader import load_problem
from core.models import ClassGroup, ProblemData, Room, Slot, Subject, Teacher, TimeStructure, Schedule
from core.validator import is_feasible, validate_timetable

ROOT = Path(__file__).resolve().parents[1]

def tiny_problem():
    return ProblemData(
        subjects=(Subject('TH', 'Theory', 'theory'), Subject('LB', 'Lab', 'lab', 2)),
        teachers=(Teacher('T1', frozenset({'TH'}), max_weekly_load=8),
                  Teacher('T2', frozenset({'LB'}), max_weekly_load=8)),
        classes=(ClassGroup('C1', 20, {'TH': 2, 'LB': 2}, 3),),
        rooms=(Room('R1', 30, 'classroom'), Room('R2', 25, 'lab')),
        time=TimeStructure(('Mon', 'Tue', 'Wed'), 4),
    )

class Phase2AlgorithmTests(unittest.TestCase):
    def assert_result_sound(self, problem, result):
        self.assertIn(result.status, {'feasible', 'proven_infeasible', 'inconclusive', 'iteration_limit'})
        if result.schedule is not None:
            self.assertEqual(validate_timetable(problem, result.schedule), [])
            self.assertTrue(is_feasible(problem, result.schedule))
            self.assertEqual(result.status, 'feasible')
            expected = sum(n for c in problem.classes for n in c.subject_periods.values())
            actual = sum(p.duration for p in result.schedule.placements)
            self.assertEqual(actual, expected)

    def test_all_algorithms_solve_tiny_problem(self):
        p = tiny_problem()
        results = [solve_backtracking(p, time_limit_seconds=3, node_limit=10000),
                   solve_improved_backtracking(p, time_limit_seconds=3, node_limit=10000),
                   solve_min_conflicts(p, max_iterations=500, seed=7, restart_after=30)]
        for result in results: self.assert_result_sound(p, result)
        self.assertTrue(all(r.feasible for r in results), [r.termination_reason for r in results])

    def test_empty_unary_domain_is_proven_infeasible_for_csp_search(self):
        p = tiny_problem()
        teachers = (Teacher('T1', frozenset({'TH'}), max_weekly_load=0), p.teachers[1])
        p = ProblemData(p.subjects, teachers, p.classes, p.rooms, p.time)
        for solve in (solve_backtracking, solve_improved_backtracking):
            result = solve(p, time_limit_seconds=2, node_limit=100)
            self.assertEqual(result.status, 'proven_infeasible')
            self.assertIsNone(result.schedule)

    def test_plain_backtracking_node_limit_is_inconclusive(self):
        p = tiny_problem()
        result = solve_backtracking(p, time_limit_seconds=None, node_limit=0)
        self.assertEqual(result.status, 'inconclusive')
        self.assertIsNone(result.schedule)
        self.assertIn('node_limit', result.termination_reason)

    def test_improved_reports_domain_deletions(self):
        p = tiny_problem()
        result = solve_improved_backtracking(p, time_limit_seconds=3, node_limit=10000)
        self.assert_result_sound(p, result)
        self.assertGreaterEqual(result.domain_deletions, 0)

    def test_min_conflicts_seed_is_reproducible(self):
        p = tiny_problem()
        a = solve_min_conflicts(p, max_iterations=15, seed=91, restart_after=5)
        b = solve_min_conflicts(p, max_iterations=15, seed=91, restart_after=5)
        self.assertEqual(a.status, b.status)
        self.assertEqual(a.cost_history, b.cost_history)
        self.assertEqual([x for x in (a.schedule.placements if a.schedule else [])],
                         [x for x in (b.schedule.placements if b.schedule else [])])

    def test_all_algorithms_on_small_dataset(self):
        p = load_problem(ROOT / 'data' / 'small_dataset.json')
        results = [solve_backtracking(p, time_limit_seconds=2, node_limit=500),
                   solve_improved_backtracking(p, time_limit_seconds=2, node_limit=500),
                   solve_min_conflicts(p, max_iterations=40, seed=2026, restart_after=15, max_restarts=1)]
        for result in results: self.assert_result_sound(p, result)
        self.assertTrue(all(r.runtime_seconds >= 0 for r in results))

    def test_large_dataset_uses_resource_limits(self):
        p = load_problem(ROOT / 'data' / 'large_dataset.json')
        a = solve_backtracking(p, time_limit_seconds=0.05, node_limit=5)
        b = solve_improved_backtracking(p, time_limit_seconds=0.05, node_limit=5)
        c = solve_min_conflicts(p, max_iterations=0, seed=2)
        for result in (a, b, c): self.assert_result_sound(p, result)
        self.assertNotEqual(a.status, 'proven_infeasible')
        self.assertNotEqual(b.status, 'proven_infeasible')
        self.assertEqual(c.status, 'iteration_limit')

if __name__ == '__main__': unittest.main()
