#!/usr/bin/env python3
"""Synchronous DMA bounds, accounting, reset, and sequence stress checks."""

from __future__ import annotations

import argparse
import ctypes
import threading
from pathlib import Path


SUCCESS = 0
INVALID_ARGUMENT = 1
INVALID_ADDRESS = 4


class Stats(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
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
    runtime.aecCopyH2D.argtypes = [ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
    runtime.aecCopyH2D.restype = ctypes.c_int
    runtime.aecCopyD2H.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_size_t]
    runtime.aecCopyD2H.restype = ctypes.c_int
    runtime.aecGetRuntimeStats.argtypes = [ctypes.POINTER(Stats)]
    runtime.aecGetRuntimeStats.restype = ctypes.c_int
    runtime.aecResetRuntimeStats.restype = ctypes.c_int

    first = ctypes.c_uint64()
    second = ctypes.c_uint64()
    assert runtime.aecAlloc(ctypes.byref(first), 64) == SUCCESS
    assert runtime.aecAlloc(ctypes.byref(second), 64) == SUCCESS
    source = (ctypes.c_ubyte * 64)(*range(64))
    target = (ctypes.c_ubyte * 64)()
    try:
        assert runtime.aecResetRuntimeStats() == SUCCESS
        assert runtime.aecCopyH2D(first.value, source, 64) == SUCCESS
        assert runtime.aecCopyD2H(target, first.value, 64) == SUCCESS
        assert bytes(target) == bytes(source)

        before = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(before)) == SUCCESS
        assert before.submitted_commands == 2 and before.dma_commands == 2
        assert runtime.aecCopyH2D(first.value + 32, source, 64) == INVALID_ADDRESS
        assert runtime.aecCopyH2D(first.value, None, 1) == INVALID_ARGUMENT
        assert runtime.aecCopyD2H(target, first.value, 0) == INVALID_ARGUMENT
        assert runtime.aecCopyD2H(target, (1 << 64) - 8, 16) == INVALID_ADDRESS
        after = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(after)) == SUCCESS
        assert after.submitted_commands == before.submitted_commands

        assert runtime.aecResetRuntimeStats() == SUCCESS
        assert runtime.aecCopyH2D(first.value + 4, source, 16) == SUCCESS
        reset_stats = Stats()
        assert runtime.aecGetRuntimeStats(ctypes.byref(reset_stats)) == SUCCESS
        assert reset_stats.submitted_commands == 1

        errors: list[int] = []

        def worker(device: int) -> None:
            local = (ctypes.c_ubyte * 16)(*range(16))
            for _ in range(20):
                status = runtime.aecCopyH2D(device, local, 16)
                if status != SUCCESS:
                    errors.append(status)

        threads = [threading.Thread(target=worker, args=(first.value,)),
                   threading.Thread(target=worker, args=(second.value,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors, errors
    finally:
        assert runtime.aecFree(first.value) == SUCCESS
        assert runtime.aecFree(second.value) == SUCCESS

    print("PASS custom R103: spans/accounting/reset and 40 concurrent DMA submits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
