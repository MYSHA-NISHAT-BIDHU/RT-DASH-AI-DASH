# Reproducibility Guide

## 1. Software prerequisites

- Linux, macOS, or Windows with a POSIX-like shell for the provided script;
- Python 3.11 or newer;
- CMake 3.16 or newer;
- a C++17 compiler;
- Python packages listed in `research/requirements.txt`.

For exact reproduction of the frozen strongest-version environment, use
`research/requirements-lock-2026-08-05.txt` with Python 3.12.13. The shorter
`requirements.txt` remains the portable minimum specification.

## 2. Validate source

```bash
make test
```

This runs the Python unit tests and the C++ reference tests.

The final simulation-only suite contains 48 Python tests. To verify every
preserved deterministic result plus the principal AI study, exploratory
future-window study, and measured host benchmark, run:

```bash
cd research
make verify-all
```

To rebuild all final AI/forecasting evidence blocks before verifying them, run:

```bash
cd research
make strongest-reproduce
```

## 3. Reproduce controlled results

```bash
cd research
PYTHONPATH=. python scripts/run_batched_experiments.py
PYTHONPATH=. python scripts/analyze_results.py
PYTHONPATH=. python -c "from pathlib import Path; from rt_dash.plotting import plot_controlled; plot_controlled(Path('results/controlled_summary.csv'), Path('results/figures'))"
```

Per-seed results are written under `research/results/batches/`. Existing successful batches are reused unless `--force` is specified.

## 4. Reproduce trace results

```bash
cd research
PYTHONPATH=. python scripts/run_batched_experiments.py --trace
```

The raw CSV must exist at `data/raw/smart_home_dataset.csv` relative to the project root.

## 5. Reproduce dataset audit

```bash
python research/scripts/audit_dataset.py \
  --raw data/raw/smart_home_dataset.csv \
  --processed data/processed/processed_smart_home_dataset_with_resources.csv \
  --output research/results/dataset_audit.json
```

## 6. Reproduce preprocessing sample

```bash
python research/scripts/preprocess_reproducible.py \
  data/raw/smart_home_dataset.csv \
  research/data_samples/clean_trace_sample.csv \
  --limit 10000 --synthetic-resources --seed 20260707
```

## 7. C++ sanitized validation

```bash
cmake -S research_cpp -B research_cpp/build_sanitized \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
  -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'
cmake --build research_cpp/build_sanitized
ASAN_OPTIONS=detect_leaks=1 ctest --test-dir research_cpp/build_sanitized --output-on-failure
```

## 8. AI principal, ARIMA/LSTM, future-window, and portable-host evidence

```bash
cd research
PYTHONPATH=. python scripts/run_ai_extension_study.py
PYTHONPATH=. python scripts/run_ai_early_warning_study.py
PYTHONPATH=. python scripts/run_arima_lstm_thesis_study.py
PYTHONPATH=.:scripts python scripts/run_arima_lstm_advanced_study.py
PYTHONPATH=. python scripts/run_portable_host_benchmark.py
PYTHONPATH=. python scripts/verify_ai_extension_results.py
PYTHONPATH=. python scripts/verify_ai_early_warning_results.py
PYTHONPATH=. python scripts/verify_arima_lstm_thesis_results.py
PYTHONPATH=. python scripts/verify_arima_lstm_advanced_results.py
PYTHONPATH=. python scripts/verify_portable_host_benchmark.py
```

The principal model and thresholds are frozen before the post-lock diagnostics;
see `docs/AI_POST_LOCK_GOVERNANCE.md`. The future-window study is exploratory
and has its own manifest. The portable benchmark records 25 repeated measured
host trials and its compiler/CPU provenance. It must not be reported as MCU,
WCET, energy, or hardware-validation evidence.

The advanced ARIMA/LSTM protocol is frozen before its own execution but reuses
dates whose locked thesis-test metrics were already inspected. It is therefore
post-lock sensitivity/robustness evidence; see
`docs/ARIMA_LSTM_ADVANCED_POST_LOCK_GOVERNANCE_2026-08-06.md`.

## 9. Provenance rules

- `research/results/controlled_*` and `trace_*` are new outputs.
- thesis numerical summaries must not be merged into these files;
- synthetic resource annotations must never be described as measured traces;
- trace-task timing parameters must be reported as model choices;
- physical-board outputs must be stored in a separate directory with a hardware manifest.
- no post-lock diagnostic may be used to tune the principal AI model or its
  locked raw-sensor thresholds against the already inspected final three dates.
