#include "rtdash/Scheduler.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
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
            return std::tuple{leftPeriod, -static_cast<int>(left.task.criticality), left.absoluteDeadlineMs, left.jobId()} <
                   std::tuple{rightPeriod, -static_cast<int>(right.task.criticality), right.absoluteDeadlineMs, right.jobId()};
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
            return std::tuple{leftCrit, left.absoluteDeadlineMs, left.releaseMs, left.jobId()} <
                   std::tuple{rightCrit, right.absoluteDeadlineMs, right.releaseMs, right.jobId()};
        }
        const auto leftCrit = -static_cast<int>(left.task.criticality);
        const auto rightCrit = -static_cast<int>(right.task.criticality);
        return std::tuple{left.absoluteDeadlineMs, leftCrit, left.releaseMs, left.jobId()} <
               std::tuple{right.absoluteDeadlineMs, rightCrit, right.releaseMs, right.jobId()};
    };

    std::size_t best = 0;
    for (std::size_t index = 1; index < ready.size(); ++index) {
        if (better(ready[index], ready[best])) {
            best = index;
        }
    }
    return best;
}

std::uint32_t Scheduler::applyCriticalModeService(
    std::vector<Job>& ready,
    std::uint64_t nowMs,
    std::uint64_t observationWindowMs,
    double utilizationHigh) const {
    if (policy_ != Policy::RTDASH && policy_ != Policy::RTDASHRecoveryEDF) {
        return 0;
    }
    if (observationWindowMs == 0 || utilizationHigh < 0.0 || utilizationHigh > 1.0) {
        throw std::invalid_argument("invalid controlled-degradation parameters");
    }

    const auto horizonEnd = nowMs + observationWindowMs;
    std::uint64_t estimatedDemand = 0;
    for (const auto& job : ready) {
        if (job.absoluteDeadlineMs <= horizonEnd) {
            estimatedDemand += job.remainingMs;
        }
    }
    const double capacity = utilizationHigh * static_cast<double>(observationWindowMs);
    const double excess = std::max(0.0, static_cast<double>(estimatedDemand) - capacity);
    if (excess <= 0.0) {
        return 0;
    }

    std::vector<std::size_t> candidates;
    for (std::size_t index = 0; index < ready.size(); ++index) {
        const auto& job = ready[index];
        if (job.task.criticality == Criticality::Low && job.task.degradable &&
            job.optionalRemaining() > 0) {
            candidates.push_back(index);
        }
    }
    std::sort(candidates.begin(), candidates.end(), [&ready](std::size_t left, std::size_t right) {
        const auto& a = ready[left];
        const auto& b = ready[right];
        return std::tuple{a.task.minimumServiceFraction, -static_cast<std::int64_t>(a.absoluteDeadlineMs), a.jobId()} <
               std::tuple{b.task.minimumServiceFraction, -static_cast<std::int64_t>(b.absoluteDeadlineMs), b.jobId()};
    });

    std::uint32_t total = 0;
    for (const auto index : candidates) {
        const double remainingExcess = std::max(0.0, excess - static_cast<double>(total));
        const auto required64 = static_cast<std::uint64_t>(std::ceil(remainingExcess));
        const auto required = static_cast<std::uint32_t>(
            std::min<std::uint64_t>(required64, std::numeric_limits<std::uint32_t>::max()));
        total += ready[index].reduceOptional(required);
        if (static_cast<double>(total) >= excess) {
            break;
        }
    }
    return total;
}

} // namespace rtdash
