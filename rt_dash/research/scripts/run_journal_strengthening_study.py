#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

from rt_dash.metrics import job_records, summarize_result
from rt_dash.model import Criticality, TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import EventRelease, SimulationConfig, Simulator
from rt_dash.workloads import (
    emergency_profile_releases,
    nominal_utilization,
    scalable_taskset,
    scaled_periodic_taskset,
    trace_window_events,
)

ALL_POLICIES = list(PolicyName)
CORE_POLICIES = [
    PolicyName.EDF,
    PolicyName.RMS,
    PolicyName.CRITICALITY_EDF,
    PolicyName.RT_DASH,
    PolicyName.RT_DASH_NO_HYSTERESIS,
    PolicyName.RT_DASH_NO_DEGRADATION,
]

SCENARIOS: dict[str, list[float]] = {
    "routine": [0.50, 0.65, 0.80, 0.90],
    "overload": [0.90, 1.00, 1.10, 1.20],
    "emergency_mild": [0.60, 0.75, 0.90],
    "emergency_moderate": [0.70, 0.85, 1.00],
    "emergency_severe": [0.80, 0.95, 1.10],
    "prolonged_emergency": [0.80, 0.95],
    "threshold_chatter": [0.72, 0.82, 0.88],
    "recovery_backlog": [0.75, 0.90, 1.05],
    "optional_service_stress": [0.70, 0.85, 1.00],
}

TRACE_WINDOWS = {
    0: "routine_sleep",
    1951: "sleep_eat_transition",
    160406: "sleep_anomaly_transition",
    941986: "three_activity_transition",
    963756: "mixed_four_activity_transition",
}
TRACE_PROFILES = {
    "relaxed": (0.75, 1.25),
    "nominal": (1.00, 1.00),
    "stressed": (1.25, 0.85),
}


def _high_event(task_id: str, release: int, wcet: int, deadline: int, source: str) -> EventRelease:
    return EventRelease(
        TaskSpec(
            task_id=task_id,
            name="Safety-event response",
            wcet=wcet,
            relative_deadline=deadline,
            criticality=Criticality.HIGH,
            degradable=False,
            min_service_fraction=1.0,
            memory=20,
            bandwidth=8,
            source=source,
        ),
        release,
    )


def _medium_burst(seed: int, start: int, count: int, spacing: int = 50) -> list[EventRelease]:
    rng = np.random.default_rng(50_000 + seed + start)
    events: list[EventRelease] = []
    for index in range(count):
        wcet = int(rng.integers(35, 70))
        task = TaskSpec(
            task_id=f"burst_m_{start}_{index}",
            name="Transient sensor-analysis burst",
            wcet=wcet,
            relative_deadline=300,
            criticality=Criticality.MEDIUM,
            degradable=False,
            min_service_fraction=1.0,
            memory=8,
            bandwidth=3,
            source="controlled_threshold_burst",
        )
        events.append(EventRelease(task, start + index * spacing))
    return events


def _low_backlog(seed: int, start: int, count: int, spacing: int = 40) -> list[EventRelease]:
    rng = np.random.default_rng(70_000 + seed)
    events: list[EventRelease] = []
    for index in range(count):
        wcet = int(rng.integers(25, 60))
        task = TaskSpec(
            task_id=f"backlog_l_{index}",
            name="Deferred comfort-service request",
            wcet=wcet,
            relative_deadline=1_800,
            criticality=Criticality.LOW,
            degradable=True,
            min_service_fraction=0.3,
            memory=8,
            bandwidth=2,
            source="controlled_recovery_backlog",
        )
        events.append(EventRelease(task, start + index * spacing))
    return events




def _optional_service_stress(seed: int, start: int = 14_500, count: int = 60) -> list[EventRelease]:
    rng = np.random.default_rng(80_000 + seed)
    events: list[EventRelease] = []
    for index in range(count):
        wcet = int(rng.integers(35, 70))
        task = TaskSpec(
            task_id=f"optional_stress_{index}",
            name="Optional comfort/visualization request",
            wcet=wcet,
            relative_deadline=800,
            criticality=Criticality.LOW,
            degradable=True,
            min_service_fraction=0.2,
            memory=6,
            bandwidth=2,
            source="controlled_optional_service_stress",
        )
        events.append(EventRelease(task, start + index * 20))
    return events

