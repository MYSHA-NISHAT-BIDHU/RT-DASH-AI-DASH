# Journal Readiness Assessment After Redevelopment

## Verdict

The project is now a substantially stronger simulation study. It has adequate repeated-run depth, graded stress regions, an explicit static criticality-first baseline, multiple ablations, sensitivity analysis, scalability analysis, recovery metrics and mapping-robustness analysis.

## Strengths

- 30 paired seeds for every principal scenario/load/policy cell.
- 9 policies, including five mechanism-isolating RT-DASH variants.
- Mild, moderate and severe emergency profiles reduce ceiling effects.
- Bootstrap confidence intervals, Wilcoxon tests, Holm correction and paired effect sizes.
- Transparent negative results and infeasibility boundaries.
- Reproducible code, manifests, raw summaries, representative job traces and hashes.

## Remaining boundaries

- Simulation task budgets and trace deadlines are model assumptions, not measured WCETs.
- The C++ host run is a parity check, not a separate statistical population.
- The study does not prove hard real-time schedulability or universal dominance over published mixed-criticality algorithms.
- A direct implementation of a published mixed-criticality comparator would strengthen state-of-the-art positioning further, but EDF, RMS and static criticality-first now provide defensible internal controls.

## Recommendation

Suitable as the experimental foundation of a simulation-focused journal article, provided the manuscript reports the model assumptions, ablation findings and evidence boundaries exactly as documented here.
