from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
    lines = (output / "SHA256SUMS_SIMULATION_COMPLETION.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    for line in lines:
        expected, relative = line.split("  ", 1)
        path = output / relative
        require(path.is_file(), f"hashed artifact missing: {relative}")
        require(sha256(path) == expected, f"hash mismatch: {relative}")
    return len(lines)


def main() -> None:
    output = Path("results/simulation_completion")
    manifest = json.loads(
        (output / "simulation_completion_manifest.json").read_text(encoding="utf-8")
    )
    period = pd.read_csv(output / "period_heldout_test.csv")
    blocking = pd.read_csv(output / "blocking_robustness.csv")
    stress = pd.read_csv(output / "stress_surface.csv")
    train_rank = pd.read_csv(output / "period_tuning_train_ranking.csv")
    validation_rank = pd.read_csv(output / "period_tuning_validation_ranking.csv")

    require(manifest["hardware_used"] is False, "study must be simulation-only")
    require(manifest["test_used_for_selection"] is False, "test leakage in selection")
    require(manifest["train_seeds"] == list(range(30, 40)), "unexpected train seeds")
    require(manifest["validation_seeds"] == list(range(40, 50)), "unexpected validation seeds")
    require(manifest["heldout_test_seeds"] == list(range(50, 60)), "unexpected held-out seeds")
    require(len(train_rank) == 12, "period tuning must evaluate all 12 candidates")
    require(len(validation_rank) >= 2, "validation shortlist unexpectedly small")
    require(len(period) == 180 and len(blocking) == 480 and len(stress) == 600, "run matrix size mismatch")
    require(manifest["new_simulation_runs_total"] == 2340, "new run-count mismatch")
    require(manifest["project_scheduler_simulations_total"] == 18750, "project run-count mismatch")
    require(set(period.seed) == set(range(50, 60)), "held-out period seed mismatch")
    require(set(stress.seed) == set(range(50, 60)), "stress seed mismatch")
    require(set(period.split) == {"heldout_test"}, "period results are not labeled held-out")

    adaptive = period[period.policy.str.contains("period")]
    require((adaptive.period_stretched_intervals > 0).any(), "period stretching was not exercised")
    require((adaptive.period_shrunk_intervals > 0).any(), "period shrinking was not exercised")

    blocked = blocking[blocking.policy == "rt_dash_recovery_edf"].groupby("blocking_ms").high_response_ms.mean()
    require(10 in blocked.index and 0 in blocked.index, "blocking endpoints missing")
    require(blocked.loc[10] > blocked.loc[0], "blocking stress did not affect response time")

    hash_count = verify_hashes(output)
    print("SIMULATION COMPLETION VERIFICATION: PASS")
    print(json.dumps({"hashed_outputs": hash_count, "verified_runs": 2340}, indent=2))


if __name__ == "__main__":
    main()
