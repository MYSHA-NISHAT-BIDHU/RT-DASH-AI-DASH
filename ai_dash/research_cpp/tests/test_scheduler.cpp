#include "rtdash/ResourceManager.hpp"
#include "rtdash/PortableLogisticModel.hpp"
#include "rtdash/Scheduler.hpp"

#include <cmath>
#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>

namespace {
bool close(double left, double right) {
    return std::abs(left - right) < 1e-9;
}

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error("C++ validation failure: " + message);
    }
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
    require(edf.select(jobs, Mode::Normal) == 0, "EDF must select the earliest absolute deadline");


    Scheduler staticCriticality(Policy::CriticalityEDF);
    require(staticCriticality.select(jobs, Mode::Normal) == 1, "static criticality-first must select high-criticality work");

    Scheduler rt(Policy::RTDASH);
    require(rt.select(jobs, Mode::Critical) == 1, "RT-DASH Critical Mode must select high-criticality work");
    require(rt.applyCriticalModeService(jobs) == 60, "service control must remove the expected optional work");
    require(jobs[0].remainingMs == 40, "service control must preserve the configured service floor");

    // The recovery-aware variant is high-first while high work is pending,
    // but returns to EDF ordering for a low/medium backlog without leaving the
    // protected mode.
    Scheduler recovery(Policy::RTDASHRecoveryEDF);
    require(recovery.select(jobs, Mode::Critical) == 1, "recovery-aware policy must remain high-first while high work is pending");
    std::vector<Job> recoveryJobs;
    TaskSpec mediumLate{"medium-late", 5, 200, 200, Criticality::Medium, false, 1.0};
    TaskSpec lowUrgent{"low-urgent", 5, 30, 100, Criticality::Low, true, 0.5};
    recoveryJobs.emplace_back(mediumLate, 0, 0);
    recoveryJobs.emplace_back(lowUrgent, 0, 0);
    require(recovery.select(recoveryJobs, Mode::Critical) == 1, "recovery-aware policy must return to EDF for low/medium backlog");

    // RMS follows period rather than generic application priority.
    TaskSpec shortPeriod{"short", 5, 50, 20, Criticality::Low, false, 1.0};
    TaskSpec longPeriod{"long", 5, 10, 100, Criticality::High, false, 1.0};
    std::vector<Job> rmsJobs;
    rmsJobs.emplace_back(longPeriod, 0, 0);
    rmsJobs.emplace_back(shortPeriod, 0, 0);
    Scheduler rms(Policy::RMS);
    require(rms.select(rmsJobs, Mode::Normal) == 1, "RMS must select the shortest-period task");

    // Utilization trigger requires the configured hold time; explicit high
    // criticality enters immediately; recovery requires a continuous hold.
    ModeController controller({0.85, 0.65, 100, 200});
    require(controller.update(0, 0.9, false) == Mode::Normal, "utilization entry must respect the hold time");
    require(controller.update(100, 0.9, false) == Mode::Critical, "utilization entry must occur after the configured hold");
    require(controller.update(200, 0.5, false) == Mode::Critical, "recovery must respect the configured hold");
    require(controller.update(400, 0.5, false) == Mode::Normal, "recovery must return to Normal after the hold");

    ModeController eventController({0.85, 0.65, 100, 200});
    require(eventController.update(17, 0.1, true) == Mode::Critical, "semantic high-criticality entry must be immediate");

    // Resource reservations are atomic across all dimensions and are released
    // exactly once.
    ResourceManager resources({100, 200, 500, 100});
    require(resources.reserve("job-a", {30, 50, 100, 10}), "first resource reservation must succeed");
    require(!resources.reserve("job-a", {1, 1, 1, 1}), "duplicate resource reservation must be rejected");
    const auto beforeFailure = resources.used();
    require(!resources.reserve("job-b", {80, 10, 10, 10}), "over-capacity reservation must fail atomically");
    const auto afterFailure = resources.used();
    require(close(beforeFailure.cpu, afterFailure.cpu), "failed reservation must not change CPU accounting");
    require(close(beforeFailure.memory, afterFailure.memory), "failed reservation must not change memory accounting");
    require(resources.reserve("job-c", {60, 100, 200, 50}), "second valid resource reservation must succeed");
    require(resources.release("job-a"), "reserved resource set must release once");
    require(!resources.release("job-a"), "duplicate release must be rejected");
    const auto remaining = resources.used();
    require(close(remaining.cpu, 60), "resource accounting after release must preserve remaining CPU reservation");
    require(close(remaining.memory, 100), "resource accounting after release must preserve remaining memory reservation");
    require(resources.release("job-c"), "final resource reservation must release");
    const auto empty = resources.used();
    require(close(empty.cpu, 0), "CPU accounting must return to zero");
    require(close(empty.memory, 0), "memory accounting must return to zero");
    require(close(empty.storage, 0), "storage accounting must return to zero");
    require(close(empty.bandwidth, 0), "bandwidth accounting must return to zero");

    // Portable AI inference uses a stable sigmoid and validates dimensions.
    PortableLogisticModel predictor(
        {0.0, 1.0}, {1.0, 2.0}, {2.0, -1.0}, 0.25);
    require(predictor.featureCount() == 2, "portable predictor feature count must match the model");
    const double risk = predictor.risk({1.0, 1.0});
    require(close(risk, 1.0 / (1.0 + std::exp(-2.25))), "portable predictor sigmoid output must match the reference calculation");
    require(predictor.shouldTrigger({1.0, 1.0}, 0.8), "portable predictor must trigger above threshold");
    bool rejected = false;
    try {
        static_cast<void>(predictor.risk({1.0}));
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "portable predictor must reject the wrong feature dimension");
    return 0;
}
