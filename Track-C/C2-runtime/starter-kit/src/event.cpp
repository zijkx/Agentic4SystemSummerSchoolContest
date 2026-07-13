#include "event.h"

#include "aec_device_abi.h"
#include "error.h"
#include "stream.h"

#include <condition_variable>
#include <cstdint>
#include <limits>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <utility>
#include <vector>

struct aecEventOpaque {
    uint64_t stable_id;
};

namespace aec {
namespace {

struct EventCompletion {
    uint64_t cycle = 0;
    aecError_t status = AEC_SUCCESS;
    bool completed = false;
};

struct ReservedGeneration {
    uint64_t generation = 0;
    uint64_t previous_latest = 0;
};

class EventState {
public:
    aecError_t reserve_generation(ReservedGeneration &reservation) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!accepting_) return AEC_ERROR_INVALID_HANDLE;
        if (next_generation_ == std::numeric_limits<uint64_t>::max()) {
            return AEC_ERROR_INTERNAL;
        }
        reservation.previous_latest = latest_generation_;
        reservation.generation = next_generation_ + 1;
        const auto inserted = completions_.emplace(
            reservation.generation, EventCompletion{});
        if (!inserted.second) return AEC_ERROR_INTERNAL;
        next_generation_ = reservation.generation;
        latest_generation_ = reservation.generation;
        return AEC_SUCCESS;
    }

    void cancel_generation(const ReservedGeneration &reservation,
                           aecError_t status) {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto &completion = completions_.at(reservation.generation);
            completion = {0, status, true};
            if (latest_generation_ == reservation.generation) {
                latest_generation_ = reservation.previous_latest;
            }
        }
        condition_.notify_all();
    }

    void complete(uint64_t generation, uint64_t cycle,
                  aecError_t status) {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto &completion = completions_.at(generation);
            completion = {cycle, status, true};
        }
        condition_.notify_all();
    }

    uint64_t begin_destroy() {
        std::lock_guard<std::mutex> lock(mutex_);
        accepting_ = false;
        return latest_generation_;
    }

    uint64_t latest_generation() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return latest_generation_;
    }

    aecError_t query(uint64_t generation, EventCompletion &completion) const {
        std::lock_guard<std::mutex> lock(mutex_);
        const auto iterator = completions_.find(generation);
        if (iterator == completions_.end() || !iterator->second.completed) {
            return AEC_ERROR_NOT_READY;
        }
        completion = iterator->second;
        return completion.status;
    }

    aecError_t wait(uint64_t generation, EventCompletion &completion) {
        std::unique_lock<std::mutex> lock(mutex_);
        condition_.wait(lock, [&] {
            const auto iterator = completions_.find(generation);
            return iterator != completions_.end() && iterator->second.completed;
        });
        completion = completions_.at(generation);
        return completion.status;
    }

private:
    mutable std::mutex mutex_;
    std::condition_variable condition_;
    std::unordered_map<uint64_t, EventCompletion> completions_;
    uint64_t next_generation_ = 0;
    uint64_t latest_generation_ = 0;
    bool accepting_ = true;
};

struct EventRegistry {
    std::mutex mutex;
    std::unordered_map<aecEvent_t, std::shared_ptr<EventState>> live;
    std::vector<std::unique_ptr<aecEventOpaque>> handles;
    uint64_t next_id = 1;
};

EventRegistry &registry() {
    static EventRegistry value;
    return value;
}

std::shared_ptr<EventState> find_event(aecEvent_t event) {
    if (event == nullptr) return {};
    auto &state = registry();
    std::lock_guard<std::mutex> lock(state.mutex);
    const auto iterator = state.live.find(event);
    return iterator == state.live.end() ? std::shared_ptr<EventState>{}
                                        : iterator->second;
}

aecError_t latest_or_error(const std::shared_ptr<EventState> &state,
                           uint64_t &generation) {
    generation = state->latest_generation();
    return generation == 0 ? AEC_ERROR_INVALID_ARGUMENT : AEC_SUCCESS;
}

} // namespace

