#include "allocation.h"

#include "aec_device_abi.h"
#include "error.h"

#include <condition_variable>
#include <map>
#include <mutex>
#include <utility>

namespace aec {

struct AllocationRecord {
    AllocationRecord(aecDevicePtr allocation_base, uint64_t allocation_size)
        : base(allocation_base), size(allocation_size) {}

    const aecDevicePtr base;
    const uint64_t size;
    std::mutex mutex;
    std::condition_variable condition;
    uint64_t pending_references = 0;
    bool closing = false;
};

namespace {

struct AllocationRegistry {
    std::mutex mutex;
    std::map<aecDevicePtr, std::shared_ptr<AllocationRecord>> live;
};

AllocationRegistry &registry() {
    static AllocationRegistry value;
    return value;
}

} // namespace

AllocationLease::AllocationLease(std::shared_ptr<AllocationRecord> record) noexcept
    : record_(std::move(record)) {}

AllocationLease::AllocationLease(AllocationLease &&other) noexcept
    : record_(std::move(other.record_)) {}

AllocationLease &AllocationLease::operator=(AllocationLease &&other) noexcept {
    if (this != &other) {
        release();
        record_ = std::move(other.record_);
    }
    return *this;
}

AllocationLease::~AllocationLease() {
    release();
}

void AllocationLease::release() noexcept {
    if (record_ == nullptr) return;
    std::shared_ptr<AllocationRecord> record = std::move(record_);
    {
        std::lock_guard<std::mutex> lock(record->mutex);
        if (record->pending_references > 0) {
            --record->pending_references;
        }
    }
    record->condition.notify_all();
}

aecError_t allocate_device(aecDevicePtr *out_ptr, size_t bytes) {
    if (out_ptr == nullptr || bytes == 0) return AEC_ERROR_INVALID_ARGUMENT;

    aecDevicePtr ptr = 0;
    const aecError_t status = aec::map_device_status(
        aecDeviceAlloc(static_cast<uint64_t>(bytes), 64, &ptr));
    if (status != AEC_SUCCESS) return status;
    if (ptr == 0 || ptr % 64 != 0) {
        (void)aecDeviceFree(ptr);
        return AEC_ERROR_INTERNAL;
    }

    try {
        auto record = std::make_shared<AllocationRecord>(ptr, bytes);
        auto &state = registry();
        {
            std::lock_guard<std::mutex> lock(state.mutex);
            const auto inserted = state.live.emplace(ptr, std::move(record));
            if (!inserted.second) {
                (void)aecDeviceFree(ptr);
                return AEC_ERROR_INTERNAL;
            }
        }
    } catch (...) {
        (void)aecDeviceFree(ptr);
        throw;
    }
    *out_ptr = ptr;
    return AEC_SUCCESS;
}

aecError_t free_device(aecDevicePtr ptr) {
    if (ptr == 0) return AEC_ERROR_INVALID_ADDRESS;

    std::shared_ptr<AllocationRecord> record;
    auto &state = registry();
    {
        std::lock_guard<std::mutex> registry_lock(state.mutex);
        const auto iterator = state.live.find(ptr);
        if (iterator == state.live.end()) return AEC_ERROR_INVALID_ADDRESS;
        record = iterator->second;
        {
            std::lock_guard<std::mutex> record_lock(record->mutex);
            if (record->closing) return AEC_ERROR_INVALID_ADDRESS;
            record->closing = true;
        }
        state.live.erase(iterator);
    }

    {
        std::unique_lock<std::mutex> lock(record->mutex);
        record->condition.wait(lock, [&] {
            return record->pending_references == 0;
        });
    }
    return aec::map_device_status(aecDeviceFree(ptr));
}

aecError_t acquire_device_span(aecDevicePtr ptr, uint64_t bytes,
                               AllocationLease &lease) {
    if (ptr == 0 || bytes == 0) return AEC_ERROR_INVALID_ADDRESS;

    auto &state = registry();
    std::lock_guard<std::mutex> registry_lock(state.mutex);
    auto iterator = state.live.upper_bound(ptr);
    if (iterator == state.live.begin()) return AEC_ERROR_INVALID_ADDRESS;
    --iterator;
    const std::shared_ptr<AllocationRecord> &record = iterator->second;
    if (ptr < record->base) return AEC_ERROR_INVALID_ADDRESS;
    // Device pointers remain opaque offsets. This subtraction form proves the
    // span fits without ever evaluating the potentially overflowing ptr+bytes.
    const uint64_t offset = ptr - record->base;
    if (offset > record->size || bytes > record->size - offset) {
        return AEC_ERROR_INVALID_ADDRESS;
    }

    {
        std::lock_guard<std::mutex> record_lock(record->mutex);
        if (record->closing) return AEC_ERROR_INVALID_ADDRESS;
        ++record->pending_references;
    }
    lease = AllocationLease(record);
    return AEC_SUCCESS;
}

} // namespace aec
