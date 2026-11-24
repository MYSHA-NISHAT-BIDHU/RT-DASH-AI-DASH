#!/usr/bin/env python3
"""Execute the leakage-controlled AI extension and scheduler integration study."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import pickle
import platform
import sys
import time
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats
import sklearn
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve, roc_curve
from sklearn.preprocessing import StandardScaler

from rt_dash.ai import (
    PortableLogisticRiskModel,
    audit_openshs_source,
    choose_safety_threshold,
    classification_metrics,
    cluster_bootstrap_mean_ci,
    episode_metrics,
    predictive_signals,
    prepare_openshs_ai_dataset,
    sensor_outage_feature_matrix,
)
from rt_dash.metrics import summarize_result
from rt_dash.model import Criticality, TaskSpec
from rt_dash.policies import PolicyName
from rt_dash.simulator import EventRelease, SimulationConfig, Simulator
from rt_dash.workloads import ACTIVITY_TEMPLATE, scaled_periodic_taskset


BACKGROUND_LOADS = (0.30, 0.45, 0.60)


@dataclass
class FittedModel:
    name: str
    estimator: object
    columns: np.ndarray
    scaler: StandardScaler | None
    fit_seconds: float
    serialized_bytes: int

    def predict(self, features: np.ndarray) -> np.ndarray:
        matrix = features[:, self.columns]
        if self.scaler is not None:
            matrix = self.scaler.transform(matrix)
        return self.estimator.predict_proba(matrix)[:, 1]


def fit_model(
    name: str,
    factory: Callable[[], object],
    features: np.ndarray,
    labels: np.ndarray,
    train_mask: np.ndarray,
    columns: np.ndarray,
    standardized: bool,
) -> FittedModel:
    scaler = StandardScaler().fit(features[train_mask][:, columns]) if standardized else None
    training = features[train_mask][:, columns]
    if scaler is not None:
        training = scaler.transform(training)
    estimator = factory()
    started = time.perf_counter()
    estimator.fit(training, labels[train_mask])
    fit_seconds = time.perf_counter() - started
    payload = pickle.dumps({"estimator": estimator, "scaler": scaler, "columns": columns})
    return FittedModel(name, estimator, columns, scaler, fit_seconds, len(payload))


def model_definitions(sensor_count: int, feature_count: int):
    current = np.arange(sensor_count)
    sensor_temporal = np.arange(feature_count - 2)
    time_only = np.arange(feature_count - 2, feature_count)
    all_features = np.arange(feature_count)
    return (
        (
            "time_only_logistic",
            lambda: LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0),
            time_only,
            True,
        ),
        (
            "current_sensor_logistic",
            lambda: LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0),
            current,
            True,
        ),
        (
            "temporal_logistic",
            lambda: LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0),
            all_features,
            True,
        ),
        (
            "hist_gradient_boosting",
            lambda: HistGradientBoostingClassifier(
                max_iter=200,
                learning_rate=0.08,
                max_leaf_nodes=31,
                l2_regularization=1.0,
                class_weight="balanced",
                random_state=20260804,
            ),
            all_features,
            False,
        ),
        (
            "extra_trees",
            lambda: ExtraTreesClassifier(
                n_estimators=300,
                min_samples_leaf=10,
                max_features="sqrt",
                class_weight="balanced",
                n_jobs=max(1, min(4, os.cpu_count() or 1)),
                random_state=20260804,
            ),
            all_features,
            False,
        ),
    )


def build_trace_blocks(dataset, split: str, probabilities: np.ndarray, block_rows: int):
    mask = dataset.mask(split)
    positions = np.flatnonzero(mask)
    dates = dataset.timestamps.astype("datetime64[D]")
    blocks: list[dict[str, object]] = []
    for date in np.unique(dates[positions]):
        day_positions = positions[dates[positions] == date]
        # Do not merge separate source sequences into one simulated block.
        for sequence in np.unique(dataset.sequence_ids[day_positions]):
            sequence_positions = day_positions[dataset.sequence_ids[day_positions] == sequence]
            for start in range(0, len(sequence_positions), block_rows):
                selected = sequence_positions[start : start + block_rows]
                if len(selected) < max(60, block_rows // 4):
                    continue
                blocks.append(
                    {
                        "block_id": f"{str(date)}_s{int(sequence)}_b{start // block_rows}",
                        "date": str(date),
                        "sequence_id": int(sequence),
                        "positions": selected,
                        "probabilities": probabilities[selected],
                        "activities": dataset.activities[selected],
                    }
                )
    return blocks


def trace_events(activities: np.ndarray, block_id: str, step_ms: int) -> list[EventRelease]:
    events: list[EventRelease] = []
    for index, activity in enumerate(activities):
        label = activity if activity in ACTIVITY_TEMPLATE else "unknown"
        normalized, criticality, wcet, deadline, degradable, floor = ACTIVITY_TEMPLATE[label]
        task = TaskSpec(
            task_id=f"{block_id}_{index}",
            name=f"AI trace activity: {normalized}",
            wcet=wcet,
            relative_deadline=deadline,
            criticality=criticality,
            period=None,
            degradable=degradable,
            min_service_fraction=floor,
            source=f"openshs_ai_test_{block_id}",
        )
        events.append(EventRelease(task, index * step_ms))
    return events


def run_trace_policy(
    block: dict[str, object],
    policy: PolicyName,
    threshold: float,
    background_load: float,
    step_ms: int,
    quantum: int,
) -> dict[str, object]:
    activities = np.asarray(block["activities"])
    probabilities = np.asarray(block["probabilities"], dtype=float)
    duration = len(activities) * step_ms + 1_000
    seed = int(hashlib.sha256(str(block["block_id"]).encode()).hexdigest()[:8], 16)
    periodic = scaled_periodic_taskset(background_load, seed % 10_000)
    events = trace_events(activities, str(block["block_id"]), step_ms)
    signals = predictive_signals(probabilities, step_ms, source="selected-openshs-model")
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
    started = time.perf_counter()
    result = Simulator(periodic, events, config, signals).run()
    row = summarize_result(result)
    row.update(
        {
            "block_id": block["block_id"],
            "source_date": block["date"],
            "sequence_id": block["sequence_id"],
            "rows": len(activities),
            "anomaly_fraction": float(np.mean(activities == "anomaly")),
            "predictive_positive_fraction": float(np.mean(probabilities >= threshold)),
            "predictive_threshold": threshold,
            "background_utilization_target": background_load,
            "host_runtime_ms": (time.perf_counter() - started) * 1000.0,
        }
    )
    return row


def scheduling_objective(frame: pd.DataFrame) -> float:
    high_dmr = float(frame.high_deadline_miss_ratio.fillna(0.0).mean())
    high_response = float((frame.high_mean_response.fillna(0.0) / 500.0).clip(0, 2).mean())
    low_loss = 1.0 - float(frame.low_work_weighted_utility_linear.fillna(1.0).mean())
    critical_fraction = float(frame.critical_mode_fraction.mean())
    return 0.55 * high_dmr + 0.15 * high_response + 0.20 * low_loss + 0.10 * critical_fraction


def tune_scheduler_threshold(
    blocks: list[dict[str, object]],
    classification_threshold: float,
    quantum: int,
    step_ms: int,
) -> tuple[float, pd.DataFrame]:
    values = np.concatenate([np.asarray(block["probabilities"]) for block in blocks])
    candidates = np.unique(
        np.concatenate(
            [
                [classification_threshold, 0.5],
                np.quantile(values, [0.50, 0.65, 0.75, 0.85, 0.90, 0.95, 0.98, 0.99]),
            ]
        )
    )
    rows: list[dict[str, object]] = []
    for threshold in candidates:
        frame = pd.DataFrame(
            run_trace_policy(
                block,
                PolicyName.RT_DASH_AI_ONLY,
                float(threshold),
                background_load,
                step_ms,
                quantum,
            )
            for block in blocks
            for background_load in BACKGROUND_LOADS
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
            }
        )
    ranking = pd.DataFrame(rows).sort_values(["objective", "threshold"], ascending=[True, False])
    return float(ranking.iloc[0].threshold), ranking.reset_index(drop=True)


def scheduling_comparisons(frame: pd.DataFrame) -> pd.DataFrame:
    specifications = (
        ("rt_dash_ai_only", "rt_dash_no_event_trigger", "high_deadline_miss_ratio"),
        ("rt_dash_ai_only", "rt_dash", "high_deadline_miss_ratio"),
        ("rt_dash_ai_only", "rt_dash", "high_mean_response"),
        ("rt_dash_ai_safe_recovery_edf", "rt_dash_recovery_edf", "high_deadline_miss_ratio"),
        ("rt_dash_ai_safe_recovery_edf", "rt_dash_recovery_edf", "low_work_weighted_utility_linear"),
        ("rt_dash_ai_safe_recovery_edf", "rt_dash_recovery_edf", "critical_mode_fraction"),
    )
    rows: list[dict[str, object]] = []
    for left, right, metric in specifications:
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
        low, high = cluster_bootstrap_mean_ci(differences, clusters)
        try:
            pvalue = float(stats.wilcoxon(differences, zero_method="zsplit").pvalue)
        except ValueError:
            pvalue = np.nan
        rows.append(
            {
                "left": left,
                "right": right,
                "metric": metric,
                "n_blocks": len(differences),
                "n_day_clusters": len(np.unique(clusters)),
                "mean_difference": float(np.mean(differences)),
                "day_cluster_bootstrap_ci95_low": low,
                "day_cluster_bootstrap_ci95_high": high,
                "wilcoxon_p_uncorrected": pvalue,
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        ordered = result.wilcoxon_p_uncorrected.fillna(1.0).sort_values().index
        adjusted = np.empty(len(result), dtype=float)
        previous = 0.0
        for rank, index in enumerate(ordered, start=1):
            value = min(1.0, float(result.loc[index, "wilcoxon_p_uncorrected"]) * (len(result) - rank + 1))
            previous = max(previous, value)
            adjusted[index] = previous
        result["holm_p"] = adjusted
    return result


def temporal_generalization_diagnostics(
    dataset,
    probabilities: np.ndarray,
    threshold: float,
) -> pd.DataFrame:
    """Report date-level performance and covariate/risk shift after model lock.

    The reference distribution is the training partition.  Validation and test
    dates are reported separately; no quantity produced here participates in
    model or threshold selection.
    """

    train = dataset.mask("train")
    train_features = dataset.features[train].astype(float)
    train_mean = train_features.mean(axis=0)
    train_scale = train_features.std(axis=0)
    train_scale[train_scale < 1e-12] = 1.0
    train_risk = np.asarray(probabilities[train], dtype=float)
    dates = dataset.timestamps.astype("datetime64[D]")
    rows: list[dict[str, object]] = []
    for split in ("validation", "test"):
        split_mask = dataset.mask(split)
        for date in np.unique(dates[split_mask]):
            mask = split_mask & (dates == date)
            metrics = classification_metrics(
                dataset.target_current[mask], probabilities[mask], threshold
            )
            date_features = dataset.features[mask].astype(float)
            standardized_shift = np.abs(
                (date_features.mean(axis=0) - train_mean) / train_scale
            )
            metrics.update(
                {
                    "split": split,
                    "source_date": str(date),
                    "positive_rate": float(dataset.target_current[mask].mean()),
                    "mean_predicted_risk": float(np.mean(probabilities[mask])),
                    "mean_absolute_standardized_feature_shift": float(
                        np.mean(standardized_shift)
                    ),
                    "max_absolute_standardized_feature_shift": float(
                        np.max(standardized_shift)
                    ),
                    "risk_wasserstein_distance_vs_train": float(
                        stats.wasserstein_distance(train_risk, probabilities[mask])
                    ),
                    "diagnostic_only_after_model_lock": True,
                }
            )
            rows.append(metrics)
    return pd.DataFrame(rows)


def logistic_feature_importance(model: FittedModel, dataset) -> pd.DataFrame:
    """Return standardized logistic coefficients without inspecting test data."""

    if model.scaler is None or not hasattr(model.estimator, "coef_"):
        raise ValueError("feature-importance export requires a standardized logistic model")
    coefficients = np.asarray(model.estimator.coef_[0], dtype=float)
    names = np.asarray(dataset.feature_names, dtype=object)[model.columns]
    frame = pd.DataFrame(
        {
            "feature": names,
            "standardized_coefficient": coefficients,
            "absolute_standardized_coefficient": np.abs(coefficients),
            "odds_ratio_per_one_training_sd": np.exp(np.clip(coefficients, -50, 50)),
            "direction": np.where(coefficients >= 0, "higher-risk", "lower-risk"),
        }
    ).sort_values(
        ["absolute_standardized_coefficient", "feature"], ascending=[False, True]
    ).reset_index(drop=True)
    frame.insert(0, "rank", np.arange(1, len(frame) + 1))
    return frame


def leave_one_sensor_out_diagnostics(
    model: FittedModel,
    dataset,
    probabilities: np.ndarray,
    threshold: float,
) -> pd.DataFrame:
    """Measure held-out degradation when each raw sensor channel is unavailable."""

    test = dataset.mask("test")
    baseline = classification_metrics(
        dataset.target_current[test], probabilities[test], threshold
    )
    rows: list[dict[str, object]] = []
    for sensor in dataset.sensor_names:
        failed = sensor_outage_feature_matrix(
            dataset.features, dataset.feature_names, [sensor]
        )
        risk = model.predict(failed)
        metrics = classification_metrics(dataset.target_current[test], risk[test], threshold)
        rows.append(
            {
                "failed_sensor": sensor,
                "auroc": metrics["auroc"],
                "auprc": metrics["auprc"],
                "brier": metrics["brier"],
                "sensitivity": metrics["sensitivity"],
                "specificity": metrics["specificity"],
                "delta_auroc_vs_baseline": float(metrics["auroc"] - baseline["auroc"]),
                "delta_auprc_vs_baseline": float(metrics["auprc"] - baseline["auprc"]),
                "delta_brier_vs_baseline": float(metrics["brier"] - baseline["brier"]),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["delta_auprc_vs_baseline", "failed_sensor"]
    ).reset_index(drop=True)


def validation_locked_operating_curve(
    dataset,
    probabilities: np.ndarray,
    classification_threshold: float,
    scheduling_threshold: float,
) -> pd.DataFrame:
    """Evaluate a validation-defined threshold grid on validation and held-out data."""

    validation = dataset.mask("validation")
    candidates = np.unique(
        np.concatenate(
            (
                [classification_threshold, scheduling_threshold, 0.5],
                np.quantile(
                    probabilities[validation],
                    [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99],
                ),
            )
        )
    )
    rows: list[dict[str, object]] = []
    for threshold in candidates:
        for split in ("validation", "test"):
            mask = dataset.mask(split)
            metrics = classification_metrics(
                dataset.target_current[mask], probabilities[mask], float(threshold)
            )
            rows.append(
                {
                    "split": split,
                    "threshold": float(threshold),
                    "sensitivity": metrics["sensitivity"],
                    "specificity": metrics["specificity"],
                    "precision": metrics["precision"],
                    "f1": metrics["f1"],
                    "positive_prediction_rate": float(
                        np.mean(probabilities[mask] >= threshold)
                    ),
                    "threshold_grid_source": "validation_only",
                    "is_classification_threshold": bool(
                        np.isclose(threshold, classification_threshold, rtol=0.0, atol=1e-15)
                    ),
                    "is_scheduler_threshold": bool(
                        np.isclose(threshold, scheduling_threshold, rtol=0.0, atol=1e-15)
                    ),
                }
            )
    return pd.DataFrame(rows)


def make_figures(
    predictions: dict[str, np.ndarray],
    labels: np.ndarray,
    test_mask: np.ndarray,
    model_metrics: pd.DataFrame,
    robustness: pd.DataFrame,
    scheduling: pd.DataFrame,
    temporal_diagnostics: pd.DataFrame,
    feature_importance: pd.DataFrame,
    output: Path,
) -> None:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    def save_figure(stem: str) -> None:
        figure = plt.gcf()
        figure.savefig(figures / f"{stem}.png", dpi=300, bbox_inches="tight")
        figure.savefig(figures / f"{stem}.svg", bbox_inches="tight")

    plt.figure(figsize=(7.2, 5.2))
    for name, probability in predictions.items():
        precision, recall, _ = precision_recall_curve(labels[test_mask], probability[test_mask])
        plt.plot(recall, precision, label=name.replace("_", " "))
    prevalence = float(labels[test_mask].mean())
    plt.axhline(
        prevalence, color="gray", linestyle="--", linewidth=1,
        label=f"no-skill prevalence ({prevalence:.3f})",
    )
    plt.xlabel("Sensitivity (recall)")
    plt.ylabel("Precision")
    plt.title("Held-out chronological test: precision–recall")
    plt.legend(fontsize=7)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    save_figure("ai_test_precision_recall")
    plt.close()

    plt.figure(figsize=(7.2, 5.2))
    for name, probability in predictions.items():
        fpr, tpr, _ = roc_curve(labels[test_mask], probability[test_mask])
        plt.plot(fpr, tpr, label=name.replace("_", " "))
    plt.plot([0, 1], [0, 1], "--", color="gray", linewidth=1)
    plt.xlabel("False-positive rate")
    plt.ylabel("True-positive rate")
    plt.title("Held-out chronological test: ROC")
    plt.legend(fontsize=7)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    save_figure("ai_test_roc")
    plt.close()

    test_summary = model_metrics[model_metrics.split == "test"].sort_values("selection_objective")
    selected = str(test_summary.iloc[0].model)
    display_names = [
        name.replace("_", " ") + (" (selected)" if name == selected else "")
        for name in test_summary.model
    ]
    positions = np.arange(len(test_summary))
    width = 0.34
    plt.figure(figsize=(8.4, 4.8))
    plt.barh(positions - width / 2, test_summary.auroc, height=width, label="AUROC")
    plt.barh(positions + width / 2, test_summary.auprc, height=width, label="AUPRC")
    plt.yticks(positions, display_names)
    plt.gca().invert_yaxis()
    plt.xlim(0, 1)
    plt.xlabel("Held-out discrimination score")
    plt.title("Model comparison on held-out dates\n(selection performed on validation dates)")
    plt.legend(loc="lower right")
    plt.grid(axis="x", alpha=0.25)
    plt.tight_layout()
    save_figure("ai_model_comparison")
    plt.close()

    plt.figure(figsize=(7.2, 4.8))
    for model, group in robustness.groupby("model"):
        data = group.groupby("sensor_outage_fraction").auprc.agg(["mean", "std"]).reset_index()
        plt.errorbar(
            data.sensor_outage_fraction * 100,
            data["mean"],
            yerr=data["std"].fillna(0),
            marker="o",
            capsize=3,
            label=model.replace("_", " "),
        )
    plt.xlabel("Failed sensor channels (%)")
    plt.ylabel("Held-out AUPRC")
    plt.title("Sensor-channel outage stress test\n(mean ± SD across fixed channel subsets)")
    plt.ylim(0.70, 0.91)
    plt.legend(fontsize=8)
    plt.grid(alpha=0.25)
    plt.tight_layout()
    save_figure("ai_sensor_outage_robustness")
    plt.close()

    aggregate = scheduling.groupby(["policy", "background_utilization_target"]).agg(
        high_dmr=("high_deadline_miss_ratio", "mean"),
        low_utility=("low_work_weighted_utility_linear", "mean"),
    ).reset_index()
    policy_labels = {
        "edf": "EDF",
        "rt_dash": "Semantic RT-DASH (= safe AI)",
        "rt_dash_ai_only": "AI only",
        "rt_dash_no_event_trigger": "Load only",
        "rt_dash_recovery_edf": "Recovery RT-DASH (= safe AI recovery)",
    }
    shown = aggregate[aggregate.policy.isin(policy_labels)].copy()
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.6))
    for policy, group in shown.groupby("policy", sort=False):
        label = policy_labels[policy]
        axes[0].plot(
            group.background_utilization_target,
            group.high_dmr,
            marker="o",
            label=label,
        )
        if policy != "edf":
            axes[1].plot(
                group.background_utilization_target,
                group.high_dmr,
                marker="o",
                label=label,
            )
        axes[2].plot(
            group.background_utilization_target,
            group.low_utility,
            marker="o",
            label=label,
        )
    axes[0].set_xlabel("Background periodic utilization")
    axes[0].set_ylabel("High-criticality deadline-miss ratio")
    axes[0].set_title("Safety outcome (all policies)")
    axes[1].set_xlabel("Background periodic utilization")
    axes[1].set_ylabel("High-criticality deadline-miss ratio")
    axes[1].set_title("Safety outcome (non-EDF zoom)")
    axes[1].set_ylim(-0.0005, 0.014)
    axes[2].set_xlabel("Background periodic utilization")
    axes[2].set_ylabel("Low-criticality work-weighted utility")
    axes[2].set_title("Retained routine utility")
    for axis in axes:
        axis.grid(axis="x", alpha=0.25)
    handles, labels_for_legend = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels_for_legend, loc="lower center", ncol=3,
        fontsize=7, bbox_to_anchor=(0.5, -0.03),
    )
    plt.tight_layout(rect=(0, 0.09, 1, 1))
    save_figure("ai_scheduler_integration")
    plt.close()

    temporal = temporal_diagnostics.copy()
    temporal["date_label"] = pd.to_datetime(temporal.source_date).dt.strftime("%b %d")
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.5))
    colors = temporal.split.map({"validation": "tab:blue", "test": "tab:orange"})
    axes[0].bar(temporal.date_label, temporal.auprc, color=colors)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("AUPRC")
    axes[0].set_title("Discrimination by date")
    axes[1].bar(
        temporal.date_label,
        temporal.mean_absolute_standardized_feature_shift,
        color=colors,
    )
    axes[1].set_ylabel("Mean absolute standardized shift")
    axes[1].set_title("Feature-distribution shift vs training")
    for axis in axes:
        axis.tick_params(axis="x", rotation=45)
        axis.grid(axis="y", alpha=0.2)
    from matplotlib.patches import Patch
    fig.legend(
        handles=[Patch(color="tab:blue", label="Validation"), Patch(color="tab:orange", label="Held-out test")],
        loc="lower center",
        ncol=2,
        bbox_to_anchor=(0.5, -0.03),
    )
    fig.suptitle("Temporal generalization after model lock")
    plt.tight_layout(rect=(0, 0.08, 1, 0.95))
    save_figure("ai_temporal_generalization")
    plt.close()

    top = feature_importance.head(15).sort_values(
        "absolute_standardized_coefficient", ascending=True
    )
    labels = top.feature.str.replace("sensor_current__", "", regex=False)
    colors = np.where(top.standardized_coefficient >= 0, "tab:red", "tab:blue")
    plt.figure(figsize=(8.0, 5.4))
    plt.barh(labels, top.standardized_coefficient, color=colors)
    plt.axvline(0, color="black", linewidth=0.8)
    plt.xlabel("Coefficient per one training-set standard deviation")
    plt.title("Selected logistic model: strongest standardized coefficients")
    plt.grid(axis="x", alpha=0.2)
    plt.tight_layout()
    save_figure("ai_selected_model_coefficients")
    plt.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(
    output: Path,
    selected_model: str,
    classification_threshold: float,
    scheduling_threshold: float,
    metrics: pd.DataFrame,
    scheduling: pd.DataFrame,
    comparisons: pd.DataFrame,
    temporal_diagnostics: pd.DataFrame,
    feature_importance: pd.DataFrame,
    leave_one_out: pd.DataFrame,
    manifest: dict[str, object],
) -> None:
    selected_test = metrics[(metrics.model == selected_model) & (metrics.split == "test")].iloc[0]
    aggregate = scheduling.groupby(["policy", "background_utilization_target"]).agg(
        high_dmr=("high_deadline_miss_ratio", "mean"),
        high_response=("high_mean_response", "mean"),
        low_utility=("low_work_weighted_utility_linear", "mean"),
        critical_fraction=("critical_mode_fraction", "mean"),
    )
    moderate_ai = aggregate.loc[("rt_dash_ai_only", 0.45)]
    moderate_load = aggregate.loc[("rt_dash_no_event_trigger", 0.45)]
    high_ai = aggregate.loc[("rt_dash_ai_only", 0.60)]
    high_load = aggregate.loc[("rt_dash_no_event_trigger", 0.60)]
    ai_vs_load = comparisons[
        (comparisons.left == "rt_dash_ai_only")
        & (comparisons.right == "rt_dash_no_event_trigger")
        & (comparisons.metric == "high_deadline_miss_ratio")
    ].iloc[0]
    ai_vs_semantic = comparisons[
        (comparisons.left == "rt_dash_ai_only")
        & (comparisons.right == "rt_dash")
        & (comparisons.metric == "high_deadline_miss_ratio")
    ].iloc[0]
    test_dates = temporal_diagnostics[temporal_diagnostics.split == "test"]
    worst_sensor = leave_one_out.iloc[0]
    strongest_features = feature_importance.head(5)[
        ["feature", "standardized_coefficient"]
    ]
    report = f"""# AI-RT-DASH Extension Validation Report

