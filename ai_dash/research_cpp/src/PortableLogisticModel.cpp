#include "rtdash/PortableLogisticModel.hpp"

#include <cmath>
#include <stdexcept>
#include <utility>

namespace rtdash {

PortableLogisticModel::PortableLogisticModel(
    std::vector<double> mean,
    std::vector<double> scale,
    std::vector<double> weights,
    double intercept)
    : mean_(std::move(mean)),
      scale_(std::move(scale)),
      weights_(std::move(weights)),
      intercept_(intercept) {
    if (mean_.empty() || mean_.size() != scale_.size() ||
        mean_.size() != weights_.size()) {
        throw std::invalid_argument("portable model vectors must have equal nonzero size");
    }
    for (const double value : scale_) {
        if (!(value > 0.0) || !std::isfinite(value)) {
            throw std::invalid_argument("portable model scales must be finite and positive");
        }
    }
}

std::size_t PortableLogisticModel::featureCount() const noexcept {
    return mean_.size();
}

double PortableLogisticModel::risk(const std::vector<double>& features) const {
    if (features.size() != featureCount()) {
        throw std::invalid_argument("feature count does not match portable model");
    }
    double score = intercept_;
    for (std::size_t index = 0; index < features.size(); ++index) {
        if (!std::isfinite(features[index])) {
            throw std::invalid_argument("features must be finite");
        }
        score += ((features[index] - mean_[index]) / scale_[index]) * weights_[index];
    }
    if (score >= 0.0) {
        return 1.0 / (1.0 + std::exp(-score));
    }
    const double exponential = std::exp(score);
    return exponential / (1.0 + exponential);
}

bool PortableLogisticModel::shouldTrigger(
    const std::vector<double>& features,
    const double threshold) const {
    if (threshold < 0.0 || threshold > 1.0) {
        throw std::invalid_argument("threshold must be in [0, 1]");
    }
    return risk(features) >= threshold;
}

}  // namespace rtdash
