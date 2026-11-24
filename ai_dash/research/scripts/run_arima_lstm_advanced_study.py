from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from rt_dash.ai import cluster_bootstrap_mean_ci, predictive_signals
from rt_dash.forecasting import (
    RESOURCE_NAMES,
    NumpyLSTMRegressor,
    RidgeVARRegressor,
    TrainStandardizer,
    arima_predict_examples,
    audit_resource_source,
    convex_blend_predictions,
    exponentially_weighted_history_prediction,
    fit_arima_models,
    make_forecast_examples,
    prepare_resource_forecast_dataset,
    regression_metrics,
    select_convex_blend_weights,
    thesis_hybrid_pressure,
)
from rt_dash.metrics import summarize_result
from rt_dash.policies import PolicyName
from rt_dash.simulator import SimulationConfig, Simulator
from rt_dash.workloads import scaled_periodic_taskset
from run_arima_lstm_thesis_study import (
    BACKGROUND_LOADS,
    build_blocks,
    holm_adjust,
    scheduling_objective,
    sha256,
    trace_events,
)


MASTER_SEED = 20260806
PROTOCOL = Path("docs/ARIMA_LSTM_ADVANCED_PROTOCOL_FROZEN_2026-08-06.md")
LOCKED_PROTOCOL = Path("docs/ARIMA_LSTM_THESIS_PROTOCOL_FROZEN_2026-08-06.md")
LOCKED_OUTPUT_MANIFEST = Path("results/arima_lstm_thesis/SHA256SUMS_ARIMA_LSTM.txt")
LSTM_GRID = tuple((hidden, rate) for hidden in (8, 16, 32) for rate in (0.003, 0.005))
RIDGE_GRID = (1e-4, 1e-2, 1.0, 100.0)
EWMA_GRID = (0.2, 0.5, 0.8)
BLEND_GRID = np.linspace(0.0, 1.0, 21)
FAULT_CASES = (
    "nominal",
    "blackout",
    "stuck_high",
    "negative_bias_015",
    "positive_bias_015",
    "gaussian_sigma_010",
    "gaussian_sigma_020",
)


def metric_rows(examples, predictions: dict[str, np.ndarray], train_scale: np.ndarray) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for split in ("train", "validation", "test"):
        mask = examples.mask(split)
        for model, prediction in predictions.items():
            for column, resource in enumerate(RESOURCE_NAMES):
                rows.append(
                    {
                        "split": split,
                        "model": model,
                        "resource": resource,
                        "n": int(mask.sum()),
                        **regression_metrics(
                            examples.y[mask, column],
                            prediction[mask, column],
                            train_scale[column],
                        ),
                    }
                )
    return pd.DataFrame(rows)


def fit_lstm_candidate(
    examples,
    standardizer: TrainStandardizer,
    hidden: int,
    learning_rate: float,
    max_epochs: int,
    patience: int,
):
    train = examples.mask("train")
    validation = examples.mask("validation")
    x = standardizer.transform(examples.x)
    y = standardizer.transform(examples.y)
    model = NumpyLSTMRegressor(
        input_size=len(RESOURCE_NAMES),
        hidden_size=hidden,
        output_size=len(RESOURCE_NAMES),
        seed=MASTER_SEED,
    )
    history = model.fit(
        x[train],
        y[train],
        x[validation],
        y[validation],
        learning_rate=learning_rate,
        batch_size=128,
        max_epochs=max_epochs,
        patience=patience,
        gradient_clip=5.0,
    )
    prediction = standardizer.inverse_transform(model.predict(x))
    return model, pd.DataFrame(history), prediction


def tune_lstm(examples, standardizer: TrainStandardizer):
    validation = examples.mask("validation")
    rows: list[dict[str, object]] = []
    candidates = []
    for hidden, learning_rate in LSTM_GRID:
        model, history, prediction = fit_lstm_candidate(
            examples, standardizer, hidden, learning_rate, max_epochs=30, patience=5
        )
        normalized = []
        row: dict[str, object] = {
            "hidden_units": hidden,
            "learning_rate": learning_rate,
            "epochs_executed": len(history),
            "selection_split": "validation",
        }
        for column, resource in enumerate(RESOURCE_NAMES):
            score = regression_metrics(
                examples.y[validation, column],
                prediction[validation, column],
                standardizer.scale[column],
            )["normalized_rmse_train_sd"]
            normalized.append(score)
            row[f"validation_nrmse_{resource}"] = score
        row["mean_validation_nrmse"] = float(np.mean(normalized))
        rows.append(row)
        candidates.append((float(row["mean_validation_nrmse"]), hidden, learning_rate, model, history, prediction))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    _, hidden, learning_rate, model, history, prediction = candidates[0]
    tuning = pd.DataFrame(rows).sort_values(
        ["mean_validation_nrmse", "hidden_units", "learning_rate"]
    ).reset_index(drop=True)
    return model, history, prediction, tuning, hidden, learning_rate


