# Baseline Report

Audit date/commit: 2026-07-13, `87a99a5c544c0d67282144fe2eda488f5049a287`. Commands ran from a clean working tree. No source, test, grader, model, fixed image, or system dependency was modified.

## C1

From `Track-C/C1-compiler`:

```bash
aec-cc testcases/PTX-01_vector_add.ptx -O0 -o /tmp/PTX-01_vector_add.aecbin
```

Exit 127: `command not found: aec-cc`. Inventory also found no source/build file, installed `aec-objdump`, binary validator, Golden Model, or Cycle Model. No clean build or public execution test exists to run. Classification: missing participant implementation and missing released test infrastructure, not a compiler defect and not primarily a host-resource failure.

## C2

From `Track-C/C2-runtime/starter-kit`:

```bash
make -j2
make examples
python3 cases/test_r101.py --submission .
```

Both Make commands exited 2: `No rule to make target 'lib/libaec_device.so', needed by 'libaec.so'`. R101 exited 1 after the nested grader reported missing `libaec.so`. Because compilation never started, these results say nothing about starter-code correctness or macOS compiler compatibility. The root cause is the missing mandatory release binary. The current starter implementation would still fail most requirements after that artifact is restored because nearly all APIs are explicit unsupported stubs.

No `libaec.so`, examples, device query, dynamic symbol check, or full public grader could be produced. The required device library's format/architecture could not be inspected.

A SHA-256 pass over `RELEASE_MANIFEST.json` verified 84 of 85 entries with no mismatches; `lib/libaec_device.so` was the sole missing entry. This rules out broader starter-kit corruption detectable by that manifest.

## C3

From `Track-C/C3-scheduler`:

```bash
python3 export_dag.py --onnx testcases/release_to_competitors/models/mlp_v1.onnx --output /tmp/c3_mlp_dag.json
python3 benchmarks/c32_c33/bench_c32_c33.py --models mnist_mlp cifar_resnet18 --output-dir /tmp/c32_c33_results
```

Both exited 2 because the scripts do not exist. This is missing participant/release code, not a failed graph algorithm. Import checks against Python 3.9.6 and 3.13.9 found NumPy, ONNX, ONNX Runtime, PyTorch, protobuf, pytest, jsonschema, and pynvml absent.

A standard-library read-only probe successfully parsed all six input/golden manifests and NumPy headers for the available uncompressed MLP and Transformer inputs. It confirmed little-endian FP32 MLP shape `(10000, 1, 28, 28)` and little-endian int64 Transformer shape `(10000, 18)`, matching manifests. The ResNet input remains `input.npy.gz`; decompression was intentionally skipped because it would create a 117 MiB file and no inference runner is present.

All 19 JSON files under Track C parsed successfully with the Python standard library.

`nvidia-smi` and `nvcc` were not found; the PyTorch CUDA query could not start because PyTorch is absent. Therefore no C3.5 inference, accuracy, timing, peak VRAM, GPU, or NVML test was run.

## Supporting environment probes

The following materially support baseline conclusions:

```bash
docker info
docker compose version
python3 -m pip check
/opt/homebrew/bin/python3.13 -m pip check
clang++ -std=c++17 -fPIC -shared -x c++ - -o /tmp/aec_audit_shared.so
file /tmp/aec_audit_shared.so
otool -hv /tmp/aec_audit_shared.so
```

Docker CLI/Compose exist but the daemon connection failed. Both Python package checks found no broken installed distributions. The C++17 probe built successfully and was identified as arm64 Mach-O, not ELF.

## Summary

| Area | Successful | Failed / unavailable | Classification |
|---|---|---|---|
| C1 | Spec/public PTX readability only | Build, CLI, correctness, performance | Implementation and released-oracle absence |
| C2 | Python grader wrapper starts | Build/examples/R101 | Missing release artifact; later implementation gaps remain untested |
| C3 | Manifests and two NumPy headers parsed | DAG CLI, benchmark, imports, GPU checks | Missing implementation/benchmark/deps and unavailable NVIDIA environment |
| Host ABI | C++17 compilation | Linux ELF production | Platform mismatch |
| Docker | CLI and Compose version | Daemon/info/container test | Local service unavailable |

No module built successfully and no scoring requirement passed. It is currently impossible to distinguish latent compiler/runtime/scheduler bugs beyond the visible starter stubs because each path stops at an earlier missing prerequisite.