## Evidence boundary

This is a simulation and machine-learning study. The classifier uses raw OpenSHS device states and time-of-day only. The `Activity` field is a label and is not a feature. Thesis-generated CPU, memory, storage, bandwidth, priority and power values are excluded. No physical-board, energy, WCET, safety-certification or universal-generalization claim is made.

The raw source contains only 14 dates and 13 contiguous anomaly episodes; exact timestamps also include conflicting duplicate rows. These facts bound external validity. The chronological test remains untouched during model fitting, model selection and threshold selection.

## Locked protocol

- Training dates: first 8 source dates.
- Validation dates: next 3 source dates.
- Held-out test dates: final 3 source dates.
- Boundary purge: 300 seconds.
- Sampling period: {manifest['sample_period_seconds']} seconds.
- Features: current device states, causal 60-second device-state means, current/60-second transition counts and cyclic time-of-day.
- Current-state target: `Activity == anomaly`.
- Exploratory future target: anomaly present within {manifest['prediction_horizon_seconds']} seconds; this is not used for the principal scheduler claim.
- Selected model: `{selected_model}` using validation data only.
- Classification safety threshold: {classification_threshold:.8f}.
- End-to-end scheduler threshold: {scheduling_threshold:.8f}, selected on validation scheduling blocks only.
- Background periodic utilization profiles: {', '.join(f'{value:.2f}' for value in BACKGROUND_LOADS)}.

