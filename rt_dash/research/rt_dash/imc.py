from __future__ import annotations

"""Independent dual-criticality benchmark used for external comparison.

The runtime semantics follow the EDF-VD mixed-criticality model: high-
criticality tasks use shortened virtual deadlines in LO mode and a mode switch
is triggered when a high-criticality job executes beyond its LO budget.  Two
variants are exposed: the classical model, which drops low-criticality work in
HI mode, and the imprecise/degraded-quality variant, which preserves a declared
fraction of low-criticality execution.  The module is intentionally separate
from RT-DASH's smart-home event model so the external benchmark does not blur
semantic event triggers with execution-budget overruns.
"""

from dataclasses import dataclass
from enum import Enum
from math import ceil
from statistics import fmean
from typing import Iterable

import numpy as np


class MCPolicy(str, Enum):
    EDF = "edf"
    CRITICALITY_EDF = "criticality_edf"
    EDF_VD_DROP = "edf_vd_drop"
    EDF_VD_IMC = "edf_vd_imc"
    RT_DASH_MC = "rt_dash_mc"


class MCMode(str, Enum):
    LO = "lo"
    HI = "hi"


@dataclass(frozen=True, slots=True)
class MCTask:
    task_id: str
    period: int
    c_lo: int
    c_hi: int
    high: bool
    phase: int = 0

    def __post_init__(self) -> None:
        if self.period <= 0 or self.c_lo <= 0:
            raise ValueError("period and c_lo must be positive")
        if self.high and self.c_hi < self.c_lo:
            raise ValueError("high-criticality tasks require c_hi >= c_lo")
        if not self.high and not (0 <= self.c_hi <= self.c_lo):
            raise ValueError("low-criticality tasks require 0 <= c_hi <= c_lo")
        if self.phase < 0 or self.phase >= self.period:
            raise ValueError("phase must be in [0, period)")


@dataclass(slots=True)
class MCJob:
    task: MCTask
    sequence: int
    release: int
    deadline: int
    actual_budget: int
    remaining: int
    executed: int = 0
    completion: int | None = None
    dropped: bool = False
    degraded: bool = False
    first_start: int | None = None

    @property
    def job_id(self) -> str:
        return f"{self.task.task_id}#{self.sequence}"


@dataclass(frozen=True, slots=True)
class MCBenchmarkConfig:
    duration: int = 20_000
    quantum: int = 1
    policy: MCPolicy = MCPolicy.EDF_VD_IMC
    overrun_probability: float = 0.2
    seed: int = 0


@dataclass(slots=True)
class MCBenchmarkResult:
    policy: MCPolicy
    jobs: list[MCJob]
    mode_switches: int
    virtual_deadline_factor: float
    lo_utilization: float
    hi_utilization: float
    busy_time: int
    duration: int


def utilization_components(tasks: Iterable[MCTask]) -> tuple[float, float, float, float]:
    u_lo_lo = sum(t.c_lo / t.period for t in tasks if not t.high)
    u_lo_hi = sum(t.c_hi / t.period for t in tasks if not t.high)
    u_hi_lo = sum(t.c_lo / t.period for t in tasks if t.high)
    u_hi_hi = sum(t.c_hi / t.period for t in tasks if t.high)
    return u_lo_lo, u_lo_hi, u_hi_lo, u_hi_hi


def virtual_deadline_factor(tasks: Iterable[MCTask]) -> float:
    u_lo_lo, _, u_hi_lo, _ = utilization_components(tasks)
    denominator = 1.0 - u_lo_lo
    if denominator <= 0:
        return 1.0
    return min(1.0, max(1e-6, u_hi_lo / denominator))


