#ifndef AEC_RUNTIME_STREAM_H
#define AEC_RUNTIME_STREAM_H

#include "aec_runtime.h"

#include <cstdint>
#include <functional>

namespace aec {

using StreamWork = std::function<aecError_t(uint64_t stream_id)>;

aecError_t stream_create(aecStream_t *stream);
aecError_t stream_destroy(aecStream_t stream);
aecError_t stream_sync(aecStream_t stream);
aecError_t enqueue_stream_work(aecStream_t stream, StreamWork work);

} // namespace aec

#endif
