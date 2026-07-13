#include "stream.h"

#include <condition_variable>
#include <cstdint>
#include <deque>
#include <limits>
#include <memory>
#include <mutex>
#include <new>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

struct aecStreamOpaque {
    uint64_t stable_id;
};

namespace aec {
namespace {

class StreamState {
public:
    explicit StreamState(uint64_t stable_id)
        : stable_id_(stable_id), worker_([this] { worker_loop(); }) {}

    StreamState(const StreamState &) = delete;
    StreamState &operator=(const StreamState &) = delete;

    ~StreamState() {
        shutdown();
    }

    aecError_t enqueue(StreamWork work) {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!accepting_) return AEC_ERROR_INVALID_HANDLE;
            queue_.push_back(std::move(work));
        }
        condition_.notify_all();
        return AEC_SUCCESS;
    }

    aecError_t synchronize() {
        std::unique_lock<std::mutex> lock(mutex_);
        condition_.wait(lock, [&] {
            return queue_.empty() && in_flight_ == 0;
        });
        const aecError_t error = first_unreported_error_;
        first_unreported_error_ = AEC_SUCCESS;
        return error;
    }

    void shutdown() noexcept {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            accepting_ = false;
            stop_ = true;
        }
        condition_.notify_all();
        if (worker_.joinable() && worker_.get_id() != std::this_thread::get_id()) {
            worker_.join();
        }
    }

private:
    void worker_loop() noexcept {
        for (;;) {
            StreamWork work;
            {
                std::unique_lock<std::mutex> lock(mutex_);
                condition_.wait(lock, [&] { return stop_ || !queue_.empty(); });
                if (queue_.empty()) {
                    if (stop_) break;
                    continue;
                }
                work = std::move(queue_.front());
                queue_.pop_front();
                ++in_flight_;
            }

            aecError_t status = AEC_SUCCESS;
            try {
                status = work(stable_id_);
            } catch (const std::bad_alloc &) {
                status = AEC_ERROR_OUT_OF_MEMORY;
            } catch (...) {
                status = AEC_ERROR_INTERNAL;
            }
            // Release command metadata and allocation leases before notifying
            // waiters. In particular, the final queued item must not keep a
            // lease alive while the worker sleeps with an empty queue.
            work = {};

            {
                std::lock_guard<std::mutex> lock(mutex_);
                if (status != AEC_SUCCESS &&
                    first_unreported_error_ == AEC_SUCCESS) {
                    first_unreported_error_ = status;
                }
                --in_flight_;
            }
            condition_.notify_all();
        }
        condition_.notify_all();
    }

    const uint64_t stable_id_;
    std::mutex mutex_;
    std::condition_variable condition_;
    std::deque<StreamWork> queue_;
    std::thread worker_;
    uint64_t in_flight_ = 0;
    aecError_t first_unreported_error_ = AEC_SUCCESS;
    bool accepting_ = true;
    bool stop_ = false;
};

struct StreamRegistry {
    ~StreamRegistry() {
        for (auto &entry : live) {
            entry.second->shutdown();
        }
    }

    std::mutex mutex;
    std::unordered_map<aecStream_t, std::shared_ptr<StreamState>> live;
    // Handle shells are process-lifetime tombstones. Their addresses are never
    // recycled, so a stale handle cannot alias a later Stream.
    std::vector<std::unique_ptr<aecStreamOpaque>> handles;
    uint64_t next_id = 1;
};

StreamRegistry &registry() {
    static StreamRegistry value;
    return value;
}

std::shared_ptr<StreamState> find_stream(aecStream_t stream) {
    if (stream == nullptr) return {};
    auto &state = registry();
    std::lock_guard<std::mutex> lock(state.mutex);
    const auto iterator = state.live.find(stream);
    return iterator == state.live.end() ? std::shared_ptr<StreamState>{}
                                        : iterator->second;
}

} // namespace

aecError_t stream_create(aecStream_t *stream) {
    if (stream == nullptr) return AEC_ERROR_INVALID_ARGUMENT;

    auto &state = registry();
    std::lock_guard<std::mutex> lock(state.mutex);
    if (state.next_id == 0 ||
        state.next_id == std::numeric_limits<uint64_t>::max()) {
        return AEC_ERROR_INTERNAL;
    }
    const uint64_t id = state.next_id++;
    auto handle = std::make_unique<aecStreamOpaque>();
    handle->stable_id = id;
    auto stream_state = std::make_shared<StreamState>(id);
    aecStream_t raw_handle = handle.get();
    // Vault insertion happens before registry publication. If publication
    // later throws, the unexposed shell may remain as a harmless tombstone,
    // but the registry can never retain a pointer to freed storage.
    state.handles.push_back(std::move(handle));
    const auto inserted = state.live.emplace(raw_handle, std::move(stream_state));
    if (!inserted.second) return AEC_ERROR_INTERNAL;
    *stream = raw_handle;
    return AEC_SUCCESS;
}

aecError_t stream_destroy(aecStream_t stream) {
    if (stream == nullptr) return AEC_ERROR_INVALID_HANDLE;
    std::shared_ptr<StreamState> stream_state;
    auto &state = registry();
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        const auto iterator = state.live.find(stream);
        if (iterator == state.live.end()) return AEC_ERROR_INVALID_HANDLE;
        stream_state = iterator->second;
        state.live.erase(iterator);
    }
    stream_state->shutdown();
    return AEC_SUCCESS;
}

aecError_t stream_sync(aecStream_t stream) {
    const auto state = find_stream(stream);
    return state == nullptr ? AEC_ERROR_INVALID_HANDLE : state->synchronize();
}

aecError_t enqueue_stream_work(aecStream_t stream, StreamWork work) {
    const auto state = find_stream(stream);
    return state == nullptr ? AEC_ERROR_INVALID_HANDLE
                            : state->enqueue(std::move(work));
}

} // namespace aec
