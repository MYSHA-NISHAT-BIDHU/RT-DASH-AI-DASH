#!/usr/bin/env python3
"""Measure exported AI inference cost on the current host without extrapolation."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cpu_model() -> str:
    path = Path("/proc/cpuinfo")
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def binary_size(binary: Path) -> dict[str, int | None]:
    values: dict[str, int | None] = {
        "executable_bytes": binary.stat().st_size,
        "text_bytes": None,
        "data_bytes": None,
        "bss_bytes": None,
    }
    tool = shutil.which("size")
    if tool is None:
        return values
    lines = subprocess.check_output([tool, str(binary)], text=True).splitlines()
    if len(lines) >= 2:
        fields = lines[1].split()
        if len(fields) >= 3:
            values.update(
                text_bytes=int(fields[0]),
                data_bytes=int(fields[1]),
                bss_bytes=int(fields[2]),
            )
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--header", type=Path, default=Path("results/ai_extension/portable_logistic_model.h")
    )
    parser.add_argument(
        "--source", type=Path,
        default=Path("../research_cpp/benchmarks/benchmark_portable_header.cpp"),
    )
    parser.add_argument("--output", type=Path, default=Path("results/ai_host_benchmark"))
    parser.add_argument("--iterations", type=int, default=1000000)
    parser.add_argument("--warmup", type=int, default=100000)
    parser.add_argument("--trials", type=int, default=25)
    args = parser.parse_args()
    if args.iterations <= 0 or args.warmup < 0 or args.trials < 5:
        raise ValueError("iterations must be positive, warmup non-negative, and trials >= 5")

    header = args.header.resolve()
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("g++")
    if compiler is None:
        raise RuntimeError("g++ is required for the portable host benchmark")
    if not header.is_file() or not source.is_file():
        raise FileNotFoundError("portable header or benchmark source is missing")

    compiler_version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
    with tempfile.TemporaryDirectory(prefix="rtdash-host-bench-") as temporary:
        binary = Path(temporary) / "rtdash_ai_benchmark"
        command = [
            compiler,
            "-std=c++17",
            "-O3",
            "-DNDEBUG",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            f"-I{header.parent}",
            str(source),
            "-o",
            str(binary),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        sizes = binary_size(binary)
        rows = []
        for trial in range(args.trials):
            payload = json.loads(
                subprocess.check_output(
                    [str(binary), str(args.iterations), str(args.warmup)], text=True
                )
            )
            rows.append({"trial": trial, **payload})

    trials = pd.DataFrame(rows)
    trials.to_csv(output / "portable_host_inference_trials.csv", index=False)
    latency = trials.ns_per_inference.to_numpy(dtype=float)
    manifest = {
        "study": "RT-DASH portable AI host inference benchmark",
        "scope": "measured on this host only; not an MCU/WCET claim",
        "created_utc": pd.Timestamp.utcnow().isoformat(),
        "iterations_per_trial": args.iterations,
        "warmup_iterations": args.warmup,
        "trials": args.trials,
        "median_ns_per_inference": float(np.median(latency)),
        "mean_ns_per_inference": float(np.mean(latency)),
        "p05_ns_per_inference": float(np.percentile(latency, 5)),
        "p95_ns_per_inference": float(np.percentile(latency, 95)),
        "min_ns_per_inference": float(np.min(latency)),
        "max_ns_per_inference": float(np.max(latency)),
        "binary_size": sizes,
        "header_sha256": sha256(header),
        "source_sha256": sha256(source),
        "compiler": compiler_version,
        "cpu_model": cpu_model(),
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    (output / "portable_host_benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    targets = sorted(path for path in output.iterdir() if path.is_file() and not path.name.startswith("SHA256SUMS"))
    (output / "SHA256SUMS_HOST_BENCHMARK.txt").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in targets), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