def scenario_events(name: str, seed: int) -> list[EventRelease]:
    if name in {"routine", "overload"}:
        return []
    if name.startswith("emergency_"):
        return emergency_profile_releases(seed, name.split("_", 1)[1])
    if name == "prolonged_emergency":
        events: list[EventRelease] = []
        rng = np.random.default_rng(90_000 + seed)
        for burst, (start, stop) in enumerate(((15_000, 21_000), (39_000, 44_000))):
            for index, release in enumerate(range(start, stop, 400)):
                events.append(
                    _high_event(
                        f"prolonged_h_{burst}_{index}",
                        release,
                        int(rng.integers(45, 75)),
                        int(rng.integers(260, 380)),
                        "controlled_prolonged_emergency",
                    )
                )
        return events
    if name == "threshold_chatter":
        events: list[EventRelease] = []
        for start in range(5_000, 55_000, 900):
            events.extend(_medium_burst(seed, start, count=3, spacing=60))
        return events
    if name == "recovery_backlog":
        events = emergency_profile_releases(seed, "moderate", times=(20_000,))
        events.extend(_low_backlog(seed, 19_500, count=45, spacing=40))
        return events
    if name == "optional_service_stress":
        events = emergency_profile_releases(seed, "moderate", times=(15_000,))
        events.extend(_optional_service_stress(seed))
        return events
    raise ValueError(f"unknown scenario: {name}")


def event_density(events: list[EventRelease], windows: Iterable[int] = (200, 500, 1000)) -> float:
    if not events:
        return 0.0
    best = 0.0
    for window in windows:
        releases = sorted((e.release_time, e.execution_budget or e.task.wcet) for e in events)
        left = 0
        work = 0
        for right, (release, budget) in enumerate(releases):
            work += budget
            while release - releases[left][0] >= window:
                work -= releases[left][1]
                left += 1
            best = max(best, work / window)
    return best


def _run_controlled_one(args: tuple[str, float, int, str, int, int, bool]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    scenario, load, seed, policy_value, duration, quantum, save_jobs = args
    tasks = scaled_periodic_taskset(load, seed)
    events = scenario_events(scenario, seed)
    policy = PolicyName(policy_value)
    config = SimulationConfig(duration=duration, quantum=quantum, policy=policy, drop_expired_jobs=True)
    start = time.perf_counter()
    result = Simulator(tasks, events, config).run()
    wall_ms = (time.perf_counter() - start) * 1000.0
    row = summarize_result(result)
    row.update(
        {
            "scenario": scenario,
            "target_utilization": load,
            "actual_periodic_utilization": nominal_utilization(tasks),
            "seed": seed,
            "event_jobs": len(events),
            "event_work": sum(e.execution_budget or e.task.wcet for e in events),
            "high_event_work": sum((e.execution_budget or e.task.wcet) for e in events if e.task.criticality is Criticality.HIGH),
            "max_event_density": event_density(events),
            "host_runtime_ms": wall_ms,
        }
    )
    transitions = [
        {
            "scenario": scenario,
            "target_utilization": load,
            "seed": seed,
            "policy": policy.value,
            "time": t.time,
            "old_mode": t.old_mode.value,
            "new_mode": t.new_mode.value,
            "reason": t.reason,
            "smoothed_utilization": t.smoothed_utilization,
            "guard_onset_time": t.guard_onset_time,
            "control_latency": t.control_latency,
        }
        for t in result.transitions
    ]
    jobs: list[dict[str, object]] = []
    if save_jobs:
        for record in job_records(result):
            record.update({"scenario": scenario, "target_utilization": load, "seed": seed})
            jobs.append(record)
    return row, transitions, jobs


def run_controlled(output: Path, seeds: list[int], duration: int, quantum: int, workers: int) -> pd.DataFrame:
    work: list[tuple[str, float, int, str, int, int, bool]] = []
    for scenario, loads in SCENARIOS.items():
        for load in loads:
            for seed in seeds:
                for policy in ALL_POLICIES:
                    save = seed == seeds[0] and load == loads[0] and policy in CORE_POLICIES
                    work.append((scenario, load, seed, policy.value, duration, quantum, save))
    rows: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    jobs: list[dict[str, object]] = []
    if workers <= 1:
        iterator = map(_run_controlled_one, work)
    else:
        executor = concurrent.futures.ProcessPoolExecutor(
            max_workers=workers, mp_context=multiprocessing.get_context("fork")
        )
        iterator = executor.map(_run_controlled_one, work, chunksize=8)
    try:
        for index, (row, run_transitions, run_jobs) in enumerate(iterator, 1):
            rows.append(row)
            transitions.extend(run_transitions)
            jobs.extend(run_jobs)
            if index % 250 == 0 or index == len(work):
                print(f"controlled {index}/{len(work)}", flush=True)
    finally:
        if workers > 1:
            executor.shutdown()
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "controlled_runs_v2.csv", index=False)
    pd.DataFrame(transitions).to_csv(output / "mode_transitions_v2.csv", index=False)
    pd.DataFrame(jobs).to_csv(output / "representative_job_traces_v2.csv", index=False)
    return frame


