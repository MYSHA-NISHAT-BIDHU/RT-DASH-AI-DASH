# RT-DASH Journal-Strengthening Completion Report

**Study type:** deterministic software simulation only  
**Hardware evidence:** none used or claimed  
**Principal controlled seeds:** 30  
**Total executed simulations:** 8,980

## 1. What was redeveloped

The original completed simulator was scientifically useful but still had several weaknesses for journal review. The strengthened version corrects or addresses them as follows:

1. **Startup-utilization bias removed.** The moving utilization window is now zero-filled at startup rather than averaging only the first few busy samples.
2. **Work-conserving quantum execution.** When a job completes before the end of a simulation quantum, the remaining time is immediately assigned to the next ready job. The earlier model could create artificial idle time.
3. **Explicit stale-job policy.** Unfinished jobs are dropped at their absolute deadline, matching a smart-home controller in which obsolete actuation or sensing work should not accumulate indefinitely.
4. **Graded emergency demand.** Mild, moderate, and severe emergency profiles replace a single ceiling-dominated workload.
5. **Expanded controls.** Nine policies are evaluated: EDF, RMS, static criticality-first EDF, full RT-DASH, and RT-DASH without hysteresis, degradation, event trigger, load trigger, or recovery hold.
6. **Thirty matched seeds.** Every principal scenario/load/policy cell has 30 paired seeds.
7. **Mechanism-specific validation.** Dedicated threshold-chatter, recovery, overload, and optional-service-stress scenarios isolate individual RT-DASH mechanisms.
8. **Sensitivity and scalability.** Thresholds, hysteresis gap, recovery hold, observation window, smoothing, and task count are evaluated separately.
9. **Trace-mapping robustness.** Five contiguous OpenSHS-derived windows are replayed using relaxed, nominal, and stressed task-mapping assumptions.
10. **Stronger statistics.** Paired bootstrap confidence intervals, Wilcoxon signed-rank tests, Holm correction, Cohen's dz, and rank-biserial effect sizes are archived.

## 2. Executed experiment matrix

| Study component | Executed runs |
|---|---:|
| Principal controlled study | 7,560 |
| Parameter sensitivity | 880 |
| Scalability | 450 |
| Trace-mapping robustness | 90 |
| **Total** | **8,980** |

The principal study contains 28 scenario/load cells, 30 matched seeds, and 9 policies. Every policy receives the same periodic task set and event releases within each matched cell.

## 3. Principal findings

### 3.1 Critical-task protection

Across the declared emergency scenarios, full RT-DASH reduced high-criticality deadline-miss ratio relative to EDF by an average absolute difference of **0.4449**, with a paired bootstrap 95% confidence interval of **0.4116–0.4786** in the favourable direction. Relative to RMS, the average absolute reduction was **0.7430**, with a 95% interval of **0.7119–0.7742**.

High-criticality mean response time was lower than EDF by **169.6 ms** on average and lower than RMS by **131.4 ms** in the matched emergency comparisons.

### 3.2 What causes the high-criticality improvement

RT-DASH and static criticality-first EDF produced identical high-criticality deadline-miss and response results in matched emergency cases. Therefore, the critical-task benefit is attributable to **criticality-first dispatch**. The incremental RT-DASH contribution is not a new priority rule; it is adaptive activation, combined event/load triggering, hysteresis, recovery control, and optional-service management.

### 3.3 Event trigger contribution

Removing the event trigger increased high-criticality deadline-miss ratio by **0.1233** on average in the graded emergency study. This verifies that immediate semantic event detection matters beyond sampled load monitoring.

### 3.4 Hysteresis and recovery

Removing hysteresis caused **44.7 additional transitions per threshold-chatter run** on average, with a bootstrap 95% interval of **41.6–47.8**.

Removing the recovery hold shortened Critical-Mode residence by approximately **0.01165 of the run duration** in mild-emergency cases. The measured simulated recovery-control latency changed exactly with the configured hold interval, from 0 to 2,000 ms. This confirms the implementation and exposes the expected responsiveness–stability trade-off.

### 3.5 Optional-service degradation

In the dedicated optional-service-stress scenario, RT-DASH increased low-criticality completion by **0.02188** relative to RT-DASH without degradation. Both variants delivered the same aggregate low-criticality service fraction (**0.82461**), because RT-DASH omitted approximately **1,687 ms** of declared optional work per run and converted otherwise incomplete jobs into reduced-service completions. This is a quality-versus-completion trade-off, not free performance.

### 3.6 Load-threshold sensitivity

Increasing the upper utilization threshold from 0.75 to 0.95 reduced mean Critical-Mode residence from approximately **0.923** to **0.588**, while increasing low-criticality completion and delivered service. No single threshold is universally optimal; the selected operating point must reflect the safety/service objective.

### 3.7 Scalability

At 128 periodic tasks and nominal utilization 0.95, RT-DASH averaged a maximum ready-queue length of **11.5** and approximately **3,963 scheduling decisions** per 20-second run. The host runtime measurements are environment-specific and are included only as implementation-cost diagnostics, not real-time guarantees.

### 3.8 Trace-derived robustness

For RT-DASH, mean high-criticality deadline-miss ratio across the selected trace windows changed from **0.5789** under the relaxed mapping to **0.7895** under the nominal mapping and **0.8947** under the stressed mapping. This demonstrates that task-budget and deadline assumptions materially affect the results. The trace study is therefore reported as trace-informed simulation, not measured processor replay.

## 4. Scientific conclusions now supported

The executed project supports the following bounded conclusions:

1. Criticality-first dispatch protects safety-relevant jobs in the declared emergency workloads more effectively than EDF and RMS.
2. Immediate event triggering improves high-criticality outcomes compared with relying only on sampled utilization.
3. Hysteresis suppresses transition chatter.
4. Recovery hold controls how quickly the scheduler returns to Normal Mode.
5. Optional-work reduction can increase completed low-criticality jobs without increasing aggregate delivered service.
6. Adaptive mode control does not improve high-criticality performance beyond always-on criticality-first dispatch when both use the same ordering rule.
7. Simulation outcomes are sensitive to task mapping, load, and threshold choices.
8. No scheduling policy can overcome intrinsically infeasible mandatory processor demand.

## 5. Claims that remain unsupported

The project does not establish:

- hard real-time schedulability;
- physical FreeRTOS timing or microcontroller performance;
- measured energy savings;
- real memory, storage, or network reservations;
- universal superiority over all published mixed-criticality schedulers;
- safety certification of reduced-service application modes.

## 6. Journal-readiness judgement

The project is now a strong experimental foundation for a **simulation-focused journal article**. Its strongest contribution is a transparent, recovery-aware adaptive control layer for smart-home scheduling, not a new fundamental scheduling theorem.

A direct implementation of one published mixed-criticality or emergency-first comparator would further improve external state-of-the-art positioning. It is no longer required to establish internal correctness or mechanism-level causality, because the present package contains matched classic baselines, static criticality-first control, five ablations, sensitivity analysis, scalability analysis, and trace-mapping robustness.
