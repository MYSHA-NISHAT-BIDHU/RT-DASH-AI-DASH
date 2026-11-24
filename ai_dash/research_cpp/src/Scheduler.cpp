#include "rtdash/Scheduler.hpp"

#include <algorithm>
#include <tuple>

namespace rtdash {

ModeController::ModeController(ModeConfig config) : config_(config) {
    if (!(0.0 <= config_.utilizationLow && config_.utilizationLow < config_.utilizationHigh &&
          config_.utilizationHigh <= 1.0)) {
        throw std::invalid_argument("invalid utilization thresholds");
    }
}

Mode ModeController::update(
    std::uint64_t nowMs, double smoothedUtilization, bool highCriticalityPending) {
    if (mode_ == Mode::Normal) {
        if (highCriticalityPending) {
            mode_ = Mode::Critical;
            highSince_.reset();
            recoverySince_.reset();
        } else if (smoothedUtilization >= config_.utilizationHigh) {
            if (!highSince_) {
                highSince_ = nowMs;
            }
            if (nowMs - *highSince_ >= config_.entryHoldMs) {
                mode_ = Mode::Critical;
                highSince_.reset();
            }
        } else {
            highSince_.reset();
        }
    } else {
        if (highCriticalityPending || smoothedUtilization > config_.utilizationLow) {
            recoverySince_.reset();
        } else {
            if (!recoverySince_) {
                recoverySince_ = nowMs;
            }
            if (nowMs - *recoverySince_ >= config_.recoveryHoldMs) {
                mode_ = Mode::Normal;
                recoverySince_.reset();
            }
        }
    }
    return mode_;
}

std::size_t Scheduler::select(const std::vector<Job>& ready, Mode mode) const {
    if (ready.empty()) {
        throw std::invalid_argument("cannot select from an empty ready set");
    }
    auto better = [this, mode, &ready](const Job& left, const Job& right) {
        if (policy_ == Policy::RMS) {
            const auto leftPeriod = left.task.periodMs == 0 ? left.task.relativeDeadlineMs : left.task.periodMs;
            const auto rightPeriod = right.task.periodMs == 0 ? right.task.relativeDeadlineMs : right.task.periodMs;
            return std::tie(leftPeriod, left.absoluteDeadlineMs) <
                   std::tie(rightPeriod, right.absoluteDeadlineMs);
        }
        const bool highPending = std::any_of(
            ready.begin(), ready.end(), [](const Job& job) {
                return job.task.criticality == Criticality::High && job.remainingMs > 0;
            });
        const bool criticalOrdering =
            policy_ == Policy::CriticalityEDF ||
            (policy_ == Policy::RTDASH && mode == Mode::Critical) ||
            (policy_ == Policy::RTDASHRecoveryEDF && mode == Mode::Critical && highPending);
        if (criticalOrdering) {
            const auto leftCrit = -static_cast<int>(left.task.criticality);
            const auto rightCrit = -static_cast<int>(right.task.criticality);
            return std::tie(leftCrit, left.absoluteDeadlineMs) <
                   std::tie(rightCrit, right.absoluteDeadlineMs);
        }
        const auto leftCrit = -static_cast<int>(left.task.criticality);
        const auto rightCrit = -static_cast<int>(right.task.criticality);
        return std::tie(left.absoluteDeadlineMs, leftCrit) <
               std::tie(right.absoluteDeadlineMs, rightCrit);
    };

    std::size_t best = 0;
    for (std::size_t index = 1; index < ready.size(); ++index) {
        if (better(ready[index], ready[best])) {
            best = index;
        }
    }
    return best;
}

std::uint32_t Scheduler::applyCriticalModeService(std::vector<Job>& ready) const {
    if (policy_ != Policy::RTDASH && policy_ != Policy::RTDASHRecoveryEDF) {
        return 0;
    }
    std::uint32_t total = 0;
    for (auto& job : ready) {
        if (job.task.criticality == Criticality::Low) {
            total += job.applyServiceFloor();
        }
    }
    return total;
}

} // namespace rtdash
