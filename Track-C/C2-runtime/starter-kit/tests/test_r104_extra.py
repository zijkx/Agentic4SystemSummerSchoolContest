#!/usr/bin/env python3
"""Vector launch validation and fixed-image evidence checks."""

from __future__ import annotations

import argparse
import ctypes
import math
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
INVALID_ADDRESS = 4
NOT_SUPPORTED = 6
VECTOR_ADD = 1


class Dim3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32), ("y", ctypes.c_uint32),
                ("z", ctypes.c_uint32)]


class VectorArgs(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint64), ("b", ctypes.c_uint64),
                ("c", ctypes.c_uint64), ("count", ctypes.c_uint64)]


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
    runtime.aecAlloc.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [ctypes.c_uint64]
    runtime.aecFree.restype = ctypes.c_int
    runtime.aecCopyH2D.argtypes = [ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
    runtime.aecCopyH2D.restype = ctypes.c_int
    runtime.aecCopyD2H.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_size_t]
    runtime.aecCopyD2H.restype = ctypes.c_int
    runtime.aecLaunch.argtypes = [ctypes.c_int, Dim3, Dim3, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.c_void_p]
    runtime.aecLaunch.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int

    count = 33
    raw_a = struct.pack(f"<{count}f", *(float(i) for i in range(count)))
    raw_b = struct.pack(f"<{count}f", *(0.25 - i for i in range(count)))
    pointers = [ctypes.c_uint64() for _ in range(3)]
    for pointer in pointers:
        assert runtime.aecAlloc(ctypes.byref(pointer), len(raw_a)) == SUCCESS
    a, b, c = (pointer.value for pointer in pointers)
    host_a = ctypes.create_string_buffer(raw_a)
    host_b = ctypes.create_string_buffer(raw_b)
    output = ctypes.create_string_buffer(len(raw_a))
    try:
        assert runtime.aecCopyH2D(a, host_a, len(raw_a)) == SUCCESS
        assert runtime.aecCopyH2D(b, host_b, len(raw_b)) == SUCCESS
        assert runtime.aecResetRuntimeStats() == SUCCESS
        launch_args = VectorArgs(a, b, c, count)
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(2, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 None) == SUCCESS
        assert runtime.aecCopyD2H(output, c, len(raw_a)) == SUCCESS
        actual = struct.unpack(f"<{count}f", output.raw)
        assert all(math.isclose(value, 0.25, abs_tol=1e-6) for value in actual)
        stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
        assert stats.kernel_commands == 1 and stats.isa_launches == 1
        assert stats.instructions_retired > 0
        assert stats.last_kernel_handle != 0 and stats.last_trace_digest != 0

        submitted = stats.submitted_commands
        checks = [
            runtime.aecLaunch(999, Dim3(1, 1, 1), Dim3(1, 1, 1),
                              ctypes.byref(launch_args), ctypes.sizeof(launch_args), None),
            runtime.aecLaunch(VECTOR_ADD, Dim3(0, 1, 1), Dim3(32, 1, 1),
                              ctypes.byref(launch_args), ctypes.sizeof(launch_args), None),
            runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(1025, 1, 1),
                              ctypes.byref(launch_args), ctypes.sizeof(launch_args), None),
            runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                              None, ctypes.sizeof(launch_args), None),
            runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                              ctypes.byref(launch_args), 1, None),
        ]
        assert checks == [NOT_SUPPORTED, INVALID_ARGUMENT, INVALID_ARGUMENT,
                          INVALID_ARGUMENT, INVALID_ARGUMENT], checks
        launch_args.count = 0
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 None) == INVALID_ARGUMENT
        launch_args.count = count
        launch_args.c = a
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(2, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 None) == INVALID_ARGUMENT
        launch_args.c = c
        launch_args.a = a + len(raw_a) - 4
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(2, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 None) == INVALID_ADDRESS
        final = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(final)) == SUCCESS
        assert final.submitted_commands == submitted
    finally:
        for pointer in pointers:
            assert runtime.aecFree(pointer.value) == SUCCESS

    print("PASS custom R104: fixed image, 33 elements, launch rejection, no-submit preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
