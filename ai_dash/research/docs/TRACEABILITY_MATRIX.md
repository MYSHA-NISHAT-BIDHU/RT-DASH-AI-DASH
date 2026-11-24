# Requirement-to-Evidence Traceability Matrix

| Research requirement | Implementation | Automated verification | Experimental evidence | Status |
|---|---|---|---|---|
| EDF ordering | `policies.py`, C++ `Scheduler.cpp` | policy/C++ tests | EDF baseline runs | Verified in reference model |
| RMS ordering | `policies.py`, C++ `Scheduler.cpp` | policy/C++ tests | RMS baseline runs | Verified in reference model |
| Immediate critical-event entry | `simulator.py`, C++ `ModeController` | event-between-samples test | transition log reason | Verified |
| Sustained-load entry | `simulator.py`, C++ `ModeController` | mode tests | controlled transition logs | Verified |
| Hysteretic recovery | `simulator.py`, C++ `ModeController` | recovery test | full vs no-hysteresis transitions | Verified in reference model |
| Criticality-first dispatch | policy selection functions | policy/C++ tests | high response/DMR under controlled conflict | Verified for declared workloads |
| Optional service reduction | `Job.apply_service_floor` | model/simulator/C++ tests | service-reduction and no-degradation ablation | Verified in reference model |
| High-critical work not degraded | model validation | invalid-model tests | configuration inspection | Verified |
| Thesis-style period stretching/shrinking | `simulator.py`, period-adaptive policies | simulator period-control test + completion verifier | fresh 30--59 tuning/held-out study | Verified in reference model; comparator result |
| Bounded synchronization/blocking term | `TaskSpec.blocking_time`, non-preemptive job section | model and simulator blocking tests | 480-run adversarial blocking matrix | Verified as declared stress abstraction |
| Correct deadline denominator | `metrics.py` | horizon-censoring test | assessed/censored result columns | Verified |
| Transactional resources | C++ `ResourceManager` | admission/release tests + sanitizers | not used as a kernel reservation experiment | Code verified; system effect unmeasured |
| OpenSHS activity provenance | trace mapper and audit script | deterministic mapping test | three contiguous windows | Verified data handling |
| Safety envelope across load/severity | completion-study generator | completion verifier | 600-run 0.50--1.10 × 3-severity surface | Verified for declared surface |
| Published mixed-criticality comparator | EDF-VD and degraded-quality EDF-VD | best-project verifier | 800-run external EDF-VD benchmark | Verified under documented model translation |
| Thesis ARIMA prediction | `forecasting.ARIMA510` | ARIMA trend test + thesis verifier | 11,033/4,320/4,043 chronological examples; ARIMA(5,1,0) | Verified for synthetic thesis resource series |
| Thesis LSTM prediction | `forecasting.NumpyLSTMRegressor` | learning + finite-difference BPTT gradient tests + thesis verifier | validation-only early stopping; held-out resource metrics | Verified for synthetic thesis resource series |
| Combined ARIMA/LSTM predictive scheduling | thesis hybrid pressure + predictive RT-DASH | thesis result verifier | 972 validation + 714 test scheduler simulations | Verified simulation integration |
| Advanced ARIMA/LSTM sensitivity | validation-selected convex blend + EWMA/ridge-VAR comparators | advanced ARIMA/LSTM verifier | 6 LSTM candidates + 8 causal rolling-origin folds | Verified post-lock robustness evidence |
| Predictive runtime assurance under faults | safe recovery policy + frozen pressure-fault transforms | advanced ARIMA/LSTM verifier | 7 fault cases × 102 held-out cells; 714 runs | Verified for declared fault matrix |
| AI inference from raw smart-home states | `ai.py`, AI study | AI verifier + parity | locked 8/3/3 chronology and 20,670-sample test | Verified with stated generalization limits |
| AI rolling temporal robustness | fixed four-family rolling-origin study | AI-generalization verifier | 9 prospective-style folds | Verified post-lock diagnostic |
| Correlated sensor-group failure | exact serialized principal model + outage transform | AI-generalization verifier | 7 room/group outages | Verified post-lock diagnostic |
| Hardware FreeRTOS timing | deliberately not used | none | none | Out of declared project scope |
| Energy optimization | not implemented/measured | none | none | Out of declared project scope |
