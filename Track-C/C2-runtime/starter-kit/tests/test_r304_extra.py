#!/usr/bin/env python3
"""R304 one-shot DMA/kernel/command fault and recovery checks."""

from __future__ import annotations

import argparse
import ctypes
import struct
from pathlib import Path


SUCCESS = 0
DEVICE_ERROR = 7
H2D = 1
D2H = 2
VECTOR_ADD = 1
FAULT_NEXT_DMA = 1
FAULT_NEXT_KERNEL = 2
FAULT_NEXT_COMMAND = 3


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
    device = ctypes.CDLL(str(root / "lib" / "libaec_device.so"))
    ptr = ctypes.c_void_p
    u64 = ctypes.c_uint64
    runtime.aecAlloc.argtypes = [ctypes.POINTER(u64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [u64]
    runtime.aecFree.restype = ctypes.c_int
    runtime.aecCopyH2D.argtypes = [u64, ptr, ctypes.c_size_t]
    runtime.aecCopyH2D.restype = ctypes.c_int
    runtime.aecCopyD2H.argtypes = [ptr, u64, ctypes.c_size_t]
    runtime.aecCopyD2H.restype = ctypes.c_int
    runtime.aecCopyAsync.argtypes = [u64, ptr, ctypes.c_size_t, ctypes.c_int, ptr]
    runtime.aecCopyAsync.restype = ctypes.c_int
    runtime.aecStreamCreate.argtypes = [ctypes.POINTER(ptr)]
    runtime.aecStreamCreate.restype = ctypes.c_int
    runtime.aecStreamDestroy.argtypes = [ptr]
    runtime.aecStreamDestroy.restype = ctypes.c_int
    runtime.aecStreamSync.argtypes = [ptr]
    runtime.aecStreamSync.restype = ctypes.c_int
    runtime.aecLaunch.argtypes = [ctypes.c_int, Dim3, Dim3, ptr,
                                  ctypes.c_size_t, ptr]
    runtime.aecLaunch.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    device.aecDeviceInjectFault.argtypes = [ctypes.c_int]
    device.aecDeviceInjectFault.restype = ctypes.c_int

    allocations: list[int] = []

    def alloc(size: int) -> int:
        value = u64()
        assert runtime.aecAlloc(ctypes.byref(value), size) == SUCCESS
        allocations.append(value.value)
        return value.value

    stream = ptr()
    assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
    try:
        dma = alloc(1024)
        first_host = ctypes.create_string_buffer(bytes([1]) * 1024)
        second_host = ctypes.create_string_buffer(bytes([2]) * 1024)
        dma_output = ctypes.create_string_buffer(1024)
        assert device.aecDeviceInjectFault(FAULT_NEXT_DMA) == SUCCESS
        assert runtime.aecCopyAsync(dma, first_host, 1024, H2D, stream) == SUCCESS
        assert runtime.aecCopyAsync(dma, second_host, 1024, H2D, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == DEVICE_ERROR
        assert runtime.aecCopyD2H(dma_output, dma, 1024) == SUCCESS
        assert dma_output.raw == second_host.raw[:-1]
        assert runtime.aecCopyAsync(dma, first_host, 16, H2D, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS

        a, b, c = alloc(16), alloc(16), alloc(16)
        raw_a = struct.pack("<4f", 1.0, 2.0, 3.0, 4.0)
        raw_b = struct.pack("<4f", 5.0, 6.0, 7.0, 8.0)
        host_a = ctypes.create_string_buffer(raw_a)
        host_b = ctypes.create_string_buffer(raw_b)
        assert runtime.aecCopyH2D(a, host_a, 16) == SUCCESS
        assert runtime.aecCopyH2D(b, host_b, 16) == SUCCESS
        launch_args = VectorArgs(a, b, c, 4)
        assert device.aecDeviceInjectFault(FAULT_NEXT_KERNEL) == SUCCESS
        for _ in range(2):
            assert runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                                     ctypes.byref(launch_args),
                                     ctypes.sizeof(launch_args), stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == DEVICE_ERROR
        kernel_output = ctypes.create_string_buffer(16)
        assert runtime.aecCopyD2H(kernel_output, c, 16) == SUCCESS
        assert struct.unpack("<4f", kernel_output.raw) == (6.0, 8.0, 10.0, 12.0)
        stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(stats)) == SUCCESS
        assert stats.instructions_retired > 0 and stats.last_trace_digest != 0

        assert device.aecDeviceInjectFault(FAULT_NEXT_COMMAND) == SUCCESS
        assert runtime.aecCopyH2D(dma, first_host, 16) == DEVICE_ERROR
        assert runtime.aecCopyH2D(dma, first_host, 16) == SUCCESS
    finally:
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print("PASS custom R304: one-shot DMA/kernel/command faults and recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
