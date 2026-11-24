from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_hashes(output: Path) -> int:
    lines = (output / "SHA256SUMS_AI_GENERALIZATION.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    for line in lines:
        expected, relative = line.split("  ", 1)
        path = output / relative
        require(path.is_file(), f"hashed artifact missing: {relative}")
        require(sha256(path) == expected, f"hash mismatch: {relative}")
    return len(lines)


def main() -> None:
    output = Path("results/ai_generalization")
    manifest = json.loads(
        (output / "ai_generalization_manifest.json").read_text(encoding="utf-8")
    )
    rolling = pd.read_csv(output / "rolling_origin_metrics.csv")
    summary = pd.read_csv(output / "rolling_origin_summary.csv")
    outage = pd.read_csv(output / "grouped_sensor_outage.csv")
    duplicate = pd.read_csv(output / "duplicate_timestamp_sensitivity.csv")
    principal = pd.read_csv("results/ai_extension/classification_metrics.csv")
    principal = principal[(principal.model == "current_sensor_logistic") & (principal.split == "test")].iloc[0]
    baseline = outage[outage.group == "none"].iloc[0]

    require(manifest["hardware_used"] is False, "AI study must be simulation/software only")
    require(manifest["principal_model_reselected"] is False, "principal model was reselected")
    require(manifest["principal_threshold_changed"] is False, "principal threshold changed")
    require(manifest["principal_scheduler_result_changed"] is False, "principal scheduler evidence changed")
    require(manifest["rolling_origin_folds"] == 9 and len(rolling) == 36, "rolling-origin matrix mismatch")
    require(rolling.groupby("test_date").size().eq(4).all(), "each rolling date must contain four models")
    require((rolling.diagnostic_only_after_principal_test_lock == True).all(), "post-lock diagnostic flag missing")  # noqa: E712
    require(len(summary) == 4, "rolling summary must contain four candidate families")
    require(manifest["sensor_failure_groups"] == 7, "sensor failure-group count mismatch")
    require(len(outage) == 8, "outage matrix must include baseline plus seven groups")

    # The loaded serialized principal reproduces threshold metrics/calibration
    # exactly.  AUROC/AUPRC can move by <1e-4 under different BLAS batch shapes
    # when probabilities are effectively tied, so only those rank metrics use
    # a deliberately narrow numerical tolerance.
    for column in ("sensitivity", "specificity", "brier", "ece_10"):
        require(np.isclose(float(baseline[column]), float(principal[column]), rtol=0, atol=1e-12), f"locked baseline mismatch: {column}")
    for column in ("auroc", "auprc"):
        require(np.isclose(float(baseline[column]), float(principal[column]), rtol=0, atol=1e-4), f"locked rank metric mismatch: {column}")
    require((duplicate.excluded == 0).all(), "prepared held-out split unexpectedly contains duplicate timestamps")

    hash_count = verify_hashes(output)
    print("AI GENERALIZATION VERIFICATION: PASS")
    print(json.dumps({"hashed_outputs": hash_count, "rolling_origin_rows": 36}, indent=2))


if __name__ == "__main__":
    main()
