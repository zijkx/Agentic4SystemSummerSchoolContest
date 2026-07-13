#ifndef AEC_RUNTIME_KERNEL_H
#define AEC_RUNTIME_KERNEL_H

#include "aec_device_abi.h"
#include "aec_runtime.h"

#include <cstddef>

namespace aec {

aecError_t build_isa_command(uint32_t semantic_kernel, uint32_t dtype,
                             uint32_t variant, aecDim3 grid, aecDim3 block,
                             const uint8_t *parameters,
                             uint32_t parameter_bytes,
                             aecDeviceCommand &command);

aecError_t launch(int kernel, aecDim3 grid, aecDim3 block,
                  const void *args, size_t args_size, aecStream_t stream);

} // namespace aec

#endif
