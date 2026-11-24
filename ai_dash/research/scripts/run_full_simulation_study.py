#!/usr/bin/env python3
"""Execute the complete simulation-only RT-DASH study.

This runner deliberately excludes physical hardware and firmware claims. It
executes matched Python discrete-event simulations for EDF, RMS, full RT-DASH,
a static criticality-first baseline, and two RT-DASH ablations across controlled and trace-derived workloads.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import hashlib
import json
import math
import multiprocessing
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from rt_dash.experiments import run_trace
from rt_dash.metrics import job_records, summarize_result
from rt_dash.model import Criticality, TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import EventRelease, SimulationConfig, Simulator
from rt_dash.workloads import emergency_releases, scaled_periodic_taskset, trace_window_events

POLICIES = list(PolicyName)


def _high_event(task_id: str, release: int, wcet: int = 90, deadline: int = 180) -> EventRelease:
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
            source="controlled_prolonged_emergency",
        ),
        release,
    )


def _medium_burst(seed: int, start: int, count: int, spacing: int = 50) -> list[EventRelease]:
    rng = np.random.default_rng(50_000 + seed + start)
    events: list[EventRelease] = []
    for index in range(count):
        wcet = int(rng.integers(50, 90))
        task = TaskSpec(
            task_id=f"burst_m_{start}_{index}",
            name="Transient sensor-analysis burst",
            wcet=wcet,
            relative_deadline=250,
            criticality=Criticality.MEDIUM,
            degradable=False,
            min_service_fraction=1.0,
            memory=8,
            bandwidth=3,
            source="controlled_threshold_burst",
        )
        events.append(EventRelease(task, start + index * spacing))
    return events


def _low_backlog(seed: int, start: int, count: int, spacing: int = 30) -> list[EventRelease]:
    rng = np.random.default_rng(70_000 + seed)
    events: list[EventRelease] = []
    for index in range(count):
        wcet = int(rng.integers(35, 70))
        task = TaskSpec(
            task_id=f"backlog_l_{index}",
            name="Deferred comfort-service request",
            wcet=wcet,
            relative_deadline=1_500,
            criticality=Criticality.LOW,
            degradable=True,
            min_service_fraction=0.3,
            memory=8,
            bandwidth=2,
            source="controlled_recovery_backlog",
        )
        events.append(EventRelease(task, start + index * spacing))
    return events


def scenario_events(name: str, seed: int) -> list[EventRelease]:
    if name in {"routine", "overload"}:
        return []
    if name == "transient_emergency":
        return emergency_releases(seed)
    if name == "prolonged_emergency":
        events: list[EventRelease] = []
        for burst, (start, stop) in enumerate(((15_000, 22_000), (39_000, 44_000))):
            for index, release in enumerate(range(start, stop, 250)):
                events.append(_high_event(f"prolonged_h_{burst}_{index}", release, 85 + (index % 4) * 5, 200))
        return events
    if name == "threshold_chatter":
        events: list[EventRelease] = []
        for start in range(5_000, 55_000, 800):
            events.extend(_medium_burst(seed, start, count=4, spacing=50))
        return events
    if name == "recovery_backlog":
        events = emergency_releases(seed, times=(20_000,))
        events.extend(_low_backlog(seed, 19_800, count=40, spacing=40))
        return events
    raise ValueError(f"unknown scenario: {name}")


SCENARIOS: dict[str, list[float]] = {
    "routine": [0.50, 0.70, 0.85],
    "overload": [0.95, 1.10, 1.25],
    "transient_emergency": [0.70, 0.90, 1.10],
    "prolonged_emergency": [0.80, 1.00],
    "threshold_chatter": [0.75],
    "recovery_backlog": [0.90],
}


def _run_one_controlled(args: tuple[str, float, int, str, int, int, bool]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    scenario, load, seed, policy_value, duration, quantum, save_jobs = args
    policy = PolicyName(policy_value)
    tasks = scaled_periodic_taskset(load, seed)
    events = scenario_events(scenario, seed)
    config = SimulationConfig(duration=duration, policy=policy, quantum=quantum)
    result = Simulator(tasks, events, config).run()
    row = summarize_result(result)
    row.update({"scenario": scenario, "target_utilization": load, "seed": seed, "event_jobs": len(events)})
    transitions = [
        {
            "scenario": scenario,
            "target_utilization": load,
            "seed": seed,
            "policy": policy.value,
            "time": item.time,
            "old_mode": item.old_mode.value,
            "new_mode": item.new_mode.value,
            "reason": item.reason,
            "smoothed_utilization": item.smoothed_utilization,
        }
        for item in result.transitions
    ]
    jobs: list[dict[str, object]] = []
    if save_jobs:
        for record in job_records(result):
            record.update({"scenario": scenario, "target_utilization": load, "seed": seed})
            jobs.append(record)
    return row, transitions, jobs


def run_controlled_full(
    output: Path,
    seeds: Iterable[int],
    duration: int,
    quantum: int,
    workers: int,
) -> pd.DataFrame:
    work: list[tuple[str, float, int, str, int, int, bool]] = []
    seed_values = list(seeds)
    for scenario, loads in SCENARIOS.items():
        for load in loads:
            for seed in seed_values:
                for policy in POLICIES:
                    work.append((scenario, load, seed, policy.value, duration, quantum, seed == 0 and load == loads[0]))

    summaries: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    representative_jobs: list[dict[str, object]] = []
    if workers <= 1:
        iterator = map(_run_one_controlled, work)
        for index, (row, run_transitions, jobs) in enumerate(iterator, start=1):
            summaries.append(row)
            transitions.extend(run_transitions)
            representative_jobs.extend(jobs)
            if index % 50 == 0 or index == len(work):
                print(f"controlled progress: {index}/{len(work)}", flush=True)
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as executor:
            for index, (row, run_transitions, jobs) in enumerate(executor.map(_run_one_controlled, work, chunksize=2), start=1):
                summaries.append(row)
                transitions.extend(run_transitions)
                representative_jobs.extend(jobs)
                if index % 50 == 0 or index == len(work):
                    print(f"controlled progress: {index}/{len(work)}", flush=True)

    frame = pd.DataFrame(summaries)
    frame.to_csv(output / "all_controlled_runs.csv", index=False)
    pd.DataFrame(transitions).to_csv(output / "all_mode_transitions.csv", index=False)
    pd.DataFrame(representative_jobs).to_csv(output / "representative_job_traces.csv", index=False)
    return frame


def _ci(values: pd.Series) -> tuple[int, float, float, float, float]:
    from scipy import stats
    x = values.dropna().astype(float)
    n = len(x)
    if n == 0:
        return 0, math.nan, math.nan, math.nan, math.nan
    mean = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    half = float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n)) if n > 1 else 0.0
    return n, mean, sd, mean - half, mean + half


def aggregate_results(controlled: pd.DataFrame, trace: pd.DataFrame, output: Path) -> None:
    metrics = [
        "high_deadline_miss_ratio",
        "high_completion_rate",
        "high_mean_response",
        "high_p95_response",
        "low_completion_rate",
        "low_deadline_miss_ratio",
        "low_delivered_service_fraction",
        "overall_completion_rate",
        "overall_deadline_miss_ratio",
        "overall_mean_wait",
        "overall_p95_response",
        "overall_backlog_at_horizon",
        "processor_utilization",
        "context_switches",
        "mode_transitions",
        "critical_mode_fraction",
        "service_reduction",
    ]
    rows: list[dict[str, object]] = []
    for key, subset in controlled.groupby(["scenario", "target_utilization", "policy"], dropna=False):
        scenario, load, policy = key
        for metric in metrics:
            n, mean, sd, low, high = _ci(subset[metric])
            rows.append(
                {
                    "source": "controlled",
                    "scenario": scenario,
                    "load": load,
                    "policy": policy,
                    "metric": metric,
                    "n": n,
                    "mean": mean,
                    "sd": sd,
                    "ci95_low": low,
                    "ci95_high": high,
                }
            )
    if not trace.empty:
        for key, subset in trace.groupby(["start_row", "load_scale", "policy"], dropna=False):
            start, scale, policy = key
            for metric in metrics:
                if metric not in subset.columns:
                    continue
                n, mean, sd, low, high = _ci(subset[metric])
                rows.append(
                    {
                        "source": "trace",
                        "scenario": f"trace_start_{start}",
                        "load": scale,
                        "policy": policy,
                        "metric": metric,
                        "n": n,
                        "mean": mean,
                        "sd": sd,
                        "ci95_low": low,
                        "ci95_high": high,
                    }
                )
    pd.DataFrame(rows).to_csv(output / "aggregate_results_with_ci.csv", index=False)


def paired_comparisons(controlled: pd.DataFrame, output: Path) -> pd.DataFrame:
    from scipy import stats
    comparisons = [
        ("rt_dash", "edf", "high_deadline_miss_ratio", "all"),
        ("rt_dash", "rms", "high_deadline_miss_ratio", "all"),
        ("rt_dash", "edf", "high_mean_response", "emergency"),
        ("rt_dash", "rms", "high_mean_response", "emergency"),
        ("rt_dash", "criticality_edf", "high_deadline_miss_ratio", "emergency"),
        ("rt_dash", "criticality_edf", "high_mean_response", "emergency"),
        ("rt_dash", "criticality_edf", "low_completion_rate", "adaptive"),
        ("rt_dash", "criticality_edf", "low_delivered_service_fraction", "adaptive"),
        ("criticality_edf", "edf", "high_deadline_miss_ratio", "emergency"),
        ("rt_dash_no_hysteresis", "rt_dash", "mode_transitions", "threshold_chatter"),
        ("rt_dash", "rt_dash_no_degradation", "low_completion_rate", "adaptive"),
        ("rt_dash", "rt_dash_no_degradation", "low_delivered_service_fraction", "adaptive"),
        ("rt_dash", "rt_dash_no_degradation", "high_deadline_miss_ratio", "adaptive"),
    ]
    rows: list[dict[str, object]] = []
    for left, right, metric, scope in comparisons:
        data = controlled.copy()
        if scope == "emergency":
            data = data[data["scenario"].isin(["transient_emergency", "prolonged_emergency", "recovery_backlog"])]
        elif scope == "threshold_chatter":
            data = data[data["scenario"] == "threshold_chatter"]
        elif scope == "adaptive":
            data = data[data["scenario"].isin(["overload", "transient_emergency", "prolonged_emergency", "recovery_backlog"])]
        wide = data.pivot_table(
            index=["scenario", "target_utilization", "seed"],
            columns="policy",
            values=metric,
            aggfunc="first",
        )
        if left not in wide.columns or right not in wide.columns:
            continue
        differences = (wide[left] - wide[right]).dropna().astype(float)
        n, mean, sd, low, high = _ci(differences)
        if n > 0 and np.any(differences != 0):
            try:
                wilcoxon_stat, wilcoxon_p = stats.wilcoxon(differences)
            except ValueError:
                wilcoxon_stat, wilcoxon_p = math.nan, math.nan
        else:
            wilcoxon_stat, wilcoxon_p = math.nan, math.nan
        rows.append(
            {
                "scope": scope,
                "left_policy": left,
                "right_policy": right,
                "metric": metric,
                "definition": "left minus right on identical scenario/load/seed",
                "n_pairs": n,
                "mean_difference": mean,
                "sd_difference": sd,
                "ci95_low": low,
                "ci95_high": high,
                "cohen_dz": mean / sd if sd > 0 else (math.inf if mean != 0 else 0.0),
                "wilcoxon_statistic": wilcoxon_stat,
                "wilcoxon_p": wilcoxon_p,
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(output / "paired_policy_comparisons.csv", index=False)
    return result


def make_figures(controlled: pd.DataFrame, output: Path) -> None:
    import matplotlib.pyplot as plt
    figure_dir = output / "figures"
    figure_dir.mkdir(exist_ok=True)
    plot_specs = [
        ("high_deadline_miss_ratio", "High-criticality deadline-miss ratio"),
        ("high_mean_response", "High-criticality mean response time (ms)"),
        ("low_completion_rate", "Low-criticality completion rate"),
        ("low_delivered_service_fraction", "Low-criticality delivered service fraction"),
        ("mode_transitions", "Mode transitions per run"),
        ("critical_mode_fraction", "Fraction of run in Critical Mode"),
        ("overall_backlog_at_horizon", "Backlog at simulation horizon"),
        ("context_switches", "Context switches per run"),
    ]
    for metric, ylabel in plot_specs:
        grouped = controlled.groupby(["scenario", "policy"], as_index=False)[metric].mean()
        pivot = grouped.pivot(index="scenario", columns="policy", values=metric)
        ax = pivot.plot(kind="bar", figsize=(12, 6))
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Scenario")
        ax.set_title(ylabel + " across simulation scenarios")
        ax.legend(title="Policy", fontsize=8)
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        plt.savefig(figure_dir / f"{metric}.png", dpi=300)
        plt.close()


def write_report(
    controlled: pd.DataFrame,
    trace: pd.DataFrame,
    comparisons: pd.DataFrame,
    output: Path,
    seeds: list[int],
    duration: int,
    quantum: int,
) -> None:
    policy_runs = controlled.groupby("policy").size().to_dict()
    overall = controlled.groupby("policy").agg(
        high_dmr=("high_deadline_miss_ratio", "mean"),
        high_response=("high_mean_response", "mean"),
        low_completion=("low_completion_rate", "mean"),
        low_service=("low_delivered_service_fraction", "mean"),
        transitions=("mode_transitions", "mean"),
        utilization=("processor_utilization", "mean"),
    )
    comparison_lines = []
    for _, row in comparisons.iterrows():
        comparison_lines.append(
            f"- {row['scope']}: `{row['left_policy']} - {row['right_policy']}` for "
            f"`{row['metric']}` = {row['mean_difference']:.6g} "
            f"(95% CI {row['ci95_low']:.6g} to {row['ci95_high']:.6g}, n={int(row['n_pairs'])})."
        )

    report = f"""# RT-DASH Complete Simulation Execution Report

