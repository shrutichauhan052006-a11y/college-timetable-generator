# PROJECT_STATUS.md

Current phase
Phase 4 complete: algorithm benchmarking, raw experiment records, summary tables, Min-Conflicts cost trace, report PDF/source, tests, and reproducibility documentation generated from the existing Phase 1–3 project.
Phase 1 retained
- core/models.py, core/data_loader.py, core/schema.json
- core/constraints.py, core/scoring.py, core/validator.py
- data/small_dataset.json, data/large_dataset.json
- tools/generate_datasets.py, tests/test_phase1.py, reports/phase1_verification.md
Phase 2 retained
- algorithms/backtracking.py — plain fixed-order recursive CSP backtracking; no MRV, Degree, or Forward Checking.
- algorithms/improved_backtracking.py — MRV, Degree tie-break, reversible Forward Checking.
- algorithms/min_conflicts.py — seeded complete-assignment local search, random walk and plateau restart.
- algorithms/common.py, algorithms/README.md, tests/test_phase2.py.
Phase 3 retained
- app.py and ui/services.py — Streamlit app, data editing, timetable views, manual edits/undo, validation, CSV/Excel exports.
- algorithms/simulated_annealing.py — feasible-start SA that rejects hard-infeasible neighbours.
- algorithms/hybrid_csp_sa.py — improved CSP feasibility stage then SA refinement.
- tests/test_phase3.py.
Phase 4 files added or updated
- experiments/run_benchmarks.py — reproducible 64-attempt experiment runner with resumable per-run persistence, independent final validation, random seeds, failure/timeout fields, candidate costs, and summary statistics.
- experiments/generate_report.py — generates actual cost-history graph, editable Markdown report and PDF.
- tests/test_phase4.py — witness validation, objective formula, Min-Conflicts history/reproducibility, summary calculation tests.
- reports/phase4/raw_results.csv, raw_results.json — per-run records.
- reports/phase4/comparison_summary.csv, comparison_summary.json — dataset/algorithm aggregates and variability.
- reports/phase4/experiment_metadata.json — environment, dataset sizes, weights, settings, seeds and protocol.
- reports/phase4/min_conflicts_cost_history.csv, .json — actual trace for small dataset, seed 20261001.
- reports/phase4/min_conflicts_cost_vs_iterations.png — report-ready plotted trace.
- reports/phase4/project_report.pdf — verified 8-page report.
- reports/phase4/project_report.md — editable report source with course/college/supervisor/date placeholders.
- reports/phase4/benchmark_console.log — benchmark execution log.
- README.md and requirements.txt updated for reproducibility/report generation.
Inspection findings and data validation
All five algorithms are implemented and callable. All use the shared ProblemData model; CSP methods use shared incremental constraints and all returned schedules are checked by core/validator.py. Min-Conflicts may explore infeasible complete assignments by design, but only a complete candidate with zero independent-validator issues is counted as a success. SA requires an independently feasible initial schedule and rejects invalid neighbors. Hybrid runs SA only if CSP returns a validated feasible schedule.

