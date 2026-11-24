from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import fmean
from typing import Sequence

from .model import Criticality, Job, JobStatus, TaskSpec
from .policies import (
    Mode,
    PolicyName,
    high_criticality_pending,
    is_adaptive,
    options_for,
    select_job,
)


@dataclass(frozen=True, slots=True)
class EventRelease:
    task: TaskSpec
    release_time: int
    execution_budget: int | None = None


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    duration: int = 60_000
    quantum: int = 1
    policy: PolicyName = PolicyName.RT_DASH
    observation_window: int = 1_000
    smoothing_samples: int = 5
    monitor_interval: int = 100
    utilization_high: float = 0.85
    utilization_low: float = 0.65
    entry_hold: int = 200
    recovery_hold: int = 1_000
    drop_expired_jobs: bool = False

    def __post_init__(self) -> None:
        if self.duration <= 0 or self.quantum <= 0:
            raise ValueError("duration and quantum must be positive")
        if self.duration % self.quantum:
            raise ValueError("duration must be divisible by quantum")
        if self.observation_window % self.quantum or self.monitor_interval % self.quantum:
            raise ValueError("observation and monitor intervals must be divisible by quantum")
        if self.observation_window <= 0 or self.monitor_interval <= 0:
            raise ValueError("monitoring intervals must be positive")
        if self.smoothing_samples <= 0:
            raise ValueError("smoothing_samples must be positive")
        if not 0 <= self.utilization_low < self.utilization_high <= 1:
            raise ValueError("require 0 <= utilization_low < utilization_high <= 1")
        if self.entry_hold < 0 or self.recovery_hold < 0:
            raise ValueError("hold intervals cannot be negative")


@dataclass(slots=True)
class ModeTransition:
    time: int
    old_mode: Mode
    new_mode: Mode
    reason: str
    smoothed_utilization: float
    guard_onset_time: int
    control_latency: int


@dataclass(slots=True)
class SimulationResult:
    config: SimulationConfig
    jobs: list[Job]
    transitions: list[ModeTransition]
    busy_time: int
    context_switches: int
    service_reduction: int
    critical_mode_time: int
    utilization_trace: list[tuple[int, float, float]] = field(default_factory=list)
    max_ready_queue: int = 0
    max_low_ready_queue: int = 0
    max_high_ready_queue: int = 0
    ready_queue_area: int = 0
    scheduling_decisions: int = 0
    recovery_clearance_times: list[int] = field(default_factory=list)
    recovery_censored_count: int = 0
    recovery_censored_age: int = 0
    critical_episode_durations: list[int] = field(default_factory=list)

    @property
    def processor_utilization(self) -> float:
        return self.busy_time / self.config.duration

    @property
    def average_ready_queue(self) -> float:
        return self.ready_queue_area / self.config.duration


