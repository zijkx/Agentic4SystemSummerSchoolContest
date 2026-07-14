#!/usr/bin/env python3
"""Kernel Agent protocol, legality, metamorphic, and certificate checks."""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


DTYPE_NAMES = (
    "fp4_e2m1", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
    "fp32", "fp64", "int4", "int8", "int32",
)
REQUIREMENTS = {
    1: (10, 0, 1, 1),
    2: (11, 4096, 1, 4),
    3: (12, 8192, 16, 8),
}
EXPECTED_ORACLE_CALLS = 5_570_560


def candidate(dtype: int, identifier: str, variant: int,
              diagnostic: int | None = None) -> dict:
    semantic, workspace, alignment, divisibility = REQUIREMENTS[variant]
    value = {
        "id": identifier,
        "semantic_kernel_id": semantic,
        "image_id": (semantic << 16) | (dtype << 8) | variant,
        "variant": variant,
        "workspace": workspace,
        "alignment": alignment,
        "divisibility": divisibility,
    }
    if diagnostic is not None:
        value["diagnostic_cycles"] = diagnostic
    return value


def run_agent(path: Path, request: object, *, valid: bool = True,
              duration: list[float] | None = None) -> dict:
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(path)], input=json.dumps(request), text=True,
        capture_output=True, timeout=1, check=False,
        env={"PATH": "", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    if duration is not None:
        duration.append((time.perf_counter() - started) * 1000.0)
    assert not result.stderr, result.stderr
    assert len(result.stdout) + len(result.stderr) < 65536
    if not valid:
        assert result.returncode != 0 and result.stdout == ""
        return {}
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1
    output = json.loads(result.stdout)
    assert isinstance(output, dict) and set(output) == {"kernel_id"}
    return output


def run_raw_agent(path: Path, payload: str,
                  expected: dict | None = None) -> None:
    result = subprocess.run(
        [sys.executable, str(path)], input=payload, text=True,
        capture_output=True, timeout=1, check=False,
        env={"PATH": "", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"})
    assert not result.stderr, result.stderr
    assert len(result.stdout) + len(result.stderr) < 65536
    if expected is None:
        assert result.returncode != 0 and result.stdout == ""
    else:
        assert result.returncode == 0
        assert json.loads(result.stdout) == expected


def request(dtype_name: str, shape: tuple[int, int, int],
            candidates: list[dict], *, case_id: int = 1,
            alignment: int = 64, workspace: int = 8192) -> dict:
    m, n, k = shape
    return {
        "case_id": case_id, "dtype": dtype_name, "m": m, "n": n, "k": k,
        "alignment": alignment, "workspace": workspace,
        "candidates": candidates,
    }


def static_audit(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not imports & {"ctypes", "os", "pathlib", "socket", "subprocess",
                          "urllib", "requests"}
    for forbidden in ("aecDeviceEvaluateKernel", "libaec_device", "grader/",
                      "cases/", "http://", "https://"):
        assert forbidden not in source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    parser.add_argument("--determinism-runs", type=int, default=1000)
    args = parser.parse_args()
    root = args.submission.resolve()
    agent = root / "agents" / "kernel_agent.py"
    summary = json.loads(
        (root / "reports" / "kernel_oracle_summary.json").read_text(encoding="utf-8"))
    policy_report = json.loads(
        (root / "reports" / "kernel_policy_report.json").read_text(encoding="utf-8"))
    assert summary["certified_full_oracle_calls"] == EXPECTED_ORACLE_CALLS
    assert summary["dominance_violation_count"] == 0
    assert summary["policy_mismatch_count"] == 0
    assert summary["argmin_accuracy"] == 1.0
    assert summary["max_regret_cycles"] == 0
    assert policy_report["agent_sha256"] == hashlib.sha256(
        agent.read_bytes()).hexdigest()
    assert policy_report["oracle_summary_sha256"] == hashlib.sha256(
        (root / "reports" / "kernel_oracle_summary.json").read_bytes()).hexdigest()
    assert policy_report["mismatch_count"] == 0
    static_audit(agent)

    subprocess_cases = 0
    for dtype, dtype_name in enumerate(DTYPE_NAMES, start=1):
        all_candidates = [
            candidate(dtype, f"dtype{dtype}-variant{variant}-arbitrary-id", variant)
            for variant in (1, 2, 3)
        ]
        shape_cases = (
            ((7, 9, 5), 1),
            ((20, 12, 28), 2),
            ((8, 16, 24), 3),
            ((256, 256, 256), 3),
        )
        for shape, maximum_legal_variant in shape_cases:
            for count in range(1, 4):
                for subset in itertools.combinations(all_candidates, count):
                    legal = [item for item in subset
                             if item["variant"] <= maximum_legal_variant]
                    if not legal:
                        continue
                    expected = max(legal, key=lambda item: item["variant"])["id"]
                    for permutation in itertools.permutations(subset):
                        output = run_agent(
                            agent, request(dtype_name, shape, list(permutation)))
                        assert output == {"kernel_id": expected}
                        subprocess_cases += 1

    dtype = 6
    base_candidates = [candidate(dtype, f"candidate-{variant}", variant)
                       for variant in (1, 2, 3)]
    base = request("fp32", (32, 64, 16), base_candidates)
    baseline = run_agent(agent, base)
    assert baseline == {"kernel_id": "candidate-3"}
    for case_id in (0, 7, 999999):
        assert run_agent(agent, dict(base, case_id=case_id)) == baseline
    assert run_agent(agent, request(
        "fp32", (32, 64, 16), [
            candidate(dtype, "diagnostic-naive", 1, 300),
            candidate(dtype, "diagnostic-tiled", 2, 100),
            candidate(dtype, "diagnostic-vector", 3, 200),
        ])) == {"kernel_id": "diagnostic-tiled"}
    assert run_agent(agent, request(
        "fp32", (32, 64, 16), [
            candidate(dtype, "partial-naive", 1, 1),
            candidate(dtype, "partial-vector", 3),
        ])) == {"kernel_id": "partial-vector"}
    assert run_agent(agent, request(
        "fp32", (8, 8, 8), base_candidates, alignment=15,
        workspace=8192)) == {"kernel_id": "candidate-2"}
    assert run_agent(agent, request(
        "fp32", (8, 8, 8), base_candidates, alignment=16,
        workspace=8191)) == {"kernel_id": "candidate-2"}
    assert run_agent(agent, request(
        "fp32", (8, 8, 8), base_candidates, alignment=16,
        workspace=8192)) == {"kernel_id": "candidate-3"}
    escaped_id = 'quote"slash\\snowman\u2603supplementary\U0001f642'
    assert run_agent(agent, request(
        "fp32", (8, 8, 8), [candidate(dtype, escaped_id, 3)])) == {
            "kernel_id": escaped_id}

    reordered = dict(reversed(list(base.items())))
    reordered["candidates"] = [
        dict(reversed(list(item.items()))) for item in base_candidates
    ]
    run_raw_agent(
        agent, json.dumps(reordered, ensure_ascii=True, indent=2), baseline)
    base_payload = json.dumps(base, ensure_ascii=True)
    invalid_payloads = (
        '{"case_id":1,' + base_payload[1:],
        base_payload + " trailing",
        base_payload.replace('"case_id": 1', '"case_id": 01', 1),
        base_payload.replace('"case_id": 1', '"case_id": 1.0', 1),
        base_payload.replace('"case_id": 1', '"case_id": true', 1),
        base_payload.replace('"case_id": 1', '"case_id": null', 1),
        base_payload.replace('"case_id": 1', '"case_id": NaN', 1),
        base_payload.replace('"candidate-1"', '"\\uD800"', 1),
        base_payload.replace('"candidate-1"', '"\\u12xz"', 1),
    )
    for payload in invalid_payloads:
        run_raw_agent(agent, payload)

    large_candidates = [
        candidate(dtype, f"large-{index:03d}-" + "x" * 24, index % 3 + 1)
        for index in range(300)
    ]
    large_request = request("fp32", (256, 256, 256), large_candidates)
    assert len(json.dumps(large_request, separators=(",", ":")).encode()) < 65536
    assert run_agent(agent, large_request) == {
        "kernel_id": "large-002-" + "x" * 24}

    invalid_requests = [
        {}, dict(base, dtype="unknown"), dict(base, m=0), dict(base, n=257),
        dict(base, alignment=0), dict(base, workspace=-1),
        dict(base, candidates=[]),
        dict(base, candidates=[base_candidates[0], base_candidates[0]]),
        dict(base, candidates=[dict(base_candidates[0], unexpected=1)]),
        request("fp32", (8, 8, 8), [candidate(dtype, "v", 3)],
                alignment=15, workspace=8192),
    ]
    for invalid in invalid_requests:
        run_agent(agent, invalid, valid=False)

    injected = dict(summary, policy_mismatch_count=1, max_regret_cycles=1)
    with tempfile.TemporaryDirectory(prefix="aec-kernel-negative-") as temporary:
        temporary_path = Path(temporary)
        injected_path = temporary_path / "injected-summary.json"
        injected_path.write_text(json.dumps(injected), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(root / "tools" / "kernel_policy_generate.py"),
             "--submission", str(root), "--oracle-summary", str(injected_path),
             "--output", str(temporary_path / "should-not-exist.json")],
            text=True, capture_output=True, timeout=5, check=False)
        assert result.returncode != 0
        assert not (temporary_path / "should-not-exist.json").exists()

    durations = []
    for _ in range(args.determinism_runs):
        assert run_agent(agent, base, duration=durations) == baseline
    ordered = sorted(durations)
    p99_index = max(0, int(len(ordered) * 0.99) - 1)
    p99_ms = ordered[p99_index]
    assert p99_ms < 20.0, f"Kernel Agent p99 is {p99_ms:.3f} ms"
    print(
        "PASS Kernel Agent optimality: full-domain certificate "
        f"calls={EXPECTED_ORACLE_CALLS}, subset/permutation cases={subprocess_cases}, "
        f"determinism={args.determinism_runs}, median_ms={statistics.median(durations):.3f}, "
        f"p99_ms={p99_ms:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
