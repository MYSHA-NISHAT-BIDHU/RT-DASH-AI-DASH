from pathlib import Path

import pandas as pd

from rt_dash.workloads import nominal_utilization, scaled_periodic_taskset, trace_window_events


def test_scaled_utilization_is_close_to_target():
    for target in (0.6, 0.9, 1.2):
        tasks = scaled_periodic_taskset(target, seed=3)
        assert abs(nominal_utilization(tasks) - target) < 0.03


def test_trace_mapping_is_deterministic(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "timestamp": ["2025-01-01 00:00:00", "2025-01-01 00:00:01"],
            "sensor": [0, 1],
            "Activity": [0, 5],
            "Priority": [1, 5],
            "CPU": [20, 90],
            "Memory": [50, 400],
            "Storage": [10, 70],
            "Bandwidth": [2, 20],
        }
    )
    path = tmp_path / "trace.csv"
    frame.to_csv(path, index=False)
    first = trace_window_events(path, 0, 2)
    second = trace_window_events(path, 0, 2)
    assert [(e.task.name, e.release_time, e.task.wcet) for e in first] == [
        (e.task.name, e.release_time, e.task.wcet) for e in second
    ]
    assert any(e.task.criticality.name == "HIGH" for e in first)


def test_scalable_taskset_is_deterministic_and_close_to_target():
    from rt_dash.workloads import scalable_taskset

    first = scalable_taskset(32, 0.9, seed=4)
    second = scalable_taskset(32, 0.9, seed=4)
    assert [(t.wcet, t.period, t.relative_deadline, t.criticality) for t in first] == [
        (t.wcet, t.period, t.relative_deadline, t.criticality) for t in second
    ]
    assert abs(nominal_utilization(first) - 0.9) < 0.12


def test_trace_deadline_scaling_changes_deadline(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "timestamp": ["2025-01-01 00:00:00"],
            "sensor": [0],
            "Activity": [5],
            "Priority": [5],
            "CPU": [50],
            "Memory": [10],
            "Storage": [0],
            "Bandwidth": [1],
        }
    )
    path = tmp_path / "trace_deadline.csv"
    frame.to_csv(path, index=False)
    nominal = trace_window_events(path, 0, 1, deadline_scale=1.0)
    relaxed = trace_window_events(path, 0, 1, deadline_scale=1.5)
    assert relaxed[0].task.relative_deadline > nominal[0].task.relative_deadline
