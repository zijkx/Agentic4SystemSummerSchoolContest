#ifndef AEC_RUNTIME_REGISTRATION_H
#define AEC_RUNTIME_REGISTRATION_H

#include "aec_runtime.h"

#include <cstddef>
#include <cstdint>
#include <memory>

namespace aec {

struct RegistrationRecord;

class RegistrationLease {
public:
    RegistrationLease() noexcept = default;
    RegistrationLease(const RegistrationLease &) = delete;
    RegistrationLease &operator=(const RegistrationLease &) = delete;
    RegistrationLease(RegistrationLease &&other) noexcept;
    RegistrationLease &operator=(RegistrationLease &&other) noexcept;
    ~RegistrationLease();

    explicit operator bool() const noexcept { return record_ != nullptr; }

private:
    friend aecError_t acquire_registered_span(void *, uint64_t,
                                              RegistrationLease &, bool &);
    explicit RegistrationLease(std::shared_ptr<RegistrationRecord> record) noexcept;
    void release() noexcept;

    std::shared_ptr<RegistrationRecord> record_;
};

aecError_t host_register(void *ptr, size_t bytes);
aecError_t host_unregister(void *ptr);
aecError_t acquire_registered_span(void *ptr, uint64_t bytes,
                                   RegistrationLease &lease,
                                   bool &registered);

} // namespace aec

#endif
