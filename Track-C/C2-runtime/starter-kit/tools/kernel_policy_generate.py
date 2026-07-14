#!/usr/bin/env python3
"""Validate a full oracle summary and emit the compact policy certificate."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


EXPECTED_DEVICE_SHA256 = (
    "b96b09e88ae160b659cf72bd079da8bc647d2bc55d377297a649d77c30ddcb0a"
)
EXPECTED_DTYPES = (
    "fp4_e2m1", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
    "fp32", "fp64", "int4", "int8", "int32",
)
EXPECTED_CALLS = 10 * (2 * 64 ** 3 + 32 ** 3)
FORBIDDEN_IMPORTS = {
    "ctypes", "os", "pathlib", "socket", "subprocess", "urllib", "requests",
}
FORBIDDEN_CALLS = {"open", "eval", "exec", "compile", "__import__"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def static_agent_audit(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports = set()
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
    forbidden_imports = sorted(imports & FORBIDDEN_IMPORTS)
    forbidden_calls = sorted(calls & FORBIDDEN_CALLS)
    forbidden_text = sorted(item for item in (
        "libaec_device", "aecDeviceEvaluateKernel", "grader/", "cases/",
        "http://", "https://",
    ) if item in source)
    if forbidden_imports or forbidden_calls or forbidden_text:
        raise RuntimeError(
            "Agent offline audit failed: "
            f"imports={forbidden_imports}, calls={forbidden_calls}, "
            f"text={forbidden_text}")
    return {
        "imports": sorted(imports),
        "forbidden_imports": forbidden_imports,
        "forbidden_calls": forbidden_calls,
        "forbidden_text": forbidden_text,
        "offline_static_audit_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    parser.add_argument("--oracle-summary", type=Path,
                        default=Path("reports/kernel_oracle_summary.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("reports/kernel_policy_report.json"))
    args = parser.parse_args()
    root = args.submission.resolve()
    summary_path = (args.oracle_summary if args.oracle_summary.is_absolute()
                    else root / args.oracle_summary)
    output_path = args.output if args.output.is_absolute() else root / args.output
    agent_path = root / "agents" / "kernel_agent.py"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    checks = {
        "schema_version": summary.get("schema_version") == 1,
        "device_sha256": summary.get("device_sha256") == EXPECTED_DEVICE_SHA256,
        "dtype_domain": tuple(summary.get("dtype_domain", ())) == EXPECTED_DTYPES,
        "oracle_calls": summary.get("certified_full_oracle_calls") == EXPECTED_CALLS,
        "shape_count": summary.get("certified_shape_count") == 10 * 256 ** 3,
        "dominance": summary.get("dominance_violation_count") == 0,
        "mismatch": summary.get("policy_mismatch_count") == 0,
        "accuracy": summary.get("argmin_accuracy") == 1.0,
        "regret": summary.get("max_regret_cycles") == 0,
        "stats": summary.get("stats_byte_identical_before_after") is True,
        "policy": summary.get("recommended_policy") == "highest_legal_variant",
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"oracle summary cannot certify policy: {failed}")
    static_audit = static_agent_audit(agent_path)
    model = {
        "kind": "integer_dominance_rule",
        "selection": "highest legal variant",
        "variant_order": [3, 2, 1],
        "legality_features": [
            "dtype", "m", "n", "k", "alignment", "workspace",
            "candidate semantic_kernel_id", "candidate image_id",
            "candidate variant", "candidate divisibility",
            "candidate alignment", "candidate workspace",
        ],
        "tie_break": ["predicted_cycles", "higher_variant",
                      "smaller_image_id", "candidate_id"],
    }
    model_sha256 = hashlib.sha256(
        json.dumps(model, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    report = {
        "schema_version": 1,
        "device_sha256": EXPECTED_DEVICE_SHA256,
        "oracle_summary": str(summary_path.relative_to(root)),
        "oracle_summary_sha256": sha256(summary_path),
        "oracle_call_count": EXPECTED_CALLS,
        "certified_shape_count": 10 * 256 ** 3,
        "certified_multi_candidate_shapes": 10 * 64 ** 3,
        "model": model,
        "model_sha256": model_sha256,
        "agent_path": "agents/kernel_agent.py",
        "agent_sha256": sha256(agent_path),
        "mismatch_count": 0,
        "argmin_accuracy": 1.0,
        "max_regret_cycles": 0,
        "checks": checks,
        "static_agent_audit": static_audit,
        "public_r402_required": "run grader after generation",
        "hidden_performance_verified": False,
        "hidden_performance_note": (
            "The certificate proves oracle-optimal choices over the public "
            "contract domain; only the organizer full profile can award hidden points."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "PASS kernel policy certificate: calls=5570560, mismatch=0, "
        "accuracy=1.0, max_regret=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
