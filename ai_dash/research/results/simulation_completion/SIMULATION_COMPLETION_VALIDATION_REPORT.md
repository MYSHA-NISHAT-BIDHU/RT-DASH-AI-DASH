# Simulation-Only Thesis Completion and Stress Report

## Scope and lock discipline

This additive study closes simulation-side mechanisms that were described in the
original thesis but were not part of the locked principal RT-DASH result. It does
not modify or replace the 15,780-run deterministic evidence or the locked AI
held-out test. Period-control parameters use new seeds 30--39 for training and
40--49 for validation; seeds 50--59 are held out until the final comparison.

No hardware, physical timing, WCET, or energy claim is made.

## Selected period-control configuration

```json
{
  "candidate_id": "s1.5_r0.50_w1000",
  "period_stretch_factor": 1.5,
  "period_shrink_factor": 0.5,
  "period_recovery_window_ms": 1000,
  "selection_rule": "minimum validation score: 100*high_DMR + capped_high_response/1000 + (1-capped_nominal_low_service)",
  "train_seeds": [
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,
    38,
    39
  ],
  "validation_seeds": [
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49
  ],
  "heldout_test_seeds": [
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59
  ],
  "test_used_for_selection": false
}
```

The safety-dominant selection score is declared in `selected_period_control.json`.
Completion rates are not allowed to hide reduced release frequency: all period
policies are additionally scored by executed low-criticality work divided by the
nominal work that the unadapted task set would have requested.

## Held-out period-control result

```
                             policy  n  high_dmr_mean  high_dmr_sd  high_response_ms_mean  high_response_ms_sd  low_nominal_service_fraction_mean  low_nominal_service_fraction_sd  low_actual_release_fraction_mean  low_actual_release_fraction_sd  critical_mode_fraction_mean  critical_mode_fraction_sd  mode_transitions_mean  mode_transitions_sd
        rt_dash_period_recovery_edf 60       0.162302     0.237453             136.594325            60.164833                           1.020082                         0.062006                          1.022238                        0.063856                     0.539222                   0.123193              14.350000             1.964300
rt_dash_period_service_recovery_edf 60       0.162302     0.237453             136.594325            60.164833                           1.020082                         0.062006                          1.022238                        0.063856                     0.539222                   0.123193              14.350000             1.964300
               rt_dash_recovery_edf 60       0.162302     0.237453             136.594325            60.164833                           1.000000                         0.000000                          1.000000                        0.000000                     0.509611                   0.362400               2.500000             1.512658
```

## Paired held-out comparisons

```
                               left                right                       metric  n_cells  n_seed_clusters  mean_difference  seed_cluster_bootstrap_ci95_low  seed_cluster_bootstrap_ci95_high  wilcoxon_p     holm_p
        rt_dash_period_recovery_edf rt_dash_recovery_edf                     high_dmr       60               10                0                                0                                 0           1          1
        rt_dash_period_recovery_edf rt_dash_recovery_edf             high_response_ms       60               10                0                                0                                 0           1          1
        rt_dash_period_recovery_edf rt_dash_recovery_edf low_nominal_service_fraction       60               10        0.0200823                        0.0144759                         0.0254743  0.00102609 0.00615651
rt_dash_period_service_recovery_edf rt_dash_recovery_edf                     high_dmr       60               10                0                                0                                 0           1          1
rt_dash_period_service_recovery_edf rt_dash_recovery_edf             high_response_ms       60               10                0                                0                                 0           1          1
rt_dash_period_service_recovery_edf rt_dash_recovery_edf low_nominal_service_fraction       60               10        0.0200823                        0.0144759                         0.0254743  0.00102609 0.00615651
```

## Synchronization/blocking robustness

The thesis's unspecified synchronization term is operationalized here as a
bounded initial non-preemptive section for low/medium periodic jobs. Mode entry
can still occur immediately, but a newly released high-criticality job may be
blocked until the running non-preemptive section ends. This is a stress model,
not a claim that it reconstructs an unavailable historical lock protocol.

