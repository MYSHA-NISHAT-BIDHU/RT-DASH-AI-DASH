from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from rt_dash.metrics import summarize_result
from rt_dash.model import Criticality, TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import SimulationConfig, Simulator
from rt_dash.workloads import emergency_profile_releases, scaled_periodic_taskset


TRAIN_SEEDS = tuple(range(30, 40))
VALIDATION_SEEDS = tuple(range(40, 50))
TEST_SEEDS = tuple(range(50, 60))
SEVERITIES = ("mild", "moderate", "severe")
TUNING_LOADS = (0.75, 0.90)
STRESS_LOADS = (0.50, 0.65, 0.80, 0.95, 1.10)
DURATION_MS = 30_000
EVENT_TIMES_MS = (8_000, 20_000)


def nominal_low_demand(tasks: list[TaskSpec], duration: int) -> tuple[int, int]:
    releases = 0
    work = 0
    for task in tasks:
        if task.criticality is not Criticality.LOW or task.period is None:
            continue
        if task.phase >= duration:
            count = 0
        else:
            count = 1 + (duration - 1 - task.phase) // task.period
        releases += count
        work += count * task.wcet
    return releases, work


def make_config(
    policy: PolicyName,
    *,
    quantum: int,
    stretch: float = 2.0,
    shrink: float = 0.5,
    recovery_window: int = 1_000,
) -> SimulationConfig:
    return SimulationConfig(
        duration=DURATION_MS,
        quantum=quantum,
        policy=policy,
        observation_window=1_000,
        smoothing_samples=5,
        monitor_interval=100,
        utilization_high=0.90,
        utilization_low=0.80,
        entry_hold=200,
        recovery_hold=500,
        period_stretch_factor=stretch,
        period_shrink_factor=shrink,
        period_recovery_window=recovery_window,
    )


def run_case(
    seed: int,
    severity: str,
    load: float,
    policy: PolicyName,
    *,
    stretch: float = 2.0,
    shrink: float = 0.5,
    recovery_window: int = 1_000,
    blocking_ms: int = 0,
    quantum: int = 5,
    event_times: tuple[int, int] = EVENT_TIMES_MS,
) -> dict[str, object]:
    tasks = scaled_periodic_taskset(load, seed)
    if blocking_ms:
        tasks = [
            replace(
                task,
                blocking_time=(
                    min(blocking_ms, task.wcet)
                    if task.criticality is not Criticality.HIGH
                    else task.blocking_time
                ),
            )
            for task in tasks
        ]
    events = emergency_profile_releases(seed, severity, times=event_times)
    result = Simulator(
        tasks,
        events,
        make_config(
            policy,
            quantum=quantum,
            stretch=stretch,
            shrink=shrink,
            recovery_window=recovery_window,
        ),
    ).run()
    summary = summarize_result(result)
    nominal_releases, nominal_work = nominal_low_demand(tasks, DURATION_MS)
    executed_low = float(summary.get("low_executed_work") or 0.0)
    actual_releases = int(summary.get("low_released") or 0)
    high_response = summary.get("high_mean_response")
    return {
        "seed": seed,
        "severity": severity,
        "target_utilization": load,
        "policy": policy.value,
        "blocking_ms": blocking_ms,
        "period_stretch_factor": stretch,
        "period_shrink_factor": shrink,
        "period_recovery_window_ms": recovery_window,
        "high_dmr": float(summary.get("high_deadline_miss_ratio") or 0.0),
        "high_response_ms": float(high_response) if high_response is not None else math.nan,
        "high_p95_response_ms": float(summary.get("high_p95_response") or math.nan),
        "low_completion_rate": float(summary.get("low_completion_rate") or 0.0),
        "low_linear_utility": float(summary.get("low_work_weighted_utility_linear") or 0.0),
        "low_nominal_service_fraction": executed_low / nominal_work if nominal_work else math.nan,
        "low_actual_release_fraction": actual_releases / nominal_releases if nominal_releases else math.nan,
        "mode_transitions": int(summary.get("mode_transitions") or 0),
        "critical_mode_fraction": float(summary.get("critical_mode_fraction") or 0.0),
        "period_stretched_intervals": int(summary.get("period_stretched_intervals") or 0),
        "period_shrunk_intervals": int(summary.get("period_shrunk_intervals") or 0),
    }


