"""Leakage-controlled AI utilities for the RT-DASH extension study.

The original thesis-era ``PredictiveModel`` is deliberately not imported here:
it computes descriptive means and does not implement a learned temporal model.
This module instead builds causal features from raw OpenSHS device states,
enforces day-disjoint partitions, supplies deterministic metrics, and exposes a
small logistic model representation whose inference does not require
scikit-learn.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .simulator import PredictiveModeSignal


NON_SENSOR_COLUMNS = {
    "timestamp",
    "Activity",
    "Priority",
    "CPU",
    "Memory",
    "Storage",
    "Bandwidth",
}


def audit_openshs_source(csv_path: str | Path) -> dict[str, object]:
    """Return deterministic source-quality facts that constrain AI claims."""

    frame = pd.read_csv(csv_path)
    if "timestamp" not in frame or "Activity" not in frame:
        raise ValueError("OpenSHS input must contain timestamp and Activity")
    timestamps = pd.to_datetime(
        frame["timestamp"].astype(str).str.replace("_", ":", regex=False),
        errors="coerce",
    )
    activity = frame["Activity"].astype(str).str.strip().str.lower()
    valid = timestamps.notna()
    differences = timestamps.diff().dt.total_seconds()
    anomaly = activity.eq("anomaly").to_numpy()
    starts = anomaly & ~np.r_[False, anomaly[:-1]]
    timestamp_label_counts = frame.groupby("timestamp", dropna=False)["Activity"].nunique()
    sensors = [column for column in frame if column not in NON_SENSOR_COLUMNS]
    return {
        "raw_rows": len(frame),
        "sensor_columns": sensors,
        "sensor_column_count": len(sensors),
        "invalid_timestamps": int((~valid).sum()),
        "distinct_valid_timestamps": int(timestamps[valid].nunique()),
        "duplicate_timestamp_rows_beyond_first": int(timestamps.duplicated().sum()),
        "timestamp_groups_with_conflicting_activity_labels": int(
            (timestamp_label_counts > 1).sum()
        ),
        "backward_timestamp_jumps": int((differences < 0).sum()),
        "forward_timestamp_gaps_over_one_second": int((differences > 1).sum()),
        "distinct_dates": int(timestamps[valid].dt.date.nunique()),
        "anomaly_rows": int(anomaly.sum()),
        "contiguous_anomaly_episodes_in_source_order": int(starts.sum()),
        "activity_counts": {
            str(label): int(count)
            for label, count in activity.value_counts(dropna=False).items()
        },
        "sensor_missing_values": int(frame[sensors].isna().sum().sum()),
    }


@dataclass(frozen=True, slots=True)
class PreparedAIDataset:
    features: np.ndarray
    feature_names: tuple[str, ...]
    timestamps: np.ndarray
    sequence_ids: np.ndarray
    source_rows: np.ndarray
    activities: np.ndarray
    target_current: np.ndarray
    target_future: np.ndarray
    splits: np.ndarray
    sensor_names: tuple[str, ...]
    sample_period_seconds: int
    prediction_horizon_seconds: int

    def mask(self, split: str) -> np.ndarray:
        if split not in {"train", "validation", "test"}:
            raise ValueError(f"unknown split: {split}")
        return self.splits == split

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        digest.update("\n".join(self.feature_names).encode("utf-8"))
        digest.update(self.timestamps.astype("datetime64[s]").astype("int64").tobytes())
        digest.update(self.source_rows.astype("int64").tobytes())
        digest.update(self.target_current.astype("uint8").tobytes())
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class PortableLogisticRiskModel:
    """A deterministic standardized logistic model for host/firmware parity."""

    feature_names: tuple[str, ...]
    mean: np.ndarray
    scale: np.ndarray
    coefficients: np.ndarray
    intercept: float

    def __post_init__(self) -> None:
        length = len(self.feature_names)
        if any(len(value) != length for value in (self.mean, self.scale, self.coefficients)):
            raise ValueError("portable model vectors do not match feature names")
        if np.any(self.scale <= 0):
            raise ValueError("portable model scales must be positive")

    @staticmethod
    def _sigmoid(value: np.ndarray) -> np.ndarray:
        positive = value >= 0
        output = np.empty_like(value, dtype=float)
        output[positive] = 1.0 / (1.0 + np.exp(-value[positive]))
        exponential = np.exp(value[~positive])
        output[~positive] = exponential / (1.0 + exponential)
        return output

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        matrix = np.asarray(features, dtype=float)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.shape[1] != len(self.feature_names):
            raise ValueError("feature matrix width does not match portable model")
        standardized = (matrix - self.mean) / self.scale
        return self._sigmoid(standardized @ self.coefficients + self.intercept)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rt-dash-portable-logistic-v1",
            "feature_names": list(self.feature_names),
            "mean": self.mean.astype(float).tolist(),
            "scale": self.scale.astype(float).tolist(),
            "coefficients": self.coefficients.astype(float).tolist(),
            "intercept": float(self.intercept),
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    def save_c_header(self, path: str | Path) -> None:
        """Export allocation-free C99/C++ inference for embedded integration."""

        def array(values: np.ndarray) -> str:
            return ",\n    ".join(f"{float(value):.17g}" for value in values)

        comments = "\n".join(
            f"/* {index}: {name} */" for index, name in enumerate(self.feature_names)
        )
        header = f"""#ifndef RTDASH_PORTABLE_LOGISTIC_MODEL_H
