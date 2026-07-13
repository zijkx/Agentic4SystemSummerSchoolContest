#include "kernel.h"

#include "aec_device_abi.h"
#include "aec_isa.h"
#include "allocation.h"
#include "command.h"
#include "error.h"
#include "library_ops.h"
#include "numeric.h"
#include "serialization.h"
#include "stream.h"

#include <cstring>
#include <limits>
#include <memory>

namespace aec {
namespace {

constexpr uint64_t kMaxVectorElements = 1048576;

struct PreparedLaunch {
    aecDeviceCommand command{};
    AllocationLease first;
    AllocationLease second;
    AllocationLease output;
};

template <typename Field>
void read_field(const uint8_t *raw, size_t offset, Field &field) noexcept {
    std::memcpy(&field, raw + offset, sizeof(field));
}

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

aecError_t launch(int kernel, aecDim3 grid, aecDim3 block,
                  const void *args, size_t args_size, aecStream_t stream) {
    const aecError_t dimension_status = validate_dimensions(grid, block);
    if (dimension_status != AEC_SUCCESS) return dimension_status;
    if (args == nullptr) return AEC_ERROR_INVALID_ARGUMENT;

    // Read each native API field independently so caller alignment is not
    // assumed and native tail padding can never enter the wire parameter block.
    const auto *raw_args = static_cast<const uint8_t *>(args);
    if (kernel == AEC_KERNEL_VECTOR_ADD_F32) {
        if (args_size != sizeof(aecVectorAddArgs)) {
            return AEC_ERROR_INVALID_ARGUMENT;
        }
        aecVectorAddArgs vector_args{};
        read_field(raw_args, offsetof(aecVectorAddArgs, a), vector_args.a);
        read_field(raw_args, offsetof(aecVectorAddArgs, b), vector_args.b);
        read_field(raw_args, offsetof(aecVectorAddArgs, c), vector_args.c);
        read_field(raw_args, offsetof(aecVectorAddArgs, count),
                   vector_args.count);
        auto prepared = std::make_shared<PreparedLaunch>();
        const aecError_t status = prepare_vector_add(
            grid, block, vector_args, *prepared);
        if (stream == nullptr) {
            if (status != AEC_SUCCESS) return status;
            return submit_and_validate_completion(prepared->command);
        }
        return enqueue_stream_work(stream,
            [prepared, status](uint64_t stream_id) {
                if (status != AEC_SUCCESS) return status;
                prepared->command.stream_id = stream_id;
                return submit_and_validate_completion(prepared->command);
            });
    }

    if (kernel == AEC_KERNEL_GEMM_NAIVE ||
        kernel == AEC_KERNEL_GEMM_TILED ||
        kernel == AEC_KERNEL_GEMM_VECTORIZED) {
        if (args_size != sizeof(aecGemmArgs)) return AEC_ERROR_INVALID_ARGUMENT;
        aecGemmArgs gemm_args{};
        read_field(raw_args, offsetof(aecGemmArgs, a), gemm_args.a);
        read_field(raw_args, offsetof(aecGemmArgs, b), gemm_args.b);
        read_field(raw_args, offsetof(aecGemmArgs, c), gemm_args.c);
        read_field(raw_args, offsetof(aecGemmArgs, m), gemm_args.m);
        read_field(raw_args, offsetof(aecGemmArgs, n), gemm_args.n);
        read_field(raw_args, offsetof(aecGemmArgs, k), gemm_args.k);
        read_field(raw_args, offsetof(aecGemmArgs, dtype), gemm_args.dtype);
        read_field(raw_args, offsetof(aecGemmArgs, reserved),
                   gemm_args.reserved);
        return launch_matmul(static_cast<aecKernelId>(kernel), grid, block,
                             gemm_args, stream);
    }

    if (kernel == AEC_KERNEL_AXPY_F32) {
        if (args_size != sizeof(aecAxpyArgs)) return AEC_ERROR_INVALID_ARGUMENT;
        aecAxpyArgs axpy_args{};
        read_field(raw_args, offsetof(aecAxpyArgs, x), axpy_args.x);
        read_field(raw_args, offsetof(aecAxpyArgs, y), axpy_args.y);
        read_field(raw_args, offsetof(aecAxpyArgs, count), axpy_args.count);
        read_field(raw_args, offsetof(aecAxpyArgs, alpha), axpy_args.alpha);
        read_field(raw_args, offsetof(aecAxpyArgs, reserved),
                   axpy_args.reserved);
        return launch_axpy(grid, block, axpy_args, stream);
    }

    if (kernel == AEC_KERNEL_DOT_F32) {
        if (args_size != sizeof(aecDotArgs)) return AEC_ERROR_INVALID_ARGUMENT;
        aecDotArgs dot_args{};
        read_field(raw_args, offsetof(aecDotArgs, x), dot_args.x);
        read_field(raw_args, offsetof(aecDotArgs, y), dot_args.y);
        read_field(raw_args, offsetof(aecDotArgs, result), dot_args.result);
        read_field(raw_args, offsetof(aecDotArgs, count), dot_args.count);
        return launch_dot(grid, block, dot_args, stream);
    }

    if (kernel == AEC_KERNEL_NRM2_F32) {
        if (args_size != sizeof(aecNrm2Args)) return AEC_ERROR_INVALID_ARGUMENT;
        aecNrm2Args nrm2_args{};
        read_field(raw_args, offsetof(aecNrm2Args, x), nrm2_args.x);
        read_field(raw_args, offsetof(aecNrm2Args, result), nrm2_args.result);
        read_field(raw_args, offsetof(aecNrm2Args, count), nrm2_args.count);
        return launch_nrm2(grid, block, nrm2_args, stream);
    }
    return AEC_ERROR_INVALID_ARGUMENT;
}

} // namespace aec
