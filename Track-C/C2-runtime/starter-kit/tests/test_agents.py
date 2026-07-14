#!/usr/bin/env python3
"""Agent schema, legality, purity, determinism, and invalid-input checks."""

from __future__ import annotations

import argparse
import ctypes
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path


SUCCESS = 0


class DeviceCompletion(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32), ("status", ctypes.c_uint32),
        ("sequence", ctypes.c_uint64), ("virtual_cycles", ctypes.c_uint64),
        ("bytes_completed", ctypes.c_uint64),
        ("instructions_retired", ctypes.c_uint64),
        ("trace_digest", ctypes.c_uint64), ("fault_code", ctypes.c_uint32),
        ("trap_pc", ctypes.c_uint32),
    ]


def run_agent(path: Path, request: object, *, valid: bool = True) -> dict:
    result = subprocess.run(
        [sys.executable, str(path)], input=json.dumps(request), text=True,
        capture_output=True, timeout=1, check=False,
        env={"PATH": "", "PYTHONHASHSEED": "0"})
    assert not result.stderr, result.stderr
    if not valid:
        assert result.returncode != 0 and result.stdout == ""
        return {}
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    return output


def candidate(identifier: str, variant: int, workspace: int,
              alignment: int, divisibility: int,
              diagnostic: int | None = None) -> dict:
    value = {
        "id": identifier,
        "semantic_kernel_id": 9 + variant,
        "image_id": 1000 + variant,
        "variant": variant,
        "workspace": workspace,
        "alignment": alignment,
        "divisibility": divisibility,
    }
    if diagnostic is not None:
        value["diagnostic_cycles"] = diagnostic
    return value


