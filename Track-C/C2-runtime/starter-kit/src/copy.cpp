#include "copy.h"

#include "allocation.h"
#include "command.h"
#include "registration.h"
#include "stream.h"

#include <memory>

namespace aec {
namespace {

aecError_t copy_sync(aecDevicePtr device_ptr, void *host_ptr, size_t bytes,
                     aecCopyDirection direction) {
    if (host_ptr == nullptr || bytes == 0) return AEC_ERROR_INVALID_ARGUMENT;

    AllocationLease allocation;
    const aecError_t span_status = acquire_device_span(
        device_ptr, static_cast<uint64_t>(bytes), allocation);
    if (span_status != AEC_SUCCESS) return span_status;

    RegistrationLease registration;
    bool registered = false;
    const aecError_t registration_status = acquire_registered_span(
        host_ptr, static_cast<uint64_t>(bytes), registration, registered);
    if (registration_status != AEC_SUCCESS) return registration_status;
    const uint16_t flags = registered
                               ? AEC_DEVICE_FLAG_REGISTERED |
                                     AEC_DEVICE_FLAG_ZERO_COPY
                               : AEC_DEVICE_FLAG_NONE;
    return submit_dma(device_ptr, host_ptr, static_cast<uint64_t>(bytes),
                      direction, 0, 0, flags);
}

} // namespace

aecError_t copy_h2d(aecDevicePtr dst, const void *src, size_t bytes) {
    return copy_sync(dst, const_cast<void *>(src), bytes,
                     AEC_COPY_HOST_TO_DEVICE);
}

aecError_t copy_d2h(void *dst, aecDevicePtr src, size_t bytes) {
    return copy_sync(src, dst, bytes, AEC_COPY_DEVICE_TO_HOST);
}

aecError_t copy_async(aecDevicePtr device_ptr, void *host_ptr, size_t bytes,
                      int direction_value, aecStream_t stream) {
    if (host_ptr == nullptr || bytes == 0 ||
        (direction_value != AEC_COPY_HOST_TO_DEVICE &&
         direction_value != AEC_COPY_DEVICE_TO_HOST)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    const auto direction = static_cast<aecCopyDirection>(direction_value);

    struct AsyncCopy {
        AllocationLease allocation;
        RegistrationLease registration;
        aecError_t preflight = AEC_SUCCESS;
        aecDevicePtr device_ptr = 0;
        void *host_ptr = nullptr;
        uint64_t bytes = 0;
        aecCopyDirection direction = AEC_COPY_HOST_TO_DEVICE;
        uint16_t flags = AEC_DEVICE_FLAG_NONE;
    };
    auto work = std::make_shared<AsyncCopy>();
    work->device_ptr = device_ptr;
    work->host_ptr = host_ptr;
    work->bytes = static_cast<uint64_t>(bytes);
    work->direction = direction;
    work->preflight = acquire_device_span(device_ptr, work->bytes,
                                          work->allocation);
    if (work->preflight == AEC_SUCCESS) {
        bool registered = false;
        work->preflight = acquire_registered_span(
            host_ptr, work->bytes, work->registration, registered);
        if (registered) {
            work->flags = AEC_DEVICE_FLAG_REGISTERED |
                          AEC_DEVICE_FLAG_ZERO_COPY;
        }
    }
    return enqueue_stream_work(stream, [work](uint64_t stream_id) {
        if (work->preflight != AEC_SUCCESS) return work->preflight;
        const uint8_t channel = static_cast<uint8_t>(stream_id % 2);
        return submit_dma(work->device_ptr, work->host_ptr, work->bytes,
                          work->direction, stream_id, channel, work->flags);
    });
}

} // namespace aec
