#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def audit(raw_path: Path, processed_path: Path | None, output: Path) -> dict[str, object]:
    raw = pd.read_csv(raw_path)
    timestamps = pd.to_datetime(
        raw["timestamp"].astype(str).str.replace("_", ":", regex=False),
        errors="coerce",
    )
    sorted_ts = timestamps.sort_values()
    deltas = sorted_ts.diff().dt.total_seconds()
    report: dict[str, object] = {
        "raw": {
            "rows": int(len(raw)),
            "columns": list(raw.columns),
            "invalid_timestamps": int(timestamps.isna().sum()),
            "duplicate_rows": int(raw.duplicated().sum()),
            "duplicate_timestamps": int(timestamps.duplicated().sum()),
            "start": str(timestamps.min()),
            "end": str(timestamps.max()),
            "span_seconds": int((timestamps.max() - timestamps.min()).total_seconds()),
            "one_second_steps": int((deltas == 1).sum()),
            "zero_second_steps": int((deltas == 0).sum()),
            "gaps_greater_than_one_second": int((deltas > 1).sum()),
            "activity_counts": {
                str(k): int(v) for k, v in raw["Activity"].value_counts(dropna=False).items()
            },
        }
    }
    if processed_path and processed_path.exists():
        processed = pd.read_csv(processed_path)
        report["processed"] = {
            "rows": int(len(processed)),
            "columns": list(processed.columns),
            "activity_counts": {
                str(k): int(v)
                for k, v in processed["Activity"].value_counts(dropna=False).items()
            },
            "priority_counts": {
                str(k): int(v)
                for k, v in processed["Priority"].value_counts(dropna=False).items()
            },
            "missing_activity": int(processed["Activity"].isna().sum()),
            "resource_ranges": {
                column: {
                    "min": float(processed[column].min()),
                    "max": float(processed[column].max()),
                    "mean": float(processed[column].mean()),
                }
                for column in ["CPU", "Memory", "Storage", "Bandwidth"]
                if column in processed
            },
        }
        report["findings"] = [
            "The raw dataset contains the activity label 'leisure', which the original preprocessing mapping omitted.",
            "The processed dataset contains missing activity values and therefore cannot be treated as a fully classified trace.",
            "CPU, memory, storage, and bandwidth columns are synthetic annotations, not measurements.",
            "Random priority boosts and random resource generation in the original preprocessing script were not seeded, so the processed file cannot be regenerated exactly from the script as written.",
            "Chunk-wise resampling can create inconsistent boundary treatment and forward-fill activities across gaps.",
        ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--processed", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.raw, args.processed, args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
