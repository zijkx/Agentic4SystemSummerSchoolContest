#!/usr/bin/env python3
"""Additional R101 checks that do not inspect or modify the official grader."""

from __future__ import annotations

import argparse
import ctypes
import threading
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    library = args.submission / "libaec.so" if args.submission.is_dir() else args.submission
    runtime = ctypes.CDLL(str(library.resolve()))
    runtime.aecDeviceCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
    runtime.aecDeviceCount.restype = ctypes.c_int
    runtime.aecAlloc.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecGetLastError.restype = ctypes.c_int
    runtime.aecPeekAtLastError.restype = ctypes.c_int
    runtime.aecGetErrorName.argtypes = [ctypes.c_int]
    runtime.aecGetErrorName.restype = ctypes.c_char_p

    runtime.aecGetLastError()
    assert runtime.aecAlloc(None, 1) == INVALID_ARGUMENT
    count = ctypes.c_int()
    assert runtime.aecDeviceCount(ctypes.byref(count)) == SUCCESS
    assert runtime.aecPeekAtLastError() == INVALID_ARGUMENT
    assert runtime.aecGetLastError() == INVALID_ARGUMENT
    assert runtime.aecGetLastError() == SUCCESS
    assert runtime.aecGetErrorName(0x7FFFFFFF) == b"AEC_ERROR_UNKNOWN"

    barrier = threading.Barrier(2)
    observed: list[int] = []

    def failing_thread() -> None:
        assert runtime.aecAlloc(None, 1) == INVALID_ARGUMENT
        barrier.wait()
        observed.append(runtime.aecPeekAtLastError())

    def clean_thread() -> None:
        barrier.wait()
        observed.append(runtime.aecPeekAtLastError())

    first = threading.Thread(target=failing_thread)
    second = threading.Thread(target=clean_thread)
    first.start()
    second.start()
    first.join()
    second.join()
    assert sorted(observed) == [SUCCESS, INVALID_ARGUMENT], observed
    print("PASS custom R101: TLS, success-preserves-error, Peek/Get, unknown name")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
