import pytest

from rt_dash.model import Criticality, Job, TaskSpec


def test_task_validation_rejects_degradable_high_criticality():
    with pytest.raises(ValueError):
        TaskSpec(
            "h", "high", 10, 20, Criticality.HIGH,
            degradable=True, min_service_fraction=0.5,
        )


def test_service_floor_removes_only_optional_remaining_work():
    task = TaskSpec(
        "low", "low", 100, 200, Criticality.LOW,
        degradable=True, min_service_fraction=0.4,
    )
    job = Job(task, 0, 0, 100, 200)
    job.remaining = 70  # 30 units already executed
    removed = job.apply_service_floor()
    assert removed == 60
    assert job.remaining == 10
    assert job.service_reduction == 60
    assert job.apply_service_floor() == 0


def test_blocking_time_is_bounded_by_execution_budget():
    with pytest.raises(ValueError, match="blocking_time"):
        TaskSpec(
            "blocked", "blocked", 5, 20, Criticality.LOW, blocking_time=6
        )
