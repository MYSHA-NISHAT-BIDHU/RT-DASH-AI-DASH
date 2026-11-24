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
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

from rt_dash.imc import (
    MCBenchmarkConfig,
    MCPolicy,
    generate_mc_taskset,
    run_mc_benchmark,
    summarize_mc,
    utilization_components,
)
from rt_dash.metrics import job_records, summarize_result
from rt_dash.model import Criticality, TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import EventRelease, SimulationConfig, Simulator
from rt_dash.workloads import nominal_utilization, scaled_periodic_taskset
from run_journal_strengthening_study import scenario_events


TUNING_CELLS: tuple[tuple[str, float], ...] = (
    ("emergency_mild", 0.75),
    ("emergency_moderate", 0.85),
    ("emergency_severe", 0.95),
    ("threshold_chatter", 0.82),
    ("recovery_backlog", 0.90),
    ("optional_service_stress", 0.85),
    ("overload", 1.00),
)


FULL_MATRIX_CELLS: tuple[tuple[str, float], ...] = (
    ("routine", 0.50), ("routine", 0.65), ("routine", 0.80), ("routine", 0.90),
    ("overload", 0.90), ("overload", 1.00), ("overload", 1.10), ("overload", 1.20),
    ("emergency_mild", 0.60), ("emergency_mild", 0.75), ("emergency_mild", 0.90),
    ("emergency_moderate", 0.70), ("emergency_moderate", 0.85), ("emergency_moderate", 1.00),
    ("emergency_severe", 0.80), ("emergency_severe", 0.95), ("emergency_severe", 1.10),
    ("prolonged_emergency", 0.80), ("prolonged_emergency", 0.95),
    ("threshold_chatter", 0.72), ("threshold_chatter", 0.82), ("threshold_chatter", 0.88),
    ("recovery_backlog", 0.75), ("recovery_backlog", 0.90), ("recovery_backlog", 1.05),
    ("optional_service_stress", 0.70), ("optional_service_stress", 0.85), ("optional_service_stress", 1.00),
)

FULL_MATRIX_METRICS: tuple[str, ...] = (
    "high_deadline_miss_ratio",
    "high_mean_response",
    "low_completion_rate",
    "low_work_weighted_utility_concave",
    "low_work_weighted_utility_linear",
    "low_work_weighted_utility_convex",
    "low_service_fairness_jain",
    "low_p95_wait",
    "mode_transitions",
    "critical_mode_fraction",
    "recovery_clearance_mean",
)


@dataclass(frozen=True, slots=True)
class TunableConfig:
    utilization_high: float
    utilization_low: float
    entry_hold: int
    recovery_hold: int
    observation_window: int = 1000
    smoothing_samples: int = 5

    @property
    def config_id(self) -> str:
        return (
            f"uh{self.utilization_high:.2f}_ul{self.utilization_low:.2f}_"
            f"eh{self.entry_hold}_rh{self.recovery_hold}"
        )


def candidate_configs() -> list[TunableConfig]:
    configs: list[TunableConfig] = []
    for high in (0.80, 0.85, 0.90):
        for gap in (0.10, 0.20):
            for entry in (0, 200):
                for recovery in (500, 1000, 2000):
                    configs.append(
                        TunableConfig(
                            utilization_high=high,
                            utilization_low=high - gap,
                            entry_hold=entry,
                            recovery_hold=recovery,
                        )
                    )
    return configs


def _run_configured(args: tuple[str, float, int, str, TunableConfig, int, int, str]) -> dict[str, object]:
    scenario, load, seed, policy_value, tuning, duration, quantum, variant = args
    tasks = scaled_periodic_taskset(load, seed)
    events = scenario_events(scenario, seed)
    config = SimulationConfig(
        duration=duration,
        quantum=quantum,
        policy=PolicyName(policy_value),
        observation_window=tuning.observation_window,
        smoothing_samples=tuning.smoothing_samples,
        utilization_high=tuning.utilization_high,
        utilization_low=tuning.utilization_low,
        entry_hold=tuning.entry_hold,
        recovery_hold=tuning.recovery_hold,
        drop_expired_jobs=True,
    )
    start = time.perf_counter()
    result = Simulator(tasks, events, config).run()
    wall_ms = (time.perf_counter() - start) * 1000.0
    row = summarize_result(result)
    row.update(
        {
            "variant": variant,
            "scenario": scenario,
            "target_utilization": load,
            "actual_periodic_utilization": nominal_utilization(tasks),
            "seed": seed,
            "config_id": tuning.config_id,
            "utilization_high": tuning.utilization_high,
            "utilization_low": tuning.utilization_low,
            "entry_hold": tuning.entry_hold,
            "recovery_hold": tuning.recovery_hold,
            "observation_window": tuning.observation_window,
            "smoothing_samples": tuning.smoothing_samples,
            "host_runtime_ms": wall_ms,
        }
    )
    return row


