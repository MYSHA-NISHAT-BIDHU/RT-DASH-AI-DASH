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

    [[nodiscard]] std::string jobId() const {
        return task.id + "#" + std::to_string(sequence);
    }

    [[nodiscard]] static std::uint32_t roundTiesToEven(double value) {
        const double lower = std::floor(value);
        const double fraction = value - lower;
        if (fraction < 0.5) {
            return static_cast<std::uint32_t>(lower);
        }
        if (fraction > 0.5) {
            return static_cast<std::uint32_t>(lower + 1.0);
        }
        const auto integer = static_cast<std::uint64_t>(lower);
        return static_cast<std::uint32_t>((integer % 2U == 0U) ? integer : integer + 1U);
    }

    [[nodiscard]] std::uint32_t optionalRemaining() const {
        if (!task.degradable) {
            return 0;
        }
        const auto mandatoryTotal = roundTiesToEven(
            static_cast<double>(originalBudgetMs) * task.minimumServiceFraction);
        const auto executed = originalBudgetMs - remainingMs - serviceReductionMs;
        const auto targetRemaining = mandatoryTotal > executed ? mandatoryTotal - executed : 0U;
        return remainingMs > targetRemaining ? remainingMs - targetRemaining : 0U;
    }

    std::uint32_t reduceOptional(std::uint32_t maximum) {
        const auto removed = std::min(optionalRemaining(), maximum);
        remainingMs -= removed;
        serviceReductionMs += removed;
        degradationApplied = degradationApplied || removed > 0;
        return removed;
    }

    std::uint32_t applyServiceFloor() {
        return reduceOptional(optionalRemaining());
    }
};

} // namespace rtdash