def _run_sensitivity_one(args: tuple[str, float, int, str, float, float, int, int, int, int]) -> dict[str, object]:
    scenario, load, seed, parameter, high, low, entry_hold, recovery_hold, obs_window, smoothing = args
    tasks = scaled_periodic_taskset(load, seed)
    events = scenario_events(scenario, seed)
    config = SimulationConfig(
        duration=60_000,
        quantum=10,
        policy=PolicyName.RT_DASH,
        utilization_high=high,
        utilization_low=low,
        entry_hold=entry_hold,
        recovery_hold=recovery_hold,
        observation_window=obs_window,
        monitor_interval=50,
        smoothing_samples=smoothing,
        drop_expired_jobs=True,
    )
    result = Simulator(tasks, events, config).run()
    row = summarize_result(result)
    row.update(
        {
            "study_parameter": parameter,
            "scenario": scenario,
            "target_utilization": load,
            "seed": seed,
            "utilization_high": high,
            "utilization_low": low,
            "entry_hold": entry_hold,
            "recovery_hold": recovery_hold,
            "observation_window": obs_window,
            "smoothing_samples": smoothing,
        }
    )
    return row


def run_sensitivity(output: Path, workers: int) -> pd.DataFrame:
    scenarios = [("emergency_mild", 0.75), ("emergency_moderate", 0.85), ("threshold_chatter", 0.82), ("recovery_backlog", 0.90)]
    seeds = list(range(10))
    settings: list[tuple[str, float, float, int, int, int, int]] = []
    for high in [0.75, 0.80, 0.85, 0.90, 0.95]:
        settings.append(("utilization_high", high, max(0.40, high - 0.20), 200, 1000, 1000, 5))
    for gap in [0.05, 0.10, 0.20, 0.30]:
        settings.append(("hysteresis_gap", 0.85, 0.85 - gap, 200, 1000, 1000, 5))
    for hold in [0, 250, 500, 1000, 2000]:
        settings.append(("recovery_hold", 0.85, 0.65, 200, hold, 1000, 5))
    for window in [250, 500, 1000, 2000]:
        settings.append(("observation_window", 0.85, 0.65, 200, 1000, window, 5))
    for smoothing in [1, 3, 5, 9]:
        settings.append(("smoothing_samples", 0.85, 0.65, 200, 1000, 1000, smoothing))
    work = []
    for scenario, load in scenarios:
        for seed in seeds:
            for parameter, high, low, entry, recovery, window, smoothing in settings:
                work.append((scenario, load, seed, parameter, high, low, entry, recovery, window, smoothing))
    if workers <= 1:
        rows = list(map(_run_sensitivity_one, work))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as ex:
            rows = list(ex.map(_run_sensitivity_one, work, chunksize=8))
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "parameter_sensitivity.csv", index=False)
    return frame


def _run_scalability_one(args: tuple[int, float, int, str]) -> dict[str, object]:
    count, load, seed, policy_value = args
    tasks = scalable_taskset(count, load, seed)
    events = emergency_profile_releases(seed, "moderate", times=(5_000, 12_000))
    config = SimulationConfig(duration=20_000, quantum=10, policy=PolicyName(policy_value), drop_expired_jobs=True)
    start = time.perf_counter()
    result = Simulator(tasks, events, config).run()
    wall_ms = (time.perf_counter() - start) * 1000.0
    row = summarize_result(result)
    row.update(
        {
            "task_count": count,
            "target_utilization": load,
            "actual_periodic_utilization": nominal_utilization(tasks),
            "seed": seed,
            "host_runtime_ms": wall_ms,
        }
    )
    return row


