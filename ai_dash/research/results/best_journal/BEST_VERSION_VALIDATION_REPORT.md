# RT-DASH Best-Version Simulation Project Report

**Study scope:** software simulation only; no physical hardware evidence  
**Parameter selection:** separated training, validation, and held-out test partitions  
**Published external comparator:** EDF with Virtual Deadlines, including classical drop and degraded-quality runtime variants  

## 1. Redevelopment completed

The best-version project adds the remaining high-value scientific controls without tuning on the final test set:

1. a safety-dominant parameter-selection objective evaluated on seeds 0–9;
2. validation-based configuration selection on seeds 10–19;
3. a locked held-out comparison on seeds 20–29;
4. a recovery-aware RT-DASH variant that dispatches the low/medium recovery backlog by EDF only when no high-criticality work is pending;
5. nonlinear utility reporting under concave, linear, and convex service-value assumptions;
6. a demand-bound screening analysis for full and minimum-service workload demand;
7. release-jitter and execution-overhead robustness experiments;
8. an independent dual-criticality benchmark containing classical EDF-VD and degraded-quality EDF-VD semantics.

## 2. Selected configuration

```json
{
  "utilization_high": 0.9,
  "utilization_low": 0.8,
  "entry_hold": 200,
  "recovery_hold": 500,
  "observation_window": 1000,
  "smoothing_samples": 5
}
```

The configuration was selected from 36 candidates. The held-out test partition was not inspected during selection.

Top training candidates:

```
                 config_id  utilization_high  utilization_low  entry_hold  recovery_hold  observation_window  smoothing_samples    score  safety_dmr  high_response_norm  low_utility_loss  low_completion_loss  chatter_norm  recovery_wait_norm
uh0.90_ul0.80_eh200_rh2000               0.9              0.8         200           2000                1000                  5 0.162794    0.155754            0.225472          0.142160             0.264174         0.032              0.0351
 uh0.90_ul0.80_eh200_rh500               0.9              0.8         200            500                1000                  5 0.162943    0.155754            0.225472          0.141586             0.262521         0.040              0.0351
uh0.90_ul0.80_eh200_rh1000               0.9              0.8         200           1000                1000                  5 0.163058    0.155754            0.225472          0.141859             0.263266         0.040              0.0351
  uh0.90_ul0.80_eh0_rh2000               0.9              0.8           0           2000                1000                  5 0.163073    0.155754            0.225472          0.142867             0.265901         0.032              0.0351
   uh0.90_ul0.80_eh0_rh500               0.9              0.8           0            500                1000                  5 0.163222    0.155754            0.225472          0.142293             0.264248         0.040              0.0351
  uh0.90_ul0.80_eh0_rh1000               0.9              0.8           0           1000                1000                  5 0.163337    0.155754            0.225472          0.142566             0.264993         0.040              0.0351
```

Validation ranking of the six shortlisted candidates:

```
                 config_id  utilization_high  utilization_low  entry_hold  recovery_hold  observation_window  smoothing_samples    score  safety_dmr  high_response_norm  low_utility_loss  low_completion_loss  chatter_norm  recovery_wait_norm
 uh0.90_ul0.80_eh200_rh500               0.9              0.8         200            500                1000                  5 0.157355    0.153175             0.21548          0.134098             0.246193         0.040            0.034235
   uh0.90_ul0.80_eh0_rh500               0.9              0.8           0            500                1000                  5 0.157449    0.153175             0.21548          0.134313             0.246833         0.040            0.034192
uh0.90_ul0.80_eh200_rh1000               0.9              0.8         200           1000                1000                  5 0.157970    0.153175             0.21548          0.135524             0.250199         0.040            0.034235
  uh0.90_ul0.80_eh0_rh1000               0.9              0.8           0           1000                1000                  5 0.158064    0.153175             0.21548          0.135740             0.250839         0.040            0.034192
uh0.90_ul0.80_eh200_rh2000               0.9              0.8         200           2000                1000                  5 0.158375    0.153175             0.21548          0.137074             0.253933         0.036            0.034235
  uh0.90_ul0.80_eh0_rh2000               0.9              0.8           0           2000                1000                  5 0.158470    0.153175             0.21548          0.137290             0.254573         0.036            0.034192
```

## 3. Held-out emergency results

```
                            high_deadline_miss_ratio  high_mean_response  low_completion_rate  low_work_weighted_utility_linear
variant                                                                                                                        
criticality_edf                              0.15675           106.60278              0.76771                           0.90278
edf                                          0.62722           250.59259              0.99736                           0.99847
rms                                          0.91667           274.90000              0.85790                           0.97314
rt_dash_default                              0.15675           106.60278              0.78712                           0.90958
rt_dash_recovery_edf_tuned                   0.15675           106.60278              0.99307                           0.99413
rt_dash_tuned                                0.15675           106.60278              0.82095                           0.92059
```

## 4. Recovery-backlog results

```
                            low_completion_rate  low_p95_wait  low_work_weighted_utility_linear
variant                                                                                        
criticality_edf                         0.72540      70.80000                           0.85006
edf                                     0.94934      64.60000                           0.95703
rms                                     0.83363      60.00000                           0.93137
rt_dash_default                         0.74955      70.80000                           0.85314
rt_dash_recovery_edf_tuned              0.96623      64.60000                           0.95498
rt_dash_tuned                           0.76837      69.77000                           0.86302
```

