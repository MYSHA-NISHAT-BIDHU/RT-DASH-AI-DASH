# AI-RT-DASH Data Card

> This card describes the raw-sensor AI dataset. Synthetic thesis resource
> forecasting is documented separately in the ARIMA/LSTM protocol/model card.

## Intended use

The OpenSHS trace is used to study whether raw simulated smart-home device
states can supply an advisory critical-state signal to RT-DASH. It is not used
to infer human identity, diagnose health, or establish real-home safety.

## Source

OpenSHS Smart Home Dataset v3, Mendeley Data,
<https://doi.org/10.17632/zgsw84b2ff.3>. The repository describes 29 sensors,
timestamped activities, and an `anomaly` activity label.

## Audited properties

- Raw rows: 1,048,575.
- Sensor columns: 29.
- Source dates: 14.
- Invalid timestamps: 0.
- Duplicate timestamp rows beyond the first: 9,026.
- Timestamp groups with conflicting activity labels: 4,179.
- Backward timestamp jumps: 7.
- Forward gaps larger than one second: 20.
- Anomaly rows: 408,683.
- Contiguous anomaly episodes in source order: 13.

The authoritative machine-readable record is
`results/ai_extension/data_quality_audit.json`.

## Partitions

| Split | Dates | Samples after sampling/purge | Positive rate |
|---|---:|---:|---:|
| Training | first 8 | 60,108 | 0.2996 |
| Validation | next 3 | 23,972 | 0.4188 |
| Test | final 3 | 20,670 | 0.6173 |

The large prevalence shift is real and materially affects calibration. No
random row split is used.

## Labels and features

`Activity == anomaly` is the confirmatory target. `Activity` never appears in
the features. Resource/priority columns created during the earlier thesis work
are excluded. The model sees current device states, causal 60-second summaries,
transition counts, and time of day.

## Known limitations

- Simulated home, not physical deployment.
- One trace source and only 14 dates.
- Thirteen anomaly episodes are insufficient for a strong independent
  ahead-of-event forecasting claim.
- Duplicate timestamps include conflicting labels.
- Test prevalence is much higher than training prevalence.
- Activity labels may encode simulator construction choices rather than
  naturally occurring hazardous events.

Any paper must retain these limitations and may not call the data a measured
controller workload or a representative population of real homes.
