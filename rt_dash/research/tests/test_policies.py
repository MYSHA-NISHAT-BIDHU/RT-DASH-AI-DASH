from rt_dash.model import Criticality, Job, TaskSpec
from rt_dash.policies import Mode, PolicyName, select_job


def make_job(task_id, deadline, criticality, period=100):
    task = TaskSpec(task_id, task_id, 10, deadline, criticality, period=period)
    return Job(task, 0, 0, 10, deadline)


def test_edf_selects_earliest_deadline():
    early = make_job("early", 20, Criticality.LOW)
    late = make_job("late", 40, Criticality.HIGH)
    assert select_job([late, early], PolicyName.EDF, Mode.NORMAL) is early


def test_rt_dash_critical_mode_selects_high_criticality_before_deadline():
    low_early = make_job("low", 20, Criticality.LOW)
    high_late = make_job("high", 40, Criticality.HIGH)
    assert select_job([low_early, high_late], PolicyName.RT_DASH, Mode.CRITICAL) is high_late


def test_rms_selects_shortest_period():
    fast = make_job("fast", 100, Criticality.LOW, period=50)
    slow = make_job("slow", 50, Criticality.HIGH, period=200)
    assert select_job([slow, fast], PolicyName.RMS, Mode.NORMAL) is fast

def test_static_criticality_edf_prioritizes_criticality_without_mode_switch():
    from rt_dash.model import Criticality, Job, TaskSpec
    from rt_dash.policies import Mode, PolicyName, select_job

    low = Job(TaskSpec('low_static', 'low', 5, 10, Criticality.LOW), 0, 0, 5, 10)
    high = Job(TaskSpec('high_static', 'high', 5, 50, Criticality.HIGH), 0, 0, 5, 50)
    assert select_job([low, high], PolicyName.CRITICALITY_EDF, Mode.NORMAL) is high


def test_recovery_edf_uses_edf_when_no_high_jobs():
    from rt_dash.model import Job
    from rt_dash.policies import Mode, PolicyName, select_job

    later_medium = TaskSpec(
        "m", "medium", 5, 200, Criticality.MEDIUM, period=200
    )
    urgent_low = TaskSpec(
        "l", "low", 5, 50, Criticality.LOW, period=100,
        degradable=True, min_service_fraction=0.5,
    )
    medium_job = Job(later_medium, 0, 0, 5, 200)
    low_job = Job(urgent_low, 0, 0, 5, 50)
    assert select_job(
        [medium_job, low_job], PolicyName.RT_DASH_RECOVERY_EDF, Mode.CRITICAL
    ) is low_job


def test_recovery_edf_still_prioritizes_high_jobs():
    from rt_dash.model import Job
    from rt_dash.policies import Mode, PolicyName, select_job

    high = TaskSpec("h", "high", 5, 200, Criticality.HIGH, period=200)
    low = TaskSpec(
        "l2", "low", 5, 20, Criticality.LOW, period=100,
        degradable=True, min_service_fraction=0.5,
    )
    high_job = Job(high, 0, 0, 5, 200)
    low_job = Job(low, 0, 0, 5, 20)
    assert select_job(
        [high_job, low_job], PolicyName.RT_DASH_RECOVERY_EDF, Mode.CRITICAL
    ) is high_job