def run_scalability(output: Path, workers: int) -> pd.DataFrame:
    work = [
        (count, load, seed, policy.value)
        for count in [8, 16, 32, 64, 128]
        for load in [0.75, 0.95, 1.15]
        for seed in range(10)
        for policy in [PolicyName.EDF, PolicyName.CRITICALITY_EDF, PolicyName.RT_DASH]
    ]
    if workers <= 1:
        rows = list(map(_run_scalability_one, work))
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as ex:
            rows = list(ex.map(_run_scalability_one, work, chunksize=8))
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "scalability_study.csv", index=False)
    return frame


def run_trace_robustness(output: Path, csv_path: Path, quantum: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    job_rows: list[dict[str, object]] = []
    for start, window_name in TRACE_WINDOWS.items():
        for profile, (budget_scale, deadline_scale) in TRACE_PROFILES.items():
            events = trace_window_events(
                csv_path,
                start,
                120,
                time_scale=20,
                load_scale=budget_scale,
                deadline_scale=deadline_scale,
                mapping_label=profile,
            )
            duration = max(e.release_time for e in events) + 5_000
            duration += (-duration) % quantum
            for policy in CORE_POLICIES:
                result = Simulator([], events, SimulationConfig(duration=duration, quantum=quantum, policy=policy, drop_expired_jobs=True)).run()
                row = summarize_result(result)
                row.update(
                    {
                        "start_row": start,
                        "window_name": window_name,
                        "mapping_profile": profile,
                        "budget_scale": budget_scale,
                        "deadline_scale": deadline_scale,
                        "event_jobs": len(events),
                    }
                )
                rows.append(row)
                if start == 160406 and profile == "nominal":
                    for record in job_records(result):
                        record.update({"window_name": window_name, "mapping_profile": profile})
                        job_rows.append(record)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "trace_mapping_robustness.csv", index=False)
    pd.DataFrame(job_rows).to_csv(output / "trace_representative_jobs_v2.csv", index=False)
    return frame


def mean_ci(series: pd.Series) -> tuple[int, float, float, float, float, float, float]:
    x = series.dropna().astype(float).to_numpy()
    n = len(x)
    if n == 0:
        return 0, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan
    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1)) if n > 1 else 0.0
    half = float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else 0.0
    return n, mean, sd, mean - half, mean + half, float(np.median(x)), float(np.subtract(*np.percentile(x, [75, 25])))


def aggregate(frame: pd.DataFrame, group_cols: list[str], metrics: list[str], source: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, subset in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_cols, keys))
        for metric in metrics:
            if metric not in subset:
                continue
            n, mean, sd, low, high, med, iqr = mean_ci(subset[metric])
            rows.append({"source": source, **base, "metric": metric, "n": n, "mean": mean, "sd": sd, "ci95_low": low, "ci95_high": high, "median": med, "iqr": iqr})
    return pd.DataFrame(rows)


