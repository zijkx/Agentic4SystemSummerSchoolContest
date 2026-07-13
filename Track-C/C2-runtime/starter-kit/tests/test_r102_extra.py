#!/usr/bin/env python3
"""Allocation boundary and lifetime checks beyond the public R102 case."""

from __future__ import annotations

import argparse
import ctypes
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
OUT_OF_MEMORY = 2
INVALID_ADDRESS = 4
DEVICE_BYTES = 64 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    library = args.submission / "libaec.so" if args.submission.is_dir() else args.submission
    runtime = ctypes.CDLL(str(library.resolve()))
    runtime.aecAlloc.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t]
    runtime.aecAlloc.restype = ctypes.c_int
    runtime.aecFree.argtypes = [ctypes.c_uint64]
    runtime.aecFree.restype = ctypes.c_int

    assert runtime.aecAlloc(None, 64) == INVALID_ARGUMENT
    sentinel = ctypes.c_uint64(0xDEADBEEF)
    assert runtime.aecAlloc(ctypes.byref(sentinel), 0) == INVALID_ARGUMENT
    assert sentinel.value == 0xDEADBEEF
    assert runtime.aecFree(0) == INVALID_ADDRESS
    assert runtime.aecFree((1 << 64) - 1) == INVALID_ADDRESS

    first = ctypes.c_uint64()
    second = ctypes.c_uint64()
    assert runtime.aecAlloc(ctypes.byref(first), 1) == SUCCESS
    assert runtime.aecAlloc(ctypes.byref(second), 129) == SUCCESS
    assert first.value != 0 and first.value % 64 == 0
    assert second.value != 0 and second.value % 64 == 0
    assert runtime.aecFree(first.value + 1) == INVALID_ADDRESS
    assert runtime.aecFree(first.value) == SUCCESS

    reused = ctypes.c_uint64()
    assert runtime.aecAlloc(ctypes.byref(reused), 1) == SUCCESS
    assert reused.value == first.value
    assert runtime.aecFree(reused.value) == SUCCESS
    assert runtime.aecFree(reused.value) == INVALID_ADDRESS
    assert runtime.aecFree(second.value) == SUCCESS

    too_large = ctypes.c_uint64(0x1234)
    assert runtime.aecAlloc(ctypes.byref(too_large), DEVICE_BYTES) == OUT_OF_MEMORY
    assert too_large.value == 0x1234
    print("PASS custom R102: zero/OOM/alignment/reuse/interior/stale/double-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
