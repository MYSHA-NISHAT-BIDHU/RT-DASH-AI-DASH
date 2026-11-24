#include "rtdash/Scheduler.hpp"

#include <algorithm>
#include <cstdint>
#include <deque>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <string>
#include <vector>

namespace {
using namespace rtdash;

struct RuntimeJob {
    Job job;
    std::uint64_t firstStart{UINT64_MAX};
    std::uint64_t completion{UINT64_MAX};
    std::uint32_t preemptions{0};
    bool complete{false};
    bool dropped{false};

    RuntimeJob(TaskSpec spec, std::uint32_t seq, std::uint64_t release)
        : job(std::move(spec), seq, release) {}
};

struct Summary {
    std::string policy;
    std::size_t released{};
    std::size_t completed{};
    std::size_t highReleased{};
    std::size_t highMisses{};
    double highMeanResponse{};
    std::size_t lowReleased{};
    std::size_t lowCompleted{};
    std::size_t transitions{};
    std::size_t contextSwitches{};
    double utilization{};
};

std::string policyName(Policy p) {
    switch (p) {
        case Policy::EDF: return "edf";
        case Policy::RMS: return "rms";
        case Policy::CriticalityEDF: return "criticality_edf";
        case Policy::RTDASH: return "rt_dash";
        case Policy::RTDASHRecoveryEDF: return "rt_dash_recovery_edf";
    }
    return "unknown";
}

Summary runPolicy(Policy policy) {
    constexpr std::uint64_t duration = 20000;
    constexpr std::uint32_t quantum = 10;
    std::vector<TaskSpec> periodic{
        {"temperature", 12, 100, 100, Criticality::Medium, false, 1.0},
        {"motion", 8, 80, 80, Criticality::Medium, false, 1.0},
        {"energy", 18, 250, 250, Criticality::Medium, false, 1.0},
        {"lighting", 15, 60, 120, Criticality::Low, true, 0.5},
        {"display", 20, 50, 100, Criticality::Low, true, 0.25},
        {"comfort", 30, 150, 200, Criticality::Low, true, 0.4},
    };
    std::vector<std::pair<std::uint64_t, TaskSpec>> events;
    for (auto base : {std::uint64_t{5000}, std::uint64_t{12000}}) {
        events.push_back({base, {"fire", 90, 180, 0, Criticality::High, false, 1.0}});
        events.push_back({base + 10, {"intrusion", 75, 160, 0, Criticality::High, false, 1.0}});
        events.push_back({base + 20, {"gas", 100, 200, 0, Criticality::High, false, 1.0}});
    }

    Scheduler scheduler(policy);
    ModeController controller({0.85, 0.65, 200, 1000});
    std::map<std::string, std::uint32_t> sequences;
    std::vector<RuntimeJob> all;
    std::vector<std::size_t> ready;
    std::deque<double> busyHistory;
    std::size_t runningIndex = static_cast<std::size_t>(-1);
    std::size_t lastRunningIndex = static_cast<std::size_t>(-1);
    std::size_t transitions = 0;
    std::size_t contextSwitches = 0;
    std::uint64_t busy = 0;
    Mode previousMode = Mode::Normal;

    auto releaseJob = [&](const TaskSpec& task, std::uint64_t now) {
        auto seq = sequences[task.id]++;
        all.emplace_back(task, seq, now);
        ready.push_back(all.size() - 1);
    };

    for (std::uint64_t now = 0; now < duration; now += quantum) {
        for (const auto& task : periodic) {
            if (now % task.periodMs == 0) {
                releaseJob(task, now);
            }
        }
        for (const auto& [release, task] : events) {
            if (release == now) {
                releaseJob(task, now);
            }
        }

        const bool highPending = std::any_of(ready.begin(), ready.end(), [&](std::size_t idx) {
            return !all[idx].complete && all[idx].job.task.criticality == Criticality::High;
        });
        const double observed = busyHistory.empty()
            ? 0.0
            : std::accumulate(busyHistory.begin(), busyHistory.end(), 0.0) /
              static_cast<double>(busyHistory.size());
        const bool adaptive = policy == Policy::RTDASH || policy == Policy::RTDASHRecoveryEDF;
        Mode mode = adaptive ? controller.update(now, observed, highPending) : Mode::Normal;
        if (mode != previousMode) {
            ++transitions;
            previousMode = mode;
        }

        // Firm-deadline semantics: stale jobs are removed at their absolute deadline.
        for (auto idx : ready) {
            if (!all[idx].complete && !all[idx].dropped &&
                now >= all[idx].job.absoluteDeadlineMs && all[idx].job.remainingMs > 0) {
                all[idx].dropped = true;
            }
        }
        ready.erase(std::remove_if(ready.begin(), ready.end(), [&](std::size_t idx) {
            return all[idx].complete || all[idx].dropped;
        }), ready.end());

        if (mode == Mode::Critical && adaptive) {
            std::vector<Job> serviceCandidates;
            serviceCandidates.reserve(ready.size());
            for (auto idx : ready) {
                serviceCandidates.push_back(all[idx].job);
            }
            scheduler.applyCriticalModeService(serviceCandidates, now, 1000, 0.85);
            for (std::size_t local = 0; local < ready.size(); ++local) {
                const auto idx = ready[local];
                all[idx].job = serviceCandidates[local];
                if (all[idx].job.remainingMs == 0) {
                    all[idx].complete = true;
                    all[idx].completion = now;
                }
            }
            ready.erase(std::remove_if(ready.begin(), ready.end(), [&](std::size_t idx) {
                return all[idx].complete || all[idx].dropped;
            }), ready.end());
        }

        std::uint32_t elapsed = 0;
        std::uint32_t busyThisQuantum = 0;
        while (elapsed < quantum) {
            std::vector<Job> candidates;
            std::vector<std::size_t> candidateMap;
            for (auto idx : ready) {
                if (!all[idx].complete && !all[idx].dropped && all[idx].job.remainingMs > 0) {
                    candidates.push_back(all[idx].job);
                    candidateMap.push_back(idx);
                }
            }
            if (candidates.empty()) {
                runningIndex = static_cast<std::size_t>(-1);
                lastRunningIndex = static_cast<std::size_t>(-1);
                break;
            }

            const auto chosenLocal = scheduler.select(candidates, mode);
            const auto chosen = candidateMap[chosenLocal];
            if (runningIndex != static_cast<std::size_t>(-1) && runningIndex != chosen &&
                !all[runningIndex].complete && !all[runningIndex].dropped) {
                ++all[runningIndex].preemptions;
            }
            runningIndex = chosen;
            if (all[chosen].firstStart == UINT64_MAX) all[chosen].firstStart = now + elapsed;
            if (lastRunningIndex != chosen) ++contextSwitches;
            lastRunningIndex = chosen;

            const auto available = quantum - elapsed;
            const auto executed = std::min<std::uint32_t>(available, all[chosen].job.remainingMs);
            all[chosen].job.remainingMs -= executed;
            busy += executed;
            busyThisQuantum += executed;
            elapsed += executed;
            if (all[chosen].job.remainingMs == 0) {
                all[chosen].complete = true;
                all[chosen].completion = now + elapsed;
                ready.erase(std::remove(ready.begin(), ready.end(), chosen), ready.end());
                runningIndex = static_cast<std::size_t>(-1);
            }
            if (executed == 0) break;
        }
        busyHistory.push_back(static_cast<double>(busyThisQuantum) / quantum);
        if (busyHistory.size() > 100) busyHistory.pop_front();
    }

    Summary s;
    s.policy = policyName(policy);
    s.released = all.size();
    s.transitions = transitions;
    s.contextSwitches = contextSwitches;
    s.utilization = static_cast<double>(busy) / duration;
    double highResponseTotal = 0.0;
    for (const auto& r : all) {
        if (r.complete) ++s.completed;
        if (r.job.task.criticality == Criticality::High) {
            ++s.highReleased;
            if (!r.complete || r.completion > r.job.absoluteDeadlineMs) ++s.highMisses;
            if (r.complete) highResponseTotal += static_cast<double>(r.completion - r.job.releaseMs);
        }
        if (r.job.task.criticality == Criticality::Low) {
            ++s.lowReleased;
            if (r.complete) ++s.lowCompleted;
        }
    }
    s.highMeanResponse = s.highReleased ? highResponseTotal / s.highReleased : 0.0;
    return s;
}
} // namespace

int main() {
    std::cout << "policy,released,completed,high_released,high_misses,high_mean_response_ms,low_released,low_completed,mode_transitions,context_switches,processor_utilization\n";
    for (auto policy : {rtdash::Policy::EDF, rtdash::Policy::RMS, rtdash::Policy::CriticalityEDF, rtdash::Policy::RTDASH, rtdash::Policy::RTDASHRecoveryEDF}) {
        const auto s = runPolicy(policy);
        std::cout << s.policy << ',' << s.released << ',' << s.completed << ',' << s.highReleased << ','
                  << s.highMisses << ',' << std::fixed << std::setprecision(3) << s.highMeanResponse << ','
                  << s.lowReleased << ',' << s.lowCompleted << ',' << s.transitions << ','
                  << s.contextSwitches << ',' << std::setprecision(6) << s.utilization << '\n';
    }
    return 0;
}
