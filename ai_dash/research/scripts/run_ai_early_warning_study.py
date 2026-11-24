#!/usr/bin/env python3
"""Execute the predeclared exploratory 60-second AI early-warning study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd
import scipy
import sklearn

from rt_dash.ai import (
    choose_safety_threshold,
    classification_metrics,
    prepare_openshs_ai_dataset,
)
from run_ai_extension_study import fit_model, model_definitions


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pre_onset_warning_rows(dataset, probabilities: np.ndarray, threshold: float) -> pd.DataFrame:
    """Report whether an alert occurs during the fixed horizon before each onset."""

    test = dataset.mask("test")
    horizon_steps = int(np.ceil(dataset.prediction_horizon_seconds / dataset.sample_period_seconds))
    rows: list[dict[str, object]] = []
    episode = 0
    for sequence in np.unique(dataset.sequence_ids[test]):
        positions = np.flatnonzero(test & (dataset.sequence_ids == sequence))
        truth = dataset.target_current[positions].astype(bool)
        starts = np.flatnonzero(truth & ~np.r_[False, truth[:-1]])
        for start in starts:
            episode += 1
            window_start = max(0, start - horizon_steps)
            pre_positions = positions[window_start:start]
            pre_positions = pre_positions[dataset.target_current[pre_positions] == 0]
            warnings = pre_positions[probabilities[pre_positions] >= threshold]
            warned = bool(len(warnings))
            lead = None
            if warned:
                lead = float(
                    (positions[start] - warnings[0]) * dataset.sample_period_seconds
                )
            rows.append(
                {
                    "episode": episode,
                    "sequence_id": int(sequence),
                    "onset_timestamp": str(dataset.timestamps[positions[start]]),
                    "eligible_pre_onset_samples": len(pre_positions),
                    "warned_before_onset": warned,
                    "maximum_observed_lead_seconds": lead,
                    "horizon_seconds": dataset.prediction_horizon_seconds,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("../data/raw/smart_home_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/ai_early_warning"))
    parser.add_argument("--sample-period", type=int, default=10)
    parser.add_argument("--prediction-horizon", type=int, default=60)
    args = parser.parse_args()
    if args.prediction_horizon != 60:
        raise ValueError("principal exploratory protocol fixes the future window at 60 seconds")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dataset = prepare_openshs_ai_dataset(
        args.data.resolve(),
        sample_period_seconds=args.sample_period,
        prediction_horizon_seconds=args.prediction_horizon,
        purge_seconds=300,
    )
    train = dataset.mask("train")
    validation = dataset.mask("validation")
    test = dataset.mask("test")

    selection_rows: list[dict[str, object]] = []
    metric_rows: list[dict[str, object]] = []
    predictions: dict[str, np.ndarray] = {}
    models = []
    for name, factory, columns, standardized in model_definitions(
        len(dataset.sensor_names), dataset.features.shape[1]
    ):
        model = fit_model(
            name,
            factory,
            dataset.features,
            dataset.target_future,
            train,
            columns,
            standardized,
        )
        models.append(model)
        probability = model.predict(dataset.features)
        predictions[name] = probability
        threshold, objective = choose_safety_threshold(
            dataset.target_future[validation], probability[validation], 5.0, 1.0
        )
        selection_rows.append(
            {
                "model": name,
                "validation_threshold": threshold,
                "selection_objective": objective,
                "serialized_bytes": model.serialized_bytes,
            }
        )
        for split, mask in (("train", train), ("validation", validation), ("test", test)):
            row = classification_metrics(dataset.target_future[mask], probability[mask], threshold)
            row.update({"model": name, "split": split, "selection_objective": objective})
            metric_rows.append(row)

    selection = pd.DataFrame(selection_rows).sort_values(
        ["selection_objective", "serialized_bytes", "model"]
    ).reset_index(drop=True)
    selected_name = str(selection.iloc[0].model)
    threshold = float(selection.iloc[0].validation_threshold)
    selection.to_csv(output / "future_model_selection.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(output / "future_classification_metrics.csv", index=False)

    warnings = pre_onset_warning_rows(dataset, predictions[selected_name], threshold)
    warnings.to_csv(output / "future_pre_onset_warnings.csv", index=False)
    eligible = warnings[warnings.eligible_pre_onset_samples > 0]
    warned = eligible[eligible.warned_before_onset.astype(bool)]
    manifest = {
        "study": "RT-DASH predeclared exploratory 60-second early-warning analysis",
        "claim_status": "exploratory only; does not replace the locked current-state principal model",
        "created_utc": pd.Timestamp.utcnow().isoformat(),
        "dataset_fingerprint": dataset.fingerprint,
        "raw_file_sha256": sha256(args.data.resolve()),
        "sample_period_seconds": dataset.sample_period_seconds,
        "prediction_horizon_seconds": dataset.prediction_horizon_seconds,
        "purge_seconds": 300,
        "partition_counts": {
            split: int(dataset.mask(split).sum()) for split in ("train", "validation", "test")
        },
        "future_positive_rates": {
            split: float(dataset.target_future[dataset.mask(split)].mean())
            for split in ("train", "validation", "test")
        },
        "selected_model": selected_name,
        "validation_threshold": threshold,
        "selection_uses_test": False,
        "test_onset_episodes": len(warnings),
        "test_onsets_with_pre_window": len(eligible),
        "test_onsets_warned_before_onset": len(warned),
        "pre_onset_warning_recall": float(len(warned) / len(eligible)) if len(eligible) else None,
        "median_maximum_lead_seconds": float(warned.maximum_observed_lead_seconds.median())
        if len(warned)
        else None,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    (output / "future_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    targets = sorted(
        path for path in output.iterdir()
        if path.is_file() and path.name != "SHA256SUMS_FUTURE.txt"
    )
    (output / "SHA256SUMS_FUTURE.txt").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in targets), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
