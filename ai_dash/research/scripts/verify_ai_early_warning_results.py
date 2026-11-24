#!/usr/bin/env python3
"""Fail-closed verification of the exploratory 60-second early-warning study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/ai_early_warning"))
    args = parser.parse_args()
    output = args.results.resolve()
    manifest = json.loads((output / "future_execution_manifest.json").read_text(encoding="utf-8"))
    selection = pd.read_csv(output / "future_model_selection.csv")
    metrics = pd.read_csv(output / "future_classification_metrics.csv")
    warnings = pd.read_csv(output / "future_pre_onset_warnings.csv")

    require(manifest["claim_status"].startswith("exploratory only"), "claim boundary changed")
    require(manifest["prediction_horizon_seconds"] == 60, "future horizon changed")
    require(manifest["purge_seconds"] == 300, "purge changed")
    require(manifest["selection_uses_test"] is False, "test was used for future-model selection")
    require(
        manifest["partition_counts"] == {"train": 60108, "validation": 23972, "test": 20670},
        "partition counts changed",
    )
    require(str(selection.iloc[0].model) == manifest["selected_model"], "selected future model mismatch")
    require(set(metrics.split) == {"train", "validation", "test"}, "metric splits incomplete")
    require(metrics.model.nunique() == 5 and len(metrics) == 15, "future model matrix incomplete")
    require(len(warnings) == manifest["test_onset_episodes"], "episode count mismatch")
    observed_leads = warnings.maximum_observed_lead_seconds.dropna().to_numpy(dtype=float)
    require(np.all(observed_leads > 0), "non-positive pre-onset lead")
    require(np.all(observed_leads <= 60), "pre-onset lead exceeds fixed horizon")

    lines = (output / "SHA256SUMS_FUTURE.txt").read_text(encoding="utf-8").splitlines()
    require(len(lines) == 4, "unexpected future-study hash manifest size")
    for line in lines:
        expected, name = line.split("  ", 1)
        require(sha256(output / name) == expected, f"hash mismatch: {name}")

    print("AI EARLY-WARNING VALIDATION: PASS")
    print(json.dumps({
        "selected_model": manifest["selected_model"],
        "test_onset_episodes": manifest["test_onset_episodes"],
        "pre_onset_warning_recall": manifest["pre_onset_warning_recall"],
        "median_maximum_lead_seconds": manifest["median_maximum_lead_seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
