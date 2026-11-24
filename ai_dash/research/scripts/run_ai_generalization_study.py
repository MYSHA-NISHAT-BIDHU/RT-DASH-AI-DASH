from __future__ import annotations

import argparse
import hashlib
import json
import math
import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from rt_dash.ai import (
    choose_safety_threshold,
    classification_metrics,
    prepare_openshs_ai_dataset,
    sensor_outage_feature_matrix,
)


def chronological_masks(dataset, test_index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dates = dataset.timestamps.astype("datetime64[D]")
    unique_dates = np.array(sorted(np.unique(dates)))
    if test_index < 4 or test_index >= len(unique_dates):
        raise ValueError("rolling-origin test index must leave at least two train and two validation dates")
    test_date = unique_dates[test_index]
    validation_dates = unique_dates[test_index - 2:test_index]
    train_dates = unique_dates[:test_index - 2]
    train = np.isin(dates, train_dates)
    validation = np.isin(dates, validation_dates)
    test = dates == test_date

    # Remove the first five minutes of each validation/test date. Causal feature
    # windows already reset at source discontinuities; this additional purge
    # mirrors the principal study's conservative boundary handling.
    seconds = dataset.timestamps.astype("datetime64[s]").astype(np.int64)
    for boundary_date in tuple(validation_dates) + (test_date,):
        boundary_positions = np.flatnonzero(dates == boundary_date)
        if len(boundary_positions) == 0:
            continue
        boundary = int(seconds[boundary_positions[0]])
        purge = (seconds >= boundary) & (seconds < boundary + 300)
        train &= ~purge
        validation &= ~purge
        test &= ~purge
    return train, validation, test


def model_specs(sensor_count: int, feature_count: int):
    current = np.arange(sensor_count)
    all_features = np.arange(feature_count)
    return (
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
                random_state=20260806,
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
                n_jobs=4,
                random_state=20260806,
            ),
            all_features,
            False,
        ),
    )


def fit_predict(
    features: np.ndarray,
    labels: np.ndarray,
    train: np.ndarray,
    validation: np.ndarray,
    test: np.ndarray,
    columns: np.ndarray,
    standardized: bool,
    factory,
) -> tuple[np.ndarray, np.ndarray, float]:
    scaler = StandardScaler().fit(features[train][:, columns]) if standardized else None
    training = features[train][:, columns]
    validation_matrix = features[validation][:, columns]
    test_matrix = features[test][:, columns]
    if scaler is not None:
        training = scaler.transform(training)
        validation_matrix = scaler.transform(validation_matrix)
        test_matrix = scaler.transform(test_matrix)
    estimator = factory()
    estimator.fit(training, labels[train])
    validation_probability = estimator.predict_proba(validation_matrix)[:, 1]
    test_probability = estimator.predict_proba(test_matrix)[:, 1]
    threshold, _ = choose_safety_threshold(
        labels[validation], validation_probability, false_negative_cost=5.0, false_positive_cost=1.0
    )
    return validation_probability, test_probability, threshold


