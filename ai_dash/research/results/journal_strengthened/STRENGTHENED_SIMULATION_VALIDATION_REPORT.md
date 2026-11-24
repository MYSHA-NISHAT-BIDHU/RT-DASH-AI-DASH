# RT-DASH Strengthened Simulation Validation Report

**Executed:** 2026-07-08T07:02:23.002951+00:00  
**Study type:** simulation only  
**Controlled runs:** 7560  
**Sensitivity runs:** 880  
**Scalability runs:** 450  
**Trace-mapping runs:** 90  
**Total executed simulations:** 8980  
**Seeds in principal controlled study:** 30 (0–29)  
**Duration/quantum:** 60000 ms / 10 ms

## Major redevelopment completed

- Corrected startup utilization estimation by zero-filling the observation window.
- Made each scheduling quantum work-conserving; residual time after job completion is no longer discarded.
- Added event-trigger, load-trigger, recovery-hold, hysteresis and degradation ablations.
- Replaced ceiling-dominated emergency tests with mild, moderate and severe demand regions.
- Added 30-seed paired experiments, bootstrap confidence intervals, effect sizes and Holm-adjusted tests.
- Added parameter sensitivity, task-count scalability, recovery/queue metrics and trace-to-task mapping robustness.
- Retained a static criticality-first baseline to separate criticality-first dispatch from adaptive mode control.

## Principal emergency-scenario means

```
                          high_deadline_miss_ratio  high_mean_response  low_completion_rate  low_delivered_service_fraction
policy                                                                                                                     
criticality_edf                            0.12700           100.03710              0.72674                         0.87429
edf                                        0.57195           252.00363              0.96085                         0.98340
rms                                        0.86997           212.72802              0.80269                         0.95285
rt_dash                                    0.12700           100.03710              0.74257                         0.87995
rt_dash_no_degradation                     0.12700           100.03710              0.74257                         0.87995
rt_dash_no_event_trigger                   0.22788           140.73037              0.75531                         0.88440
rt_dash_no_hysteresis                      0.12700           100.03710              0.79664                         0.90040
rt_dash_no_load_trigger                    0.12700           100.03710              0.78359                         0.89899
rt_dash_no_recovery_hold                   0.12700           100.03710              0.74259                         0.87996
```

## Threshold-chatter mean transitions

```
policy
criticality_edf             0.000
edf                         0.000
rms                         0.000
rt_dash                     1.000
rt_dash_no_degradation      1.000
rt_dash_no_event_trigger    1.000
rt_dash_no_hysteresis      45.700
rt_dash_no_load_trigger     0.000
rt_dash_no_recovery_hold    1.000
```

## Controlled run balance

`{'criticality_edf': 840, 'edf': 840, 'rms': 840, 'rt_dash': 840, 'rt_dash_no_degradation': 840, 'rt_dash_no_event_trigger': 840, 'rt_dash_no_hysteresis': 840, 'rt_dash_no_load_trigger': 840, 'rt_dash_no_recovery_hold': 840}`

## Scientific interpretation

1. Criticality-first dispatch is the primary mechanism protecting high-criticality jobs.
2. RT-DASH's incremental contribution is adaptive activation, load/event trigger integration, hysteretic recovery and controlled optional-service reduction.
3. Performance is now evaluated across graded demand regions rather than only extreme baseline failure.
4. Completion and delivered service are reported together, preventing degraded completions from being mistaken for full-quality service.
5. Trace-derived conclusions are tested under relaxed, nominal and stressed mapping assumptions.
6. Results remain bounded to the declared single-core simulation model and do not imply hard schedulability or physical-device timing.

## Authoritative result files

- `controlled_runs_v2.csv`
- `mode_transitions_v2.csv`
- `parameter_sensitivity.csv`
- `scalability_study.csv`
- `trace_mapping_robustness.csv`
- `aggregate_controlled_v2.csv`
- `aggregate_sensitivity.csv`
- `aggregate_scalability.csv`
- `aggregate_trace_robustness.csv`
- `paired_comparisons_v2.csv`
- `figures/`
- `execution_manifest_v2.json`
- `sha256sums_v2.txt`
