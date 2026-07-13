#!/usr/bin/env python3
"""R201 GEMM boundaries, overlap, FP32, and INT32 saturation checks."""

from __future__ import annotations

import argparse
import ctypes
import math
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
INVALID_ADDRESS = 4


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
    root = args.submission.resolve()
    runtime = ctypes.CDLL(str(root / "libaec.so"))
    u64 = ctypes.c_uint64
    runtime.aecAlloc.argtypes = [ctypes.POINTER(u64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [u64]
    runtime.aecFree.restype = ctypes.c_int
    runtime.aecCopyH2D.argtypes = [u64, ctypes.c_void_p, ctypes.c_size_t]
    runtime.aecCopyH2D.restype = ctypes.c_int
    runtime.aecCopyD2H.argtypes = [ctypes.c_void_p, u64, ctypes.c_size_t]
    runtime.aecCopyD2H.restype = ctypes.c_int
    common = [u64, u64, u64, ctypes.c_uint32, ctypes.c_uint32,
              ctypes.c_uint32, ctypes.c_void_p]
    runtime.aecMatmulF32.argtypes = common
    runtime.aecMatmulF32.restype = ctypes.c_int
    runtime.aecMatmulI32.argtypes = common
    runtime.aecMatmulI32.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int

    allocations: list[int] = []

    def alloc(size: int) -> int:
        pointer = u64()
        assert runtime.aecAlloc(ctypes.byref(pointer), size) == SUCCESS
        allocations.append(pointer.value)
        return pointer.value

    try:
        fa, fb, fc = alloc(8), alloc(8), alloc(4)
        host_a = ctypes.create_string_buffer(struct.pack("<2f", 1.5, -2.0))
        host_b = ctypes.create_string_buffer(struct.pack("<2f", 4.0, 3.0))
        output = ctypes.create_string_buffer(4)
        assert runtime.aecCopyH2D(fa, host_a, 8) == SUCCESS
        assert runtime.aecCopyH2D(fb, host_b, 8) == SUCCESS
        assert runtime.aecResetRuntimeStats() == SUCCESS
        assert runtime.aecMatmulF32(fa, fb, fc, 1, 1, 2, None) == SUCCESS
        assert runtime.aecCopyD2H(output, fc, 4) == SUCCESS
        assert math.isclose(struct.unpack("<f", output.raw)[0], 0.0, abs_tol=1e-6)

        ia, ib, ic = alloc(8), alloc(8), alloc(4)
        maximum = (1 << 31) - 1
        int_a = ctypes.create_string_buffer(struct.pack("<2i", maximum, maximum))
        int_b = ctypes.create_string_buffer(struct.pack("<2i", maximum, maximum))
        int_output = ctypes.create_string_buffer(4)
        assert runtime.aecCopyH2D(ia, int_a, 8) == SUCCESS
        assert runtime.aecCopyH2D(ib, int_b, 8) == SUCCESS
        assert runtime.aecMatmulI32(ia, ib, ic, 1, 1, 2, None) == SUCCESS
        assert runtime.aecCopyD2H(int_output, ic, 4) == SUCCESS
        assert struct.unpack("<i", int_output.raw)[0] == maximum

        stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
        assert stats.kernel_commands == 2 and stats.isa_launches == 2
        submitted = stats.submitted_commands
        assert runtime.aecMatmulF32(fa, fb, fc, 0, 1, 2, None) == INVALID_ARGUMENT
        assert runtime.aecMatmulF32(fa, fb, fc, 257, 1, 2, None) == INVALID_ARGUMENT
        assert runtime.aecMatmulF32(fa, fb, fa, 1, 1, 2, None) == INVALID_ARGUMENT
        assert runtime.aecMatmulF32(fa + 4, fb, fc, 1, 1, 2, None) == INVALID_ADDRESS
        final = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(final)) == SUCCESS
        assert final.submitted_commands == submitted
    finally:
        for pointer in reversed(allocations):
            assert runtime.aecFree(pointer) == SUCCESS

    print("PASS custom R201: FP32, INT32 saturation, dimensions, overlap, spans")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
