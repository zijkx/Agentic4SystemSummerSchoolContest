#ifndef AEC_RUNTIME_ERROR_H
#define AEC_RUNTIME_ERROR_H

#include "aec_device_abi.h"
#include "aec_runtime.h"

#include <new>
#include <utility>

namespace aec {

aecError_t finish(aecError_t error) noexcept;
aecError_t get_last_error() noexcept;
aecError_t peek_last_error() noexcept;
const char *error_name(int error) noexcept;
aecError_t map_device_status(aecDeviceStatus status) noexcept;

template <typename Function>
aecError_t api_boundary(Function &&function) noexcept {
    try {
        return finish(std::forward<Function>(function)());
    } catch (const std::bad_alloc &) {
        return finish(AEC_ERROR_OUT_OF_MEMORY);
    } catch (...) {
        return finish(AEC_ERROR_INTERNAL);
    }
}

} // namespace aec

#endif
