# AI-RT-DASH Post-Lock Governance — 5 August 2026

## Purpose

The chronological held-out dates have been evaluated and inspected. They are
therefore no longer a valid unseen test set for choosing a new principal model,
feature set, hyperparameter, classification threshold, or scheduler threshold.

## Frozen principal result

- model: `current_sensor_logistic`;
- classification threshold: `0.00020000396225545737`;
- scheduling threshold: `0.9998768125363638`;
- train/validation/test partition: first 8 / next 3 / final 3 dates;
- purge: 300 seconds;
- held-out integration matrix: 30 blocks × 3 loads × 7 policies = 630 runs.

The strongest-version additions reproduce these locked fields exactly.

## Allowed use of the existing test dates

Post-lock diagnostics may quantify failure modes, temporal shift,
interpretability, or robustness if they are explicitly labelled diagnostic and
cannot feed back into model/threshold selection. The per-date shift table,
leave-one-sensor-out analysis, and validation-defined operating curve follow
this rule.

The 60-second future-window experiment was already predeclared as exploratory
in the AI protocol. It is executed and reported separately; it does not replace
the principal current-state model.

The later ARIMA/LSTM thesis-completion branch is a **different prediction
target**: it forecasts the thesis-generated CPU/Memory/Storage/Bandwidth
simulation annotations rather than reselecting the raw-sensor anomaly model.
Its ARIMA order, LSTM architecture, chronology, early-stopping rule and
scheduler-selection protocol were frozen separately before its forecasting
test was executed. It therefore does not alter this document's frozen
`current_sensor_logistic` model or thresholds.

The subsequent **advanced** ARIMA/LSTM study is different: its own protocol is
frozen before its new executions, but the thesis resource-test dates had
already been inspected in the locked ARIMA/LSTM branch. The advanced forecast
comparisons are therefore post-lock sensitivity/robustness evidence and cannot
be promoted as a second fresh confirmatory test. See
`ARIMA_LSTM_ADVANCED_POST_LOCK_GOVERNANCE_2026-08-06.md`.

## Requirement for a stronger future confirmatory claim

Any newly designed replacement for the **principal raw-sensor AI** architecture,
feature family, calibration method, or hyperparameter search requires an
independent confirmatory dataset/site or a prospectively collected trace.
Reusing the final three OpenSHS dates to choose an apparent better replacement
for that principal model would invalidate their held-out status.

## External-validation candidates

The CASAS official dataset catalogue lists both annotated scripted ADL data
with errors and a larger one-class activity-error dataset. Those are credible
future external-validation candidates:

- <https://casas.wsu.edu/datasets/>
- CASAS scripted activities with errors: <https://zenodo.org/records/15713378>

Their sensor/event schemas and labels differ from OpenSHS. No artificial
“anomaly” mapping is introduced in this project merely to manufacture a second
dataset result. A future cross-dataset study must define and justify the target
semantics before accessing the new test labels.
