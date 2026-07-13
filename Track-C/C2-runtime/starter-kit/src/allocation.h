#ifndef AEC_RUNTIME_ALLOCATION_H
#define AEC_RUNTIME_ALLOCATION_H

#include "aec_runtime.h"

#include <cstddef>
#include <cstdint>
#include <memory>

namespace aec {

struct AllocationRecord;

class AllocationLease {
public:
    AllocationLease() noexcept = default;
    AllocationLease(const AllocationLease &) = delete;
    AllocationLease &operator=(const AllocationLease &) = delete;
    AllocationLease(AllocationLease &&other) noexcept;
    AllocationLease &operator=(AllocationLease &&other) noexcept;
    ~AllocationLease();

    explicit operator bool() const noexcept { return record_ != nullptr; }

private:
    friend aecError_t acquire_device_span(aecDevicePtr, uint64_t,
                                          AllocationLease &);
    explicit AllocationLease(std::shared_ptr<AllocationRecord> record) noexcept;
    void release() noexcept;

    std::shared_ptr<AllocationRecord> record_;
};

aecError_t allocate_device(aecDevicePtr *out_ptr, size_t bytes);
aecError_t free_device(aecDevicePtr ptr);
aecError_t acquire_device_span(aecDevicePtr ptr, uint64_t bytes,
                               AllocationLease &lease);

} // namespace aec

#endif
