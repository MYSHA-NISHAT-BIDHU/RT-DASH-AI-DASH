# Project Overview

## RT-DASH

RT-DASH addresses adaptive service control for mixed-importance smart-home workloads.

Core ideas documented by the project include:

- Normal and Critical operating modes
- semantic-event and workload-triggered entry
- hysteresis using separate entry/recovery conditions
- deadline-aware scheduling
- criticality-aware dispatch in Critical Mode
- optional-work reduction only for explicitly degradable low-criticality jobs
- recovery-aware return to Normal Mode
- controlled simulation, held-out evaluation, robustness analysis, and reproducibility checks

Published article:

Mysha Nishat Bidhu and Jalil Boudjadar.  
“Workload- and Event-Adaptive Dual-Mode Scheduling with Recovery-Aware Service Control for Smart Home Controllers.”  
Algorithms 2026, 19(10), 863. DOI: 10.3390/a19100863.

## AI-DASH

AI-DASH extends RT-DASH with resource-state prediction.

The documented research pipeline uses ARIMA(5,1,0) and a multivariate LSTM to forecast CPU, memory, storage, and bandwidth annotations. Forecasts are converted into an advisory pressure signal used by the mode controller.

The research protocol emphasizes temporal causality through chronological splitting and rolling-origin evaluation.

## Why this repository exists

The repository is intended to provide a concise, technically honest public artifact for:

- research reproducibility
- academic review
- PhD/research applications
- future extension of adaptive and dependable AI-enabled embedded/edge systems