## 5. Paired held-out comparisons

```
                      left           right                           metric  n_pairs  mean_difference  ci95_low  ci95_high  wilcoxon_p
             rt_dash_tuned rt_dash_default         high_deadline_miss_ratio       30         0.000000  0.000000   0.000000    1.000000
             rt_dash_tuned rt_dash_default low_work_weighted_utility_linear       70         0.008311  0.005806   0.011033    0.000000
rt_dash_recovery_edf_tuned   rt_dash_tuned              low_completion_rate       70         0.228856  0.190703   0.268798    0.000000
rt_dash_recovery_edf_tuned   rt_dash_tuned                     low_p95_wait       70        -0.978571 -1.960036   0.005036    0.174028
rt_dash_recovery_edf_tuned   rt_dash_tuned         high_deadline_miss_ratio       30         0.000000  0.000000   0.000000    1.000000
rt_dash_recovery_edf_tuned criticality_edf low_work_weighted_utility_linear       70         0.125913  0.109692   0.142637    0.000000
rt_dash_recovery_edf_tuned             edf         high_deadline_miss_ratio       30        -0.470476 -0.579923  -0.361111    0.000005
rt_dash_recovery_edf_tuned             rms         high_deadline_miss_ratio       30        -0.759921 -0.856746  -0.653175    0.000001
```

## 6. Demand-bound screening

The screen combines constrained-deadline periodic demand-bound functions with finite event-job demand over a dense set of interval lengths and event-aligned starts. It is a diagnostic screen, not a universal schedulability proof.

```
                         full_screened_feasible  minimum_service_screened_feasible  max_full_demand_ratio  max_minimum_service_demand_ratio
scenario                                                                                                                                   
emergency_mild                          0.70000                            1.00000                0.96808                           0.67544
emergency_moderate                      0.00000                            0.10000                1.37659                           1.05290
emergency_severe                        0.00000                            0.00000                2.36344                           1.98541
optional_service_stress                 0.00000                            0.50000                2.48765                           0.98741
overload                                0.10000                            1.00000                1.00490                           0.60715
recovery_backlog                        0.00000                            0.50000                1.48164                           1.00964
threshold_chatter                       0.00000                            1.00000                1.16200                           0.85875
```

## 7. Execution-overhead and release-jitter robustness

```
                                                        high_deadline_miss_ratio  low_work_weighted_utility_linear
variant                    execution_overhead_fraction                                                            
criticality_edf            0.00                                          0.00000                           0.91076
                           0.05                                          0.00000                           0.87392
                           0.10                                          0.00000                           0.84015
                           0.20                                          0.00000                           0.73334
edf                        0.00                                          0.72528                           0.97762
                           0.05                                          0.82361                           0.97538
                           0.10                                          0.91778                           0.97125
                           0.20                                          0.99722                           0.90390
rt_dash_recovery_edf_tuned 0.00                                          0.00000                           0.97452
                           0.05                                          0.00000                           0.97223
                           0.10                                          0.00000                           0.96779
                           0.20                                          0.00000                           0.89975
rt_dash_tuned              0.00                                          0.00000                           0.92303
                           0.05                                          0.00000                           0.88351
                           0.10                                          0.00000                           0.84358
                           0.20                                          0.00000                           0.73732
```

## 8. External EDF-VD benchmark

The external benchmark is deliberately separate from the smart-home event study. It uses implicit-deadline dual-criticality task sets, high-task LO/HI execution budgets, overrun-triggered mode changes, virtual deadlines in LO mode, and low-criticality drop or degraded service in HI mode. This avoids falsely labelling RT-DASH's semantic event trigger as the EDF-VD overrun mechanism.

```
                 high_dmr  high_mean_response  low_completion_rate  low_service_fraction
policy                                                                                  
criticality_edf   0.00000             9.87735              0.95655               0.96129
edf               0.01602            38.87287              0.98775               0.98696
edf_vd_drop       0.00000            12.95291              0.64365               0.56106
edf_vd_imc        0.00012            14.38895              0.87485               0.64766
rt_dash_mc        0.00000            14.01926              0.87087               0.66068
```

The EDF-VD comparator is based on the runtime model described by Liu et al., *EDF-VD Scheduling of Mixed-Criticality Systems with Degraded Quality Guarantees*, RTSS 2016, DOI 10.1109/RTSS.2016.013. The project does not claim that empirical execution of an arbitrary generated task set establishes the paper's sufficient schedulability condition.

## 9. Interpretation

- Results are stronger because tuning and final evaluation are separated.
- The recovery-aware variant is accepted only if held-out data show no deterioration in high-criticality deadline outcomes.
- Utility conclusions are tested under three plausible service-value shapes rather than one linear assumption.
- Demand-screen classifications explain when failures reflect intrinsic processor demand rather than a poor priority rule.
- EDF-VD provides an external mixed-criticality reference, but its overrun semantics differ from smart-home semantic-event triggering; both differences and similarities are reported.
- No result is selected or suppressed because it is unfavourable.

## 10. Remaining evidence boundary

The project remains a single-core simulation study. It does not establish physical timing, measured WCET, energy savings, safety certification, or universal dominance over every mixed-criticality method. The FreeRTOS files retained from the original archive are not used as a result generator because the supplied PC port does not implement a functioning host context-switch mechanism.
