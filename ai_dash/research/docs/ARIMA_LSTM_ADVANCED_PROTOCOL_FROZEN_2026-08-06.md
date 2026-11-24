# Frozen Advanced ARIMA + LSTM Validation Protocol — 2026-08-06

## Status and non-negotiable evidence boundary

This protocol is frozen before the advanced experiment is executed. It is an
additive strengthening study. It does not replace, retune, delete, or rewrite
the locked deterministic RT-DASH study, the raw-sensor AI study, or the
thesis-faithful ARIMA(5,1,0)+LSTM study.

- Processed thesis resource table SHA-256:
  `c4a717fcd22bad056a163b474ac2813b4661b04fe4f545c2e7246767e9b16a54`
- Locked thesis ARIMA+LSTM output-manifest SHA-256:
  `8de9cbe63475c5b490550e05f36edac61316e9ba42178a31988dce61fd7a08ac`
- Locked thesis ARIMA+LSTM protocol SHA-256:
  `f903ec4d816fe495f77710995d7a050472318258a80f90bf46c8738f7d68bdc7`
- Hardware used: **none**.
- Resource values: **synthetic thesis simulation annotations**, not physical
  CPU, memory, storage, bandwidth, energy, MCU, or WCET measurements.
- No test observation may select a model, hyperparameter, blend weight,
  scheduler threshold, perturbation case, or paper claim.

## Scientific questions

1. Does a leakage-controlled ARIMA+LSTM ensemble improve one-minute resource
   forecasts relative to the fixed thesis hybrid and non-neural baselines?
2. Are conclusions stable under causal rolling-origin refits across dates?
3. Which predictive component actually changes RT-DASH behavior?
4. Does deterministic runtime assurance preserve critical-task behavior when
   predictions are absent, biased, noisy, or stuck high?

## Primary chronological split

The locked split remains unchanged: first 8 dates train, next 3 dates
validation, final 3 dates test. Resampling is 60 s, lookback is 12 intervals,
forecast horizon is 1 interval, and windows never cross timestamp gaps.
Scaling is fitted on training data only.

## Forecast models

All candidates are retained in the output, including inferior ones.

1. Persistence: last observed resource vector.
2. Exponentially weighted history: alpha in `{0.2, 0.5, 0.8}`, selected per
   resource using validation RMSE only.
3. Multivariate ridge-VAR: flattened 12x4 standardized history with an
   intercept; lambda in `{1e-4, 1e-2, 1, 100}`, selected by mean validation
   normalized RMSE across the four outputs.
4. Thesis ARIMA: ARIMA(5,1,0), conditional least squares on first differences.
5. Thesis LSTM anchor: hidden=16, learning rate=0.005, unchanged from the
   locked study.
6. Tuned LSTM: hidden units in `{8, 16, 32}` crossed with learning rate in
   `{0.003, 0.005}`; seed `20260806`; Adam; batch 128; at most 30 epochs;
   patience 5; gradient clipping 5. Candidate selection uses mean validation
   normalized RMSE across all four resources only.
7. Thesis hybrid: ARIMA CPU + locked LSTM Memory/Storage/Bandwidth.
8. Adaptive ARIMA-LSTM: per-resource convex prediction
   `(1-w)*ARIMA + w*tuned-LSTM`; `w` is selected from `0.00, 0.05, ..., 1.00`
   by validation RMSE for that resource. The test split is never inspected for
   weights.

The operational advanced predictor is item 8 even if another baseline is
better on the held-out test. This prevents post-hoc test selection.

## Rolling-origin robustness

Eight causal refit folds are fixed. For fold `k=5,...,12`, dates `1..k` are
training, date `k+1` is validation/early stopping, and date `k+2` is test.
ARIMA(5,1,0), the fixed thesis LSTM architecture (hidden=16, lr=0.005), the
thesis hybrid, and persistence are refitted within every fold. These folds are
robustness evidence only and do not alter the primary split, tuned LSTM, or
adaptive blend.

## Scheduler ablation

Prediction pressures are built independently for:

- all-resource ARIMA;
- all-resource tuned LSTM;
- thesis ARIMA-CPU/LSTM-other hybrid;
- adaptive ARIMA-LSTM blend.

Each predictor receives its own predictive threshold selected on validation
blocks only from `{0.5}` plus pressure quantiles `{0.50, 0.65, 0.75, 0.85,
0.90, 0.95, 0.98, 0.99}`. Test blocks use background-load targets
`{0.30, 0.45, 0.60}`. Both predictive-only and deterministic-safe recovery
policies are executed on the test blocks. The load-only RT-DASH, semantic
RT-DASH, and deterministic recovery policies are also executed once per test
cell as predictor-independent baselines. Semantic event and utilization guards
remain active in the safe policy and cannot be suppressed by the predictor.

## Prediction-fault stress test

The adaptive predictor's validation-selected threshold is frozen before test.
The following pressure faults are then applied to every held-out test block:

- nominal;
- blackout: all prediction pressure = 0;
- stuck-high: all prediction pressure = 1;
- negative bias: pressure - 0.15;
- positive bias: pressure + 0.15;
- deterministic Gaussian error, sigma=0.10;
- deterministic Gaussian error, sigma=0.20.

Pressure is clipped to `[0,1]`. Gaussian seeds are SHA-256-derived from block
identifier, fault name, and master seed `20260806`. The safe recovery policy is
compared with deterministic recovery. Required safety check: blackout behavior
must be exactly identical to deterministic recovery for high-criticality DMR,
low-work utility, and critical-mode fraction. Other faults are reported without
requiring improvement; any utility loss from false positives remains visible.

## Statistics and reporting

- Primary forecast metrics: MAE, RMSE, sMAPE, R2, train-SD-normalized RMSE.
- Primary scheduler metrics: high-criticality DMR and mean response, low-work
  weighted utility, critical-mode fraction.
- Primary test forecast model is the frozen adaptive ARIMA-LSTM predictor.
- Forecast uncertainty: date-cluster bootstrap 95% CI of paired absolute-error
  differences versus persistence and thesis hybrid; only three primary test
  date clusters are explicitly disclosed.
- Rolling-origin robustness is summarized by eight per-date test folds; no
  independence beyond the date-level evaluation is claimed.
- Scheduler comparisons are paired by block/date/background-load and use
  date-cluster bootstrap CIs plus Wilcoxon tests with Holm correction where
  applicable.
- Exact-equality safety claims are made only where the executed rows are exactly
  equal.

## Complexity evidence

Only analytical model size/operation counts are reported. No physical latency,
energy, WCET, FreeRTOS, MCU, or deployment claim is permitted.

## Publication interpretation

The thesis-faithful ARIMA+LSTM model remains the conceptual anchor. The advanced
study adds validation-only model selection, complementary baselines, causal
temporal robustness, mechanism ablation, and runtime-assurance stress testing.
The deterministic RT-DASH framework remains suitable for the generic framework
paper; the predictive ARIMA+LSTM evidence remains the focused AI-paper scope.
