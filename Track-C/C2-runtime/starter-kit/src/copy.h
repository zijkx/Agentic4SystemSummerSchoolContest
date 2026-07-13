#ifndef AEC_RUNTIME_COPY_H
#define AEC_RUNTIME_COPY_H

#include "aec_runtime.h"

#include <cstddef>

namespace aec {

aecError_t copy_h2d(aecDevicePtr dst, const void *src, size_t bytes);
aecError_t copy_d2h(void *dst, aecDevicePtr src, size_t bytes);
aecError_t copy_async(aecDevicePtr device_ptr, void *host_ptr, size_t bytes,
                      int direction_value, aecStream_t stream);

} // namespace aec

#endif
