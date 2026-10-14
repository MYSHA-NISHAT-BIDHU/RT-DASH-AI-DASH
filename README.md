# RT-DASH / AI-DASH

**Adaptive Real-Time Scheduling and Predictive Mode Entry for Resource-Constrained Intelligent Systems**

This repository is the public research-artifact home for RT-DASH and AI-DASH, developed from MSc research at Aarhus University and subsequent research extensions.

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

The current public package contains documentation and repository scaffolding. The authoritative source files should be copied from the validated research project into the corresponding folders before the repository is described as fully reproducible.

## Reproducibility

See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## Limitations

See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## Data

The research uses an OpenSHS-derived smart-home trace. CPU, memory, storage, and bandwidth forecasting variables used by AI-DASH are synthetic preprocessing annotations rather than measurements of physical devices.

Do not upload third-party data unless its license permits redistribution. Instead, document how to obtain the original source and how to reproduce preprocessing.

## Citation

See [`CITATION.cff`](CITATION.cff).

## Contact

**Mysha Nishat Bidhu**  
MSc in Engineering (Computer Engineering), Aarhus University  
GitHub: https://github.com/MYSHA-NISHAT-BIDHU
