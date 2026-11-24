from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from .model import Criticality, Job


class PolicyName(str, Enum):
    EDF = "edf"
    RMS = "rms"
    CRITICALITY_EDF = "criticality_edf"
    RT_DASH = "rt_dash"
    RT_DASH_NO_HYSTERESIS = "rt_dash_no_hysteresis"
    RT_DASH_NO_DEGRADATION = "rt_dash_no_degradation"
    RT_DASH_NO_EVENT_TRIGGER = "rt_dash_no_event_trigger"
    RT_DASH_NO_LOAD_TRIGGER = "rt_dash_no_load_trigger"
    RT_DASH_NO_RECOVERY_HOLD = "rt_dash_no_recovery_hold"
    RT_DASH_RECOVERY_EDF = "rt_dash_recovery_edf"
    RT_DASH_AI_ONLY = "rt_dash_ai_only"
    RT_DASH_AI_SAFE = "rt_dash_ai_safe"
    RT_DASH_AI_SAFE_RECOVERY_EDF = "rt_dash_ai_safe_recovery_edf"
    RT_DASH_PERIOD_RECOVERY_EDF = "rt_dash_period_recovery_edf"
    RT_DASH_PERIOD_SERVICE_RECOVERY_EDF = "rt_dash_period_service_recovery_edf"


class Mode(str, Enum):
    NORMAL = "normal"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class PolicyOptions:
    name: PolicyName
    degradation_enabled: bool = True
    hysteresis_enabled: bool = True
    event_trigger_enabled: bool = True
    load_trigger_enabled: bool = True
    recovery_hold_enabled: bool = True
    predictive_trigger_enabled: bool = False
    period_adaptation_enabled: bool = False


_ADAPTIVE = {
    PolicyName.RT_DASH,
    PolicyName.RT_DASH_NO_HYSTERESIS,
    PolicyName.RT_DASH_NO_DEGRADATION,
    PolicyName.RT_DASH_NO_EVENT_TRIGGER,
    PolicyName.RT_DASH_NO_LOAD_TRIGGER,
    PolicyName.RT_DASH_NO_RECOVERY_HOLD,
    PolicyName.RT_DASH_RECOVERY_EDF,
    PolicyName.RT_DASH_AI_ONLY,
    PolicyName.RT_DASH_AI_SAFE,
    PolicyName.RT_DASH_AI_SAFE_RECOVERY_EDF,
    PolicyName.RT_DASH_PERIOD_RECOVERY_EDF,
    PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF,
}


def is_adaptive(name: PolicyName) -> bool:
    return name in _ADAPTIVE


def options_for(name: PolicyName) -> PolicyOptions:
    if name is PolicyName.RT_DASH_NO_HYSTERESIS:
        return PolicyOptions(
            name=name,
            degradation_enabled=True,
            hysteresis_enabled=False,
            event_trigger_enabled=True,
            load_trigger_enabled=True,
            recovery_hold_enabled=False,
        )
    if name is PolicyName.RT_DASH_NO_DEGRADATION:
        return PolicyOptions(name=name, degradation_enabled=False)
    if name is PolicyName.RT_DASH_NO_EVENT_TRIGGER:
        return PolicyOptions(name=name, event_trigger_enabled=False)
    if name is PolicyName.RT_DASH_NO_LOAD_TRIGGER:
        return PolicyOptions(name=name, load_trigger_enabled=False)
    if name is PolicyName.RT_DASH_NO_RECOVERY_HOLD:
        return PolicyOptions(name=name, recovery_hold_enabled=False)
    if name is PolicyName.RT_DASH_AI_ONLY:
        return PolicyOptions(
            name=name,
            event_trigger_enabled=False,
            predictive_trigger_enabled=True,
        )
    if name in (
        PolicyName.RT_DASH_AI_SAFE,
        PolicyName.RT_DASH_AI_SAFE_RECOVERY_EDF,
    ):
        return PolicyOptions(name=name, predictive_trigger_enabled=True)
    if name is PolicyName.RT_DASH_PERIOD_RECOVERY_EDF:
        return PolicyOptions(
            name=name,
            degradation_enabled=False,
            period_adaptation_enabled=True,
        )
    if name is PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF:
        return PolicyOptions(name=name, period_adaptation_enabled=True)
    if name in (PolicyName.RT_DASH, PolicyName.RT_DASH_RECOVERY_EDF):
        return PolicyOptions(name=name)
    return PolicyOptions(
        name=name,
        degradation_enabled=False,
        hysteresis_enabled=False,
        event_trigger_enabled=False,
        load_trigger_enabled=False,
        recovery_hold_enabled=False,
    )


def _edf_key(job: Job) -> tuple[int, int, int, str]:
    return (
        job.absolute_deadline,
        -int(job.task.criticality),
        job.release_time,
        job.job_id,
    )


def _rms_key(job: Job) -> tuple[int, int, int, str]:
    # One-shot jobs have no natural RMS period. Their relative deadline is used
    # as a deterministic effective period and is reported as a baseline choice.
    effective_period = job.task.period or job.task.relative_deadline
    return (
        effective_period,
        -int(job.task.criticality),
        job.absolute_deadline,
        job.job_id,
    )


def _critical_key(job: Job) -> tuple[int, int, int, str]:
    return (
        -int(job.task.criticality),
        job.absolute_deadline,
        job.release_time,
        job.job_id,
    )


def select_job(
    ready_jobs: Iterable[Job], policy: PolicyName, mode: Mode
) -> Optional[Job]:
    jobs = list(ready_jobs)
    if not jobs:
        return None
    if policy is PolicyName.EDF:
        return min(jobs, key=_edf_key)
    if policy is PolicyName.RMS:
        return min(jobs, key=_rms_key)
    if policy is PolicyName.CRITICALITY_EDF:
        return min(jobs, key=_critical_key)
    if mode is Mode.CRITICAL:
        # Recovery-aware RT-DASH retains the mode guard and hysteresis, but
        # once no high-criticality job remains it dispatches the recovery
        # backlog by EDF. A newly released high-criticality job immediately
        # regains precedence on the next scheduling decision.
        if (
            policy in (
                PolicyName.RT_DASH_RECOVERY_EDF,
                PolicyName.RT_DASH_AI_SAFE_RECOVERY_EDF,
                PolicyName.RT_DASH_PERIOD_RECOVERY_EDF,
                PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF,
            )
            and not any(j.task.criticality is Criticality.HIGH for j in jobs)
        ):
            return min(jobs, key=_edf_key)
        return min(jobs, key=_critical_key)
    return min(jobs, key=_edf_key)


def high_criticality_pending(jobs: Iterable[Job]) -> bool:
    return any(j.task.criticality is Criticality.HIGH and j.remaining > 0 for j in jobs)
