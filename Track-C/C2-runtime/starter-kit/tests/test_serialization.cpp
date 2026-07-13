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
    return 0;
}
