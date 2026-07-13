#ifndef AEC_RUNTIME_EVENT_H
#define AEC_RUNTIME_EVENT_H

#include "aec_runtime.h"

#include <cstdint>

namespace aec {

aecError_t event_create(aecEvent_t *event);
aecError_t event_destroy(aecEvent_t event);
aecError_t event_record(aecEvent_t event, aecStream_t stream);
aecError_t event_synchronize(aecEvent_t event);
aecError_t event_query(aecEvent_t event);
aecError_t event_elapsed_cycles(aecEvent_t start, aecEvent_t end,
                                uint64_t *cycles);

} // namespace aec

#endif
