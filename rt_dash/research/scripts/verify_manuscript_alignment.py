#!/usr/bin/env python3
"""Verify that archived evidence reproduces every numerical manuscript table.

This preflight check is intentionally independent of the simulation unit tests. It
checks the published run inventory, locked configuration, Tables 4--11, the exact
input-data identity, final figure assets, and compiled-firmware evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "results"


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def require_rounded(actual: float, expected: float, digits: int, label: str) -> None:
    if round(float(actual), digits) != expected:
        fail(
            f"{label}: expected {expected} at {digits} decimals, "
            f"got {float(actual):.{digits}f}"
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    return len(pd.read_csv(path))


def check_table_4_inventory() -> None:
    files = {
        "controlled": (RESULTS / "journal_strengthened/controlled_runs_v2.csv", 7560),
        "sensitivity": (RESULTS / "journal_strengthened/parameter_sensitivity.csv", 880),
        "scalability": (RESULTS / "journal_strengthened/scalability_study.csv", 450),
        "trace": (RESULTS / "journal_strengthened/trace_mapping_robustness.csv", 90),
        "training": (RESULTS / "best_journal/tuning_train_runs.csv", 2520),
        "validation": (RESULTS / "best_journal/tuning_validation_runs.csv", 420),
        "held_out": (RESULTS / "best_journal/heldout_test_runs.csv", 420),
        "overhead_jitter": (RESULTS / "best_journal/overhead_jitter_robustness.csv", 960),
        "external_edf_vd": (RESULTS / "best_journal/external_edf_vd_benchmark.csv", 800),
        "optimized_matrix": (
            RESULTS / "best_journal/full_matrix_optimized_variants.csv",
            1680,
        ),
    }
    observed = {}
    for name, (path, expected) in files.items():
        observed[name] = csv_rows(path)
        require(observed[name] == expected, f"Table 4 {name} count mismatch")
    require(sum(observed.values()) == 15780, "Table 4 total must equal 15,780")
    require(
        csv_rows(RESULTS / "best_journal/demand_bound_screen.csv") == 70,
        "Demand screen must contain 70 non-simulation records",
    )


def check_table_5_configuration() -> None:
    selected = json.loads(
        (RESULTS / "best_journal/selected_configuration.json").read_text(encoding="utf-8")
    )
    expected = {
        "utilization_high": 0.90,
        "utilization_low": 0.80,
        "entry_hold": 200,
        "recovery_hold": 500,
        "observation_window": 1000,
        "smoothing_samples": 5,
    }
    require(selected == expected, "Table 5 locked configuration mismatch")


def check_table_6_held_out() -> None:
    frame = pd.read_csv(RESULTS / "best_journal/heldout_test_runs.csv")
    frame = frame[
        frame["scenario"].isin(
            ["emergency_mild", "emergency_moderate", "emergency_severe"]
        )
    ]
    metrics = [
        "high_deadline_miss_ratio",
        "high_mean_response",
        "low_completion_rate",
        "low_work_weighted_utility_linear",
    ]
    aggregate = frame.groupby("variant")[metrics].mean()
    expected = {
        "criticality_edf": (0.15675, 106.60, 0.76771, 0.90278),
        "edf": (0.62722, 250.59, 0.99736, 0.99847),
        "rms": (0.91667, 274.90, 0.85790, 0.97314),
        "rt_dash_default": (0.15675, 106.60, 0.78712, 0.90958),
        "rt_dash_tuned": (0.15675, 106.60, 0.82095, 0.92059),
        "rt_dash_recovery_edf_tuned": (0.15675, 106.60, 0.99307, 0.99413),
    }
    for variant, values in expected.items():
        require(variant in aggregate.index, f"Table 6 missing variant {variant}")
        row = aggregate.loc[variant]
        for metric, actual, expected_value, digits in zip(
            metrics, row, values, (5, 2, 5, 5), strict=True
        ):
            require_rounded(actual, expected_value, digits, f"Table 6 {variant} {metric}")


def check_tables_7_and_8_inference() -> None:
    controlled = pd.read_csv(RESULTS / "seed_clustered_inference/controlled_inference.csv")
    expected_7 = {
        "rt_dash_minus_no_event_trigger_high_dmr": (-0.1233, -0.1334, -0.1135, 4),
        "no_hysteresis_minus_rt_dash_transitions": (44.7, 44.11, 45.41, 1),
        "rt_dash_minus_no_degradation_low_completion": (0.02188, 0.02148, 0.02230, 5),
        "rt_dash_minus_criticality_edf_low_completion": (0.02009, 0.01960, 0.02059, 5),
    }
    for comparison, (mean, low, high, digits) in expected_7.items():
        rows = controlled[controlled["comparison"] == comparison]
        require(len(rows) == 1, f"Table 7 comparison missing or duplicated: {comparison}")
        row = rows.iloc[0]
        require_rounded(row["mean_difference"], mean, digits, f"Table 7 {comparison} mean")
        ci_digits = 4 if comparison.endswith("high_dmr") else (2 if "transitions" in comparison else 5)
        require_rounded(row["bootstrap_ci95_low"], low, ci_digits, f"Table 7 {comparison} CI low")
        require_rounded(row["bootstrap_ci95_high"], high, ci_digits, f"Table 7 {comparison} CI high")

    full = pd.read_csv(RESULTS / "seed_clustered_inference/full_matrix_inference.csv")
    expected_8 = {
        "recovery_minus_tuned_high_dmr": (0.00000, 0.00000, 0.00000, 510),
        "recovery_minus_tuned_low_completion": (0.18755, 0.18210, 0.19299, 840),
        "recovery_minus_tuned_low_concave_utility": (0.07842, 0.07664, 0.08023, 840),
        "recovery_minus_tuned_low_linear_utility": (0.09784, 0.09543, 0.10024, 840),
        "recovery_minus_tuned_low_convex_utility": (0.12025, 0.11711, 0.12338, 840),
        "recovery_minus_tuned_low_jain_fairness": (0.01129, 0.01075, 0.01186, 840),
        "recovery_minus_tuned_low_p95_wait": (2.81607, 2.54809, 3.08530, 840),
        "recovery_minus_tuned_mode_transitions": (-0.80714, -0.85000, -0.76190, 840),
        "recovery_minus_tuned_critical_fraction": (0.04682, 0.03975, 0.05381, 840),
    }
    for comparison, (mean, low, high, pairs) in expected_8.items():
        rows = full[full["comparison"] == comparison]
        require(len(rows) == 1, f"Table 8 comparison missing or duplicated: {comparison}")
        row = rows.iloc[0]
        require(int(row["matched_pairs"]) == pairs, f"Table 8 pair count mismatch: {comparison}")
        require(int(row["seed_clusters"]) == 30, f"Table 8 seed count mismatch: {comparison}")
        require_rounded(row["mean_difference"], mean, 5, f"Table 8 {comparison} mean")
        require_rounded(row["bootstrap_ci95_low"], low, 5, f"Table 8 {comparison} CI low")
        require_rounded(row["bootstrap_ci95_high"], high, 5, f"Table 8 {comparison} CI high")


def check_table_9_demand_screen() -> None:
    frame = pd.read_csv(RESULTS / "best_journal/demand_bound_screen.csv")
    aggregate = frame.groupby("scenario").agg(
        full=("full_screened_feasible", "mean"),
        minimum=("minimum_service_screened_feasible", "mean"),
        max_full=("max_full_demand_ratio", "max"),
        max_min=("max_minimum_service_demand_ratio", "max"),
    )
    expected = {
        "emergency_mild": (0.70, 1.00, 1.062, 0.767),
        "emergency_moderate": (0.00, 0.10, 1.567, 1.246),
        "emergency_severe": (0.00, 0.00, 2.576, 2.177),
        "optional_service_stress": (0.00, 0.50, 2.538, 1.236),
        "overload": (0.10, 1.00, 1.014, 0.618),
        "recovery_backlog": (0.00, 0.50, 1.597, 1.267),
        "threshold_chatter": (0.00, 1.00, 1.184, 0.875),
    }
    for scenario, values in expected.items():
        row = aggregate.loc[scenario]
        for label, actual, expected_value, digits in zip(
            ("full", "minimum", "max_full", "max_min"),
            row,
            values,
            (2, 2, 3, 3),
            strict=True,
        ):
            require_rounded(actual, expected_value, digits, f"Table 9 {scenario} {label}")


def check_table_10_robustness() -> None:
    frame = pd.read_csv(RESULTS / "best_journal/overhead_jitter_robustness.csv")
    frame = frame[frame["release_jitter_ms"] == 20]
    aggregate = frame.groupby(["variant", "execution_overhead_fraction"])[
        ["high_deadline_miss_ratio", "low_work_weighted_utility_linear"]
    ].mean()
    expected = {
        "criticality_edf": [(0.00, 0.00000, 0.91409), (0.05, 0.00000, 0.86958), (0.10, 0.00000, 0.83375), (0.20, 0.00000, 0.72318)],
        "edf": [(0.00, 0.72750, 0.97764), (0.05, 0.83333, 0.97540), (0.10, 0.92417, 0.97118), (0.20, 1.00000, 0.89976)],
        "rt_dash_tuned": [(0.00, 0.00000, 0.92705), (0.05, 0.00000, 0.87962), (0.10, 0.00000, 0.83733), (0.20, 0.00000, 0.72728)],
        "rt_dash_recovery_edf_tuned": [(0.00, 0.00000, 0.97443), (0.05, 0.00000, 0.97219), (0.10, 0.00000, 0.96780), (0.20, 0.00000, 0.89542)],
    }
    for variant, rows in expected.items():
        for overhead, dmr, utility in rows:
            actual = aggregate.loc[(variant, overhead)]
            require_rounded(actual.iloc[0], dmr, 5, f"Table 10 {variant} {overhead} DMR")
            require_rounded(actual.iloc[1], utility, 5, f"Table 10 {variant} {overhead} utility")


def check_table_11_external_benchmark() -> None:
    frame = pd.read_csv(RESULTS / "best_journal/external_edf_vd_benchmark.csv")
    aggregate = frame.groupby("policy")[
        ["high_dmr", "high_mean_response", "low_completion_rate", "low_service_fraction"]
    ].mean()
    expected = {
        "criticality_edf": (0.00000, 9.88, 0.95655, 0.96129),
        "edf": (0.01602, 38.87, 0.98775, 0.98696),
        "edf_vd_drop": (0.00000, 12.95, 0.64365, 0.56106),
        "edf_vd_imc": (0.00012, 14.39, 0.87485, 0.64766),
        "rt_dash_mc": (0.00000, 14.02, 0.87087, 0.66068),
    }
    for policy, values in expected.items():
        row = aggregate.loc[policy]
        for label, actual, expected_value, digits in zip(
            ("high DMR", "high response", "low completion", "low service"),
            row,
            values,
            (5, 2, 5, 5),
            strict=True,
        ):
            require_rounded(actual, expected_value, digits, f"Table 11 {policy} {label}")


def check_dataset_identity() -> None:
    raw = ROOT / "data/raw/smart_home_dataset.csv"
    audit = json.loads((ROOT / "data/dataset_audit.json").read_text(encoding="utf-8"))["raw"]
    require(
        sha256(raw) == "dcb873f7b7c74c0f1cc246d716d88865076c0ed25b89593b6c3448ded19aca8d",
        "Raw dataset SHA-256 mismatch",
    )
    require(audit["rows"] == 1048575, "Dataset row count mismatch")
    require(len(audit["columns"]) == 31, "Dataset column count mismatch")
    require(audit["duplicate_rows"] == 3, "Dataset duplicate-row count mismatch")
    require(audit["invalid_timestamps"] == 0, "Dataset timestamp audit mismatch")


def check_figures_and_implementation() -> None:
    figures = ROOT / "manuscript_figures"
    expected_dimensions = [
        (6240, 3240), (6540, 3840), (5926, 4140), (5938, 3235), (5938, 3235),
        (5037, 3055), (5039, 3055), (5906, 3231), (5338, 3115), (5418, 3341),
    ]
    manifest = pd.read_csv(figures / "FIGURE_EXTRACTION_MANIFEST.tsv", sep="\t")
    require(len(manifest) == 10, "Final manuscript figure manifest must list 10 figures")
    for number, (width, height) in enumerate(expected_dimensions, start=1):
        path = figures / f"figure_{number:02d}_final_manuscript.png"
        require(path.is_file() and path.stat().st_size > 1000, f"Missing Figure {number}")
        row = manifest[manifest["figure"] == number]
        require(len(row) == 1, f"Figure {number} missing from extraction manifest")
        require(int(row.iloc[0]["width_px"]) == width, f"Figure {number} width mismatch")
        require(int(row.iloc[0]["height_px"]) == height, f"Figure {number} height mismatch")
        require(row.iloc[0]["sha256"] == sha256(path), f"Figure {number} hash mismatch")

    required_sources = [
        ROOT / "research/rt_dash/simulator.py",
        ROOT / "research/rt_dash/policies.py",
        ROOT / "research/scripts/run_journal_strengthening_study.py",
        ROOT / "research/scripts/run_best_journal_study.py",
        ROOT / "research_cpp/src/Scheduler.cpp",
        ROOT / "research_cpp/tests/test_scheduler.cpp",
        ROOT / "rtos/RTOS_Scheduler.cpp",
        ROOT / "firmware/common/src/rtdash.c",
    ]
    for path in required_sources:
        require(path.is_file() and path.stat().st_size > 0, f"Missing source: {path.relative_to(ROOT)}")

    firmware = ROOT / "firmware"
    expected_counts = {"*.elf": 10, "*.bin": 10, "*.hex": 5, "*.map": 10, "*.disasm": 10}
    for pattern, expected in expected_counts.items():
        require(len(list(firmware.rglob(pattern))) == expected, f"Firmware count mismatch for {pattern}")
    for target in ("qemu_lm3s6965", "stm32f103_bluepill"):
        undefined = firmware / target / "logs/undefined_symbols.txt"
        require(undefined.read_bytes() == b"", f"Unresolved firmware symbols for {target}")
        hashes = firmware / target / "logs/build_sha256.txt"
        for line in hashes.read_text(encoding="utf-8").splitlines():
            expected_hash, archived_path = line.split(maxsplit=1)
            local = firmware / target / "build" / Path(archived_path).name
            require(sha256(local) == expected_hash, f"Firmware hash mismatch: {local.name}")


def main() -> None:
    check_table_4_inventory()
    check_table_5_configuration()
    check_table_6_held_out()
    check_tables_7_and_8_inference()
    check_table_9_demand_screen()
    check_table_10_robustness()
    check_table_11_external_benchmark()
    check_dataset_identity()
    check_figures_and_implementation()
    print("FINAL MANUSCRIPT ALIGNMENT: PASS")
    print("Verified Table 4 inventory: 15,780 simulations plus 70 demand-screen records")
    print("Verified Tables 5-11 and all headline held-out/statistical values")
    print("Verified exact dataset identity: 1,048,575 rows, 31 columns, SHA-256 intact")
    print("Verified Figures 1-10, Python/C++/RTOS sources, and firmware build evidence")


if __name__ == "__main__":
    main()
