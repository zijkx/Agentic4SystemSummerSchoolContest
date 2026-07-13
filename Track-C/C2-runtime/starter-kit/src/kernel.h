#ifndef AEC_RUNTIME_KERNEL_H
#define AEC_RUNTIME_KERNEL_H

#include "aec_runtime.h"

#include <cstddef>

namespace aec {

aecError_t launch(aecKernelId kernel, aecDim3 grid, aecDim3 block,
                  const void *args, size_t args_size, aecStream_t stream);

} // namespace aec

#endif