**Execution timestamp (UTC):** {datetime.now(timezone.utc).isoformat()}  
**Study type:** software simulation only; no hardware or physical-device measurements  
**Python:** {platform.python_version()}  
**Run duration:** {duration} ms per controlled run  
**Scheduling quantum:** {quantum} ms  
**Seeds:** {', '.join(map(str, seeds))}

## 1. Executed project scope

The complete project was executed as a reproducible single-core, preemptive software simulation. The experiment matrix includes EDF, RMS, a static criticality-first baseline, full RT-DASH, RT-DASH without hysteresis, and RT-DASH without low-criticality degradation. All policies receive identical task releases for every matched scenario, load, and seed.

The controlled study covers routine load, processor overload, transient emergencies, prolonged emergencies, threshold-sensitive oscillation, and post-emergency recovery backlog. A separate study replays contiguous OpenSHS-derived trace windows at three modelled load scales.

## 2. Run counts

- Controlled runs: **{len(controlled)}**
- Trace-derived runs: **{len(trace)}**
- Total simulations: **{len(controlled) + len(trace)}**
- Controlled runs per policy: **{policy_runs}**

## 3. Mean results across all controlled scenarios

```
{overall.to_string(float_format=lambda x: f'{x:.6f}')}
```

These cross-scenario means are descriptive only. The scenario/load-specific CSV and confidence intervals are the correct evidence for detailed interpretation.