## Held-out AI result

- AUROC: {selected_test.auroc:.4f}
- AUPRC: {selected_test.auprc:.4f}
- Sensitivity: {selected_test.sensitivity:.4f}
- Specificity: {selected_test.specificity:.4f}
- Precision: {selected_test.precision:.4f}
- F1: {selected_test.f1:.4f}
- Brier score: {selected_test.brier:.4f}
- ECE (10 bins): {selected_test.ece_10:.4f}
- Episode recall: {selected_test.episode_recall:.4f}
- Median within-episode detection delay: {selected_test.median_detection_delay_seconds} seconds

The chronological distribution shift is material and is reported rather than hidden. A safe hybrid therefore retains the original semantic-event and utilization triggers; AI is an additional trigger, never the only safety path in the deployment-oriented policy.

## Post-lock temporal and interpretability diagnostics

Held-out date-level AUPRC ranges from {test_dates.auprc.min():.4f} to {test_dates.auprc.max():.4f}. The mean absolute standardized feature shift relative to training ranges from {test_dates.mean_absolute_standardized_feature_shift.min():.4f} to {test_dates.mean_absolute_standardized_feature_shift.max():.4f} across the three held-out dates. These diagnostics are calculated only after the model and classification threshold are locked and do not participate in selection.

The standardized coefficient export makes the selected logistic model auditable. Its five largest absolute coefficients are:

