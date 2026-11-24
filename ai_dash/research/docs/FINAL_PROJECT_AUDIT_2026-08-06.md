# RT-DASH Final Project Audit — 6 August 2026

## Verdict

Within the declared **simulation/software-only** scope, the project is complete
as a reproducible research artifact and materially stronger than the thesis-era
implementation. It is suitable as the computational basis of the two separated
papers. “Complete” does not mean that journal acceptance or universal
superiority is guaranteed; those are not scientific claims a repository can
prove.

## Executed evidence inventory

| Evidence block | Executed count/result |
|---|---:|
| principal + robustness deterministic scheduler simulations | 15,780 |
| additive thesis-completion/stress simulations | 2,340 |
| locked AI/scheduler simulations | 630 |
| ARIMA+LSTM validation/test scheduler simulations | 1,686 |
| advanced ARIMA+LSTM validation/ablation/fault simulations | 5,724 |
| total scheduler simulations represented in final package | 26,160 |
| independent C++ policy executions | 5 |
| Python tests | 48 passed |
| principal AI samples after split/purge | 104,750 |
| principal held-out AI samples | 20,670 |
| post-lock rolling-origin folds | 9 × 4 model families |
| exhaustive single-sensor removal cases | 29 |
| correlated room/sensor-group failures | 7 |
| host inference benchmark | 25 × 1,000,000 calls |
| ARIMA+LSTM forecast examples | 11,033 train / 4,320 validation / 4,043 test |
| advanced ARIMA+LSTM rolling-origin folds | 8 |
| frozen prediction-fault cases | 7 |

All completion-study, AI-generalization and ARIMA/LSTM outputs have their own
SHA-256 manifests and independent verification scripts.

## Query 1 — is everything from the original thesis introduced?

Scientifically defensible thesis mechanisms are now covered. The previously
missing period stretch/shrink behavior and a concrete synchronization/blocking
term are executable and tested. The full mapping is in
`THESIS_TO_FINAL_PROJECT_TRACEABILITY_2026-08-06.md`.

The thesis's named ARIMA and LSTM mechanisms are now implemented directly under
a corrected chronological protocol. ARIMA(5,1,0) forecasts the thesis CPU
series; the LSTM forecasts the multivariate resource series; the thesis hybrid
uses ARIMA CPU plus LSTM Memory/Storage/Bandwidth and drives predictive RT-DASH.
The source resource columns remain explicitly synthetic simulation annotations,
so the project does not relabel them as measured hardware resources. The
five-level historical field remains normalized to three defined consequence
classes, and FreeRTOS/Simulink-era files remain provenance rather than result
generators.

## Query 2 — are these the best results, and what are they?

“Best” is defined as the strongest result reachable without test leakage or
fabricated data, not the largest number obtainable by retuning after inspection.

### Deterministic Paper 1 headline

Across the locked 30-seed optimized matrix, recovery-aware RT-DASH changes mean
high-criticality DMR by **0.000000** versus tuned RT-DASH while increasing mean
low-criticality completion by **0.1875** and linear work-weighted utility by
**0.097842**. In emergency cells the gains are **0.1805** and **0.0864** with
high-criticality DMR again unchanged.

### New thesis-completion result

The fresh held-out period-control comparison has identical mean high DMR
(**0.162302**) and high response (**136.594 ms**) to recovery-aware RT-DASH.
Its mean nominal low-service fraction rises from **1.000000** to **1.020082**,
but mean transitions rise from **2.50** to **14.35**. This is evidence that the
mechanism works but is not a better principal controller.

At 10 ms bounded non-preemptive blocking, recovery-aware RT-DASH's mean high
response rises from **169.229 ms** to **175.697 ms** in the adversarial blocking
study; mean high DMR rises from **0.243452** to **0.270238**. The failure-envelope
surface deliberately retains overload and severe-emergency failures instead of
filtering them out.

### AI Paper 2 principal result