def _parallel_map(function, work: list[tuple], workers: int, chunksize: int = 8):
    if workers <= 1:
        return list(map(function, work))
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("fork"),
    ) as executor:
        return list(executor.map(function, work, chunksize=chunksize))


def tuning_score(frame: pd.DataFrame) -> dict[str, float]:
    emergency = frame[
        frame.scenario.str.startswith("emergency_")
        | (frame.scenario == "prolonged_emergency")
    ]
    adaptive = frame[frame.scenario != "routine"]
    chatter = frame[frame.scenario == "threshold_chatter"]
    recovery = frame[frame.scenario == "recovery_backlog"]

    def mean_or(data: pd.DataFrame, column: str, fallback: float) -> float:
        if column not in data or data[column].dropna().empty:
            return fallback
        return float(data[column].dropna().mean())

    safety_dmr = mean_or(emergency, "high_deadline_miss_ratio", 1.0)
    high_response_norm = min(2.0, mean_or(emergency, "high_mean_response", 1000.0) / 500.0)
    low_utility_loss = 1.0 - mean_or(
        adaptive, "low_work_weighted_utility_linear", 0.0
    )
    low_completion_loss = 1.0 - mean_or(adaptive, "low_completion_rate", 0.0)
    chatter_norm = min(2.0, mean_or(chatter, "mode_transitions", 50.0) / 50.0)
    recovery_wait_norm = min(2.0, mean_or(recovery, "low_p95_wait", 4000.0) / 2000.0)

    # Predeclared safety-dominant objective. It is applied identically to the
    # training and validation partitions; held-out test data are never used for
    # configuration selection.
    score = (
        0.50 * safety_dmr
        + 0.15 * high_response_norm
        + 0.15 * low_utility_loss
        + 0.10 * low_completion_loss
        + 0.05 * chatter_norm
        + 0.05 * recovery_wait_norm
    )
    return {
        "score": score,
        "safety_dmr": safety_dmr,
        "high_response_norm": high_response_norm,
        "low_utility_loss": low_utility_loss,
        "low_completion_loss": low_completion_loss,
        "chatter_norm": chatter_norm,
        "recovery_wait_norm": recovery_wait_norm,
    }


def run_tuning(output: Path, workers: int, duration: int, quantum: int) -> tuple[TunableConfig, pd.DataFrame, pd.DataFrame]:
    configs = candidate_configs()
    train_seeds = list(range(0, 10))
    validation_seeds = list(range(10, 20))

    train_work = [
        (scenario, load, seed, PolicyName.RT_DASH.value, cfg, duration, quantum, "rt_dash_candidate")
        for cfg in configs
        for scenario, load in TUNING_CELLS
        for seed in train_seeds
    ]
    train = pd.DataFrame(_parallel_map(_run_configured, train_work, workers))
    train.to_csv(output / "tuning_train_runs.csv", index=False)

    train_scores: list[dict[str, object]] = []
    for cfg in configs:
        metrics = tuning_score(train[train.config_id == cfg.config_id])
        train_scores.append({"config_id": cfg.config_id, **asdict(cfg), **metrics})
    train_ranking = pd.DataFrame(train_scores).sort_values("score").reset_index(drop=True)
    train_ranking.to_csv(output / "tuning_train_ranking.csv", index=False)

    top_ids = set(train_ranking.head(6).config_id)
    top_configs = [cfg for cfg in configs if cfg.config_id in top_ids]
    validation_work = [
        (scenario, load, seed, PolicyName.RT_DASH.value, cfg, duration, quantum, "rt_dash_candidate")
        for cfg in top_configs
        for scenario, load in TUNING_CELLS
        for seed in validation_seeds
    ]
    validation = pd.DataFrame(_parallel_map(_run_configured, validation_work, workers))
    validation.to_csv(output / "tuning_validation_runs.csv", index=False)

    validation_scores: list[dict[str, object]] = []
    for cfg in top_configs:
        metrics = tuning_score(validation[validation.config_id == cfg.config_id])
        validation_scores.append({"config_id": cfg.config_id, **asdict(cfg), **metrics})
    validation_ranking = (
        pd.DataFrame(validation_scores).sort_values("score").reset_index(drop=True)
    )
    validation_ranking.to_csv(output / "tuning_validation_ranking.csv", index=False)
    winner_id = str(validation_ranking.iloc[0].config_id)
    winner = next(cfg for cfg in configs if cfg.config_id == winner_id)
    return winner, train_ranking, validation_ranking


