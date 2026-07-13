#include "aec_runtime.h"
#include "aec_device_abi.h"
#include "allocation.h"
#include "copy.h"
#include "error.h"
#include "kernel.h"

#include <cstring>

namespace {

aecError_t unsupported() noexcept {
    return AEC_ERROR_NOT_SUPPORTED;
}

} // namespace

extern "C" {

aecError_t aecDeviceCount(int *count) {
    return aec::api_boundary([&] {
        if (count == nullptr) return AEC_ERROR_INVALID_ARGUMENT;
        aecDeviceCaps caps{};
        const aecError_t status = aec::map_device_status(aecDeviceGetCaps(&caps));
        if (status != AEC_SUCCESS) return status;
        if (caps.abi_version != AEC_DEVICE_ABI_VERSION) return AEC_ERROR_INTERNAL;
        *count = static_cast<int>(caps.device_count);
        return AEC_SUCCESS;
    });
}

aecError_t aecDeviceInfo(int device, aecDeviceInfoData *info) {
    return aec::api_boundary([&] {
        if (device != 0 || info == nullptr) return AEC_ERROR_INVALID_ARGUMENT;
        aecDeviceCaps caps{};
        const aecError_t status = aec::map_device_status(aecDeviceGetCaps(&caps));
        if (status != AEC_SUCCESS) return status;
        if (caps.abi_version != AEC_DEVICE_ABI_VERSION) return AEC_ERROR_INTERNAL;
        *info = {};
        info->abi_version = AEC_RUNTIME_ABI_VERSION;
        std::strncpy(info->name, "AEC Deterministic Virtual Device", sizeof(info->name) - 1);
        info->memory_bytes = caps.memory_bytes;
        info->dma_channels = caps.dma_channels;
        info->max_threads_per_block = caps.max_threads_per_block;
        info->isa_version = caps.isa_version;
        info->isa_profile = caps.isa_profile;
        info->max_parameter_bytes = caps.max_parameter_bytes;
        return AEC_SUCCESS;
    });
}

aecError_t aecGetLastError(void) {
    return aec::get_last_error();
}

aecError_t aecPeekAtLastError(void) { return aec::peek_last_error(); }

const char *aecGetErrorName(aecError_t error) {
    return aec::error_name(error);
}

aecError_t aecAlloc(aecDevicePtr *out_ptr, size_t bytes) {
    return aec::api_boundary([&] { return aec::allocate_device(out_ptr, bytes); });
}
#define AEC_UNSUPPORTED_BODY() return aec::api_boundary([] { return unsupported(); })
aecError_t aecFree(aecDevicePtr ptr) {
    return aec::api_boundary([&] { return aec::free_device(ptr); });
}
aecError_t aecCopyH2D(aecDevicePtr dst, const void *src, size_t bytes) {
    return aec::api_boundary([&] { return aec::copy_h2d(dst, src, bytes); });
}
aecError_t aecCopyD2H(void *dst, aecDevicePtr src, size_t bytes) {
    return aec::api_boundary([&] { return aec::copy_d2h(dst, src, bytes); });
}
aecError_t aecCopyAsync(aecDevicePtr, void *, size_t, aecCopyDirection, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecStreamCreate(aecStream_t *) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecStreamDestroy(aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecStreamSync(aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecEventCreate(aecEvent_t *) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecEventDestroy(aecEvent_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecEventRecord(aecEvent_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecEventSynchronize(aecEvent_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecEventQuery(aecEvent_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecEventElapsedCycles(aecEvent_t, aecEvent_t, uint64_t *) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecHostRegister(void *, size_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecHostUnregister(void *) { AEC_UNSUPPORTED_BODY(); }

aecError_t aecGetRuntimeStats(aecRuntimeStats *stats) {
    return aec::api_boundary([&] {
        if (stats == nullptr) return AEC_ERROR_INVALID_ARGUMENT;
        aecDeviceStats device_stats{};
        const aecError_t status = aec::map_device_status(aecDeviceGetStats(&device_stats));
        if (status != AEC_SUCCESS) return status;
        if (device_stats.abi_version != AEC_DEVICE_ABI_VERSION) return AEC_ERROR_INTERNAL;
        static_assert(sizeof(*stats) == sizeof(device_stats));
        std::memcpy(stats, &device_stats, sizeof(*stats));
        stats->abi_version = AEC_RUNTIME_ABI_VERSION;
        return AEC_SUCCESS;
    });
}

aecError_t aecResetRuntimeStats(void) {
    return aec::api_boundary([] {
        return aec::map_device_status(aecDeviceResetStats());
    });
}

aecError_t aecLaunch(aecKernelId kernel, aecDim3 grid, aecDim3 block,
                     const void *args, size_t args_size, aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::launch(kernel, grid, block, args, args_size, stream);
    });
}
aecError_t aecMatmulF4(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulF8(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecFp8Format, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulF16(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulBF16(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulF32(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulF64(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulI4(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulI8(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecMatmulI32(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint32_t, uint32_t, uint32_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecAxpy(aecDevicePtr, aecDevicePtr, uint64_t, float, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecDot(aecDevicePtr, aecDevicePtr, aecDevicePtr, uint64_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }
aecError_t aecNrm2(aecDevicePtr, aecDevicePtr, uint64_t, aecStream_t) { AEC_UNSUPPORTED_BODY(); }

#undef AEC_UNSUPPORTED_BODY

} // extern "C"
