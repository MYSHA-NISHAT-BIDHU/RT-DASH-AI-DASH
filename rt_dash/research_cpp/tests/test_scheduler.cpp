#include "rtdash/ResourceManager.hpp"
#include "rtdash/Scheduler.hpp"

#include <cassert>
#include <cmath>
#include <vector>

namespace {
bool close(double left, double right) {
    return std::abs(left - right) < 1e-9;
}
}

int main() {
    using namespace rtdash;

    // Policy correctness: EDF follows absolute deadline; Critical Mode follows
    // criticality before deadline.
    TaskSpec low{"low", 100, 20, 50, Criticality::Low, true, 0.4};
    TaskSpec high{"high", 10, 40, 0, Criticality::High, false, 1.0};
    std::vector<Job> jobs;
    jobs.emplace_back(low, 0, 0);
    jobs.emplace_back(high, 0, 0);

    Scheduler edf(Policy::EDF);
    assert(edf.select(jobs, Mode::Normal) == 0);


    Scheduler staticCriticality(Policy::CriticalityEDF);
    assert(staticCriticality.select(jobs, Mode::Normal) == 1);

    Scheduler rt(Policy::RTDASH);
    assert(rt.select(jobs, Mode::Critical) == 1);
    assert(rt.applyCriticalModeService(jobs, 0, 40, 0.50) == 60);
    assert(jobs[0].remainingMs == 40);

    // Service-floor rounding matches Python's round-to-nearest, ties-to-even.
    TaskSpec halfEvenLow{"half-even-low", 5, 20, 20, Criticality::Low, true, 0.5};
    TaskSpec halfEvenHigh{"half-even-high", 7, 20, 20, Criticality::Low, true, 0.5};
    Job evenLow(halfEvenLow, 0, 0);
    Job evenHigh(halfEvenHigh, 0, 0);
    assert(evenLow.applyServiceFloor() == 3);  // round(2.5) = 2
    assert(evenHigh.applyServiceFloor() == 3); // round(3.5) = 4

    // The recovery-aware variant is high-first while high work is pending,
    // but returns to EDF ordering for a low/medium backlog without leaving the
    // protected mode.
    Scheduler recovery(Policy::RTDASHRecoveryEDF);
    assert(recovery.select(jobs, Mode::Critical) == 1);
    std::vector<Job> recoveryJobs;
    TaskSpec mediumLate{"medium-late", 5, 200, 200, Criticality::Medium, false, 1.0};
    TaskSpec lowUrgent{"low-urgent", 5, 30, 100, Criticality::Low, true, 0.5};
    recoveryJobs.emplace_back(mediumLate, 0, 0);
    recoveryJobs.emplace_back(lowUrgent, 0, 0);
    assert(recovery.select(recoveryJobs, Mode::Critical) == 1);

    // RMS follows period rather than generic application priority.
    TaskSpec shortPeriod{"short", 5, 50, 20, Criticality::Low, false, 1.0};
    TaskSpec longPeriod{"long", 5, 10, 100, Criticality::High, false, 1.0};
    std::vector<Job> rmsJobs;
    rmsJobs.emplace_back(longPeriod, 0, 0);
    rmsJobs.emplace_back(shortPeriod, 0, 0);
    Scheduler rms(Policy::RMS);
    assert(rms.select(rmsJobs, Mode::Normal) == 1);

    // Deterministic tie-breaking uses release time and job identifier.
    TaskSpec equalA{"a", 5, 20, 20, Criticality::Low, false, 1.0};
    TaskSpec equalB{"b", 5, 20, 20, Criticality::Low, false, 1.0};
    std::vector<Job> tied;
    tied.emplace_back(equalB, 0, 0);
    tied.emplace_back(equalA, 0, 0);
    assert(edf.select(tied, Mode::Normal) == 1);

    // Utilization trigger requires the configured hold time; explicit high
    // criticality enters immediately; recovery requires a continuous hold.
    ModeController controller({0.85, 0.65, 100, 200});
    assert(controller.update(0, 0.9, false) == Mode::Normal);
    assert(controller.update(100, 0.9, false) == Mode::Critical);
    assert(controller.update(200, 0.5, false) == Mode::Critical);
    assert(controller.update(400, 0.5, false) == Mode::Normal);

    ModeController eventController({0.85, 0.65, 100, 200});
    assert(eventController.update(17, 0.1, true) == Mode::Critical);

    // Resource reservations are atomic across all dimensions and are released
    // exactly once.
    ResourceManager resources({100, 200, 500, 100});
    assert(resources.reserve("job-a", {30, 50, 100, 10}));
    assert(!resources.reserve("job-a", {1, 1, 1, 1}));
    const auto beforeFailure = resources.used();
    assert(!resources.reserve("job-b", {80, 10, 10, 10}));
    const auto afterFailure = resources.used();
    assert(close(beforeFailure.cpu, afterFailure.cpu));
    assert(close(beforeFailure.memory, afterFailure.memory));
    assert(resources.reserve("job-c", {60, 100, 200, 50}));
    assert(resources.release("job-a"));
    assert(!resources.release("job-a"));
    const auto remaining = resources.used();
    assert(close(remaining.cpu, 60));
    assert(close(remaining.memory, 100));
    assert(resources.release("job-c"));
    const auto empty = resources.used();
    assert(close(empty.cpu, 0));
    assert(close(empty.memory, 0));
    assert(close(empty.storage, 0));
    assert(close(empty.bandwidth, 0));
    return 0;
}
