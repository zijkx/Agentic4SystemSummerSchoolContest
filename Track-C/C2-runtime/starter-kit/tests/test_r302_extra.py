#!/usr/bin/env python3
"""R302 multi-Stream channel use, concurrent FIFO, and recovery checks."""

from __future__ import annotations

import argparse
import ctypes
import threading
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
INVALID_HANDLE = 3
INVALID_ADDRESS = 4
H2D = 1
D2H = 2


class Stats(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32), ("reserved", ctypes.c_uint32),
        ("submitted_commands", ctypes.c_uint64), ("dma_commands", ctypes.c_uint64),
        ("kernel_commands", ctypes.c_uint64), ("zero_copy_commands", ctypes.c_uint64),
        ("channel_commands", ctypes.c_uint64 * 2),
        ("total_virtual_cycles", ctypes.c_uint64),
        ("last_virtual_cycles", ctypes.c_uint64),
        ("isa_launches", ctypes.c_uint64),
        ("instructions_retired", ctypes.c_uint64),
        ("isa_traps", ctypes.c_uint64),
        ("last_kernel_handle", ctypes.c_uint64),
        ("last_trace_digest", ctypes.c_uint64),
    ]


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
    runtime.aecStreamSync.argtypes = [ptr]
    runtime.aecStreamSync.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int

    streams = [ptr() for _ in range(4)]
    devices: list[int] = []
    sources = [ctypes.create_string_buffer(bytes([index + 1]) * 4096)
               for index in range(4)]
    targets = [ctypes.create_string_buffer(4096) for _ in range(4)]
    for stream in streams:
        assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
    for _ in streams:
        value = u64()
        assert runtime.aecAlloc(ctypes.byref(value), 4096) == SUCCESS
        devices.append(value.value)
    try:
        assert runtime.aecResetRuntimeStats() == SUCCESS
        for index, stream in enumerate(streams):
            assert runtime.aecCopyAsync(devices[index], sources[index], 4096,
                                        H2D, stream) == SUCCESS
            assert runtime.aecCopyAsync(devices[index], targets[index], 4096,
                                        D2H, stream) == SUCCESS
        sync_statuses: list[int] = []
        threads = [threading.Thread(
            target=lambda value=stream: sync_statuses.append(
                runtime.aecStreamSync(value))) for stream in streams]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sync_statuses == [SUCCESS] * 4
        for source, target in zip(sources, targets):
            assert target.raw == source.raw[:-1]
        stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
        assert stats.dma_commands == 8
        assert stats.channel_commands[0] > 0 and stats.channel_commands[1] > 0

        bad_host = ctypes.create_string_buffer(32)
        assert runtime.aecCopyAsync(devices[0] + 4090, bad_host, 16,
                                    H2D, streams[0]) == SUCCESS
        assert runtime.aecStreamSync(streams[0]) == INVALID_ADDRESS
        assert runtime.aecStreamSync(streams[0]) == SUCCESS
        assert runtime.aecCopyAsync(devices[0], bad_host, 16,
                                    H2D, streams[0]) == SUCCESS
        assert runtime.aecStreamSync(streams[0]) == SUCCESS
        assert runtime.aecCopyAsync(devices[0], bad_host, 16, 99,
                                    streams[0]) == INVALID_ARGUMENT
        assert runtime.aecCopyAsync(devices[0], bad_host, 16,
                                    H2D, None) == INVALID_HANDLE
    finally:
        for stream in streams:
            assert runtime.aecStreamDestroy(stream) == SUCCESS
        for device in devices:
            assert runtime.aecFree(device) == SUCCESS

    print("PASS custom R302: 4 Streams/both channels/concurrent FIFO/recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