def tune_ewma(examples, train_scale: np.ndarray):
    validation = examples.mask("validation")
    candidate_predictions = {
        alpha: exponentially_weighted_history_prediction(examples, alpha)
        for alpha in EWMA_GRID
    }
    selected = np.empty(len(RESOURCE_NAMES), dtype=float)
    rows = []
    for column, resource in enumerate(RESOURCE_NAMES):
        for alpha in EWMA_GRID:
            metrics = regression_metrics(
                examples.y[validation, column],
                candidate_predictions[alpha][validation, column],
                train_scale[column],
            )
            rows.append(
                {
                    "resource": resource,
                    "alpha": alpha,
                    "validation_rmse": metrics["rmse"],
                    "validation_nrmse": metrics["normalized_rmse_train_sd"],
                }
            )
        subset = [row for row in rows if row["resource"] == resource]
        best = min(subset, key=lambda row: (row["validation_rmse"], row["alpha"]))
        selected[column] = float(best["alpha"])
    prediction = exponentially_weighted_history_prediction(examples, selected)
    return prediction, selected, pd.DataFrame(rows)


def tune_ridge_var(examples, standardizer: TrainStandardizer):
    train = examples.mask("train")
    validation = examples.mask("validation")
    x = standardizer.transform(examples.x)
    y = standardizer.transform(examples.y)
    rows = []
    candidates = []
    for ridge in RIDGE_GRID:
        model = RidgeVARRegressor(ridge=ridge).fit(x[train], y[train])
        prediction_standardized = model.predict(x)
        validation_error = prediction_standardized[validation] - y[validation]
        resource_nrmse = np.sqrt(np.mean(validation_error**2, axis=0))
        score = float(np.mean(resource_nrmse))
        row = {"ridge": ridge, "mean_validation_nrmse": score}
        for resource, value in zip(RESOURCE_NAMES, resource_nrmse):
            row[f"validation_nrmse_{resource}"] = float(value)
        rows.append(row)
        candidates.append((score, ridge, model, prediction_standardized))
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, ridge, model, prediction_standardized = candidates[0]
    prediction = standardizer.inverse_transform(prediction_standardized)
    return model, prediction, pd.DataFrame(rows).sort_values("mean_validation_nrmse"), ridge