def dma_cycles(request: dict, action: dict) -> int:
    chunks = math.ceil(request["bytes"] / action["chunk_bytes"])
    payload = math.ceil(request["bytes"] / 32)
    parallelism = min(action["queue_depth"], request["concurrency"], 2)
    setup = 45 if action["use_zero_copy"] else 100
    penalty = 0 if request["alignment"] >= 64 else 13
    return setup + math.ceil(payload / parallelism) + 24 * (chunks - 1) + penalty


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.submission.resolve()
    dma = root / "agents" / "dma_agent.py"
    kernel = root / "agents" / "kernel_agent.py"

    dma_request = {
        "case_id": 17, "direction": "d2h", "bytes": 65536,
        "alignment": 64, "registered": True, "concurrency": 4,
    }
    dma_output = run_agent(dma, dma_request)
    assert dma_output == {
        "channel": 1, "chunk_bytes": 1048576, "queue_depth": 2,
        "use_zero_copy": True,
    }
    single = dict(dma_request, direction="h2d", registered=False, concurrency=1)
    assert run_agent(dma, single) == {
        "channel": 0, "chunk_bytes": 1048576, "queue_depth": 1,
        "use_zero_copy": False,
    }
    assert [run_agent(dma, dma_request) for _ in range(5)] == [dma_output] * 5
    run_agent(dma, {}, valid=False)
    run_agent(dma, dict(dma_request, bytes=0), valid=False)

    for case_id, values in enumerate(itertools.product(
            ("h2d", "d2h"), (1, 4096, 65536, 1048576, 2097153),
            (16, 64), (False, True), (1, 2, 7))):
        direction, byte_count, alignment, registered, concurrency = values
        request = {
            "case_id": case_id, "direction": direction, "bytes": byte_count,
            "alignment": alignment, "registered": registered,
            "concurrency": concurrency,
        }
        action = run_agent(dma, request)
        legal_cycles = []
        for chunk, depth, zero_copy in itertools.product(
                (4096, 65536, 1048576), (1, 2, 4, 8), (False, True)):
            if zero_copy and not registered:
                continue
            legal_cycles.append(dma_cycles(request, {
                "chunk_bytes": chunk, "queue_depth": depth,
                "use_zero_copy": zero_copy,
            }))
        assert dma_cycles(request, action) == min(legal_cycles)

    base_request = {
        "case_id": 3, "dtype": "fp16", "m": 32, "n": 64, "k": 16,
        "alignment": 64, "workspace": 8192,
        "candidates": [
            candidate("fallback", 1, 0, 1, 1),
            candidate("middle", 2, 4096, 1, 4),
            candidate("fast", 3, 8192, 16, 8),
        ],
    }
    assert run_agent(kernel, base_request) == {"kernel_id": "fast"}
    tiled_request = dict(base_request, m=20, n=12, k=28)
    assert run_agent(kernel, tiled_request) == {"kernel_id": "middle"}
    naive_request = dict(base_request, m=7, n=9, k=5, alignment=8, workspace=0)
    assert run_agent(kernel, naive_request) == {"kernel_id": "fallback"}
    diagnostic_request = dict(base_request, candidates=[
        candidate("n", 1, 0, 1, 1, 300),
        candidate("t", 2, 4096, 1, 4, 100),
        candidate("v", 3, 8192, 16, 8, 200),
    ])
    assert run_agent(kernel, diagnostic_request) == {"kernel_id": "t"}
    empty_id_request = dict(
        base_request,
        candidates=[candidate("", 1, 0, 1, 1)],
    )
    assert run_agent(kernel, empty_id_request) == {"kernel_id": ""}
    expected = run_agent(kernel, base_request)
    assert [run_agent(kernel, base_request) for _ in range(5)] == [expected] * 5
    run_agent(kernel, {}, valid=False)
    run_agent(kernel, dict(base_request, candidates=[]), valid=False)
    run_agent(kernel, dict(base_request, alignment=1, workspace=0,
                           candidates=[candidate("illegal", 3, 8192, 16, 8)]),
              valid=False)

    device = ctypes.CDLL(str(root / "lib" / "libaec_device.so"))
    device.aecDeviceEvaluateKernel.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_uint32, ctypes.c_uint64, ctypes.POINTER(DeviceCompletion),
    ]
    device.aecDeviceEvaluateKernel.restype = ctypes.c_int
    dtype_names = (
        "fp4_e2m1", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
        "fp32", "fp64", "int4", "int8", "int32",
    )
    shapes = ((1, 1, 1), (4, 4, 4), (8, 8, 8), (8, 16, 24),
              (16, 16, 16), (20, 12, 28), (32, 64, 16), (256, 256, 256))
    for dtype, dtype_name in enumerate(dtype_names, start=1):
        for case_id, (m, n, k) in enumerate(shapes):
            candidates = [
                {
                    "id": f"v{variant}", "semantic_kernel_id": 9 + variant,
                    "image_id": ((9 + variant) << 16) | (dtype << 8) | variant,
                    "variant": variant, "workspace": workspace,
                    "alignment": alignment, "divisibility": divisibility,
                }
                for variant, workspace, alignment, divisibility in
                ((1, 0, 1, 1), (2, 4096, 1, 4), (3, 8192, 16, 8))
            ]
            request = {
                "case_id": case_id, "dtype": dtype_name, "m": m, "n": n,
                "k": k, "alignment": 64, "workspace": 8192,
                "candidates": candidates,
            }
            action = run_agent(kernel, request)
            cycles = {}
            for item in candidates:
                if any(value % item["divisibility"] for value in (m, n, k)):
                    continue
                completion = DeviceCompletion()
                status = device.aecDeviceEvaluateKernel(
                    item["semantic_kernel_id"], dtype, item["variant"],
                    m, n, k, 64, 8192, ctypes.byref(completion))
                assert status == SUCCESS and completion.virtual_cycles > 0
                cycles[item["id"]] = completion.virtual_cycles
            assert cycles[action["kernel_id"]] == min(cycles.values())

    print("PASS custom Agents: schema/purity + 120 DMA optima + 80 Kernel optima")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