The corrected thesis ARIMA+LSTM branch evaluates 4,043 chronological test
forecasts. ARIMA CPU RMSE is **2.499591** versus **2.516280** for persistence;
LSTM Memory RMSE is **14.262286** versus **15.469165**. The hybrid's Bandwidth
RMSE is **0.973536**, worse than persistence **0.835214**, and remains reported.
Validation selected predictive pressure threshold **0.809598008**. Across 714
test scheduler runs, predictive-only RT-DASH has mean high-criticality DMR
**0.000000** versus **0.032169** for load-only RT-DASH. It matches semantic
RT-DASH DMR but has a paired mean high-criticality response penalty of
**0.372825 ms**. The safe recovery hybrid exactly matches deterministic
recovery-aware RT-DASH on protected DMR, low utility and Critical-Mode fraction.

The separately frozen advanced study is deliberately governed as **post-lock
sensitivity evidence** because those three test dates had already been
inspected in the thesis branch. It selects a 32-unit LSTM and validation-only
convex ARIMA/LSTM weights. On the same locked dates adaptive CPU RMSE improves
to **2.413298**, but Memory/Storage/Bandwidth RMSE are
**14.823566/3.183144/0.844892**, so it does not uniformly beat the thesis hybrid
or persistence. Eight causal rolling-origin refits add temporal robustness.
Adaptive predictive-only RT-DASH again reaches high DMR **0.000000** versus
0.032169 load-only. Across all seven frozen prediction-fault cases, safe
recovery has mean high DMR 0; blackout is exactly identical to deterministic
recovery on high DMR, low utility and Critical-Mode fraction. Stuck-high raises
Critical-Mode fraction by **0.364706**, retaining the false-positive cost.

The separate raw-sensor AI branch remains complementary evidence:

The locked current-sensor logistic model has held-out AUROC **0.748740** and
AUPRC **0.832280** on 20,670 samples. At the validation-selected threshold it
has sensitivity **1.000000**, specificity **0.342940**, Brier **0.314482** and
ECE10 **0.271896**. AI-only scheduling is directionally better than load-only
RT-DASH in the declared comparison but is not statistically established; the
safe hybrid exactly reproduces deterministic fallback behavior across all 90
protected held-out cells.

The new nine-fold rolling-origin diagnostic exposes, rather than hides,
nonstationarity. ExtraTrees is descriptively strongest/stablest among its four
fixed post-lock families (mean AUROC **0.876846**, minimum **0.578804**, zero
folds below 0.5), but it **does not replace** the locked principal model because
the principal test dates had already been inspected. Bathroom-group outage is
the largest correlated AUPRC loss (**−0.126146**).

## Query 3 — is it worthy of IEEE?

Yes as a **bounded simulation/AI systems study**, provided the manuscripts use
the claim matrices and do not imply physical validation, universal optimality,
or broad anomaly generalization. Paper 1 has a mature deterministic experiment,
state-of-the-art semantic comparator coverage, ablations and a fresh mechanism
completion study. Paper 2 has genuine leakage-controlled AI, end-to-end
scheduler integration, runtime assurance, failure analysis and explicit
post-lock governance.

The remaining weaknesses are publication risks rather than missing code:
single-source OpenSHS external validity, only 13 source-order anomaly episodes,
three principal held-out date clusters, reuse of those locked dates for the
advanced post-lock sensitivity study, and weak calibration/specificity. The
papers should feature these limitations openly. Acceptance cannot be guaranteed.

## Query 4 — is the project perfectly complete?

It is complete for the declared repository scope: no known simulation mechanism
from the defensible thesis core is left unaccounted for, the new studies are
executed, and every major evidence block is verifier-backed. It is not “perfect”
in the literal scientific sense; no finite study can remove external-validity
limits or prove universal superiority.

The correct final claim is therefore: **computationally complete,
reproducibility-complete, and publication-ready within a simulation-only claim
boundary**, with clearly documented external-validity limits.
