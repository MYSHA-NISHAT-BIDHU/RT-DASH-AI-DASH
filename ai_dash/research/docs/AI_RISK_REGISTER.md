# AI-RT-DASH Risk Register

| Risk | Evidence | Mitigation | Residual status |
|---|---|---|---|
| Temporal leakage | Rolling features could cross partitions | causal windows, chronological day split, 300 s purge, `generated_at <= time` invariant | controlled in software |
| Label leakage | `Activity` directly names anomaly | label excluded from all feature names and portable-model verifier | controlled |
| Synthetic-resource leakage into raw-sensor AI | thesis CPU/memory/etc. columns are random annotations | excluded from raw-sensor AI features and asserted by verifier | controlled |
| Thesis resource-forecast provenance | ARIMA/LSTM predicts generated resource annotations | separate frozen forecast protocol; causal historical resources only; every report labels targets synthetic | valid only as simulation/thesis-completion evidence |
| Distribution shift | positive rate rises 0.2996 → 0.4188 → 0.6173; test ECE 0.2719; held-out date AUROC ranges 0.4084–0.9999 | post-lock date diagnostics; separate scheduling threshold; deterministic fallback | material, unresolved externally |
| Sparse independent episodes | 13 source-order anomaly episodes | no strong future-warning claim; day-cluster inference | unresolved |
| Duplicate/conflicting timestamps | 9,026 duplicates; 4,179 conflicting-label groups | data audit retained; sequence boundaries and chronological grouping | unresolved source limitation |
| False positives | held-out specificity 0.3429 at classification threshold | validation scheduling threshold 0.99988; utility in objective | bounded in model study |
| False negatives / delayed entry | AI-only worse than semantic trigger | semantic and load triggers retained in safe hybrid | controlled by fallback in simulation |
| Sensor loss | explicit 5–20% channel-outage stress plus all 29 leave-one-out cases; `bathroomDoorLock` removal lowers AUPRC by 0.124564 | fail-safe path independent of ML output; dependence disclosed | not physically measured |
| Overclaiming novelty | proactive prediction and learner-based MC scheduling pre-exist | bounded novelty: smart-home sensor inference + runtime-assurance fallback + locked end-to-end evidence | manuscript wording required |
| Model execution interference | inference consumes host/software time | C export, C++ parity; measured host median 50.399 ns over 25×1M trials | physical WCET/stack/energy are outside declared scope |
| Reproducibility drift | runtime and library versions change | exact manifests, raw/result CSVs, hashes, verifier, portable format | bootstrap endpoints may vary by environment |
| Test-set reuse | held-out dates are now inspected | post-lock governance forbids future principal-model reselection on these dates | new confirmatory model changes require new data |
| Advanced ARIMA/LSTM repeated-test interpretation | advanced design was frozen after locked thesis-test metrics were already known | label all advanced forecast comparisons post-lock sensitivity; do not promote them to a fresh confirmatory test | external/new trace needed for independent confirmation |
| Prediction-signal faults | blackout, stuck-high, ±0.15 bias, Gaussian sigma 0.10/0.20 | deterministic semantic/load guards plus safe recovery; seven-case stress matrix | high DMR stays 0 in evaluated matrix, but stuck-high raises Critical-Mode residency; no universal safety claim |
