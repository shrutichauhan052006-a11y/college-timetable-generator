# Phase 1 dataset verification evidence

## Execution
The Phase 1 test suite was executed in the available runtime using `python -m unittest discover -s tests -v`: **22 passed, 0 failed**.

## Witnesses
- `data/small_dataset.json`: 3 classes, 6 teachers, 4 rooms, 5 working days × 6 periods; 24 placement records, representing 30 teaching periods (10 per class).
- `data/large_dataset.json`: 8 classes, 15 teachers, 8 rooms, 5 working days × 7 periods; 64 placement records, representing 80 teaching periods (10 per class).

Each JSON includes a `verification_witness`. The test reconstructs a `Schedule` and calls `core.validator.validate_timetable`, which independently checks teacher/class/room collisions, room type and capacity, teacher qualification and availability, lunch/break overlap, duration and period bounds, teacher load, and exact weekly period requirements per class/subject. Both witnesses returned no violations.

This is witness-based feasibility evidence for the provided synthetic data, not proof that arbitrary input instances are feasible and not a result from any production search algorithm. Windows PowerShell execution has not been observed in this environment and should be run locally.
