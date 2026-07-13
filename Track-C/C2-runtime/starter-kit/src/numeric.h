#ifndef AEC_RUNTIME_NUMERIC_H
#define AEC_RUNTIME_NUMERIC_H

#include "aec_runtime.h"

#include <cstdint>

namespace aec {

aecError_t matmul(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                  uint32_t m, uint32_t n, uint32_t k, aecDataType dtype,
                  aecStream_t stream);

} // namespace aec

#endif
