#!/usr/bin/env python3
"""Stream lifetime, deep-copy, recovery, free-waits, and race checks."""

from __future__ import annotations

import argparse
import ctypes
import struct
import threading
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
INVALID_HANDLE = 3
INVALID_ADDRESS = 4
H2D = 1
D2H = 2
VECTOR_ADD = 1


class Dim3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32), ("y", ctypes.c_uint32),
                ("z", ctypes.c_uint32)]


class VectorArgs(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint64), ("b", ctypes.c_uint64),
                ("c", ctypes.c_uint64), ("count", ctypes.c_uint64)]


def bind(root: Path) -> ctypes.CDLL:
    runtime = ctypes.CDLL(str(root / "libaec.so"))
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
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    runtime = bind(args.submission.resolve())
    assert runtime.aecStreamCreate(None) == INVALID_ARGUMENT
    assert runtime.aecStreamSync(None) == INVALID_HANDLE
    assert runtime.aecStreamDestroy(None) == INVALID_HANDLE

    allocations: list[int] = []

    def alloc(size: int) -> int:
        pointer = ctypes.c_uint64()
        assert runtime.aecAlloc(ctypes.byref(pointer), size) == SUCCESS
        allocations.append(pointer.value)
        return pointer.value

    stream = ctypes.c_void_p()
    assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
    try:
        count = 8
        raw_a = struct.pack("<8f", *range(count))
        raw_b = struct.pack("<8f", *(10 - index for index in range(count)))
        a, b, c = alloc(len(raw_a)), alloc(len(raw_b)), alloc(len(raw_a))
        host_a = ctypes.create_string_buffer(raw_a)
        host_b = ctypes.create_string_buffer(raw_b)
        output = ctypes.create_string_buffer(len(raw_a))
        assert runtime.aecCopyH2D(a, host_a, len(raw_a)) == SUCCESS
        assert runtime.aecCopyH2D(b, host_b, len(raw_b)) == SUCCESS
        launch_args = VectorArgs(a, b, c, count)
        assert runtime.aecLaunch(VECTOR_ADD, Dim3(1, 1, 1), Dim3(32, 1, 1),
                                 ctypes.byref(launch_args), ctypes.sizeof(launch_args),
                                 stream) == SUCCESS
        launch_args.a = launch_args.b = launch_args.c = launch_args.count = 0
        assert runtime.aecCopyAsync(c, output, len(raw_a), D2H, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert struct.unpack("<8f", output.raw) == (10.0,) * count

        invalid_host = ctypes.create_string_buffer(16)
        assert runtime.aecCopyAsync(a + len(raw_a) - 4, invalid_host, 16,
                                    H2D, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == INVALID_ADDRESS
        assert runtime.aecCopyAsync(a, invalid_host, 16, H2D, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS

        pending = alloc(1024 * 1024)
        pending_source = ctypes.create_string_buffer(bytes([0x5A]) * (1024 * 1024))
        pending_target = ctypes.create_string_buffer(1024 * 1024)
        assert runtime.aecCopyAsync(pending, pending_source, len(pending_source) - 1,
                                    H2D, stream) == SUCCESS
        assert runtime.aecCopyAsync(pending, pending_target, len(pending_target),
                                    D2H, stream) == SUCCESS
        assert runtime.aecFree(pending) == SUCCESS
        allocations.remove(pending)
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert pending_target.raw == pending_source.raw[:-1]
    finally:
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        assert runtime.aecStreamDestroy(stream) == INVALID_HANDLE
        assert runtime.aecStreamSync(stream) == INVALID_HANDLE
        for pointer in reversed(allocations):
            assert runtime.aecFree(pointer) == SUCCESS

    # Race enqueue against destroy repeatedly. Enqueue may linearize before
    # destroy (SUCCESS) or after it (INVALID_HANDLE), but must never crash.
    for _ in range(20):
        race_stream = ctypes.c_void_p()
        assert runtime.aecStreamCreate(ctypes.byref(race_stream)) == SUCCESS
        device = alloc(64)
        host = ctypes.create_string_buffer(64)
        statuses: list[int] = []

        def producer() -> None:
            for _ in range(16):
                statuses.append(runtime.aecCopyAsync(
                    device, host, 64, H2D, race_stream))

        thread = threading.Thread(target=producer)
        thread.start()
        destroy_status = runtime.aecStreamDestroy(race_stream)
        thread.join()
        assert destroy_status == SUCCESS
        assert all(status in (SUCCESS, INVALID_HANDLE) for status in statuses)
        assert runtime.aecFree(device) == SUCCESS
        allocations.remove(device)

    print("PASS custom R105: FIFO/deep-copy/recovery/free-waits and 20 destroy races")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