aecError_t event_create(aecEvent_t *event) {
    if (event == nullptr) return AEC_ERROR_INVALID_ARGUMENT;
    auto &state = registry();
    std::lock_guard<std::mutex> lock(state.mutex);
    if (state.next_id == 0 ||
        state.next_id == std::numeric_limits<uint64_t>::max()) {
        return AEC_ERROR_INTERNAL;
    }
    const uint64_t id = state.next_id++;
    auto handle = std::make_unique<aecEventOpaque>();
    handle->stable_id = id;
    auto event_state = std::make_shared<EventState>();
    aecEvent_t raw_handle = handle.get();
    state.handles.push_back(std::move(handle));
    const auto inserted = state.live.emplace(raw_handle, std::move(event_state));
    if (!inserted.second) return AEC_ERROR_INTERNAL;
    *event = raw_handle;
    return AEC_SUCCESS;
}

aecError_t event_destroy(aecEvent_t event) {
    if (event == nullptr) return AEC_ERROR_INVALID_HANDLE;
    std::shared_ptr<EventState> event_state;
    auto &state = registry();
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        const auto iterator = state.live.find(event);
        if (iterator == state.live.end()) return AEC_ERROR_INVALID_HANDLE;
        event_state = iterator->second;
        state.live.erase(iterator);
    }
    const uint64_t generation = event_state->begin_destroy();
    if (generation == 0) return AEC_SUCCESS;
    EventCompletion completion;
    return event_state->wait(generation, completion);
}

aecError_t event_record(aecEvent_t event, aecStream_t stream) {
    const auto event_state = find_event(event);
    if (event_state == nullptr) return AEC_ERROR_INVALID_HANDLE;

    ReservedGeneration reservation;
    const aecError_t reserve_status =
        event_state->reserve_generation(reservation);
    if (reserve_status != AEC_SUCCESS) return reserve_status;

    const aecError_t enqueue_status = enqueue_stream_work(
        stream, [event_state, generation = reservation.generation](uint64_t) {
            aecDeviceStats stats{};
            const aecError_t status = map_device_status(aecDeviceGetStats(&stats));
            if (status != AEC_SUCCESS ||
                stats.abi_version != AEC_DEVICE_ABI_VERSION) {
                const aecError_t final_status =
                    status == AEC_SUCCESS ? AEC_ERROR_INTERNAL : status;
                event_state->complete(generation, 0, final_status);
                return final_status;
            }
            event_state->complete(generation, stats.total_virtual_cycles,
                                  AEC_SUCCESS);
            return AEC_SUCCESS;
        });
    if (enqueue_status != AEC_SUCCESS) {
        event_state->cancel_generation(reservation, enqueue_status);
    }
    return enqueue_status;
}

aecError_t event_synchronize(aecEvent_t event) {
    const auto state = find_event(event);
    if (state == nullptr) return AEC_ERROR_INVALID_HANDLE;
    uint64_t generation = 0;
    const aecError_t status = latest_or_error(state, generation);
    if (status != AEC_SUCCESS) return status;
    EventCompletion completion;
    return state->wait(generation, completion);
}

aecError_t event_query(aecEvent_t event) {
    const auto state = find_event(event);
    if (state == nullptr) return AEC_ERROR_INVALID_HANDLE;
    uint64_t generation = 0;
    const aecError_t status = latest_or_error(state, generation);
    if (status != AEC_SUCCESS) return status;
    EventCompletion completion;
    return state->query(generation, completion);
}

aecError_t event_elapsed_cycles(aecEvent_t start, aecEvent_t end,
                                uint64_t *cycles) {
    if (cycles == nullptr) return AEC_ERROR_INVALID_ARGUMENT;
    const auto start_state = find_event(start);
    const auto end_state = find_event(end);
    if (start_state == nullptr || end_state == nullptr) {
        return AEC_ERROR_INVALID_HANDLE;
    }

    uint64_t start_generation = 0;
    aecError_t status = latest_or_error(start_state, start_generation);
    if (status != AEC_SUCCESS) return status;
    if (start_state == end_state) {
        EventCompletion completion;
        status = start_state->query(start_generation, completion);
        if (status != AEC_SUCCESS) return status;
        *cycles = 0;
        return AEC_SUCCESS;
    }

    uint64_t end_generation = 0;
    status = latest_or_error(end_state, end_generation);
    if (status != AEC_SUCCESS) return status;
    EventCompletion start_completion;
    EventCompletion end_completion;
    status = start_state->query(start_generation, start_completion);
    if (status != AEC_SUCCESS) return status;
    status = end_state->query(end_generation, end_completion);
    if (status != AEC_SUCCESS) return status;
    if (end_completion.cycle < start_completion.cycle) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    *cycles = end_completion.cycle - start_completion.cycle;
    return AEC_SUCCESS;
}

} // namespace aec
