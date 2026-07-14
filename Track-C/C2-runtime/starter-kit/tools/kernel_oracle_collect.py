#!/usr/bin/env python3
"""Build a reproducible full-domain certificate from the device policy oracle."""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import hashlib
import json
import multiprocessing
import struct
import sys
import tempfile
import time
from pathlib import Path


SUCCESS = 0
MAX_DIMENSION = 256
DTYPE_NAMES = (
    "fp4_e2m1", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16",
    "fp32", "fp64", "int4", "int8", "int32",
)
VARIANTS = {
    1: {"semantic_kernel_id": 10, "divisibility": 1,
        "alignment": 1, "workspace": 0},
    2: {"semantic_kernel_id": 11, "divisibility": 4,
        "alignment": 1, "workspace": 4096},
    3: {"semantic_kernel_id": 12, "divisibility": 8,
        "alignment": 16, "workspace": 8192},
}
ALIGNMENTS = (1, 15, 16, 63, 64, 128)
WORKSPACES = (0, 4095, 4096, 8191, 8192, 16384)
EQUIVALENCE_SHAPES = ((8, 8, 8), (16, 24, 32), (256, 256, 256))
RECORD = struct.Struct("<IIIIIQIIIIQQQ")


class DeviceCompletion(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32), ("status", ctypes.c_uint32),
        ("sequence", ctypes.c_uint64), ("virtual_cycles", ctypes.c_uint64),
        ("bytes_completed", ctypes.c_uint64),
        ("instructions_retired", ctypes.c_uint64),
        ("trace_digest", ctypes.c_uint64), ("fault_code", ctypes.c_uint32),
        ("trap_pc", ctypes.c_uint32),
    ]


class DeviceStats(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32), ("reserved", ctypes.c_uint32),
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class Oracle:
    def __init__(self, library: Path):
        self.library_path = library.resolve()
        self.library = ctypes.CDLL(str(self.library_path))
        self.library.aecDeviceEvaluateKernel.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.c_uint64,
            ctypes.POINTER(DeviceCompletion),
        ]
        self.library.aecDeviceEvaluateKernel.restype = ctypes.c_int
        self.library.aecDeviceGetStats.argtypes = [ctypes.POINTER(DeviceStats)]
        self.library.aecDeviceGetStats.restype = ctypes.c_int
        self.calls = 0

    def stats(self) -> bytes:
        stats = DeviceStats()
        status = self.library.aecDeviceGetStats(ctypes.byref(stats))
        if status != SUCCESS:
            raise RuntimeError(f"aecDeviceGetStats failed with {status}")
        return bytes(stats)

    def evaluate(self, semantic_kernel_id: int, dtype: int, variant: int,
                 m: int, n: int, k: int, alignment: int,
                 workspace: int) -> tuple[int, DeviceCompletion]:
        completion = DeviceCompletion()
        status = self.library.aecDeviceEvaluateKernel(
            semantic_kernel_id, dtype, variant, m, n, k, alignment,
            workspace, ctypes.byref(completion))
        self.calls += 1
        if status == SUCCESS and completion.status != SUCCESS:
            raise RuntimeError("successful oracle call has a failed completion")
        if status != SUCCESS and completion.status not in (SUCCESS, status):
            raise RuntimeError("invalid oracle completion status")
        return status, completion


def image_id(dtype: int, variant: int) -> int:
    return (VARIANTS[variant]["semantic_kernel_id"] << 16) | (dtype << 8) | variant


def completion_signature(completion: DeviceCompletion) -> tuple[int, int, int]:
    return (completion.virtual_cycles, completion.instructions_retired,
            completion.trace_digest)


