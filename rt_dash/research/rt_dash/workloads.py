from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .model import Criticality, TaskSpec
from .simulator import EventRelease


BASE_PERIODIC_TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("temperature", "Temperature sampling", 12, 100, Criticality.MEDIUM, period=100, memory=8, bandwidth=1),
    TaskSpec("motion", "Motion sensing", 8, 80, Criticality.MEDIUM, period=80, memory=6, bandwidth=1),
    TaskSpec("energy", "Energy monitoring", 18, 250, Criticality.MEDIUM, period=250, memory=10, bandwidth=2),
    TaskSpec("lighting", "Lighting control", 15, 60, Criticality.LOW, period=120, degradable=True, min_service_fraction=0.5, memory=5, bandwidth=1),
    TaskSpec("display", "Status display", 20, 50, Criticality.LOW, period=100, degradable=True, min_service_fraction=0.25, memory=8, bandwidth=1),
    TaskSpec("comfort", "Comfort optimization", 30, 150, Criticality.LOW, period=200, degradable=True, min_service_fraction=0.4, memory=12, bandwidth=2),
)


def nominal_utilization(tasks: Sequence[TaskSpec]) -> float:
    total = 0.0
    for task in tasks:
        if task.period is None:
            continue
        total += task.wcet / task.period
    return total


def scaled_periodic_taskset(target_utilization: float, seed: int) -> list[TaskSpec]:
    """Create a deterministic workload with a requested nominal utilization.

    Periods and deadlines remain fixed. Execution budgets are scaled together
    and then perturbed by a small seeded factor so repeated seeds represent
    distinct, but controlled, task sets.
    """

    if target_utilization <= 0:
        raise ValueError("target_utilization must be positive")
    rng = np.random.default_rng(seed)
    base_u = nominal_utilization(BASE_PERIODIC_TASKS)
    factor = target_utilization / base_u
    tasks: list[TaskSpec] = []
    provisional: list[tuple[TaskSpec, int]] = []
    for task in BASE_PERIODIC_TASKS:
        perturbation = float(rng.uniform(0.92, 1.08))
        wcet = max(1, int(round(task.wcet * factor * perturbation)))
        provisional.append((task, wcet))
    current_u = sum(w / t.period for t, w in provisional if t.period)
    correction = target_utilization / current_u
    for task, wcet in provisional:
        adjusted = max(1, int(round(wcet * correction)))
        tasks.append(replace(task, wcet=adjusted, source=f"controlled_seed_{seed}"))
    return tasks


def emergency_releases(seed: int, times: Sequence[int] = (15_000, 40_000)) -> list[EventRelease]:
    rng = np.random.default_rng(seed + 10_000)
    events: list[EventRelease] = []
    templates = (
        ("fire", "Fire alarm response", 90, 180),
        ("intrusion", "Intrusion response", 75, 160),
        ("gas", "Gas-leak response", 100, 200),
    )
    for event_index, release in enumerate(times):
        # Inject a small burst of two or three safety jobs to create a realistic
        # transient rather than a single isolated dispatch.
        count = 2 + int(rng.integers(0, 2))
        for offset_index in range(count):
            name, label, wcet, deadline = templates[(event_index + offset_index) % len(templates)]
            task = TaskSpec(
                task_id=f"{name}_{event_index}_{offset_index}",
                name=label,
                wcet=wcet,
                relative_deadline=deadline,
                criticality=Criticality.HIGH,
                period=None,
                phase=0,
                degradable=False,
                min_service_fraction=1.0,
                memory=20,
                bandwidth=8,
                source=f"emergency_seed_{seed}",
            )
            events.append(EventRelease(task, release + 10 * offset_index))
    return events


ACTIVITY_TEMPLATE = {
    "sleep": ("sleep", Criticality.LOW, 20, 500, True, 0.25),
    "leisure": ("leisure", Criticality.LOW, 30, 300, True, 0.4),
    "other": ("other", Criticality.LOW, 25, 300, True, 0.4),
    "eat": ("eat", Criticality.MEDIUM, 40, 250, False, 1.0),
    "work": ("work", Criticality.MEDIUM, 55, 220, False, 1.0),
    "personal": ("personal", Criticality.MEDIUM, 35, 250, False, 1.0),
    "anomaly": ("anomaly", Criticality.HIGH, 60, 180, False, 1.0),
    "unknown": ("unknown", Criticality.LOW, 15, 500, True, 0.2),
}

