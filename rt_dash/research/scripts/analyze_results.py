#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def aggregate(frame: pd.DataFrame, group: list[str], metrics: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for key, subset in frame.groupby(group, dropna=False):
        keys = key if isinstance(key, tuple) else (key,)
        base = dict(zip(group, keys))
        for metric in metrics:
            values = subset[metric].dropna().astype(float)
            n = len(values)
            mean = values.mean() if n else np.nan
            sd = values.std(ddof=1) if n > 1 else 0.0 if n == 1 else np.nan
            half = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n) if n > 1 else 0.0 if n == 1 else np.nan
            rows.append(
                {
                    **base,
                    "metric": metric,
                    "n": n,
                    "mean": mean,
                    "sd": sd,
                    "ci95_low": mean - half if n else np.nan,
                    "ci95_high": mean + half if n else np.nan,
                }
            )
    return pd.DataFrame(rows)


def paired(frame: pd.DataFrame, left: str, right: str, metric: str) -> dict[str, object]:
    index = ["target_utilization", "seed"]
    wide = frame.pivot_table(index=index, columns="policy", values=metric, aggfunc="first")
    values = (wide[left] - wide[right]).dropna().astype(float)
    n = len(values)
    mean = values.mean()
    sd = values.std(ddof=1) if n > 1 else 0.0
    half = stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n) if n > 1 else 0.0
    dz = mean / sd if sd > 0 else np.inf if mean != 0 else 0.0
    return {
        "left_policy": left,
        "right_policy": right,
        "metric": metric,
        "definition": "left minus right on matched load/seed runs",
        "n_pairs": n,
        "mean_difference": mean,
        "sd_difference": sd,
        "ci95_low": mean - half,
        "ci95_high": mean + half,
        "cohen_dz": dz,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path(__file__).resolve().parents[1] / "results")
    args = parser.parse_args()
    results = args.results
    output = results / "statistics"
    output.mkdir(parents=True, exist_ok=True)

    controlled = pd.read_csv(results / "controlled_summary.csv")
    metrics = [
        "high_deadline_miss_ratio",
        "high_completion_rate",
        "high_mean_response",
        "low_completion_rate",
        "low_deadline_miss_ratio",
        "mode_transitions",
        "service_reduction",
        "processor_utilization",
        "context_switches",
    ]
    aggregate(controlled, ["policy", "target_utilization"], metrics).to_csv(
        output / "controlled_aggregate_ci.csv", index=False
    )

    comparisons = [
        paired(controlled, "rt_dash", "edf", "high_deadline_miss_ratio"),
        paired(controlled, "rt_dash", "rms", "high_deadline_miss_ratio"),
        paired(controlled, "rt_dash", "edf", "high_mean_response"),
        paired(controlled, "rt_dash", "rms", "high_mean_response"),
        paired(controlled, "rt_dash_no_hysteresis", "rt_dash", "mode_transitions"),
        paired(controlled, "rt_dash", "rt_dash_no_degradation", "low_completion_rate"),
    ]
    pd.DataFrame(comparisons).to_csv(output / "paired_comparisons.csv", index=False)

    trace_file = results / "trace_summary.csv"
    if trace_file.exists():
        trace = pd.read_csv(trace_file)
        trace_metrics = [metric for metric in metrics if metric in trace.columns]
        aggregate(trace, ["policy", "start_row", "load_scale"], trace_metrics).to_csv(
            output / "trace_aggregate_ci.csv", index=False
        )


if __name__ == "__main__":
    main()