#define RTDASH_PORTABLE_LOGISTIC_MODEL_H

#include <math.h>
#include <stddef.h>

#define RTDASH_AI_FEATURE_COUNT {len(self.feature_names)}u

{comments}

static const double RTDASH_AI_MEAN[RTDASH_AI_FEATURE_COUNT] = {{
    {array(self.mean)}
}};
static const double RTDASH_AI_SCALE[RTDASH_AI_FEATURE_COUNT] = {{
    {array(self.scale)}
}};
static const double RTDASH_AI_WEIGHT[RTDASH_AI_FEATURE_COUNT] = {{
    {array(self.coefficients)}
}};
static const double RTDASH_AI_INTERCEPT = {self.intercept:.17g};

static inline double rtdash_ai_risk(const double *features, size_t length) {{
    if (features == NULL || length != RTDASH_AI_FEATURE_COUNT) return -1.0;
    double score = RTDASH_AI_INTERCEPT;
    for (size_t i = 0; i < RTDASH_AI_FEATURE_COUNT; ++i) {{
        score += ((features[i] - RTDASH_AI_MEAN[i]) / RTDASH_AI_SCALE[i])
                 * RTDASH_AI_WEIGHT[i];
    }}
    if (score >= 0.0) return 1.0 / (1.0 + exp(-score));
    const double exponential = exp(score);
    return exponential / (1.0 + exponential);
}}

