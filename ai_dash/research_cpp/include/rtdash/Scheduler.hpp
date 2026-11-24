#pragma once

#include "rtdash/Task.hpp"
#include <cstdint>
#include <optional>
#include <vector>

namespace rtdash {

enum class Policy : std::uint8_t { EDF, RMS, CriticalityEDF, RTDASH, RTDASHRecoveryEDF };

struct ModeConfig {
    double utilizationHigh{0.85};
    double utilizationLow{0.65};
    std::uint64_t entryHoldMs{200};
    std::uint64_t recoveryHoldMs{1000};
};

class ModeController {
public:
    explicit ModeController(ModeConfig config = {});
    Mode update(std::uint64_t nowMs, double smoothedUtilization, bool highCriticalityPending);
    [[nodiscard]] Mode mode() const noexcept { return mode_; }

private:
    ModeConfig config_;
    Mode mode_{Mode::Normal};
    std::optional<std::uint64_t> highSince_;
    std::optional<std::uint64_t> recoverySince_;
};

class Scheduler {
public:
    explicit Scheduler(Policy policy) : policy_(policy) {}
    [[nodiscard]] std::size_t select(const std::vector<Job>& ready, Mode mode) const;
    std::uint32_t applyCriticalModeService(std::vector<Job>& ready) const;

private:
    Policy policy_;
};

} // namespace rtdash