def rolling_origin_study(dataset) -> pd.DataFrame:
    dates = dataset.timestamps.astype("datetime64[D]")
    unique_dates = np.array(sorted(np.unique(dates)))
    rows: list[dict[str, object]] = []
    # The first candidate fold (test index 4) would train on 1--2 March,
    # which contain no anomaly samples. Start at the first fold whose historical
    # training window contains both classes; no synthetic positives are added.
    for test_index in range(5, len(unique_dates)):
        train, validation, test = chronological_masks(dataset, test_index)
        for model, factory, columns, standardized in model_specs(
            len(dataset.sensor_names), dataset.features.shape[1]
        ):
            validation_probability, test_probability, threshold = fit_predict(
                dataset.features,
                dataset.target_current,
                train,
                validation,
                test,
                columns,
                standardized,
                factory,
            )
            validation_metrics = classification_metrics(
                dataset.target_current[validation], validation_probability, threshold
            )
            test_metrics = classification_metrics(
                dataset.target_current[test], test_probability, threshold
            )
            rows.append(
                {
                    "model": model,
                    "test_date": str(unique_dates[test_index]),
                    "train_dates": int(len(np.unique(dates[train]))),
                    "validation_dates": int(len(np.unique(dates[validation]))),
                    "train_n": int(train.sum()),
                    "validation_n": int(validation.sum()),
                    "test_n": int(test.sum()),
                    "threshold": threshold,
                    "validation_auroc": validation_metrics["auroc"],
                    "validation_auprc": validation_metrics["auprc"],
                    "test_auroc": test_metrics["auroc"],
                    "test_auprc": test_metrics["auprc"],
                    "test_sensitivity": test_metrics["sensitivity"],
                    "test_specificity": test_metrics["specificity"],
                    "test_precision": test_metrics["precision"],
                    "test_f1": test_metrics["f1"],
                    "test_brier": test_metrics["brier"],
                    "test_ece_10": test_metrics["ece_10"],
                    "diagnostic_only_after_principal_test_lock": True,
                }
            )
    return pd.DataFrame(rows)


def rolling_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model, group in frame.groupby("model", sort=True):
        rows.append(
            {
                "model": model,
                "folds": len(group),
                "mean_auroc": group.test_auroc.mean(),
                "median_auroc": group.test_auroc.median(),
                "min_auroc": group.test_auroc.min(),
                "mean_auprc": group.test_auprc.mean(),
                "median_auprc": group.test_auprc.median(),
                "min_auprc": group.test_auprc.min(),
                "mean_brier": group.test_brier.mean(),
                "mean_ece_10": group.test_ece_10.mean(),
                "folds_auroc_below_0_5": int((group.test_auroc < 0.5).sum()),
            }
        )
    return pd.DataFrame(rows)


def load_locked_logistic(dataset, model_path: Path, selection_path: Path):
    test = dataset.mask("test")
    with model_path.open("rb") as handle:
        payload = pickle.load(handle)
    if payload.get("name") != "current_sensor_logistic":
        raise RuntimeError("locked principal artifact is not current_sensor_logistic")
    if tuple(payload.get("feature_names", ())) != tuple(dataset.feature_names):
        raise RuntimeError("locked model feature schema does not match prepared dataset")
    estimator = payload["estimator"]
    scaler = payload["scaler"]
    columns = np.asarray(payload["columns"], dtype=int)
    selection = pd.read_csv(selection_path)
    row = selection.loc[selection.model == "current_sensor_logistic"]
    if len(row) != 1:
        raise RuntimeError("expected exactly one locked current_sensor_logistic selection row")
    threshold = float(row.iloc[0].validation_threshold)
    return estimator, scaler, columns, threshold, test


def sensor_groups(sensor_names: tuple[str, ...]) -> dict[str, list[str]]:
    groups = {
        "bathroom": [name for name in sensor_names if name.startswith("bathroom")],
        "bedroom": [name for name in sensor_names if name.startswith("bedroom") or name in {"bed", "bedTableLamp"}],
        "kitchen": [name for name in sensor_names if name.startswith("kitchen") or name in {"fridge", "oven"}],
        "office": [name for name in sensor_names if name.startswith("office")],
        "living": [name for name in sensor_names if name.startswith("living") or name in {"couch", "tv"}],
        "entry": [name for name in sensor_names if name.startswith("mainDoor")],
    }
    assigned = {sensor for sensors in groups.values() for sensor in sensors}
    groups["other"] = [sensor for sensor in sensor_names if sensor not in assigned]
    return {name: sensors for name, sensors in groups.items() if sensors}


