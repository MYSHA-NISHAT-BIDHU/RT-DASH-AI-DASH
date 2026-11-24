#pragma once

#include <cstddef>
#include <vector>

namespace rtdash {

// Allocation occurs only during construction. `risk` itself is deterministic,
// read-only and suitable for a statically constructed embedded adapter.
class PortableLogisticModel {
public:
    PortableLogisticModel(
        std::vector<double> mean,
        std::vector<double> scale,
        std::vector<double> weights,
        double intercept);

    [[nodiscard]] std::size_t featureCount() const noexcept;
    [[nodiscard]] double risk(const std::vector<double>& features) const;
    [[nodiscard]] bool shouldTrigger(
        const std::vector<double>& features,
        double threshold) const;

private:
    std::vector<double> mean_;
    std::vector<double> scale_;
    std::vector<double> weights_;
    double intercept_;
};

}  // namespace rtdash