def safety_dominant_score(frame: pd.DataFrame) -> float:
    response = frame.high_response_ms.fillna(1_000.0).clip(upper=1_000.0).mean()
    service = frame.low_nominal_service_fraction.clip(upper=1.0).mean()
    return float(100.0 * frame.high_dmr.mean() + response / 1_000.0 + (1.0 - service))


def tune_period_control() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    candidates = [
        (stretch, shrink, window)
        for stretch in (1.5, 2.0, 3.0)
        for shrink in (0.50, 0.75)
        for window in (500, 1_000)
    ]
    train_rows: list[dict[str, object]] = []
    for stretch, shrink, window in candidates:
        candidate_id = f"s{stretch:.1f}_r{shrink:.2f}_w{window}"
        for seed in TRAIN_SEEDS:
            for severity in SEVERITIES:
                for load in TUNING_LOADS:
                    row = run_case(
                        seed,
                        severity,
                        load,
                        PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF,
                        stretch=stretch,
                        shrink=shrink,
                        recovery_window=window,
                    )
                    row["candidate_id"] = candidate_id
                    row["split"] = "train"
                    train_rows.append(row)
    train = pd.DataFrame(train_rows)
    ranking = []
    for candidate_id, group in train.groupby("candidate_id", sort=True):
        first = group.iloc[0]
        ranking.append(
            {
                "candidate_id": candidate_id,
                "period_stretch_factor": first.period_stretch_factor,
                "period_shrink_factor": first.period_shrink_factor,
                "period_recovery_window_ms": int(first.period_recovery_window_ms),
                "train_score": safety_dominant_score(group),
                "train_high_dmr": group.high_dmr.mean(),
                "train_low_nominal_service_fraction": group.low_nominal_service_fraction.mean(),
            }
        )
    train_ranking = pd.DataFrame(ranking).sort_values(
        ["train_score", "candidate_id"]
    ).reset_index(drop=True)
    shortlist = train_ranking.head(6)

    validation_rows: list[dict[str, object]] = []
    for candidate in shortlist.itertuples(index=False):
        for seed in VALIDATION_SEEDS:
            for severity in SEVERITIES:
                for load in TUNING_LOADS:
                    row = run_case(
                        seed,
                        severity,
                        load,
                        PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF,
                        stretch=float(candidate.period_stretch_factor),
                        shrink=float(candidate.period_shrink_factor),
                        recovery_window=int(candidate.period_recovery_window_ms),
                    )
                    row["candidate_id"] = candidate.candidate_id
                    row["split"] = "validation"
                    validation_rows.append(row)
    validation = pd.DataFrame(validation_rows)
    validation_ranking = []
    for candidate_id, group in validation.groupby("candidate_id", sort=True):
        first = group.iloc[0]
        validation_ranking.append(
            {
                "candidate_id": candidate_id,
                "period_stretch_factor": first.period_stretch_factor,
                "period_shrink_factor": first.period_shrink_factor,
                "period_recovery_window_ms": int(first.period_recovery_window_ms),
                "validation_score": safety_dominant_score(group),
                "validation_high_dmr": group.high_dmr.mean(),
                "validation_low_nominal_service_fraction": group.low_nominal_service_fraction.mean(),
            }
        )
    validation_ranking_frame = pd.DataFrame(validation_ranking).sort_values(
        ["validation_score", "candidate_id"]
    ).reset_index(drop=True)
    selected = validation_ranking_frame.iloc[0]
    selected_config = {
        "candidate_id": str(selected.candidate_id),
        "period_stretch_factor": float(selected.period_stretch_factor),
        "period_shrink_factor": float(selected.period_shrink_factor),
        "period_recovery_window_ms": int(selected.period_recovery_window_ms),
        "selection_rule": "minimum validation score: 100*high_DMR + capped_high_response/1000 + (1-capped_nominal_low_service)",
        "train_seeds": list(TRAIN_SEEDS),
        "validation_seeds": list(VALIDATION_SEEDS),
        "heldout_test_seeds": list(TEST_SEEDS),
        "test_used_for_selection": False,
    }
    return train_ranking, validation_ranking_frame, selected_config