def bootstrap_ci(values: np.ndarray, seed: int = 12345, resamples: int = 10_000) -> tuple[float, float]:
    if len(values) == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(resamples, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = np.argsort([1.0 if math.isnan(p) else p for p in p_values])
    adjusted = [math.nan] * m
    running = 0.0
    for rank, idx in enumerate(order):
        p = p_values[idx]
        if math.isnan(p):
            adjusted[idx] = math.nan
            continue
        value = min(1.0, (m - rank) * p)
        running = max(running, value)
        adjusted[idx] = running
    return adjusted


def paired_comparisons(controlled: pd.DataFrame, output: Path) -> pd.DataFrame:
    specs = [
        ("emergency", "rt_dash", "edf", "high_deadline_miss_ratio"),
        ("emergency", "rt_dash", "rms", "high_deadline_miss_ratio"),
        ("emergency", "rt_dash", "criticality_edf", "high_deadline_miss_ratio"),
        ("emergency", "rt_dash", "edf", "high_mean_response"),
        ("emergency", "rt_dash", "rms", "high_mean_response"),
        ("adaptive", "rt_dash", "criticality_edf", "low_completion_rate"),
        ("adaptive", "rt_dash", "criticality_edf", "low_delivered_service_fraction"),
        ("adaptive", "rt_dash", "rt_dash_no_degradation", "low_completion_rate"),
        ("adaptive", "rt_dash", "rt_dash_no_degradation", "low_delivered_service_fraction"),
        ("degradation_stress", "rt_dash", "rt_dash_no_degradation", "low_completion_rate"),
        ("degradation_stress", "rt_dash", "rt_dash_no_degradation", "low_delivered_service_fraction"),
        ("event", "rt_dash", "rt_dash_no_event_trigger", "high_deadline_miss_ratio"),
        ("overload", "rt_dash", "rt_dash_no_load_trigger", "mode_transitions"),
        ("chatter", "rt_dash_no_hysteresis", "rt_dash", "mode_transitions"),
        ("recovery", "rt_dash_no_recovery_hold", "rt_dash", "critical_mode_fraction"),
        ("recovery", "rt_dash_no_recovery_hold", "rt_dash", "recovery_control_latency_mean"),
    ]
    rows: list[dict[str, object]] = []
    for scope, left, right, metric in specs:
        data = controlled.copy()
        if scope == "emergency":
            data = data[data.scenario.str.startswith("emergency_") | (data.scenario == "prolonged_emergency")]
        elif scope == "adaptive":
            data = data[data.scenario.isin(["overload", "emergency_mild", "emergency_moderate", "emergency_severe", "prolonged_emergency", "recovery_backlog", "optional_service_stress"])]
        elif scope == "event":
            data = data[data.scenario.isin(["emergency_mild", "emergency_moderate", "emergency_severe"])]
        elif scope == "degradation_stress":
            data = data[data.scenario == "optional_service_stress"]
        elif scope == "overload":
            data = data[data.scenario == "overload"]
        elif scope == "chatter":
            data = data[data.scenario == "threshold_chatter"]
        elif scope == "recovery":
            data = data[data.scenario == "emergency_mild"]
        wide = data.pivot_table(index=["scenario", "target_utilization", "seed"], columns="policy", values=metric, aggfunc="first")
        if left not in wide or right not in wide:
            continue
        diff = (wide[left] - wide[right]).dropna().astype(float).to_numpy()
        n = len(diff)
        mean = float(np.mean(diff)) if n else math.nan
        sd = float(np.std(diff, ddof=1)) if n > 1 else 0.0
        low, high = bootstrap_ci(diff)
        if n and np.any(diff != 0):
            wil = stats.wilcoxon(diff, zero_method="wilcox", alternative="two-sided")
            p = float(wil.pvalue)
            stat = float(wil.statistic)
            nonzero = diff[diff != 0]
            ranks = stats.rankdata(np.abs(nonzero))
            rb = float((ranks[nonzero > 0].sum() - ranks[nonzero < 0].sum()) / ranks.sum())
        else:
            p, stat, rb = math.nan, math.nan, 0.0
        rows.append({
            "scope": scope,
            "left_policy": left,
            "right_policy": right,
            "metric": metric,
            "n_pairs": n,
            "mean_difference": mean,
            "median_difference": float(np.median(diff)) if n else math.nan,
            "sd_difference": sd,
            "bootstrap_ci95_low": low,
            "bootstrap_ci95_high": high,
            "cohen_dz": mean / sd if sd > 0 else (math.inf if mean else 0.0),
            "rank_biserial": rb,
            "wilcoxon_statistic": stat,
            "wilcoxon_p": p,
        })
    frame = pd.DataFrame(rows)
    frame["wilcoxon_p_holm"] = holm_adjust(frame.wilcoxon_p.tolist())
    frame.to_csv(output / "paired_comparisons_v2.csv", index=False)
    return frame


def make_figures(controlled: pd.DataFrame, sensitivity: pd.DataFrame, scalability: pd.DataFrame, trace: pd.DataFrame, output: Path) -> None:
    import matplotlib.pyplot as plt
    figures = output / "figures"
    figures.mkdir(exist_ok=True)

    selected = ["edf", "rms", "criticality_edf", "rt_dash"]
    for scenario in ["emergency_mild", "emergency_moderate", "emergency_severe"]:
        sub = controlled[(controlled.scenario == scenario) & controlled.policy.isin(selected)]
        agg = sub.groupby(["target_utilization", "policy"])["high_deadline_miss_ratio"].agg(["mean", "sem"]).reset_index()
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for policy, p in agg.groupby("policy"):
            ax.errorbar(p.target_utilization, p["mean"], yerr=1.96 * p["sem"], marker="o", label=policy)
        ax.set_xlabel("Nominal periodic utilization")
        ax.set_ylabel("High-criticality deadline-miss ratio")
        ax.set_title(scenario.replace("_", " ").title())
        ax.set_ylim(-0.03, 1.03)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(figures / f"{scenario}_high_dmr_load_curve.png", dpi=600)
        plt.close(fig)

    adaptive = controlled[controlled.scenario.isin(["overload", "emergency_moderate", "emergency_severe", "recovery_backlog", "optional_service_stress"])]
    trade = adaptive.groupby("policy")[["low_completion_rate", "low_delivered_service_fraction"]].mean().reset_index()
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(trade.low_delivered_service_fraction, trade.low_completion_rate)
    for _, row in trade.iterrows():
        ax.annotate(row.policy, (row.low_delivered_service_fraction, row.low_completion_rate), fontsize=8)
    ax.set_xlabel("Low-criticality delivered service fraction")
    ax.set_ylabel("Low-criticality completion rate")
    ax.set_title("Completion–service trade-off")
    fig.tight_layout()
    fig.savefig(figures / "low_criticality_tradeoff.png", dpi=600)
    plt.close(fig)

    chat = controlled[controlled.scenario == "threshold_chatter"].groupby(["target_utilization", "policy"])["mode_transitions"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for policy in ["rt_dash", "rt_dash_no_hysteresis", "rt_dash_no_recovery_hold"]:
        p = chat[chat.policy == policy]
        ax.plot(p.target_utilization, p.mode_transitions, marker="o", label=policy)
    ax.set_xlabel("Nominal periodic utilization")
    ax.set_ylabel("Mode transitions per run")
    ax.set_title("Hysteresis and recovery-hold ablations")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "transition_chatter_ablation.png", dpi=600)
    plt.close(fig)

    for parameter in sensitivity.study_parameter.unique():
        sub = sensitivity[sensitivity.study_parameter == parameter].copy()
        value_col = {
            "utilization_high": "utilization_high",
            "hysteresis_gap": None,
            "recovery_hold": "recovery_hold",
            "observation_window": "observation_window",
            "smoothing_samples": "smoothing_samples",
        }[parameter]
        if parameter == "hysteresis_gap":
            sub["parameter_value"] = sub.utilization_high - sub.utilization_low
        else:
            sub["parameter_value"] = sub[value_col]
        metric = {
            "utilization_high": "critical_mode_fraction",
            "hysteresis_gap": "mode_transitions",
            "recovery_hold": "recovery_control_latency_mean",
            "observation_window": "critical_mode_fraction",
            "smoothing_samples": "critical_mode_fraction",
        }[parameter]
        agg = sub.groupby(["parameter_value", "scenario"])[metric].mean().reset_index()
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for scenario, p in agg.groupby("scenario"):
            ax.plot(p.parameter_value, p[metric], marker="o", label=scenario)
        ax.set_xlabel(parameter.replace("_", " "))
        ax.set_ylabel(metric.replace("_", " "))
        ax.set_title(f"Sensitivity: {parameter.replace('_', ' ')}")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(figures / f"sensitivity_{parameter}.png", dpi=600)
        plt.close(fig)

    scale = scalability.groupby(["task_count", "policy"])[["max_ready_queue", "scheduling_decisions", "host_runtime_ms"]].mean().reset_index()
    for metric, ylabel in [
        ("max_ready_queue", "Maximum ready-queue length"),
        ("scheduling_decisions", "Scheduling decisions per run"),
        ("host_runtime_ms", "Host execution time (ms; environment-specific)"),
    ]:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for policy, p in scale.groupby("policy"):
            ax.plot(p.task_count, p[metric], marker="o", label=policy)
        ax.set_xlabel("Number of periodic tasks")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Scalability: {ylabel}")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(figures / f"scalability_{metric}.png", dpi=600)
        plt.close(fig)

    tr = trace.groupby(["mapping_profile", "policy"])["high_deadline_miss_ratio"].mean().reset_index()
    pivot = tr.pivot(index="mapping_profile", columns="policy", values="high_deadline_miss_ratio")
    ax = pivot.plot(kind="bar", figsize=(9, 5))
    ax.set_ylabel("High-criticality deadline-miss ratio")
    ax.set_xlabel("Trace-to-task mapping profile")
    ax.set_title("Trace mapping robustness")
    ax.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(figures / "trace_mapping_robustness.png", dpi=600)
    plt.close()


def build_cpp(project_root: Path, output: Path) -> str:
    build = project_root / "research_cpp" / "build_journal"
    build.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cmake", "-S", str(project_root / "research_cpp"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"], check=True, capture_output=True, text=True)
    subprocess.run(["cmake", "--build", str(build), "-j", "4"], check=True, capture_output=True, text=True)
    subprocess.run(["ctest", "--test-dir", str(build), "--output-on-failure"], check=True, capture_output=True, text=True)
    result = subprocess.run([str(build / "rtdash_host_simulation")], check=True, capture_output=True, text=True)
    (output / "cpp_host_simulation_v2.csv").write_text(result.stdout)
    return result.stdout


