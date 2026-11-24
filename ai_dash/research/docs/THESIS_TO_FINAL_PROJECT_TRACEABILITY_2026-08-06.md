# Thesis-to-Final-Project Traceability — 6 August 2026

## Purpose

This is the authoritative reconciliation between the thesis-era design and the
final simulation-only research project. “Covered” means executable and backed
by tests/results. “Corrected” means the thesis mechanism is now implemented
under a leakage-controlled protocol even though the supplied thesis-era code
did not validate it.

| Thesis-era concept | Final treatment | Evidence/status |
|---|---|---|
| Normal/Critical dual-mode scheduler | Covered | explicit mode controller and transition log |
| EDF normal dispatch | Covered | Python + independent C++ tests/results |
| criticality-first emergency dispatch | Covered | Python + C++ tests, conflict workloads |
| RMS comparison | Covered | baseline policy and executed comparisons |
| load-triggered mode entry | Covered | smoothed utilization + sustained entry hold |
| semantic/critical-event entry | Covered | immediate event entry independent of monitor sampling |
| hysteretic return to normal | Covered | separate entry/recovery thresholds and holds |
| state preservation/preemption | Covered | job remaining work, preemption and recovery backlog |
| dynamic service/task shrinking | Covered and strengthened | declared degradable service floors; high-criticality work cannot be reduced |
| period stretching in Critical Mode | Covered in additive study | true online release rescheduling; validation-selected stretch factor |
| period shrinking during recovery | Covered in additive study | validation-selected shrink factor/window; fresh held-out seeds 50--59 |
| synchronization/barrier term `beta` | Covered as bounded abstraction | `blocking_time` initial non-preemptive section + 480-run stress matrix |
| task tuple C/D/P/criticality | Covered | immutable `TaskSpec`, releases/jobs/deadlines |
| thesis five-level `L` field | Normalized | three consequence classes LOW/MEDIUM/HIGH; no false five-level semantics are claimed |
| resource annotations | Covered as metadata/transactional C++ code | memory/bandwidth annotations are not presented as kernel reservation measurements |
| performance assessor | Covered | right-censored DMR, response, completion, service/utility, transitions, critical-mode fraction |
| demand feasibility analysis | Strengthened | demand-bound screening plus explicit failure-envelope simulation |
| overload/robustness evaluation | Strengthened | quantum, overhead, jitter, load 0.50--1.10, severity, and bounded blocking studies |
| smart-home dataset use | Covered and audited | OpenSHS source provenance, causal preprocessing, duplicate/gap audit |
| ARIMA resource prediction | Corrected and covered | real ARIMA(5,1,0), 11,033/4,320/4,043 chronological forecast examples, persistence baseline |
| LSTM nonlinear resource prediction | Corrected and covered | genuine 4-input/16-hidden/4-output LSTM, BPTT+Adam, validation-only early stopping |
| combined ARIMA/LSTM prediction | Corrected and covered | ARIMA CPU + LSTM Memory/Storage/Bandwidth; train-distribution pressure score feeds predictive RT-DASH |
| ARIMA/LSTM robustness and fault behavior | Strengthened | validation-only blend/tuning, EWMA/ridge-VAR baselines, 8 causal refit folds, predictor ablation and 7 prediction-fault cases |
| learned predictive/advisory capability | Covered and strengthened | thesis ARIMA/LSTM branch plus five leakage-controlled sensor-state candidates, chronological selection, early-warning exploratory study |
| AI failure handling | New strengthening | deterministic runtime-assurance fallback, single-sensor and correlated-group outage studies |
| AI temporal validation | New strengthening | per-date shift audit plus nine post-lock rolling-origin folds |
| FreeRTOS source integration | Preserved for provenance, not result generator | historical PC port is not used to manufacture timing evidence |
| independent portable implementation | Strengthened | C++17 scheduler parity and compact C logistic inference parity |
| Simulink documentation | Legacy only | no executable `.slx`/`.mdl` artifact was supplied; Python is the authoritative simulator |
| physical timing/WCET | Excluded by final scope | no hardware is used and no physical timing is claimed |
| energy result | Excluded by final scope | no simulated annotation is relabeled as measured energy |

## Corrected ARIMA/LSTM implementation

The historical resource columns (`CPU`, memory, storage, bandwidth and power)
are generated annotations rather than measured physical resource demand. They
are therefore used only as a **thesis-faithful simulation forecasting target**,
with that provenance stated in every report. The final implementation uses
ARIMA(5,1,0) on first differences and a genuinely trained multivariate LSTM,
with first 8 dates for training, next 3 for validation and final 3 for test.
Scaling, LSTM early stopping and scheduler-threshold selection never use test.

The hybrid follows the thesis intent: ARIMA supplies CPU forecasting while LSTM
supplies Memory/Storage/Bandwidth. On held-out dates ARIMA CPU RMSE is 2.499591
versus 2.516280 for persistence; LSTM Memory RMSE is 14.262286 versus 15.469165.
The LSTM/hybrid Bandwidth RMSE is 0.973536, worse than persistence 0.835214;
this negative result is retained. The combined predictor is then evaluated in
1,686 validation/test scheduler simulations. The old C++ `PredictiveModel`
remains provenance; the new validated implementation is `rt_dash/forecasting.py`.

A separately frozen advanced study adds validation-only convex ARIMA/LSTM
blending, stronger forecasting baselines, eight causal rolling-origin refits
and seven prediction-fault cases without deleting the thesis hybrid. Because
the locked thesis-test dates had already been inspected before this advanced
study was designed, its results are explicitly post-lock sensitivity evidence,
not a new confirmatory test. The advanced model improves CPU RMSE to 2.413298
but does not uniformly improve Memory/Storage/Bandwidth, so it does not replace
the thesis hybrid post hoc.

## Period-control finding

The period mechanism is no longer missing. Using new train seeds 30--39,
validation seeds 40--49 and untouched test seeds 50--59, the selected
`1.5×` Critical-Mode stretch, `0.5×` recovery shrink and 1000 ms recovery window
has the same held-out mean high-criticality DMR and response time as
recovery-aware RT-DASH. It increases mean nominal low-service fraction by
0.020082 (95% seed-cluster bootstrap interval 0.014476--0.025474; Holm-adjusted
p=0.006157), but also increases mean mode transitions from 2.50 to 14.35 and
Critical-Mode fraction from 0.5096 to 0.5392. It is therefore a completed
mechanism and useful ablation, not a basis for replacing the principal policy.

## Final answer to “is everything from the thesis included?”

Every thesis concept that can be supported honestly within a software-only
simulation project is now executable or explicitly mapped. This includes the
named ARIMA, LSTM, combined predictive path, period adaptation and bounded
synchronization abstraction. Historical code defects remain documented instead
of being mistaken for the corrected implementation.
