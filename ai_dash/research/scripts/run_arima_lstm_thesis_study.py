from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from rt_dash.ai import cluster_bootstrap_mean_ci, predictive_signals
from rt_dash.forecasting import (
    RESOURCE_NAMES,
    NumpyLSTMRegressor,
    TrainStandardizer,
    arima_predict_examples,
    audit_resource_source,
    fit_arima_models,
    make_forecast_examples,
    prepare_resource_forecast_dataset,
    regression_metrics,
    thesis_hybrid_pressure,
)
from rt_dash.metrics import summarize_result
from rt_dash.model import TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import EventRelease, SimulationConfig, Simulator
from rt_dash.workloads import ACTIVITY_TEMPLATE, scaled_periodic_taskset


BACKGROUND_LOADS = (0.30, 0.45, 0.60)
ACTIVITY_INDEX = {
    0: "sleep",
    1: "eat",
    2: "work",
    3: "personal",
    4: "other",
    5: "anomaly",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metrics_table(examples, predictions: dict[str, np.ndarray], train_scale: np.ndarray) -> pd.DataFrame:
    rows = []
    for split in ("train", "validation", "test"):
        mask = examples.mask(split)
        for model_name, predicted in predictions.items():
            for column, resource in enumerate(RESOURCE_NAMES):
                row = regression_metrics(
                    examples.y[mask, column], predicted[mask, column], train_scale[column]
                )
                rows.append(
                    {
                        "split": split,
                        "model": model_name,
                        "resource": resource,
                        "n": int(mask.sum()),
                        **row,
                    }
                )
    return pd.DataFrame(rows)


def prediction_table(dataset, examples, predictions, pressure) -> pd.DataFrame:
    keep = examples.splits != "train"
    indices = examples.target_indices[keep]
    frame = pd.DataFrame(
        {
            "timestamp": dataset.timestamps[indices].astype("datetime64[s]").astype(str),
            "split": examples.splits[keep],
            "sequence_id": dataset.sequence_ids[indices],
            "activity": dataset.activities[indices],
            "hybrid_pressure": pressure[keep],
        }
    )
    for column, resource in enumerate(RESOURCE_NAMES):
        frame[f"actual_{resource}"] = examples.y[keep, column]
        for model_name, predicted in predictions.items():
            frame[f"{model_name}_{resource}"] = predicted[keep, column]
    return frame


def build_blocks(dataset, examples, pressure: np.ndarray, split: str, block_rows: int = 120):
    selected_rows = np.flatnonzero(examples.mask(split))
    target_indices = examples.target_indices
    dates = dataset.timestamps.astype("datetime64[D]")
    blocks = []
    for date in np.unique(dates[target_indices[selected_rows]]):
        date_rows = selected_rows[dates[target_indices[selected_rows]] == date]
        for sequence in np.unique(dataset.sequence_ids[target_indices[date_rows]]):
            sequence_rows = date_rows[
                dataset.sequence_ids[target_indices[date_rows]] == sequence
            ]
            for start in range(0, len(sequence_rows), block_rows):
                rows = sequence_rows[start : start + block_rows]
                if len(rows) < max(30, block_rows // 4):
                    continue
                targets = target_indices[rows]
                blocks.append(
                    {
                        "block_id": f"{str(date)}_s{int(sequence)}_b{start // block_rows}",
                        "date": str(date),
                        "sequence_id": int(sequence),
                        "pressure": pressure[rows],
                        "activities": dataset.activities[targets],
                    }
                )
    return blocks


def trace_events(activities: np.ndarray, block_id: str, step_ms: int):
    releases = []
    for index, activity_code in enumerate(activities):
        activity = ACTIVITY_INDEX.get(int(activity_code), "other")
        normalized, criticality, wcet, deadline, degradable, floor = ACTIVITY_TEMPLATE[activity]
        task = TaskSpec(
            task_id=f"{block_id}_{index}",
            name=f"ARIMA-LSTM trace activity: {normalized}",
            wcet=wcet,
            relative_deadline=deadline,
            criticality=criticality,
            period=None,
            degradable=degradable,
            min_service_fraction=floor,
            source=f"thesis_arima_lstm_{block_id}",
        )
        releases.append(EventRelease(task, index * step_ms))
    return releases


def run_trace_policy(
    block,
    policy: PolicyName,
    threshold: float,
    background_load: float,
    step_ms: int = 100,
    quantum: int = 10,
):
    activities = np.asarray(block["activities"])
    pressure = np.asarray(block["pressure"], dtype=float)
    duration = len(activities) * step_ms + 1_000
    seed = int(hashlib.sha256(str(block["block_id"]).encode()).hexdigest()[:8], 16)
    periodic = scaled_periodic_taskset(background_load, seed % 10_000)
    events = trace_events(activities, str(block["block_id"]), step_ms)
    signals = predictive_signals(pressure, step_ms, source="thesis-arima-lstm-hybrid")
    config = SimulationConfig(
        duration=duration,
        quantum=quantum,
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
            "predictor": "thesis_arima_lstm_hybrid",
        }
    )
    return row


def scheduling_objective(frame: pd.DataFrame) -> float:
    high_dmr = float(frame.high_deadline_miss_ratio.fillna(0.0).mean())
    high_response = float((frame.high_mean_response.fillna(0.0) / 500.0).clip(0, 2).mean())
    low_loss = 1.0 - float(frame.low_work_weighted_utility_linear.fillna(1.0).mean())
    critical_fraction = float(frame.critical_mode_fraction.mean())
    return 0.55 * high_dmr + 0.15 * high_response + 0.20 * low_loss + 0.10 * critical_fraction


def tune_scheduler_threshold(blocks, quantum: int = 10, step_ms: int = 100):
    values = np.concatenate([np.asarray(block["pressure"], dtype=float) for block in blocks])
    candidates = np.unique(
        np.r_[0.5, np.quantile(values, [0.50, 0.65, 0.75, 0.85, 0.90, 0.95, 0.98, 0.99])]
    )
    rows = []
    for threshold in candidates:
        frame = pd.DataFrame(
            run_trace_policy(
                block, PolicyName.RT_DASH_AI_ONLY, float(threshold), load, step_ms, quantum
            )
            for block in blocks
            for load in BACKGROUND_LOADS
        )
        rows.append(
            {
                "threshold": float(threshold),
                "objective": scheduling_objective(frame),
                "high_dmr": float(frame.high_deadline_miss_ratio.fillna(0.0).mean()),
                "high_mean_response": float(frame.high_mean_response.dropna().mean())
                if frame.high_mean_response.notna().any()
                else np.nan,
                "low_utility": float(frame.low_work_weighted_utility_linear.dropna().mean()),
                "critical_mode_fraction": float(frame.critical_mode_fraction.mean()),
                "selection_split": "validation",
            }
        )
    ranking = pd.DataFrame(rows).sort_values(["objective", "threshold"], ascending=[True, False])
    return float(ranking.iloc[0].threshold), ranking.reset_index(drop=True)


def holm_adjust(pvalues: np.ndarray) -> np.ndarray:
    pvalues = np.asarray(pvalues, dtype=float)
    order = np.argsort(np.nan_to_num(pvalues, nan=1.0))
    adjusted = np.ones(len(pvalues), dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (len(pvalues) - rank) * np.nan_to_num(pvalues[index], nan=1.0))
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def scheduling_comparisons(frame: pd.DataFrame) -> pd.DataFrame:
    specs = (
        ("rt_dash_ai_only", "rt_dash_no_event_trigger", "high_deadline_miss_ratio"),
        ("rt_dash_ai_only", "rt_dash", "high_deadline_miss_ratio"),
        ("rt_dash_ai_only", "rt_dash", "high_mean_response"),
        ("rt_dash_ai_safe_recovery_edf", "rt_dash_recovery_edf", "high_deadline_miss_ratio"),
        ("rt_dash_ai_safe_recovery_edf", "rt_dash_recovery_edf", "low_work_weighted_utility_linear"),
        ("rt_dash_ai_safe_recovery_edf", "rt_dash_recovery_edf", "critical_mode_fraction"),
    )
    rows = []
    for left, right, metric in specs:
        wide = frame.pivot_table(
            index=["block_id", "source_date", "background_utilization_target"],
            columns="policy",
            values=metric,
        )
        if left not in wide or right not in wide:
            continue
        paired = wide[[left, right]].dropna()
        differences = (paired[left] - paired[right]).to_numpy(dtype=float)
        clusters = paired.index.get_level_values("source_date").to_numpy()
        low, high = cluster_bootstrap_mean_ci(differences, clusters, seed=20260806)
        try:
            pvalue = float(stats.wilcoxon(differences, zero_method="zsplit").pvalue)
        except ValueError:
            pvalue = 1.0
        rows.append(
            {
                "left": left,
                "right": right,
                "metric": metric,
                "n_cells": len(differences),
                "n_date_clusters": len(np.unique(clusters)),
                "mean_difference": float(np.mean(differences)),
                "date_cluster_bootstrap_ci95_low": low,
                "date_cluster_bootstrap_ci95_high": high,
                "wilcoxon_p_uncorrected": pvalue,
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result["holm_p"] = holm_adjust(result.wilcoxon_p_uncorrected.to_numpy())
    return result


def make_figures(output: Path, dataset, examples, predictions, scheduling: pd.DataFrame):
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    test = np.flatnonzero(examples.mask("test"))
    shown = test[: min(360, len(test))]
    timestamps = dataset.timestamps[examples.target_indices[shown]]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(timestamps, examples.y[shown, 0], label="actual CPU", linewidth=1.4)
    ax.plot(timestamps, predictions["arima_510"][shown, 0], label="ARIMA(5,1,0)", alpha=0.85)
    ax.plot(timestamps, predictions["lstm"][shown, 0], label="LSTM", alpha=0.8)
    ax.set_title("Thesis resource forecasting — held-out CPU excerpt")
    ax.set_ylabel("Synthetic CPU annotation")
    ax.tick_params(axis="x", rotation=25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "heldout_cpu_forecast.png", dpi=240)
    fig.savefig(figures / "heldout_cpu_forecast.svg")
    plt.close(fig)

    aggregate = scheduling.groupby("policy", as_index=False).agg(
        high_dmr=("high_deadline_miss_ratio", "mean"),
        low_utility=("low_work_weighted_utility_linear", "mean"),
    )
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    x = np.arange(len(aggregate))
    ax.bar(x - 0.18, aggregate.high_dmr, width=0.36, label="high DMR")
    ax.bar(x + 0.18, 1.0 - aggregate.low_utility, width=0.36, label="1 - low utility")
    ax.set_xticks(x, aggregate.policy, rotation=35, ha="right")
    ax.set_title("ARIMA+LSTM predictive RT-DASH — held-out scheduling")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "heldout_scheduler_tradeoff.png", dpi=240)
    fig.savefig(figures / "heldout_scheduler_tradeoff.svg")
    plt.close(fig)


def write_report(output: Path, metrics: pd.DataFrame, history: pd.DataFrame, threshold: float, scheduling: pd.DataFrame, comparisons: pd.DataFrame):
    test = metrics[metrics.split == "test"]
    summary = test.pivot_table(index=["model", "resource"], values=["mae", "rmse", "smape_percent", "r2", "normalized_rmse_train_sd"])
    schedule_summary = scheduling.groupby("policy").agg(
        n=("block_id", "size"),
        high_dmr=("high_deadline_miss_ratio", "mean"),
        high_response_ms=("high_mean_response", "mean"),
        low_utility=("low_work_weighted_utility_linear", "mean"),
        critical_mode_fraction=("critical_mode_fraction", "mean"),
    )
    report = f"""# ARIMA + LSTM Thesis-Completion Validation Report

## Evidence boundary

This study implements the thesis-predicted resource branch with a real
ARIMA(5,1,0), a trained multivariate LSTM, and the thesis hybrid. The four
resource columns are fixed **synthetic thesis simulation annotations**, not
physical measurements. All forecasting windows are chronological and causal.

## Held-out forecasting metrics

```
{summary.to_string(float_format=lambda x: f'{x:.6f}')}
```

The thesis hybrid uses ARIMA for CPU and LSTM for Memory/Storage/Bandwidth.
Persistence is retained as a necessary forecasting baseline. No inferior model
or negative metric is removed.

## LSTM training

The LSTM stopped after {len(history)} epochs using validation-only early
stopping. Its best validation standardized MSE is
{history.validation_mse_standardized.min():.6f}. The test split never selects an
epoch, architecture, scale, or scheduler threshold.

## Predictive scheduler integration

Validation selected hybrid-pressure threshold: **{threshold:.9f}**.

```
{schedule_summary.to_string(float_format=lambda x: f'{x:.6f}')}
```

Paired held-out comparisons:

```
{comparisons.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

The safe ARIMA+LSTM policies retain the semantic-event and utilization guards.
Forecasting is advisory; it cannot suppress deterministic mode entry.

## Publication interpretation

This branch demonstrates that the ARIMA/LSTM mechanism described in the thesis
is now genuinely implemented, leakage-controlled and connected to RT-DASH. It
does **not** convert synthetic resource annotations into claims of measured
hardware demand. The existing raw-sensor AI study remains separate evidence and
is not overwritten by this thesis-completion branch.
"""
    (output / "ARIMA_LSTM_THESIS_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("../data/processed/processed_smart_home_dataset_with_resources.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("results/arima_lstm_thesis"))
    args = parser.parse_args()
    data_path = args.data.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    data_audit = audit_resource_source(data_path)
    (output / "resource_data_quality_audit.json").write_text(
        json.dumps(data_audit, indent=2) + "\n", encoding="utf-8"
    )
    dataset = prepare_resource_forecast_dataset(data_path, interval_seconds=60)
    examples = make_forecast_examples(dataset, lookback=12)
    train_examples = examples.mask("train")
    validation_examples = examples.mask("validation")
    test_examples = examples.mask("test")
    train_values = dataset.values[dataset.mask("train")]
    standardizer = TrainStandardizer.fit(train_values)

    arima_models = fit_arima_models(dataset)
    arima_prediction = arima_predict_examples(arima_models, examples)

    lstm = NumpyLSTMRegressor(input_size=4, hidden_size=16, output_size=4, seed=20260806)
    x_standardized = standardizer.transform(examples.x)
    y_standardized = standardizer.transform(examples.y)
    history_rows = lstm.fit(
        x_standardized[train_examples],
        y_standardized[train_examples],
        x_standardized[validation_examples],
        y_standardized[validation_examples],
        learning_rate=0.005,
        batch_size=128,
        max_epochs=40,
        patience=6,
        gradient_clip=5.0,
    )
    history = pd.DataFrame(history_rows)
    lstm_prediction = standardizer.inverse_transform(lstm.predict(x_standardized))
    persistence = examples.x[:, -1, :].copy()
    hybrid = lstm_prediction.copy()
    hybrid[:, 0] = arima_prediction[:, 0]
    predictions = {
        "persistence": persistence,
        "arima_510": arima_prediction,
        "lstm": lstm_prediction,
        "thesis_hybrid": hybrid,
    }

    metrics = metrics_table(examples, predictions, standardizer.scale)
    metrics.to_csv(output / "forecast_metrics.csv", index=False)
    history.to_csv(output / "lstm_training_history.csv", index=False)
    pressure = thesis_hybrid_pressure(hybrid, train_values)
    prediction_table(dataset, examples, predictions, pressure).to_csv(
        output / "forecast_predictions_validation_test.csv", index=False
    )
    np.savez_compressed(
        output / "lstm_weights.npz",
        **lstm.parameters,
        train_mean=standardizer.mean,
        train_scale=standardizer.scale,
    )
    arima_payload = {
        resource: model.coefficients.tolist()
        for resource, model in zip(RESOURCE_NAMES, arima_models)
    }
    (output / "arima_510_coefficients.json").write_text(
        json.dumps(arima_payload, indent=2) + "\n", encoding="utf-8"
    )

    validation_blocks = build_blocks(dataset, examples, pressure, "validation", 120)
    test_blocks = build_blocks(dataset, examples, pressure, "test", 120)
    threshold, ranking = tune_scheduler_threshold(validation_blocks)
    ranking.to_csv(output / "scheduler_threshold_validation.csv", index=False)
    policies = (
        PolicyName.EDF,
        PolicyName.RT_DASH_NO_EVENT_TRIGGER,
        PolicyName.RT_DASH,
        PolicyName.RT_DASH_RECOVERY_EDF,
        PolicyName.RT_DASH_AI_ONLY,
        PolicyName.RT_DASH_AI_SAFE,
        PolicyName.RT_DASH_AI_SAFE_RECOVERY_EDF,
    )
    scheduling = pd.DataFrame(
        run_trace_policy(block, policy, threshold, load)
        for block in test_blocks
        for load in BACKGROUND_LOADS
        for policy in policies
    )
    scheduling.to_csv(output / "scheduling_integration_runs.csv", index=False)
    comparisons = scheduling_comparisons(scheduling)
    comparisons.to_csv(output / "scheduling_paired_comparisons.csv", index=False)

    make_figures(output, dataset, examples, predictions, scheduling)
    write_report(output, metrics, history, threshold, scheduling, comparisons)

    unique_dates = dataset.timestamps.astype("datetime64[D]")
    manifest = {
        "study": "thesis-faithful ARIMA+LSTM resource forecasting and RT-DASH integration",
        "processed_resource_sha256": sha256(data_path),
        "frozen_protocol_sha256": sha256(
            Path("docs/ARIMA_LSTM_THESIS_PROTOCOL_FROZEN_2026-08-06.md").resolve()
        ),
        "resource_data_quality": data_audit,
        "resource_columns_are_synthetic_thesis_annotations": True,
        "hardware_used": False,
        "interval_seconds": 60,
        "lookback_intervals": 12,
        "forecast_horizon_intervals": 1,
        "arima_order": [5, 1, 0],
        "lstm_hidden_units": 16,
        "lstm_seed": 20260806,
        "train_examples": int(train_examples.sum()),
        "validation_examples": int(validation_examples.sum()),
        "test_examples": int(test_examples.sum()),
        "train_dates": sorted(np.unique(unique_dates[dataset.mask("train")]).astype(str).tolist()),
        "validation_dates": sorted(np.unique(unique_dates[dataset.mask("validation")]).astype(str).tolist()),
        "test_dates": sorted(np.unique(unique_dates[dataset.mask("test")]).astype(str).tolist()),
        "lstm_epochs_executed": int(len(history)),
        "validation_blocks": int(len(validation_blocks)),
        "test_blocks": int(len(test_blocks)),
        "scheduler_threshold": threshold,
        "scheduler_threshold_selected_on": "validation only",
        "scheduler_threshold_candidates": int(len(ranking)),
        "scheduler_tuning_runs": int(len(ranking) * len(validation_blocks) * len(BACKGROUND_LOADS)),
        "scheduler_test_runs": int(len(scheduling)),
        "test_used_for_model_or_threshold_selection": False,
        "prior_locked_results_modified": False,
    }
    (output / "arima_lstm_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    artifacts = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS_ARIMA_LSTM.txt"
    )
    (output / "SHA256SUMS_ARIMA_LSTM.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(output)}" for path in artifacts) + "\n",
        encoding="utf-8",
    )
    print("ARIMA+LSTM THESIS STUDY: DONE")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
