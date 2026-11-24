from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from rt_dash.forecasting import RESOURCE_NAMES, regression_metrics


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_hashes(output: Path) -> int:
    lines = (output / "SHA256SUMS_ARIMA_LSTM.txt").read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, relative = line.split("  ", 1)
        path = output / relative
        require(path.is_file(), f"hashed ARIMA/LSTM artifact missing: {relative}")
        require(sha256(path) == expected, f"ARIMA/LSTM artifact hash mismatch: {relative}")
    return len(lines)


def main() -> None:
    output = Path("results/arima_lstm_thesis")
    manifest = json.loads(
        (output / "arima_lstm_execution_manifest.json").read_text(encoding="utf-8")
    )
    metrics = pd.read_csv(output / "forecast_metrics.csv")
    predictions = pd.read_csv(output / "forecast_predictions_validation_test.csv")
    threshold = pd.read_csv(output / "scheduler_threshold_validation.csv")
    scheduling = pd.read_csv(output / "scheduling_integration_runs.csv")
    weights = np.load(output / "lstm_weights.npz")

    require(manifest["hardware_used"] is False, "forecasting study must be software-only")
    require(manifest["resource_columns_are_synthetic_thesis_annotations"] is True, "synthetic resource provenance flag missing")
    require(manifest["test_used_for_model_or_threshold_selection"] is False, "test leakage flag is invalid")
    require(manifest["prior_locked_results_modified"] is False, "prior locked evidence was marked modified")
    require(manifest["arima_order"] == [5, 1, 0], "ARIMA order changed after protocol freeze")
    require(manifest["lstm_hidden_units"] == 16, "LSTM architecture changed after protocol freeze")
    require(manifest["lstm_seed"] == 20260806, "LSTM seed changed")
    require(manifest["train_examples"] == 11033, "train example count mismatch")
    require(manifest["validation_examples"] == 4320, "validation example count mismatch")
    require(manifest["test_examples"] == 4043, "test example count mismatch")
    require(manifest["train_dates"] == [f"2021-03-{day:02d}" for day in range(1, 9)], "train chronology mismatch")
    require(manifest["validation_dates"] == [f"2021-03-{day:02d}" for day in range(9, 12)], "validation chronology mismatch")
    require(manifest["test_dates"] == [f"2021-03-{day:02d}" for day in range(12, 15)], "test chronology mismatch")
    require(manifest["resource_data_quality"]["rows_missing_any_resource"] == 1, "resource missing-row audit changed")
    require(manifest["resource_data_quality"]["missing_activity_rows"] == 168923, "activity missing-row audit changed")

    require(set(metrics.model) == {"persistence", "arima_510", "lstm", "thesis_hybrid"}, "forecast model set mismatch")
    require(set(metrics.resource) == set(RESOURCE_NAMES), "forecast resource set mismatch")
    require(set(metrics.split) == {"train", "validation", "test"}, "forecast split set mismatch")
    require(len(metrics) == 48, "forecast metric matrix must be 4 models × 4 resources × 3 splits")
    require(np.isfinite(metrics[["mae", "rmse", "smape_percent", "normalized_rmse_train_sd"]].to_numpy()).all(), "non-finite forecast error metric")

    test = predictions[predictions.split == "test"]
    train_scale = np.asarray(weights["train_scale"], dtype=float)
    for model in ("persistence", "arima_510", "lstm", "thesis_hybrid"):
        for column, resource in enumerate(RESOURCE_NAMES):
            recomputed = regression_metrics(
                test[f"actual_{resource}"].to_numpy(),
                test[f"{model}_{resource}"].to_numpy(),
                train_scale[column],
            )
            stored = metrics[(metrics.split == "test") & (metrics.model == model) & (metrics.resource == resource)].iloc[0]
            for field in ("mae", "rmse", "smape_percent", "r2", "normalized_rmse_train_sd"):
                require(np.isclose(float(stored[field]), float(recomputed[field]), rtol=1e-10, atol=1e-12), f"recomputed test metric mismatch: {model}/{resource}/{field}")

    require(np.allclose(predictions.thesis_hybrid_CPU, predictions.arima_510_CPU), "hybrid CPU must come from ARIMA")
    for resource in ("Memory", "Storage", "Bandwidth"):
        require(np.allclose(predictions[f"thesis_hybrid_{resource}"], predictions[f"lstm_{resource}"]), f"hybrid {resource} must come from LSTM")

    require((threshold.selection_split == "validation").all(), "scheduler threshold includes non-validation selection")
    require(np.isclose(float(threshold.iloc[0].threshold), float(manifest["scheduler_threshold"])), "selected scheduler threshold mismatch")
    require(len(scheduling) == manifest["scheduler_test_runs"] == 714, "scheduler test matrix size mismatch")
    require(set(scheduling.policy) == {
        "edf", "rt_dash_no_event_trigger", "rt_dash", "rt_dash_recovery_edf",
        "rt_dash_ai_only", "rt_dash_ai_safe", "rt_dash_ai_safe_recovery_edf",
    }, "scheduler policy set mismatch")
    require((scheduling.predictor == "thesis_arima_lstm_hybrid").all(), "predictor provenance missing from scheduler rows")

    wide = scheduling.pivot_table(
        index=["block_id", "source_date", "background_utilization_target"],
        columns="policy",
        values=["high_deadline_miss_ratio", "low_work_weighted_utility_linear", "critical_mode_fraction"],
    )
    for metric in ("high_deadline_miss_ratio", "low_work_weighted_utility_linear", "critical_mode_fraction"):
        left = wide[(metric, "rt_dash_ai_safe_recovery_edf")]
        right = wide[(metric, "rt_dash_recovery_edf")]
        require(np.allclose(left, right, equal_nan=True), f"safe recovery fallback mismatch: {metric}")

    protocol = Path("docs/ARIMA_LSTM_THESIS_PROTOCOL_FROZEN_2026-08-06.md")
    require(sha256(protocol) == manifest["frozen_protocol_sha256"], "frozen protocol hash mismatch")
    source = Path("../data/processed/processed_smart_home_dataset_with_resources.csv")
    require(sha256(source) == manifest["processed_resource_sha256"], "processed resource source hash mismatch")
    hash_count = verify_hashes(output)
    print("ARIMA+LSTM THESIS VERIFICATION: PASS")
    print(json.dumps({"hashed_outputs": hash_count, "forecast_test_examples": 4043, "scheduler_test_runs": 714}, indent=2))


if __name__ == "__main__":
    main()
