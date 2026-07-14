#!/usr/bin/env python3
"""Audit every public GEMM dtype at the maximum contract shape."""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path


SUCCESS = 0
M = N = K = 256


class Stats(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32), ("reserved", ctypes.c_uint32),
        ("submitted_commands", ctypes.c_uint64),
        ("dma_commands", ctypes.c_uint64),
        ("kernel_commands", ctypes.c_uint64),
        ("zero_copy_commands", ctypes.c_uint64),
        ("channel_commands", ctypes.c_uint64 * 2),
        ("total_virtual_cycles", ctypes.c_uint64),
        ("last_virtual_cycles", ctypes.c_uint64),
        ("isa_launches", ctypes.c_uint64),
        ("instructions_retired", ctypes.c_uint64),
        ("isa_traps", ctypes.c_uint64),
        ("last_kernel_handle", ctypes.c_uint64),
        ("last_trace_digest", ctypes.c_uint64),
    ]


def storage(elements: int, bytes_per_element: int, packed: bool = False) -> int:
    return (elements + 1) // 2 if packed else elements * bytes_per_element


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
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
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int

    common = [u64, u64, u64, ctypes.c_uint32, ctypes.c_uint32,
              ctypes.c_uint32, ptr]
    cases = [
        ("fp4_e2m1", "aecMatmulF4", 1, True, 1, True, None),
        ("fp8_e4m3", "aecMatmulF8", 1, False, 1, False, 1),
        ("fp8_e5m2", "aecMatmulF8", 1, False, 1, False, 2),
        ("fp16", "aecMatmulF16", 2, False, 2, False, None),
        ("bf16", "aecMatmulBF16", 2, False, 2, False, None),
        ("fp32", "aecMatmulF32", 4, False, 4, False, None),
        ("fp64", "aecMatmulF64", 8, False, 8, False, None),
        ("int4", "aecMatmulI4", 1, True, 4, False, None),
        ("int8", "aecMatmulI8", 1, False, 4, False, None),
        ("int32", "aecMatmulI32", 4, False, 4, False, None),
    ]
    for name, function_name, input_width, input_packed, output_width, output_packed, fp8 in cases:
        function = getattr(runtime, function_name)
        function.argtypes = common if fp8 is None else common[:-1] + [ctypes.c_int, ptr]
        function.restype = ctypes.c_int
        a_bytes = storage(M * K, input_width, input_packed)
        b_bytes = storage(K * N, input_width, input_packed)
        c_bytes = storage(M * N, output_width, output_packed)
        allocations = []

        def allocate(size: int) -> int:
            value = u64()
            assert runtime.aecAlloc(ctypes.byref(value), size) == SUCCESS
            allocations.append(value.value)
            return value.value

        try:
            a = allocate(a_bytes)
            b = allocate(b_bytes)
            c = allocate(c_bytes)
            a_host = ctypes.create_string_buffer(a_bytes)
            b_host = ctypes.create_string_buffer(b_bytes)
            assert runtime.aecCopyH2D(a, a_host, a_bytes) == SUCCESS
            assert runtime.aecCopyH2D(b, b_host, b_bytes) == SUCCESS
            assert runtime.aecResetRuntimeStats() == SUCCESS
            if fp8 is None:
                status = function(a, b, c, M, N, K, None)
            else:
                status = function(a, b, c, M, N, K, fp8, None)
            assert status == SUCCESS, f"{name} status {status}"
            stats = Stats()
            assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
            assert stats.isa_launches == 1 and stats.instructions_retired > 0
            assert stats.isa_traps == 0 and stats.last_trace_digest != 0
            output = ctypes.create_string_buffer(c_bytes)
            assert runtime.aecCopyD2H(output, c, c_bytes) == SUCCESS
            assert output.raw == bytes(c_bytes), f"{name} nonzero output"
            print(
                f"PASS {name}: bytes={a_bytes}/{b_bytes}/{c_bytes}, "
                f"cycles={stats.last_virtual_cycles}, "
                f"retired={stats.instructions_retired}")
        finally:
            for allocation in reversed(allocations):
                assert runtime.aecFree(allocation) == SUCCESS
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
