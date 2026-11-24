#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=None, help="Result directory to verify")
    parser.add_argument("--skip-build", action="store_true", help="Skip pytest/C++ build checks")
    args = parser.parse_args()
    research = Path(__file__).resolve().parents[1]
    project = research.parent
    out = args.results.resolve() if args.results else research / "results" / "best_journal"

    if not args.skip_build:
        test_environment = os.environ.copy()
        existing_pythonpath = test_environment.get("PYTHONPATH")
        test_environment["PYTHONPATH"] = str(research) + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=research,
            env=test_environment,
            check=True,
        )
        cpp = project / "research_cpp"
        if shutil.which("cmake") and shutil.which("ctest"):
            build = cpp / "build_best"
            subprocess.run(
                ["cmake", "-S", str(cpp), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["cmake", "--build", str(build), "-j", "4"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["ctest", "--test-dir", str(build), "--output-on-failure"], check=True
            )
        elif shutil.which("g++"):
            with tempfile.TemporaryDirectory(prefix="rtdash_cpp_") as temporary:
                executable = Path(temporary) / "rtdash_tests"
                subprocess.run(
                    [
                        "g++", "-std=c++17", "-Wall", "-Wextra", "-Wpedantic",
                        f"-I{cpp / 'include'}",
                        str(cpp / "src" / "Scheduler.cpp"),
                        str(cpp / "src" / "ResourceManager.cpp"),
                        str(cpp / "src" / "PortableLogisticModel.cpp"),
                        str(cpp / "tests" / "test_scheduler.cpp"),
                        "-o", str(executable),
                    ],
                    check=True,
                )
                subprocess.run([str(executable)], check=True)
        else:
            raise RuntimeError("verification requires either CMake/CTest or g++")

    manifest = json.loads((out / "execution_manifest_best.json").read_text())
    expected = {
        "tuning_train_runs.csv": 2520,
        "tuning_validation_runs.csv": 420,
        "heldout_test_runs.csv": 420,
        "demand_bound_screen.csv": 70,
        "overhead_jitter_robustness.csv": 960,
        "external_edf_vd_benchmark.csv": 800,
        "full_matrix_optimized_variants.csv": 1680,
    }
    for name, rows in expected.items():
        frame = pd.read_csv(out / name)
        require(len(frame) == rows, f"{name}: expected {rows}, got {len(frame)}")

    train = pd.read_csv(out / "tuning_train_runs.csv")
    validation = pd.read_csv(out / "tuning_validation_runs.csv")
    heldout = pd.read_csv(out / "heldout_test_runs.csv")
    require(set(train.seed.unique()) == set(range(10)), "training seeds are not 0-9")
    require(set(validation.seed.unique()) == set(range(10, 20)), "validation seeds are not 10-19")
    require(set(heldout.seed.unique()) == set(range(20, 30)), "held-out seeds are not 20-29")
    require(set(train.seed).isdisjoint(set(validation.seed)), "train/validation overlap")
    require(set(train.seed).isdisjoint(set(heldout.seed)), "train/test overlap")
    require(set(validation.seed).isdisjoint(set(heldout.seed)), "validation/test overlap")

    selected = json.loads((out / "selected_configuration.json").read_text())
    validation_rank = pd.read_csv(out / "tuning_validation_ranking.csv")
    winner = validation_rank.iloc[0]
    require(math.isclose(selected["utilization_high"], winner.utilization_high), "selected high threshold mismatch")
    require(math.isclose(selected["utilization_low"], winner.utilization_low), "selected low threshold mismatch")
    require(selected["entry_hold"] == int(winner.entry_hold), "selected entry hold mismatch")
    require(selected["recovery_hold"] == int(winner.recovery_hold), "selected recovery hold mismatch")

    emergency = heldout[heldout.scenario.str.startswith("emergency_")]
    wide = emergency.pivot_table(
        index=["scenario", "target_utilization", "seed"],
        columns="variant", values="high_deadline_miss_ratio", aggfunc="first",
    )
    high_diff = wide["rt_dash_recovery_edf_tuned"] - wide["rt_dash_tuned"]
    require(np.allclose(high_diff.fillna(0), 0), "recovery-aware policy changed high-criticality DMR")

    full = pd.read_csv(out / "full_matrix_optimized_variants.csv")
    wide_low = full.pivot_table(
        index=["scenario", "target_utilization", "seed"],
        columns="variant", values="low_work_weighted_utility_linear", aggfunc="first",
    )
    utility_diff = wide_low["rt_dash_recovery_edf_tuned"] - wide_low["rt_dash_tuned"]
    require(float(utility_diff.mean()) > 0.05, "full-matrix utility improvement unexpectedly small")

    external = pd.read_csv(out / "external_edf_vd_benchmark.csv")
    expected_policies = {"edf", "criticality_edf", "edf_vd_drop", "edf_vd_imc", "rt_dash_mc"}
    require(set(external.policy.unique()) == expected_policies, "external comparator policies incomplete")
    require(external.virtual_deadline_factor.between(0, 1, inclusive="neither").all(), "invalid virtual deadline factor")

    demand = pd.read_csv(out / "demand_bound_screen.csv")
    require((demand.max_full_demand_ratio >= demand.max_minimum_service_demand_ratio - 1e-12).all(), "minimum demand exceeds full demand")

    cpp = pd.read_csv(out / "cpp_host_simulation_best.csv")
    require("rt_dash_recovery_edf" in set(cpp.policy), "C++ recovery-aware parity run missing")

    require(manifest["counts"]["cumulative_executed_simulations"] == 15780, "manifest cumulative count mismatch")
    print("BEST PROJECT VALIDATION: PASS")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"Held-out high-DMR difference (recovery-aware - tuned): {high_diff.mean():.6f}")
    print(f"Full-matrix low utility difference: {utility_diff.mean():.6f}")


if __name__ == "__main__":
    main()
