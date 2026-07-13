#include "library_ops.h"

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

constexpr uint64_t kMaxVectorElements = 1048576;

struct PreparedVectorOp {
    aecDeviceCommand command{};
    AllocationLease first;
    AllocationLease second;
    AllocationLease output;
};

bool spans_overlap(aecDevicePtr left, uint64_t left_bytes,
                   aecDevicePtr right, uint64_t right_bytes) noexcept {
    if (left <= right) return right - left < left_bytes;
    return left - right < right_bytes;
}

aecError_t vector_bytes(uint64_t count, uint64_t &bytes) noexcept {
    if (count == 0 || count > kMaxVectorElements ||
        count > std::numeric_limits<uint64_t>::max() / sizeof(float)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    bytes = count * sizeof(float);
    return AEC_SUCCESS;
}

aecError_t execute_or_enqueue(const std::shared_ptr<PreparedVectorOp> &prepared,
                              aecError_t preflight, aecStream_t stream) {
    if (stream == nullptr) {
        if (preflight != AEC_SUCCESS) return preflight;
        return submit_and_validate_completion(prepared->command);
    }
    return enqueue_stream_work(stream, [prepared, preflight](uint64_t stream_id) {
        if (preflight != AEC_SUCCESS) return preflight;
        prepared->command.stream_id = stream_id;
        return submit_and_validate_completion(prepared->command);
    });
}

aecError_t prepare_axpy(aecDevicePtr x, aecDevicePtr y, uint64_t count,
                        float alpha, PreparedVectorOp &prepared) {
    uint64_t bytes = 0;
    aecError_t status = vector_bytes(count, bytes);
    if (status != AEC_SUCCESS) return status;
    if (x != y && spans_overlap(x, bytes, y, bytes)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    status = acquire_device_span(x, bytes, prepared.first);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(y, bytes, prepared.output);
    if (status != AEC_SUCCESS) return status;

    ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> parameters;
    if (!parameters.put_u64(0, x) || !parameters.put_u64(8, y) ||
        !parameters.put_u64(16, count) || !parameters.put_f32(24, alpha)) {
        return AEC_ERROR_INTERNAL;
    }
    const uint32_t grid_x = static_cast<uint32_t>((count + 31) / 32);
    return build_isa_command(
        AEC_KERNEL_AXPY_F32, AEC_DTYPE_FP32, AEC_KERNEL_VARIANT_DEFAULT,
        {grid_x, 1, 1}, {32, 1, 1}, parameters.data(),
        AEC_KERNEL_PARAM_AXPY_BYTES, prepared.command);
}

aecError_t prepare_dot(aecDevicePtr x, aecDevicePtr y, aecDevicePtr result,
                       uint64_t count, PreparedVectorOp &prepared) {
    uint64_t bytes = 0;
    aecError_t status = vector_bytes(count, bytes);
    if (status != AEC_SUCCESS) return status;
    if (spans_overlap(result, sizeof(float), x, bytes) ||
        spans_overlap(result, sizeof(float), y, bytes)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    status = acquire_device_span(x, bytes, prepared.first);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(y, bytes, prepared.second);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(result, sizeof(float), prepared.output);
    if (status != AEC_SUCCESS) return status;

    ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> parameters;
    if (!parameters.put_u64(0, x) || !parameters.put_u64(8, y) ||
        !parameters.put_u64(16, result) ||
        !parameters.put_u64(24, count)) {
        return AEC_ERROR_INTERNAL;
    }
    return build_isa_command(
        AEC_KERNEL_DOT_F32, AEC_DTYPE_FP32, AEC_KERNEL_VARIANT_DEFAULT,
        {1, 1, 1}, {1, 1, 1}, parameters.data(), AEC_KERNEL_PARAM_DOT_BYTES,
        prepared.command);
}

aecError_t prepare_nrm2(aecDevicePtr x, aecDevicePtr result, uint64_t count,
                        PreparedVectorOp &prepared) {
    uint64_t bytes = 0;
    aecError_t status = vector_bytes(count, bytes);
    if (status != AEC_SUCCESS) return status;
    if (spans_overlap(result, sizeof(float), x, bytes)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    status = acquire_device_span(x, bytes, prepared.first);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(result, sizeof(float), prepared.output);
    if (status != AEC_SUCCESS) return status;

    ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> parameters;
    if (!parameters.put_u64(0, x) || !parameters.put_u64(8, result) ||
        !parameters.put_u64(16, count)) {
        return AEC_ERROR_INTERNAL;
    }
    return build_isa_command(
        AEC_KERNEL_NRM2_F32, AEC_DTYPE_FP32, AEC_KERNEL_VARIANT_DEFAULT,
        {1, 1, 1}, {1, 1, 1}, parameters.data(), AEC_KERNEL_PARAM_NRM2_BYTES,
        prepared.command);
}

} // namespace

aecError_t axpy(aecDevicePtr x, aecDevicePtr y, uint64_t count, float alpha,
                aecStream_t stream) {
    auto prepared = std::make_shared<PreparedVectorOp>();
    const aecError_t status = prepare_axpy(x, y, count, alpha, *prepared);
    return execute_or_enqueue(prepared, status, stream);
}

aecError_t dot(aecDevicePtr x, aecDevicePtr y, aecDevicePtr result,
               uint64_t count, aecStream_t stream) {
    auto prepared = std::make_shared<PreparedVectorOp>();
    const aecError_t status = prepare_dot(x, y, result, count, *prepared);
    return execute_or_enqueue(prepared, status, stream);
}

aecError_t nrm2(aecDevicePtr x, aecDevicePtr result, uint64_t count,
                aecStream_t stream) {
    auto prepared = std::make_shared<PreparedVectorOp>();
    const aecError_t status = prepare_nrm2(x, result, count, *prepared);
    return execute_or_enqueue(prepared, status, stream);
}

} // namespace aec
