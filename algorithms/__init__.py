"""Search algorithms for the college timetable project."""
from .common import AlgorithmResult
from .backtracking import solve_backtracking
from .improved_backtracking import solve_improved_backtracking
from .min_conflicts import solve_min_conflicts

__all__ = ["AlgorithmResult", "solve_backtracking", "solve_improved_backtracking", "solve_min_conflicts"]
