#!/usr/bin/env python3
"""R303 interval, subspan, zero-copy, and pending unregister checks."""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
H2D = 1


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


class AlignedBuffer:
    def __init__(self, size: int, alignment: int = 64):
        self.storage = (ctypes.c_ubyte * (size + alignment))()
        address = ctypes.addressof(self.storage)
        self.address = (address + alignment - 1) & ~(alignment - 1)
        self.ptr = ctypes.c_void_p(self.address)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    runtime = ctypes.CDLL(str(args.submission.resolve() / "libaec.so"))
    u64 = ctypes.c_uint64
    ptr = ctypes.c_void_p
    runtime.aecAlloc.argtypes = [ctypes.POINTER(u64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [u64]
    runtime.aecFree.restype = ctypes.c_int
    runtime.aecCopyH2D.argtypes = [u64, ptr, ctypes.c_size_t]
    runtime.aecCopyH2D.restype = ctypes.c_int
    runtime.aecCopyAsync.argtypes = [u64, ptr, ctypes.c_size_t, ctypes.c_int, ptr]
    runtime.aecCopyAsync.restype = ctypes.c_int
    runtime.aecHostRegister.argtypes = [ptr, ctypes.c_size_t]
    runtime.aecHostRegister.restype = ctypes.c_int
    runtime.aecHostUnregister.argtypes = [ptr]
    runtime.aecHostUnregister.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    runtime.aecStreamCreate.argtypes = [ctypes.POINTER(ptr)]
    runtime.aecStreamCreate.restype = ctypes.c_int
    runtime.aecStreamDestroy.argtypes = [ptr]
    runtime.aecStreamDestroy.restype = ctypes.c_int
    runtime.aecStreamSync.argtypes = [ptr]
    runtime.aecStreamSync.restype = ctypes.c_int

    assert runtime.aecHostRegister(None, 64) == INVALID_ARGUMENT
    buffer = AlignedBuffer(2 * 65536)
    base = buffer.address
    assert runtime.aecHostRegister(ptr(base), 65536) == SUCCESS
    assert runtime.aecHostRegister(ptr(base), 65536) == INVALID_ARGUMENT
    assert runtime.aecHostRegister(ptr(base + 64), 1024) == INVALID_ARGUMENT
    assert runtime.aecHostRegister(ptr(base + 65536 - 64), 128) == INVALID_ARGUMENT
    assert runtime.aecHostRegister(ptr(base + 65536), 65536) == SUCCESS
    assert runtime.aecHostUnregister(ptr(base + 1)) == INVALID_ARGUMENT
    assert runtime.aecHostUnregister(ptr(base + 65536)) == SUCCESS
    assert runtime.aecHostRegister(ptr((1 << 64) - 4), 8) == INVALID_ARGUMENT

    device = u64()
    assert runtime.aecAlloc(ctypes.byref(device), 65536) == SUCCESS
    try:
        assert runtime.aecResetRuntimeStats() == SUCCESS
        assert runtime.aecCopyH2D(device.value, ptr(base + 128), 4096) == SUCCESS
        stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
        assert stats.zero_copy_commands == 1

        # This span starts outside the registered interval and only overlaps
        # it; the copy remains legal but must use normal DMA flags.
        assert runtime.aecHostUnregister(ptr(base)) == SUCCESS
        assert runtime.aecHostRegister(ptr(base + 64), 65472) == SUCCESS
        assert runtime.aecResetRuntimeStats() == SUCCESS
        assert runtime.aecCopyH2D(device.value, ptr(base), 128) == SUCCESS
        partial = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(partial)) == SUCCESS
        assert partial.zero_copy_commands == 0
        assert runtime.aecHostUnregister(ptr(base + 64)) == SUCCESS

        assert runtime.aecHostRegister(ptr(base), 65536) == SUCCESS
        stream = ptr()
        assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
        assert runtime.aecCopyAsync(device.value, ptr(base), 65536,
                                    H2D, stream) == SUCCESS
        assert runtime.aecHostUnregister(ptr(base)) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        assert runtime.aecHostUnregister(ptr(base)) == INVALID_ARGUMENT
    finally:
        assert runtime.aecFree(device.value) == SUCCESS

    print("PASS custom R303: intervals/subspan/partial flags/pending unregister")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
