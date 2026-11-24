#!/usr/bin/env python3
"""Fail-closed verifier for the archived AI-RT-DASH result package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
import pandas as pd

from rt_dash.ai import PortableLogisticRiskModel


EXPECTED_POLICIES = {
    "edf",
    "rt_dash_no_event_trigger",
    "rt_dash",
    "rt_dash_recovery_edf",
    "rt_dash_ai_only",
    "rt_dash_ai_safe",
    "rt_dash_ai_safe_recovery_edf",
}
EXPECTED_LOADS = {0.30, 0.45, 0.60}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify_hashes(output: Path) -> int:
    manifest = output / "SHA256SUMS_AI.txt"
    require(manifest.exists(), "missing SHA256SUMS_AI.txt")
    count = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = output / relative
        require(path.is_file(), f"hashed output is missing: {relative}")
        require(digest(path) == expected, f"SHA-256 mismatch: {relative}")
        count += 1
    return count


def verify_cpp_header(output: Path, model: PortableLogisticRiskModel) -> None:
    compiler = shutil.which("g++")
    if compiler is None:
        raise RuntimeError("g++ is unavailable; pass --skip-cpp only when documented")
    header = output / "portable_logistic_model.h"
    require(header.exists(), "missing portable_logistic_model.h")
    features = np.linspace(0.0, 1.0, len(model.feature_names), dtype=float)
    expected = float(model.predict_proba(features)[0])
    initializer = ", ".join(f"{value:.17g}" for value in features)
    program = f'''#include <iomanip>\n#include <iostream>\n#include "{header}"\nint main() {{\n  const double x[RTDASH_AI_FEATURE_COUNT] = {{{initializer}}};\n  std::cout << std::setprecision(17) << rtdash_ai_risk(x, RTDASH_AI_FEATURE_COUNT);\n}}\n'''
    with tempfile.TemporaryDirectory(prefix="rtdash-ai-verify-") as temporary:
        source = Path(temporary) / "parity.cpp"
        binary = Path(temporary) / "parity"
        source.write_text(program, encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c++17", "-O2", str(source), "-o", str(binary)],
            check=True,
            capture_output=True,
            text=True,
        )
        observed = float(subprocess.check_output([str(binary)], text=True))
    require(np.isclose(expected, observed, rtol=1e-12, atol=1e-12), "C/Python inference mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/ai_extension"))
    parser.add_argument("--skip-cpp", action="store_true")
    args = parser.parse_args()
    output = args.results.resolve()
    require(output.is_dir(), f"results directory does not exist: {output}")

    manifest = json.loads((output / "ai_execution_manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("selection_uses_test") is False, "test partition was used in selection")
    require(
        manifest.get("diagnostics_use_test_for_selection") is False,
        "post-lock diagnostics were allowed to affect selection",
    )
    require(manifest.get("scheduler_test_runs") == 630, "unexpected scheduler run count")
    require(set(manifest.get("background_utilization_targets", [])) == EXPECTED_LOADS, "load matrix mismatch")
    require(manifest.get("partition_counts") == {"train": 60108, "validation": 23972, "test": 20670}, "partition counts changed")

    selection = pd.read_csv(output / "model_selection.csv")
    require(str(selection.iloc[0].model) == manifest["selected_model"], "selected model mismatch")
    thresholds = pd.read_csv(output / "scheduler_threshold_validation.csv")
    require(
        np.isclose(float(thresholds.iloc[0].threshold), float(manifest["scheduling_threshold"])),
        "scheduler threshold was not the validation winner",
    )

    runs = pd.read_csv(output / "scheduling_integration_runs.csv")
    require(len(runs) == 630, "scheduling_integration_runs.csv row count mismatch")
    require(set(runs.policy.unique()) == EXPECTED_POLICIES, "policy matrix mismatch")
    require(set(np.round(runs.background_utilization_target.unique(), 2)) == EXPECTED_LOADS, "load values mismatch")
    counts = runs.groupby(["block_id", "background_utilization_target"]).policy.nunique()
    require(bool((counts == len(EXPECTED_POLICIES)).all()), "a workload cell lacks a policy")

    index = ["block_id", "background_utilization_target"]
    safe = runs[runs.policy == "rt_dash_ai_safe_recovery_edf"].sort_values(index)
    fallback = runs[runs.policy == "rt_dash_recovery_edf"].sort_values(index)
    require(len(safe) == len(fallback) == 90, "safe/fallback cell count mismatch")
    for metric in (
        "high_deadline_miss_ratio",
        "high_mean_response",
        "low_work_weighted_utility_linear",
        "critical_mode_fraction",
    ):
        require(
            np.allclose(safe[metric], fallback[metric], equal_nan=True, rtol=0.0, atol=0.0),
            f"safe hybrid changed fallback outcome: {metric}",
        )

    ai_only = runs[runs.policy == "rt_dash_ai_only"].high_deadline_miss_ratio.fillna(0).mean()
    load_only = runs[runs.policy == "rt_dash_no_event_trigger"].high_deadline_miss_ratio.fillna(0).mean()
    semantic = runs[runs.policy == "rt_dash"].high_deadline_miss_ratio.fillna(0).mean()
    require(ai_only <= load_only + 1e-15, "AI-only did not reproduce archived directional DMR gain")
    require(semantic <= ai_only + 1e-15, "semantic fallback should remain at least as safe as AI-only")

    temporal = pd.read_csv(output / "temporal_generalization_by_date.csv")
    require(len(temporal) == 6, "temporal diagnostic must contain three validation and three test dates")
    require(
        temporal.groupby("split").source_date.nunique().to_dict()
        == {"test": 3, "validation": 3},
        "temporal diagnostic split/date matrix changed",
    )
    require(
        temporal.diagnostic_only_after_model_lock.astype(bool).all(),
        "temporal diagnostics are not marked post-lock",
    )
    require(
        np.isfinite(temporal[["auprc", "brier", "mean_absolute_standardized_feature_shift"]]).all().all(),
        "temporal diagnostic contains a non-finite primary metric",
    )

    importance = pd.read_csv(output / "selected_model_feature_importance.csv")
    require(len(importance) == 29, "selected logistic feature-importance width changed")
    require(importance.feature.nunique() == len(importance), "duplicate feature-importance row")
    require(list(importance["rank"]) == list(range(1, len(importance) + 1)), "feature ranks changed")

    leave_one_out = pd.read_csv(output / "leave_one_sensor_out.csv")
    require(len(leave_one_out) == 29, "leave-one-sensor-out matrix is incomplete")
    require(leave_one_out.failed_sensor.nunique() == 29, "sensor failure cases are duplicated")
    require(
        np.isfinite(leave_one_out[["auroc", "auprc", "brier"]]).all().all(),
        "sensor-failure diagnostic contains a non-finite primary metric",
    )

    operating = pd.read_csv(output / "validation_locked_operating_curve.csv")
    require(set(operating.split) == {"validation", "test"}, "operating curve split changed")
    require(
        (operating.groupby("threshold").split.nunique() == 2).all(),
        "operating curve threshold grid is not shared across validation/test",
    )
    require(
        (operating.threshold_grid_source == "validation_only").all(),
        "operating curve contains a test-derived threshold",
    )
    require(
        operating.is_classification_threshold.astype(bool).sum() == 2
        and operating.is_scheduler_threshold.astype(bool).sum() == 2,
        "locked threshold markers are incomplete",
    )

    model = PortableLogisticRiskModel.load(output / "portable_logistic_model.json")
    forbidden = ("Activity", "CPU", "Memory", "Storage", "Bandwidth", "Priority", "Power")
    require(
        not any(any(token.lower() in name.lower() for token in forbidden) for name in model.feature_names),
        "portable model contains a forbidden label/resource feature",
    )
    if not args.skip_cpp:
        verify_cpp_header(output, model)

    hash_count = verify_hashes(output)
    print("AI EXTENSION VALIDATION: PASS")
    print(json.dumps({
        "classification_samples": sum(manifest["partition_counts"].values()),
        "scheduler_test_runs": len(runs),
        "safe_fallback_cells": len(safe),
        "temporal_diagnostic_dates": len(temporal),
        "leave_one_sensor_out_cases": len(leave_one_out),
        "hashed_outputs": hash_count,
        "cpp_header_parity": not args.skip_cpp,
    }, indent=2))


if __name__ == "__main__":
    main()
