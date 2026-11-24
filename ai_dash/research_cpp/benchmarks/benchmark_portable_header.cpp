#include "portable_logistic_model.h"

#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <vector>

int main(int argc, char **argv) {
    const std::size_t iterations = argc > 1
        ? static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10))
        : 1000000u;
    const std::size_t warmup = argc > 2
        ? static_cast<std::size_t>(std::strtoull(argv[2], nullptr, 10))
        : 100000u;
    if (iterations == 0u) return 2;

    std::vector<double> features(RTDASH_AI_FEATURE_COUNT, 0.0);
    for (std::size_t index = 0; index < features.size(); ++index) {
        features[index] = static_cast<double>((index * 7u) % 11u) / 10.0;
    }

    volatile double checksum = 0.0;
    for (std::size_t index = 0; index < warmup; ++index) {
        features[0] = static_cast<double>(index & 1u);
        checksum += rtdash_ai_risk(features.data(), features.size());
    }

    const auto started = std::chrono::steady_clock::now();
    for (std::size_t index = 0; index < iterations; ++index) {
        features[0] = static_cast<double>(index & 1u);
        checksum += rtdash_ai_risk(features.data(), features.size());
    }
    const auto stopped = std::chrono::steady_clock::now();
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        stopped - started
    ).count();
    const double per_inference = static_cast<double>(elapsed) /
        static_cast<double>(iterations);

    std::cout << std::setprecision(17)
              << "{\"iterations\":" << iterations
              << ",\"warmup\":" << warmup
              << ",\"elapsed_ns\":" << elapsed
              << ",\"ns_per_inference\":" << per_inference
              << ",\"checksum\":" << checksum
              << "}\n";
    return std::isfinite(checksum) ? 0 : 3;
}
