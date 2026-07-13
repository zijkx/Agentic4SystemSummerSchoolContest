#include "registration.h"

#include <condition_variable>
#include <iterator>
#include <limits>
#include <map>
#include <mutex>
#include <utility>

namespace aec {

struct RegistrationRecord {
    RegistrationRecord(uintptr_t interval_base, uintptr_t interval_end)
        : base(interval_base), end(interval_end) {}

    const uintptr_t base;
    const uintptr_t end;
    std::mutex mutex;
    std::condition_variable condition;
    uint64_t pending_references = 0;
    bool closing = false;
};

namespace {

struct RegistrationRegistry {
    std::mutex mutex;
    std::map<uintptr_t, std::shared_ptr<RegistrationRecord>> live;
};

RegistrationRegistry &registry() {
    static RegistrationRegistry value;
    return value;
}

bool interval_end(uintptr_t start, uint64_t bytes, uintptr_t &end) noexcept {
    if (bytes == 0 || bytes > std::numeric_limits<uintptr_t>::max() - start) {
        return false;
    }
    end = start + static_cast<uintptr_t>(bytes);
    return true;
}

} // namespace

RegistrationLease::RegistrationLease(
    std::shared_ptr<RegistrationRecord> record) noexcept
    : record_(std::move(record)) {}

RegistrationLease::RegistrationLease(RegistrationLease &&other) noexcept
    : record_(std::move(other.record_)) {}

RegistrationLease &RegistrationLease::operator=(
    RegistrationLease &&other) noexcept {
    if (this != &other) {
        release();
        record_ = std::move(other.record_);
    }
    return *this;
}

RegistrationLease::~RegistrationLease() {
    release();
}

void RegistrationLease::release() noexcept {
    if (record_ == nullptr) return;
    std::shared_ptr<RegistrationRecord> record = std::move(record_);
    {
        std::lock_guard<std::mutex> lock(record->mutex);
        if (record->pending_references > 0) {
            --record->pending_references;
        }
    }
    record->condition.notify_all();
}

aecError_t host_register(void *ptr, size_t bytes) {
    if (ptr == nullptr || bytes == 0) return AEC_ERROR_INVALID_ARGUMENT;
    const uintptr_t start = reinterpret_cast<uintptr_t>(ptr);
    uintptr_t end = 0;
    if (!interval_end(start, static_cast<uint64_t>(bytes), end)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    auto record = std::make_shared<RegistrationRecord>(start, end);
    auto &state = registry();
    std::lock_guard<std::mutex> registry_lock(state.mutex);
    const auto successor = state.live.lower_bound(start);
    if (successor != state.live.end() && successor->first < end) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    if (successor != state.live.begin()) {
        const auto predecessor = std::prev(successor);
        if (predecessor->second->end > start) {
            return AEC_ERROR_INVALID_ARGUMENT;
        }
    }
    const auto inserted = state.live.emplace(start, std::move(record));
    return inserted.second ? AEC_SUCCESS : AEC_ERROR_INVALID_ARGUMENT;
}

aecError_t host_unregister(void *ptr) {
    if (ptr == nullptr) return AEC_ERROR_INVALID_ARGUMENT;
    const uintptr_t start = reinterpret_cast<uintptr_t>(ptr);
    std::shared_ptr<RegistrationRecord> record;
    auto &state = registry();
    {
        std::lock_guard<std::mutex> registry_lock(state.mutex);
        const auto iterator = state.live.find(start);
        if (iterator == state.live.end()) return AEC_ERROR_INVALID_ARGUMENT;
        record = iterator->second;
        {
            std::lock_guard<std::mutex> record_lock(record->mutex);
            if (record->closing) return AEC_ERROR_INVALID_ARGUMENT;
            record->closing = true;
        }
        state.live.erase(iterator);
    }
    std::unique_lock<std::mutex> lock(record->mutex);
    record->condition.wait(lock, [&] {
        return record->pending_references == 0;
    });
    return AEC_SUCCESS;
}

aecError_t acquire_registered_span(void *ptr, uint64_t bytes,
                                   RegistrationLease &lease,
                                   bool &registered) {
    registered = false;
    if (ptr == nullptr || bytes == 0) return AEC_ERROR_INVALID_ARGUMENT;
    const uintptr_t start = reinterpret_cast<uintptr_t>(ptr);
    uintptr_t end = 0;
    if (!interval_end(start, bytes, end)) return AEC_ERROR_INVALID_ARGUMENT;

    auto &state = registry();
    std::lock_guard<std::mutex> registry_lock(state.mutex);
    auto iterator = state.live.upper_bound(start);
    if (iterator == state.live.begin()) return AEC_SUCCESS;
    --iterator;
    const std::shared_ptr<RegistrationRecord> &record = iterator->second;
    if (start < record->base || end > record->end) return AEC_SUCCESS;
    {
        std::lock_guard<std::mutex> record_lock(record->mutex);
        if (record->closing) return AEC_SUCCESS;
        ++record->pending_references;
    }
    lease = RegistrationLease(record);
    registered = true;
    return AEC_SUCCESS;
}

} // namespace aec