#endif
"""
        Path(path).write_text(header, encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "PortableLogisticRiskModel":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema") != "rt-dash-portable-logistic-v1":
            raise ValueError("unsupported portable model schema")
        return cls(
            feature_names=tuple(payload["feature_names"]),
            mean=np.asarray(payload["mean"], dtype=float),
            scale=np.asarray(payload["scale"], dtype=float),
            coefficients=np.asarray(payload["coefficients"], dtype=float),
            intercept=float(payload["intercept"]),
        )


def _future_any(values: np.ndarray, groups: np.ndarray, steps: int) -> np.ndarray:
    output = np.zeros(len(values), dtype=np.uint8)
    for group in np.unique(groups):
        positions = np.flatnonzero(groups == group)
        data = values[positions].astype(np.uint8)
        # O(n) reverse sliding maximum for a binary target.
        reverse = pd.Series(data[::-1]).rolling(steps + 1, min_periods=1).max()
        output[positions] = reverse.to_numpy(dtype=np.uint8)[::-1]
    return output


def prepare_openshs_ai_dataset(
    csv_path: str | Path,
    sample_period_seconds: int = 10,
    prediction_horizon_seconds: int = 60,
    purge_seconds: int = 300,
) -> PreparedAIDataset:
    """Build causal features and fixed chronological train/validation/test data.

    The first eight source dates form training, the next three validation, and
    the final three test.  A five-minute default purge removes samples adjacent
    to both partition boundaries.  ``Activity`` supplies labels only and is
    never included in the feature matrix.  Thesis-generated resource columns
    are also excluded because they are synthetic annotations.
    """

    if sample_period_seconds <= 0 or prediction_horizon_seconds < 0:
        raise ValueError("sample period must be positive and horizon non-negative")
    frame = pd.read_csv(csv_path)
    if "timestamp" not in frame or "Activity" not in frame:
        raise ValueError("OpenSHS input must contain timestamp and Activity")

    timestamps = pd.to_datetime(
        frame["timestamp"].astype(str).str.replace("_", ":", regex=False),
        errors="coerce",
    )
    if timestamps.isna().any():
        raise ValueError("OpenSHS input contains invalid timestamps")
    source_rows = np.arange(len(frame), dtype=np.int64)
    sequence_ids = timestamps.diff().dt.total_seconds().ne(1).cumsum().to_numpy()
    within_sequence = pd.Series(sequence_ids).groupby(sequence_ids, sort=False).cumcount()
    keep = (within_sequence % sample_period_seconds).to_numpy() == 0

    frame = frame.loc[keep].reset_index(drop=True)
    timestamps = timestamps.loc[keep].reset_index(drop=True)
    source_rows = source_rows[keep]
    sequence_ids = sequence_ids[keep]
    sensor_names = tuple(column for column in frame.columns if column not in NON_SENSOR_COLUMNS)
    if not sensor_names:
        raise ValueError("OpenSHS input contains no sensor columns")

    sensors = frame.loc[:, sensor_names].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    sensors = sensors.astype(np.float32)
    group = pd.Series(sequence_ids, index=sensors.index)
    previous = sensors.groupby(group, sort=False).shift(1).fillna(sensors)
    changes = (sensors - previous).abs()
    window_samples = max(1, int(round(60 / sample_period_seconds)))
    rolling_changes = (
        changes.groupby(group, sort=False)
        .rolling(window_samples, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    rolling_means = (
        sensors.groupby(group, sort=False)
        .rolling(window_samples, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    seconds = (
        timestamps.dt.hour.to_numpy() * 3600
        + timestamps.dt.minute.to_numpy() * 60
        + timestamps.dt.second.to_numpy()
    )
    time_features = np.column_stack(
        [
            np.sin(2.0 * np.pi * seconds / 86_400.0),
            np.cos(2.0 * np.pi * seconds / 86_400.0),
        ]
    )
    features = np.column_stack(
        [
            sensors.to_numpy(dtype=np.float32),
            changes.sum(axis=1).to_numpy(dtype=np.float32),
            rolling_changes.sum(axis=1).to_numpy(dtype=np.float32),
            rolling_means.to_numpy(dtype=np.float32),
            time_features.astype(np.float32),
        ]
    ).astype(np.float32)
    feature_names = (
        tuple(f"sensor_current__{name}" for name in sensor_names)
        + ("sensor_changes_current_total", "sensor_changes_60s_total")
        + tuple(f"sensor_mean_60s__{name}" for name in sensor_names)
        + ("time_of_day_sin", "time_of_day_cos")
    )

    activities = frame["Activity"].astype(str).str.strip().str.lower().to_numpy()
    target_current = (activities == "anomaly").astype(np.uint8)
    future_steps = int(math.ceil(prediction_horizon_seconds / sample_period_seconds))
    target_future = _future_any(target_current, sequence_ids, future_steps)

    unique_dates = np.array(sorted(timestamps.dt.date.unique()))
    if len(unique_dates) < 14:
        raise ValueError("expected at least 14 distinct OpenSHS dates")
    train_dates = set(unique_dates[:8])
    validation_dates = set(unique_dates[8:11])
    test_dates = set(unique_dates[11:14])
    dates = timestamps.dt.date.to_numpy()
    splits = np.full(len(frame), "purged", dtype="U10")
    splits[np.isin(dates, list(train_dates))] = "train"
    splits[np.isin(dates, list(validation_dates))] = "validation"
    splits[np.isin(dates, list(test_dates))] = "test"

    if purge_seconds:
        boundaries = [
            pd.Timestamp(min(validation_dates)),
            pd.Timestamp(min(test_dates)),
        ]
        for boundary in boundaries:
            distance = np.abs((timestamps - boundary).dt.total_seconds().to_numpy())
            splits[distance < purge_seconds] = "purged"

    return PreparedAIDataset(
        features=features,
        feature_names=feature_names,
        timestamps=timestamps.to_numpy(dtype="datetime64[s]"),
        sequence_ids=sequence_ids.astype(np.int64),
        source_rows=source_rows,
        activities=activities,
        target_current=target_current,
        target_future=target_future,
        splits=splits,
        sensor_names=sensor_names,
        sample_period_seconds=sample_period_seconds,
        prediction_horizon_seconds=prediction_horizon_seconds,
    )


def choose_safety_threshold(
    labels: np.ndarray,
    probabilities: np.ndarray,
    false_negative_cost: float = 5.0,
    false_positive_cost: float = 1.0,
) -> tuple[float, float]:
    """Select a threshold on validation data with an explicit safety cost."""

    labels = np.asarray(labels, dtype=np.uint8)
    probabilities = np.asarray(probabilities, dtype=float)
    if len(labels) != len(probabilities) or not len(labels):
        raise ValueError("labels and probabilities must be equally non-empty")
    candidates = np.unique(
        np.concatenate(([0.0, 1.0], np.quantile(probabilities, np.linspace(0, 1, 1001))))
    )
    prevalence = max(float(labels.mean()), np.finfo(float).eps)
    negative_rate = max(1.0 - float(labels.mean()), np.finfo(float).eps)
    best = (math.inf, 1.0)
    for threshold in candidates:
        prediction = probabilities >= threshold
        fnr = float(np.sum((labels == 1) & ~prediction)) / (len(labels) * prevalence)
        fpr = float(np.sum((labels == 0) & prediction)) / (len(labels) * negative_rate)
        objective = false_negative_cost * fnr + false_positive_cost * fpr
        # Higher thresholds win exact ties, limiting needless Critical Mode.
        candidate = (objective, -float(threshold))
        if candidate < (best[0], -best[1]):
            best = (objective, float(threshold))
    return best[1], best[0]


def expected_calibration_error(
    labels: np.ndarray, probabilities: np.ndarray, bins: int = 10
) -> float:
    labels = np.asarray(labels, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for index in range(bins):
        if index == bins - 1:
            mask = (probabilities >= edges[index]) & (probabilities <= edges[index + 1])
        else:
            mask = (probabilities >= edges[index]) & (probabilities < edges[index + 1])
        if mask.any():
            error += float(mask.mean()) * abs(float(labels[mask].mean()) - float(probabilities[mask].mean()))
    return error


def classification_metrics(
    labels: np.ndarray, probabilities: np.ndarray, threshold: float
) -> dict[str, float | int]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    labels = np.asarray(labels, dtype=np.uint8)
    probabilities = np.asarray(probabilities, dtype=float)
    prediction = probabilities >= threshold
    tp = int(np.sum((labels == 1) & prediction))
    tn = int(np.sum((labels == 0) & ~prediction))
    fp = int(np.sum((labels == 0) & prediction))
    fn = int(np.sum((labels == 1) & ~prediction))
    sensitivity = tp / (tp + fn) if tp + fn else math.nan
    specificity = tn / (tn + fp) if tn + fp else math.nan
    precision = tp / (tp + fp) if tp + fp else math.nan
    f1 = 2 * precision * sensitivity / (precision + sensitivity) if precision + sensitivity else math.nan
    brier = float(np.mean((probabilities - labels) ** 2))
    return {
        "n": len(labels),
        "positives": int(labels.sum()),
        "threshold": float(threshold),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "auroc": float(roc_auc_score(labels, probabilities)),
        "auprc": float(average_precision_score(labels, probabilities)),
        "brier": brier,
        "ece_10": expected_calibration_error(labels, probabilities, 10),
    }


def episode_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    sequence_ids: np.ndarray,
    threshold: float,
    sample_period_seconds: int,
) -> dict[str, float | int | None]:
    """Score whether and how quickly each contiguous anomaly episode is found."""

    labels = np.asarray(labels, dtype=np.uint8)
    prediction = np.asarray(probabilities, dtype=float) >= threshold
    groups = np.asarray(sequence_ids)
    episodes = 0
    detected = 0
    delays: list[float] = []
    for group in np.unique(groups):
        positions = np.flatnonzero(groups == group)
        truth = labels[positions].astype(bool)
        starts = np.flatnonzero(truth & ~np.r_[False, truth[:-1]])
        ends = np.flatnonzero(truth & ~np.r_[truth[1:], False])
        for start, end in zip(starts, ends):
            episodes += 1
            found = np.flatnonzero(prediction[positions[start : end + 1]])
            if found.size:
                detected += 1
                delays.append(float(found[0] * sample_period_seconds))
    return {
        "episodes": episodes,
        "episodes_detected": detected,
        "episode_recall": detected / episodes if episodes else None,
        "mean_detection_delay_seconds": float(np.mean(delays)) if delays else None,
        "median_detection_delay_seconds": float(np.median(delays)) if delays else None,
        "max_detection_delay_seconds": float(np.max(delays)) if delays else None,
    }


def cluster_bootstrap_mean_ci(
    values: np.ndarray,
    clusters: np.ndarray,
    seed: int = 20260804,
    resamples: int = 10_000,
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    clusters = np.asarray(clusters)
    finite = np.isfinite(values)
    values, clusters = values[finite], clusters[finite]
    unique = np.unique(clusters)
    if not len(values) or not len(unique):
        return math.nan, math.nan
    by_cluster = [values[clusters == cluster] for cluster in unique]
    rng = np.random.default_rng(seed)
    means = np.empty(resamples, dtype=float)
    for index in range(resamples):
        selected = rng.integers(0, len(unique), size=len(unique))
        sample = np.concatenate([by_cluster[position] for position in selected])
        means[index] = float(sample.mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def predictive_signals(
    probabilities: Iterable[float],
    step_ms: int,
    start_ms: int = 0,
    source: str = "ai-critical-state",
) -> list[PredictiveModeSignal]:
    if step_ms <= 0 or start_ms < 0:
        raise ValueError("invalid predictive-signal timing")
    return [
        PredictiveModeSignal(
            time=start_ms + index * step_ms,
            risk=float(probability),
            generated_at=start_ms + index * step_ms,
            source=source,
        )
        for index, probability in enumerate(probabilities)
    ]


def sensor_outage_feature_matrix(
    features: np.ndarray,
    feature_names: Sequence[str],
    failed_sensors: Sequence[str],
) -> np.ndarray:
    """Return a copy with all feature channels for failed sensors zeroed."""

    output = np.asarray(features, dtype=np.float32).copy()
    failed = set(failed_sensors)
    for index, name in enumerate(feature_names):
        if any(name.endswith(f"__{sensor}") for sensor in failed):
            output[:, index] = 0.0
    return output