def generate_mc_taskset(
    task_count: int,
    total_lo_utilization: float,
    high_task_fraction: float,
    high_budget_factor: float,
    low_retention: float,
    seed: int,
) -> list[MCTask]:
    """Generate a valid implicit-deadline dual-criticality task set.

    Generation is repeated until the EDF-VD LO-mode virtual-deadline factor is
    below one. The task set is not claimed schedulable in HI mode; empirical
    miss ratios and utilization components are reported explicitly.
    """

    if task_count < 4:
        raise ValueError("task_count must be at least four")
    if not 0 < total_lo_utilization < 1.2:
        raise ValueError("invalid total_lo_utilization")
    if not 0 < high_task_fraction < 1:
        raise ValueError("invalid high_task_fraction")
    if high_budget_factor < 1 or not 0 <= low_retention <= 1:
        raise ValueError("invalid budget parameters")

    rng = np.random.default_rng(700_000 + seed)
    periods = np.array([50, 80, 100, 125, 160, 200, 250, 320, 400, 500])
    for attempt in range(500):
        remaining = total_lo_utilization
        utils: list[float] = []
        for index in range(1, task_count):
            nxt = remaining * float(rng.random()) ** (1.0 / (task_count - index))
            utils.append(remaining - nxt)
            remaining = nxt
        utils.append(remaining)
        high_count = max(1, min(task_count - 1, int(round(task_count * high_task_fraction))))
        high_indices = set(int(x) for x in rng.choice(task_count, size=high_count, replace=False))
        tasks: list[MCTask] = []
        for index, util in enumerate(utils):
            period = int(rng.choice(periods))
            c_lo = max(1, min(period - 1, int(round(util * period))))
            high = index in high_indices
            c_hi = (
                min(period, max(c_lo, int(ceil(c_lo * high_budget_factor))))
                if high
                else int(round(c_lo * low_retention))
            )
            tasks.append(
                MCTask(
                    task_id=f"mc_{seed}_{attempt}_{index}",
                    period=period,
                    c_lo=c_lo,
                    c_hi=c_hi,
                    high=high,
                    phase=int(rng.integers(0, period)),
                )
            )
        if virtual_deadline_factor(tasks) < 1.0:
            return tasks
    raise RuntimeError("could not generate an EDF-VD-compatible task set")


def _key(job: MCJob, policy: MCPolicy, mode: MCMode, x: float) -> tuple[float, int, str]:
    if policy is MCPolicy.CRITICALITY_EDF or (
        policy is MCPolicy.RT_DASH_MC and mode is MCMode.HI
    ):
        return (-int(job.task.high), job.deadline, job.job_id)
    if policy in (MCPolicy.EDF_VD_DROP, MCPolicy.EDF_VD_IMC) and mode is MCMode.LO:
        effective_deadline = (
            job.release + x * job.task.period if job.task.high else job.deadline
        )
        return (effective_deadline, -int(job.task.high), job.job_id)
    return (job.deadline, -int(job.task.high), job.job_id)


