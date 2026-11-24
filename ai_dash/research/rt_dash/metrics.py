from __future__ import annotations

from statistics import fmean, median, pstdev
from typing import Iterable

from .model import Criticality, Job, JobStatus
from .policies import Mode
from .simulator import SimulationResult


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _deadline_is_assessed(job: Job, horizon: int) -> bool:
    return job.completion_time is not None or job.absolute_deadline <= horizon


def _deadline_missed(job: Job, horizon: int) -> bool:
    if not _deadline_is_assessed(job, horizon):
        return False
    return job.completion_time is None or job.completion_time > job.absolute_deadline


def _executed_work(job: Job) -> int:
    return max(0, job.original_budget - job.remaining - job.service_reduction)


def _lateness(job: Job, horizon: int) -> float | None:
    if not _deadline_is_assessed(job, horizon):
        return None
    observed_finish = job.completion_time if job.completion_time is not None else horizon
    return float(observed_finish - job.absolute_deadline)


def summarize_jobs(
    jobs: Iterable[Job], horizon: int
) -> dict[str, float | int | None]:
    job_list = list(jobs)
    completed = [j for j in job_list if j.status is JobStatus.COMPLETED]
    dropped = [j for j in job_list if j.status is JobStatus.DROPPED]
    unfinished = [j for j in job_list if j.status not in (JobStatus.COMPLETED, JobStatus.DROPPED)]
    responses = [float(j.response_time) for j in completed if j.response_time is not None]
    waits = [float(j.first_start - j.release_time) for j in job_list if j.first_start is not None]
    assessed = [j for j in job_list if _deadline_is_assessed(j, horizon)]
    misses = [j for j in assessed if _deadline_missed(j, horizon)]
    lateness = [value for j in assessed if (value := _lateness(j, horizon)) is not None]
    tardiness = [max(0.0, value) for value in lateness]
    reductions = sum(j.service_reduction for j in job_list)
    offered_work = sum(j.original_budget for j in job_list)
    executed_work = sum(_executed_work(j) for j in job_list)
    degraded = [j for j in job_list if j.service_reduction > 0]
    fully_omitted = [j for j in job_list if j.service_reduction >= j.original_budget]
    never_started_assessed = [j for j in assessed if j.first_start is None]
    start_deadline_violations = [
        j for j in assessed
        if j.first_start is None or j.first_start > j.absolute_deadline
    ]
    response_per_second = len(completed) / (horizon / 1000.0) if horizon > 0 else None

    # Application utility is reported under three monotone utility shapes so
    # conclusions do not depend on assuming that execution fraction and user
    # value are identical. Concave utility models early service as especially
    # valuable; convex utility penalizes partial service more strongly.
    service_fractions = [
        (_executed_work(j) / j.original_budget) if j.original_budget else 0.0
        for j in job_list
    ]
    utility_shapes = {
        "concave": lambda x: x ** 0.5,
        "linear": lambda x: x,
        "convex": lambda x: x ** 2.0,
    }
    utility_metrics: dict[str, float | None] = {}
    total_weight = float(sum(j.original_budget for j in job_list))
    for label, transform in utility_shapes.items():
        values = [transform(max(0.0, min(1.0, x))) for x in service_fractions]
        utility_metrics[f"mean_service_utility_{label}"] = (
            fmean(values) if values else None
        )
        utility_metrics[f"work_weighted_utility_{label}"] = (
            sum(j.original_budget * transform(max(0.0, min(1.0, frac)))
                for j, frac in zip(job_list, service_fractions)) / total_weight
            if total_weight else None
        )

    by_task: dict[str, list[float]] = {}
    for job, fraction in zip(job_list, service_fractions):
        by_task.setdefault(job.task.task_id, []).append(fraction)
    task_service = [fmean(values) for values in by_task.values() if values]
    fairness_numerator = sum(task_service) ** 2
    fairness_denominator = len(task_service) * sum(value * value for value in task_service)
    service_fairness_jain = (
        fairness_numerator / fairness_denominator if fairness_denominator > 0 else None
    )

    return {
        "released": len(job_list),
        "completed": len(completed),
        "dropped": len(dropped),
        "unfinished": len(unfinished),
        "completion_rate": len(completed) / len(job_list) if job_list else None,
        "throughput_jobs_per_s": response_per_second,
        "deadline_assessed": len(assessed),
        "deadline_censored": len(job_list) - len(assessed),
        "deadline_misses": len(misses),
        "deadline_miss_ratio": len(misses) / len(assessed) if assessed else None,
        "mean_response": fmean(responses) if responses else None,
        "median_response": median(responses) if responses else None,
        "max_response": max(responses) if responses else None,
        "p95_response": _percentile(responses, 0.95),
        "p99_response": _percentile(responses, 0.99),
        "response_std": pstdev(responses) if len(responses) > 1 else 0.0 if responses else None,
        "mean_wait": fmean(waits) if waits else None,
        "median_wait": median(waits) if waits else None,
        "max_wait": max(waits) if waits else None,
        "p95_wait": _percentile(waits, 0.95),
        "p99_wait": _percentile(waits, 0.99),
        "mean_lateness": fmean(lateness) if lateness else None,
        "max_lateness": max(lateness) if lateness else None,
        "mean_tardiness": fmean(tardiness) if tardiness else None,
        "p95_tardiness": _percentile(tardiness, 0.95),
        "preemptions": sum(j.preemptions for j in job_list),
        "max_preemptions_per_job": max((j.preemptions for j in job_list), default=0),
        "service_reduction": reductions,
        "degraded_jobs": len(degraded),
        "fully_omitted_jobs": len(fully_omitted),
        "offered_work": offered_work,
        "executed_work": executed_work,
        "delivered_service_fraction": executed_work / offered_work if offered_work else None,
        "never_started_assessed": len(never_started_assessed),
        "start_deadline_violations": len(start_deadline_violations),
        "start_deadline_violation_rate": (
            len(start_deadline_violations) / len(assessed) if assessed else None
        ),
        "backlog_at_horizon": len(unfinished),
        "service_fairness_jain": service_fairness_jain,
        **utility_metrics,
    }


