#ifndef AEC_RUNTIME_SERIALIZATION_H
#define AEC_RUNTIME_SERIALIZATION_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace aec {

template <size_t Size>
class ParameterBlock {
public:
    bool put_u32(size_t offset, uint32_t value) noexcept {
        if (offset > Size || Size - offset < 4) return false;
        for (size_t index = 0; index < 4; ++index) {
            bytes_[offset + index] = static_cast<uint8_t>(value >> (8 * index));
        }
        return true;
    }

    bool put_u64(size_t offset, uint64_t value) noexcept {
        if (offset > Size || Size - offset < 8) return false;
        for (size_t index = 0; index < 8; ++index) {
            bytes_[offset + index] = static_cast<uint8_t>(value >> (8 * index));
        }
        return true;
    }

    bool put_f32(size_t offset, float value) noexcept {
        uint32_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value));
        std::memcpy(&bits, &value, sizeof(bits));
        return put_u32(offset, bits);
    }

    const uint8_t *data() const noexcept { return bytes_.data(); }
    constexpr size_t size() const noexcept { return Size; }
    const std::array<uint8_t, Size> &bytes() const noexcept { return bytes_; }

private:
    std::array<uint8_t, Size> bytes_{};
};

} // namespace aec

#endif
