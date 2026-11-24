#!/usr/bin/env python3
"""Reproduce the 30-seed optimized RT-DASH full-matrix evidence.

This script closes a reproducibility gap in the archived best-version package:
the raw full-matrix CSVs were present and validated, but their dedicated generator
was not exposed as an executable script.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np
import json
import pandas as pd
from scipy import stats

from rt_dash.policies import PolicyName
from run_best_journal_study import (
    TunableConfig,
    _parallel_map,
    _run_configured,
    aggregate,
    bootstrap_ci,
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

METRICS: tuple[str, ...] = (
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

COMPARISON_METRICS: tuple[str, ...] = METRICS[:-1]


def run_matrix(
    output: Path,
    config: TunableConfig,
    workers: int,
    duration: int,
    quantum: int,
) -> pd.DataFrame:
    variants = (
        (PolicyName.RT_DASH, "rt_dash_tuned"),
        (PolicyName.RT_DASH_RECOVERY_EDF, "rt_dash_recovery_edf_tuned"),
    )
    work = [
        (scenario, load, seed, policy.value, config, duration, quantum, label)
        for scenario, load in FULL_MATRIX_CELLS
        for seed in range(30)
        for policy, label in variants
    ]
    frame = pd.DataFrame(_parallel_map(_run_configured, work, workers, chunksize=8))
    frame.to_csv(output / "full_matrix_optimized_variants.csv", index=False)
    return frame


def paired_row(frame: pd.DataFrame, scope: str, metric: str) -> dict[str, object] | None:
    left = "rt_dash_recovery_edf_tuned"
    right = "rt_dash_tuned"
    if metric.startswith("high_"):
        frame = frame[frame[metric].notna()]
    wide = frame.pivot_table(
        index=["scenario", "target_utilization", "seed"],
        columns="variant",
        values=metric,
        aggfunc="first",
    )
    if left not in wide or right not in wide:
        return None
    diff = (wide[left] - wide[right]).dropna().to_numpy(dtype=float)
    if diff.size == 0:
        return None
    low, high = bootstrap_ci(diff)
    try:
        pvalue = float(stats.wilcoxon(diff, zero_method="zsplit").pvalue)
    except ValueError:
        pvalue = math.nan
    return {
        "scope": scope,
        "left": left,
        "right": right,
        "metric": metric,
        "n_pairs": int(diff.size),
        "mean_difference": float(np.mean(diff)),
        "ci95_low": low,
        "ci95_high": high,
        "wilcoxon_p": pvalue,
    }


def comparisons(frame: pd.DataFrame) -> pd.DataFrame:
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
        for metric in COMPARISON_METRICS:
            row = paired_row(subset, scope, metric)
            if row is not None:
                rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results/best_journal"))
    parser.add_argument("--configuration", type=Path, default=Path("results/best_journal/selected_configuration.json"))
    parser.add_argument("--duration", type=int, default=60_000)
    parser.add_argument("--quantum", type=int, default=10)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    config_data = json.loads(args.configuration.read_text())
    config = TunableConfig(**{k: int(v) if k in {"entry_hold", "recovery_hold", "observation_window", "smoothing_samples"} else float(v) for k, v in config_data.items()})

    frame = run_matrix(output, config, args.workers, args.duration, args.quantum)
    aggregate(frame, ["scenario", "target_utilization", "variant"], list(METRICS)).to_csv(
        output / "aggregate_full_matrix_optimized.csv", index=False
    )
    comparisons(frame).to_csv(output / "full_matrix_optimized_comparisons.csv", index=False)

    print({
        "configuration": asdict(config),
        "cells": len(FULL_MATRIX_CELLS),
        "seeds": 30,
        "variants": 2,
        "executed_runs": len(frame),
    })


if __name__ == "__main__":
    main()