def run_mc_benchmark(tasks: list[MCTask], config: MCBenchmarkConfig) -> MCBenchmarkResult:
    rng = np.random.default_rng(800_000 + config.seed)
    x = virtual_deadline_factor(tasks)
    releases: dict[int, list[MCJob]] = {}
    sequence: dict[str, int] = {}
    for task in tasks:
        for release in range(task.phase, config.duration, task.period):
            seq = sequence.get(task.task_id, 0)
            sequence[task.task_id] = seq + 1
            if task.high:
                overrun = bool(rng.random() < config.overrun_probability)
                if overrun and task.c_hi > task.c_lo:
                    actual = int(rng.integers(task.c_lo + 1, task.c_hi + 1))
                else:
                    actual = int(rng.integers(max(1, int(ceil(0.7 * task.c_lo))), task.c_lo + 1))
            else:
                actual = task.c_lo
            job = MCJob(task, seq, release, release + task.period, actual, actual)
            releases.setdefault(release, []).append(job)

    jobs: list[MCJob] = []
    ready: list[MCJob] = []
    mode = MCMode.LO
    switches = 0
    busy = 0

    def switch_to_hi(now: int) -> None:
        nonlocal mode, switches
        if mode is MCMode.HI:
            return
        mode = MCMode.HI
        switches += 1
        for job in list(ready):
            if job.task.high:
                continue
            cap = 0 if config.policy is MCPolicy.EDF_VD_DROP else job.task.c_hi
            if job.executed >= cap:
                job.remaining = 0
                job.completion = now if cap > 0 else None
                job.dropped = cap == 0
                job.degraded = cap < job.actual_budget
                ready.remove(job)
            else:
                new_remaining = cap - job.executed
                if new_remaining < job.remaining:
                    job.remaining = new_remaining
                    job.degraded = True

    for now in range(0, config.duration, config.quantum):
        for job in releases.get(now, []):
            if mode is MCMode.HI and not job.task.high and config.policy in (
                MCPolicy.EDF_VD_DROP,
                MCPolicy.EDF_VD_IMC,
                MCPolicy.RT_DASH_MC,
            ):
                cap = 0 if config.policy is MCPolicy.EDF_VD_DROP else job.task.c_hi
                job.remaining = min(job.actual_budget, cap)
                job.degraded = cap < job.actual_budget
                if job.remaining == 0:
                    job.dropped = True
                    jobs.append(job)
                    continue
            ready.append(job)
            jobs.append(job)

        for job in list(ready):
            if now >= job.deadline and job.remaining > 0:
                job.dropped = True
                ready.remove(job)

        elapsed = 0
        while elapsed < config.quantum and ready:
            selected = min(ready, key=lambda j: _key(j, config.policy, mode, x))
            if selected.first_start is None:
                selected.first_start = now + elapsed
            available = config.quantum - elapsed
            # Stop exactly at a high task's LO budget to trigger mode switch
            # before assigning additional execution in the same quantum.
            until_overrun = available
            if (
                mode is MCMode.LO
                and selected.task.high
                and config.policy in (MCPolicy.EDF_VD_DROP, MCPolicy.EDF_VD_IMC, MCPolicy.RT_DASH_MC)
                and selected.actual_budget > selected.task.c_lo
                and selected.executed < selected.task.c_lo
            ):
                until_overrun = min(until_overrun, selected.task.c_lo - selected.executed)
            executed = min(available, selected.remaining, until_overrun)
            selected.remaining -= executed
            selected.executed += executed
            elapsed += executed
            busy += executed

            if selected.remaining == 0:
                selected.completion = now + elapsed
                ready.remove(selected)
            elif (
                mode is MCMode.LO
                and selected.task.high
                and selected.executed >= selected.task.c_lo
                and selected.remaining > 0
                and config.policy in (MCPolicy.EDF_VD_DROP, MCPolicy.EDF_VD_IMC, MCPolicy.RT_DASH_MC)
            ):
                switch_to_hi(now + elapsed)
            elif executed == 0:
                break

        # An idle instant is the documented safe return point used for this
        # finite simulation benchmark.
        if mode is MCMode.HI and not ready:
            mode = MCMode.LO
            switches += 1

    return MCBenchmarkResult(
        policy=config.policy,
        jobs=jobs,
        mode_switches=switches,
        virtual_deadline_factor=x,
        lo_utilization=sum(t.c_lo / t.period for t in tasks),
        hi_utilization=sum(t.c_hi / t.period for t in tasks),
        busy_time=busy,
        duration=config.duration,
    )


def summarize_mc(result: MCBenchmarkResult) -> dict[str, float | int | str]:
    high = [j for j in result.jobs if j.task.high]
    low = [j for j in result.jobs if not j.task.high]

    def summarize(items: list[MCJob]) -> dict[str, float | int]:
        assessed = [j for j in items if j.deadline <= result.duration]
        completed = [j for j in assessed if j.completion is not None and j.completion <= j.deadline]
        misses = [j for j in assessed if j not in completed]
        responses = [j.completion - j.release for j in completed if j.completion is not None]
        offered = sum(j.actual_budget for j in assessed)
        delivered = sum(j.executed for j in assessed)
        return {
            "released": len(assessed),
            "completion_rate": len(completed) / len(assessed) if assessed else float("nan"),
            "dmr": len(misses) / len(assessed) if assessed else float("nan"),
            "mean_response": fmean(responses) if responses else float("nan"),
            "service_fraction": delivered / offered if offered else float("nan"),
        }

    hs, ls = summarize(high), summarize(low)
    return {
        "policy": result.policy.value,
        "high_released": hs["released"],
        "high_completion_rate": hs["completion_rate"],
        "high_dmr": hs["dmr"],
        "high_mean_response": hs["mean_response"],
        "low_released": ls["released"],
        "low_completion_rate": ls["completion_rate"],
        "low_service_fraction": ls["service_fraction"],
        "mode_switches": result.mode_switches,
        "virtual_deadline_factor": result.virtual_deadline_factor,
        "lo_utilization": result.lo_utilization,
        "hi_utilization": result.hi_utilization,
        "processor_utilization": result.busy_time / result.duration,
    }