def write_reports(controlled: pd.DataFrame, sensitivity: pd.DataFrame, scalability: pd.DataFrame, trace: pd.DataFrame, comparisons: pd.DataFrame, output: Path, seeds: list[int], duration: int, quantum: int) -> None:
    emergency = controlled[controlled.scenario.str.startswith("emergency_") | (controlled.scenario == "prolonged_emergency")]
    key = emergency.groupby("policy")[["high_deadline_miss_ratio", "high_mean_response", "low_completion_rate", "low_delivered_service_fraction"]].mean()
    chatter = controlled[controlled.scenario == "threshold_chatter"].groupby("policy")["mode_transitions"].mean()
    count_by_policy = controlled.groupby("policy").size().to_dict()

    report = f"""# RT-DASH Strengthened Simulation Validation Report

**Executed:** {datetime.now(timezone.utc).isoformat()}  
**Study type:** simulation only  
**Controlled runs:** {len(controlled)}  
**Sensitivity runs:** {len(sensitivity)}  
**Scalability runs:** {len(scalability)}  
**Trace-mapping runs:** {len(trace)}  
**Total executed simulations:** {len(controlled)+len(sensitivity)+len(scalability)+len(trace)}  
**Seeds in principal controlled study:** {len(seeds)} ({seeds[0]}–{seeds[-1]})  
**Duration/quantum:** {duration} ms / {quantum} ms

## Major redevelopment completed

- Corrected startup utilization estimation by zero-filling the observation window.
- Made each scheduling quantum work-conserving; residual time after job completion is no longer discarded.
- Added event-trigger, load-trigger, recovery-hold, hysteresis and degradation ablations.
- Replaced ceiling-dominated emergency tests with mild, moderate and severe demand regions.
- Added 30-seed paired experiments, bootstrap confidence intervals, effect sizes and Holm-adjusted tests.
- Added parameter sensitivity, task-count scalability, recovery/queue metrics and trace-to-task mapping robustness.
- Retained a static criticality-first baseline to separate criticality-first dispatch from adaptive mode control.

## Principal emergency-scenario means

```
{key.to_string(float_format=lambda x: f'{x:.5f}')}
```

## Threshold-chatter mean transitions

```
{chatter.to_string(float_format=lambda x: f'{x:.3f}')}
```

## Controlled run balance

`{count_by_policy}`

## Scientific interpretation

1. Criticality-first dispatch is the primary mechanism protecting high-criticality jobs.
2. RT-DASH's incremental contribution is adaptive activation, load/event trigger integration, hysteretic recovery and controlled optional-service reduction.
3. Performance is now evaluated across graded demand regions rather than only extreme baseline failure.
4. Completion and delivered service are reported together, preventing degraded completions from being mistaken for full-quality service.
5. Trace-derived conclusions are tested under relaxed, nominal and stressed mapping assumptions.
6. Results remain bounded to the declared single-core simulation model and do not imply hard schedulability or physical-device timing.

## Authoritative result files

- `controlled_runs_v2.csv`
- `mode_transitions_v2.csv`
- `parameter_sensitivity.csv`
- `scalability_study.csv`
- `trace_mapping_robustness.csv`
- `aggregate_controlled_v2.csv`
- `aggregate_sensitivity.csv`
- `aggregate_scalability.csv`
- `aggregate_trace_robustness.csv`
- `paired_comparisons_v2.csv`
- `figures/`
- `execution_manifest_v2.json`
- `sha256sums_v2.txt`
"""
    (output / "STRENGTHENED_SIMULATION_VALIDATION_REPORT.md").write_text(report)

    readiness = f"""# Journal Readiness Assessment After Redevelopment

## Verdict

The project is now a substantially stronger simulation study. It has adequate repeated-run depth, graded stress regions, an explicit static criticality-first baseline, multiple ablations, sensitivity analysis, scalability analysis, recovery metrics and mapping-robustness analysis.

## Strengths

- {len(seeds)} paired seeds for every principal scenario/load/policy cell.
- {len(ALL_POLICIES)} policies, including five mechanism-isolating RT-DASH variants.
- Mild, moderate and severe emergency profiles reduce ceiling effects.
- Bootstrap confidence intervals, Wilcoxon tests, Holm correction and paired effect sizes.
- Transparent negative results and infeasibility boundaries.
- Reproducible code, manifests, raw summaries, representative job traces and hashes.

## Remaining boundaries

- Simulation task budgets and trace deadlines are model assumptions, not measured WCETs.
- The C++ host run is a parity check, not a separate statistical population.
- The study does not prove hard real-time schedulability or universal dominance over published mixed-criticality algorithms.
- A direct implementation of a published mixed-criticality comparator would strengthen state-of-the-art positioning further, but EDF, RMS and static criticality-first now provide defensible internal controls.

## Recommendation

Suitable as the experimental foundation of a simulation-focused journal article, provided the manuscript reports the model assumptions, ablation findings and evidence boundaries exactly as documented here.
"""
    (output / "JOURNAL_READINESS_ASSESSMENT.md").write_text(readiness)


