#include "command.h"

#include "error.h"

#include <limits>
#include <mutex>

namespace aec {
namespace {

struct SubmitState {
    std::mutex mutex;
    uint64_t next_sequence = 1;
    bool exhausted = false;
};

SubmitState &submit_state() {
    static SubmitState state;
    return state;
}

} // namespace

aecError_t submit_and_validate_completion(
    aecDeviceCommand &command, aecDeviceCompletion *completion_out) {
    auto &state = submit_state();
    std::lock_guard<std::mutex> submit_lock(state.mutex);
    if (state.exhausted || state.next_sequence == 0) {
        return AEC_ERROR_INTERNAL;
    }

    // Sequence assignment and the blocking submit share this lock. A worker
    // can therefore never deliver a larger sequence before a smaller one.
    command.sequence = state.next_sequence;
    if (state.next_sequence == std::numeric_limits<uint64_t>::max()) {
        state.exhausted = true;
    } else {
        ++state.next_sequence;
    }

    aecDeviceCompletion completion{};
    const aecDeviceStatus submit_status = aecDeviceSubmit(&command, &completion);
    if (completion.abi_version != AEC_DEVICE_ABI_VERSION ||
        completion.sequence != command.sequence) {
        return AEC_ERROR_INTERNAL;
    }
    if (static_cast<uint32_t>(submit_status) != completion.status) {
        return AEC_ERROR_INTERNAL;
    }
    if (completion_out != nullptr) {
        *completion_out = completion;
    }
    return map_device_status(submit_status);
}

aecError_t submit_dma(aecDevicePtr device_ptr, void *host_ptr, uint64_t bytes,
                      aecCopyDirection direction, uint64_t stream_id,
                      uint8_t channel, uint16_t flags) {
    if (host_ptr == nullptr || bytes == 0 || channel > 1) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    if (direction != AEC_COPY_HOST_TO_DEVICE &&
        direction != AEC_COPY_DEVICE_TO_HOST) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    if ((flags & AEC_DEVICE_FLAG_ZERO_COPY) != 0 &&
        (flags & AEC_DEVICE_FLAG_REGISTERED) == 0) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    aecDeviceCommand command{};
    command.abi_version = AEC_DEVICE_ABI_VERSION;
    command.opcode = direction == AEC_COPY_HOST_TO_DEVICE
                         ? AEC_DEVICE_OP_H2D
                         : AEC_DEVICE_OP_D2H;
    command.flags = flags;
    command.stream_id = stream_id;
    if (direction == AEC_COPY_HOST_TO_DEVICE) {
        command.dst = device_ptr;
    } else {
        command.src = device_ptr;
    }
    command.host_address = static_cast<uint64_t>(
        reinterpret_cast<uintptr_t>(host_ptr));
    command.bytes = bytes;
    command.chunk_bytes = 65536;
    command.queue_depth = 2;
    command.channel = channel;
    return submit_and_validate_completion(command);
}

} // namespace aec
