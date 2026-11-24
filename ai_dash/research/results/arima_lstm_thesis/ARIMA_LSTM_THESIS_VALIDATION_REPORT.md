# ARIMA + LSTM Thesis-Completion Validation Report

## Evidence boundary

This study implements the thesis-predicted resource branch with a real
ARIMA(5,1,0), a trained multivariate LSTM, and the thesis hybrid. The four
resource columns are fixed **synthetic thesis simulation annotations**, not
physical measurements. All forecasting windows are chronological and causal.

## Held-out forecasting metrics

```
                             mae  normalized_rmse_train_sd       r2      rmse  smape_percent
model         resource                                                                      
arima_510     Bandwidth 0.452586                  0.099746 0.991158  0.796183       3.816277
              CPU       1.083590                  0.082506 0.993978  2.499591       2.458421
              Memory    7.516049                  0.088867 0.992943 15.117285       2.710105
              Storage   1.857876                  0.110060 0.989218  2.935836       3.242178
lstm          Bandwidth 0.514104                  0.121965 0.986781  0.973536       4.312885
              CPU       1.074926                  0.082583 0.993967  2.501931       2.362301
              Memory    6.886329                  0.083841 0.993719 14.262286       2.634591
              Storage   1.842476                  0.111345 0.988965  2.970106       3.117508
persistence   Bandwidth 0.493887                  0.104636 0.990270  0.835214       4.150226
              CPU       1.111629                  0.083057 0.993898  2.516280       2.524466
              Memory    8.006608                  0.090936 0.992611 15.469165       2.878596
              Storage   2.134051                  0.117336 0.987745  3.129938       3.727662
thesis_hybrid Bandwidth 0.514104                  0.121965 0.986781  0.973536       4.312885
              CPU       1.083590                  0.082506 0.993978  2.499591       2.458421
              Memory    6.886329                  0.083841 0.993719 14.262286       2.634591
              Storage   1.842476                  0.111345 0.988965  2.970106       3.117508
```

The thesis hybrid uses ARIMA for CPU and LSTM for Memory/Storage/Bandwidth.
Persistence is retained as a necessary forecasting baseline. No inferior model
or negative metric is removed.

## LSTM training

The LSTM stopped after 23 epochs using validation-only early
stopping. Its best validation standardized MSE is
0.005816. The test split never selects an
epoch, architecture, scale, or scheduler threshold.

## Predictive scheduler integration

Validation selected hybrid-pressure threshold: **0.809598008**.

```
                                n  high_dmr  high_response_ms  low_utility  critical_mode_fraction
policy                                                                                            
edf                           102  0.444210        141.244573     0.979506                0.000000
rt_dash                       102  0.000000         60.000000     0.711630                0.556969
rt_dash_ai_only               102  0.000000         60.372825     0.713008                0.554707
rt_dash_ai_safe               102  0.000000         60.000000     0.711630                0.556969
rt_dash_ai_safe_recovery_edf  102  0.000000         60.000000     0.762022                0.557723
rt_dash_no_event_trigger      102  0.032169         68.890841     0.764867                0.445842
rt_dash_recovery_edf          102  0.000000         60.000000     0.762022                0.557723
```

Paired held-out comparisons:

```
                        left                    right                           metric  n_cells  n_date_clusters  mean_difference  date_cluster_bootstrap_ci95_low  date_cluster_bootstrap_ci95_high  wilcoxon_p_uncorrected   holm_p
             rt_dash_ai_only rt_dash_no_event_trigger         high_deadline_miss_ratio       54                3        -0.032169                        -0.033984                         -0.023895                0.000000 0.000002
             rt_dash_ai_only                  rt_dash         high_deadline_miss_ratio       54                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
             rt_dash_ai_only                  rt_dash               high_mean_response       54                3         0.372825                         0.129321                          1.028674                0.000252 0.001260
rt_dash_ai_safe_recovery_edf     rt_dash_recovery_edf         high_deadline_miss_ratio       54                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
rt_dash_ai_safe_recovery_edf     rt_dash_recovery_edf low_work_weighted_utility_linear      102                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
rt_dash_ai_safe_recovery_edf     rt_dash_recovery_edf           critical_mode_fraction      102                3         0.000000                         0.000000                          0.000000                1.000000 1.000000
```

The safe ARIMA+LSTM policies retain the semantic-event and utilization guards.
Forecasting is advisory; it cannot suppress deterministic mode entry.

## Publication interpretation

This branch demonstrates that the ARIMA/LSTM mechanism described in the thesis
is now genuinely implemented, leakage-controlled and connected to RT-DASH. It
does **not** convert synthetic resource annotations into claims of measured
hardware demand. The existing raw-sensor AI study remains separate evidence and
is not overwritten by this thesis-completion branch.
