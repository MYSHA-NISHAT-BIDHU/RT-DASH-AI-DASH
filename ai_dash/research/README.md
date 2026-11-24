# RT-DASH Scientific Reference Implementation

## Components

- `rt_dash/model.py`: task and job model with criticality and declared service floors.
- `rt_dash/policies.py`: EDF, RMS, RT-DASH, and ablation policies.
- `rt_dash/simulator.py`: deterministic preemptive uniprocessor reference simulator.
- `rt_dash/workloads.py`: controlled task sets, emergency bursts, and contiguous OpenSHS trace mapping.
- `rt_dash/metrics.py`: completion, deadline, response, preemption, transition, and service-reduction metrics with horizon censoring.
- `rt_dash/experiments.py`: controlled and trace-derived experiment execution.
- `scripts/run_batched_experiments.py`: restartable per-seed runner.
- `scripts/analyze_results.py`: confidence intervals and matched comparisons.
- `scripts/audit_dataset.py`: raw/processed dataset integrity audit.
- `scripts/preprocess_reproducible.py`: deterministic preprocessing replacement.
- `scripts/run_simulation_completion_study.py`: true period adaptation, bounded blocking, and load/severity safety-envelope study.
- `scripts/run_ai_generalization_study.py`: post-lock rolling-origin and correlated sensor-group robustness diagnostics.
- `rt_dash/forecasting.py`: ARIMA(5,1,0) and a dependency-light genuine LSTM for the corrected thesis resource-forecasting branch.
- `scripts/run_arima_lstm_thesis_study.py`: chronological thesis resource forecasting plus predictive RT-DASH integration.
- `scripts/run_arima_lstm_advanced_study.py`: frozen post-lock ARIMA/LSTM
  tuning/baseline, eight-fold temporal robustness, scheduler ablation and
  prediction-fault runtime-assurance study.

## Environment

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

## Rerun controlled experiments

```bash
PYTHONPATH=. python scripts/run_batched_experiments.py
PYTHONPATH=. python scripts/analyze_results.py
```

## Rerun trace-derived experiments

```bash
PYTHONPATH=. python scripts/run_batched_experiments.py --trace
```

The trace runner expects `../data/raw/smart_home_dataset.csv`.

## Final strongest-version verification

```bash
PYTHONPATH=. python scripts/verify_best_journal_results.py
PYTHONPATH=. python scripts/verify_ai_extension_results.py
PYTHONPATH=.:scripts python scripts/verify_ai_early_warning_results.py
PYTHONPATH=. python scripts/verify_portable_host_benchmark.py
PYTHONPATH=. python scripts/verify_simulation_completion_results.py
PYTHONPATH=. python scripts/verify_ai_generalization_results.py
PYTHONPATH=. python scripts/verify_arima_lstm_thesis_results.py
PYTHONPATH=. python scripts/verify_arima_lstm_advanced_results.py
```

The new additive completion study uses seeds 30--39 for training, 40--49 for
validation and 50--59 for a fresh held-out test. The AI generalization study is
post-lock diagnostic and cannot reselect the principal model or thresholds.
The advanced ARIMA/LSTM study likewise reuses already-inspected thesis-test
dates and is governed as post-lock sensitivity/robustness evidence.

## Interpretation warning

The activity-to-task timing map in `workloads.py` is a new explicit research artifact introduced to make the incomplete project reproducible. It is not a recovered measured WCET map. Controlled experiment results are generated simulation evidence, not historical thesis results or physical measurements. The final project uses no hardware.
