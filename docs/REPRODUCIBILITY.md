# Reproducibility Guide

## Status of this public package

This package is a **repository scaffold plus research documentation** prepared from the validated RT-DASH / AI-DASH project record.

Before claiming that this GitHub repository is fully executable or fully reproducible, copy the authoritative source code, test suite, configuration files, result-verification scripts, and exact environment metadata from the validated research project into this repository.

## Verified project evidence

The validated RT-DASH project record documents:

- authoritative Python code under `research/rt_dash` and `research/scripts`
- an independent portable C++17 core under `research_cpp`
- automated tests and validation scripts
- raw and processed OpenSHS-derived data
- manifests and SHA-256 hashes
- Python test execution
- a fresh C++ Release build and CTest pass
- exact reproduction of deterministic training and optimized-matrix outputs

The AI-DASH project record documents:

- 4,043 chronologically held-out forecast examples
- 714 primary matched scheduler simulations
- eight causal rolling-origin forecasting folds
- 5,724 additional scheduler simulations in robustness analysis

## Recommended public-repository workflow

1. Copy validated source files into `rt_dash/` and `ai_dash/`.
2. Copy only the configuration files needed to reproduce public experiments into `configs/`.
3. Copy verification/test scripts into `tests/`.
4. Do not upload duplicated, private, or manuscript-only working files.
5. Preserve the final SHA-256 manifest if it belongs to the public artifact.
6. Record the exact Python version and package versions from the validated environment.
7. Add exact run commands only after testing them from a clean checkout.
8. Tag a release only after the clean-checkout test succeeds.

## Environment

The public `requirements.txt` lists known core dependencies but is intentionally not version-pinned because the exact historical package versions must come from the validated research environment.

Do not replace this statement with guessed versions.

## Data

The work uses an OpenSHS-derived smart-home trace.

The CPU, memory, storage, and bandwidth variables used in AI-DASH forecasting are synthetic preprocessing annotations. They must not be described as physical resource measurements.

If redistribution terms for any source dataset are uncertain, do not place the raw dataset in GitHub. Provide acquisition and preprocessing instructions instead.

## Evidence boundary

All primary claims in RT-DASH and AI-DASH are based on software simulation. C++ semantic/parity checks are not measurements of deployed RTOS timing.

## Release checklist

- [ ] Source copied from authoritative project
- [ ] Private files removed
- [ ] Dataset licensing checked
- [ ] Exact dependency versions recovered
- [ ] Clean environment created
- [ ] Tests pass
- [ ] Primary experiments reproduce
- [ ] Result verifier passes
- [ ] README commands verified
- [ ] Hash manifest generated
- [ ] GitHub release tagged