def forecast_uncertainty(dataset, examples, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    mask = examples.mask("test")
    dates = dataset.timestamps[examples.target_indices[mask]].astype("datetime64[D]").astype(str)
    rows = []
    for comparator in ("persistence", "thesis_hybrid"):
        for column, resource in enumerate(RESOURCE_NAMES):
            actual = examples.y[mask, column]
            adaptive_error = np.abs(predictions["adaptive_arima_lstm"][mask, column] - actual)
            comparator_error = np.abs(predictions[comparator][mask, column] - actual)
            difference = adaptive_error - comparator_error
            low, high = cluster_bootstrap_mean_ci(difference, dates, seed=MASTER_SEED)
            rows.append(
                {
                    "left": "adaptive_arima_lstm",
                    "right": comparator,
                    "resource": resource,
                    "metric": "absolute_error",
                    "n": len(difference),
                    "n_date_clusters": len(np.unique(dates)),
                    "mean_difference": float(np.mean(difference)),
                    "date_cluster_bootstrap_ci95_low": low,
                    "date_cluster_bootstrap_ci95_high": high,
                }
            )
    return pd.DataFrame(rows)


def make_fold_dataset(dataset, train_days: int):
    dates = dataset.timestamps.astype("datetime64[D]")
    unique_dates = np.array(sorted(np.unique(dates)))
    splits = np.full(len(dates), "purged", dtype="U10")
    splits[np.isin(dates, unique_dates[:train_days])] = "train"
    splits[dates == unique_dates[train_days]] = "validation"
    splits[dates == unique_dates[train_days + 1]] = "test"
    return replace(dataset, splits=splits), unique_dates


def rolling_origin_study(dataset) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for train_days in range(5, 13):
        fold_dataset, unique_dates = make_fold_dataset(dataset, train_days)
        fold_examples = make_forecast_examples(fold_dataset, lookback=12)
        train_values = fold_dataset.values[fold_dataset.mask("train")]
        standardizer = TrainStandardizer.fit(train_values)
        arima_models = fit_arima_models(fold_dataset)
        arima = arima_predict_examples(arima_models, fold_examples)
        lstm, history, lstm_prediction = fit_lstm_candidate(
            fold_examples,
            standardizer,
            hidden=16,
            learning_rate=0.005,
            max_epochs=40,
            patience=6,
        )
        persistence = fold_examples.x[:, -1, :].copy()
        hybrid = lstm_prediction.copy()
        hybrid[:, 0] = arima[:, 0]
        predictions = {
            "persistence": persistence,
            "arima_510": arima,
            "lstm_fixed": lstm_prediction,
            "thesis_hybrid": hybrid,
        }
        test = fold_examples.mask("test")
        for model, prediction in predictions.items():
            for column, resource in enumerate(RESOURCE_NAMES):
                rows.append(
                    {
                        "fold": train_days - 4,
                        "train_days": train_days,
                        "validation_date": str(unique_dates[train_days]),
                        "test_date": str(unique_dates[train_days + 1]),
                        "lstm_epochs": len(history),
                        "model": model,
                        "resource": resource,
                        "n": int(test.sum()),
                        **regression_metrics(
                            fold_examples.y[test, column],
                            prediction[test, column],
                            standardizer.scale[column],
                        ),
                    }
                )
    return pd.DataFrame(rows)


def run_policy(block, policy: PolicyName, threshold: float, background_load: float, predictor: str):
    activities = np.asarray(block["activities"])
    pressure = np.asarray(block["pressure"], dtype=float)
    step_ms = 100
    duration = len(activities) * step_ms + 1_000
    seed = int(hashlib.sha256(str(block["block_id"]).encode()).hexdigest()[:8], 16)
    periodic = scaled_periodic_taskset(background_load, seed % 10_000)
    events = trace_events(activities, str(block["block_id"]), step_ms)
    signals = predictive_signals(pressure, step_ms, source=f"advanced-{predictor}")
    config = SimulationConfig(
        duration=duration,
        quantum=10,
        policy=policy,
        observation_window=1_000,
        smoothing_samples=5,
        monitor_interval=100,
        utilization_high=0.90,
        utilization_low=0.80,
        entry_hold=200,
        recovery_hold=500,
        predictive_threshold=threshold,
        drop_expired_jobs=True,
    )
    result = Simulator(periodic, events, config, signals).run()
    row = summarize_result(result)
    row.update(
        {
            "block_id": block["block_id"],
            "source_date": block["date"],
            "sequence_id": block["sequence_id"],
            "rows": len(activities),
            "anomaly_fraction": float(np.mean(activities == 5)),
            "predictive_positive_fraction": float(np.mean(pressure >= threshold)),
            "predictive_threshold": threshold,
            "background_utilization_target": background_load,
            "predictor": predictor,
        }
    )
    return row


def tune_threshold(blocks, predictor: str):
    values = np.concatenate([np.asarray(block["pressure"], dtype=float) for block in blocks])
    candidates = np.unique(
        np.r_[0.5, np.quantile(values, [0.50, 0.65, 0.75, 0.85, 0.90, 0.95, 0.98, 0.99])]
    )
    rows = []
    for threshold in candidates:
        frame = pd.DataFrame(
            run_policy(block, PolicyName.RT_DASH_AI_ONLY, float(threshold), load, predictor)
            for block in blocks
            for load in BACKGROUND_LOADS
        )
        rows.append(
            {
                "predictor": predictor,
                "threshold": float(threshold),
                "objective": scheduling_objective(frame),
                "high_dmr": float(frame.high_deadline_miss_ratio.fillna(0.0).mean()),
                "high_mean_response": float(frame.high_mean_response.dropna().mean()),
                "low_utility": float(frame.low_work_weighted_utility_linear.dropna().mean()),
                "critical_mode_fraction": float(frame.critical_mode_fraction.mean()),
                "selection_split": "validation",
            }
        )
    ranking = pd.DataFrame(rows).sort_values(["objective", "threshold"], ascending=[True, False])
    return float(ranking.iloc[0].threshold), ranking.reset_index(drop=True)


def scheduler_pairwise(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["variant"] = work["predictor"].astype(str) + "|" + work["policy"].astype(str)
    adaptive_only = "adaptive_arima_lstm|rt_dash_ai_only"
    adaptive_safe = "adaptive_arima_lstm|rt_dash_ai_safe_recovery_edf"
    thesis_only = "thesis_hybrid|rt_dash_ai_only"
    deterministic_recovery = "deterministic_baseline|rt_dash_recovery_edf"
    load_only = "deterministic_baseline|rt_dash_no_event_trigger"
    semantic = "deterministic_baseline|rt_dash"
    specs = (
        (adaptive_only, thesis_only, "high_deadline_miss_ratio"),
        (adaptive_only, thesis_only, "low_work_weighted_utility_linear"),
        (adaptive_only, load_only, "high_deadline_miss_ratio"),
        (adaptive_only, semantic, "high_deadline_miss_ratio"),
        (adaptive_only, semantic, "high_mean_response"),
        (adaptive_safe, deterministic_recovery, "high_deadline_miss_ratio"),
        (adaptive_safe, deterministic_recovery, "low_work_weighted_utility_linear"),
        (adaptive_safe, deterministic_recovery, "critical_mode_fraction"),
    )
    rows = []
    wide = work.pivot_table(
        index=["block_id", "source_date", "background_utilization_target"],
        columns="variant",
        values=["high_deadline_miss_ratio", "low_work_weighted_utility_linear", "high_mean_response", "critical_mode_fraction"],
    )
    for left, right, metric in specs:
        if (metric, left) not in wide.columns or (metric, right) not in wide.columns:
            continue
        paired = wide.loc[:, [(metric, left), (metric, right)]].dropna()
        difference = paired[(metric, left)].to_numpy() - paired[(metric, right)].to_numpy()
        clusters = paired.index.get_level_values("source_date").to_numpy()
        low, high = cluster_bootstrap_mean_ci(difference, clusters, seed=MASTER_SEED)
        try:
            pvalue = float(stats.wilcoxon(difference, zero_method="zsplit").pvalue)
        except ValueError:
            pvalue = 1.0
        rows.append(
            {
                "left": left,
                "right": right,
                "metric": metric,
                "n_cells": len(difference),
                "n_date_clusters": len(np.unique(clusters)),
                "mean_difference": float(np.mean(difference)),
                "date_cluster_bootstrap_ci95_low": low,
                "date_cluster_bootstrap_ci95_high": high,
                "wilcoxon_p_uncorrected": pvalue,
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["holm_p"] = holm_adjust(result.wilcoxon_p_uncorrected.to_numpy())
    return result


def corrupt_pressure(block, fault: str):
    copied = dict(block)
    pressure = np.asarray(block["pressure"], dtype=float).copy()
    if fault == "nominal":
        pass
    elif fault == "blackout":
        pressure[:] = 0.0
    elif fault == "stuck_high":
        pressure[:] = 1.0
    elif fault == "negative_bias_015":
        pressure -= 0.15
    elif fault == "positive_bias_015":
        pressure += 0.15
    elif fault.startswith("gaussian_sigma_"):
        sigma = 0.10 if fault.endswith("010") else 0.20
        material = f"{block['block_id']}|{fault}|{MASTER_SEED}".encode()
        seed = int(hashlib.sha256(material).hexdigest()[:16], 16)
        rng = np.random.default_rng(seed)
        pressure += rng.normal(0.0, sigma, size=len(pressure))
    else:
        raise ValueError(f"unknown fault: {fault}")
    copied["pressure"] = np.clip(pressure, 0.0, 1.0)
    return copied


def fault_summary(stress: pd.DataFrame, deterministic: pd.DataFrame) -> pd.DataFrame:
    reference = deterministic.set_index(["block_id", "background_utilization_target"])
    rows = []
    for fault, group in stress.groupby("fault_case"):
        aligned = group.set_index(["block_id", "background_utilization_target"]).join(
            reference[["high_deadline_miss_ratio", "low_work_weighted_utility_linear", "critical_mode_fraction"]],
            rsuffix="_deterministic",
        )
        rows.append(
            {
                "fault_case": fault,
                "n_cells": len(aligned),
                "high_dmr": float(aligned.high_deadline_miss_ratio.mean()),
                "high_dmr_difference_vs_deterministic": float(
                    (aligned.high_deadline_miss_ratio - aligned.high_deadline_miss_ratio_deterministic).mean()
                ),
                "low_utility": float(aligned.low_work_weighted_utility_linear.mean()),
                "low_utility_difference_vs_deterministic": float(
                    (aligned.low_work_weighted_utility_linear - aligned.low_work_weighted_utility_linear_deterministic).mean()
                ),
                "critical_mode_fraction": float(aligned.critical_mode_fraction.mean()),
                "critical_fraction_difference_vs_deterministic": float(
                    (aligned.critical_mode_fraction - aligned.critical_mode_fraction_deterministic).mean()
                ),
                "exact_high_dmr_match": bool(
                    np.allclose(
                        aligned.high_deadline_miss_ratio.to_numpy(),
                        aligned.high_deadline_miss_ratio_deterministic.to_numpy(),
                        rtol=0.0,
                        atol=0.0,
                        equal_nan=True,
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def save_complexity(output: Path, tuned_hidden: int, ridge_model: RidgeVARRegressor):
    input_size = output_size = len(RESOURCE_NAMES)
    lstm_parameters = (
        4 * (input_size * tuned_hidden + tuned_hidden * tuned_hidden + tuned_hidden)
        + tuned_hidden * output_size
        + output_size
    )
    payload = {
        "evidence_type": "analytical counts only; not timing, WCET, MCU, energy, or hardware evidence",
        "arima_order": [5, 1, 0],
        "arima_scalar_coefficients_all_resources": 4 * 6,
        "tuned_lstm_hidden_units": tuned_hidden,
        "tuned_lstm_trainable_parameters": int(lstm_parameters),
        "tuned_lstm_approx_matrix_multiplications_per_12_step_forecast": int(
            12 * 4 * tuned_hidden * (input_size + tuned_hidden) + tuned_hidden * output_size
        ),
        "ridge_var_coefficients": int(ridge_model.coefficients.size),
    }
    (output / "analytical_model_complexity.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def make_figures(output: Path, metrics: pd.DataFrame, rolling: pd.DataFrame, faults: pd.DataFrame):
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    shown_models = ["persistence", "arima_510", "lstm_tuned", "thesis_hybrid", "adaptive_arima_lstm"]
    test = metrics[(metrics.split == "test") & metrics.model.isin(shown_models)].copy()
    pivot = test.pivot(index="resource", columns="model", values="normalized_rmse_train_sd").reindex(RESOURCE_NAMES)
    ax = pivot.plot(kind="bar", figsize=(10.2, 5.0), width=0.82)
    ax.set_ylabel("RMSE / training SD")
    ax.set_title("Held-out forecast error — thesis and advanced ARIMA+LSTM")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(fontsize=8)
    ax.figure.tight_layout()
    ax.figure.savefig(figures / "advanced_forecast_nrmse.png", dpi=240)
    ax.figure.savefig(figures / "advanced_forecast_nrmse.svg")
    plt.close(ax.figure)

    roll = rolling.groupby("model", as_index=False).normalized_rmse_train_sd.mean()
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.bar(roll.model, roll.normalized_rmse_train_sd)
    ax.set_ylabel("Mean normalized RMSE")
    ax.set_title("Eight-fold causal rolling-origin robustness")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(figures / "rolling_origin_robustness.png", dpi=240)
    fig.savefig(figures / "rolling_origin_robustness.svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    ax.bar(faults.fault_case, faults.low_utility_difference_vs_deterministic)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_ylabel("Low-utility difference vs deterministic recovery")
    ax.set_title("Predictive fault stress — utility effect under safe recovery")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(figures / "prediction_fault_utility.png", dpi=240)
    fig.savefig(figures / "prediction_fault_utility.svg")
    plt.close(fig)


def write_report(
    output: Path,
    metrics: pd.DataFrame,
    lstm_tuning: pd.DataFrame,
    blend_weights: np.ndarray,
    rolling: pd.DataFrame,
    scheduler: pd.DataFrame,
    comparisons: pd.DataFrame,
    faults: pd.DataFrame,
):
    test = metrics[metrics.split == "test"]
    forecast = test.pivot_table(index=["model", "resource"], values=["mae", "rmse", "smape_percent", "r2", "normalized_rmse_train_sd"])
    scheduler_summary = scheduler.groupby(["predictor", "policy"]).agg(
        n=("block_id", "size"),
        high_dmr=("high_deadline_miss_ratio", "mean"),
        high_response_ms=("high_mean_response", "mean"),
        low_utility=("low_work_weighted_utility_linear", "mean"),
        critical_fraction=("critical_mode_fraction", "mean"),
    )
    rolling_summary = rolling.groupby(["model", "resource"]).agg(
        folds=("fold", "nunique"),
        mean_rmse=("rmse", "mean"),
        mean_nrmse=("normalized_rmse_train_sd", "mean"),
    )
    selected = lstm_tuning.iloc[0]
    weight_text = ", ".join(
        f"{resource}={weight:.2f}" for resource, weight in zip(RESOURCE_NAMES, blend_weights)
    )
    report = f"""# Advanced ARIMA + LSTM Validation Report

## Evidence boundary

This is an additive, pre-frozen simulation-only strengthening study. The resource
targets are synthetic thesis annotations. No physical hardware, MCU timing,
energy, measured WCET, FreeRTOS execution, or safety-certification claim is made.
All primary choices are training/validation-only; the final three test dates are
held out from selection.

The three test dates had already been inspected in the earlier locked thesis
study before this advanced study was designed. Therefore the advanced model
comparison is post-lock sensitivity/robustness evidence, not a second fresh
confirmatory test, even though its computational selection uses validation only.

## Validation-selected model

Selected tuned LSTM: hidden={int(selected.hidden_units)}, learning
rate={selected.learning_rate:.3f}, validation mean normalized RMSE=
{selected.mean_validation_nrmse:.6f}. Adaptive convex LSTM weights are
**{weight_text}**; the remaining weight for each resource belongs to ARIMA(5,1,0).

## Held-out forecasting

```
{forecast.to_string(float_format=lambda x: f'{x:.6f}')}
```

No baseline is removed when it outperforms the proposed model. In particular,
distribution shift in Bandwidth remains visible rather than being tuned away on
the test set.

## Eight-fold causal rolling-origin robustness

```
{rolling_summary.to_string(float_format=lambda x: f'{x:.6f}')}
```

These folds refit each model causally and are robustness evidence, not eight
independent datasets.

## Scheduler ablation

```
{scheduler_summary.to_string(float_format=lambda x: f'{x:.6f}')}
```

Paired comparisons:

```
{comparisons.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

## Prediction-fault runtime assurance

```
{faults.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

The blackout case is the deterministic-fallback check. Stuck-high and noisy
cases intentionally expose false-positive utility cost; they are not suppressed
from the report. Forecasting remains advisory to the deterministic semantic and
utilization guards.

## Publication interpretation

The thesis mechanism is preserved: ARIMA handles periodic structure and LSTM
handles nonlinear multivariate structure. The advanced contribution is a
leakage-controlled ARIMA-LSTM ensemble plus explicit runtime assurance. The
generic deterministic RT-DASH framework remains separable for Paper 1; this
forecasting/assurance evidence belongs to the focused AI paper.
"""
    (output / "ARIMA_LSTM_ADVANCED_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("../data/processed/processed_smart_home_dataset_with_resources.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("results/arima_lstm_advanced"))
    args = parser.parse_args()
    data_path = args.data.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    if sha256(LOCKED_OUTPUT_MANIFEST.resolve()) != "8de9cbe63475c5b490550e05f36edac61316e9ba42178a31988dce61fd7a08ac":
        raise RuntimeError("locked ARIMA+LSTM result manifest changed before advanced study")

    data_audit = audit_resource_source(data_path)
    dataset = prepare_resource_forecast_dataset(data_path, interval_seconds=60)
    examples = make_forecast_examples(dataset, lookback=12)
    train = examples.mask("train")
    validation = examples.mask("validation")
    test = examples.mask("test")
    train_values = dataset.values[dataset.mask("train")]
    standardizer = TrainStandardizer.fit(train_values)

    arima_models = fit_arima_models(dataset)
    arima = arima_predict_examples(arima_models, examples)
    persistence = examples.x[:, -1, :].copy()

    anchor_lstm, anchor_history, anchor_prediction = fit_lstm_candidate(
        examples, standardizer, hidden=16, learning_rate=0.005, max_epochs=40, patience=6
    )
    thesis_hybrid = anchor_prediction.copy()
    thesis_hybrid[:, 0] = arima[:, 0]

    tuned_lstm, tuned_history, tuned_prediction, lstm_tuning, tuned_hidden, tuned_rate = tune_lstm(
        examples, standardizer
    )
    ewma_prediction, ewma_alphas, ewma_tuning = tune_ewma(examples, standardizer.scale)
    ridge_model, ridge_prediction, ridge_tuning, selected_ridge = tune_ridge_var(examples, standardizer)

    blend_weights = select_convex_blend_weights(
        examples.y[validation], arima[validation], tuned_prediction[validation], BLEND_GRID
    )
    adaptive = convex_blend_predictions(arima, tuned_prediction, blend_weights)
    predictions = {
        "persistence": persistence,
        "ewma": ewma_prediction,
        "ridge_var": ridge_prediction,
        "arima_510": arima,
        "lstm_anchor": anchor_prediction,
        "lstm_tuned": tuned_prediction,
        "thesis_hybrid": thesis_hybrid,
        "adaptive_arima_lstm": adaptive,
    }

    metrics = metric_rows(examples, predictions, standardizer.scale)
    metrics.to_csv(output / "forecast_metrics_advanced.csv", index=False)
    lstm_tuning.to_csv(output / "lstm_validation_tuning.csv", index=False)
    tuned_history.to_csv(output / "selected_lstm_training_history.csv", index=False)
    ewma_tuning.to_csv(output / "ewma_validation_tuning.csv", index=False)
    ridge_tuning.to_csv(output / "ridge_var_validation_tuning.csv", index=False)

    selection = pd.DataFrame(
        {
            "resource": RESOURCE_NAMES,
            "ewma_alpha": ewma_alphas,
            "adaptive_lstm_weight": blend_weights,
            "adaptive_arima_weight": 1.0 - blend_weights,
        }
    )
    selection.to_csv(output / "validation_selected_forecast_configuration.csv", index=False)
    np.savez_compressed(
        output / "selected_tuned_lstm_weights.npz",
        **tuned_lstm.parameters,
        train_mean=standardizer.mean,
        train_scale=standardizer.scale,
    )

    kept = examples.splits != "train"
    indices = examples.target_indices[kept]
    table = pd.DataFrame(
        {
            "timestamp": dataset.timestamps[indices].astype("datetime64[s]").astype(str),
            "split": examples.splits[kept],
            "sequence_id": dataset.sequence_ids[indices],
            "activity": dataset.activities[indices],
        }
    )
    for column, resource in enumerate(RESOURCE_NAMES):
        table[f"actual_{resource}"] = examples.y[kept, column]
        for model, prediction in predictions.items():
            table[f"{model}_{resource}"] = prediction[kept, column]
    table.to_csv(output / "advanced_forecast_predictions_validation_test.csv", index=False)

    uncertainty = forecast_uncertainty(dataset, examples, predictions)
    uncertainty.to_csv(output / "forecast_cluster_bootstrap_comparisons.csv", index=False)

    rolling = rolling_origin_study(dataset)
    rolling.to_csv(output / "rolling_origin_forecast_metrics.csv", index=False)

    pressure_predictions = {
        "arima_all": arima,
        "lstm_tuned": tuned_prediction,
        "thesis_hybrid": thesis_hybrid,
        "adaptive_arima_lstm": adaptive,
    }
    pressure = {
        name: thesis_hybrid_pressure(prediction, train_values)
        for name, prediction in pressure_predictions.items()
    }
    thresholds: dict[str, float] = {}
    tuning_frames = []
    validation_blocks_by_predictor = {}
    test_blocks_by_predictor = {}
    for predictor, scores in pressure.items():
        validation_blocks = build_blocks(dataset, examples, scores, "validation", 120)
        test_blocks = build_blocks(dataset, examples, scores, "test", 120)
        validation_blocks_by_predictor[predictor] = validation_blocks
        test_blocks_by_predictor[predictor] = test_blocks
        threshold, ranking = tune_threshold(validation_blocks, predictor)
        thresholds[predictor] = threshold
        tuning_frames.append(ranking)
    threshold_tuning = pd.concat(tuning_frames, ignore_index=True)
    threshold_tuning.to_csv(output / "scheduler_predictor_threshold_validation.csv", index=False)

    ablation_rows = []
    for predictor in pressure:
        threshold = thresholds[predictor]
        for block in test_blocks_by_predictor[predictor]:
            for load in BACKGROUND_LOADS:
                for policy in (PolicyName.RT_DASH_AI_ONLY, PolicyName.RT_DASH_AI_SAFE_RECOVERY_EDF):
                    ablation_rows.append(run_policy(block, policy, threshold, load, predictor))

    adaptive_blocks = test_blocks_by_predictor["adaptive_arima_lstm"]
    adaptive_threshold = thresholds["adaptive_arima_lstm"]
    for block in adaptive_blocks:
        for load in BACKGROUND_LOADS:
            for policy in (
                PolicyName.RT_DASH_NO_EVENT_TRIGGER,
                PolicyName.RT_DASH,
                PolicyName.RT_DASH_RECOVERY_EDF,
            ):
                ablation_rows.append(
                    run_policy(block, policy, adaptive_threshold, load, "deterministic_baseline")
                )
    scheduler = pd.DataFrame(ablation_rows)
    scheduler.to_csv(output / "scheduler_predictor_ablation_runs.csv", index=False)
    scheduler_comparisons = scheduler_pairwise(scheduler)
    scheduler_comparisons.to_csv(output / "scheduler_predictor_paired_comparisons.csv", index=False)

    stress_rows = []
    for block in adaptive_blocks:
        for fault in FAULT_CASES:
            corrupted = corrupt_pressure(block, fault)
            for load in BACKGROUND_LOADS:
                row = run_policy(
                    corrupted,
                    PolicyName.RT_DASH_AI_SAFE_RECOVERY_EDF,
                    adaptive_threshold,
                    load,
                    "adaptive_arima_lstm",
                )
                row["fault_case"] = fault
                stress_rows.append(row)
    stress = pd.DataFrame(stress_rows)
    stress.to_csv(output / "prediction_fault_stress_runs.csv", index=False)
    deterministic = scheduler[
        (scheduler.predictor == "deterministic_baseline")
        & (scheduler.policy == "rt_dash_recovery_edf")
    ].copy()
    faults = fault_summary(stress, deterministic)
    faults.to_csv(output / "prediction_fault_stress_summary.csv", index=False)

    blackout = faults[faults.fault_case == "blackout"].iloc[0]
    if not bool(blackout.exact_high_dmr_match):
        raise RuntimeError("blackout safety fallback failed exact high-DMR equality")
    blackout_rows = stress[stress.fault_case == "blackout"].set_index(
        ["block_id", "background_utilization_target"]
    )
    deterministic_rows = deterministic.set_index(["block_id", "background_utilization_target"])
    for metric in ("high_deadline_miss_ratio", "low_work_weighted_utility_linear", "critical_mode_fraction"):
        if not np.allclose(
            blackout_rows[metric].to_numpy(),
            deterministic_rows[metric].to_numpy(),
            rtol=0.0,
            atol=0.0,
            equal_nan=True,
        ):
            raise RuntimeError(f"blackout fallback failed exact equality for {metric}")

    save_complexity(output, tuned_hidden, ridge_model)
    make_figures(output, metrics, rolling, faults)
    write_report(output, metrics, lstm_tuning, blend_weights, rolling, scheduler, scheduler_comparisons, faults)

    dates = dataset.timestamps.astype("datetime64[D]")
    manifest = {
        "study": "advanced thesis-preserving ARIMA+LSTM forecasting and deterministic runtime assurance",
        "protocol_sha256": sha256(PROTOCOL.resolve()),
        "locked_thesis_protocol_sha256": sha256(LOCKED_PROTOCOL.resolve()),
        "locked_thesis_output_manifest_sha256": sha256(LOCKED_OUTPUT_MANIFEST.resolve()),
        "processed_resource_sha256": sha256(data_path),
        "resource_data_quality": data_audit,
        "resource_columns_are_synthetic_thesis_annotations": True,
        "hardware_used": False,
        "primary_train_dates": sorted(np.unique(dates[dataset.mask("train")]).astype(str).tolist()),
        "primary_validation_dates": sorted(np.unique(dates[dataset.mask("validation")]).astype(str).tolist()),
        "primary_test_dates": sorted(np.unique(dates[dataset.mask("test")]).astype(str).tolist()),
        "train_examples": int(train.sum()),
        "validation_examples": int(validation.sum()),
        "test_examples": int(test.sum()),
        "lstm_candidates": len(LSTM_GRID),
        "selected_lstm_hidden_units": int(tuned_hidden),
        "selected_lstm_learning_rate": float(tuned_rate),
        "selected_lstm_epochs": int(len(tuned_history)),
        "selected_ridge": float(selected_ridge),
        "ewma_alphas": {r: float(v) for r, v in zip(RESOURCE_NAMES, ewma_alphas)},
        "adaptive_lstm_weights": {r: float(v) for r, v in zip(RESOURCE_NAMES, blend_weights)},
        "rolling_origin_folds": int(rolling.fold.nunique()),
        "scheduler_predictors": list(pressure.keys()),
        "scheduler_thresholds": thresholds,
        "scheduler_threshold_selection": "validation only",
        "scheduler_tuning_runs": int(sum(len(frame) * len(validation_blocks_by_predictor[name]) * len(BACKGROUND_LOADS) for name, frame in zip(pressure.keys(), tuning_frames))),
        "scheduler_ablation_test_runs": int(len(scheduler)),
        "prediction_fault_stress_runs": int(len(stress)),
        "new_scheduler_simulations_total": int(sum(len(frame) * len(validation_blocks_by_predictor[name]) * len(BACKGROUND_LOADS) for name, frame in zip(pressure.keys(), tuning_frames)) + len(scheduler) + len(stress)),
        "test_used_for_selection": False,
        "prior_locked_results_modified": False,
    }
    (output / "arima_lstm_advanced_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    artifacts = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS_ARIMA_LSTM_ADVANCED.txt"
    )
    (output / "SHA256SUMS_ARIMA_LSTM_ADVANCED.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(output)}" for path in artifacts) + "\n",
        encoding="utf-8",
    )
    print("ARIMA+LSTM ADVANCED STUDY: DONE")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
