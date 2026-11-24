#!/usr/bin/env python3
"""Reproduce the manuscript's principal seed-clustered inference.

The analysis unit is the independent simulation seed.  Within each comparison,
matched scenario/load cells are first differenced and then averaged within seed.
Percentile intervals use 10,000 bootstrap resamples from one deterministic random
number stream initialized with seed 20260709.  Comparisons are evaluated in the
predeclared order below so that the archived values are bit-for-bit reproducible
with NumPy 2.3.5.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


BOOTSTRAP_SEED = 20260709
BOOTSTRAP_RESAMPLES = 10_000
PAIR_KEYS = ["scenario", "target_utilization", "seed"]
EMERGENCY_SCENARIOS = {
    "emergency_mild",
    "emergency_moderate",
    "emergency_severe",
}
ADAPTIVE_SCENARIOS = EMERGENCY_SCENARIOS | {
    "optional_service_stress",
    "overload",
    "prolonged_emergency",
    "recovery_backlog",
}


@dataclass(frozen=True)
class Comparison:
    study: str
    comparison: str
    left: str
    right: str
    metric: str
    scope: str


HELD_OUT = [
    Comparison("held_out", "recovery_minus_edf_high_dmr", "rt_dash_recovery_edf_tuned", "edf", "high_deadline_miss_ratio", "three_emergency_families"),
    Comparison("held_out", "recovery_minus_rms_high_dmr", "rt_dash_recovery_edf_tuned", "rms", "high_deadline_miss_ratio", "three_emergency_families"),
    Comparison("held_out", "tuned_minus_default_low_linear_utility", "rt_dash_tuned", "rt_dash_default", "low_work_weighted_utility_linear", "all_seven_held_out_cells"),
    Comparison("held_out", "recovery_minus_tuned_low_completion", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_completion_rate", "all_seven_held_out_cells"),
    Comparison("held_out", "recovery_minus_tuned_low_p95_wait", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_p95_wait", "all_seven_held_out_cells"),
    Comparison("held_out", "recovery_minus_criticality_edf_low_linear_utility", "rt_dash_recovery_edf_tuned", "criticality_edf", "low_work_weighted_utility_linear", "all_seven_held_out_cells"),
]

CONTROLLED = [
    Comparison("controlled", "rt_dash_minus_no_event_trigger_high_dmr", "rt_dash", "rt_dash_no_event_trigger", "high_deadline_miss_ratio", "three_emergency_families"),
    Comparison("controlled", "no_hysteresis_minus_rt_dash_transitions", "rt_dash_no_hysteresis", "rt_dash", "mode_transitions", "threshold_chatter"),
    Comparison("controlled", "rt_dash_minus_no_degradation_low_completion", "rt_dash", "rt_dash_no_degradation", "low_completion_rate", "optional_service_stress"),
    Comparison("controlled", "rt_dash_minus_criticality_edf_low_completion", "rt_dash", "criticality_edf", "low_completion_rate", "adaptive_scenarios"),
]

FULL_MATRIX = [
    Comparison("full_matrix", "recovery_minus_tuned_high_dmr", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "high_deadline_miss_ratio", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_low_completion", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_completion_rate", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_low_concave_utility", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_work_weighted_utility_concave", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_low_linear_utility", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_work_weighted_utility_linear", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_low_convex_utility", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_work_weighted_utility_convex", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_low_jain_fairness", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_service_fairness_jain", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_low_p95_wait", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "low_p95_wait", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_mode_transitions", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "mode_transitions", "all_28_cells"),
    Comparison("full_matrix", "recovery_minus_tuned_critical_fraction", "rt_dash_recovery_edf_tuned", "rt_dash_tuned", "critical_mode_fraction", "all_28_cells"),
]


def select_scope(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "three_emergency_families":
        return frame[frame["scenario"].isin(EMERGENCY_SCENARIOS)]
    if scope == "threshold_chatter":
        return frame[frame["scenario"] == "threshold_chatter"]
    if scope == "optional_service_stress":
        return frame[frame["scenario"] == "optional_service_stress"]
    if scope == "adaptive_scenarios":
        return frame[frame["scenario"].isin(ADAPTIVE_SCENARIOS)]
    return frame


def paired_seed_means(frame: pd.DataFrame, spec: Comparison, label_column: str) -> tuple[pd.DataFrame, int]:
    scoped = select_scope(frame, spec.scope)
    left = scoped[scoped[label_column] == spec.left][PAIR_KEYS + [spec.metric]].rename(columns={spec.metric: "left_value"})
    right = scoped[scoped[label_column] == spec.right][PAIR_KEYS + [spec.metric]].rename(columns={spec.metric: "right_value"})
    paired = left.merge(right, on=PAIR_KEYS, how="inner", validate="one_to_one")
    # A pair is valid only when the metric is defined for both policies.  This
    # matters for high-criticality metrics in routine/overload/chatter cells
    # that release no high-criticality jobs.
    paired = paired.dropna(subset=["left_value", "right_value"])
    if paired.empty:
        raise ValueError(f"no matched pairs for {spec.comparison}")
    paired["difference"] = paired["left_value"] - paired["right_value"]
    seeds = paired.groupby("seed", as_index=False)["difference"].mean().sort_values("seed")
    seeds.insert(0, "comparison", spec.comparison)
    seeds.insert(0, "study", spec.study)
    return seeds, len(paired)


def analyze(seed_rows: pd.DataFrame, pair_count: int, spec: Comparison, rng: np.random.Generator) -> dict[str, object]:
    values = seed_rows["difference"].to_numpy(dtype=float)
    indices = rng.integers(0, len(values), size=(BOOTSTRAP_RESAMPLES, len(values)))
    bootstrap_means = values[indices].mean(axis=1)
    ci_low, ci_high = np.quantile(bootstrap_means, [0.025, 0.975])
    if np.all(values == 0):
        statistic = np.nan
        p_value = np.nan
        test_status = "not_applicable_all_zero"
    else:
        test = stats.wilcoxon(values, alternative="two-sided")
        statistic = float(test.statistic)
        p_value = float(test.pvalue)
        test_status = "computed"
    return {
        "study": spec.study,
        "comparison": spec.comparison,
        "scope": spec.scope,
        "left": spec.left,
        "right": spec.right,
        "metric": spec.metric,
        "difference_definition": "left_minus_right",
        "matched_pairs": pair_count,
        "seed_clusters": len(values),
        "mean_difference": float(values.mean()),
        "bootstrap_ci95_low": float(ci_low),
        "bootstrap_ci95_high": float(ci_high),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "wilcoxon_statistic": statistic,
        "wilcoxon_p_two_sided": p_value,
        "wilcoxon_status": test_status,
    }


def main() -> None:
    package_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=package_root / "research" / "results")
    parser.add_argument("--output", type=Path, default=package_root / "research" / "results" / "seed_clustered_inference")
    args = parser.parse_args()

    held = pd.read_csv(args.results_root / "best_journal" / "heldout_test_runs.csv")
    controlled = pd.read_csv(args.results_root / "journal_strengthened" / "controlled_runs_v2.csv")
    full = pd.read_csv(args.results_root / "best_journal" / "full_matrix_optimized_variants.csv")
    studies = [(held, "variant", HELD_OUT), (controlled, "policy", CONTROLLED), (full, "variant", FULL_MATRIX)]

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    summaries: list[dict[str, object]] = []
    seed_tables: list[pd.DataFrame] = []
    for frame, label_column, specs in studies:
        for spec in specs:
            seed_rows, pair_count = paired_seed_means(frame, spec, label_column)
            summaries.append(analyze(seed_rows, pair_count, spec, rng))
            seed_tables.append(seed_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summaries)
    summary.to_csv(args.output / "seed_clustered_inference.csv", index=False, float_format="%.12g")
    pd.concat(seed_tables, ignore_index=True).to_csv(args.output / "seed_level_paired_means.csv", index=False, float_format="%.12g")
    for study in summary["study"].unique():
        summary[summary["study"] == study].to_csv(args.output / f"{study}_inference.csv", index=False, float_format="%.12g")
    print(summary[["study", "comparison", "matched_pairs", "seed_clusters", "mean_difference", "bootstrap_ci95_low", "bootstrap_ci95_high", "wilcoxon_p_two_sided"]].to_string(index=False))


if __name__ == "__main__":
    main()