## 4. Matched policy comparisons

{chr(10).join(comparison_lines)}

A negative difference means the left policy produced a lower value than the right policy. For deadline-miss ratio and response time, a negative difference is favourable. For completion or delivered-service fraction, a positive difference is favourable.

## 5. Scientific interpretation

- Full RT-DASH is evaluated as an adaptive scheduling policy, not as a proof of hard real-time schedulability.
- EDF and RMS are algorithm baselines using the same releases and execution budgets.
- The no-hysteresis ablation isolates switching stability.
- The no-degradation ablation isolates the service-quality/schedulability trade-off.
- Completion of a degraded job does not mean full service was delivered; `delivered_service_fraction` and `service_reduction` must be reported with completion rate.
- Trace-derived execution budgets and deadlines are explicit modelling choices because the original project did not preserve measured WCET or deadline mappings.
- CPU utilization, timing, memory, bandwidth, and service results are simulated/model-derived. They are not hardware measurements.

## 6. Reproducibility outputs

- `all_controlled_runs.csv`: one row per controlled simulation.
- `trace_runs.csv`: one row per trace-derived simulation.
- `all_mode_transitions.csv`: every RT-DASH mode transition.
- `representative_job_traces.csv`: complete per-job records for matched representative runs.
- `aggregate_results_with_ci.csv`: means, standard deviations, and 95% confidence intervals.
- `paired_policy_comparisons.csv`: matched differences and Wilcoxon tests.
- `figures/`: publication-quality plots generated from result CSVs.
- `execution_manifest.json`: exact scenarios, policies, seeds, and runtime environment.
- `sha256sums.txt`: hashes for code and result artifacts.