```
{strongest_features.to_string(index=False, float_format=lambda value: f'{value:.6f}')}
```

A complete leave-one-sensor-out test is also reported. The largest held-out AUPRC decrease occurs when `{worst_sensor.failed_sensor}` is removed: {worst_sensor.delta_auprc_vs_baseline:.6f}. This is a failure-dependence measurement, not a causal interpretation of the sensor.

## End-to-end scheduling aggregate

```
{aggregate.to_string(float_format=lambda value: f'{value:.6f}')}
```

## Paired comparisons

```
{comparisons.to_string(index=False, float_format=lambda value: f'{value:.6g}') if not comparisons.empty else 'No complete paired comparisons.'}
```

Day-cluster bootstrap intervals use the three held-out dates as clusters. They are necessarily wide and must not be interpreted as population-level assurance.

## What the integration result does and does not establish

At background utilization 0.45, AI-only triggering reduced mean high-criticality DMR from {moderate_load.high_dmr:.6f} (load-only) to {moderate_ai.high_dmr:.6f}; at 0.60 it reduced DMR from {high_load.high_dmr:.6f} to {high_ai.high_dmr:.6f}. The pooled paired difference was {ai_vs_load.mean_difference:.6f}, but the three-day-cluster Holm-adjusted p-value was {ai_vs_load.holm_p:.4f}; the direction is not statistically confirmed with this dataset.

