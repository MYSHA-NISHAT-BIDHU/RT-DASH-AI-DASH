#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace rtdash {

enum class Criticality : std::uint8_t { Low = 1, Medium = 2, High = 3 };

enum class Mode : std::uint8_t { Normal, Critical };

struct TaskSpec {
    std::string id;
    std::uint32_t wcetMs{};
    std::uint32_t relativeDeadlineMs{};
    std::uint32_t periodMs{}; // 0 denotes a one-shot event task.
    Criticality criticality{Criticality::Low};
    bool degradable{false};
    double minimumServiceFraction{1.0};

    void validate() const {
        if (id.empty() || wcetMs == 0 || relativeDeadlineMs == 0) {
            throw std::invalid_argument("invalid task parameters");
        }
        if (minimumServiceFraction < 0.0 || minimumServiceFraction > 1.0) {
            throw std::invalid_argument("minimumServiceFraction must be in [0,1]");
        }
        if (!degradable && minimumServiceFraction != 1.0) {
            throw std::invalid_argument("non-degradable task must retain full service");
        }
        if (criticality == Criticality::High && minimumServiceFraction < 1.0) {
            throw std::invalid_argument("high-criticality service cannot be reduced");
        }
    }
};

struct Job {
    TaskSpec task;
    std::uint32_t sequence{};
    std::uint64_t releaseMs{};
    std::uint64_t absoluteDeadlineMs{};
    std::uint32_t originalBudgetMs{};
    std::uint32_t remainingMs{};
    std::uint32_t serviceReductionMs{};
    bool degradationApplied{false};

    Job(TaskSpec spec, std::uint32_t seq, std::uint64_t release)
        : task(std::move(spec)), sequence(seq), releaseMs(release),
          absoluteDeadlineMs(release + task.relativeDeadlineMs),
          originalBudgetMs(task.wcetMs), remainingMs(task.wcetMs) {
        task.validate();
    }

    std::uint32_t applyServiceFloor() {
        if (degradationApplied || !task.degradable) {
            return 0;
        }
        const auto mandatoryTotal = static_cast<std::uint32_t>(
            std::lround(static_cast<double>(originalBudgetMs) * task.minimumServiceFraction));
        const auto executed = originalBudgetMs - remainingMs;
        const auto targetRemaining = mandatoryTotal > executed ? mandatoryTotal - executed : 0U;
        const auto removed = remainingMs > targetRemaining ? remainingMs - targetRemaining : 0U;
        remainingMs -= removed;
        serviceReductionMs += removed;
        degradationApplied = true;
        return removed;
    }
};

} // namespace rtdash
