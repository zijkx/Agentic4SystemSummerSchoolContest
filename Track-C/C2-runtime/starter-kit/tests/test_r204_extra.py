#!/usr/bin/env python3
"""R204 alias, async, count, span, and preflight checks."""

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
    runtime = ctypes.CDLL(str(args.submission.resolve() / "libaec.so"))
    u64 = ctypes.c_uint64
    ptr = ctypes.c_void_p
    runtime.aecAlloc.argtypes = [ctypes.POINTER(u64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [u64]
    runtime.aecFree.restype = ctypes.c_int
    runtime.aecCopyH2D.argtypes = [u64, ptr, ctypes.c_size_t]
    runtime.aecCopyH2D.restype = ctypes.c_int
    runtime.aecCopyD2H.argtypes = [ptr, u64, ctypes.c_size_t]
    runtime.aecCopyD2H.restype = ctypes.c_int
    runtime.aecAxpy.argtypes = [u64, u64, u64, ctypes.c_float, ptr]
    runtime.aecAxpy.restype = ctypes.c_int
    runtime.aecDot.argtypes = [u64, u64, u64, u64, ptr]
    runtime.aecDot.restype = ctypes.c_int
    runtime.aecNrm2.argtypes = [u64, u64, u64, ptr]
    runtime.aecNrm2.restype = ctypes.c_int
    runtime.aecStreamCreate.argtypes = [ctypes.POINTER(ptr)]
    runtime.aecStreamCreate.restype = ctypes.c_int
    runtime.aecStreamDestroy.argtypes = [ptr]
    runtime.aecStreamDestroy.restype = ctypes.c_int
    runtime.aecStreamSync.argtypes = [ptr]
    runtime.aecStreamSync.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int

    allocations: list[int] = []

    def alloc(size: int) -> int:
        value = u64()
        assert runtime.aecAlloc(ctypes.byref(value), size) == SUCCESS
        allocations.append(value.value)
        return value.value

    try:
        raw = struct.pack("<3f", 1.0, -2.0, 0.5)
        vector = alloc(len(raw))
        result = alloc(4)
        host = ctypes.create_string_buffer(raw)
        output = ctypes.create_string_buffer(len(raw))
        scalar = ctypes.create_string_buffer(4)
        assert runtime.aecCopyH2D(vector, host, len(raw)) == SUCCESS
        assert runtime.aecAxpy(vector, vector, 3, ctypes.c_float(2.0), None) == SUCCESS
        assert runtime.aecCopyD2H(output, vector, len(raw)) == SUCCESS
        assert struct.unpack("<3f", output.raw) == (3.0, -6.0, 1.5)

        stream = ptr()
        assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
        assert runtime.aecDot(vector, vector, result, 3, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        assert runtime.aecCopyD2H(scalar, result, 4) == SUCCESS
        assert math.isclose(struct.unpack("<f", scalar.raw)[0], 47.25,
                            abs_tol=2e-5)
        assert runtime.aecNrm2(vector, result, 3, None) == SUCCESS
        assert runtime.aecCopyD2H(scalar, result, 4) == SUCCESS
        assert math.isclose(struct.unpack("<f", scalar.raw)[0], math.sqrt(47.25),
                            abs_tol=2e-5, rel_tol=5e-5)

        stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
        submitted = stats.submitted_commands
        assert runtime.aecAxpy(vector, vector + 4, 2, ctypes.c_float(1.0),
                               None) == INVALID_ARGUMENT
        assert runtime.aecAxpy(vector, vector, 0, ctypes.c_float(1.0),
                               None) == INVALID_ARGUMENT
        assert runtime.aecDot(vector, vector, vector, 3, None) == INVALID_ARGUMENT
        assert runtime.aecNrm2(vector + 8, result, 2, None) == INVALID_ADDRESS
        final = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(final)) == SUCCESS
        assert final.submitted_commands == submitted
    finally:
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print("PASS custom R204: AXPY alias, async DOT, NRM2, preflight bounds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