def grouped_outage_study(dataset, model_path: Path, selection_path: Path) -> pd.DataFrame:
    estimator, scaler, columns, threshold, test = load_locked_logistic(
        dataset, model_path, selection_path
    )
    # Preserve the principal study's full-batch inference path.  For nearly
    # tied probabilities, changing BLAS batch shape can alter rank metrics at
    # the fifth decimal even though calibrated probabilities are unchanged.
    baseline_matrix = dataset.features

    def probabilities(matrix: np.ndarray) -> np.ndarray:
        return estimator.predict_proba(scaler.transform(matrix[:, columns]))[:, 1]

    baseline_probability = probabilities(baseline_matrix)[test]
    baseline = classification_metrics(dataset.target_current[test], baseline_probability, threshold)
    rows = [
        {
            "group": "none",
            "failed_sensors": "",
            "sensor_count": 0,
            **{key: baseline[key] for key in ("auroc", "auprc", "sensitivity", "specificity", "brier", "ece_10")},
            "delta_auroc": 0.0,
            "delta_auprc": 0.0,
            "delta_brier": 0.0,
        }
    ]
    for group, sensors in sensor_groups(dataset.sensor_names).items():
        failed = sensor_outage_feature_matrix(
            baseline_matrix, dataset.feature_names, sensors
        )
        metric = classification_metrics(
            dataset.target_current[test], probabilities(failed)[test], threshold
        )
        rows.append(
            {
                "group": group,
                "failed_sensors": ";".join(sensors),
                "sensor_count": len(sensors),
                **{key: metric[key] for key in ("auroc", "auprc", "sensitivity", "specificity", "brier", "ece_10")},
                "delta_auroc": metric["auroc"] - baseline["auroc"],
                "delta_auprc": metric["auprc"] - baseline["auprc"],
                "delta_brier": metric["brier"] - baseline["brier"],
            }
        )
    return pd.DataFrame(rows)


def duplicate_timestamp_sensitivity(
    dataset, model_path: Path, selection_path: Path
) -> pd.DataFrame:
    estimator, scaler, columns, threshold, test = load_locked_logistic(
        dataset, model_path, selection_path
    )
    probability = estimator.predict_proba(
        scaler.transform(dataset.features[:, columns])
    )[:, 1][test]
    test_timestamps = dataset.timestamps[test]
    duplicated = pd.Series(test_timestamps).duplicated(keep=False).to_numpy()
    rows = []
    for label, keep in (
        ("all_test_samples", np.ones(len(probability), dtype=bool)),
        ("exclude_duplicate_timestamps", ~duplicated),
    ):
        metric = classification_metrics(
            dataset.target_current[test][keep], probability[keep], threshold
        )
        rows.append(
            {
                "subset": label,
                "n": int(keep.sum()),
                "excluded": int((~keep).sum()),
                **{key: metric[key] for key in (
                    "auroc", "auprc", "sensitivity", "specificity", "precision",
                    "f1", "brier", "ece_10"
                )},
                "diagnostic_only_after_principal_test_lock": True,
            }
        )
    return pd.DataFrame(rows)


