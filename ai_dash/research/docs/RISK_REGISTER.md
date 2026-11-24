# Research Risk Register

## Critical

### R1 — Simulation-to-deployment external validity

**Impact:** physical timing, WCET, memory, energy, and deployment determinism cannot be inferred.  
**Mitigation:** keep all claims explicitly simulation/software-only. Hardware validation is outside the user-declared project scope, not silently estimated.

### R2 — Comparator model translation

**Impact:** EDF-VD uses different assumptions from semantic-event RT-DASH, so a numeric comparison can be overinterpreted.  
**Mitigation:** the 800-run EDF-VD/degraded-quality EDF-VD benchmark is implemented and its semantic translation is documented beside results.

### R3 — Reduced-service semantics are not application-certified

**Impact:** a scheduler could report success while removing functionality that is unsafe to omit.  
**Mitigation:** define mandatory/optional segments for every degradable task and obtain domain-level acceptance criteria.

## Major

### R4 — Execution budgets are model parameters

**Impact:** simulation feasibility may not transfer to hardware.  
**Mitigation:** replace with measured or bounded WCET distributions.

### R5 — Synchronization abstraction is bounded rather than a full lock protocol

**Impact:** real lock chains, priority inheritance/ceiling, and self-suspension are not reproduced.  
**Mitigation:** a 0/2/5/10 ms bounded initial non-preemptive section is now executable and stressed at adversarial release phases; interpret it as a response-sensitivity bound, not a mutex proof.

### R6 — Trace-to-task mapping is newly introduced

**Impact:** external validity depends on modelling choices.  
**Mitigation:** publish the mapping and perform sensitivity analysis over budgets and deadlines.

### R7 — Monitoring/remapping overhead omitted

**Impact:** high transition frequency could consume non-negligible CPU.  
**Mitigation:** model and then measure every controller operation.

### R8 — Emergency workload family remains model-defined

**Impact:** results may depend on the declared burst generator and three severity templates.  
**Mitigation:** the final completion study sweeps 0.50--1.10 nominal load and mild/moderate/severe families; the blocking study deliberately shifts event phase to create contention. Broader workload families remain an external-validity question rather than hidden evidence.

## Minor

### R9 — RMS convention for one-shot jobs

**Impact:** baseline interpretation can be disputed.  
**Mitigation:** report periodic-only RMS results or use a defined sporadic server/fixed-priority baseline.

### R10 — Discrete quantum approximation

**Impact:** rounding affects short jobs and transition time.  
**Mitigation:** sensitivity tests with 1, 2, 5, and 10 ms quanta.

### R11 — Completion with reduced service can be misread

**Impact:** completion rate alone overstates delivered quality.  
**Mitigation:** always report service retained/removed and full-quality completion separately.

## Editorial/administrative

### R12 — Legacy and validated implementations coexist

**Impact:** researchers may run the wrong entry point.  
**Mitigation:** root README and Makefile identify `research/` and `research_cpp/` as validated; legacy files are explicitly marked.
