#include "aec_device_abi.h"
#include "serialization.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

int main() {
    aec::ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> block;
    assert(block.put_u64(0, UINT64_C(0x0102030405060708)));
    assert(block.put_u64(8, UINT64_C(0x1112131415161718)));
    assert(block.put_u64(16, UINT64_C(0x2122232425262728)));
    assert(block.put_u64(24, UINT64_C(0x3132333435363738)));

    const std::array<uint8_t, 32> expected = {
        0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01,
        0x18, 0x17, 0x16, 0x15, 0x14, 0x13, 0x12, 0x11,
        0x28, 0x27, 0x26, 0x25, 0x24, 0x23, 0x22, 0x21,
        0x38, 0x37, 0x36, 0x35, 0x34, 0x33, 0x32, 0x31,
    };
    for (std::size_t index = 0; index < expected.size(); ++index) {
        assert(block.bytes()[index] == expected[index]);
    }
    for (std::size_t index = expected.size(); index < block.size(); ++index) {
        assert(block.bytes()[index] == 0);
    }
    assert(!block.put_u64(AEC_DEVICE_MAX_PARAM_BYTES - 7, 1));

    aec::ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> gemm;
    assert(gemm.put_u64(0, UINT64_C(0x0102030405060708)));
    assert(gemm.put_u64(8, UINT64_C(0x1112131415161718)));
    assert(gemm.put_u64(16, UINT64_C(0x2122232425262728)));
    assert(gemm.put_u32(24, UINT32_C(0x31323334)));
    assert(gemm.put_u32(28, UINT32_C(0x41424344)));
    assert(gemm.put_u32(32, UINT32_C(0x51525354)));
    assert(gemm.put_u32(36, UINT32_C(0x61626364)));
    assert(gemm.bytes()[24] == 0x34 && gemm.bytes()[27] == 0x31);
    assert(gemm.bytes()[28] == 0x44 && gemm.bytes()[31] == 0x41);
    assert(gemm.bytes()[32] == 0x54 && gemm.bytes()[35] == 0x51);
    assert(gemm.bytes()[36] == 0x64 && gemm.bytes()[39] == 0x61);
    for (std::size_t index = 40; index < gemm.size(); ++index) {
        assert(gemm.bytes()[index] == 0);
    }

    aec::ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> axpy;
    assert(axpy.put_u64(0, UINT64_C(0x0102030405060708)));
    assert(axpy.put_u64(8, UINT64_C(0x1112131415161718)));
    assert(axpy.put_u64(16, UINT64_C(0x2122232425262728)));
    assert(axpy.put_f32(24, 1.0f));
    assert(axpy.bytes()[24] == 0x00 && axpy.bytes()[25] == 0x00 &&
           axpy.bytes()[26] == 0x80 && axpy.bytes()[27] == 0x3f);
    for (std::size_t index = 28; index < axpy.size(); ++index) {
        assert(axpy.bytes()[index] == 0);
    }

    aec::ParameterBlock<AEC_DEVICE_MAX_PARAM_BYTES> reduction;
    assert(reduction.put_u64(0, 1));
    assert(reduction.put_u64(8, 2));
    assert(reduction.put_u64(16, 3));
    assert(reduction.put_u64(24, 4));
    for (std::size_t index = 32; index < reduction.size(); ++index) {
        assert(reduction.bytes()[index] == 0);
    }
    return 0;
}