def run_period_test(selected: dict[str, object]) -> pd.DataFrame:
    policies = (
        PolicyName.RT_DASH_RECOVERY_EDF,
        PolicyName.RT_DASH_PERIOD_RECOVERY_EDF,
        PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF,
    )
    rows = []
    for seed in TEST_SEEDS:
        for severity in SEVERITIES:
            for load in TUNING_LOADS:
                for policy in policies:
                    row = run_case(
                        seed,
                        severity,
                        load,
                        policy,
                        stretch=float(selected["period_stretch_factor"]),
                        shrink=float(selected["period_shrink_factor"]),
                        recovery_window=int(selected["period_recovery_window_ms"]),
                    )
                    row["split"] = "heldout_test"
                    rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_seed_ci(differences: pd.DataFrame, metric: str) -> tuple[float, float]:
    by_seed = differences.groupby("seed", sort=True)[metric].mean()
    values = by_seed.to_numpy(dtype=float)
    rng = np.random.default_rng(20260806)
    means = np.empty(10_000, dtype=float)
    for index in range(len(means)):
        means[index] = rng.choice(values, size=len(values), replace=True).mean()
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def paired_period_comparisons(frame: pd.DataFrame) -> pd.DataFrame:
    comparisons = []
    keys = ["seed", "severity", "target_utilization"]
    metrics = ("high_dmr", "high_response_ms", "low_nominal_service_fraction")
    pairs = (
        (PolicyName.RT_DASH_PERIOD_RECOVERY_EDF.value, PolicyName.RT_DASH_RECOVERY_EDF.value),
        (PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF.value, PolicyName.RT_DASH_RECOVERY_EDF.value),
    )
    for left, right in pairs:
        left_frame = frame[frame.policy == left].set_index(keys)
        right_frame = frame[frame.policy == right].set_index(keys)
        for metric in metrics:
            paired = pd.concat(
                [left_frame[metric].rename("left"), right_frame[metric].rename("right")],
                axis=1,
                join="inner",
            ).dropna()
            paired["difference"] = paired.left - paired.right
            indexed = paired.reset_index()
            ci_low, ci_high = bootstrap_seed_ci(indexed, "difference")
            differences = paired.difference.to_numpy(dtype=float)
            pvalue = (
                float(stats.wilcoxon(differences, zero_method="zsplit").pvalue)
                if np.any(np.abs(differences) > 1e-12)
                else 1.0
            )
            comparisons.append(
                {
                    "left": left,
                    "right": right,
                    "metric": metric,
                    "n_cells": len(paired),
                    "n_seed_clusters": indexed.seed.nunique(),
                    "mean_difference": differences.mean(),
                    "seed_cluster_bootstrap_ci95_low": ci_low,
                    "seed_cluster_bootstrap_ci95_high": ci_high,
                    "wilcoxon_p": pvalue,
                }
            )
    output = pd.DataFrame(comparisons)
    order = np.argsort(output.wilcoxon_p.to_numpy())
    adjusted = np.empty(len(output), dtype=float)
    running = 0.0
    m = len(output)
    for rank, index in enumerate(order):
        value = min(1.0, float(output.iloc[index].wilcoxon_p) * (m - rank))
        running = max(running, value)
        adjusted[index] = running
    output["holm_p"] = adjusted
    return output


def run_blocking_study() -> pd.DataFrame:
    rows = []
    for blocking in (0, 2, 5, 10):
        for seed in TEST_SEEDS:
            for severity in ("moderate", "severe"):
                for load in TUNING_LOADS:
                    for policy in (
                        PolicyName.EDF,
                        PolicyName.CRITICALITY_EDF,
                        PolicyName.RT_DASH_RECOVERY_EDF,
                    ):
                        row = run_case(
                            seed,
                            severity,
                            load,
                            policy,
                            blocking_ms=blocking,
                            quantum=1,
                            # Offset emergency release one millisecond after
                            # dense periodic release boundaries. This creates
                            # an explicit contention stress case in which a
                            # low/medium job can already be inside its bounded
                            # non-preemptive prefix when the safety event arrives.
                            event_times=(8_001, 20_001),
                        )
                        row["study"] = "bounded_nonpreemptive_blocking"
                        rows.append(row)
    return pd.DataFrame(rows)


