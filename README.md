# RT-DASH & AI-DASH — Research Source Code (Curated Release)

This repository hosts **two related research projects** by Mysha Nishat Bidhu.

| Project | Description | Publication status |
| --- | --- | --- |
| [RT-DASH](rt_dash/README.md) | Workload- and event-adaptive dual-mode scheduling with recovery-aware control for smart-home controllers | Published in *Algorithms* (2026), [DOI](https://doi.org/10.3390/a19100863) |
| [AI-DASH](ai_dash/README.md) | ARIMA/LSTM-informed scheduling with deterministic fallback for critical services | Manuscript **submitted** for peer review (2026), not published |

## Included

Both directories contain research Python code, C++17 implementations, configs, scripts and unit tests extracted from the provided research archives. The archive review on 24 November 2026 found **25 passing Python tests for RT-DASH**, **48 passing Python tests for AI-DASH**, and **1 passing CTest per project**.

## Important reproducibility boundary

This is a **curated code release**, not a copy of the complete multi-hundred-megabyte scholarly archives. To limit unnecessary distribution of data, legacy files, and platform-specific binaries, it excludes original dataset snapshots, large run-level experimental outputs, model binary checkpoints, and generated firmware. Consequently, the paper's complete numerical reproduction needs the original supplementary/archive material as well as the files here.

The work is software-simulation based and does not claim measured physical hardware timing, WCET or safety certification. AI-DASH is a submitted manuscript and must not be described as peer reviewed or accepted.

See each project folder for details and licensing notes. The original RT-DASH supplementary materials are associated with the [published paper](https://doi.org/10.3390/a19100863).
