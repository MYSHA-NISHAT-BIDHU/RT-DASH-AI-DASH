# Scientific Project Specification

## 1. Research question

Can a lightweight single-core scheduler protect high-criticality smart-home jobs during emergency arrivals and transient overload while explicitly controlling the loss of optional lower-criticality service?

## 2. Hypotheses

- **H1:** Under matched task sets that create deadline-versus-criticality conflict, event-triggered criticality-first dispatch reduces high-criticality response time and deadline misses relative to single-mode EDF and RMS.
- **H2:** Separate entry/exit thresholds and hold intervals reduce mode oscillation relative to an otherwise identical no-hysteresis policy.
- **H3:** Declared degradation of optional low-criticality work increases retained completion under overload relative to an otherwise identical no-degradation policy.
- **H4:** Under feasible workloads that do not need adaptation, RT-DASH should not materially change completion or timing outcomes.

These hypotheses are workload-conditional. They do not imply global optimality.

## 3. Platform assumptions

- one preemptive processor;
- integer simulation time;
- independent job execution in principal experiments; the completion study adds
  an explicit bounded initial non-preemptive section as a synchronization stress;
- no self-suspension in the reference simulator;
- execution budget is known to the model;
- event releases and periodic releases are explicit;
- optional execution can be removed only through a task-declared valid service mode;
- high-criticality mandatory work is never deliberately reduced.

## 4. Task model

A task is described by:

`(id, C, D, T, criticality, degradable, gamma_min, beta, resources, source)`

where `C` is the nominal execution budget, `D` is relative deadline, `T` is period for periodic tasks, and `gamma_min` is the minimum retained fraction for a degradable task. Each job has release `r`, deadline `d=r+D`, remaining execution, status, and instrumentation state.
`beta` is the optional bounded non-preemptive execution prefix used only in the
synchronization/blocking stress model; it is not asserted to reconstruct a
historical mutex protocol.

## 5. Policy definitions

### EDF

Select minimum `(absolute_deadline, -criticality, release, job_id)`. Criticality is only a deterministic tie-break.

### RMS

Select minimum `(period, -criticality, absolute_deadline, job_id)`. One-shot baseline jobs use relative deadline as an effective period; this convention is documented because pure RMS is defined for periodic tasks.

### RT-DASH Normal Mode

Use EDF selection.

### RT-DASH Critical Mode

Select minimum `(-criticality, absolute_deadline, release, job_id)`.

### Thesis-completion period-control comparator

For degradable periodic tasks only, a Critical-Mode release interval may be
multiplied by a selected stretch factor. During the recovery window it may be
multiplied by a shrink factor before returning to the nominal period. This is
implemented as true online release rescheduling, not as post-hoc deletion. Its
parameters are tuned on seeds 30--49 and evaluated once on seeds 50--59. It is
kept as a comparator because the held-out safety metrics do not improve over
the recovery-aware service-control policy.

## 6. Mode controller

- Immediate entry on release of any high-criticality job.
- Load entry when smoothed utilization is at least `U_high` for `H_entry`.
- Exit when no high-criticality job remains and smoothed utilization is at most `U_low` continuously for `H_recovery`.
- Constraint: `0 <= U_low < U_high <= 1`.

## 7. Safety and correctness invariants

1. A high-criticality task has service floor 1.0.
2. Non-degradable work cannot have a service floor below 1.0.
3. Service reduction never removes already executed work.
4. A job is degraded at most once.
5. A deadline outcome is included in DMR only when completion is observed or the deadline has occurred by the simulation horizon.
6. A resource reservation is all-or-nothing.
7. A reservation identifier can be released at most once.
8. Event-triggered entry does not depend on monitor sampling latency.
9. Recovery requires a continuous hold interval.
10. Completion after optional-work omission is reported with service reduction, not treated as full-quality service.

## 8. Complexity

The Python reference uses an explicit ready list and therefore selection is `O(n)` per quantum. The portable C++ selection is also `O(n)`. A production implementation can use heaps or priority bands, but dynamic priority remapping on FreeRTOS must be measured because the kernel itself is fixed-priority.

## 9. Non-goals

The project does not claim a new general schedulability theorem, formal mixed-criticality assurance certification, cloud offloading, measured energy optimization, or multidimensional kernel reservation.
