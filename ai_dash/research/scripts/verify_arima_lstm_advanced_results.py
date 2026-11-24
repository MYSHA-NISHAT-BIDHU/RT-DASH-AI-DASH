from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from rt_dash.forecasting import RESOURCE_NAMES, regression_metrics


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "arima_lstm_advanced"
PROTOCOL = ROOT / "docs" / "ARIMA_LSTM_ADVANCED_PROTOCOL_FROZEN_2026-08-06.md"
LOCKED_PROTOCOL = ROOT / "docs" / "ARIMA_LSTM_THESIS_PROTOCOL_FROZEN_2026-08-06.md"
LOCKED_SUMS = ROOT / "results" / "arima_lstm_thesis" / "SHA256SUMS_ARIMA_LSTM.txt"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify_hashes() -> int:
    sums = OUTPUT / "SHA256SUMS_ARIMA_LSTM_ADVANCED.txt"
    lines = [line for line in sums.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in lines:
        expected, relative = line.split("  ", 1)
        assert digest(OUTPUT / relative) == expected, relative
    return len(lines)


def equal_nan(left: pd.Series, right: pd.Series) -> bool:
    return bool(
        np.allclose(
            left.to_numpy(dtype=float),
            right.to_numpy(dtype=float),
            rtol=0.0,
            atol=0.0,
            equal_nan=True,
        )
    )


def main() -> None:
    hashed = verify_hashes()
    manifest = json.loads((OUTPUT / "arima_lstm_advanced_execution_manifest.json").read_text())
    assert manifest["hardware_used"] is False
    assert manifest["resource_columns_are_synthetic_thesis_annotations"] is True
    assert manifest["test_used_for_selection"] is False
    assert manifest["prior_locked_results_modified"] is False
    assert manifest["protocol_sha256"] == digest(PROTOCOL)
    assert manifest["locked_thesis_protocol_sha256"] == digest(LOCKED_PROTOCOL)
    assert manifest["locked_thesis_output_manifest_sha256"] == digest(LOCKED_SUMS)
    assert manifest["lstm_candidates"] == 6
    assert manifest["rolling_origin_folds"] == 8
    assert len(manifest["primary_train_dates"]) == 8
    assert len(manifest["primary_validation_dates"]) == 3
    assert len(manifest["primary_test_dates"]) == 3
    assert set(manifest["primary_train_dates"]).isdisjoint(manifest["primary_test_dates"])

    tuning = pd.read_csv(OUTPUT / "lstm_validation_tuning.csv")
    assert len(tuning) == 6
    assert set(tuning.selection_split) == {"validation"}
    assert np.isclose(tuning.iloc[0].mean_validation_nrmse, tuning.mean_validation_nrmse.min())
    assert int(tuning.iloc[0].hidden_units) == manifest["selected_lstm_hidden_units"]
    assert np.isclose(tuning.iloc[0].learning_rate, manifest["selected_lstm_learning_rate"])

    predictions = pd.read_csv(OUTPUT / "advanced_forecast_predictions_validation_test.csv")
    assert set(predictions.split) == {"validation", "test"}
    assert int((predictions.split == "test").sum()) == manifest["test_examples"]
    configuration = pd.read_csv(OUTPUT / "validation_selected_forecast_configuration.csv")
    assert configuration.resource.tolist() == list(RESOURCE_NAMES)
    assert np.all((configuration.adaptive_lstm_weight >= 0.0) & (configuration.adaptive_lstm_weight <= 1.0))
    assert np.allclose(configuration.adaptive_lstm_weight * 20.0, np.round(configuration.adaptive_lstm_weight * 20.0))
    validation = predictions[predictions.split == "validation"]
    for _, row in configuration.iterrows():
        resource = row.resource
        actual = validation[f"actual_{resource}"].to_numpy()
        arima = validation[f"arima_510_{resource}"].to_numpy()
        lstm = validation[f"lstm_tuned_{resource}"].to_numpy()
        losses = []
        for weight in np.linspace(0.0, 1.0, 21):
            blended = (1.0 - weight) * arima + weight * lstm
            losses.append(float(np.sqrt(np.mean((blended - actual) ** 2))))
        expected = np.linspace(0.0, 1.0, 21)[int(np.argmin(losses))]
        assert np.isclose(row.adaptive_lstm_weight, expected)

    metrics = pd.read_csv(OUTPUT / "forecast_metrics_advanced.csv")
    expected_models = {
        "persistence", "ewma", "ridge_var", "arima_510", "lstm_anchor",
        "lstm_tuned", "thesis_hybrid", "adaptive_arima_lstm",
    }
    assert set(metrics.model) == expected_models
    assert set(metrics.split) == {"train", "validation", "test"}
    assert len(metrics) == 3 * len(expected_models) * len(RESOURCE_NAMES)
    train_scale = {}
    for resource in RESOURCE_NAMES:
        row = metrics[(metrics.split == "test") & (metrics.model == "persistence") & (metrics.resource == resource)].iloc[0]
        train_scale[resource] = row.rmse / row.normalized_rmse_train_sd
    for split in ("validation", "test"):
        subset = predictions[predictions.split == split]
        for model in expected_models:
            for resource in RESOURCE_NAMES:
                actual = subset[f"actual_{resource}"].to_numpy()
                predicted = subset[f"{model}_{resource}"].to_numpy()
                recomputed = regression_metrics(actual, predicted, train_scale[resource])
                recorded = metrics[(metrics.split == split) & (metrics.model == model) & (metrics.resource == resource)].iloc[0]
                for key in ("mae", "rmse", "smape_percent", "r2", "normalized_rmse_train_sd"):
                    assert np.isclose(recomputed[key], recorded[key], rtol=1e-10, atol=1e-10), (split, model, resource, key)

    uncertainty = pd.read_csv(OUTPUT / "forecast_cluster_bootstrap_comparisons.csv")
    assert len(uncertainty) == 8
    assert set(uncertainty.n_date_clusters) == {3}

    rolling = pd.read_csv(OUTPUT / "rolling_origin_forecast_metrics.csv")
    assert set(rolling.fold) == set(range(1, 9))
    assert set(rolling.model) == {"persistence", "arima_510", "lstm_fixed", "thesis_hybrid"}
    assert len(rolling) == 8 * 4 * 4
    for _, fold in rolling.groupby("fold"):
        assert pd.Timestamp(fold.validation_date.iloc[0]) < pd.Timestamp(fold.test_date.iloc[0])
    rolling_wide = rolling.pivot_table(index=["fold", "resource"], columns="model", values="rmse")
    assert int((rolling_wide["lstm_fixed"] < rolling_wide["persistence"]).sum()) == 26
    assert int((rolling_wide["arima_510"] < rolling_wide["persistence"]).sum()) == 23

    thresholds = pd.read_csv(OUTPUT / "scheduler_predictor_threshold_validation.csv")
    assert set(thresholds.selection_split) == {"validation"}
    for predictor, group in thresholds.groupby("predictor"):
        selected = group.sort_values(["objective", "threshold"], ascending=[True, False]).iloc[0]
        assert np.isclose(selected.threshold, manifest["scheduler_thresholds"][predictor])

    scheduler = pd.read_csv(OUTPUT / "scheduler_predictor_ablation_runs.csv")
    assert len(scheduler) == manifest["scheduler_ablation_test_runs"] == 1122
    for predictor in ("arima_all", "lstm_tuned", "thesis_hybrid", "adaptive_arima_lstm"):
        for policy in ("rt_dash_ai_only", "rt_dash_ai_safe_recovery_edf"):
            assert len(scheduler[(scheduler.predictor == predictor) & (scheduler.policy == policy)]) == 102
    for policy in ("rt_dash_no_event_trigger", "rt_dash", "rt_dash_recovery_edf"):
        assert len(scheduler[(scheduler.predictor == "deterministic_baseline") & (scheduler.policy == policy)]) == 102

    deterministic = scheduler[
        (scheduler.predictor == "deterministic_baseline")
        & (scheduler.policy == "rt_dash_recovery_edf")
    ].set_index(["block_id", "background_utilization_target"]).sort_index()
    for predictor in ("arima_all", "lstm_tuned", "thesis_hybrid", "adaptive_arima_lstm"):
        safe = scheduler[
            (scheduler.predictor == predictor)
            & (scheduler.policy == "rt_dash_ai_safe_recovery_edf")
        ].set_index(["block_id", "background_utilization_target"]).sort_index()
        for metric in ("high_deadline_miss_ratio", "low_work_weighted_utility_linear", "critical_mode_fraction"):
            assert equal_nan(safe[metric], deterministic[metric]), (predictor, metric)

    stress = pd.read_csv(OUTPUT / "prediction_fault_stress_runs.csv")
    assert len(stress) == manifest["prediction_fault_stress_runs"] == 714
    expected_faults = {
        "nominal", "blackout", "stuck_high", "negative_bias_015",
        "positive_bias_015", "gaussian_sigma_010", "gaussian_sigma_020",
    }
    assert set(stress.fault_case) == expected_faults
    assert all(len(group) == 102 for _, group in stress.groupby("fault_case"))
    blackout = stress[stress.fault_case == "blackout"].set_index(
        ["block_id", "background_utilization_target"]
    ).sort_index()
    for metric in ("high_deadline_miss_ratio", "low_work_weighted_utility_linear", "critical_mode_fraction"):
        assert equal_nan(blackout[metric], deterministic[metric]), metric
    summary = pd.read_csv(OUTPUT / "prediction_fault_stress_summary.csv")
    assert set(summary.fault_case) == expected_faults
    assert np.allclose(summary.high_dmr.fillna(0.0), 0.0)

    complexity = json.loads((OUTPUT / "analytical_model_complexity.json").read_text())
    assert "not timing" in complexity["evidence_type"]

    expected_total = manifest["scheduler_tuning_runs"] + len(scheduler) + len(stress)
    assert expected_total == manifest["new_scheduler_simulations_total"] == 5724
    print("ARIMA+LSTM ADVANCED VERIFICATION: PASS")
    print(json.dumps({
        "hashed_outputs": hashed,
        "forecast_test_examples": manifest["test_examples"],
        "rolling_origin_folds": manifest["rolling_origin_folds"],
        "new_scheduler_simulations": manifest["new_scheduler_simulations_total"],
    }, indent=2))


if __name__ == "__main__":
    main()