def make_figures(output: Path, rolling: pd.DataFrame, outage: pd.DataFrame) -> None:
    figure_dir = output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    for model, group in rolling.groupby("model", sort=True):
        ax.plot(group.test_date, group.test_auroc, marker="o", label=model)
    ax.axhline(0.5, color="black", linewidth=1, linestyle="--", alpha=0.6)
    ax.set_ylabel("Rolling-origin AUROC")
    ax.set_xlabel("Held-out date")
    ax.set_title("Prospective-style temporal generalization diagnostic")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(figure_dir / "rolling_origin_auroc.png", dpi=240)
    fig.savefig(figure_dir / "rolling_origin_auroc.svg")
    plt.close(fig)

    failed = outage[outage.group != "none"].sort_values("delta_auprc")
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.barh(failed.group, failed.delta_auprc, color="tab:red")
    ax.axvline(0.0, color="black", linewidth=1)
    ax.set_xlabel("Held-out AUPRC change vs no outage")
    ax.set_title("Correlated room-level sensor outage")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(figure_dir / "grouped_sensor_outage.png", dpi=240)
    fig.savefig(figure_dir / "grouped_sensor_outage.svg")
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(
    output: Path,
    summary: pd.DataFrame,
    outage: pd.DataFrame,
    duplicate: pd.DataFrame,
) -> None:
    worst_outage = outage[outage.group != "none"].sort_values("delta_auprc").iloc[0]
    text = f"""# AI Temporal Generalization and Correlated-Failure Report

## Evidence boundary

This is an additive post-lock diagnostic. The principal 8/3/3-day model,
classification threshold, scheduling threshold, and 630-run scheduler result
remain unchanged. No model in this study is allowed to replace the principal
model on the already-inspected held-out dates.

## Rolling-origin evaluation

Nine prospective-style folds are evaluated. In each fold, all model fitting uses
only earlier dates, the two immediately preceding dates choose that model's
safety threshold, and the next chronological date is evaluated once. Model
families are fixed in advance; this diagnostic does not select a new principal
model.

```
{summary.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

The fold-wise record is retained in `rolling_origin_metrics.csv`, including
poor-performing days. This directly quantifies temporal instability instead of
hiding it in a pooled score.

## Correlated sensor-group failure

The exact serialized locked current-sensor logistic model and its original
validation-selected threshold are loaded without refitting or reselection. All
feature channels for one room/group are then zeroed together on the original
held-out dates.

```
{outage.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

Largest grouped AUPRC loss: `{worst_outage.group}`
({worst_outage.delta_auprc:.6f}). This is an observed failure dependence, not
a causal claim about the room or sensors.

## Duplicate-timestamp sensitivity

```
{duplicate.to_string(index=False, float_format=lambda x: f'{x:.6f}')}
```

This check does not rewrite source labels or choose a preferred dataset version;
it reports how the locked model behaves when duplicate timestamps are excluded
from scoring.
"""
    (output / "AI_GENERALIZATION_VALIDATION_REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("../data/raw/smart_home_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/ai_generalization"))
    parser.add_argument(
        "--principal-model",
        type=Path,
        default=Path("results/ai_extension/selected_model.pkl"),
    )
    parser.add_argument(
        "--principal-selection",
        type=Path,
        default=Path("results/ai_extension/model_selection.csv"),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    dataset = prepare_openshs_ai_dataset(
        args.data.resolve(), sample_period_seconds=10, prediction_horizon_seconds=60, purge_seconds=300
    )
    rolling = rolling_origin_study(dataset)
    summary = rolling_summary(rolling)
    outage = grouped_outage_study(
        dataset, args.principal_model.resolve(), args.principal_selection.resolve()
    )
    duplicate = duplicate_timestamp_sensitivity(
        dataset, args.principal_model.resolve(), args.principal_selection.resolve()
    )

    rolling.to_csv(output / "rolling_origin_metrics.csv", index=False)
    summary.to_csv(output / "rolling_origin_summary.csv", index=False)
    outage.to_csv(output / "grouped_sensor_outage.csv", index=False)
    duplicate.to_csv(output / "duplicate_timestamp_sensitivity.csv", index=False)
    make_figures(output, rolling, outage)
    write_report(output, summary, outage, duplicate)

    manifest = {
        "study": "post-lock AI temporal generalization and correlated failure",
        "rolling_origin_folds": int(rolling.test_date.nunique()),
        "rolling_origin_models": sorted(rolling.model.unique().tolist()),
        "rolling_origin_rows": int(len(rolling)),
        "sensor_failure_groups": int((outage.group != "none").sum()),
        "principal_model_reselected": False,
        "principal_threshold_changed": False,
        "principal_scheduler_result_changed": False,
        "principal_model_artifact": str(args.principal_model),
        "principal_selection_artifact": str(args.principal_selection),
        "hardware_used": False,
    }
    (output / "ai_generalization_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    artifacts = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS_AI_GENERALIZATION.txt"
    )
    lines = [f"{sha256(path)}  {path.relative_to(output)}" for path in artifacts]
    (output / "SHA256SUMS_AI_GENERALIZATION.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("AI GENERALIZATION STUDY: DONE")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