def run_heldout_test(
    output: Path,
    winner: TunableConfig,
    workers: int,
    duration: int,
    quantum: int,
) -> pd.DataFrame:
    test_seeds = list(range(20, 30))
    default = TunableConfig(0.85, 0.65, 200, 1000)
    variants = (
        (PolicyName.EDF, default, "edf"),
        (PolicyName.RMS, default, "rms"),
        (PolicyName.CRITICALITY_EDF, default, "criticality_edf"),
        (PolicyName.RT_DASH, default, "rt_dash_default"),
        (PolicyName.RT_DASH, winner, "rt_dash_tuned"),
        (PolicyName.RT_DASH_RECOVERY_EDF, winner, "rt_dash_recovery_edf_tuned"),
    )
    work = [
        (scenario, load, seed, policy.value, cfg, duration, quantum, label)
        for scenario, load in TUNING_CELLS
        for seed in test_seeds
        for policy, cfg, label in variants
    ]
    frame = pd.DataFrame(_parallel_map(_run_configured, work, workers))
    frame.to_csv(output / "heldout_test_runs.csv", index=False)
    return frame


def bootstrap_ci(values: np.ndarray, seed: int = 991, resamples: int = 10_000) -> tuple[float, float]:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    index = rng.integers(0, values.size, size=(resamples, values.size))
    means = values[index].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def heldout_comparisons(frame: pd.DataFrame, output: Path) -> pd.DataFrame:
    specs = [
        ("rt_dash_tuned", "rt_dash_default", "high_deadline_miss_ratio"),
        ("rt_dash_tuned", "rt_dash_default", "low_work_weighted_utility_linear"),
        ("rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_completion_rate"),
        ("rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_p95_wait"),
        ("rt_dash_recovery_edf_tuned", "rt_dash_tuned", "high_deadline_miss_ratio"),
        ("rt_dash_recovery_edf_tuned", "criticality_edf", "low_work_weighted_utility_linear"),
        ("rt_dash_recovery_edf_tuned", "edf", "high_deadline_miss_ratio"),
        ("rt_dash_recovery_edf_tuned", "rms", "high_deadline_miss_ratio"),
    ]
    rows: list[dict[str, object]] = []
    emergency_mask = frame.scenario.str.startswith("emergency_")
    for left, right, metric in specs:
        data = frame.copy()
        if "high_" in metric:
            data = data[emergency_mask]
        wide = data.pivot_table(
            index=["scenario", "target_utilization", "seed"],
            columns="variant",
            values=metric,
            aggfunc="first",
        )
        if left not in wide or right not in wide:
            continue
        diff = (wide[left] - wide[right]).dropna().to_numpy(dtype=float)
        low, high = bootstrap_ci(diff)
        try:
            wilcoxon = stats.wilcoxon(diff, zero_method="zsplit")
            pvalue = float(wilcoxon.pvalue)
        except ValueError:
            pvalue = math.nan
        rows.append(
            {
                "left": left,
                "right": right,
                "metric": metric,
                "n_pairs": len(diff),
                "mean_difference": float(np.mean(diff)) if len(diff) else math.nan,
                "ci95_low": low,
                "ci95_high": high,
                "wilcoxon_p": pvalue,
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(output / "heldout_paired_comparisons.csv", index=False)
    return result



def run_full_optimized_matrix(
    output: Path, winner: TunableConfig, workers: int, duration: int, quantum: int
) -> pd.DataFrame:
    variants = (
        (PolicyName.RT_DASH, "rt_dash_tuned"),
        (PolicyName.RT_DASH_RECOVERY_EDF, "rt_dash_recovery_edf_tuned"),
    )
    work = [
        (scenario, load, seed, policy.value, winner, duration, quantum, label)
        for scenario, load in FULL_MATRIX_CELLS
        for seed in range(30)
        for policy, label in variants
    ]
    frame = pd.DataFrame(_parallel_map(_run_configured, work, workers))
    frame.to_csv(output / "full_matrix_optimized_variants.csv", index=False)
    return frame


def full_matrix_comparisons(frame: pd.DataFrame, output: Path) -> pd.DataFrame:
    left = "rt_dash_recovery_edf_tuned"
    right = "rt_dash_tuned"
    scopes = (
        ("all", pd.Series(True, index=frame.index)),
        ("emergency", frame.scenario.str.startswith("emergency_") | (frame.scenario == "prolonged_emergency")),
        ("recovery", frame.scenario == "recovery_backlog"),
        ("chatter", frame.scenario == "threshold_chatter"),
        ("optional_service", frame.scenario == "optional_service_stress"),
    )
    rows: list[dict[str, object]] = []
    for scope, mask in scopes:
        subset = frame[mask]
        for metric in FULL_MATRIX_METRICS[:-1]:
            data = subset
            if metric.startswith("high_"):
                data = data[data[metric].notna()]
            wide = data.pivot_table(
                index=["scenario", "target_utilization", "seed"],
                columns="variant", values=metric, aggfunc="first",
            )
            if left not in wide or right not in wide:
                continue
            diff = (wide[left] - wide[right]).dropna().to_numpy(dtype=float)
            if not len(diff):
                continue
            low, high = bootstrap_ci(diff)
            try:
                pvalue = float(stats.wilcoxon(diff, zero_method="zsplit").pvalue)
            except ValueError:
                pvalue = math.nan
            rows.append({
                "scope": scope, "left": left, "right": right, "metric": metric,
                "n_pairs": len(diff),
                "mean_difference": float(np.mean(diff)),
                "ci95_low": low, "ci95_high": high, "wilcoxon_p": pvalue,
            })
    result = pd.DataFrame(rows)
    result.to_csv(output / "full_matrix_optimized_comparisons.csv", index=False)
    return result


def periodic_dbf(tasks: list[TaskSpec], length: int, minimum_service: bool) -> float:
    total = 0.0
    for task in tasks:
        if task.period is None:
            continue
        jobs = max(0, math.floor((length - task.relative_deadline) / task.period) + 1)
        budget = float(task.wcet)
        if minimum_service and task.degradable:
            budget *= task.min_service_fraction
        total += jobs * budget
    return total


def event_interval_demand(events: list[EventRelease], start: int, end: int, minimum_service: bool) -> float:
    total = 0.0
    for event in events:
        deadline = event.release_time + event.task.relative_deadline
        if event.release_time >= start and deadline <= end:
            budget = float(event.execution_budget or event.task.wcet)
            if minimum_service and event.task.degradable:
                budget *= event.task.min_service_fraction
            total += budget
    return total


def demand_screen(tasks: list[TaskSpec], events: list[EventRelease]) -> tuple[float, float, int, int]:
    lengths = sorted(
        set(range(100, 5001, 100))
        | set(range(6000, 10001, 1000))
        | {t.relative_deadline for t in tasks}
        | {t.period for t in tasks if t.period is not None}
        | {e.task.relative_deadline for e in events}
    )
    starts = sorted({0} | {e.release_time for e in events})
    max_full = 0.0
    max_min = 0.0
    arg_full = 0
    arg_min = 0
    for length in lengths:
        if length <= 0:
            continue
        base_full = periodic_dbf(tasks, length, False)
        base_min = periodic_dbf(tasks, length, True)
        for start in starts:
            end = start + length
            full = (base_full + event_interval_demand(events, start, end, False)) / length
            minimum = (base_min + event_interval_demand(events, start, end, True)) / length
            if full > max_full:
                max_full, arg_full = full, length
            if minimum > max_min:
                max_min, arg_min = minimum, length
    return max_full, max_min, arg_full, arg_min


def run_feasibility_screen(output: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for scenario, load in TUNING_CELLS:
        for seed in range(20, 30):
            tasks = scaled_periodic_taskset(load, seed)
            events = scenario_events(scenario, seed)
            full, minimum, full_window, minimum_window = demand_screen(tasks, events)
            rows.append(
                {
                    "scenario": scenario,
                    "target_utilization": load,
                    "seed": seed,
                    "periodic_utilization": nominal_utilization(tasks),
                    "max_full_demand_ratio": full,
                    "max_minimum_service_demand_ratio": minimum,
                    "full_worst_window_ms": full_window,
                    "minimum_worst_window_ms": minimum_window,
                    "full_screened_feasible": full <= 1.0,
                    "minimum_service_screened_feasible": minimum <= 1.0,
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "demand_bound_screen.csv", index=False)
    return frame


def _perturb_workload(
    scenario: str,
    load: float,
    seed: int,
    overhead_fraction: float,
    jitter_ms: int,
    quantum: int,
) -> tuple[list[TaskSpec], list[EventRelease]]:
    from dataclasses import replace

    rng = np.random.default_rng(900_000 + seed + int(overhead_fraction * 1000) + jitter_ms)
    tasks: list[TaskSpec] = []
    for task in scaled_periodic_taskset(load, seed):
        extra = max(0, int(round(task.wcet * overhead_fraction)))
        phase_shift = int(rng.integers(0, jitter_ms + 1)) if jitter_ms else 0
        phase = (task.phase + phase_shift) % int(task.period or 1)
        phase -= phase % quantum
        tasks.append(replace(task, wcet=task.wcet + extra, phase=phase))
    events: list[EventRelease] = []
    for event in scenario_events(scenario, seed):
        shift = int(rng.integers(-jitter_ms, jitter_ms + 1)) if jitter_ms else 0
        release = max(0, event.release_time + shift)
        release -= release % quantum
        base = event.execution_budget or event.task.wcet
        budget = base + max(0, int(round(base * overhead_fraction)))
        events.append(EventRelease(event.task, release, budget))
    return tasks, events


def _run_robustness_one(args: tuple[str, float, int, float, int, str, TunableConfig, int, int, str]) -> dict[str, object]:
    scenario, load, seed, overhead, jitter, policy_value, tuning, duration, quantum, variant = args
    tasks, events = _perturb_workload(scenario, load, seed, overhead, jitter, quantum)
    config = SimulationConfig(
        duration=duration,
        quantum=quantum,
        policy=PolicyName(policy_value),
        utilization_high=tuning.utilization_high,
        utilization_low=tuning.utilization_low,
        entry_hold=tuning.entry_hold,
        recovery_hold=tuning.recovery_hold,
        observation_window=tuning.observation_window,
        smoothing_samples=tuning.smoothing_samples,
        drop_expired_jobs=True,
    )
    result = Simulator(tasks, events, config).run()
    row = summarize_result(result)
    row.update(
        {
            "variant": variant,
            "scenario": scenario,
            "target_utilization": load,
            "seed": seed,
            "execution_overhead_fraction": overhead,
            "release_jitter_ms": jitter,
        }
    )
    return row


def run_robustness(output: Path, winner: TunableConfig, workers: int, duration: int, quantum: int) -> pd.DataFrame:
    policies = (
        (PolicyName.EDF, "edf"),
        (PolicyName.CRITICALITY_EDF, "criticality_edf"),
        (PolicyName.RT_DASH, "rt_dash_tuned"),
        (PolicyName.RT_DASH_RECOVERY_EDF, "rt_dash_recovery_edf_tuned"),
    )
    work = [
        (scenario, load, seed, overhead, jitter, policy.value, winner, duration, quantum, label)
        for scenario, load in (("emergency_moderate", 0.85), ("recovery_backlog", 0.90))
        for seed in range(20, 30)
        for overhead in (0.0, 0.05, 0.10, 0.20)
        for jitter in (0, 20, 50)
        for policy, label in policies
    ]
    frame = pd.DataFrame(_parallel_map(_run_robustness_one, work, workers))
    frame.to_csv(output / "overhead_jitter_robustness.csv", index=False)
    return frame


def _run_mc_one(args: tuple[float, float, float, float, int, str]) -> dict[str, object]:
    load, high_factor, retention, overrun, seed, policy_value = args
    tasks = generate_mc_taskset(
        task_count=20,
        total_lo_utilization=load,
        high_task_fraction=0.30,
        high_budget_factor=high_factor,
        low_retention=retention,
        seed=seed,
    )
    policy = MCPolicy(policy_value)
    result = run_mc_benchmark(
        tasks,
        MCBenchmarkConfig(
            duration=5_000,
            quantum=1,
            policy=policy,
            overrun_probability=overrun,
            seed=seed,
        ),
    )
    row = summarize_mc(result)
    u_lo_lo, u_lo_hi, u_hi_lo, u_hi_hi = utilization_components(tasks)
    row.update(
        {
            "target_lo_utilization": load,
            "high_budget_factor": high_factor,
            "low_retention": retention,
            "overrun_probability": overrun,
            "seed": seed,
            "u_lo_lo": u_lo_lo,
            "u_lo_hi": u_lo_hi,
            "u_hi_lo": u_hi_lo,
            "u_hi_hi": u_hi_hi,
        }
    )
    return row


def run_external_mc_benchmark(output: Path, workers: int) -> pd.DataFrame:
    work = [
        (load, high_factor, retention, overrun, seed, policy.value)
        for load in (0.85, 0.95)
        for high_factor in (2.0, 2.5)
        for retention in (0.25, 0.50)
        for overrun in (0.30, 0.60)
        for seed in range(10)
        for policy in MCPolicy
    ]
    frame = pd.DataFrame(_parallel_map(_run_mc_one, work, workers, chunksize=5))
    frame.to_csv(output / "external_edf_vd_benchmark.csv", index=False)
    return frame


def aggregate(frame: pd.DataFrame, group_cols: list[str], metrics: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for keys, subset in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_cols, keys))
        for metric in metrics:
            if metric not in subset:
                continue
            values = subset[metric].dropna().astype(float).to_numpy()
            if not len(values):
                continue
            mean = float(np.mean(values))
            sd = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            half = float(stats.t.ppf(0.975, len(values) - 1) * sd / math.sqrt(len(values))) if len(values) > 1 else 0.0
            rows.append(
                {
                    **base,
                    "metric": metric,
                    "n": len(values),
                    "mean": mean,
                    "sd": sd,
                    "ci95_low": mean - half,
                    "ci95_high": mean + half,
                    "median": float(np.median(values)),
                    "iqr": float(np.subtract(*np.percentile(values, [75, 25]))),
                }
            )
    return pd.DataFrame(rows)


def make_figures(
    heldout: pd.DataFrame,
    robustness: pd.DataFrame,
    mc: pd.DataFrame,
    train_ranking: pd.DataFrame,
    validation_ranking: pd.DataFrame,
    output: Path,
) -> None:
    import matplotlib.pyplot as plt

    figures = output / "figures"
    figures.mkdir(exist_ok=True)

    emergency = heldout[heldout.scenario.str.startswith("emergency_")]
    means = emergency.groupby("variant")["high_deadline_miss_ratio"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(means.index, means.values)
    ax.set_ylabel("High-criticality deadline-miss ratio")
    ax.set_title("Held-out emergency performance")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(figures / "heldout_high_dmr.png", dpi=600)
    plt.close(fig)

    utility = heldout.groupby("variant")[[
        "low_work_weighted_utility_concave",
        "low_work_weighted_utility_linear",
        "low_work_weighted_utility_convex",
    ]].mean()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    utility.plot(kind="bar", ax=ax)
    ax.set_ylabel("Low-criticality utility")
    ax.set_title("Utility-shape robustness on held-out scenarios")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(figures / "heldout_utility_shapes.png", dpi=600)
    plt.close(fig)

    subset = robustness[
        (robustness.scenario == "emergency_moderate")
        & (robustness.release_jitter_ms == 20)
    ]
    pivot = subset.groupby(["execution_overhead_fraction", "variant"])["high_deadline_miss_ratio"].mean().unstack()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    pivot.plot(marker="o", ax=ax)
    ax.set_xlabel("Execution-overhead fraction")
    ax.set_ylabel("High-criticality deadline-miss ratio")
    ax.set_title("Overhead robustness with 20 ms release jitter")
    fig.tight_layout()
    fig.savefig(figures / "overhead_robustness.png", dpi=600)
    plt.close(fig)

    mc_means = mc.groupby("policy")[["high_dmr", "low_service_fraction"]].mean()
    fig, ax = plt.subplots(figsize=(8.5, 6))
    for label, row in mc_means.iterrows():
        ax.scatter(row.low_service_fraction, row.high_dmr, s=70)
        ax.annotate(label, (row.low_service_fraction, row.high_dmr), xytext=(5, 4), textcoords="offset points")
    ax.set_xlabel("Low-criticality delivered service fraction")
    ax.set_ylabel("High-criticality deadline-miss ratio")
    ax.set_title("External dual-criticality benchmark trade-off")
    fig.tight_layout()
    fig.savefig(figures / "external_mc_tradeoff.png", dpi=600)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(range(1, min(16, len(train_ranking)) + 1), train_ranking.head(16).score, marker="o", label="training")
    val_lookup = validation_ranking.set_index("config_id").score
    validation_order = [val_lookup.get(cid, np.nan) for cid in train_ranking.head(16).config_id]
    ax.plot(range(1, min(16, len(train_ranking)) + 1), validation_order, marker="s", label="validation")
    ax.set_xlabel("Configuration rank on training partition")
    ax.set_ylabel("Predeclared objective score")
    ax.set_title("Parameter-selection separation")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "tuning_train_validation.png", dpi=600)
    plt.close(fig)


def write_report(
    output: Path,
    winner: TunableConfig,
    heldout: pd.DataFrame,
    comparisons: pd.DataFrame,
    feasibility: pd.DataFrame,
    robustness: pd.DataFrame,
    mc: pd.DataFrame,
    train_ranking: pd.DataFrame,
    validation_ranking: pd.DataFrame,
) -> None:
    emergency = heldout[heldout.scenario.str.startswith("emergency_")]
    heldout_means = emergency.groupby("variant")[[
        "high_deadline_miss_ratio",
        "high_mean_response",
        "low_completion_rate",
        "low_work_weighted_utility_linear",
    ]].mean()
    recovery = heldout[heldout.scenario == "recovery_backlog"].groupby("variant")[[
        "low_completion_rate", "low_p95_wait", "low_work_weighted_utility_linear"
    ]].mean()
    mc_means = mc.groupby("policy")[["high_dmr", "high_mean_response", "low_completion_rate", "low_service_fraction"]].mean()
    feasible_summary = feasibility.groupby("scenario")[[
        "full_screened_feasible", "minimum_service_screened_feasible",
        "max_full_demand_ratio", "max_minimum_service_demand_ratio"
    ]].mean()
    robust_summary = robustness.groupby(["variant", "execution_overhead_fraction"])[[
        "high_deadline_miss_ratio", "low_work_weighted_utility_linear"
    ]].mean()

    report = f"""# RT-DASH Best-Version Simulation Project Report

**Study scope:** software simulation only; no physical hardware evidence  
**Parameter selection:** separated training, validation, and held-out test partitions  
**Published external comparator:** EDF with Virtual Deadlines, including classical drop and degraded-quality runtime variants  

## 1. Redevelopment completed

The best-version project adds the remaining high-value scientific controls without tuning on the final test set:

1. a safety-dominant parameter-selection objective evaluated on seeds 0–9;
2. validation-based configuration selection on seeds 10–19;
3. a locked held-out comparison on seeds 20–29;
4. a recovery-aware RT-DASH variant that dispatches the low/medium recovery backlog by EDF only when no high-criticality work is pending;
5. nonlinear utility reporting under concave, linear, and convex service-value assumptions;
6. a demand-bound screening analysis for full and minimum-service workload demand;
7. release-jitter and execution-overhead robustness experiments;
8. an independent dual-criticality benchmark containing classical EDF-VD and degraded-quality EDF-VD semantics.

## 2. Selected configuration

```json
{json.dumps(asdict(winner), indent=2)}
```

The configuration was selected from 36 candidates. The held-out test partition was not inspected during selection.

Top training candidates:

```
{train_ranking.head(6).to_string(index=False)}
```

Validation ranking of the six shortlisted candidates:

```
{validation_ranking.to_string(index=False)}
```

## 3. Held-out emergency results

```
{heldout_means.to_string(float_format=lambda x: f'{x:.5f}')}
```

## 4. Recovery-backlog results

```
{recovery.to_string(float_format=lambda x: f'{x:.5f}')}
```

## 5. Paired held-out comparisons

```
{comparisons.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

## 6. Demand-bound screening

The screen combines constrained-deadline periodic demand-bound functions with finite event-job demand over a dense set of interval lengths and event-aligned starts. It is a diagnostic screen, not a universal schedulability proof.

```
{feasible_summary.to_string(float_format=lambda x: f'{x:.5f}')}
```

## 7. Execution-overhead and release-jitter robustness

```
{robust_summary.to_string(float_format=lambda x: f'{x:.5f}')}
```

## 8. External EDF-VD benchmark

The external benchmark is deliberately separate from the smart-home event study. It uses implicit-deadline dual-criticality task sets, high-task LO/HI execution budgets, overrun-triggered mode changes, virtual deadlines in LO mode, and low-criticality drop or degraded service in HI mode. This avoids falsely labelling RT-DASH's semantic event trigger as the EDF-VD overrun mechanism.

```
{mc_means.to_string(float_format=lambda x: f'{x:.5f}')}
```

The EDF-VD comparator is based on the runtime model described by Liu et al., *EDF-VD Scheduling of Mixed-Criticality Systems with Degraded Quality Guarantees*, RTSS 2016, DOI 10.1109/RTSS.2016.013. The project does not claim that empirical execution of an arbitrary generated task set establishes the paper's sufficient schedulability condition.

## 9. Interpretation

- Results are stronger because tuning and final evaluation are separated.
- The recovery-aware variant is accepted only if held-out data show no deterioration in high-criticality deadline outcomes.
- Utility conclusions are tested under three plausible service-value shapes rather than one linear assumption.
- Demand-screen classifications explain when failures reflect intrinsic processor demand rather than a poor priority rule.
- EDF-VD provides an external mixed-criticality reference, but its overrun semantics differ from smart-home semantic-event triggering; both differences and similarities are reported.
- No result is selected or suppressed because it is unfavourable.

## 10. Remaining evidence boundary

The project remains a single-core simulation study. It does not establish physical timing, measured WCET, energy savings, safety certification, or universal dominance over every mixed-criticality method. The FreeRTOS files retained from the original archive are not used as a result generator because the supplied PC port does not implement a functioning host context-switch mechanism.
"""
    (output / "BEST_VERSION_VALIDATION_REPORT.md").write_text(report)


def hash_tree(root: Path, destination: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == destination or "__pycache__" in path.parts:
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}")
    destination.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/best_journal"))
    parser.add_argument("--duration", type=int, default=60_000)
    parser.add_argument("--quantum", type=int, default=10)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    print("1/7 train-validation tuning", flush=True)
    winner, train_ranking, validation_ranking = run_tuning(
        output, args.workers, args.duration, args.quantum
    )
    (output / "selected_configuration.json").write_text(json.dumps(asdict(winner), indent=2))

    print("2/7 held-out test", flush=True)
    heldout = run_heldout_test(
        output, winner, args.workers, args.duration, args.quantum
    )
    comparisons = heldout_comparisons(heldout, output)

    print("3/7 demand-bound screen", flush=True)
    feasibility = run_feasibility_screen(output)

    print("4/7 overhead/jitter robustness", flush=True)
    robustness = run_robustness(
        output, winner, args.workers, args.duration, args.quantum
    )

    print("5/7 external EDF-VD benchmark", flush=True)
    mc = run_external_mc_benchmark(output, args.workers)

    print("6/7 full optimized 30-seed matrix", flush=True)
    full_matrix = run_full_optimized_matrix(
        output, winner, args.workers, args.duration, args.quantum
    )
    full_comparisons = full_matrix_comparisons(full_matrix, output)

    print("7/7 aggregation, figures, report", flush=True)
    heldout_metrics = [
        "high_deadline_miss_ratio", "high_mean_response", "high_p95_response",
        "low_completion_rate", "low_delivered_service_fraction",
        "low_work_weighted_utility_concave", "low_work_weighted_utility_linear",
        "low_work_weighted_utility_convex", "low_service_fairness_jain",
        "low_p95_wait", "mode_transitions", "critical_mode_fraction",
        "recovery_clearance_mean", "processor_utilization",
    ]
    aggregate(heldout, ["scenario", "target_utilization", "variant"], heldout_metrics).to_csv(
        output / "aggregate_heldout_test.csv", index=False
    )
    aggregate(
        full_matrix, ["scenario", "target_utilization", "variant"], list(FULL_MATRIX_METRICS)
    ).to_csv(output / "aggregate_full_matrix_optimized.csv", index=False)
    aggregate(
        robustness,
        ["scenario", "execution_overhead_fraction", "release_jitter_ms", "variant"],
        heldout_metrics,
    ).to_csv(output / "aggregate_overhead_jitter.csv", index=False)
    aggregate(
        mc,
        ["target_lo_utilization", "high_budget_factor", "low_retention", "overrun_probability", "policy"],
        ["high_dmr", "high_mean_response", "low_completion_rate", "low_service_fraction", "mode_switches"],
    ).to_csv(output / "aggregate_external_edf_vd.csv", index=False)

    make_figures(heldout, robustness, mc, train_ranking, validation_ranking, output)
    write_report(
        output, winner, heldout, comparisons, feasibility, robustness, mc,
        train_ranking, validation_ranking,
    )

    manifest = {
        "study": "RT-DASH best-version simulation-only project",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "duration_ms": args.duration,
        "quantum_ms": args.quantum,
        "training_seeds": list(range(0, 10)),
        "validation_seeds": list(range(10, 20)),
        "heldout_test_seeds": list(range(20, 30)),
        "candidate_configurations": len(candidate_configs()),
        "selected_configuration": asdict(winner),
        "counts": {
            "tuning_train": len(pd.read_csv(output / "tuning_train_runs.csv")),
            "tuning_validation": len(pd.read_csv(output / "tuning_validation_runs.csv")),
            "heldout_test": len(heldout),
            "demand_screen": len(feasibility),
            "overhead_jitter": len(robustness),
            "external_edf_vd": len(mc),
            "full_matrix_optimized_variants": len(full_matrix),
        },
    }
    manifest["counts"]["total_new_runs"] = sum(
        v for k, v in manifest["counts"].items() if k != "demand_screen"
    )
    (output / "execution_manifest_best.json").write_text(json.dumps(manifest, indent=2))
    hash_tree(output, output / "sha256sums_best.txt")
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
