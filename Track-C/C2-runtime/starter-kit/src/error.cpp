#include "error.h"

namespace aec {
namespace {

thread_local aecError_t last_error = AEC_SUCCESS;

} // namespace

aecError_t finish(aecError_t error) noexcept {
    if (error != AEC_SUCCESS) {
        last_error = error;
    }
    return error;
}

aecError_t get_last_error() noexcept {
    const aecError_t value = last_error;
    last_error = AEC_SUCCESS;
    return value;
}

aecError_t peek_last_error() noexcept {
    return last_error;
}

const char *error_name(int error) noexcept {
    switch (error) {
    case AEC_SUCCESS: return "AEC_SUCCESS";
    case AEC_ERROR_INVALID_ARGUMENT: return "AEC_ERROR_INVALID_ARGUMENT";
    case AEC_ERROR_OUT_OF_MEMORY: return "AEC_ERROR_OUT_OF_MEMORY";
    case AEC_ERROR_INVALID_HANDLE: return "AEC_ERROR_INVALID_HANDLE";
    case AEC_ERROR_INVALID_ADDRESS: return "AEC_ERROR_INVALID_ADDRESS";
    case AEC_ERROR_NOT_READY: return "AEC_ERROR_NOT_READY";
    case AEC_ERROR_NOT_SUPPORTED: return "AEC_ERROR_NOT_SUPPORTED";
    case AEC_ERROR_DEVICE: return "AEC_ERROR_DEVICE";
    case AEC_ERROR_INTERNAL: return "AEC_ERROR_INTERNAL";
    case AEC_ERROR_ISA_TRAP: return "AEC_ERROR_ISA_TRAP";
    default: return "AEC_ERROR_UNKNOWN";
    }
}

aecError_t map_device_status(aecDeviceStatus status) noexcept {
    switch (status) {
    case AEC_DEVICE_SUCCESS: return AEC_SUCCESS;
    case AEC_DEVICE_INVALID_ARGUMENT: return AEC_ERROR_INVALID_ARGUMENT;
    case AEC_DEVICE_OUT_OF_MEMORY: return AEC_ERROR_OUT_OF_MEMORY;
    case AEC_DEVICE_INVALID_ADDRESS: return AEC_ERROR_INVALID_ADDRESS;
    case AEC_DEVICE_UNSUPPORTED: return AEC_ERROR_NOT_SUPPORTED;
    case AEC_DEVICE_INJECTED_FAULT: return AEC_ERROR_DEVICE;
    case AEC_DEVICE_ISA_TRAP: return AEC_ERROR_ISA_TRAP;
    case AEC_DEVICE_INTERNAL: return AEC_ERROR_INTERNAL;
    default: return AEC_ERROR_DEVICE;
    }
}

} // namespace aec
