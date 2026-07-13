#!/usr/bin/env python3
"""R203 odd packed INT4, async INT8, and output-span checks."""

from __future__ import annotations

import argparse
import ctypes
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ADDRESS = 4


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
    common = [u64, u64, u64, ctypes.c_uint32, ctypes.c_uint32,
              ctypes.c_uint32, ptr]
    runtime.aecMatmulI4.argtypes = common
    runtime.aecMatmulI4.restype = ctypes.c_int
    runtime.aecMatmulI8.argtypes = common
    runtime.aecMatmulI8.restype = ctypes.c_int
    runtime.aecStreamCreate.argtypes = [ctypes.POINTER(ptr)]
    runtime.aecStreamCreate.restype = ctypes.c_int
    runtime.aecStreamDestroy.argtypes = [ptr]
    runtime.aecStreamDestroy.restype = ctypes.c_int
    runtime.aecStreamSync.argtypes = [ptr]
    runtime.aecStreamSync.restype = ctypes.c_int

    allocations: list[int] = []

    def alloc(size: int) -> int:
        value = u64()
        assert runtime.aecAlloc(ctypes.byref(value), size) == SUCCESS
        allocations.append(value.value)
        return value.value

    try:
        # [7, -8, 1] and [7, 1, -8], low-index nibble first. The
        # high nibble of each odd tail byte is deliberately zero.
        i4a, i4b, i4c = alloc(2), alloc(2), alloc(4)
        packed_a = ctypes.create_string_buffer(b"\x87\x01")
        packed_b = ctypes.create_string_buffer(b"\x17\x08")
        output = ctypes.create_string_buffer(4)
        assert runtime.aecCopyH2D(i4a, packed_a, 2) == SUCCESS
        assert runtime.aecCopyH2D(i4b, packed_b, 2) == SUCCESS
        assert runtime.aecMatmulI4(i4a, i4b, i4c, 1, 1, 3, None) == SUCCESS
        assert runtime.aecCopyD2H(output, i4c, 4) == SUCCESS
        assert struct.unpack("<i", output.raw)[0] == 33

        i8a, i8b, i8c = alloc(3), alloc(3), alloc(4)
        raw_a = ctypes.create_string_buffer(struct.pack("<3b", 7, -8, 1))
        raw_b = ctypes.create_string_buffer(struct.pack("<3b", 7, 1, -8))
        assert runtime.aecCopyH2D(i8a, raw_a, 3) == SUCCESS
        assert runtime.aecCopyH2D(i8b, raw_b, 3) == SUCCESS
        stream = ptr()
        assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
        assert runtime.aecMatmulI8(i8a, i8b, i8c, 1, 1, 3, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        assert runtime.aecCopyD2H(output, i8c, 4) == SUCCESS
        assert struct.unpack("<i", output.raw)[0] == 33

        undersized = alloc(3)
        assert runtime.aecMatmulI8(i8a, i8b, undersized, 1, 1, 3,
                                   None) == INVALID_ADDRESS
    finally:
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print("PASS custom R203: odd INT4 packing, async INT8, INT32 output span")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