def run_oracle_contract_checks(oracle: Oracle) -> dict:
    stats_before = oracle.stats()
    completions = []
    for _ in range(100):
        status, completion = oracle.evaluate(12, 6, 3, 64, 64, 64, 64, 8192)
        if status != SUCCESS:
            raise RuntimeError(f"determinism probe failed with {status}")
        completions.append(bytes(completion))
    if len(set(completions)) != 1:
        raise RuntimeError("oracle completion is not deterministic")

    invalid_probes = (
        ("dtype", 10, 0, 1, 8, 8, 8, 64, 8192),
        ("variant", 10, 6, 0, 8, 8, 8, 64, 8192),
        ("zero_shape", 10, 6, 1, 0, 8, 8, 64, 8192),
        ("kernel_tuple", 10, 6, 2, 8, 8, 8, 64, 8192),
        ("alignment", 12, 6, 3, 8, 8, 8, 15, 8192),
        ("workspace", 12, 6, 3, 8, 8, 8, 16, 8191),
    )
    invalid_statuses = {}
    failed_completions_with_payload = []
    for name, semantic, dtype, variant, m, n, k, alignment, workspace in invalid_probes:
        status, completion = oracle.evaluate(
            semantic, dtype, variant, m, n, k, alignment, workspace)
        if status == SUCCESS:
            raise RuntimeError(f"invalid {name} probe unexpectedly succeeded")
        invalid_statuses[name] = status
        if any(completion_signature(completion)):
            failed_completions_with_payload.append(name)
    if oracle.stats() != stats_before:
        raise RuntimeError("oracle contract checks mutated device stats")
    return {
        "deterministic_repetitions": len(completions),
        "completion_byte_identical": True,
        "invalid_statuses": invalid_statuses,
        "failed_completions_with_payload": failed_completions_with_payload,
        "failed_completion_labels_used": False,
        "stats_byte_identical": True,
    }


def audit_equivalence_classes(oracle: Oracle) -> dict:
    calls_before = oracle.calls
    successful_signatures = 0
    for dtype in range(1, len(DTYPE_NAMES) + 1):
        for m, n, k in EQUIVALENCE_SHAPES:
            for variant, requirement in VARIANTS.items():
                observed = set()
                for alignment in ALIGNMENTS:
                    for workspace in WORKSPACES:
                        legal = (
                            alignment >= requirement["alignment"] and
                            workspace >= requirement["workspace"] and
                            m % requirement["divisibility"] == 0 and
                            n % requirement["divisibility"] == 0 and
                            k % requirement["divisibility"] == 0
                        )
                        status, completion = oracle.evaluate(
                            requirement["semantic_kernel_id"], dtype, variant,
                            m, n, k, alignment, workspace)
                        if (status == SUCCESS) != legal:
                            raise RuntimeError(
                                "alignment/workspace legality mismatch for "
                                f"dtype={dtype}, shape={(m, n, k)}, variant={variant}, "
                                f"alignment={alignment}, workspace={workspace}")
                        if legal:
                            observed.add(completion_signature(completion))
                if len(observed) != 1:
                    raise RuntimeError(
                        "legal alignment/workspace values change oracle output for "
                        f"dtype={dtype}, shape={(m, n, k)}, variant={variant}")
                successful_signatures += len(observed)
    return {
        "alignments": list(ALIGNMENTS),
        "workspaces": list(WORKSPACES),
        "shapes": [list(shape) for shape in EQUIVALENCE_SHAPES],
        "calls": oracle.calls - calls_before,
        "legal_values_only_control_availability": True,
        "successful_equivalence_classes": successful_signatures,
        "variant_requirements": {str(key): value for key, value in VARIANTS.items()},
    }


def record_oracle(hash_state: object, dtype: int, m: int, n: int, k: int,
                  alignment: int, workspace: int, variant: int, status: int,
                  completion: DeviceCompletion) -> None:
    requirement = VARIANTS[variant]
    hash_state.update(RECORD.pack(
        dtype, m, n, k, alignment, workspace,
        requirement["semantic_kernel_id"], variant, image_id(dtype, variant),
        status, completion.virtual_cycles, completion.instructions_retired,
        completion.trace_digest))