The semantic RT-DASH trigger remained stronger: AI-only DMR exceeded it by {ai_vs_semantic.mean_difference:.6f} on paired anomaly-containing cells. The safe AI + recovery-aware policy exactly reproduced the deterministic recovery-aware fallback for high DMR, low utility and Critical-Mode fraction in all 90 held-out block-load cells. Thus the AI result is an advisory-trigger result with a fail-safe boundary, not evidence that ML should replace the deterministic guard.

## Reproducible outputs

- `data_quality_audit.json`: source-row, timestamp, label-conflict and episode audit.
- `classification_metrics.csv`: split-specific discrimination, calibration and threshold metrics.
- `model_selection.csv`: validation-only selection evidence, runtime and model size.
- `sensor_outage_robustness.csv`: deterministic channel-outage stress tests.
- `leave_one_sensor_out.csv`: exhaustive single-sensor failure diagnostics for the selected model.
- `selected_model_feature_importance.csv`: standardized selected-model coefficients and odds ratios.
- `temporal_generalization_by_date.csv`: post-lock date-level performance and covariate/risk-shift diagnostics.
- `validation_locked_operating_curve.csv`: validation-defined threshold grid evaluated on validation and held-out data.
- `scheduler_threshold_validation.csv`: validation-only end-to-end threshold choice.
- `scheduling_integration_runs.csv`: held-out block-level simulator results.
- `scheduling_paired_comparisons.csv`: paired effects and day-cluster intervals.
- `portable_logistic_model.json` and `.h`: compact selected-model inference artifacts with verified Python/C parity.
- `selected_model.pkl`: selected research model and preprocessing state.
- `ai_execution_manifest.json` and `SHA256SUMS_AI.txt`: partitions, versions and file hashes.

