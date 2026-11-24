# Two-Paper Scope, Novelty, and Claim Boundary

## Paper 1 — deterministic scheduler

**Working title:** *RT-DASH: Workload- and Event-Adaptive Dual-Mode Scheduling
with Recovery-Aware Service Control for Smart-Home Controllers*

**Contribution:** application-specific integration of semantic-event and load
triggers, hysteresis, controlled optional-service reduction, and recovery-aware
backlog scheduling in a reproducible single-core model.

**Evidence:** 15,780 principal/robustness Python simulations plus 2,340 additive
thesis-completion/stress simulations, five C++ host-policy runs, 48 current
Python tests spanning deterministic and AI/integration code, demand screening,
ablations, EDF-VD, overhead/jitter, true period adaptation, bounded blocking,
load/severity envelope, and C++ host-core build evidence.

**Central result:** recovery-aware RT-DASH preserved tuned RT-DASH's
high-criticality DMR while increasing low-criticality completion by 0.1875 and
linear work-weighted utility by 0.0978 over the 30-seed full matrix.

**Must not claim:** AI scheduling, new schedulability theorem, physical timing,
measured WCET/energy, certification, or universal superiority.

## Paper 2 — thesis-faithful prediction with runtime assurance

**Working title:** *Predictive RT-DASH: Leakage-Controlled ARIMA–LSTM Resource
Forecasting with Deterministic Runtime Assurance for Mixed-Criticality Smart Homes*

**Contribution:** a corrected implementation of the thesis-proposed
ARIMA/LSTM predictive path, chronological resource forecasting, combined
forecast-to-scheduler integration and deterministic fail-safe guards. The
separate raw-sensor ML pipeline adds leakage-controlled critical-state
inference, failure/generalization audits and portable inference evidence.

**Evidence:** ARIMA(5,1,0), a genuine multivariate LSTM, persistence baseline,
11,033/4,320/4,043 chronological train/validation/test forecast examples, 972
validation scheduler runs and 714 test scheduler runs. A separately frozen
advanced study adds 5,724 scheduler simulations, six validation-only LSTM
candidates, EWMA/ridge-VAR comparators, convex ARIMA/LSTM blending, eight causal
rolling-origin forecast folds, four predictor ablations and seven prediction-
fault cases. The repository now has 48 Python tests. Complementary evidence
adds 104,750 partitioned raw-sensor ML samples, five candidate models, 630 locked
test simulations, 90 safe-hybrid/fallback comparison cells, outage stress tests,
and C/Python parity. Post-lock evidence adds six date-level temporal
generalization rows, 29 leave-one-sensor-out diagnostics, a validation-locked
operating curve, standardized logistic coefficients, a predeclared exploratory
60-second future-window study, a 25-trial host-only portable-inference
benchmark, nine prospective-style rolling-origin folds across four fixed model
families, and seven correlated room/sensor-group outage cases.

**Central bounded result:** the thesis ARIMA/LSTM hybrid predictor reduces the
evaluated predictive-only high-criticality DMR to 0.000000 from 0.032169 for
load-only RT-DASH, while semantic RT-DASH also reaches 0 and is 0.372825 ms
faster in paired high-criticality response. The safe recovery hybrid exactly
reproduces deterministic recovery-aware results on protected metrics. ARIMA
CPU RMSE is 2.499591 vs 2.516280 persistence; LSTM Memory RMSE is 14.262286 vs
15.469165 persistence. The LSTM/hybrid Bandwidth result is worse than
persistence and must remain visible.

The advanced validation-selected ARIMA/LSTM model improves CPU RMSE to
**2.413298** but is not uniformly superior: Memory/Storage/Bandwidth RMSE are
14.823566/3.183144/0.844892, while the locked thesis hybrid is better for
Memory/Storage and persistence is slightly better for Bandwidth. This is a
pre-frozen generalization result and must not be post-hoc retuned. Its
predictive-only scheduler still obtains high-criticality DMR **0.000000** versus
0.032169 load-only, and the seven-case safe-recovery fault study retains mean
high DMR 0 throughout. Blackout exactly reproduces deterministic recovery on
high DMR, low utility and Critical-Mode fraction; stuck-high raises Critical-
Mode fraction by 0.364706 and exposes false-positive mode-residency cost.

The thesis resource columns are generated simulation annotations. Forecast
metrics establish the corrected thesis mechanism, not physical resource-demand
prediction.

The post-lock temporal audit deliberately exposes nonstationarity: held-out
per-day AUROC ranges from 0.4084 to 0.9999. Removing `bathroomDoorLock` reduces
held-out AUROC from 0.7487 to 0.6069, identifying a strong observed feature
dependence rather than a causal effect. The separate 60-second future-window
study reaches held-out AUROC 0.7524 and warns before all four eligible held-out
onset episodes, but four episodes are too few for a broad early-warning claim.
The portable header measured a median 50.399 ns/inference across 25 one-million-
inference trials on the recorded AMD EPYC host; this is explicitly not a
microcontroller, WCET, or energy measurement.

## Novelty audit

The AI paper cannot claim the first predictive mixed-criticality mode switch.
Massaro et al. proposed proactive mode changes using prediction in 2018
(`10.5555/3330299.3330301`), and Saberikia et al. published learner-based
resource management for mixed-criticality systems in 2025
(`10.1049/cps2.70007`). EDF-VD with degraded-quality guarantees is also
established (`10.1109/RTSS.2016.013`).

The defensible distinction is the combination of:

1. a thesis-faithful ARIMA/LSTM resource-forecast path corrected for temporal leakage, plus a frozen validation-selected convex ARIMA/LSTM sensitivity model;
2. raw smart-home device-state inference as a complementary learned signal;
3. explicit runtime-assurance separation between prediction/ML and deterministic
   RT-DASH guards;
4. chronological split, purge, calibration, outage, and duplicate-label audits;
5. end-to-end matched scheduling evaluation at three background loads; and
6. portable trained-model parity plus the original reproducible scheduler core.

Post-lock diagnostics strengthen the evaluation of those contributions but do
not change the locked principal model, classification threshold, or scheduling
threshold. The rolling-origin table may describe ExtraTrees as the most stable
of the four fixed families on those nine diagnostic folds, but it must not be
used to replace the locked principal logistic model. Any future model selection
after inspecting the current test dates requires a new untouched evaluation
partition or external dataset.

Use “integrates,” “evaluates,” and “provides an application-specific safe
hybrid.” Do not use “first,” “unprecedented,” “guarantees safety,” or “proves
schedulability.”

## Avoiding self-plagiarism and salami slicing

- Paper 2 must cite Paper 1/preprint and state which scheduler components are
  reused.
- Repeated simulator and workload text should be summarized and cited, not
  copied.
- Paper 2's hypotheses, figures, tables, primary results, and discussion must be
  the AI experiment above, not a second presentation of the 15,780-run matrix.
- Do not submit overlapping manuscripts simultaneously without transparent
  disclosure to both editors.
