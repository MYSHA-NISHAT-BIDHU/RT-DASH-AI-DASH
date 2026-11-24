#include "rtdash/ResourceManager.hpp"

#include <cmath>
#include <stdexcept>

namespace rtdash {
namespace {
constexpr double epsilon = 1e-9;

void add(ResourceVector& left, const ResourceVector& right) {
    left.cpu += right.cpu;
    left.memory += right.memory;
    left.storage += right.storage;
    left.bandwidth += right.bandwidth;
}

void subtract(ResourceVector& left, const ResourceVector& right) {
    left.cpu -= right.cpu;
    left.memory -= right.memory;
    left.storage -= right.storage;
    left.bandwidth -= right.bandwidth;

    // Remove insignificant floating-point residue without hiding material
    // accounting errors.
    if (std::abs(left.cpu) < epsilon) left.cpu = 0.0;
    if (std::abs(left.memory) < epsilon) left.memory = 0.0;
    if (std::abs(left.storage) < epsilon) left.storage = 0.0;
    if (std::abs(left.bandwidth) < epsilon) left.bandwidth = 0.0;
}
} // namespace

ResourceManager::ResourceManager(ResourceVector capacity) : capacity_(capacity) {
    validate(capacity_);
}

void ResourceManager::validate(const ResourceVector& value) {
    if (!std::isfinite(value.cpu) || !std::isfinite(value.memory) ||
        !std::isfinite(value.storage) || !std::isfinite(value.bandwidth) ||
        value.cpu < 0.0 || value.memory < 0.0 || value.storage < 0.0 ||
        value.bandwidth < 0.0) {
        throw std::invalid_argument("resource values must be finite and non-negative");
    }
}

bool ResourceManager::fits(const ResourceVector& used, const ResourceVector& demand,
                           const ResourceVector& capacity) {
    return used.cpu + demand.cpu <= capacity.cpu + epsilon &&
           used.memory + demand.memory <= capacity.memory + epsilon &&
           used.storage + demand.storage <= capacity.storage + epsilon &&
           used.bandwidth + demand.bandwidth <= capacity.bandwidth + epsilon;
}

bool ResourceManager::reserve(const std::string& jobId, const ResourceVector& demand) {
    if (jobId.empty()) {
        throw std::invalid_argument("jobId must be non-empty");
    }
    validate(demand);
    std::lock_guard<std::mutex> guard(mutex_);
    if (allocations_.find(jobId) != allocations_.end() ||
        !fits(used_, demand, capacity_)) {
        return false;
    }
    add(used_, demand);
    allocations_.emplace(jobId, demand);
    return true;
}

bool ResourceManager::release(const std::string& jobId) {
    std::lock_guard<std::mutex> guard(mutex_);
    const auto found = allocations_.find(jobId);
    if (found == allocations_.end()) {
        return false;
    }
    subtract(used_, found->second);
    allocations_.erase(found);
    return true;
}

ResourceVector ResourceManager::capacity() const {
    std::lock_guard<std::mutex> guard(mutex_);
    return capacity_;
}

ResourceVector ResourceManager::used() const {
    std::lock_guard<std::mutex> guard(mutex_);
    return used_;
}

std::optional<ResourceVector> ResourceManager::allocation(const std::string& jobId) const {
    std::lock_guard<std::mutex> guard(mutex_);
    const auto found = allocations_.find(jobId);
    if (found == allocations_.end()) {
        return std::nullopt;
    }
    return found->second;
}

} // namespace rtdash