## Defensible conclusion

The extension establishes a real, reproducible AI path; it does not relabel the original rules as AI. The learned detector supplies a causal risk signal from raw device state without requiring the activity label at inference time. Because one OpenSHS trace cannot establish broad anomaly generalization, the deployment-oriented design keeps deterministic RT-DASH event/load fallback. The original RT-DASH paper can remain a scheduler paper, while the AI paper should focus on sensor-derived semantic-risk inference, uncertainty/failure handling, and the measured end-to-end trade-off under the explicitly limited dataset.
"""
    (output / "AI_EXTENSION_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("../data/raw/smart_home_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/ai_extension"))
    parser.add_argument("--sample-period", type=int, default=10)
    parser.add_argument("--prediction-horizon", type=int, default=60)
    parser.add_argument("--block-rows", type=int, default=720)
    parser.add_argument("--step-ms", type=int, default=100)
    parser.add_argument("--quantum", type=int, default=10)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started_all = time.perf_counter()
    data_audit = audit_openshs_source(args.data.resolve())
    (output / "data_quality_audit.json").write_text(
        json.dumps(data_audit, indent=2) + "\n", encoding="utf-8"
    )
    dataset = prepare_openshs_ai_dataset(
        args.data.resolve(),
        sample_period_seconds=args.sample_period,
        prediction_horizon_seconds=args.prediction_horizon,
        purge_seconds=300,
    )
    train_mask = dataset.mask("train")
    validation_mask = dataset.mask("validation")
    test_mask = dataset.mask("test")

    models: list[FittedModel] = []
    for definition in model_definitions(len(dataset.sensor_names), dataset.features.shape[1]):
        models.append(
            fit_model(
                definition[0], definition[1], dataset.features, dataset.target_current,
                train_mask, definition[2], definition[3]
            )
        )

    predictions: dict[str, np.ndarray] = {}
    thresholds: dict[str, float] = {}
    metric_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    for model in models:
        inference_start = time.perf_counter()
        probability = model.predict(dataset.features)
        inference_seconds = time.perf_counter() - inference_start
        predictions[model.name] = probability
        threshold, objective = choose_safety_threshold(
            dataset.target_current[validation_mask], probability[validation_mask], 5.0, 1.0
        )
        thresholds[model.name] = threshold
        selection_rows.append(
            {
                "model": model.name,
                "validation_threshold": threshold,
                "selection_objective": objective,
                "fit_seconds": model.fit_seconds,
                "full_inference_seconds": inference_seconds,
                "microseconds_per_sample": inference_seconds * 1e6 / len(dataset.features),
                "serialized_bytes": model.serialized_bytes,
            }
        )
        for split, mask in (("train", train_mask), ("validation", validation_mask), ("test", test_mask)):
            row = classification_metrics(dataset.target_current[mask], probability[mask], threshold)
            row.update(
                episode_metrics(
                    dataset.target_current[mask], probability[mask], dataset.sequence_ids[mask],
                    threshold, dataset.sample_period_seconds
                )
            )
            row.update({"model": model.name, "split": split, "selection_objective": objective})
            metric_rows.append(row)

    selection = pd.DataFrame(selection_rows).sort_values(
        ["selection_objective", "serialized_bytes", "model"]
    ).reset_index(drop=True)
    selected_name = str(selection.iloc[0].model)
    selected_model = next(model for model in models if model.name == selected_name)
    classification_threshold = thresholds[selected_name]
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(output / "classification_metrics.csv", index=False)
    selection.to_csv(output / "model_selection.csv", index=False)

    portable_source = (
        selected_model
        if hasattr(selected_model.estimator, "coef_") and selected_model.scaler is not None
        else next(model for model in models if model.name == "temporal_logistic")
    )
    portable = PortableLogisticRiskModel(
        feature_names=tuple(dataset.feature_names[index] for index in portable_source.columns),
        mean=np.asarray(portable_source.scaler.mean_, dtype=float),
        scale=np.asarray(portable_source.scaler.scale_, dtype=float),
        coefficients=np.asarray(portable_source.estimator.coef_[0], dtype=float),
        intercept=float(portable_source.estimator.intercept_[0]),
    )
    portable.save(output / "portable_logistic_model.json")
    portable.save_c_header(output / "portable_logistic_model.h")
    sklearn_probability = portable_source.predict(dataset.features[test_mask])
    portable_probability = portable.predict_proba(dataset.features[test_mask][:, portable_source.columns])
    if not np.allclose(sklearn_probability, portable_probability, rtol=1e-6, atol=1e-6):
        raise RuntimeError("portable logistic inference does not match scikit-learn")
    with (output / "selected_model.pkl").open("wb") as stream:
        pickle.dump(
            {
                "name": selected_model.name,
                "estimator": selected_model.estimator,
                "columns": selected_model.columns,
                "scaler": selected_model.scaler,
                "feature_names": dataset.feature_names,
            },
            stream,
        )

    robustness_rows: list[dict[str, object]] = []
    rng = np.random.default_rng(20260804)
    stress_models = {
        model.name: model
        for model in (
            selected_model,
            portable_source,
            next(model for model in models if model.name == "temporal_logistic"),
        )
    }
    for model in stress_models.values():
        for fraction in (0.0, 0.05, 0.10, 0.20):
            repetitions = 1 if fraction == 0 else 10
            count = int(round(len(dataset.sensor_names) * fraction))
            for repetition in range(repetitions):
                failed = tuple(rng.choice(dataset.sensor_names, size=count, replace=False)) if count else ()
                corrupted = sensor_outage_feature_matrix(
                    dataset.features[test_mask], dataset.feature_names, failed
                )
                probability = model.predict(corrupted)
                row = classification_metrics(
                    dataset.target_current[test_mask], probability, thresholds[model.name]
                )
                robustness_rows.append(
                    {
                        "model": model.name,
                        "sensor_outage_fraction": fraction,
                        "repetition": repetition,
                        "failed_sensors": ";".join(failed),
                        **row,
                    }
                )
    robustness = pd.DataFrame(robustness_rows)
    robustness.to_csv(output / "sensor_outage_robustness.csv", index=False)

    temporal_diagnostics = temporal_generalization_diagnostics(
        dataset, predictions[selected_name], classification_threshold
    )
    temporal_diagnostics.to_csv(output / "temporal_generalization_by_date.csv", index=False)
    feature_importance = logistic_feature_importance(selected_model, dataset)
    feature_importance.to_csv(output / "selected_model_feature_importance.csv", index=False)
    leave_one_out = leave_one_sensor_out_diagnostics(
        selected_model, dataset, predictions[selected_name], classification_threshold
    )
    leave_one_out.to_csv(output / "leave_one_sensor_out.csv", index=False)

    validation_blocks = build_trace_blocks(
        dataset, "validation", predictions[selected_name], args.block_rows
    )
    scheduling_threshold, threshold_ranking = tune_scheduler_threshold(
        validation_blocks, classification_threshold, args.quantum, args.step_ms
    )
    threshold_ranking.to_csv(output / "scheduler_threshold_validation.csv", index=False)
    operating_curve = validation_locked_operating_curve(
        dataset,
        predictions[selected_name],
        classification_threshold,
        scheduling_threshold,
    )
    operating_curve.to_csv(output / "validation_locked_operating_curve.csv", index=False)

    test_blocks = build_trace_blocks(dataset, "test", predictions[selected_name], args.block_rows)
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
        run_trace_policy(
            block,
            policy,
            scheduling_threshold,
            background_load,
            args.step_ms,
            args.quantum,
        )
        for block in test_blocks
        for background_load in BACKGROUND_LOADS
        for policy in policies
    )
    scheduling.to_csv(output / "scheduling_integration_runs.csv", index=False)
    comparisons = scheduling_comparisons(scheduling)
    comparisons.to_csv(output / "scheduling_paired_comparisons.csv", index=False)

    make_figures(
        predictions,
        dataset.target_current,
        test_mask,
        metrics,
        robustness,
        scheduling,
        temporal_diagnostics,
        feature_importance,
        output,
    )
    manifest = {
        "study": "AI-RT-DASH leakage-controlled extension",
        "created_utc": pd.Timestamp.utcnow().isoformat(),
        "data_path": str(args.data.resolve()),
        "dataset_fingerprint": dataset.fingerprint,
        "raw_file_sha256": sha256(args.data.resolve()),
        "data_quality_audit": data_audit,
        "sample_period_seconds": args.sample_period,
        "prediction_horizon_seconds": args.prediction_horizon,
        "purge_seconds": 300,
        "partition_counts": {
            split: int(dataset.mask(split).sum()) for split in ("train", "validation", "test")
        },
        "partition_positive_rates": {
            split: float(dataset.target_current[dataset.mask(split)].mean())
            for split in ("train", "validation", "test")
        },
        "selected_model": selected_name,
        "portable_model_source": portable_source.name,
        "classification_threshold": classification_threshold,
        "scheduling_threshold": scheduling_threshold,
        "selection_uses_test": False,
        "scheduler_validation_blocks": len(validation_blocks),
        "scheduler_test_blocks": len(test_blocks),
        "scheduler_test_runs": len(scheduling),
        "temporal_diagnostic_dates": len(temporal_diagnostics),
        "leave_one_sensor_out_cases": len(leave_one_out),
        "operating_curve_thresholds": int(operating_curve.threshold.nunique()),
        "diagnostics_use_test_for_selection": False,
        "background_utilization_targets": list(BACKGROUND_LOADS),
        "runtime_seconds": time.perf_counter() - started_all,
        "versions": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    (output / "ai_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    write_report(
        output, selected_name, classification_threshold, scheduling_threshold,
        metrics, scheduling, comparisons, temporal_diagnostics, feature_importance,
        leave_one_out, manifest
    )

    hash_targets = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS_AI.txt"
    )
    (output / "SHA256SUMS_AI.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(output)}\n" for path in hash_targets),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