def collect_dtype(oracle: Oracle, dtype: int) -> dict:
    started = time.perf_counter()
    calls_before = oracle.calls
    digest = hashlib.sha256()
    mismatch_count = 0
    max_regret_cycles = 0
    dominance_violations = {"tiled_gt_naive": 0,
                            "vectorized_gt_tiled": 0,
                            "vectorized_gt_naive": 0}
    violation_examples = []
    tie_count = 0
    tiled_speedup_min = None
    tiled_speedup_max = 0.0
    vector_speedup_min = None
    vector_speedup_max = 0.0
    performance_fraction_counts = {"zero": 0, "partial": 0, "full": 0}
    total_shapes = MAX_DIMENSION ** 3
    multi_shapes = (MAX_DIMENSION // 4) ** 3
    vector_shapes = (MAX_DIMENSION // 8) ** 3
    best_distribution = {"1": total_shapes - multi_shapes, "2": 0, "3": 0}

    for m in range(4, MAX_DIMENSION + 1, 4):
        for n in range(4, MAX_DIMENSION + 1, 4):
            for k in range(4, MAX_DIMENSION + 1, 4):
                completions = {}
                for variant in (1, 2):
                    requirement = VARIANTS[variant]
                    status, completion = oracle.evaluate(
                        requirement["semantic_kernel_id"], dtype, variant,
                        m, n, k, 64, 8192)
                    record_oracle(digest, dtype, m, n, k, 64, 8192,
                                  variant, status, completion)
                    if status != SUCCESS or completion.virtual_cycles == 0:
                        raise RuntimeError(
                            f"oracle failed at dtype={dtype}, shape={(m, n, k)}, "
                            f"variant={variant}, status={status}")
                    completions[variant] = completion

                naive_cycles = completions[1].virtual_cycles
                tiled_cycles = completions[2].virtual_cycles
                tiled_speedup = naive_cycles / tiled_cycles
                tiled_speedup_min = (tiled_speedup if tiled_speedup_min is None
                                     else min(tiled_speedup_min, tiled_speedup))
                tiled_speedup_max = max(tiled_speedup_max, tiled_speedup)
                if tiled_cycles > naive_cycles:
                    dominance_violations["tiled_gt_naive"] += 1

                chosen_variant = 2
                if m % 8 == 0 and n % 8 == 0 and k % 8 == 0:
                    requirement = VARIANTS[3]
                    status, completion = oracle.evaluate(
                        requirement["semantic_kernel_id"], dtype, 3,
                        m, n, k, 64, 8192)
                    record_oracle(digest, dtype, m, n, k, 64, 8192,
                                  3, status, completion)
                    if status != SUCCESS or completion.virtual_cycles == 0:
                        raise RuntimeError(
                            f"oracle failed at dtype={dtype}, shape={(m, n, k)}, "
                            f"variant=3, status={status}")
                    completions[3] = completion
                    chosen_variant = 3
                    vector_cycles = completion.virtual_cycles
                    vector_speedup = naive_cycles / vector_cycles
                    vector_speedup_min = (
                        vector_speedup if vector_speedup_min is None
                        else min(vector_speedup_min, vector_speedup))
                    vector_speedup_max = max(vector_speedup_max, vector_speedup)
                    if vector_cycles > tiled_cycles:
                        dominance_violations["vectorized_gt_tiled"] += 1
                    if vector_cycles > naive_cycles:
                        dominance_violations["vectorized_gt_naive"] += 1

                best_cycles = min(item.virtual_cycles for item in completions.values())
                best_variants = [
                    variant for variant, completion in completions.items()
                    if completion.virtual_cycles == best_cycles
                ]
                oracle_variant = max(best_variants)
                best_distribution[str(oracle_variant)] += 1
                if len(best_variants) > 1:
                    tie_count += 1
                chosen_cycles = completions[chosen_variant].virtual_cycles
                regret = max(0, chosen_cycles - best_cycles)
                max_regret_cycles = max(max_regret_cycles, regret)
                if regret:
                    mismatch_count += 1
                    if len(violation_examples) < 100:
                        violation_examples.append({
                            "m": m, "n": n, "k": k,
                            "chosen_variant": chosen_variant,
                            "oracle_variant": oracle_variant,
                            "cycles": {str(key): value.virtual_cycles
                                       for key, value in completions.items()},
                        })
                fraction = max(0.0, min(
                    1.0, (naive_cycles / chosen_cycles - 1.0) / 0.5))
                if fraction == 0.0:
                    performance_fraction_counts["zero"] += 1
                elif fraction == 1.0:
                    performance_fraction_counts["full"] += 1
                else:
                    performance_fraction_counts["partial"] += 1

    expected_calls = 2 * multi_shapes + vector_shapes
    actual_calls = oracle.calls - calls_before
    if actual_calls != expected_calls:
        raise RuntimeError(
            f"dtype {dtype} call count {actual_calls}, expected {expected_calls}")
    elapsed = time.perf_counter() - started
    return {
        "schema_version": 1,
        "dtype": dtype,
        "dtype_name": DTYPE_NAMES[dtype - 1],
        "shape_domain": [1, MAX_DIMENSION],
        "total_shapes": total_shapes,
        "multi_candidate_shapes": multi_shapes,
        "vector_candidate_shapes": vector_shapes,
        "oracle_calls": actual_calls,
        "record_sha256": digest.hexdigest(),
        "dominance_violations": dominance_violations,
        "policy_mismatch_count": mismatch_count,
        "argmin_accuracy": (multi_shapes - mismatch_count) / multi_shapes,
        "max_regret_cycles": max_regret_cycles,
        "tie_count": tie_count,
        "best_variant_distribution": best_distribution,
        "policy_variant_distribution": {
            "1": total_shapes - multi_shapes,
            "2": multi_shapes - vector_shapes,
            "3": vector_shapes,
        },
        "tiled_speedup": {"min": tiled_speedup_min, "max": tiled_speedup_max},
        "vectorized_speedup": {
            "min": vector_speedup_min, "max": vector_speedup_max},
        "performance_fraction_counts": performance_fraction_counts,
        "violation_examples": violation_examples,
        "elapsed_seconds": round(elapsed, 6),
        "oracle_calls_per_second": round(actual_calls / elapsed, 3),
    }


def collect_dtype_worker(library: str, dtype: int, device_sha256: str,
                         checkpoint: str) -> dict:
    oracle = Oracle(Path(library))
    stats_before = oracle.stats()
    report = collect_dtype(oracle, dtype)
    if oracle.stats() != stats_before:
        raise RuntimeError(f"dtype {dtype} collection mutated device stats")
    report["device_sha256"] = device_sha256
    report["worker_stats_byte_identical_before_after"] = True
    write_json(Path(checkpoint), report)
    return report


def validate_checkpoint(payload: dict, device_sha256: str, dtype: int) -> None:
    if (payload.get("schema_version") != 1 or payload.get("dtype") != dtype or
            payload.get("shape_domain") != [1, MAX_DIMENSION] or
            payload.get("device_sha256") != device_sha256):
        raise RuntimeError(f"incompatible checkpoint for dtype {dtype}")


def parse_dtypes(values: list[str] | None) -> list[int]:
    if not values:
        return list(range(1, len(DTYPE_NAMES) + 1))
    selected = []
    for value in values:
        if value.isdigit() and 1 <= int(value) <= len(DTYPE_NAMES):
            dtype = int(value)
        elif value in DTYPE_NAMES:
            dtype = DTYPE_NAMES.index(value) + 1
        else:
            raise ValueError(f"unknown dtype: {value}")
        if dtype not in selected:
            selected.append(dtype)
    return sorted(selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path,
                        default=Path("reports/kernel_oracle_summary.json"))
    parser.add_argument("--checkpoint-dir", type=Path)
    parser.add_argument("--dtype", action="append")
    parser.add_argument("--jobs", type=int,
                        default=min(len(DTYPE_NAMES), multiprocessing.cpu_count()))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()

    root = args.submission.resolve()
    library = root / "lib" / "libaec_device.so"
    if not library.is_file():
        raise SystemExit(f"missing device library: {library}")
    device_sha256 = sha256(library)
    checkpoint_dir = (args.checkpoint_dir.resolve() if args.checkpoint_dir
                      else Path(tempfile.gettempdir()) /
                      f"aec-c2-kernel-oracle-{device_sha256[:12]}")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    oracle = Oracle(library)
    stats_before = oracle.stats()
    started = time.perf_counter()
    contract = run_oracle_contract_checks(oracle)
    equivalence = audit_equivalence_classes(oracle)
    selected_dtypes = parse_dtypes(args.dtype)
    dtype_reports = []
    executed_full_calls = 0
    full_started = time.perf_counter()
    if not args.probe_only:
        if args.jobs < 1:
            raise SystemExit("--jobs must be positive")
        pending = []
        for dtype in selected_dtypes:
            checkpoint = checkpoint_dir / f"dtype-{dtype}.json"
            if args.resume and checkpoint.is_file():
                report = json.loads(checkpoint.read_text(encoding="utf-8"))
                validate_checkpoint(report, device_sha256, dtype)
                dtype_reports.append(report)
            else:
                pending.append((dtype, checkpoint))
        if pending:
            context = multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(
                    max_workers=min(args.jobs, len(pending)),
                    mp_context=context) as executor:
                futures = {
                    executor.submit(
                        collect_dtype_worker, str(library), dtype,
                        device_sha256, str(checkpoint)): dtype
                    for dtype, checkpoint in pending
                }
                for future in concurrent.futures.as_completed(futures):
                    report = future.result()
                    dtype_reports.append(report)
                    executed_full_calls += report["oracle_calls"]
                    print(
                        f"completed dtype {report['dtype']} "
                        f"({report['dtype_name']}): "
                        f"{report['oracle_calls']} calls, "
                        f"{report['elapsed_seconds']:.3f}s",
                        file=sys.stderr, flush=True)
    full_elapsed = time.perf_counter() - full_started
    stats_after = oracle.stats()
    if stats_after != stats_before:
        raise RuntimeError("aecDeviceEvaluateKernel mutated device stats")

    combined_digest = hashlib.sha256()
    for report in sorted(dtype_reports, key=lambda item: item["dtype"]):
        combined_digest.update(bytes.fromhex(report["record_sha256"]))
    certified_calls = sum(item["oracle_calls"] for item in dtype_reports)
    total_multi_shapes = sum(item["multi_candidate_shapes"]
                             for item in dtype_reports)
    mismatches = sum(item["policy_mismatch_count"] for item in dtype_reports)
    max_regret = max((item["max_regret_cycles"] for item in dtype_reports),
                     default=0)
    dominance_violations = sum(
        sum(item["dominance_violations"].values()) for item in dtype_reports)
    summary = {
        "schema_version": 1,
        "device_library": "lib/libaec_device.so",
        "device_sha256": device_sha256,
        "record_format": "<IIIIIQIIIIQQQ",
        "dtype_domain": [DTYPE_NAMES[index - 1] for index in selected_dtypes],
        "shape_domain": {"m": [1, MAX_DIMENSION], "n": [1, MAX_DIMENSION],
                         "k": [1, MAX_DIMENSION]},
        "oracle_contract": contract,
        "alignment_workspace_audit": equivalence,
        "dtype_reports": dtype_reports,
        "certified_full_oracle_calls": certified_calls,
        "executed_full_oracle_calls": executed_full_calls,
        "certified_shape_count": len(dtype_reports) * MAX_DIMENSION ** 3,
        "certified_multi_candidate_shapes": total_multi_shapes,
        "combined_record_sha256": combined_digest.hexdigest(),
        "dominance_violation_count": dominance_violations,
        "policy_mismatch_count": mismatches,
        "argmin_accuracy": ((total_multi_shapes - mismatches) /
                            total_multi_shapes if total_multi_shapes else None),
        "max_regret_cycles": max_regret,
        "recommended_policy": (
            "highest_legal_variant" if dominance_violations == 0 and
            mismatches == 0 and len(dtype_reports) == len(DTYPE_NAMES)
            else "requires_exception_or_model_analysis"),
        "stats_byte_identical_before_after": True,
        "probe_only": args.probe_only,
        "worker_count": min(args.jobs, len(selected_dtypes)),
        "checkpoint_directory": str(checkpoint_dir),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "full_collection_seconds": round(full_elapsed, 6),
        "executed_full_calls_per_second": (
            round(executed_full_calls / full_elapsed, 3)
            if executed_full_calls and full_elapsed else None),
    }
    output = args.output if args.output.is_absolute() else root / args.output
    write_json(output, summary)
    print(
        "PASS kernel oracle collection: "
        f"dtypes={len(dtype_reports)}, calls={certified_calls}, "
        f"violations={dominance_violations}, mismatches={mismatches}, "
        f"max_regret={max_regret}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
