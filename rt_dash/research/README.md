# Deterministic RT-DASH Research Package

This directory contains the Python reference simulator and the complete simulation evidence used in the associated manuscript.

## Main implementation

- `rt_dash/model.py`: task, job, criticality, mode, and service-floor model.
- `rt_dash/policies.py`: EDF, period-based RMS, criticality-first EDF, RT-DASH, ablations, and recovery-aware dispatch.
- `rt_dash/simulator.py`: deterministic 10 ms discrete-event simulation, sampled utilization guards, degradation, recovery, and deadline accounting.
- `rt_dash/workloads.py`: controlled, held-out, scalability, and trace-mapped workload construction.
- `rt_dash/metrics.py`: completion, deadline, response, wait, service, utility, and fairness metrics.

## Evidence groups

- `results/journal_strengthened/`: 8,980 controlled, sensitivity, scalability, and trace-mapping simulations.
- `results/best_journal/`: 6,800 configuration-selection, held-out, robustness, EDF-VD, and optimized-matrix simulations.
- `results/seed_clustered_inference/`: principal seed-level inference generated from the run-level CSV files.

The cumulative executed matrix contains 15,780 simulations. The 70 diagnostic demand screens and five C++ host-policy executions are reported separately and are not counted as simulations.

See the archive-root `REPRODUCE.md` for exact commands and the declared evidence boundary.
