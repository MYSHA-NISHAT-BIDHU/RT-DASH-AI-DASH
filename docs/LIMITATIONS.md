# Research Limitations and Claim Boundaries

The RT-DASH / AI-DASH work is intentionally described within the limits of the evidence produced by the project.

## Current limitations

- The principal evidence is software simulation.
- No physical-board timing result is claimed.
- No measured WCET table is available for a certified hardware task set.
- No measured physical mode-transition, context-save, interrupt, driver, UART, or resource-realignment latency is claimed.
- No hardware energy result is claimed.
- The primary scheduler model is single-processor.
- Smart-home workload mappings and emergency semantics include modelling assumptions.
- CPU, memory, storage, and bandwidth forecasting targets are synthetic annotations produced during preprocessing.
- Demand-bound screening is diagnostic and is not a universal schedulability proof.
- Degraded-service behavior is not safety certified.
- The principal data source is one OpenSHS-derived trace, limiting external validity.
- Predictive models do not improve every target or every operating condition.
- A forecasting model should not be described as universally superior to simpler baselines.

## Interpretation of AI-DASH

The forecasting path provides an **advisory** signal.

Deterministic semantic-event and utilization guards remain independent protection paths. Prediction is not allowed to suppress a deterministic transition required by those guards.

## Interpretation of the C++ implementation

The C++17 implementation is a portability/semantic check for scheduling, transition, and resource-accounting behavior. It is not evidence of:

- bit-for-bit equivalence in every numeric detail
- physical FreeRTOS execution time
- deployed-controller latency
- hard-real-time certification

## Publication integrity

Repository descriptions, CV statements, applications, and papers should preserve these boundaries.
