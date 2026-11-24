# Experimental Validation Protocol

## 1. Experimental questions

- RQ1: Does RT-DASH protect high-criticality jobs under a controlled scheduling conflict?
- RQ2: Does hysteresis reduce repeated mode switching?
- RQ3: What service cost is transferred to low-criticality work?
- RQ4: Does graceful degradation retain more low-criticality jobs than no degradation?
- RQ5: Does RT-DASH remain behaviorally neutral on feasible trace-derived windows?

## 2. Independent variables

- scheduling policy;
- nominal periodic utilization;
- deterministic task-set seed;
- trace window;
- trace load scale.

## 3. Policies

- EDF;
- RMS;
- full RT-DASH;
- RT-DASH without hysteresis;
- RT-DASH without degradation.

## 4. Controlled workload

The base periodic workload contains six smart-home task types with fixed periods/deadlines and low or medium criticality. WCETs are jointly scaled to the target utilization and perturbed by a seeded factor. The correction step restores the requested aggregate utilization after rounding.

Emergency bursts occur at 15 s and 40 s. Each burst contains two or three high-criticality jobs selected deterministically from fire, intrusion, and gas-leak templates. The three-job case is intentionally capable of being infeasible so that the evaluation does not assume the proposed scheduler can solve processor overload that violates demand capacity.

## 5. Run matrix

- 10 seeds: 0–9;
- 5 load levels: 0.60, 0.80, 0.95, 1.10, 1.25;
- 5 policies;
- total controlled runs: 250;
- duration: 60,000 ms;
- quantum: 5 ms.

## 6. Trace-derived workload

The experiment uses raw OpenSHS activity/device rows rather than the thesis-generated resource columns. Three contiguous windows start at rows 0, 160400, and 963496. Each window contains 600 rows. Source timestamp differences are compressed to 100 ms per source second. Load scales are 0.8, 1.0, and 1.2.

The task budgets/deadlines in `workloads.py` are model parameters, not measured WCETs. This is explicitly part of the threat-to-validity analysis.

## 7. Metrics

- released and completed jobs by criticality;
- completion rate;
- deadline-assessed and right-censored job counts;
- deadline misses and DMR;
- mean, median, p95, p99, and standard deviation of completed response times;
- preemptions and context switches;
- mode transition count and reason;
- time in Critical Mode;
- omitted optional execution;
- processor busy fraction.

## 8. Deadline censoring

An unfinished job whose deadline is later than the run horizon is not classified as a deadline miss. It is reported as right-censored. An unfinished job whose deadline has occurred is a miss.

## 9. Statistical analysis

Results are summarized by policy and load using mean, sample standard deviation, and 95% t confidence intervals. Matched comparisons use load/seed pairs and report the mean paired difference, its 95% confidence interval, and Cohen's `d_z`. These summaries quantify the declared simulation population; they do not replace hardware replication.

## 10. Rejection criteria for a run

A run is invalid if:

- event releases are not aligned to the simulation quantum;
- task parameters violate model constraints;
- output files are missing or unparsable;
- the process terminates non-zero;
- the configured seed/load/policy is absent from the result manifest.

## 11. Historical hardware-extension note (outside final scope)

Earlier project planning described a possible hardware experiment using
identical serialized task sets and measured execution budgets. The final scope
was later fixed to simulation/software only, so this is not a required project
phase and no physical result is inferred from the simulator.
