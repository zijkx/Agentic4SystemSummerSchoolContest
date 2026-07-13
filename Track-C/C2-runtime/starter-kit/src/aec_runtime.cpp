#include "aec_runtime.h"
#include "aec_device_abi.h"
#include "allocation.h"
#include "copy.h"
#include "error.h"
#include "event.h"
#include "kernel.h"
#include "library_ops.h"
#include "numeric.h"
#include "registration.h"
#include "stream.h"

#include <cstring>

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
aecError_t aecFree(aecDevicePtr ptr) {
    return aec::api_boundary([&] { return aec::free_device(ptr); });
}
aecError_t aecCopyH2D(aecDevicePtr dst, const void *src, size_t bytes) {
    return aec::api_boundary([&] { return aec::copy_h2d(dst, src, bytes); });
}
aecError_t aecCopyD2H(void *dst, aecDevicePtr src, size_t bytes) {
    return aec::api_boundary([&] { return aec::copy_d2h(dst, src, bytes); });
}
aecError_t aecCopyAsync(aecDevicePtr device_ptr, void *host_ptr, size_t bytes,
                        aecCopyDirection direction, aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::copy_async(device_ptr, host_ptr, bytes, direction, stream);
    });
}
aecError_t aecStreamCreate(aecStream_t *stream) {
    return aec::api_boundary([&] { return aec::stream_create(stream); });
}
aecError_t aecStreamDestroy(aecStream_t stream) {
    return aec::api_boundary([&] { return aec::stream_destroy(stream); });
}
aecError_t aecStreamSync(aecStream_t stream) {
    return aec::api_boundary([&] { return aec::stream_sync(stream); });
}
aecError_t aecEventCreate(aecEvent_t *event) {
    return aec::api_boundary([&] { return aec::event_create(event); });
}
aecError_t aecEventDestroy(aecEvent_t event) {
    return aec::api_boundary([&] { return aec::event_destroy(event); });
}
aecError_t aecEventRecord(aecEvent_t event, aecStream_t stream) {
    return aec::api_boundary([&] { return aec::event_record(event, stream); });
}
aecError_t aecEventSynchronize(aecEvent_t event) {
    return aec::api_boundary([&] { return aec::event_synchronize(event); });
}
aecError_t aecEventQuery(aecEvent_t event) {
    return aec::api_boundary([&] { return aec::event_query(event); });
}
aecError_t aecEventElapsedCycles(aecEvent_t start, aecEvent_t end,
                                 uint64_t *cycles) {
    return aec::api_boundary([&] {
        return aec::event_elapsed_cycles(start, end, cycles);
    });
}
aecError_t aecHostRegister(void *ptr, size_t bytes) {
    return aec::api_boundary([&] { return aec::host_register(ptr, bytes); });
}
aecError_t aecHostUnregister(void *ptr) {
    return aec::api_boundary([&] { return aec::host_unregister(ptr); });
}

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
aecError_t aecMatmulF4(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                       uint32_t m, uint32_t n, uint32_t k,
                       aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_FP4_E2M1, stream);
    });
}
aecError_t aecMatmulF8(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                       uint32_t m, uint32_t n, uint32_t k,
                       aecFp8Format format, aecStream_t stream) {
    return aec::api_boundary([&] {
        aecDataType dtype;
        if (format == AEC_FP8_E4M3) {
            dtype = AEC_DTYPE_FP8_E4M3;
        } else if (format == AEC_FP8_E5M2) {
            dtype = AEC_DTYPE_FP8_E5M2;
        } else {
            return AEC_ERROR_INVALID_ARGUMENT;
        }
        return aec::matmul(a, b, c, m, n, k, dtype, stream);
    });
}
aecError_t aecMatmulF16(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                        uint32_t m, uint32_t n, uint32_t k,
                        aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_FP16, stream);
    });
}
aecError_t aecMatmulBF16(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                         uint32_t m, uint32_t n, uint32_t k,
                         aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_BF16, stream);
    });
}
aecError_t aecMatmulF32(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                        uint32_t m, uint32_t n, uint32_t k,
                        aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_FP32, stream);
    });
}
aecError_t aecMatmulF64(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                        uint32_t m, uint32_t n, uint32_t k,
                        aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_FP64, stream);
    });
}
aecError_t aecMatmulI4(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                       uint32_t m, uint32_t n, uint32_t k,
                       aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_INT4, stream);
    });
}
aecError_t aecMatmulI8(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                       uint32_t m, uint32_t n, uint32_t k,
                       aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_INT8, stream);
    });
}
aecError_t aecMatmulI32(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                        uint32_t m, uint32_t n, uint32_t k,
                        aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::matmul(a, b, c, m, n, k, AEC_DTYPE_INT32, stream);
    });
}
aecError_t aecAxpy(aecDevicePtr x, aecDevicePtr y, uint64_t count,
                   float alpha, aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::axpy(x, y, count, alpha, stream);
    });
}
aecError_t aecDot(aecDevicePtr x, aecDevicePtr y, aecDevicePtr result,
                  uint64_t count, aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::dot(x, y, result, count, stream);
    });
}
aecError_t aecNrm2(aecDevicePtr x, aecDevicePtr result, uint64_t count,
                   aecStream_t stream) {
    return aec::api_boundary([&] {
        return aec::nrm2(x, result, count, stream);
    });
}

} // extern "C"
