#!/usr/bin/env python3
"""R301 exact accounting, reset invariants, and preflight evidence checks."""

from __future__ import annotations

import argparse
import ctypes
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ADDRESS = 4
VECTOR_ADD = 1
FP32 = 6


class Dim3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32), ("y", ctypes.c_uint32),
                ("z", ctypes.c_uint32)]


class VectorArgs(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint64), ("b", ctypes.c_uint64),
                ("c", ctypes.c_uint64), ("count", ctypes.c_uint64)]


class KernelInfo(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32), ("isa_version", ctypes.c_uint32),
        ("handle", ctypes.c_uint64), ("image_id", ctypes.c_uint32),
        ("entry_pc", ctypes.c_uint32), ("parameter_bytes", ctypes.c_uint32),
        ("image_flags", ctypes.c_uint32), ("instruction_hash", ctypes.c_uint64),
    ]


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
    device = ctypes.CDLL(str(root / "lib" / "libaec_device.so"))
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
    runtime.aecLaunch.argtypes = [ctypes.c_int, Dim3, Dim3, ptr,
                                  ctypes.c_size_t, ptr]
    runtime.aecLaunch.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    device.aecDeviceGetStats.argtypes = [ctypes.POINTER(Stats)]
    device.aecDeviceGetStats.restype = ctypes.c_int
    device.aecDeviceResolveKernel.argtypes = [ctypes.c_uint32, ctypes.c_uint32,
                                              ctypes.c_uint32,
                                              ctypes.POINTER(KernelInfo)]
    device.aecDeviceResolveKernel.restype = ctypes.c_int

    allocations: list[int] = []

    def alloc(size: int) -> int:
        value = u64()
        assert runtime.aecAlloc(ctypes.byref(value), size) == SUCCESS
        allocations.append(value.value)
        return value.value

    try:
        a, b, c = alloc(16), alloc(16), alloc(16)
        raw = struct.pack("<4f", 1.0, 2.0, 3.0, 4.0)
        host = ctypes.create_string_buffer(raw)
        output = ctypes.create_string_buffer(16)
        info_before = KernelInfo()
        assert device.aecDeviceResolveKernel(VECTOR_ADD, FP32, 0,
                                             ctypes.byref(info_before)) == SUCCESS
        assert info_before.handle != 0 and info_before.parameter_bytes == 32

        assert runtime.aecResetRuntimeStats() == SUCCESS
        assert runtime.aecCopyH2D(a, host, 16) == SUCCESS
        assert runtime.aecCopyH2D(b, host, 16) == SUCCESS
        launch_args = VectorArgs(a, b, c, 4)
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 None) == SUCCESS
        assert runtime.aecCopyD2H(output, c, 16) == SUCCESS
        assert struct.unpack("<4f", output.raw) == (2.0, 4.0, 6.0, 8.0)

        reported = Stats()
        direct = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(reported)) == SUCCESS
        assert device.aecDeviceGetStats(ctypes.byref(direct)) == SUCCESS
        assert bytes(reported) == bytes(direct)
        assert reported.submitted_commands == 4
        assert reported.dma_commands == 3 and reported.kernel_commands == 1
        assert reported.isa_launches == 1 and reported.instructions_retired > 0
        assert reported.last_kernel_handle == info_before.handle
        assert reported.last_trace_digest != 0
        assert reported.total_virtual_cycles > reported.last_virtual_cycles > 0

        launch_args.count = 5
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 None) == INVALID_ADDRESS
        unchanged = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(unchanged)) == SUCCESS
        assert bytes(unchanged) == bytes(reported)

        assert runtime.aecResetRuntimeStats() == SUCCESS
        reset = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(reset)) == SUCCESS
        assert reset.submitted_commands == 0 and reset.total_virtual_cycles == 0
        info_after = KernelInfo()
        assert device.aecDeviceResolveKernel(VECTOR_ADD, FP32, 0,
                                             ctypes.byref(info_after)) == SUCCESS
        assert info_after.handle == info_before.handle
        assert runtime.aecCopyH2D(a, host, 16) == SUCCESS
    finally:
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print("PASS custom R301: exact stats/resolve/reset and no-submit preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
