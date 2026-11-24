from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from .metrics import job_records, summarize_result
from .policies import PolicyName
from .simulator import SimulationConfig, Simulator
from .workloads import emergency_releases, scaled_periodic_taskset, trace_window_events


def run_controlled(
    output_dir: Path,
    duration: int,
    load_levels: Iterable[float],
    seeds: Iterable[int],
    policies: Iterable[PolicyName],
    quantum: int = 5,
    save_jobs: bool = False,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    all_jobs: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    for load in load_levels:
        for seed in seeds:
            tasks = scaled_periodic_taskset(load, seed)
            events = emergency_releases(seed)
            for policy in policies:
                config = SimulationConfig(duration=duration, policy=policy, quantum=quantum)
                result = Simulator(tasks, events, config).run()
                summary = summarize_result(result)
                summary.update({"scenario": "controlled", "target_utilization": load, "seed": seed})
                summaries.append(summary)
                if save_jobs:
                    for record in job_records(result):
                        record.update({"scenario": "controlled", "target_utilization": load, "seed": seed})
                        all_jobs.append(record)
                for transition in result.transitions:
                    transitions.append(
                        {
                            "scenario": "controlled",
                            "target_utilization": load,
                            "seed": seed,
                            "policy": policy.value,
                            "time": transition.time,
                            "old_mode": transition.old_mode.value,
                            "new_mode": transition.new_mode.value,
                            "reason": transition.reason,
                            "smoothed_utilization": transition.smoothed_utilization,
                        }
                    )
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(output_dir / "controlled_summary.csv", index=False)
    if save_jobs:
        pd.DataFrame(all_jobs).to_csv(output_dir / "controlled_jobs.csv", index=False)
    pd.DataFrame(transitions).to_csv(output_dir / "controlled_transitions.csv", index=False)
    return summary_df


def run_trace(
    output_dir: Path,
    csv_path: Path,
    start_rows: Iterable[int],
    rows: int,
    load_scales: Iterable[float],
    policies: Iterable[PolicyName],
    quantum: int = 5,
    save_jobs: bool = False,
    time_scale: int = 100,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    all_jobs: list[dict[str, object]] = []
    for start in start_rows:
        for scale in load_scales:
            events = trace_window_events(csv_path, start, rows, time_scale=time_scale, load_scale=scale)
            duration = max(e.release_time for e in events) + 2_000
            duration += (-duration) % quantum
            for policy in policies:
                config = SimulationConfig(duration=duration, policy=policy, quantum=quantum)
                result = Simulator([], events, config).run()
                summary = summarize_result(result)
                summary.update(
                    {
                        "scenario": "trace",
                        "start_row": start,
                        "rows": rows,
                        "load_scale": scale,
                    }
                )
                summaries.append(summary)
                if save_jobs:
                    for record in job_records(result):
                        record.update(
                            {
                                "scenario": "trace",
                                "start_row": start,
                                "rows": rows,
                                "load_scale": scale,
                            }
                        )
                        all_jobs.append(record)
    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(output_dir / "trace_summary.csv", index=False)
    if save_jobs:
        pd.DataFrame(all_jobs).to_csv(output_dir / "trace_jobs.csv", index=False)
    return summary_df


def parse_policy_list(value: str) -> list[PolicyName]:
    return [PolicyName(part.strip()) for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible RT-DASH experiments")
    parser.add_argument("--output", type=Path, default=Path("research/results"))
    parser.add_argument("--duration", type=int, default=60_000)
    parser.add_argument("--quantum", type=int, default=5)
    parser.add_argument("--seeds", default="0,1,2,3,4,5,6,7,8,9")
    parser.add_argument("--loads", default="0.6,0.8,0.95,1.1,1.25")
    parser.add_argument(
        "--policies",
        default="edf,rms,rt_dash,rt_dash_no_hysteresis,rt_dash_no_degradation",
    )
    parser.add_argument("--trace-csv", type=Path)
    parser.add_argument("--trace-starts", default="0,160400,963496")
    parser.add_argument("--trace-rows", type=int, default=600)
    parser.add_argument("--trace-scales", default="0.8,1.0,1.2")
    parser.add_argument("--save-jobs", action="store_true")
    args = parser.parse_args()

    seeds = [int(x) for x in args.seeds.split(",") if x]
    loads = [float(x) for x in args.loads.split(",") if x]
    policies = parse_policy_list(args.policies)
    controlled = run_controlled(args.output, args.duration, loads, seeds, policies, args.quantum, args.save_jobs)
    print(controlled.groupby("policy")["high_deadline_miss_ratio"].mean())

    if args.trace_csv:
        starts = [int(x) for x in args.trace_starts.split(",") if x]
        scales = [float(x) for x in args.trace_scales.split(",") if x]
        trace = run_trace(args.output, args.trace_csv, starts, args.trace_rows, scales, policies, args.quantum, args.save_jobs)
        print(trace.groupby("policy")["high_deadline_miss_ratio"].mean())

    manifest = {
        "duration": args.duration,
        "quantum": args.quantum,
        "seeds": seeds,
        "loads": loads,
        "policies": [p.value for p in policies],
        "trace_csv": str(args.trace_csv) if args.trace_csv else None,
    }
    (args.output / "experiment_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