class Simulator:
    """Deterministic, preemptive, single-core discrete-time reference model.

    Releases and control decisions occur at quantum boundaries. Within each
    quantum the dispatcher is work conserving: if a job finishes early, the
    residual portion of that quantum is immediately offered to the next ready
    job. This avoids the artificial idle time created by coarse time steps.
    """

    def __init__(
        self,
        periodic_tasks: Sequence[TaskSpec],
        event_releases: Sequence[EventRelease],
        config: SimulationConfig,
    ) -> None:
        self.periodic_tasks = tuple(periodic_tasks)
        self.event_releases = tuple(sorted(event_releases, key=lambda e: e.release_time))
        self.config = config
        self.options = options_for(config.policy)
        self.base_periodic_utilization = sum(
            task.wcet / task.period
            for task in self.periodic_tasks
            if task.period is not None
        )

    def _build_release_table(self) -> dict[int, list[Job]]:
        table: dict[int, list[Job]] = {}
        counters: dict[str, int] = {}

        def add(task: TaskSpec, release: int, budget: int | None = None) -> None:
            seq = counters.get(task.task_id, 0)
            counters[task.task_id] = seq + 1
            execution = budget if budget is not None else task.wcet
            job = Job(
                task=task,
                sequence=seq,
                release_time=release,
                execution_budget=execution,
                absolute_deadline=release + task.relative_deadline,
            )
            table.setdefault(release, []).append(job)

        for task in self.periodic_tasks:
            if task.period is None:
                raise ValueError(f"periodic task {task.task_id} has no period")
            for release in range(task.phase, self.config.duration, task.period):
                add(task, release)
        for event in self.event_releases:
            if 0 <= event.release_time < self.config.duration:
                if event.release_time % self.config.quantum:
                    raise ValueError(
                        f"event release {event.release_time} is not aligned to quantum {self.config.quantum}"
                    )
                add(event.task, event.release_time, event.execution_budget)
        return table

    def _apply_controlled_degradation(self, ready: list[Job], now: int) -> int:
        """Omit declared optional low-criticality work only under predicted overload."""

        horizon = self.config.observation_window
        capacity = self.config.utilization_high * horizon
        estimated_demand = sum(
            job.remaining
            for job in ready
            if job.absolute_deadline <= now + horizon
        )
        excess = max(0.0, estimated_demand - capacity)
        if excess <= 0:
            return 0

        candidates = [
            job
            for job in ready
            if job.task.criticality is Criticality.LOW
            and job.task.degradable
            and job.optional_remaining() > 0
        ]
        candidates.sort(
            key=lambda job: (
                job.task.min_service_fraction,
                -job.absolute_deadline,
                job.job_id,
            )
        )

        removed_total = 0
        for job in candidates:
            required = int(max(0.0, excess - removed_total) + 0.999999)
            removed_total += job.reduce_optional(required)
            if removed_total >= excess:
                break
        return removed_total

    def run(self) -> SimulationResult:
        releases = self._build_release_table()
        ready: list[Job] = []
        all_jobs: list[Job] = []
        transitions: list[ModeTransition] = []
        window_quanta = self.config.observation_window // self.config.quantum
        # A full zero-filled startup window prevents an unrealistically high
        # utilization estimate during the first few quanta.
        busy_history: deque[float] = deque([0.0] * window_quanta, maxlen=window_quanta)
        utilization_samples: deque[float] = deque(maxlen=self.config.smoothing_samples)
        utilization_trace: list[tuple[int, float, float]] = []

        mode = Mode.NORMAL
        mode_enter_time: int | None = None
        running: Job | None = None
        last_running_id: str | None = None
        context_switches = 0
        busy_time = 0
        service_reduction = 0
        critical_mode_time = 0
        high_load_since: int | None = None
        recovery_since: int | None = None
        smoothed_utilization = 0.0

        max_ready_queue = 0
        max_low_ready_queue = 0
        max_high_ready_queue = 0
        ready_queue_area = 0
        scheduling_decisions = 0
        recovery_start: int | None = None
        recovery_clearance_times: list[int] = []
        critical_episode_durations: list[int] = []

        def transition(
            now: int,
            new_mode: Mode,
            reason: str,
            guard_onset: int,
        ) -> None:
            nonlocal mode, mode_enter_time, recovery_start
            old = mode
            if old is new_mode:
                return
            transitions.append(
                ModeTransition(
                    time=now,
                    old_mode=old,
                    new_mode=new_mode,
                    reason=reason,
                    smoothed_utilization=smoothed_utilization,
                    guard_onset_time=guard_onset,
                    control_latency=max(0, now - guard_onset),
                )
            )
            mode = new_mode
            if new_mode is Mode.CRITICAL:
                mode_enter_time = now
                recovery_start = None
            else:
                if mode_enter_time is not None:
                    critical_episode_durations.append(max(0, now - mode_enter_time))
                mode_enter_time = None
                if any(j.task.criticality is Criticality.LOW and j.remaining > 0 for j in ready):
                    recovery_start = now

        for now in range(0, self.config.duration, self.config.quantum):
            newly_released = releases.get(now, [])
            for job in newly_released:
                job.status = JobStatus.READY
                ready.append(job)
                all_jobs.append(job)

            if (
                mode is Mode.NORMAL
                and is_adaptive(self.config.policy)
                and self.options.event_trigger_enabled
                and any(job.task.criticality is Criticality.HIGH for job in newly_released)
            ):
                transition(now, Mode.CRITICAL, "high-criticality arrival", now)
                high_load_since = None
                recovery_since = None

            if self.config.drop_expired_jobs:
                expired = [
                    job for job in ready
                    if job.remaining > 0 and now >= job.absolute_deadline
                ]
                for job in expired:
                    job.status = JobStatus.DROPPED
                if running in expired:
                    running = None
                ready = [j for j in ready if j.status is not JobStatus.DROPPED]

            if now % self.config.monitor_interval == 0:
                observed = sum(busy_history) / len(busy_history)
                utilization_samples.append(observed)
                smoothed_utilization = fmean(utilization_samples)
                utilization_trace.append((now, observed, smoothed_utilization))

                pending_high = high_criticality_pending(ready)
                if is_adaptive(self.config.policy):
                    if mode is Mode.NORMAL:
                        if self.options.event_trigger_enabled and pending_high:
                            transition(now, Mode.CRITICAL, "high-criticality pending", now)
                            high_load_since = None
                            recovery_since = None
                        elif (
                            self.options.load_trigger_enabled
                            and smoothed_utilization >= self.config.utilization_high
                        ):
                            if high_load_since is None:
                                high_load_since = now
                            required = (
                                self.config.entry_hold
                                if self.options.hysteresis_enabled
                                else 0
                            )
                            if now - high_load_since >= required:
                                transition(
                                    now,
                                    Mode.CRITICAL,
                                    "sustained high utilization",
                                    high_load_since,
                                )
                                high_load_since = None
                                recovery_since = None
                        else:
                            high_load_since = None
                    else:
                        # High-criticality work always prevents recovery, even in
                        # the no-event-trigger ablation. That ablation removes the
                        # entry signal, not the safety condition for leaving mode C.
                        if pending_high:
                            recovery_since = None
                        else:
                            exit_threshold = (
                                self.config.utilization_low
                                if self.options.hysteresis_enabled
                                else self.config.utilization_high
                            )
                            if smoothed_utilization <= exit_threshold:
                                if recovery_since is None:
                                    recovery_since = now
                                required = (
                                    self.config.recovery_hold
                                    if self.options.hysteresis_enabled
                                    and self.options.recovery_hold_enabled
                                    else 0
                                )
                                if now - recovery_since >= required:
                                    transition(
                                        now,
                                        Mode.NORMAL,
                                        "recovery condition",
                                        recovery_since,
                                    )
                                    recovery_since = None
                            else:
                                recovery_since = None

            if mode is Mode.CRITICAL:
                critical_mode_time += self.config.quantum
                if self.options.degradation_enabled:
                    service_reduction += self._apply_controlled_degradation(ready, now)
                    completed_by_degradation = [j for j in ready if j.remaining == 0]
                    for job in completed_by_degradation:
                        job.status = JobStatus.COMPLETED
                        if job.first_start is None:
                            job.first_start = now
                        job.completion_time = now
                    ready = [j for j in ready if j.remaining > 0]
                    if running in completed_by_degradation:
                        running = None

            low_ready = sum(
                1 for job in ready
                if job.task.criticality is Criticality.LOW and job.remaining > 0
            )
            high_ready = sum(
                1 for job in ready
                if job.task.criticality is Criticality.HIGH and job.remaining > 0
            )
            max_ready_queue = max(max_ready_queue, len(ready))
            max_low_ready_queue = max(max_low_ready_queue, low_ready)
            max_high_ready_queue = max(max_high_ready_queue, high_ready)
            ready_queue_area += len(ready) * self.config.quantum

            if recovery_start is not None and low_ready == 0:
                recovery_clearance_times.append(now - recovery_start)
                recovery_start = None

            elapsed = 0
            busy_this_quantum = 0
            while elapsed < self.config.quantum:
                scheduling_decisions += 1
                selected = select_job(ready, self.config.policy, mode)
                if selected is None:
                    running = None
                    last_running_id = None
                    break

                if running is not None and running is not selected and running.remaining > 0:
                    running.preemptions += 1
                    running.status = JobStatus.READY
                running = selected
                running.status = JobStatus.RUNNING
                dispatch_time = now + elapsed
                if running.first_start is None:
                    running.first_start = dispatch_time
                if last_running_id != running.job_id:
                    context_switches += 1
                    running.last_dispatch_time = dispatch_time
                last_running_id = running.job_id

                available = self.config.quantum - elapsed
                executed = min(available, running.remaining)
                running.remaining -= executed
                busy_time += executed
                busy_this_quantum += executed
                elapsed += executed

                if running.remaining == 0:
                    running.status = JobStatus.COMPLETED
                    running.completion_time = now + elapsed
                    ready.remove(running)
                    running = None
                    # Continue dispatching within the remaining quantum.
                elif executed == 0:  # defensive; should be impossible
                    break

            busy_history.append(busy_this_quantum / self.config.quantum)

        recovery_censored_count = 0
        recovery_censored_age = 0
        if recovery_start is not None:
            recovery_censored_count = 1
            recovery_censored_age = self.config.duration - recovery_start
        if mode is Mode.CRITICAL and mode_enter_time is not None:
            critical_episode_durations.append(self.config.duration - mode_enter_time)

        return SimulationResult(
            config=self.config,
            jobs=all_jobs,
            transitions=transitions,
            busy_time=busy_time,
            context_switches=context_switches,
            service_reduction=service_reduction,
            critical_mode_time=critical_mode_time,
            utilization_trace=utilization_trace,
            max_ready_queue=max_ready_queue,
            max_low_ready_queue=max_low_ready_queue,
            max_high_ready_queue=max_high_ready_queue,
            ready_queue_area=ready_queue_area,
            scheduling_decisions=scheduling_decisions,
            recovery_clearance_times=recovery_clearance_times,
            recovery_censored_count=recovery_censored_count,
            recovery_censored_age=recovery_censored_age,
            critical_episode_durations=critical_episode_durations,
        )
