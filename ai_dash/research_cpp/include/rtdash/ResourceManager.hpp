#pragma once

#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>

namespace rtdash {

struct ResourceVector {
    double cpu{0.0};
    double memory{0.0};
    double storage{0.0};
    double bandwidth{0.0};
};

class ResourceManager {
public:
    explicit ResourceManager(ResourceVector capacity);

    // Transactional all-or-nothing reservation. A job identifier may own at
    // most one reservation. No counter is modified when admission fails.
    bool reserve(const std::string& jobId, const ResourceVector& demand);

    // Release exactly the reservation associated with jobId. Returns false for
    // unknown/already-released identifiers, preventing double release.
    bool release(const std::string& jobId);

    [[nodiscard]] ResourceVector capacity() const;
    [[nodiscard]] ResourceVector used() const;
    [[nodiscard]] std::optional<ResourceVector> allocation(const std::string& jobId) const;

private:
    static void validate(const ResourceVector& value);
    static bool fits(const ResourceVector& used, const ResourceVector& demand,
                     const ResourceVector& capacity);

    ResourceVector capacity_;
    ResourceVector used_{};
    std::unordered_map<std::string, ResourceVector> allocations_;
    mutable std::mutex mutex_;
};

} // namespace rtdash
