#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ACTIVITY_CODE = {
    "sleep": 0,
    "eat": 1,
    "work": 2,
    "personal": 3,
    "other": 4,
    "leisure": 5,
    "anomaly": 6,
    "unknown": 7,
}
CRITICALITY = {
    "sleep": 1,
    "leisure": 1,
    "other": 1,
    "eat": 2,
    "work": 2,
    "personal": 2,
    "anomaly": 3,
    "unknown": 1,
}
BASE_RESOURCE = {
    "sleep": (12, 60, 20, 2),
    "leisure": (28, 140, 35, 7),
    "other": (24, 120, 30, 5),
    "eat": (35, 180, 45, 7),
    "work": (55, 320, 65, 12),
    "personal": (32, 170, 40, 6),
    "anomaly": (75, 400, 80, 18),
    "unknown": (10, 50, 15, 1),
}


def _mode_or_last(values: pd.Series) -> str:
    clean = values.dropna().astype(str).str.lower()
    if clean.empty:
        return "unknown"
    mode = clean.mode()
    return str(mode.iloc[0] if not mode.empty else clean.iloc[-1])


def preprocess(
    input_file: Path,
    output_file: Path,
    regularize: bool = False,
    add_synthetic_resources: bool = False,
    nrows: int | None = None,
) -> pd.DataFrame:
    frame = pd.read_csv(input_file, nrows=nrows)
    if "timestamp" not in frame or "Activity" not in frame:
        raise ValueError("input must contain timestamp and Activity columns")
    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"].astype(str).str.replace("_", ":", regex=False),
        errors="coerce",
    )
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")

    sensor_columns = [c for c in frame.columns if c not in {"timestamp", "Activity"}]
    for column in sensor_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    aggregations = {column: "max" for column in sensor_columns}
    aggregations["Activity"] = _mode_or_last
    frame = frame.groupby("timestamp", as_index=True).agg(aggregations).sort_index()
    frame["observed"] = True

    if regularize:
        full_index = pd.date_range(frame.index.min(), frame.index.max(), freq="1s")
        frame = frame.reindex(full_index)
        frame.index.name = "timestamp"
        frame["observed"] = frame["observed"].fillna(False).astype(bool)
        frame[sensor_columns] = frame[sensor_columns].fillna(0)
        frame["Activity"] = frame["Activity"].fillna("unknown")

    frame["Activity"] = frame["Activity"].astype(str).str.lower()
    frame.loc[~frame["Activity"].isin(ACTIVITY_CODE), "Activity"] = "unknown"
    frame["ActivityCode"] = frame["Activity"].map(ACTIVITY_CODE).astype(int)
    frame["Criticality"] = frame["Activity"].map(CRITICALITY).astype(int)
    frame["ActiveSensorCount"] = (frame[sensor_columns] > 0.5).sum(axis=1).astype(int)

    if add_synthetic_resources:
        bases = frame["Activity"].map(BASE_RESOURCE)
        active = frame["ActiveSensorCount"].to_numpy()
        frame["SyntheticCPU"] = [min(100, b[0] + 2 * a) for b, a in zip(bases, active)]
        frame["SyntheticMemory"] = [b[1] + 4 * a for b, a in zip(bases, active)]
        frame["SyntheticStorage"] = [b[2] + 2 * a for b, a in zip(bases, active)]
        frame["SyntheticBandwidth"] = [b[3] + a for b, a in zip(bases, active)]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    frame.reset_index().to_csv(output_file, index=False)
    return frame.reset_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic smart-home trace preprocessing")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regularize", action="store_true")
    parser.add_argument("--add-synthetic-resources", action="store_true")
    parser.add_argument("--nrows", type=int)
    args = parser.parse_args()
    result = preprocess(
        args.input,
        args.output,
        regularize=args.regularize,
        add_synthetic_resources=args.add_synthetic_resources,
        nrows=args.nrows,
    )
    print(f"wrote {len(result)} rows to {args.output}")
    print(result["Activity"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