```
              policy  blocking_ms  n  high_dmr_mean  high_dmr_sd  high_response_ms_mean  high_response_ms_sd  low_nominal_service_fraction_mean  low_nominal_service_fraction_sd  low_actual_release_fraction_mean  low_actual_release_fraction_sd  critical_mode_fraction_mean  critical_mode_fraction_sd  mode_transitions_mean  mode_transitions_sd
     criticality_edf            0 40       0.243452     0.255022             169.228988            46.482736                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
     criticality_edf            2 40       0.243452     0.255022             169.947679            46.447097                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
     criticality_edf            5 40       0.243452     0.255022             172.103750            46.345238                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
     criticality_edf           10 40       0.260417     0.274802             174.741310            46.253529                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                 edf            0 40       0.880565     0.154124             335.685893            32.526368                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                 edf            2 40       0.880565     0.154124             335.685893            32.526368                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                 edf            5 40       0.880565     0.154124             335.685893            32.526368                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                 edf           10 40       0.880565     0.154124             335.685893            32.526368                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
rt_dash_recovery_edf            0 40       0.243452     0.255022             169.228988            46.482736                           1.000000                         0.000000                          1.000000                        0.000000                     0.520460                   0.352514               2.500000             1.519109
rt_dash_recovery_edf            2 40       0.243452     0.255022             169.947679            46.447097                           1.000000                         0.000000                          1.000000                        0.000000                     0.520460                   0.352514               2.500000             1.519109
rt_dash_recovery_edf            5 40       0.243452     0.255022             172.103750            46.345238                           1.000000                         0.000000                          1.000000                        0.000000                     0.520460                   0.352514               2.500000             1.519109
rt_dash_recovery_edf           10 40       0.270238     0.289300             175.697202            46.192444                           1.000000                         0.000000                          1.000000                        0.000000                     0.520460                   0.352514               2.500000             1.519109
```

## Safety envelope

New held-out seeds are evaluated across nominal periodic utilization 0.50--1.10
and mild/moderate/severe emergency families. The surface is a failure-boundary
map; infeasible cells are retained rather than removed.

