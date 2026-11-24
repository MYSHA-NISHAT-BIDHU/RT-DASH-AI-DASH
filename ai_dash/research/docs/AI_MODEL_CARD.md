# AI-RT-DASH Model Card

> This card describes the locked raw-sensor critical-state model. The corrected
> thesis ARIMA/LSTM predictor has its own
> `ARIMA_LSTM_MODEL_CARD_2026-08-06.md`.

## Selected model

Validation selected a class-weighted logistic regression using the 29 current
device states. The choice was made before test evaluation by minimizing
`5 × FNR + FPR`. Serialized research-model size is 2,222 bytes.

## Held-out performance

At the validation-selected classification threshold (`0.00020000396`):

- AUROC: 0.7487.
- AUPRC: 0.8323.
- sensitivity: 1.0000.
- specificity: 0.3429.
- precision: 0.7105.
- F1: 0.8308.
- Brier score: 0.3145.
- 10-bin ECE: 0.2719.
- episode recall: 1.0000 on the held-out episodes.

The low specificity and high calibration error show material chronological
shift. The model is not a verified safety component.

Post-lock date-level analysis shows why the aggregate result must not be used
alone. Test-date AUPRC ranges from 0.347701 (13 March) to 0.999976 (12 March),
while AUROC ranges from 0.408408 to 0.999937. On 14 March, anomaly prevalence is
0.996968, making AUPRC particularly prevalence-sensitive. These date-level
values are diagnostics only; they did not participate in selection.

## Scheduling threshold

Validation-only end-to-end selection chose `0.99987681254`, far above the
classification threshold. This is expected: the scheduling objective penalizes
unnecessary Critical-Mode residence and lost routine utility in addition to
false negatives.

At background load 0.45, AI-only mean high-criticality DMR was 0.001604 versus
0.002299 for load-only RT-DASH. At load 0.60, the values were 0.009141 and
0.012616. The pooled paired mean difference was −0.001390, but the three-date
cluster evidence was not significant after Holm correction (`p=0.2367`).

AI-only remained worse than the direct semantic trigger: pooled DMR was 0.003582
higher, and high-criticality response was 3.649 ms longer. The safe hybrid
exactly matched recovery-aware RT-DASH for the protected metrics in all 90
held-out block-load cells.

## Intended use

Advisory trigger in a runtime-assurance architecture where deterministic
semantic-event and utilization guards remain active.

## Prohibited use

- sole safety trigger;
- real-home deployment without new data and hardware validation;
- medical, fire, intrusion, or certification decisions;
- claims of formal safety, hard schedulability, causal prediction, or universal
  anomaly detection.

## Portability

The selected model is exported as JSON and an allocation-free C header. Python/C
inference parity is verified. On the recorded AMD EPYC 9V74 host, 25 trials of
1,000,000 inferences produced a measured median of 50.399 ns/inference
(5th–95th percentile across trial means: 49.919–52.244 ns). The compiled
benchmark executable was 21,136 bytes, with `size` reporting 8,561 text, 736
data, and 280 BSS bytes. These are host/compiler measurements only, not
Cortex-M timing, stack, energy, or WCET evidence.

## Sensor dependence

Leave-one-sensor-out analysis covers all 29 raw channels. Removing
`bathroomDoorLock` causes the largest held-out AUPRC decrease, from 0.832280 to
0.707716 (−0.124564), and raises the Brier score by 0.082128. This identifies a
model dependence that should be tested on independent homes; it is not a causal
claim about the physical sensor.

## Exploratory future-window model

The separately executed predeclared 60-second future-window analysis selects
`current_sensor_logistic` on validation only. On 20,670 held-out samples it
obtains AUROC 0.752432, AUPRC 0.834116, sensitivity 0.999922, specificity
0.355984, Brier 0.291120, and ECE 0.258345. Four of five held-out anomaly onsets
have an eligible pre-onset window; all four have a warning before onset, with a
median maximum observed lead of 60 seconds. Because the episode count is tiny
and specificity is low, this remains exploratory and is not promoted to the
principal safety claim.
