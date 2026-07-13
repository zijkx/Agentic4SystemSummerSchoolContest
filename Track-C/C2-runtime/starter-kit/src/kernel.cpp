#include "kernel.h"

#include "aec_device_abi.h"
#include "aec_isa.h"
#include "allocation.h"
#include "command.h"
#include "error.h"
#include "serialization.h"

#include <cstring>
#include <limits>

namespace aec {
namespace {

constexpr uint64_t kMaxVectorElements = 1048576;

struct PreparedLaunch {
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

aecError_t validate_dimensions(aecDim3 grid, aecDim3 block) {
    if (grid.x == 0 || grid.y == 0 || grid.z == 0 ||
        block.x == 0 || block.y == 0 || block.z == 0) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    const uint64_t xy = static_cast<uint64_t>(block.x) * block.y;
    if (block.z != 0 && xy > std::numeric_limits<uint64_t>::max() / block.z) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    const uint64_t volume = xy * block.z;
    aecDeviceCaps caps{};
    const aecError_t caps_status = map_device_status(aecDeviceGetCaps(&caps));
    if (caps_status != AEC_SUCCESS) return caps_status;
    if (caps.abi_version != AEC_DEVICE_ABI_VERSION ||
        volume > caps.max_threads_per_block) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    return AEC_SUCCESS;
}

aecError_t resolve_kernel(uint32_t semantic_kernel, uint32_t dtype,
                          uint32_t variant, uint32_t parameter_bytes,
                          aecDeviceKernelInfo &info) {
    const aecError_t status = map_device_status(aecDeviceResolveKernel(
        semantic_kernel, dtype, variant, &info));
    if (status != AEC_SUCCESS) return status;
    if (info.abi_version != AEC_DEVICE_ABI_VERSION ||
        info.isa_version != AEC_ISA_VERSION || info.handle == 0 ||
        info.parameter_bytes != parameter_bytes || info.instruction_hash == 0) {
        return AEC_ERROR_INTERNAL;
    }
    return AEC_SUCCESS;
}

aecError_t prepare_vector_add(aecDim3 grid, aecDim3 block,
                              const aecVectorAddArgs &args,
                              PreparedLaunch &prepared) {
    if (args.count == 0 || args.count > kMaxVectorElements ||
        args.count > std::numeric_limits<uint64_t>::max() / sizeof(float)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }
    const uint64_t bytes = args.count * sizeof(float);
    if (spans_overlap(args.c, bytes, args.a, bytes) ||
        spans_overlap(args.c, bytes, args.b, bytes)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    aecError_t status = acquire_device_span(args.a, bytes, prepared.first);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(args.b, bytes, prepared.second);
    if (status != AEC_SUCCESS) return status;
    status = acquire_device_span(args.c, bytes, prepared.output);
    if (status != AEC_SUCCESS) return status;

    ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> parameters;
    if (!parameters.put_u64(0, args.a) || !parameters.put_u64(8, args.b) ||
        !parameters.put_u64(16, args.c) ||
        !parameters.put_u64(24, args.count)) {
        return AEC_ERROR_INTERNAL;
    }

    return build_isa_command(
        AEC_KERNEL_VECTOR_ADD_F32, AEC_DTYPE_FP32,
        AEC_KERNEL_VARIANT_DEFAULT, grid, block, parameters.data(),
        AEC_KERNEL_PARAM_VECTOR_ADD_BYTES, prepared.command);
}

} // namespace

aecError_t build_isa_command(uint32_t semantic_kernel, uint32_t dtype,
                             uint32_t variant, aecDim3 grid, aecDim3 block,
                             const uint8_t *parameters,
                             uint32_t parameter_bytes,
                             aecDeviceCommand &command) {
    const aecError_t dimension_status = validate_dimensions(grid, block);
    if (dimension_status != AEC_SUCCESS) return dimension_status;
    if (parameters == nullptr || parameter_bytes == 0 ||
        parameter_bytes > AEC_DEVICE_MAX_PARAM_BYTES) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    aecDeviceKernelInfo info{};
    const aecError_t resolve_status = resolve_kernel(
        semantic_kernel, dtype, variant, parameter_bytes, info);
    if (resolve_status != AEC_SUCCESS) return resolve_status;

    command = {};
    command.abi_version = AEC_DEVICE_ABI_VERSION;
    command.opcode = AEC_DEVICE_OP_ISA_LAUNCH;
    command.kernel_handle = info.handle;
    command.isa_version = info.isa_version;
    command.entry_pc = info.entry_pc;
    command.grid = {grid.x, grid.y, grid.z};
    command.block = {block.x, block.y, block.z};
    command.parameter_bytes = info.parameter_bytes;
    std::memcpy(command.parameters, parameters, parameter_bytes);
    return AEC_SUCCESS;
}

aecError_t launch(aecKernelId kernel, aecDim3 grid, aecDim3 block,
                  const void *args, size_t args_size, aecStream_t stream) {
    if (stream != nullptr) return AEC_ERROR_NOT_SUPPORTED;
    const aecError_t dimension_status = validate_dimensions(grid, block);
    if (dimension_status != AEC_SUCCESS) return dimension_status;
    if (args == nullptr) return AEC_ERROR_INVALID_ARGUMENT;

    if (kernel != AEC_KERNEL_VECTOR_ADD_F32) {
        return AEC_ERROR_NOT_SUPPORTED;
    }
    if (args_size != sizeof(aecVectorAddArgs)) {
        return AEC_ERROR_INVALID_ARGUMENT;
    }

    // Read each native API field independently so caller alignment is not
    // assumed and native tail padding can never enter the wire parameter block.
    const auto *raw_args = static_cast<const uint8_t *>(args);
    aecVectorAddArgs vector_args{};
    std::memcpy(&vector_args.a, raw_args + offsetof(aecVectorAddArgs, a),
                sizeof(vector_args.a));
    std::memcpy(&vector_args.b, raw_args + offsetof(aecVectorAddArgs, b),
                sizeof(vector_args.b));
    std::memcpy(&vector_args.c, raw_args + offsetof(aecVectorAddArgs, c),
                sizeof(vector_args.c));
    std::memcpy(&vector_args.count,
                raw_args + offsetof(aecVectorAddArgs, count),
                sizeof(vector_args.count));
    PreparedLaunch prepared;
    const aecError_t status = prepare_vector_add(
        grid, block, vector_args, prepared);
    if (status != AEC_SUCCESS) return status;
    return submit_and_validate_completion(prepared.command);
}

} // namespace aec
