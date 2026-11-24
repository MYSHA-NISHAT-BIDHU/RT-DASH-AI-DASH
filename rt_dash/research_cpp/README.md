# C++17 RT-DASH Portability Implementation

This directory contains an independent C++17 implementation of RT-DASH policy selection, sampled mode logic, deterministic tie-breaking, ties-to-even service-floor rounding, controlled optional-work reduction, resource reservations, a host simulation, and tests.

The policy keys match the Python reference:

- EDF: `(absolute deadline, -criticality, release time, job identifier)`
- RMS: `(effective period, -criticality, absolute deadline, job identifier)`
- Critical ordering: `(-criticality, absolute deadline, release time, job identifier)`

Controlled degradation estimates demand inside the observation window, computes excess above `utilizationHigh × observationWindow`, orders eligible low-criticality jobs by `(minimum service fraction, -deadline, job identifier)`, and removes no more optional work than required. Integer service floors use round-to-nearest with ties to even.

## Build

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/rtdash_host_simulation
```

Compiled objects and build caches are intentionally excluded. The host simulation is portability evidence, not a reproduction of the complete Python experiment matrix and not a physical-hardware timing experiment.
