#!/usr/bin/env python3
"""R204 DOT/NRM2 historical trap boundaries and maximum-length checks."""

from __future__ import annotations

import argparse
import ctypes
import math
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
MAX_COUNT = 1_048_576


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
    runtime.aecDot.argtypes = [u64, u64, u64, u64, ptr]
    runtime.aecDot.restype = ctypes.c_int
    runtime.aecNrm2.argtypes = [u64, u64, u64, ptr]
    runtime.aecNrm2.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int

    allocations: list[int] = []

    def alloc(size: int) -> int:
        value = u64()
        assert runtime.aecAlloc(ctypes.byref(value), size) == SUCCESS
        allocations.append(value.value)
        return value.value

    def read_scalar(device_result: int) -> float:
        output = ctypes.create_string_buffer(4)
        assert runtime.aecCopyD2H(output, device_result, 4) == SUCCESS
        return struct.unpack("<f", output.raw)[0]

    try:
        dot_max_cycles = 0
        nrm2_max_cycles = 0
        vector_bytes = MAX_COUNT * 4
        host = ctypes.create_string_buffer(struct.pack("<f", 1.0) * MAX_COUNT)
        x = alloc(vector_bytes)
        y = alloc(vector_bytes)
        result = alloc(4)
        assert runtime.aecCopyH2D(x, host, vector_bytes) == SUCCESS
        assert runtime.aecCopyH2D(y, host, vector_bytes) == SUCCESS

        for count in (90_908, 90_909, MAX_COUNT):
            status = runtime.aecDot(x, y, result, count, None)
            assert status == SUCCESS, f"DOT count {count}: status {status}"
            if count == MAX_COUNT:
                operation = Stats()
                assert runtime.aecGetRuntimeStats(ctypes.byref(operation)) == SUCCESS
                dot_max_cycles = operation.last_virtual_cycles
            assert read_scalar(result) == float(count)

        for count in (111_109, 111_110, MAX_COUNT):
            status = runtime.aecNrm2(x, result, count, None)
            assert status == SUCCESS, f"NRM2 count {count}: status {status}"
            if count == MAX_COUNT:
                operation = Stats()
                assert runtime.aecGetRuntimeStats(ctypes.byref(operation)) == SUCCESS
                nrm2_max_cycles = operation.last_virtual_cycles
            assert math.isclose(read_scalar(result), math.sqrt(count),
                                rel_tol=5e-5, abs_tol=2e-5)

        before = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(before)) == SUCCESS
        assert before.isa_traps == 0
        assert runtime.aecDot(x, y, result, MAX_COUNT + 1, None) == INVALID_ARGUMENT
        assert runtime.aecNrm2(x, result, MAX_COUNT + 1, None) == INVALID_ARGUMENT
        after = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(after)) == SUCCESS
        assert bytes(after) == bytes(before)
    finally:
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print(
        "PASS custom R204 max: DOT/NRM2 support 1,048,576 without ISA traps; "
        f"cycles={dot_max_cycles}/{nrm2_max_cycles}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