def run_stress_surface(selected: dict[str, object]) -> pd.DataFrame:
    rows = []
    for seed in TEST_SEEDS:
        for severity in SEVERITIES:
            for load in STRESS_LOADS:
                for policy in (
                    PolicyName.EDF,
                    PolicyName.CRITICALITY_EDF,
                    PolicyName.RT_DASH_RECOVERY_EDF,
                    PolicyName.RT_DASH_PERIOD_SERVICE_RECOVERY_EDF,
                ):
                    row = run_case(
                        seed,
                        severity,
                        load,
                        policy,
                        stretch=float(selected["period_stretch_factor"]),
                        shrink=float(selected["period_shrink_factor"]),
                        recovery_window=int(selected["period_recovery_window_ms"]),
                    )
                    row["study"] = "stress_surface"
                    rows.append(row)
    return pd.DataFrame(rows)


def aggregate(frame: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    metrics = [
        "high_dmr",
        "high_response_ms",
        "low_nominal_service_fraction",
        "low_actual_release_fraction",
        "critical_mode_fraction",
        "mode_transitions",
    ]
    rows: list[dict[str, object]] = []
    for keys, block in frame.groupby(groups, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(groups, keys))
        row["n"] = len(block)
        for metric in metrics:
            values = block[metric].dropna().to_numpy(dtype=float)
            row[f"{metric}_mean"] = float(values.mean()) if len(values) else math.nan
            row[f"{metric}_sd"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def make_figures(
    output: Path,
    period_test: pd.DataFrame,
    blocking: pd.DataFrame,
    stress: pd.DataFrame,
) -> None:
    figure_dir = output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    period_agg = aggregate(period_test, ["policy"])
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.scatter(
        period_agg.low_nominal_service_fraction_mean,
        period_agg.high_dmr_mean,
        s=90,
    )
    for row in period_agg.itertuples(index=False):
        ax.annotate(row.policy.replace("rt_dash_", ""),
                    (row.low_nominal_service_fraction_mean, row.high_dmr_mean),
                    xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Low-criticality delivered work / nominal demand")
    ax.set_ylabel("High-criticality deadline-miss ratio")
    ax.set_title("Held-out period-control safety/service trade-off")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_dir / "period_control_tradeoff.png", dpi=240)
    fig.savefig(figure_dir / "period_control_tradeoff.svg")
    plt.close(fig)

    blocking_agg = aggregate(blocking, ["policy", "blocking_ms"])
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    for policy, group in blocking_agg.groupby("policy", sort=True):
        ax.plot(group.blocking_ms, group.high_response_ms_mean, marker="o", label=policy)
    ax.set_xlabel("Modeled initial non-preemptive section (ms)")
    ax.set_ylabel("Mean high-criticality response (ms)")
    ax.set_title("Synchronization/blocking robustness")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(figure_dir / "blocking_robustness.png", dpi=240)
    fig.savefig(figure_dir / "blocking_robustness.svg")
    plt.close(fig)

    stress_agg = aggregate(stress, ["policy", "target_utilization", "severity"])
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.0), sharey=True)
    for axis, severity in zip(axes, SEVERITIES):
        subset = stress_agg[stress_agg.severity == severity]
        for policy, group in subset.groupby("policy", sort=True):
            axis.plot(group.target_utilization, group.high_dmr_mean, marker="o", label=policy)
        axis.set_title(severity.title())
        axis.set_xlabel("Nominal periodic utilization")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("High-criticality deadline-miss ratio")
    axes[-1].legend(fontsize=6, loc="upper left")
    fig.suptitle("Safety envelope across load and emergency severity")
    fig.tight_layout()
    fig.savefig(figure_dir / "stress_surface_high_dmr.png", dpi=240)
    fig.savefig(figure_dir / "stress_surface_high_dmr.svg")
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(
    output: Path,
    selected: dict[str, object],
    period_test: pd.DataFrame,
    comparisons: pd.DataFrame,
    blocking: pd.DataFrame,
    stress: pd.DataFrame,
) -> None:
    period_agg = aggregate(period_test, ["policy"])
    blocking_agg = aggregate(blocking, ["policy", "blocking_ms"])
    stress_agg = aggregate(stress, ["policy", "target_utilization", "severity"])
    text = f"""# Simulation-Only Thesis Completion and Stress Report

## Scope and lock discipline

This additive study closes simulation-side mechanisms that were described in the
original thesis but were not part of the locked principal RT-DASH result. It does
not modify or replace the 15,780-run deterministic evidence or the locked AI
held-out test. Period-control parameters use new seeds 30--39 for training and
40--49 for validation; seeds 50--59 are held out until the final comparison.

No hardware, physical timing, WCET, or energy claim is made.

## Selected period-control configuration

```json
{json.dumps(selected, indent=2)}
```

The safety-dominant selection score is declared in `selected_period_control.json`.
Completion rates are not allowed to hide reduced release frequency: all period
policies are additionally scored by executed low-criticality work divided by the
nominal work that the unadapted task set would have requested.

## Held-out period-control result

```
{period_agg.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

## Paired held-out comparisons

```
{comparisons.to_string(index=False, float_format=lambda x: f'{x:.6g}')}
```

## Synchronization/blocking robustness

The thesis's unspecified synchronization term is operationalized here as a
bounded initial non-preemptive section for low/medium periodic jobs. Mode entry
can still occur immediately, but a newly released high-criticality job may be
blocked until the running non-preemptive section ends. This is a stress model,
not a claim that it reconstructs an unavailable historical lock protocol.

```
{blocking_agg.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

## Safety envelope

New held-out seeds are evaluated across nominal periodic utilization 0.50--1.10
and mild/moderate/severe emergency families. The surface is a failure-boundary
map; infeasible cells are retained rather than removed.

```
{stress_agg.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

## Interpretation rule

True period stretching/shrinking is now executable and auditable, but the
recovery-aware service-control policy remains the principal Paper 1 result unless
the new held-out evidence justifies a stronger bounded claim. The new mechanism
is never promoted merely because it generates fewer low-criticality jobs.
"""
    (output / "SIMULATION_COMPLETION_VALIDATION_REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/simulation_completion"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    train_ranking, validation_ranking, selected = tune_period_control()
    train_ranking.to_csv(output / "period_tuning_train_ranking.csv", index=False)
    validation_ranking.to_csv(output / "period_tuning_validation_ranking.csv", index=False)
    (output / "selected_period_control.json").write_text(
        json.dumps(selected, indent=2) + "\n", encoding="utf-8"
    )

    period_test = run_period_test(selected)
    period_test.to_csv(output / "period_heldout_test.csv", index=False)
    comparisons = paired_period_comparisons(period_test)
    comparisons.to_csv(output / "period_heldout_paired_comparisons.csv", index=False)

    blocking = run_blocking_study()
    blocking.to_csv(output / "blocking_robustness.csv", index=False)
    stress = run_stress_surface(selected)
    stress.to_csv(output / "stress_surface.csv", index=False)

    aggregate(period_test, ["policy"]).to_csv(
        output / "period_heldout_aggregate.csv", index=False
    )
    aggregate(blocking, ["policy", "blocking_ms"]).to_csv(
        output / "blocking_aggregate.csv", index=False
    )
    aggregate(stress, ["policy", "target_utilization", "severity"]).to_csv(
        output / "stress_surface_aggregate.csv", index=False
    )

    make_figures(output, period_test, blocking, stress)
    write_report(output, selected, period_test, comparisons, blocking, stress)

    artifacts = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS_SIMULATION_COMPLETION.txt"
    )
    manifest = {
        "study": "simulation-only thesis completion and stress",
        "train_seeds": list(TRAIN_SEEDS),
        "validation_seeds": list(VALIDATION_SEEDS),
        "heldout_test_seeds": list(TEST_SEEDS),
        "period_tuning_candidate_count": 12,
        "test_used_for_selection": False,
        "hardware_used": False,
        "period_tuning_train_runs": 720,
        "period_tuning_validation_runs": 360,
        "period_test_runs": int(len(period_test)),
        "blocking_runs": int(len(blocking)),
        "stress_surface_runs": int(len(stress)),
        "new_simulation_runs_total": 2340,
        "project_scheduler_simulations_total": 18750,
        "selected_period_control": selected,
    }
    (output / "simulation_completion_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    artifacts.append(output / "simulation_completion_manifest.json")
    lines = [f"{sha256(path)}  {path.relative_to(output)}" for path in sorted(set(artifacts))]
    (output / "SHA256SUMS_SIMULATION_COMPLETION.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("SIMULATION COMPLETION STUDY: DONE")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
