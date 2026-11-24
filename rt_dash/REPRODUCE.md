# Reproduction and Validation Guide

All commands below are run from the extracted archive root.

## 1. Python environment

The manuscript's recorded analysis environment used CPython 3.13.5 and the exact packages in `environment/requirements-lock.txt`.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r environment/requirements-lock.txt
```

## 2. Unit tests

```bash
PYTHONPATH=research python -m pytest research/tests
```

## 3. Reproduce principal seed-clustered inference

```bash
PYTHONPATH=research python research/scripts/reproduce_seed_clustered_inference.py
```

The script uses matched scenario/load/seed pairs, averages paired differences within seed, draws 10,000 percentile-bootstrap resamples from the seed-level means, uses random seed `20260709`, and applies two-sided Wilcoxon signed-rank tests when at least one seed-level difference is nonzero.

## 4. Verify archived numerical outputs

```bash
PYTHONPATH=research python research/scripts/verify_journal_results.py
PYTHONPATH=research python research/scripts/verify_best_journal_results.py
```

## 5. Audit the trace-source snapshot

Before the dataset-only audit, the complete manuscript-to-archive alignment can be checked with:

```bash
PYTHONPATH=research python research/scripts/verify_manuscript_alignment.py
```

This verifies the complete run inventory, locked configuration, manuscript Tables 4-11, dataset identity, final Figures 1-10, required implementation sources, and firmware-build evidence.

The dataset-only audit is:

```bash
python research/scripts/audit_dataset.py \
  --raw data/raw/smart_home_dataset.csv \
  --output data/dataset_audit_reproduced.json
```

The large processed file from an earlier project stage is deliberately excluded because the RT-DASH experiments use the raw trace snapshot and deterministic workload-mapping scripts. No synthetic resource columns are required for the reported results.

## 6. Build and test the C++17 implementation

With CMake 3.20 or newer and a C++17 compiler:

```bash
cmake -S research_cpp -B build-cpp -DCMAKE_BUILD_TYPE=Release
cmake --build build-cpp
ctest --test-dir build-cpp --output-on-failure
./build-cpp/rtdash_host_simulation
```

Build directories and compiled binaries are intentionally absent from File S1 because they are platform-specific and reproducible from source.

## 7. Inspect or rebuild the FreeRTOS firmware evidence

The archived target folders contain policy-specific ELF/BIN artifacts for both targets and HEX artifacts for STM32, together with maps, disassemblies, size reports, symbol records, and build-artifact hashes. The root `SHA256SUMS.txt` verifies these exact archived files.

The upstream FreeRTOS Kernel V11.1.0 source is not redistributed. To rebuild, obtain that version from the official FreeRTOS project and place it at `rtos/FreeRTOS/`, then run:

```bash
make -C firmware/qemu_lm3s6965 clean all inspect
make -C firmware/stm32f103_bluepill clean all inspect
```

Rebuilds can differ byte-for-byte across compiler versions and paths; preserve the compiler/linker versions and new hashes when comparing them. The supplied firmware evidence is limited to compilation/linkage. It does not represent QEMU runtime output or physical-board measurements.

## 8. Full simulation reruns

The following drivers regenerate the principal experiment groups. Use separate output directories if the archived results must be preserved.

```bash
cd research
python scripts/run_journal_strengthening_study.py \
  --trace-csv ../data/raw/smart_home_dataset.csv \
  --output results/reproduced_journal_strengthened
python scripts/run_best_journal_study.py \
  --output results/reproduced_best_journal
cd ..
```

For the optimized 1,680-run matrix alone:

```bash
cd research
python scripts/reproduce_full_optimized_matrix.py \
  --configuration results/best_journal/selected_configuration.json \
  --output results/reproduced_best_journal
cd ..
```

## 9. File-integrity verification

```bash
sha256sum -c SHA256SUMS.txt
```

`SHA256SUMS.txt` intentionally does not contain a checksum for itself. The ZIP's digest is supplied outside the ZIP alongside the final deliverable.