## 7. Evidence boundary

This package completes and executes the simulation research project. It does not claim physical-board performance, measured energy consumption, device-driver interference, or hardware WCET. Those topics are outside the explicitly simulation-only study requested here.
"""
    (output / "SIMULATION_EXECUTION_REPORT.md").write_text(report)


def sha256_tree(root: Path, output_file: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == output_file:
            continue
        if any(part in {".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root)}")
    output_file.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/full_simulation"))
    parser.add_argument("--seeds", default="0,1,2,3,4,5,6,7,8,9")
    parser.add_argument("--duration", type=int, default=60_000)
    parser.add_argument("--quantum", type=int, default=5)
    parser.add_argument("--trace-csv", type=Path, default=Path("../data/raw/smart_home_dataset.csv"))
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    seeds = [int(value) for value in args.seeds.split(",") if value]

    controlled = run_controlled_full(output, seeds, args.duration, args.quantum, args.workers)
    print("stage: controlled complete", flush=True)

    trace_output = output / "trace_temp"
    trace = run_trace(
        trace_output,
        args.trace_csv.resolve(),
        start_rows=[0, 160_466, 83_000],
        rows=60,
        load_scales=[0.8, 1.2, 1.6],
        policies=POLICIES,
        quantum=args.quantum,
        save_jobs=False,
        time_scale=20,
    )
    trace.to_csv(output / "trace_runs.csv", index=False)
    print("stage: trace complete", flush=True)

    # Preserve complete job-level traces for one representative trace window
    # under every policy without writing all trace jobs for all 60 runs.
    representative_trace_records: list[dict[str, object]] = []
    representative_events = trace_window_events(
        args.trace_csv.resolve(), 160_466, 60, time_scale=20, load_scale=1.2
    )
    representative_duration = max(event.release_time for event in representative_events) + 2_000
    representative_duration += (-representative_duration) % args.quantum
    for policy in POLICIES:
        representative_result = Simulator(
            [], representative_events,
            SimulationConfig(duration=representative_duration, policy=policy, quantum=args.quantum),
        ).run()
        for record in job_records(representative_result):
            record.update({"start_row": 160466, "rows": 60, "load_scale": 1.2})
            representative_trace_records.append(record)
    pd.DataFrame(representative_trace_records).to_csv(output / "trace_job_traces.csv", index=False)
    print("stage: representative trace complete", flush=True)

    # Preserve no temporary duplicate summaries.
    for path in trace_output.glob("*"):
        path.unlink()
    trace_output.rmdir()

    aggregate_results(controlled, trace, output)
    print("stage: aggregate complete", flush=True)
    comparisons = paired_comparisons(controlled, output)
    print("stage: comparisons complete", flush=True)
    make_figures(controlled, output)
    print("stage: figures complete", flush=True)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "study": "simulation-only RT-DASH full execution",
        "hardware_used": False,
        "duration_ms": args.duration,
        "quantum_ms": args.quantum,
        "seeds": seeds,
        "policies": [p.value for p in POLICIES],
        "scenarios": SCENARIOS,
        "trace": {
            "source": str(args.trace_csv.resolve()),
            "start_rows": [0, 160466, 83000],
            "rows": 60,
            "time_scale_ms_per_source_second": 20,
            "load_scales": [0.8, 1.2, 1.6],
        },
        "python": sys.version,
        "platform": platform.platform(),
        "workers": args.workers,
        "controlled_runs": len(controlled),
        "trace_runs": len(trace),
    }
    (output / "execution_manifest.json").write_text(json.dumps(manifest, indent=2))
    write_report(controlled, trace, comparisons, output, seeds, args.duration, args.quantum)
    print("stage: report complete", flush=True)
    sha256_tree(output.parent.parent, output / "sha256sums.txt")
    print("stage: hashes complete", flush=True)

    print(f"Controlled simulations: {len(controlled)}")
    print(f"Trace simulations: {len(trace)}")
    print(f"Total simulations: {len(controlled) + len(trace)}")
    print(f"Results: {output}")


if __name__ == "__main__":
    main()
