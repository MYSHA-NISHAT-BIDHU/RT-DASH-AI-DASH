from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional


class Criticality(IntEnum):
    """Application consequence class; it is not an RTOS priority."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class JobStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    DROPPED = "dropped"


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """Immutable task parameters used to release jobs.

    Time values are expressed in integer simulation quanta (milliseconds by
    default). ``period`` is required for periodic workloads and is also the
    minimum inter-arrival time used by RMS. One-shot event jobs may set it to
    ``None``.
    """

    task_id: str
    name: str
    wcet: int
    relative_deadline: int
    criticality: Criticality
    period: Optional[int] = None
    phase: int = 0
    degradable: bool = False
    min_service_fraction: float = 1.0
    memory: float = 0.0
    bandwidth: float = 0.0
    source: str = "synthetic"
    blocking_time: int = 0

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        if self.wcet <= 0:
            raise ValueError("wcet must be positive")
        if self.relative_deadline <= 0:
            raise ValueError("relative_deadline must be positive")
        if self.period is not None and self.period <= 0:
            raise ValueError("period must be positive when provided")
        if self.phase < 0:
            raise ValueError("phase cannot be negative")
        if not 0.0 <= self.min_service_fraction <= 1.0:
            raise ValueError("min_service_fraction must be in [0, 1]")
        if not self.degradable and self.min_service_fraction != 1.0:
            raise ValueError(
                "non-degradable tasks must use min_service_fraction=1.0"
            )
        if self.criticality is Criticality.HIGH and self.min_service_fraction < 1.0:
            raise ValueError("high-criticality tasks cannot be deliberately degraded")
        if self.memory < 0 or self.bandwidth < 0:
            raise ValueError("resource annotations cannot be negative")
        if self.blocking_time < 0 or self.blocking_time > self.wcet:
            raise ValueError("blocking_time must be in [0, wcet]")


@dataclass(slots=True)
class Job:
    """Runtime job state."""

    task: TaskSpec
    sequence: int
    release_time: int
    execution_budget: int
    absolute_deadline: int
    remaining: int = field(init=False)
    original_budget: int = field(init=False)
    status: JobStatus = JobStatus.PENDING
    first_start: Optional[int] = None
    completion_time: Optional[int] = None
    preemptions: int = 0
    service_reduction: int = 0
    last_dispatch_time: Optional[int] = None
    degradation_applied: bool = False
    nonpreemptive_remaining: int = field(init=False)

    def __post_init__(self) -> None:
        if self.execution_budget <= 0:
            raise ValueError("execution_budget must be positive")
        self.remaining = self.execution_budget
        self.original_budget = self.execution_budget
        self.nonpreemptive_remaining = min(
            self.execution_budget, self.task.blocking_time
        )

    @property
    def job_id(self) -> str:
        return f"{self.task.task_id}#{self.sequence}"

    @property
    def response_time(self) -> Optional[int]:
        if self.completion_time is None:
            return None
        return self.completion_time - self.release_time

    @property
    def deadline_missed(self) -> bool:
        return self.completion_time is None or self.completion_time > self.absolute_deadline

    def optional_remaining(self) -> int:
        """Return remaining work that may be omitted without crossing the service floor."""

        if not self.task.degradable:
            return 0
        mandatory_total = int(round(self.original_budget * self.task.min_service_fraction))
        executed = self.original_budget - self.remaining - self.service_reduction
        mandatory_remaining = max(0, mandatory_total - executed)
        return max(0, self.remaining - mandatory_remaining)

    def reduce_optional(self, maximum: int) -> int:
        """Omit up to ``maximum`` optional execution units.

        Repeated calls are permitted until the task's declared minimum service
        floor is reached. Mandatory work and already executed work are never
        removed.
        """

        if maximum <= 0:
            return 0
        removable = self.optional_remaining()
        removed = min(removable, maximum)
        if removed > 0:
            self.remaining -= removed
            self.service_reduction += removed
            self.degradation_applied = True
            self.nonpreemptive_remaining = min(
                self.nonpreemptive_remaining, self.remaining
            )
        return removed

    def apply_service_floor(self) -> int:
        """Remove all currently optional remaining work."""

        return self.reduce_optional(self.optional_remaining())
