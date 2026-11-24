#!/usr/bin/env python3
"""Fail-closed verifier for the measured portable host-inference benchmark."""

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
    parser.add_argument("--results", type=Path, default=Path("results/ai_host_benchmark"))
    parser.add_argument(
        "--header", type=Path, default=Path("results/ai_extension/portable_logistic_model.h")
    )
    args = parser.parse_args()
    output = args.results.resolve()
    header = args.header.resolve()
    manifest = json.loads(
        (output / "portable_host_benchmark_manifest.json").read_text(encoding="utf-8")
    )
    trials = pd.read_csv(output / "portable_host_inference_trials.csv")

    require(manifest["scope"] == "measured on this host only; not an MCU/WCET claim", "scope changed")
    require(len(trials) == manifest["trials"] >= 5, "trial count mismatch")
    require((trials.iterations == manifest["iterations_per_trial"]).all(), "iteration count mismatch")
    require((trials.warmup == manifest["warmup_iterations"]).all(), "warmup count mismatch")
    require(np.isfinite(trials.ns_per_inference).all(), "non-finite latency")
    require((trials.ns_per_inference > 0).all(), "non-positive latency")
    require(np.isfinite(trials.checksum).all(), "non-finite benchmark checksum")
    require(manifest["header_sha256"] == sha256(header), "portable model header changed")
    require(manifest["binary_size"]["executable_bytes"] > 0, "invalid executable size")

    checksum_file = output / "SHA256SUMS_HOST_BENCHMARK.txt"
    lines = checksum_file.read_text(encoding="utf-8").splitlines()
    require(len(lines) == 2, "unexpected host-benchmark hash manifest size")
    for line in lines:
        expected, name = line.split("  ", 1)
        require(sha256(output / name) == expected, f"hash mismatch: {name}")

    print("PORTABLE HOST BENCHMARK VALIDATION: PASS")
    print(json.dumps({
        "trials": len(trials),
        "median_ns_per_inference": manifest["median_ns_per_inference"],
        "scope": manifest["scope"],
    }, indent=2))


if __name__ == "__main__":
    main()
