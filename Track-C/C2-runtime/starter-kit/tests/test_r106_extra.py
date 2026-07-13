#!/usr/bin/env python3
"""Event generation, marker ordering, stale handle, and race checks."""

from __future__ import annotations

import argparse
import ctypes
import threading
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
INVALID_HANDLE = 3
NOT_READY = 5
H2D = 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    runtime = ctypes.CDLL(str(args.submission.resolve() / "libaec.so"))
    ptr = ctypes.c_void_p
    u64 = ctypes.c_uint64
    runtime.aecAlloc.argtypes = [ctypes.POINTER(u64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [u64]
    runtime.aecFree.restype = ctypes.c_int
    runtime.aecCopyAsync.argtypes = [u64, ptr, ctypes.c_size_t, ctypes.c_int, ptr]
    runtime.aecCopyAsync.restype = ctypes.c_int
    runtime.aecStreamCreate.argtypes = [ctypes.POINTER(ptr)]
    runtime.aecStreamCreate.restype = ctypes.c_int
    runtime.aecStreamDestroy.argtypes = [ptr]
    runtime.aecStreamDestroy.restype = ctypes.c_int
    runtime.aecEventCreate.argtypes = [ctypes.POINTER(ptr)]
    runtime.aecEventCreate.restype = ctypes.c_int
    runtime.aecEventDestroy.argtypes = [ptr]
    runtime.aecEventDestroy.restype = ctypes.c_int
    runtime.aecEventRecord.argtypes = [ptr, ptr]
    runtime.aecEventRecord.restype = ctypes.c_int
    runtime.aecEventSynchronize.argtypes = [ptr]
    runtime.aecEventSynchronize.restype = ctypes.c_int
    runtime.aecEventQuery.argtypes = [ptr]
    runtime.aecEventQuery.restype = ctypes.c_int
    runtime.aecEventElapsedCycles.argtypes = [ptr, ptr, ctypes.POINTER(u64)]
    runtime.aecEventElapsedCycles.restype = ctypes.c_int

    assert runtime.aecEventCreate(None) == INVALID_ARGUMENT
    assert runtime.aecEventQuery(None) == INVALID_HANDLE
    assert runtime.aecEventDestroy(None) == INVALID_HANDLE
    stream = ptr()
    assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
    events = [ptr() for _ in range(3)]
    for event in events:
        assert runtime.aecEventCreate(ctypes.byref(event)) == SUCCESS
    start, repeated, end = events
    device = u64()
    assert runtime.aecAlloc(ctypes.byref(device), 1024 * 1024) == SUCCESS
    host = ctypes.create_string_buffer(1024 * 1024)
    try:
        assert runtime.aecEventQuery(start) == INVALID_ARGUMENT
        assert runtime.aecEventSynchronize(start) == INVALID_ARGUMENT
        assert runtime.aecEventRecord(start, stream) == SUCCESS
        assert runtime.aecEventRecord(repeated, stream) == SUCCESS
        assert runtime.aecCopyAsync(device.value, host, len(host), H2D, stream) == SUCCESS
        assert runtime.aecEventRecord(repeated, stream) == SUCCESS
        assert runtime.aecEventRecord(end, stream) == SUCCESS
        assert runtime.aecEventQuery(end) in (SUCCESS, NOT_READY)
        assert runtime.aecEventSynchronize(repeated) == SUCCESS
        assert runtime.aecEventSynchronize(end) == SUCCESS
        cycles = u64()
        assert runtime.aecEventElapsedCycles(start, end, ctypes.byref(cycles)) == SUCCESS
        assert cycles.value > 0
        assert runtime.aecEventElapsedCycles(repeated, repeated,
                                             ctypes.byref(cycles)) == SUCCESS
        assert cycles.value == 0
        assert runtime.aecEventElapsedCycles(end, start,
                                             ctypes.byref(cycles)) == INVALID_ARGUMENT

        stale_stream = ptr(stream.value)
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        unrecorded = ptr()
        assert runtime.aecEventCreate(ctypes.byref(unrecorded)) == SUCCESS
        assert runtime.aecEventRecord(unrecorded, stale_stream) == INVALID_HANDLE
        assert runtime.aecEventQuery(unrecorded) == INVALID_ARGUMENT
        assert runtime.aecEventDestroy(unrecorded) == SUCCESS
    finally:
        for event in events:
            assert runtime.aecEventDestroy(event) == SUCCESS
            assert runtime.aecEventDestroy(event) == INVALID_HANDLE
        assert runtime.aecFree(device.value) == SUCCESS

    race_stream = ptr()
    assert runtime.aecStreamCreate(ctypes.byref(race_stream)) == SUCCESS
    for _ in range(20):
        event = ptr()
        assert runtime.aecEventCreate(ctypes.byref(event)) == SUCCESS
        statuses: list[int] = []

        def recorder() -> None:
            statuses.append(runtime.aecEventRecord(event, race_stream))

        thread = threading.Thread(target=recorder)
        thread.start()
        destroy_status = runtime.aecEventDestroy(event)
        thread.join()
        assert destroy_status == SUCCESS
        assert statuses[0] in (SUCCESS, INVALID_HANDLE)
    assert runtime.aecStreamDestroy(race_stream) == SUCCESS

    print("PASS custom R106: latest generation/cycles/stale handles and 20 destroy races")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
