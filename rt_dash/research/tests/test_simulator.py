from rt_dash.metrics import summarize_result
from rt_dash.model import Criticality, TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import EventRelease, SimulationConfig, Simulator


def test_periodic_job_counts_and_completion():
    task = TaskSpec("p", "periodic", 2, 10, Criticality.MEDIUM, period=10)
    result = Simulator([task], [], SimulationConfig(duration=50, policy=PolicyName.EDF)).run()
    assert len(result.jobs) == 5
    assert all(job.completion_time is not None for job in result.jobs)
    assert result.busy_time == 10


def test_event_trigger_enters_critical_mode():
    high = TaskSpec("h", "high", 5, 20, Criticality.HIGH)
    result = Simulator(
        [], [EventRelease(high, 100)],
        SimulationConfig(duration=500, policy=PolicyName.RT_DASH, monitor_interval=10),
    ).run()
    assert any(t.new_mode.value == "critical" for t in result.transitions)


def test_degradation_reduces_low_optional_work():
    low = TaskSpec(
        "low", "low", 100, 200, Criticality.LOW,
        period=250, degradable=True, min_service_fraction=0.25,
    )
    high = TaskSpec("high", "high", 900, 1000, Criticality.HIGH)
    result = Simulator(
        [low], [EventRelease(high, 10)],
        SimulationConfig(duration=1500, policy=PolicyName.RT_DASH, monitor_interval=5),
    ).run()
    assert result.service_reduction > 0


def test_no_degradation_ablation_preserves_budget():
    low = TaskSpec(
        "low", "low", 100, 200, Criticality.LOW,
        period=250, degradable=True, min_service_fraction=0.25,
    )
    high = TaskSpec("high", "high", 900, 1000, Criticality.HIGH)
    result = Simulator(
        [low], [EventRelease(high, 10)],
        SimulationConfig(duration=1500, policy=PolicyName.RT_DASH_NO_DEGRADATION, monitor_interval=5),
    ).run()
    assert result.service_reduction == 0


def test_summary_contains_criticality_metrics():
    high = TaskSpec("h", "high", 5, 20, Criticality.HIGH)
    result = Simulator([], [EventRelease(high, 0)], SimulationConfig(duration=30)).run()
    summary = summarize_result(result)
    assert summary["high_released"] == 1
    assert summary["high_completion_rate"] == 1.0


def test_high_event_triggers_immediately_between_monitor_samples():
    high = TaskSpec("h2", "high", 5, 20, Criticality.HIGH)
    result = Simulator(
        [], [EventRelease(high, 15)],
        SimulationConfig(
            duration=200, quantum=5, policy=PolicyName.RT_DASH, monitor_interval=100
        ),
    ).run()
    entry = next(t for t in result.transitions if t.new_mode.value == "critical")
    assert entry.time == 15
    assert entry.reason == "high-criticality arrival"


def test_deadline_metric_right_censors_jobs_at_horizon():
    task = TaskSpec("censored", "censored", 20, 30, Criticality.MEDIUM, period=90)
    result = Simulator(
        [task], [], SimulationConfig(duration=100, quantum=1, policy=PolicyName.EDF)
    ).run()
    summary = summarize_result(result)
    assert summary["medium_released"] == 2
    assert summary["medium_deadline_assessed"] == 1
    assert summary["medium_deadline_censored"] == 1
    assert summary["medium_deadline_miss_ratio"] == 0.0


def test_quantum_is_work_conserving_after_early_completion():
    first = TaskSpec("q1", "first", 3, 20, Criticality.MEDIUM)
    second = TaskSpec("q2", "second", 4, 30, Criticality.MEDIUM)
    result = Simulator(
        [], [EventRelease(first, 0), EventRelease(second, 0)],
        SimulationConfig(duration=20, quantum=10, policy=PolicyName.EDF),
    ).run()
    jobs = {job.task.task_id: job for job in result.jobs}
    assert jobs["q1"].completion_time == 3
    assert jobs["q2"].completion_time == 7
    assert result.busy_time == 7


def test_no_event_trigger_ablation_does_not_enter_on_event_alone():
    high = TaskSpec("noevent", "high", 5, 50, Criticality.HIGH)
    result = Simulator(
        [], [EventRelease(high, 100)],
        SimulationConfig(
            duration=500,
            quantum=5,
            policy=PolicyName.RT_DASH_NO_EVENT_TRIGGER,
            utilization_high=0.95,
            utilization_low=0.50,
            monitor_interval=50,
        ),
    ).run()
    assert not result.transitions


def test_no_load_trigger_ablation_stays_normal_without_high_event():
    task = TaskSpec("over", "overload", 9, 10, Criticality.MEDIUM, period=10)
    result = Simulator(
        [task], [],
        SimulationConfig(
            duration=1000,
            quantum=1,
            policy=PolicyName.RT_DASH_NO_LOAD_TRIGGER,
            observation_window=100,
            monitor_interval=10,
            smoothing_samples=1,
            utilization_high=0.5,
            utilization_low=0.3,
            entry_hold=0,
        ),
    ).run()
    assert not any(t.new_mode.value == "critical" for t in result.transitions)


def test_transition_latency_and_queue_metrics_are_reported():
    high = TaskSpec("latency", "high", 25, 100, Criticality.HIGH)
    result = Simulator(
        [], [EventRelease(high, 20)],
        SimulationConfig(duration=300, quantum=5, policy=PolicyName.RT_DASH),
    ).run()
    entry = next(t for t in result.transitions if t.new_mode.value == "critical")
    summary = summarize_result(result)
    assert entry.control_latency == 0
    assert summary["max_ready_queue"] >= 1
    assert summary["scheduling_decisions"] > 0
