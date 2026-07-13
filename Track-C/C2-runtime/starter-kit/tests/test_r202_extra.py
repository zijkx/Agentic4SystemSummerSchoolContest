#!/usr/bin/env python3
"""R202 packed-tail, format validation, async FP16, and FP64 checks."""

from __future__ import annotations

import argparse
import ctypes
import math
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1


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
    for name in ("aecMatmulF4", "aecMatmulF16", "aecMatmulBF16",
                 "aecMatmulF64"):
        function = getattr(runtime, name)
        function.argtypes = common
        function.restype = ctypes.c_int
    runtime.aecMatmulF8.argtypes = [u64, u64, u64, ctypes.c_uint32,
                                    ctypes.c_uint32, ctypes.c_uint32,
                                    ctypes.c_int, ptr]
    runtime.aecMatmulF8.restype = ctypes.c_int
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
        # FP4 E2M1 code 0x2 is +1.0. A single output must occupy the low
        # nibble and leave the high nibble zero.
        f4a, f4b, f4c = alloc(1), alloc(1), alloc(1)
        one_f4 = ctypes.create_string_buffer(b"\x02")
        f4_output = ctypes.create_string_buffer(1)
        assert runtime.aecCopyH2D(f4a, one_f4, 1) == SUCCESS
        assert runtime.aecCopyH2D(f4b, one_f4, 1) == SUCCESS
        assert runtime.aecMatmulF4(f4a, f4b, f4c, 1, 1, 1, None) == SUCCESS
        assert runtime.aecCopyD2H(f4_output, f4c, 1) == SUCCESS
        assert f4_output.raw == b"\x02"
        assert runtime.aecMatmulF8(f4a, f4b, f4c, 1, 1, 1, 99, None) == INVALID_ARGUMENT

        f16a, f16b, f16c = alloc(2), alloc(2), alloc(2)
        two = ctypes.create_string_buffer(struct.pack("<e", 2.0))
        three = ctypes.create_string_buffer(struct.pack("<e", 3.0))
        half_output = ctypes.create_string_buffer(2)
        assert runtime.aecCopyH2D(f16a, two, 2) == SUCCESS
        assert runtime.aecCopyH2D(f16b, three, 2) == SUCCESS
        stream = ptr()
        assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
        assert runtime.aecMatmulF16(f16a, f16b, f16c, 1, 1, 1, stream) == SUCCESS
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        assert runtime.aecCopyD2H(half_output, f16c, 2) == SUCCESS
        assert struct.unpack("<e", half_output.raw)[0] == 6.0

        f64a, f64b, f64c = alloc(8), alloc(8), alloc(8)
        left = ctypes.create_string_buffer(struct.pack("<d", -1.25))
        right = ctypes.create_string_buffer(struct.pack("<d", 4.0))
        double_output = ctypes.create_string_buffer(8)
        assert runtime.aecCopyH2D(f64a, left, 8) == SUCCESS
        assert runtime.aecCopyH2D(f64b, right, 8) == SUCCESS
        assert runtime.aecMatmulF64(f64a, f64b, f64c, 1, 1, 1, None) == SUCCESS
        assert runtime.aecCopyD2H(double_output, f64c, 8) == SUCCESS
        assert math.isclose(struct.unpack("<d", double_output.raw)[0], -5.0,
                            abs_tol=1e-12)
    finally:
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print("PASS custom R202: FP4 odd tail, FP8 format, async FP16, FP64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
