# Advanced ARIMA + LSTM Validation Report

## Evidence boundary

This is an additive, pre-frozen simulation-only strengthening study. The resource
targets are synthetic thesis annotations. No physical hardware, MCU timing,
energy, measured WCET, FreeRTOS execution, or safety-certification claim is made.
All primary choices are training/validation-only; the final three test dates are
held out from selection.

The three test dates had already been inspected in the earlier locked thesis
study before this advanced study was designed. Therefore the advanced model
comparison is post-lock sensitivity/robustness evidence, not a second fresh
confirmatory test, even though its computational selection uses validation only.

## Validation-selected model

Selected tuned LSTM: hidden=32, learning
rate=0.005, validation mean normalized RMSE=
0.074761. Adaptive convex LSTM weights are
**CPU=0.70, Memory=0.95, Storage=1.00, Bandwidth=1.00**; the remaining weight for each resource belongs to ARIMA(5,1,0).

## Held-out forecasting

```
                                   mae  normalized_rmse_train_sd       r2      rmse  smape_percent
model               resource                                                                      
adaptive_arima_lstm Bandwidth 0.462431                  0.105849 0.990043  0.844892       3.859851
                    CPU       1.007363                  0.079657 0.994387  2.413298       2.264780
                    Memory    7.055487                  0.087141 0.993215 14.823566       2.638937
                    Storage   1.922161                  0.119331 0.987325  3.183144       3.234184
arima_510           Bandwidth 0.452586                  0.099746 0.991158  0.796183       3.816277
                    CPU       1.083590                  0.082506 0.993978  2.499591       2.458421
                    Memory    7.516049                  0.088867 0.992943 15.117285       2.710105
                    Storage   1.857876                  0.110060 0.989218  2.935836       3.242178
ewma                Bandwidth 0.459709                  0.100284 0.991063  0.800474       3.871495
                    CPU       1.044665                  0.082502 0.993979  2.499468       2.359986
                    Memory    7.446837                  0.088760 0.992960 15.099110       2.684590
                    Storage   1.820410                  0.111174 0.988999  2.965544       3.177145
lstm_anchor         Bandwidth 0.514104                  0.121965 0.986781  0.973536       4.312885
                    CPU       1.074926                  0.082583 0.993967  2.501931       2.362301
                    Memory    6.886329                  0.083841 0.993719 14.262286       2.634591
                    Storage   1.842476                  0.111345 0.988965  2.970106       3.117508
lstm_tuned          Bandwidth 0.462431                  0.105849 0.990043  0.844892       3.859851
                    CPU       1.032832                  0.080394 0.994283  2.435624       2.287569
                    Memory    7.108717                  0.087567 0.993148 14.896159       2.662981
                    Storage   1.922161                  0.119331 0.987325  3.183144       3.234184
persistence         Bandwidth 0.493887                  0.104636 0.990270  0.835214       4.150226
                    CPU       1.111629                  0.083057 0.993898  2.516280       2.524466
                    Memory    8.006608                  0.090936 0.992611 15.469165       2.878596
                    Storage   2.134051                  0.117336 0.987745  3.129938       3.727662
ridge_var           Bandwidth 0.439423                  0.097582 0.991538  0.778904       3.769540
                    CPU       1.126938                  0.084979 0.993612  2.574508       2.408021
                    Memory    7.109771                  0.086731 0.993278 14.753795       2.638520
                    Storage   1.651288                  0.099621 0.991166  2.657374       2.883195
thesis_hybrid       Bandwidth 0.514104                  0.121965 0.986781  0.973536       4.312885
                    CPU       1.083590                  0.082506 0.993978  2.499591       2.458421
                    Memory    6.886329                  0.083841 0.993719 14.262286       2.634591
                    Storage   1.842476                  0.111345 0.988965  2.970106       3.117508
```

No baseline is removed when it outperforms the proposed model. In particular,
distribution shift in Bandwidth remains visible rather than being tuned away on
the test set.

## Eight-fold causal rolling-origin robustness

```
                         folds  mean_rmse  mean_nrmse
model         resource                               
arima_510     Bandwidth      8   0.747154    0.096828
              CPU            8   2.252875    0.076658
              Memory         8  13.833890    0.083901
              Storage        8   2.872666    0.111601
lstm_fixed    Bandwidth      8   0.789078    0.100992
              CPU            8   2.227344    0.075282
              Memory         8  12.915139    0.077784
              Storage        8   2.636989    0.101641
persistence   Bandwidth      8   0.774154    0.100175
              CPU            8   2.238103    0.076012
              Memory         8  13.874613    0.083937
              Storage        8   3.026308    0.117277
thesis_hybrid Bandwidth      8   0.789078    0.100992
              CPU            8   2.252875    0.076658
              Memory         8  12.915139    0.077784
              Storage        8   2.636989    0.101641
```

