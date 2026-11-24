# Final Journal Readiness Assessment

## Decision

**Ready as the experimental foundation of a strong simulation-focused journal paper.**

The final project now has the elements that were missing from the earlier versions:

- adequate repeated-run depth;
- train/validation/test separation;
- held-out confirmation;
- a published external comparator family;
- mechanism-specific ablations;
- parameter sensitivity;
- scalability;
- utility robustness;
- demand screening;
- execution-overhead and release-jitter robustness;
- independent C++ parity evidence;
- complete manifests, raw CSV outputs, hashes, and validation scripts.

## Strongest supported conclusions

1. Criticality-first dispatch substantially protects high-criticality jobs compared with EDF and RMS in the declared emergency workloads.
2. RT-DASH can activate that dispatch adaptively rather than permanently.
3. Event triggering adds protection beyond sampled utilization alone.
4. Hysteresis suppresses transition chatter.
5. Optional-work reduction trades quality for job completion and must be reported through utility/service metrics.
6. A recovery-aware EDF phase can improve low-criticality completion and utility after high-criticality work clears without changing high-criticality deadline outcomes in the executed test matrix.
7. Workload infeasibility, mapping assumptions, and execution overhead materially affect outcomes.
8. Under the separate dual-criticality benchmark, EDF-VD and RT-DASH-style control expose different high-response/low-service trade-offs because their trigger semantics differ.

## Submission discipline

A paper based on this project must:

- call every result simulated or model-derived;
- describe the held-out test split before presenting results;
- report completion and utility/service together;
- distinguish the smart-home event model from the dual-criticality EDF-VD benchmark;
- avoid claims of hard schedulability, hardware timing, or universal superiority;
- make the complete code and result package available to reviewers.

## Residual risk

The largest remaining scientific risk is external validity: execution budgets and deadlines are not measured from deployed smart-home hardware. That risk is mitigated, but not eliminated, by mapping sensitivity, demand screening, and overhead/jitter robustness.
