#ifndef AEC_RUNTIME_LIBRARY_OPS_H
#define AEC_RUNTIME_LIBRARY_OPS_H

#include "aec_runtime.h"

#include <cstdint>

namespace aec {

aecError_t axpy(aecDevicePtr x, aecDevicePtr y, uint64_t count, float alpha,
                aecStream_t stream);
aecError_t dot(aecDevicePtr x, aecDevicePtr y, aecDevicePtr result,
               uint64_t count, aecStream_t stream);
aecError_t nrm2(aecDevicePtr x, aecDevicePtr result, uint64_t count,
                aecStream_t stream);

} // namespace aec

#endif
