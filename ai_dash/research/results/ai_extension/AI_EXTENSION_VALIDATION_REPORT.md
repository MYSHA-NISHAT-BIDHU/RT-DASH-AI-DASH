# AI-RT-DASH Extension Validation Report

## Evidence boundary

This is a simulation and machine-learning study. The classifier uses raw OpenSHS device states and time-of-day only. The `Activity` field is a label and is not a feature. Thesis-generated CPU, memory, storage, bandwidth, priority and power values are excluded. No physical-board, energy, WCET, safety-certification or universal-generalization claim is made.

The raw source contains only 14 dates and 13 contiguous anomaly episodes; exact timestamps also include conflicting duplicate rows. These facts bound external validity. The chronological test remains untouched during model fitting, model selection and threshold selection.

## Locked protocol

- Training dates: first 8 source dates.
- Validation dates: next 3 source dates.
- Held-out test dates: final 3 source dates.
- Boundary purge: 300 seconds.
- Sampling period: 10 seconds.
- Features: current device states, causal 60-second device-state means, current/60-second transition counts and cyclic time-of-day.
- Current-state target: `Activity == anomaly`.
- Exploratory future target: anomaly present within 60 seconds; this is not used for the principal scheduler claim.
- Selected model: `current_sensor_logistic` using validation data only.
- Classification safety threshold: 0.00020000.
- End-to-end scheduler threshold: 0.99987681, selected on validation scheduling blocks only.
- Background periodic utilization profiles: 0.30, 0.45, 0.60.

## Held-out AI result

- AUROC: 0.7487
- AUPRC: 0.8323
- Sensitivity: 1.0000
- Specificity: 0.3429
- Precision: 0.7105
- F1: 0.8308
- Brier score: 0.3145
- ECE (10 bins): 0.2719
- Episode recall: 1.0000
- Median within-episode detection delay: 0.0 seconds

The chronological distribution shift is material and is reported rather than hidden. A safe hybrid therefore retains the original semantic-event and utilization triggers; AI is an additional trigger, never the only safety path in the deployment-oriented policy.

## Post-lock temporal and interpretability diagnostics

Held-out date-level AUPRC ranges from 0.3477 to 1.0000. The mean absolute standardized feature shift relative to training ranges from 0.2979 to 0.3732 across the three held-out dates. These diagnostics are calculated only after the model and classification threshold are locked and do not participate in selection.

The standardized coefficient export makes the selected logistic model auditable. Its five largest absolute coefficients are:

```
                         feature  standardized_coefficient
sensor_current__bathroomDoorLock                  3.178657
 sensor_current__bedroomDoorLock                 -3.137293
             sensor_current__bed                  2.092186
     sensor_current__bedroomCarp                  1.965807
     sensor_current__livingLight                 -1.852231
```

A complete leave-one-sensor-out test is also reported. The largest held-out AUPRC decrease occurs when `bathroomDoorLock` is removed: -0.124564. This is a failure-dependence measurement, not a causal interpretation of the sensor.

## End-to-end scheduling aggregate

```
                                                            high_dmr  high_response  low_utility  critical_fraction
policy                       background_utilization_target                                                         
edf                          0.30                           0.000000      87.323747     1.000000           0.000000
                             0.45                           0.513201     170.925504     0.971522           0.000000
                             0.60                           0.880122     171.304119     0.943866           0.000000
rt_dash                      0.30                           0.000000      60.000000     0.720160           0.595638
                             0.45                           0.000000      60.000000     0.644333           0.647489
                             0.60                           0.000000      60.000000     0.537667           0.789041
rt_dash_ai_only              0.30                           0.000000      69.192736     0.816316           0.390859
                             0.45                           0.001604      61.210763     0.648613           0.638869
                             0.60                           0.009141      60.543421     0.542796           0.780878
rt_dash_ai_safe              0.30                           0.000000      60.000000     0.720160           0.595638
                             0.45                           0.000000      60.000000     0.644333           0.647489
                             0.60                           0.000000      60.000000     0.537667           0.789041
rt_dash_ai_safe_recovery_edf 0.30                           0.000000      60.000000     0.721798           0.595638
                             0.45                           0.000000      60.000000     0.720119           0.648082
                             0.60                           0.000000      60.000000     0.649453           0.789041
rt_dash_no_event_trigger     0.30                           0.000000      70.798581     0.832898           0.354695
                             0.45                           0.002299      61.623829     0.650108           0.635901
                             0.60                           0.012616      60.720491     0.544677           0.777956
rt_dash_recovery_edf         0.30                           0.000000      60.000000     0.721798           0.595638
                             0.45                           0.000000      60.000000     0.720119           0.648082
                             0.60                           0.000000      60.000000     0.649453           0.789041
```