def summarize_result(result: SimulationResult) -> dict[str, object]:
    entry_latencies = [
        float(t.control_latency)
        for t in result.transitions
        if t.new_mode is Mode.CRITICAL
    ]
    recovery_latencies = [
        float(t.control_latency)
        for t in result.transitions
        if t.new_mode is Mode.NORMAL
    ]
    episode_durations = [float(value) for value in result.critical_episode_durations]
    recovery_clearance = [float(value) for value in result.recovery_clearance_times]

    output: dict[str, object] = {
        "policy": result.config.policy.value,
        "duration": result.config.duration,
        "processor_utilization": result.processor_utilization,
        "context_switches": result.context_switches,
        "mode_transitions": len(result.transitions),
        "critical_mode_fraction": result.critical_mode_time / result.config.duration,
        "service_reduction": result.service_reduction,
        "max_ready_queue": result.max_ready_queue,
        "max_low_ready_queue": result.max_low_ready_queue,
        "max_high_ready_queue": result.max_high_ready_queue,
        "average_ready_queue": result.average_ready_queue,
        "scheduling_decisions": result.scheduling_decisions,
        "period_stretched_intervals": result.period_stretched_intervals,
        "period_shrunk_intervals": result.period_shrunk_intervals,
        "entry_transition_count": len(entry_latencies),
        "entry_control_latency_mean": fmean(entry_latencies) if entry_latencies else None,
        "entry_control_latency_max": max(entry_latencies) if entry_latencies else None,
        "recovery_transition_count": len(recovery_latencies),
        "recovery_control_latency_mean": fmean(recovery_latencies) if recovery_latencies else None,
        "recovery_control_latency_max": max(recovery_latencies) if recovery_latencies else None,
        "critical_episode_mean": fmean(episode_durations) if episode_durations else None,
        "critical_episode_max": max(episode_durations) if episode_durations else None,
        "recovery_clearance_mean": fmean(recovery_clearance) if recovery_clearance else None,
        "recovery_clearance_max": max(recovery_clearance) if recovery_clearance else None,
        "recovery_censored_count": result.recovery_censored_count,
        "recovery_censored_age": result.recovery_censored_age,
    }
    output.update({f"overall_{k}": v for k, v in summarize_jobs(result.jobs, result.config.duration).items()})
    for criticality in Criticality:
        class_jobs = [j for j in result.jobs if j.task.criticality is criticality]
        output.update(
            {
                f"{criticality.name.lower()}_{k}": v
                for k, v in summarize_jobs(class_jobs, result.config.duration).items()
            }
        )
    return output


def job_records(result: SimulationResult) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for job in result.jobs:
        records.append(
            {
                "policy": result.config.policy.value,
                "job_id": job.job_id,
                "task_id": job.task.task_id,
                "task_name": job.task.name,
                "criticality": job.task.criticality.name.lower(),
                "release_time": job.release_time,
                "absolute_deadline": job.absolute_deadline,
                "relative_deadline": job.task.relative_deadline,
                "period": job.task.period,
                "original_budget": job.original_budget,
                "executed_work": _executed_work(job),
                "service_reduction": job.service_reduction,
                "delivered_service_fraction": (
                    _executed_work(job) / job.original_budget if job.original_budget else None
                ),
                "first_start": job.first_start,
                "waiting_time": (
                    job.first_start - job.release_time if job.first_start is not None else None
                ),
                "completion_time": job.completion_time,
                "response_time": job.response_time,
                "lateness": _lateness(job, result.config.duration),
                "deadline_assessed": _deadline_is_assessed(job, result.config.duration),
                "deadline_missed": _deadline_missed(job, result.config.duration),
                "start_after_deadline": (
                    job.first_start is None or job.first_start > job.absolute_deadline
                ) if _deadline_is_assessed(job, result.config.duration) else False,
                "preemptions": job.preemptions,
                "status": job.status.value,
                "source": job.task.source,
            }
        )
    return records
