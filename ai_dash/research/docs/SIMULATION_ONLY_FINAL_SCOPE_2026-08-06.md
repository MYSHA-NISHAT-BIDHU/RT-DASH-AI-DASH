# Final Simulation-Only Scope — 6 August 2026

## Hard boundary

This project uses no physical hardware. All scheduling performance values come
from executed software simulation. AI classification values come from executed
software inference on the declared OpenSHS partitions. The portable inference
benchmark is a measured host-software benchmark and is never described as MCU,
WCET, energy, or real-time guarantee evidence.

## What is complete inside this boundary

- deterministic single-core task/job/event simulator;
- EDF, RMS, criticality-EDF, RT-DASH variants, EDF-VD comparators and ablations;
- hysteretic mode control, semantic entry, overload entry and recovery;
- optional-service degradation and recovery-aware dispatch;
- true period stretching/shrinking comparator;
- explicit bounded synchronization/non-preemptive blocking stress;
- demand screen, quantum, overhead, jitter and safety-envelope studies;
- corrected thesis ARIMA(5,1,0), genuine multivariate LSTM, combined resource
  forecast and predictive RT-DASH integration;
- frozen advanced ARIMA/LSTM sensitivity study with EWMA/ridge-VAR baselines,
  validation-only convex blending, eight causal rolling-origin refits, predictor
  ablations and seven prediction-fault stress cases;
- leakage-controlled AI model/threshold selection and locked scheduler integration;
- early-warning exploratory AI study;
- per-date, leave-one-sensor, correlated-group and rolling-origin diagnostics;
- deterministic AI fail-safe fallback;
- portable C/C++ parity and host-software inference benchmark;
- automated tests, result verifiers, hashes and reproducibility manifests;
- separate Paper 1/Paper 2 claim/evidence maps.

## Claims that are prohibited

Do not convert simulation quantities into claims of measured WCET, physical
mode-switch latency, energy saving, memory footprint on an embedded target,
safety certification, hard schedulability, causal sensor importance, universal
scheduler dominance, or broad real-home anomaly generalization.

The ARIMA/LSTM resource targets are synthetic thesis simulation annotations;
their forecasting accuracy must never be described as measured device-resource
accuracy.

The advanced ARIMA/LSTM study reuses already-inspected locked test dates and is
post-lock sensitivity/robustness evidence, not a new independent confirmatory
test.

These are evidence-boundary statements, not unfinished hardware tasks.