NUMERIC_ACTIVITY_LABELS = {
    0: "sleep",
    1: "eat",
    2: "work",
    3: "personal",
    4: "other",
    5: "anomaly",
}


def _activity_label(value: object) -> str:
    if pd.isna(value):
        return "unknown"
    if isinstance(value, str):
        label = value.strip().lower()
        return label if label in ACTIVITY_TEMPLATE else "unknown"
    try:
        return NUMERIC_ACTIVITY_LABELS.get(int(value), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def trace_window_events(
    csv_path: str | Path,
    start_row: int,
    rows: int,
    time_scale: int = 100,
    load_scale: float = 1.0,
    deadline_scale: float = 1.0,
    mapping_label: str = "nominal",
) -> list[EventRelease]:
    """Map a contiguous smart-home trace window into explicit job releases.

    The mapper accepts either the original OpenSHS-style CSV (string activity
    labels and no synthetic resource columns) or the thesis-derived processed
    file. One activity job is released per observed row. Additional
    medium-criticality jobs are emitted for device state changes. Timestamp
    differences are preserved and compressed by ``time_scale`` milliseconds
    per source second.

    This is a new, machine-readable mapping introduced to complete the project;
    the thesis did not preserve an equivalent trace-to-task specification.
    """

    if start_row < 0 or rows <= 0 or time_scale <= 0 or load_scale <= 0 or deadline_scale <= 0:
        raise ValueError("invalid trace-window parameters")
    frame = pd.read_csv(csv_path, skiprows=range(1, start_row + 1), nrows=rows)
    if frame.empty:
        raise ValueError("selected trace window is empty")
    if "Activity" not in frame.columns:
        raise ValueError("trace is missing Activity column")

    excluded = {"timestamp", "Activity", "Priority", "CPU", "Memory", "Storage", "Bandwidth"}
    sensor_columns = [c for c in frame.columns if c not in excluded]

    if "timestamp" in frame.columns:
        timestamp = pd.to_datetime(
            frame["timestamp"].astype(str).str.replace("_", ":", regex=False),
            errors="coerce",
        )
        if timestamp.notna().all():
            relative_seconds = (timestamp - timestamp.iloc[0]).dt.total_seconds().astype(int)
        else:
            relative_seconds = pd.Series(np.arange(len(frame)), index=frame.index)
    else:
        relative_seconds = pd.Series(np.arange(len(frame)), index=frame.index)

    events: list[EventRelease] = []
    previous = None
    for position, (_, row) in enumerate(frame.iterrows()):
        label = _activity_label(row["Activity"])
        normalized_label, criticality, base_wcet, deadline, degradable, floor = ACTIVITY_TEMPLATE[label]
        cpu_factor = 1.0
        if "CPU" in frame.columns and not pd.isna(row.get("CPU")):
            # Synthetic CPU annotations are used only as a relative stress
            # multiplier and are never reported as measured processor time.
            cpu_factor = max(0.25, float(row["CPU"]) / 50.0)
        wcet = max(1, int(round(base_wcet * cpu_factor * load_scale)))
        release = int(relative_seconds.iloc[position]) * time_scale
        task = TaskSpec(
            task_id=f"trace_activity_{start_row + position}",
            name=f"Trace activity: {normalized_label}",
            wcet=wcet,
            relative_deadline=max(1, int(round(deadline * deadline_scale))),
            criticality=criticality,
            degradable=degradable,
            min_service_fraction=floor,
            memory=float(row.get("Memory", 0.0) or 0.0),
            bandwidth=float(row.get("Bandwidth", 0.0) or 0.0),
            source=f"trace_rows_{start_row}_{start_row + rows - 1}_{mapping_label}",
        )
        events.append(EventRelease(task, release))

        current = row[sensor_columns].to_numpy(dtype=float) if sensor_columns else np.array([])
        if previous is not None and len(current):
            changed = np.flatnonzero(np.abs(current - previous) > 0.5)
            for change_index in changed[:6]:
                sensor = sensor_columns[int(change_index)]
                sensor_task = TaskSpec(
                    task_id=f"trace_sensor_{start_row + position}_{sensor}",
                    name=f"Sensor transition: {sensor}",
                    wcet=max(1, int(round(12 * load_scale))),
                    relative_deadline=max(1, int(round(200 * deadline_scale))),
                    criticality=Criticality.MEDIUM,
                    degradable=False,
                    min_service_fraction=1.0,
                    memory=4,
                    bandwidth=1,
                    source=f"trace_rows_{start_row}_{start_row + rows - 1}_{mapping_label}",
                )
                events.append(EventRelease(sensor_task, release))
        previous = current
    return events


def emergency_profile_releases(
    seed: int,
    severity: str,
    times: Sequence[int] = (15_000, 40_000),
) -> list[EventRelease]:
    """Create controlled emergency bursts with graded difficulty.

    The three profiles intentionally span mild, moderate and severe demand so
    baseline performance does not collapse to a single ceiling value.
    """

    rng = np.random.default_rng(200_000 + seed)
    profiles = {
        "mild": {"count": (1, 2), "wcet": (45, 70), "deadline": (260, 380), "spacing": 20},
        "moderate": {"count": (2, 3), "wcet": (60, 90), "deadline": (220, 320), "spacing": 20},
        "severe": {"count": (3, 4), "wcet": (80, 115), "deadline": (170, 240), "spacing": 10},
    }
    if severity not in profiles:
        raise ValueError(f"unknown emergency severity: {severity}")
    profile = profiles[severity]
    events: list[EventRelease] = []
    for burst_index, release in enumerate(times):
        count = int(rng.integers(profile["count"][0], profile["count"][1] + 1))
        for index in range(count):
            wcet = int(rng.integers(profile["wcet"][0], profile["wcet"][1] + 1))
            deadline = int(rng.integers(profile["deadline"][0], profile["deadline"][1] + 1))
            task = TaskSpec(
                task_id=f"{severity}_emergency_{burst_index}_{index}",
                name=f"{severity.title()} safety-event response",
                wcet=wcet,
                relative_deadline=deadline,
                criticality=Criticality.HIGH,
                period=None,
                degradable=False,
                min_service_fraction=1.0,
                memory=20,
                bandwidth=8,
                source=f"controlled_{severity}_emergency_seed_{seed}",
            )
            events.append(EventRelease(task, release + index * int(profile["spacing"])))
    return events


def scalable_taskset(
    task_count: int,
    target_utilization: float,
    seed: int,
) -> list[TaskSpec]:
    """Generate a deterministic UUniFast-like periodic task set.

    The generator is used only for scalability analysis. Criticality and
    degradability are assigned independently of utilization, while total
    nominal utilization is kept close to the requested value.
    """

    if task_count < 2:
        raise ValueError("task_count must be at least 2")
    if target_utilization <= 0:
        raise ValueError("target_utilization must be positive")
    rng = np.random.default_rng(300_000 + seed + task_count)
    utilizations: list[float] = []
    remaining = float(target_utilization)
    for i in range(1, task_count):
        next_remaining = remaining * float(rng.random()) ** (1.0 / (task_count - i))
        utilizations.append(remaining - next_remaining)
        remaining = next_remaining
    utilizations.append(remaining)

    period_choices = np.array([50, 80, 100, 120, 160, 200, 250, 320, 400, 500])
    tasks: list[TaskSpec] = []
    for index, utilization in enumerate(utilizations):
        period = int(rng.choice(period_choices))
        wcet = max(1, int(round(utilization * period)))
        deadline_factor = float(rng.uniform(0.75, 1.0))
        deadline = max(wcet, int(round(period * deadline_factor)))
        draw = float(rng.random())
        if draw < 0.15:
            criticality = Criticality.HIGH
        elif draw < 0.50:
            criticality = Criticality.MEDIUM
        else:
            criticality = Criticality.LOW
        degradable = criticality is Criticality.LOW and bool(rng.random() < 0.75)
        floor = float(rng.choice([0.25, 0.4, 0.5, 0.75])) if degradable else 1.0
        tasks.append(
            TaskSpec(
                task_id=f"scale_{task_count}_{index}",
                name=f"Scalability task {index}",
                wcet=wcet,
                relative_deadline=deadline,
                criticality=criticality,
                period=period,
                phase=int(rng.integers(0, period)),
                degradable=degradable,
                min_service_fraction=floor,
                memory=float(rng.integers(1, 16)),
                bandwidth=float(rng.integers(0, 5)),
                source=f"scalability_n{task_count}_seed{seed}",
            )
        )
    return tasks
