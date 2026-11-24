# RT-DASH Portable C++17 Host-Simulation Core

This directory contains the validated C++ reference implementation used to check the policy-selection and mode-control semantics independently of the Python simulator.

## Implemented

- EDF selection by absolute deadline;
- RMS selection by task period;
- static criticality-first EDF;
- RT-DASH criticality-first selection in Critical Mode;
- immediate high-criticality mode entry;
- utilization hold and hysteretic recovery;
- declared service-floor reduction primitives;
- transactional multidimensional resource reservations;
- duplicate-reservation and double-release prevention;
- an executable deterministic host-simulation scenario;
- portable logistic-model inference used for Python/C++ parity checking; and
- a standalone repeated-inference benchmark driver for measured host latency.

## Build and execute

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/rtdash_host_simulation
```

This is a software host simulation. It makes no physical-hardware or board-timing claim. The legacy FreeRTOS PC-port files remain elsewhere in the repository as historical source material and are not the validated implementation.

## Portable AI host benchmark

The benchmark source is `benchmarks/benchmark_portable_header.cpp`; the
reproducible runner and verifier live under `research/scripts/`. From the
`research` directory:

```bash
PYTHONPATH=. python scripts/run_portable_host_benchmark.py
PYTHONPATH=. python scripts/verify_portable_host_benchmark.py
```

The frozen 2026-08-05 run contains 25 trials of 1,000,000 inferences each after
100,000 warm-up inferences. Its median is 50.399123 ns/inference on the recorded
AMD EPYC 9V74 host using g++ 13.3.0. This value is a measured throughput-oriented
host result only; it is not a microcontroller timing result, a WCET bound, an
energy measurement, or evidence of real-time certification.