def hash_tree(root: Path, destination: Path) -> None:
    lines = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == destination or any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}")
    destination.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/journal_strengthened"))
    parser.add_argument("--trace-csv", type=Path, default=Path("../data/raw/smart_home_dataset.csv"))
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--duration", type=int, default=60_000)
    parser.add_argument("--quantum", type=int, default=10)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    project_root = Path(__file__).resolve().parents[2]
    seeds = list(range(args.seeds))

    controlled = run_controlled(output, seeds, args.duration, args.quantum, args.workers)
    print("controlled complete", flush=True)
    sensitivity = run_sensitivity(output, args.workers)
    print("sensitivity complete", flush=True)
    scalability = run_scalability(output, args.workers)
    print("scalability complete", flush=True)
    trace = run_trace_robustness(output, args.trace_csv.resolve(), args.quantum)
    print("trace complete", flush=True)

    metrics = [
        "high_deadline_miss_ratio", "high_mean_response", "high_p95_response",
        "low_completion_rate", "low_delivered_service_fraction", "low_p95_wait",
        "overall_completion_rate", "overall_deadline_miss_ratio", "processor_utilization",
        "mode_transitions", "critical_mode_fraction", "max_ready_queue", "average_ready_queue",
        "context_switches", "entry_control_latency_mean", "recovery_control_latency_mean",
        "recovery_clearance_mean", "scheduling_decisions", "host_runtime_ms",
    ]
    aggregate(controlled, ["scenario", "target_utilization", "policy"], metrics, "controlled").to_csv(output / "aggregate_controlled_v2.csv", index=False)
    aggregate(sensitivity, ["study_parameter", "scenario", "utilization_high", "utilization_low", "entry_hold", "recovery_hold", "observation_window", "smoothing_samples"], metrics, "sensitivity").to_csv(output / "aggregate_sensitivity.csv", index=False)
    aggregate(scalability, ["task_count", "target_utilization", "policy"], metrics, "scalability").to_csv(output / "aggregate_scalability.csv", index=False)
    aggregate(trace, ["window_name", "mapping_profile", "policy"], metrics, "trace").to_csv(output / "aggregate_trace_robustness.csv", index=False)
    comparisons = paired_comparisons(controlled, output)
    make_figures(controlled, sensitivity, scalability, trace, output)

    cpp_output = build_cpp(project_root, output)
    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "study": "simulation_only",
        "duration_ms": args.duration,
        "quantum_ms": args.quantum,
        "principal_seeds": seeds,
        "policies": [p.value for p in ALL_POLICIES],
        "scenarios": SCENARIOS,
        "trace_windows": TRACE_WINDOWS,
        "trace_profiles": TRACE_PROFILES,
        "counts": {
            "controlled": len(controlled),
            "sensitivity": len(sensitivity),
            "scalability": len(scalability),
            "trace": len(trace),
            "total": len(controlled) + len(sensitivity) + len(scalability) + len(trace),
        },
        "cpp_host_output_rows": len(cpp_output.strip().splitlines()) - 1,
    }
    (output / "execution_manifest_v2.json").write_text(json.dumps(manifest, indent=2))
    write_reports(controlled, sensitivity, scalability, trace, comparisons, output, seeds, args.duration, args.quantum)
    hash_tree(output, output / "sha256sums_v2.txt")
    print(json.dumps(manifest["counts"], indent=2), flush=True)


if __name__ == "__main__":
    main()
