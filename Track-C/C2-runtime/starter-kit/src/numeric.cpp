#include "numeric.h"

#include "aec_device_abi.h"
#include "aec_isa.h"
#include "allocation.h"
#include "command.h"
#include "kernel.h"
#include "serialization.h"
#include "stream.h"

#include <limits>
#include <memory>

namespace aec {
namespace {

constexpr uint32_t kMaxMatrixDimension = 256;

bool checked_multiply(uint64_t left, uint64_t right,
                      uint64_t &result) noexcept {
    if (left != 0 && right > std::numeric_limits<uint64_t>::max() / left) {
        return false;
    }
    result = left * right;
    return true;
}

bool storage_bytes(uint64_t elements, aecDataType dtype, bool output,
                   uint64_t &bytes) noexcept {
    if (output && (dtype == AEC_DTYPE_INT4 || dtype == AEC_DTYPE_INT8 ||
                   dtype == AEC_DTYPE_INT32)) {
        return checked_multiply(elements, 4, bytes);
    }
    switch (dtype) {
    case AEC_DTYPE_FP4_E2M1:
    case AEC_DTYPE_INT4:
        bytes = elements / 2 + elements % 2;
        return true;
    case AEC_DTYPE_FP8_E4M3:
    case AEC_DTYPE_FP8_E5M2:
    case AEC_DTYPE_INT8:
        bytes = elements;
        return true;
    case AEC_DTYPE_FP16:
    case AEC_DTYPE_BF16:
        return checked_multiply(elements, 2, bytes);
    case AEC_DTYPE_FP32:
    case AEC_DTYPE_INT32:
        return checked_multiply(elements, 4, bytes);
    case AEC_DTYPE_FP64:
        return checked_multiply(elements, 8, bytes);
    default:
        return false;
    }
}

bool spans_overlap(aecDevicePtr left, uint64_t left_bytes,
                   aecDevicePtr right, uint64_t right_bytes) noexcept {
    if (left <= right) return right - left < left_bytes;
    return left - right < right_bytes;
}

struct PreparedMatmul {
    aecDeviceCommand command{};
    AllocationLease a_lease;
    AllocationLease b_lease;
    AllocationLease c_lease;
};

aecError_t prepare_matmul(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                          uint32_t m, uint32_t n, uint32_t k,
                          aecDataType dtype, uint32_t semantic_kernel,
                          uint32_t variant, aecDim3 grid, aecDim3 block,
                          PreparedMatmul &prepared) {
    uint64_t a_elements = 0;
    uint64_t b_elements = 0;
    uint64_t c_elements = 0;
    if (!checked_multiply(m, k, a_elements) ||
        !checked_multiply(k, n, b_elements) ||
        !checked_multiply(m, n, c_elements)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    uint64_t a_bytes = 0;
    uint64_t b_bytes = 0;
    uint64_t c_bytes = 0;
    if (!storage_bytes(a_elements, dtype, false, a_bytes) ||
        !storage_bytes(b_elements, dtype, false, b_bytes) ||
        !storage_bytes(c_elements, dtype, true, c_bytes)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    if (spans_overlap(a, a_bytes, b, b_bytes) ||
        spans_overlap(a, a_bytes, c, c_bytes) ||
        spans_overlap(b, b_bytes, c, c_bytes)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    if (variant == AEC_KERNEL_VARIANT_TILED &&
        ((m | n | k) & 3u) != 0) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    if (variant == AEC_KERNEL_VARIANT_VECTORIZED &&
        (((m | n | k) & 7u) != 0 || (a | b | c) % 16 != 0)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    aecError_t status = acquire_device_span(a, a_bytes, prepared.a_lease);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(b, b_bytes, prepared.b_lease);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(c, c_bytes, prepared.c_lease);
    if (status != AEC_SUCCESS) return status;

    ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> parameters;
    if (!parameters.put_u64(0, a) || !parameters.put_u64(8, b) ||
        !parameters.put_u64(16, c) || !parameters.put_u32(24, m) ||
        !parameters.put_u32(28, n) || !parameters.put_u32(32, k) ||
        !parameters.put_u32(36, static_cast<uint32_t>(dtype))) {
        return AEC_ERROR_INTERNAL;
    }
    const aecError_t command_status = build_isa_command(
        semantic_kernel, static_cast<uint32_t>(dtype), variant, grid, block,
        parameters.data(), AEC_KERNEL_PARAM_GEMM_BYTES, prepared.command);
    if (command_status != AEC_SUCCESS) return command_status;
    if (variant == AEC_KERNEL_VARIANT_TILED) {
        prepared.command.dynamic_shared_bytes = 4096;
    } else if (variant == AEC_KERNEL_VARIANT_VECTORIZED) {
        prepared.command.dynamic_shared_bytes = 8192;
    }
    return AEC_SUCCESS;
}

aecError_t execute_or_enqueue(const std::shared_ptr<PreparedMatmul> &prepared,
                              aecError_t status, aecStream_t stream) {
    if (stream == nullptr) {
        if (status != AEC_SUCCESS) return status;
        return submit_and_validate_completion(prepared->command);
    }
    return enqueue_stream_work(stream, [prepared, status](uint64_t stream_id) {
        if (status != AEC_SUCCESS) return status;
        prepared->command.stream_id = stream_id;
        return submit_and_validate_completion(prepared->command);
    });
}

} // namespace

aecError_t matmul(aecDevicePtr a, aecDevicePtr b, aecDevicePtr c,
                  uint32_t m, uint32_t n, uint32_t k, aecDataType dtype,
                  aecStream_t stream) {
    if (m == 0 || n == 0 || k == 0 || m > kMaxMatrixDimension ||
        n > kMaxMatrixDimension || k > kMaxMatrixDimension) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    auto prepared = std::make_shared<PreparedMatmul>();
    const aecError_t status = prepare_matmul(
        a, b, c, m, n, k, dtype, AEC_KERNEL_GEMM_NAIVE,
        AEC_KERNEL_VARIANT_NAIVE, {1, 1, 1}, {1, 1, 1}, *prepared);
    return execute_or_enqueue(prepared, status, stream);
}

aecError_t launch_matmul(aecKernelId kernel, aecDim3 grid, aecDim3 block,
                         const aecGemmArgs &args, aecStream_t stream) {
    if (args.reserved != 0 || args.m == 0 || args.n == 0 || args.k == 0 ||
        args.m > kMaxMatrixDimension || args.n > kMaxMatrixDimension ||
        args.k > kMaxMatrixDimension) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    uint32_t variant = 0;
    switch (kernel) {
    case AEC_KERNEL_GEMM_NAIVE: variant = AEC_KERNEL_VARIANT_NAIVE; break;
    case AEC_KERNEL_GEMM_TILED: variant = AEC_KERNEL_VARIANT_TILED; break;
    case AEC_KERNEL_GEMM_VECTORIZED:
        variant = AEC_KERNEL_VARIANT_VECTORIZED;
        break;
    default: return AEC_ERROR_INVALID_ARGUMENT;
    }
    auto prepared = std::make_shared<PreparedMatmul>();
    const aecError_t status = prepare_matmul(
        args.a, args.b, args.c, args.m, args.n, args.k,
        static_cast<aecDataType>(args.dtype), static_cast<uint32_t>(kernel),
        variant, grid, block, *prepared);
    return execute_or_enqueue(prepared, status, stream);
}

} // namespace aec
