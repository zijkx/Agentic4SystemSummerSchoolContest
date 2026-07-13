#!/usr/bin/env python3
"""Exercise every public aecLaunch kernel ID and native argument structure."""

from __future__ import annotations

import argparse
import ctypes
import math
import struct
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
GEMM_NAIVE = 10
GEMM_TILED = 11
GEMM_VECTORIZED = 12
AXPY = 20
DOT = 21
NRM2 = 22
FP32 = 6


class Dim3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_uint32), ("y", ctypes.c_uint32),
                ("z", ctypes.c_uint32)]


class GemmArgs(ctypes.Structure):
    _fields_ = [
        ("a", ctypes.c_uint64), ("b", ctypes.c_uint64),
        ("c", ctypes.c_uint64), ("m", ctypes.c_uint32),
        ("n", ctypes.c_uint32), ("k", ctypes.c_uint32),
        ("dtype", ctypes.c_uint32), ("reserved", ctypes.c_uint32),
    ]


class AxpyArgs(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_uint64), ("y", ctypes.c_uint64),
        ("count", ctypes.c_uint64), ("alpha", ctypes.c_float),
        ("reserved", ctypes.c_uint32),
    ]


class DotArgs(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_uint64), ("y", ctypes.c_uint64),
        ("result", ctypes.c_uint64), ("count", ctypes.c_uint64),
    ]


class Nrm2Args(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_uint64), ("result", ctypes.c_uint64),
        ("count", ctypes.c_uint64),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    runtime = ctypes.CDLL(str(args.submission.resolve() / "libaec.so"))
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
    runtime.aecLaunch.argtypes = [ctypes.c_int, Dim3, Dim3, ptr,
                                  ctypes.c_size_t, ptr]
    runtime.aecLaunch.restype = ctypes.c_int
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
        elements = 64
        matrix_bytes = elements * 4
        a, b, c = alloc(matrix_bytes), alloc(matrix_bytes), alloc(matrix_bytes)
        ones = ctypes.create_string_buffer(struct.pack("<64f", *([1.0] * 64)))
        matrix_output = ctypes.create_string_buffer(matrix_bytes)
        assert runtime.aecCopyH2D(a, ones, matrix_bytes) == SUCCESS
        assert runtime.aecCopyH2D(b, ones, matrix_bytes) == SUCCESS
        gemm = GemmArgs(a, b, c, 8, 8, 8, FP32, 0)
        for kernel in (GEMM_NAIVE, GEMM_VECTORIZED):
            assert runtime.aecLaunch(
                kernel, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(gemm),
                ctypes.sizeof(gemm), None) == SUCCESS
            assert runtime.aecCopyD2H(matrix_output, c, matrix_bytes) == SUCCESS
            assert struct.unpack("<64f", matrix_output.raw) == (8.0,) * 64

        stream = ptr()
        assert runtime.aecStreamCreate(ctypes.byref(stream)) == SUCCESS
        assert runtime.aecLaunch(
            GEMM_TILED, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(gemm),
            ctypes.sizeof(gemm), stream) == SUCCESS
        gemm.a = gemm.b = gemm.c = 0
        assert runtime.aecStreamSync(stream) == SUCCESS
        assert runtime.aecStreamDestroy(stream) == SUCCESS
        assert runtime.aecCopyD2H(matrix_output, c, matrix_bytes) == SUCCESS
        assert struct.unpack("<64f", matrix_output.raw) == (8.0,) * 64

        gemm = GemmArgs(a, b, c, 8, 8, 8, FP32, 1)
        assert runtime.aecLaunch(
            GEMM_NAIVE, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(gemm),
            ctypes.sizeof(gemm), None) == INVALID_ARGUMENT
        gemm.reserved = 0
        gemm.dtype = 99
        assert runtime.aecLaunch(
            GEMM_NAIVE, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(gemm),
            ctypes.sizeof(gemm), None) == INVALID_ARGUMENT

        raw_x = struct.pack("<3f", 1.0, -2.0, 0.5)
        raw_y = struct.pack("<3f", 2.0, 1.0, -1.0)
        x, y, result = alloc(12), alloc(12), alloc(4)
        host_x = ctypes.create_string_buffer(raw_x)
        host_y = ctypes.create_string_buffer(raw_y)
        vector_output = ctypes.create_string_buffer(12)
        scalar_output = ctypes.create_string_buffer(4)
        assert runtime.aecCopyH2D(x, host_x, 12) == SUCCESS
        assert runtime.aecCopyH2D(y, host_y, 12) == SUCCESS
        axpy = AxpyArgs(x, y, 3, ctypes.c_float(0.5), 0)
        assert runtime.aecLaunch(
            AXPY, Dim3(1, 1, 1), Dim3(32, 1, 1), ctypes.byref(axpy),
            ctypes.sizeof(axpy), None) == SUCCESS
        assert runtime.aecCopyD2H(vector_output, y, 12) == SUCCESS
        assert struct.unpack("<3f", vector_output.raw) == (2.5, 0.0, -0.75)

        dot = DotArgs(x, x, result, 3)
        assert runtime.aecLaunch(
            DOT, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(dot),
            ctypes.sizeof(dot), None) == SUCCESS
        assert runtime.aecCopyD2H(scalar_output, result, 4) == SUCCESS
        assert struct.unpack("<f", scalar_output.raw)[0] == 5.25

        nrm2 = Nrm2Args(x, result, 3)
        assert runtime.aecLaunch(
            NRM2, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(nrm2),
            ctypes.sizeof(nrm2), None) == SUCCESS
        assert runtime.aecCopyD2H(scalar_output, result, 4) == SUCCESS
        assert math.isclose(struct.unpack("<f", scalar_output.raw)[0],
                            math.sqrt(5.25), abs_tol=2e-5)

        assert runtime.aecLaunch(
            999, Dim3(1, 1, 1), Dim3(1, 1, 1), ctypes.byref(nrm2),
            ctypes.sizeof(nrm2), None) == INVALID_ARGUMENT
    finally:
        for allocation in reversed(allocations):
            assert runtime.aecFree(allocation) == SUCCESS

    print("PASS custom aecLaunch: all public Kernel IDs and native args")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
