#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_POLICIES = {
    "edf",
    "rms",
    "criticality_edf",
    "rt_dash",
    "rt_dash_no_hysteresis",
    "rt_dash_no_degradation",
    "rt_dash_no_event_trigger",
    "rt_dash_no_load_trigger",
    "rt_dash_no_recovery_hold",
}
EXPECTED_SCENARIO_CELLS = 28
EXPECTED_SEEDS = 30


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "results" / "journal_strengthened"
    controlled = pd.read_csv(root / "controlled_runs_v2.csv")
    sensitivity = pd.read_csv(root / "parameter_sensitivity.csv")
    scalability = pd.read_csv(root / "scalability_study.csv")
    trace = pd.read_csv(root / "trace_mapping_robustness.csv")
    comparisons = pd.read_csv(root / "paired_comparisons_v2.csv")

    require(len(controlled) == EXPECTED_SCENARIO_CELLS * EXPECTED_SEEDS * len(EXPECTED_POLICIES), "controlled run count mismatch")
    require(set(controlled.policy.unique()) == EXPECTED_POLICIES, "policy set mismatch")
    require(controlled.seed.nunique() == EXPECTED_SEEDS, "seed count mismatch")
    require(len(sensitivity) == 880, "sensitivity run count mismatch")
    require(len(scalability) == 450, "scalability run count mismatch")
    require(len(trace) == 90, "trace robustness run count mismatch")

    counts = controlled.groupby("policy").size()
    require(counts.nunique() == 1, "policies are not balanced")
    require(counts.iloc[0] == EXPECTED_SCENARIO_CELLS * EXPECTED_SEEDS, "per-policy count mismatch")

    bounded = [
        "processor_utilization",
        "high_deadline_miss_ratio",
        "low_completion_rate",
        "low_delivered_service_fraction",
        "critical_mode_fraction",
    ]
    for column in bounded:
        values = controlled[column].dropna()
        require(bool(((values >= -1e-12) & (values <= 1 + 1e-12)).all()), f"{column} outside [0,1]")

    # Workload descriptors must be identical across policies for every matched cell.
    key = ["scenario", "target_utilization", "seed"]
    for column in ["actual_periodic_utilization", "event_jobs", "event_work", "high_event_work", "max_event_density"]:
        variation = controlled.groupby(key)[column].nunique(dropna=False)
        require(bool((variation == 1).all()), f"matched workload differs across policies for {column}")

    # RT-DASH and static criticality-first should have identical high-criticality
    # outcomes when both enter the same dispatch order immediately.
    emergency = controlled[
        controlled.scenario.str.startswith("emergency_")
        | (controlled.scenario == "prolonged_emergency")
    ]
    wide = emergency.pivot_table(index=key, columns="policy", values="high_deadline_miss_ratio", aggfunc="first")
    require(np.allclose(wide["rt_dash"], wide["criticality_edf"], equal_nan=True), "criticality dispatch parity failed")

    require((comparisons.n_pairs > 0).all(), "empty paired comparison")
    require((root / "cpp_host_simulation_v2.csv").exists(), "missing C++ parity output")
    require(len(list((root / "figures").glob("*.png"))) >= 10, "too few generated figures")

    manifest = json.loads((root / "execution_manifest_v2.json").read_text())
    require(manifest["counts"]["controlled"] == len(controlled), "manifest controlled count mismatch")
    require(manifest["counts"]["total"] == len(controlled) + len(sensitivity) + len(scalability) + len(trace), "manifest total mismatch")

    print("Journal-strengthened result verification passed")
    print({
        "controlled": len(controlled),
        "sensitivity": len(sensitivity),
        "scalability": len(scalability),
        "trace": len(trace),
        "total": len(controlled) + len(sensitivity) + len(scalability) + len(trace),
    })


if __name__ == "__main__":
    main()