Actual dataset sizes:
- Small: 5 subjects, 6 teachers, 3 classes, 4 rooms, 5 days × 6 periods; 30 required teaching periods; bundled witness has 24 atomic placements.
- Large: 5 subjects, 15 teachers, 8 classes, 8 rooms, 5 days × 7 periods; 80 required teaching periods; bundled witness has 64 atomic placements.
Both bundled witnesses passed the independent final validator. Lab placements are represented as atomic consecutive blocks with their subject-defined duration. The existing dataset weights were retained: S1=2, S2=3, S3=10, S4=1, S5=1. S1–S3 are the implemented primary soft criteria; S4/S5 are documented project-specific preferences already present in the source.
Phase 4 protocol
- 64 attempts: 2 deterministic algorithms × 2 datasets × 1 run, plus 3 randomized algorithms × 2 datasets × 10 runs.
- Random seeds: 20261001–20261010, distinct per run and repeated across the two datasets for comparable seed labels.
- Plain and improved CSP: one run per dataset; 5 s time cap and 30,000 node cap. Resource cutoffs are not proof of infeasibility. CSP time checks occur during recursive search after domain construction, so domain-generation time can make wall time exceed the nominal search cap.
- Min-Conflicts: 10 runs/dataset; max 30 iterations on small and 3 on large, random-walk probability 0.08, restart after 15 stagnant steps, max one restart.
- Standalone SA: 10 runs/dataset; 300 iterations, initial temperature 10, cooling 0.99, minimum temperature 0.01. Uses the independently validated bundled witness as the common feasible starting schedule; witness preparation is excluded from SA runtime, so standalone SA timing measures refinement, not end-to-end construction.
- Hybrid: 10 runs/dataset; CSP stage capped at 2 s/10,000 nodes for small and 0.5 s/1,000 nodes for large, then up to 300 SA iterations. Hybrid runtime includes CSP construction.
- Objective: 1000 * hard_violation_count + soft_penalty_score.
- Runtime/search effort average all attempts. Soft penalty and total cost are averaged only across successful, complete, independently validated schedules. Failed Min-Conflicts attempts record best-candidate hard violations when available; failed CSP/hybrid attempts without a candidate report N/A.
Actual experimental outcomes
- Total attempts: 64. Successful complete, independently validated schedules: 42/64.
- Small dataset: plain Backtracking 1/1; Improved Backtracking 1/1; Min-Conflicts 10/10; SA 10/10; Hybrid 10/10.
- Large dataset: plain Backtracking 0/1 (resource limit); Improved Backtracking 0/1 (resource limit); Min-Conflicts 0/10 (3-iteration limit); SA 10/10; Hybrid 0/10 (CSP-stage limit).
- Small mean soft penalty among successful schedules: Hybrid 31.3 (lowest), SA 31.6, Min-Conflicts 38.7, Improved Backtracking 56.0, Plain Backtracking 57.0. Since hard violations are zero for successful schedules, total cost equals soft penalty for those rows.
- Large mean soft penalty among successful schedules: SA 104.8. It is the only method with successful large-dataset runs under this protocol.
- Fastest observed mean runtime on small: Plain Backtracking, approximately 0.065 s (single run). On large: SA refinement, approximately 1.317 s mean; this excludes witness preparation and is not directly comparable to end-to-end CSP construction.
- Min-Conflicts graph uses real values from seed 20261001: cost 7054 at iteration 0, plateau at 3051 during iterations 2–3, then decreases to 41 at iteration 6. This run reaches a feasible solution because cost is below the 1000-per-hard-violation threshold and the algorithm independently validates it.
- These results are specific to the synthetic datasets and the stated resource limits. In particular, the 3-iteration Min-Conflicts limit and short large hybrid CSP cap explain some failures; limits do not imply infeasibility.
Verification performed
Environment: Python 3.13.5, Linux workspace.

Commands:
python -m compileall -q core algorithms ui tests app.py experiments
python -m unittest discover -s tests -v
python -m experiments.run_benchmarks
python -m experiments.generate_report
pdfinfo reports/phase4/project_report.pdf
Latest automated test result: 45 tests passed, 0 failures (22 Phase 1 + 7 Phase 2 + 12 Phase 3 + 4 Phase 4 tests). Both dataset witnesses independently validate. All 64 attempts were recorded. The PDF page count was checked with pdfinfo: 8 pages, landscape A4. Graph and report are generated from saved experiment data. Streamlit browser launch remains not re-verified in this offline workspace; Phase 4 did not alter the Phase 3 app.
Windows PowerShell reproduction
From the extracted project root:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m experiments.run_benchmarks
python -m experiments.generate_report
streamlit run app.py
The benchmark runner resumes from reports/phase4/raw_results.json. To intentionally start a fresh experiment, back up or remove the Phase 4 raw result and summary files before running it again. Repeated runs can take several minutes because large-domain construction is expensive.
Remaining issues / next steps
- The large-dataset results show that the current Min-Conflicts and hybrid resource settings are too restrictive for successful search; test longer iteration/CSP budgets in a separately labelled experiment before drawing broader conclusions.
- Standalone SA is a feasible-start optimizer; for a strict end-to-end comparison, either include common seed-generation cost in a separately reported total or implement a clearly specified feasible initialization stage.
- Confirm the proposed team contribution allocation and fill course, college, supervisor, and submission-date placeholders before final submission.
- Perform a Windows-local Streamlit smoke test after installing requirements; this environment verified the source/tests/report generation but did not launch the browser UI.
Stop point
Phase 4 completed. No further phase has been started.
