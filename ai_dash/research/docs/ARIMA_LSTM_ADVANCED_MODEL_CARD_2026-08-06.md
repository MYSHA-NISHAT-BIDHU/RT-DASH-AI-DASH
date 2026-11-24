# Advanced ARIMA + LSTM Model Card — 2026-08-06

## Intended use

Simulation-only one-minute forecasting of four synthetic thesis resource
annotations for predictive RT-DASH evaluation. The model is not a hardware
resource monitor, safety certificate, WCET estimator, or deployment benchmark.

## Data and chronology

- Source rows: 1,164,409.
- Invalid timestamps: 0.
- Missing Activity labels: 168,923; treated as non-critical `other` only for
  scheduler trace mapping.
- Rows missing a resource annotation: 1; dropped without interpolation.
- Primary split: 8 train dates / 3 validation dates / 3 locked test dates. The
  advanced study reuses already-inspected test dates and is post-lock
  sensitivity/robustness evidence rather than a fresh confirmatory test.
- Forecast examples: 11,033 / 4,320 / 4,043.
- Lookback/horizon: 12 minutes / 1 minute.
- Scaling: training only; windows do not cross timestamp gaps.

## Models

The thesis anchor is ARIMA(5,1,0) CPU plus a 16-hidden-unit multivariate LSTM
for Memory/Storage/Bandwidth. The advanced study freezes six LSTM candidates
before execution; validation selects hidden=32, learning rate=0.005. Per-resource
ARIMA/LSTM convex weights are selected on validation only:

| Resource | ARIMA weight | LSTM weight |
|---|---:|---:|
| CPU | 0.30 | 0.70 |
| Memory | 0.05 | 0.95 |
| Storage | 0.00 | 1.00 |
| Bandwidth | 0.00 | 1.00 |

## Held-out RMSE

| Model | CPU | Memory | Storage | Bandwidth |
|---|---:|---:|---:|---:|
| persistence | 2.516280 | 15.469165 | 3.129938 | 0.835214 |
| ARIMA(5,1,0) | 2.499591 | 15.117285 | 2.935836 | 0.796183 |
| locked thesis hybrid | 2.499591 | **14.262286** | 2.970106 | 0.973536 |
| tuned LSTM | 2.435624 | 14.896159 | 3.183144 | 0.844892 |
| adaptive ARIMA/LSTM | **2.413298** | 14.823566 | 3.183144 | 0.844892 |
| ridge-VAR baseline | 2.574508 | 14.753795 | **2.657374** | **0.778904** |

The adaptive model is not uniformly superior. Its CPU absolute-error advantage
over persistence and the thesis hybrid has a three-date cluster-bootstrap 95%
CI below zero; Memory/Storage/Bandwidth intervals do not establish uniform
improvement. The test split is not used to replace the validation-selected
model after observing this outcome.

## Temporal robustness

Eight causal rolling-origin refits use only earlier dates for training and the
immediately following date for early stopping before the next-date test. The
fixed LSTM beats persistence in 26/32 resource/fold RMSE cells; ARIMA beats it
in 23/32. The folds share an underlying trace and are not represented as eight
independent datasets.

## Runtime-assurance result

Adaptive predictive-only RT-DASH has held-out high-criticality DMR 0.000000 vs
0.032169 for load-only RT-DASH. Semantic RT-DASH also has DMR 0. Under the safe
recovery policy all seven frozen prediction faults retain mean high DMR 0.
Blackout exactly reproduces deterministic recovery on high DMR, low-work linear
utility and Critical-Mode fraction. Stuck-high raises mean Critical-Mode
fraction by 0.364706, so prediction faults are not cost-free.

## Limitations

- Synthetic resource annotations, not physical measurements.
- One source trace/site and only three primary held-out dates.
- No hardware timing, energy, WCET, FreeRTOS-board, or certification evidence.
- Forecasting superiority is resource-dependent and nonstationarity is visible.
- The safety result is empirical for the executed simulation matrix, not a
  universal schedulability theorem.
