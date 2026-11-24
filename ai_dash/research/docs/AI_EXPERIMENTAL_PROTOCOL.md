# AI-RT-DASH Experimental Protocol

> This protocol governs the **raw-sensor critical-state AI branch**. The
> corrected thesis ARIMA/LSTM resource-forecasting branch is governed by
> `ARIMA_LSTM_THESIS_PROTOCOL_FROZEN_2026-08-06.md`.

## Research question

Can a causal model inferred from raw smart-home device states provide useful
critical-state triggers without weakening the deterministic event/load safety
path of RT-DASH?

## Confirmatory hypotheses

- **AI-H1:** An AI-only trigger reduces high-criticality deadline misses or
  response time relative to load-only RT-DASH in stressed trace-derived cells.
- **AI-H2:** A safe hybrid that retains semantic-event and utilization triggers
  is no worse than deterministic recovery-aware RT-DASH on high-criticality
  deadline outcomes.
- **AI-H3:** Sensor-channel outage causes a measurable, monotone degradation in
  discrimination and is therefore an explicit operational risk.

The 60-second future-anomaly label is exploratory because the source contains
only 13 contiguous anomaly episodes. It is not used for the principal claim.
The predeclared 60-second study is executed separately in
`results/ai_early_warning/`; its results cannot alter the locked current-state
model or scheduler thresholds.

## Data and leakage control

- Source: OpenSHS v3 (`10.17632/zgsw84b2ff.3`).
- Features: 29 raw device states, current and trailing-60-second device-state
  summaries, current/trailing transition counts, and cyclic time of day.
- Excluded: `Activity`, `Priority`, `CPU`, `Memory`, `Storage`, `Bandwidth`, and
  power. The resource columns are thesis-generated annotations, not measured
  inputs.
- Sampling: one source row per sequence every 10 seconds.
- Training: first eight source dates.
- Validation: next three source dates.
- Test: final three source dates.
- Purge: 300 seconds at split boundaries.
- Model and threshold selection: validation only. The manifest asserts
  `selection_uses_test=false`.

## Models

Fixed, predeclared candidates are time-only logistic regression, current-sensor
logistic regression, temporal logistic regression, histogram gradient boosting,
and extremely randomized trees. Selection minimizes a validation cost of
`5 × false-negative rate + false-positive rate`; size and name break ties.

The classifier threshold and the scheduling threshold are separate. The latter
is selected by validation-only end-to-end simulations using a safety-dominant
objective over three background periodic loads (0.30, 0.45, 0.60).

## Scheduler policies

1. EDF.
2. RT-DASH load-only (semantic trigger removed).
3. Semantic RT-DASH.
4. Semantic recovery-aware RT-DASH.
5. AI-only RT-DASH (for ablation, not deployment).
6. Safe AI RT-DASH (AI plus semantic/load guards).
7. Safe AI recovery-aware RT-DASH.

All AI signals are timestamped with `generated_at <= time`; violations are
rejected. The deployment-oriented hybrid never removes the deterministic
semantic or load trigger.

## End-to-end matrix

- 30 untouched trace blocks.
- Three modeled background periodic utilizations.
- Seven policies.
- 630 held-out scheduling simulations.
- 34 validation blocks used only for the scheduling-threshold decision.
- 10 candidate thresholds derived without test access.

Trace activities are mapped to the same documented task templates used by the
scheduler study. Execution budgets and deadlines are model assumptions, not
WCET measurements.

## Metrics and inference

Classification: AUROC, AUPRC, sensitivity, specificity, precision, F1, Brier
score, 10-bin ECE, episode recall, and within-episode detection delay.

Scheduling: criticality-specific deadline-miss ratio and response, low-service
completion/utility, Critical-Mode time, and transitions.

Paired comparisons use identical block/load cells. Confidence intervals resample
held-out dates as clusters. Wilcoxon tests are Holm-corrected. With only three
held-out date clusters, uncertainty is reported as a limitation, not concealed
by treating correlated blocks as independent.

## Robustness and portability

- Deterministic sensor-channel outage at 0%, 5%, 10%, and 20%, with ten channel
  selections for nonzero levels.
- Exhaustive leave-one-sensor-out held-out evaluation for all 29 channels.
- Post-lock validation/test date metrics plus standardized feature-distribution
  and risk-distribution shift relative to training.
- Standardized logistic coefficients and per-training-SD odds ratios for the
  selected model; these are associational model diagnostics, not causal effects.
- Validation-defined operating thresholds applied unchanged to held-out data.
- JSON and allocation-free C header export for the selected logistic model.
- Python/C inference parity test.
- C++17 portable-model class and unit test.
- A 25-trial, one-million-inference-per-trial host benchmark compiled with
  `-O3`; this is host software evidence only and is explicitly not MCU/WCET evidence.
- SHA-256 manifest for every archived AI output.

## Post-lock governance

The held-out dates have now been inspected. No new candidate model, feature,
threshold, or hyperparameter may be promoted to the principal claim on these
same dates. Future confirmatory AI improvements require a genuinely new
independent dataset/site or prospectively collected trace. Diagnostic analyses
may use the locked test only when labelled post-lock and when they cannot feed
back into selection.
