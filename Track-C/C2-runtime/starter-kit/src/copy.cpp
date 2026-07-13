#include "copy.h"

#include "allocation.h"
#include "command.h"

namespace aec {
namespace {

aecError_t copy_sync(aecDevicePtr device_ptr, void *host_ptr, size_t bytes,
                     aecCopyDirection direction) {
    if (host_ptr == nullptr || bytes == 0) return AEC_ERROR_INVALID_ARGUMENT;

    AllocationLease allocation;
    const aecError_t span_status = acquire_device_span(
        device_ptr, static_cast<uint64_t>(bytes), allocation);
    if (span_status != AEC_SUCCESS) return span_status;

    return submit_dma(device_ptr, host_ptr, static_cast<uint64_t>(bytes),
                      direction, 0, 0);
}

} // namespace

aecError_t copy_h2d(aecDevicePtr dst, const void *src, size_t bytes) {
    return copy_sync(dst, const_cast<void *>(src), bytes,
                     AEC_COPY_HOST_TO_DEVICE);
}

aecError_t copy_d2h(void *dst, aecDevicePtr src, size_t bytes) {
    return copy_sync(src, dst, bytes, AEC_COPY_DEVICE_TO_HOST);
}

} // namespace aec