These folds refit each model causally and are robustness evidence, not eight
independent datasets.

## Scheduler ablation

```
                                                       n  high_dmr  high_response_ms  low_utility  critical_fraction
predictor              policy                                                                                       
adaptive_arima_lstm    rt_dash_ai_only               102  0.000000         60.312005     0.712720           0.555159
                       rt_dash_ai_safe_recovery_edf  102  0.000000         60.000000     0.762022           0.557723
arima_all              rt_dash_ai_only               102  0.000161         60.468826     0.713070           0.554254
                       rt_dash_ai_safe_recovery_edf  102  0.000000         60.000000     0.762022           0.557723
deterministic_baseline rt_dash                       102  0.000000         60.000000     0.711630           0.556969
                       rt_dash_no_event_trigger      102  0.032169         68.890841     0.764867           0.445842
                       rt_dash_recovery_edf          102  0.000000         60.000000     0.762022           0.557723
lstm_tuned             rt_dash_ai_only               102  0.000000         60.312005     0.712720           0.555159
                       rt_dash_ai_safe_recovery_edf  102  0.000000         60.000000     0.762022           0.557723
thesis_hybrid          rt_dash_ai_only               102  0.000000         60.372825     0.713008           0.554707
                       rt_dash_ai_safe_recovery_edf  102  0.000000         60.000000     0.762022           0.557723
```

Paired comparisons:

```
                                            left                                           right                           metric  n_cells  n_date_clusters  mean_difference  date_cluster_bootstrap_ci95_low  date_cluster_bootstrap_ci95_high  wilcoxon_p_uncorrected   holm_p
             adaptive_arima_lstm|rt_dash_ai_only                   thesis_hybrid|rt_dash_ai_only         high_deadline_miss_ratio       54                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
             adaptive_arima_lstm|rt_dash_ai_only                   thesis_hybrid|rt_dash_ai_only low_work_weighted_utility_linear      102                3        -0.000289                        -0.000981                          0.000000                0.299987 1.000000
             adaptive_arima_lstm|rt_dash_ai_only deterministic_baseline|rt_dash_no_event_trigger         high_deadline_miss_ratio       54                3        -0.032169                        -0.033984                         -0.023895                0.000000 0.000003
             adaptive_arima_lstm|rt_dash_ai_only                  deterministic_baseline|rt_dash         high_deadline_miss_ratio       54                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
             adaptive_arima_lstm|rt_dash_ai_only                  deterministic_baseline|rt_dash               high_mean_response       54                3         0.312005                         0.129321                          1.028674                0.001450 0.010151
adaptive_arima_lstm|rt_dash_ai_safe_recovery_edf     deterministic_baseline|rt_dash_recovery_edf         high_deadline_miss_ratio       54                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
adaptive_arima_lstm|rt_dash_ai_safe_recovery_edf     deterministic_baseline|rt_dash_recovery_edf low_work_weighted_utility_linear      102                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
adaptive_arima_lstm|rt_dash_ai_safe_recovery_edf     deterministic_baseline|rt_dash_recovery_edf           critical_mode_fraction      102                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
```

## Prediction-fault runtime assurance

```
        fault_case  n_cells  high_dmr  high_dmr_difference_vs_deterministic  low_utility  low_utility_difference_vs_deterministic  critical_mode_fraction  critical_fraction_difference_vs_deterministic  exact_high_dmr_match
          blackout      102  0.000000                              0.000000     0.762022                                 0.000000                0.557723                                       0.000000                  True
gaussian_sigma_010      102  0.000000                              0.000000     0.762022                                 0.000000                0.602444                                       0.044721                  True
gaussian_sigma_020      102  0.000000                              0.000000     0.762022                                 0.000000                0.677406                                       0.119683                  True
 negative_bias_015      102  0.000000                              0.000000     0.762022                                 0.000000                0.557723                                       0.000000                  True
           nominal      102  0.000000                              0.000000     0.762022                                 0.000000                0.557723                                       0.000000                  True
 positive_bias_015      102  0.000000                              0.000000     0.762022                                 0.000000                0.597014                                       0.039291                  True
        stuck_high      102  0.000000                              0.000000     0.762022                                 0.000000                0.922429                                       0.364706                  True
```

The blackout case is the deterministic-fallback check. Stuck-high and noisy
cases intentionally expose false-positive utility cost; they are not suppressed
from the report. Forecasting remains advisory to the deterministic semantic and
utilization guards.

## Publication interpretation

The thesis mechanism is preserved: ARIMA handles periodic structure and LSTM
handles nonlinear multivariate structure. The advanced contribution is a
leakage-controlled ARIMA-LSTM ensemble plus explicit runtime assurance. The
generic deterministic RT-DASH framework remains separable for Paper 1; this
forecasting/assurance evidence belongs to the focused AI paper.