```
                             policy  target_utilization severity  n  high_dmr_mean  high_dmr_sd  high_response_ms_mean  high_response_ms_sd  low_nominal_service_fraction_mean  low_nominal_service_fraction_sd  low_actual_release_fraction_mean  low_actual_release_fraction_sd  critical_mode_fraction_mean  critical_mode_fraction_sd  mode_transitions_mean  mode_transitions_sd
                    criticality_edf            0.500000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.500000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.500000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.650000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.650000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.650000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.800000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.800000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.800000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.950000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.950000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            0.950000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            1.100000     mild 10       0.000000     0.000000              71.325000             9.131536                           0.841403                         0.010682                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            1.100000 moderate 10       0.000000     0.000000             127.130000            16.653450                           0.831398                         0.009949                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                    criticality_edf            1.100000   severe 10       0.486905     0.095930             211.327976            21.576841                           0.816607                         0.010056                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.500000     mild 10       0.000000     0.000000             179.733333            17.103254                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.500000 moderate 10       0.343333     0.148074             234.676667            16.361012                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.500000   severe 10       0.729762     0.054134             294.997619            24.221901                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.650000     mild 10       0.000000     0.000000             239.275000            22.760734                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.650000 moderate 10       0.490000     0.193601             276.570000            18.633083                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.650000   severe 10       0.870238     0.106509             321.289881            25.382888                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.800000     mild 10       0.283333     0.172133             304.333333            27.787665                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.800000 moderate 10       0.698333     0.119786             313.158333            19.556100                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.800000   severe 10       1.000000     0.000000             347.626190            26.695019                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.950000     mild 10       0.716667     0.201077             349.225000            30.915258                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.950000 moderate 10       1.000000     0.000000             349.293333            20.824664                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            0.950000   severe 10       1.000000     0.000000             373.748214            27.158163                           1.000000                         0.000000                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            1.100000     mild 10       1.000000     0.000000            1863.091667           155.530541                           0.903342                         0.006127                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            1.100000 moderate 10       1.000000     0.000000            1889.220000            78.614041                           0.897040                         0.005662                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
                                edf            1.100000   severe 10       1.000000     0.000000            1985.229167            64.765992                           0.887607                         0.005301                          1.000000                        0.000000                     0.000000                   0.000000               0.000000             0.000000
rt_dash_period_service_recovery_edf            0.500000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.049339                         0.001980                          1.049143                        0.001677                     0.043667                   0.002460               4.000000             0.000000
rt_dash_period_service_recovery_edf            0.500000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.045345                         0.001225                          1.045571                        0.001054                     0.050333                   0.002460               4.000000             0.000000
rt_dash_period_service_recovery_edf            0.500000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.043549                         0.004409                          1.043857                        0.004367                     0.063000                   0.012615               4.000000             0.000000
rt_dash_period_service_recovery_edf            0.650000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.160233                         0.002107                          1.164143                        0.001838                     0.341000                   0.002744              19.500000             0.527046
rt_dash_period_service_recovery_edf            0.650000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.157416                         0.001200                          1.161429                        0.002020                     0.342667                   0.001405              19.200000             0.421637
rt_dash_period_service_recovery_edf            0.650000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.135659                         0.018486                          1.140571                        0.016291                     0.371000                   0.017501              18.100000             0.316228
rt_dash_period_service_recovery_edf            0.800000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.059641                         0.009385                          1.064857                        0.005917                     0.455000                   0.007577              14.800000             0.421637
rt_dash_period_service_recovery_edf            0.800000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.041887                         0.012468                          1.049857                        0.013324                     0.469667                   0.011161              14.700000             0.483046
rt_dash_period_service_recovery_edf            0.800000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.022059                         0.011110                          1.031286                        0.010333                     0.485667                   0.008020              13.700000             1.159502
rt_dash_period_service_recovery_edf            0.950000     mild 10       0.000000     0.000000              71.325000             9.131536                           0.914871                         0.009806                          0.916143                        0.009807                     0.757667                   0.011764              13.400000             1.264911
rt_dash_period_service_recovery_edf            0.950000 moderate 10       0.000000     0.000000             127.130000            16.653450                           0.910687                         0.008118                          0.911857                        0.007680                     0.760000                   0.007698              12.800000             0.632456
rt_dash_period_service_recovery_edf            0.950000   severe 10       0.486905     0.095930             211.327976            21.576841                           0.905737                         0.008503                          0.912143                        0.006743                     0.759000                   0.005890              12.800000             0.632456
rt_dash_period_service_recovery_edf            1.100000     mild 10       0.000000     0.000000              71.325000             9.131536                           0.683470                         0.000019                          0.682857                        0.000000                     0.953333                   0.000000               1.000000             0.000000
rt_dash_period_service_recovery_edf            1.100000 moderate 10       0.000000     0.000000             127.130000            16.653450                           0.683470                         0.000019                          0.682857                        0.000000                     0.953333                   0.000000               1.000000             0.000000
rt_dash_period_service_recovery_edf            1.100000   severe 10       0.486905     0.095930             211.327976            21.576841                           0.683470                         0.000019                          0.682857                        0.000000                     0.953333                   0.000000               1.000000             0.000000
               rt_dash_recovery_edf            0.500000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.043667                   0.002460               4.000000             0.000000
               rt_dash_recovery_edf            0.500000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.050333                   0.002460               4.000000             0.000000
               rt_dash_recovery_edf            0.500000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.095333                   0.026906               4.000000             0.000000
               rt_dash_recovery_edf            0.650000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.043667                   0.002460               4.000000             0.000000
               rt_dash_recovery_edf            0.650000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.095333                   0.032931               4.000000             0.000000
               rt_dash_recovery_edf            0.650000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.156667                   0.009686               4.000000             0.000000
               rt_dash_recovery_edf            0.800000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.445000                   0.303946               2.500000             1.581139
               rt_dash_recovery_edf            0.800000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.461000                   0.287166               2.500000             1.581139
               rt_dash_recovery_edf            0.800000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.485667                   0.261506               2.500000             1.581139
               rt_dash_recovery_edf            0.950000     mild 10       0.000000     0.000000              71.325000             9.131536                           1.000000                         0.000000                          1.000000                        0.000000                     0.953333                   0.000000               1.000000             0.000000
               rt_dash_recovery_edf            0.950000 moderate 10       0.000000     0.000000             127.130000            16.653450                           1.000000                         0.000000                          1.000000                        0.000000                     0.953333                   0.000000               1.000000             0.000000
               rt_dash_recovery_edf            0.950000   severe 10       0.486905     0.095930             211.327976            21.576841                           1.000000                         0.000000                          1.000000                        0.000000                     0.953333                   0.000000               1.000000             0.000000
               rt_dash_recovery_edf            1.100000     mild 10       0.000000     0.000000              71.325000             9.131536                           0.858469                         0.010359                          1.000000                        0.000000                     0.953333                   0.000000               1.000000             0.000000
               rt_dash_recovery_edf            1.100000 moderate 10       0.000000     0.000000             127.130000            16.653450                           0.848464                         0.009601                          1.000000                        0.000000                     0.953333                   0.000000               1.000000             0.000000
               rt_dash_recovery_edf            1.100000   severe 10       0.486905     0.095930             211.327976            21.576841                           0.833673                         0.009695                          1.000000                        0.000000                     0.953333                   0.000000               1.000000             0.000000
```

## Interpretation rule

True period stretching/shrinking is now executable and auditable, but the
recovery-aware service-control policy remains the principal Paper 1 result unless
the new held-out evidence justifies a stronger bounded claim. The new mechanism
is never promoted merely because it generates fewer low-criticality jobs.