## Paired comparisons

```
                        left                    right                           metric  n_blocks  n_day_clusters  mean_difference  day_cluster_bootstrap_ci95_low  day_cluster_bootstrap_ci95_high  wilcoxon_p_uncorrected      holm_p
             rt_dash_ai_only rt_dash_no_event_trigger         high_deadline_miss_ratio        54               3      -0.00138979                     -0.00357374                                0               0.0591692    0.236677
             rt_dash_ai_only                  rt_dash         high_deadline_miss_ratio        54               3       0.00358168                      0.00179612                       0.00569737             0.000138858 0.000694292
             rt_dash_ai_only                  rt_dash               high_mean_response        54               3          3.64897                         2.77983                          6.95589              1.3152e-09 7.89122e-09
rt_dash_ai_safe_recovery_edf     rt_dash_recovery_edf         high_deadline_miss_ratio        54               3                0                               0                                0                       1           1
rt_dash_ai_safe_recovery_edf     rt_dash_recovery_edf low_work_weighted_utility_linear        90               3                0                               0                                0                       1           1
rt_dash_ai_safe_recovery_edf     rt_dash_recovery_edf           critical_mode_fraction        90               3                0                               0                                0                       1           1
```

Day-cluster bootstrap intervals use the three held-out dates as clusters. They are necessarily wide and must not be interpreted as population-level assurance.

## What the integration result does and does not establish

At background utilization 0.45, AI-only triggering reduced mean high-criticality DMR from 0.002299 (load-only) to 0.001604; at 0.60 it reduced DMR from 0.012616 to 0.009141. The pooled paired difference was -0.001390, but the three-day-cluster Holm-adjusted p-value was 0.2367; the direction is not statistically confirmed with this dataset.

The semantic RT-DASH trigger remained stronger: AI-only DMR exceeded it by 0.003582 on paired anomaly-containing cells. The safe AI + recovery-aware policy exactly reproduced the deterministic recovery-aware fallback for high DMR, low utility and Critical-Mode fraction in all 90 held-out block-load cells. Thus the AI result is an advisory-trigger result with a fail-safe boundary, not evidence that ML should replace the deterministic guard.

## Reproducible outputs

- `data_quality_audit.json`: source-row, timestamp, label-conflict and episode audit.
- `classification_metrics.csv`: split-specific discrimination, calibration and threshold metrics.
- `model_selection.csv`: validation-only selection evidence, runtime and model size.
- `sensor_outage_robustness.csv`: deterministic channel-outage stress tests.
- `leave_one_sensor_out.csv`: exhaustive single-sensor failure diagnostics for the selected model.
- `selected_model_feature_importance.csv`: standardized selected-model coefficients and odds ratios.
- `temporal_generalization_by_date.csv`: post-lock date-level performance and covariate/risk-shift diagnostics.
- `validation_locked_operating_curve.csv`: validation-defined threshold grid evaluated on validation and held-out data.
- `scheduler_threshold_validation.csv`: validation-only end-to-end threshold choice.
- `scheduling_integration_runs.csv`: held-out block-level simulator results.
- `scheduling_paired_comparisons.csv`: paired effects and day-cluster intervals.
- `portable_logistic_model.json` and `.h`: compact selected-model inference artifacts with verified Python/C parity.
- `selected_model.pkl`: selected research model and preprocessing state.
- `ai_execution_manifest.json` and `SHA256SUMS_AI.txt`: partitions, versions and file hashes.

## Defensible conclusion

The extension establishes a real, reproducible AI path; it does not relabel the original rules as AI. The learned detector supplies a causal risk signal from raw device state without requiring the activity label at inference time. Because one OpenSHS trace cannot establish broad anomaly generalization, the deployment-oriented design keeps deterministic RT-DASH event/load fallback. The original RT-DASH paper can remain a scheduler paper, while the AI paper should focus on sensor-derived semantic-risk inference, uncertainty/failure handling, and the measured end-to-end trade-off under the explicitly limited dataset.
