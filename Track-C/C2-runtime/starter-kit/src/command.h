#ifndef AEC_RUNTIME_COMMAND_H
#define AEC_RUNTIME_COMMAND_H

#include "aec_device_abi.h"
#include "aec_runtime.h"

#include <cstdint>

namespace aec {

aecError_t submit_and_validate_completion(
    aecDeviceCommand &command,
    aecDeviceCompletion *completion_out = nullptr);

aecError_t submit_dma(aecDevicePtr device_ptr, void *host_ptr, uint64_t bytes,
                      aecCopyDirection direction, uint64_t stream_id,
                      uint8_t channel, uint16_t flags = AEC_DEVICE_FLAG_NONE);

} // namespace aec

#endif
