# RT-DASH / AI-DASH

**Adaptive Real-Time Scheduling and Predictive Mode Entry for Resource-Constrained Intelligent Systems**

This repository is the planned research-artifact home for RT-DASH and AI-DASH, developed from MSc research at Aarhus University and subsequent research extensions. **Release status: documentation-only preparation; the validated source code is not yet included.**

## Overview

RT-DASH is a workload- and event-adaptive dual-mode scheduling framework for resource-constrained smart-home controllers. It switches between Normal and Critical operating modes using workload and semantic-event conditions, with deadline-aware dispatch, controlled service degradation, and recovery-aware control.

AI-DASH extends the deterministic RT-DASH core with one-step-ahead resource forecasting. ARIMA and multivariate LSTM models estimate future CPU, memory, storage, and bandwidth pressure and provide an advisory signal for mode entry while deterministic guards remain authoritative.

## Published RT-DASH paper

Mysha Nishat Bidhu and Jalil Boudjadar,  
**“Workload- and Event-Adaptive Dual-Mode Scheduling with Recovery-Aware Service Control for Smart Home Controllers.”**  
*Algorithms*, 2026, 19(10), 863.  
DOI: https://doi.org/10.3390/a19100863

The published RT-DASH study reports 15,780 software-simulation runs.

## AI-DASH research extension

**Manuscript status:** Submitted for peer review in 2026; not accepted or published. The AI-DASH methods and results below describe the reported research, not executable files currently in this repository.


The AI-DASH research pipeline includes:

- ARIMA(5,1,0) forecasting
- multivariate LSTM forecasting
- chronological train/validation/test separation
- training-only normalization
- held-out evaluation
- rolling-origin robustness analysis
- predictive pressure integration with adaptive scheduling
- matched scheduler-policy comparisons
- prediction-fault and ablation studies

The primary AI-DASH evaluation includes 4,043 held-out forecast examples and 714 matched scheduler simulations. The post-lock robustness study adds 5,724 scheduler simulations and eight rolling-origin forecasting folds.

## Research scope and evidence boundary

This repository represents a **software-simulation research artifact**.

The reported scheduling and timing outcomes are not measurements from a physical embedded controller. The work does not claim:

- measured FreeRTOS execution latency
- physical mode-transition overhead
- hardware energy consumption
- WCET guarantees
- hard-real-time certification
- universal schedulability
- safety certification
- universal superiority of predictive control

The independent C++17 implementation is used as a portability/semantic check for scheduling, transition, and resource-accounting behavior, not as hardware timing evidence.

## Repository structure

```text
RT-DASH-AI-DASH/
├── README.md
├── requirements.txt
├── CITATION.cff
├── .gitignore
├── rt_dash/
├── ai_dash/
├── configs/
├── tests/
├── figures/
└── docs/
```

The current package contains documentation and repository scaffolding only. The authoritative source files must be copied from the validated research project into the corresponding folders, tested, and permission-checked before this repository is described as fully reproducible or made public as a software release.

## Reproducibility

See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## Limitations

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## Data

The research uses an OpenSHS-derived smart-home trace. CPU, memory, storage, and bandwidth forecasting variables used by AI-DASH are synthetic preprocessing annotations rather than measurements of physical devices.

Do not upload third-party data unless its license permits redistribution. Instead, document how to obtain the original source and how to reproduce preprocessing.

## Citation

See [`CITATION.cff`](CITATION.cff).

## Public-release checklist

- [x] Research overview, paper citation, limitations and directory layout
- [x] Ignore rules for private notes, generated data and secrets
- [ ] Import the **validated RT-DASH source and test suite** from the authoritative research archive
- [ ] Import the **validated AI-DASH forecasting and scheduler-integration source and tests**
- [ ] Add experiment configurations, reproducibility scripts, and approved figures/results
- [ ] Verify dependency versions and reproduction commands on a clean environment
- [ ] Check third-party dataset permissions, source ownership and explicit software license
- [ ] Scan all committed files and Git history for sensitive or unpublished material
- [ ] Confirm release readiness and switch GitHub visibility to public

**Avoid uploading older thesis prototypes as the final paper implementation without a documented validation match.**

## Contact

**Mysha Nishat Bidhu**  
MSc in Engineering (Computer Engineering), Aarhus University  
GitHub: https://github.com/MYSHA-NISHAT-BIDHU
