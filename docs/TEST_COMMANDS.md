# Test Commands

Status key: **verified-pass**, **verified-fail**, or **not verified**. Paths are repository-relative; commands must be run from the directory stated. A documented command is not claimed to work merely because it appears in a spec.

## C1

The checkout provides no build system, compiler, disassembler, public validator, Golden Model, Cycle Model, or submission checker. Build/full-test/clean/submission commands are therefore **unavailable**, not inferred.

| Purpose | Directory and command | Writes | Expected output / success criterion | Status |
|---|---|---|---|---|
| Environment | repo root: `command -v aec-cc; command -v aec-objdump` | No | Two executable paths | verified-fail: neither exists |
| Minimal compile | `Track-C/C1-compiler`: `aec-cc testcases/PTX-01_vector_add.ptx -O0 -o /tmp/PTX-01_vector_add.aecbin` | `/tmp` binary | exit 0 and nonempty legal AEC binary | verified-fail: exit 127 |
| Disassemble future output | same: `aec-objdump /tmp/PTX-01_vector_add.aecbin` | No | exit 0, readable matching instructions | not verified: tool/output absent |
| Single public input | same compile command with one `PTX-0N_*.ptx` | Output path | Needs official validator/Golden Model to count as a test | not verifiable with released tree |
| Full public test | unavailable | N/A | No runner/oracle provided | unavailable |
| Clean build | unavailable | N/A | No build system provided | unavailable |
| Submission check | future: exercise `aec-cc INPUT [-O0|-O2|-O3] -o OUTPUT` and `aec-objdump OUTPUT` from a clean Linux environment | Build/output artifacts | CLIs exist; binary has five required sections; no network/absolute paths | not verified; archive layout unspecified |

## C2

| Purpose | Directory and command | Writes | Expected output / success criterion | Status |
|---|---|---|---|---|
| Artifact precheck | `Track-C/C2-runtime/starter-kit`: `file lib/libaec_device.so` | No | Linux ELF plus known CPU architecture | not runnable: file absent |
| Build | same: `make -j2` | `libaec.so` | exit 0, Linux ELF when run on Linux | verified-fail: missing device library |
| Examples | same: `make examples` | `bin/01...06` | exit 0, six executables | verified-fail: same prerequisite |
| Query smoke | same: `./bin/01_device_query` | No | exit 0 and valid ABI/ISA/device values | not verified: binary absent |
| ISA smoke | same: `./bin/02_isa_encoding` | No | exit 0 and public golden encodings | not verified: binary absent |
| Single grader case | same: `python3 cases/test_r101.py --submission .` | Temporary files outside tree | prints `PASS R101` and exits 0 | verified-fail: missing `libaec.so` |
| Any requirement | same: `python3 cases/run_case.py R201 --submission .` | Temporary files | prints `PASS R201`, exit 0 | not verified; build blocked |
| Full public cases | same: `make public-cases` | Temporary reports | `16/16 cases passed`, exit 0 | not verified; build blocked |
| Full public grader | same: `python3 grader/public_grade.py --submission . --profile public --json-out /tmp/c2-public-report.json` | `/tmp` report | exit 0; inspect score/tier/every requirement | not verified; build blocked |
| Symbols (formal Linux) | same: `nm -D --defined-only libaec.so` | No | every declaration in `include/aec_runtime.h` exported with C ABI | not verified; GNU `nm`/library absent |
| ELF/dependencies | same: `file libaec.so; readelf -h -d libaec.so` | No | Linux little-endian ELF, expected machine, only declared runtime dependencies | not verified; Linux tools/library absent |
| Clean | same: `make clean` | Removes only `bin/` and `libaec.so` | generated artifacts absent; sources/contracts preserved | not run because no generated artifacts existed |
| Final submission | submission dir: `find . -maxdepth 3 -type f -print` | No | only `libaec.so` and optional two Agent scripts; no symlinks/devices/setup/network dependency | not verified |

Do not run `make` again until the official device library is restored and its SHA-256 matches `RELEASE_MANIFEST.json`. On macOS, a successful build would still not be a valid formal ELF submission.

## C3

| Purpose | Directory and command | Writes | Expected output / success criterion | Status |
|---|---|---|---|---|
| Python environment | repo root: `python3 -c 'import numpy, onnx, onnxruntime'` | No | exit 0 and reviewed versions | verified-fail: packages absent |
| CUDA/NVML | repo root: `nvidia-smi`; `nvcc --version` | No | visible NVIDIA device/driver and CUDA compiler/runtime as required by implementation | verified-fail: commands absent |
| PyTorch CUDA | repo root: `python3 -c 'import torch; print(torch.cuda.is_available(), torch.cuda.device_count())'` | No | `True` and count >=1 | verified-fail: PyTorch absent |
| Graph parse | `Track-C/C3-scheduler`: `python3 export_dag.py --onnx testcases/release_to_competitors/models/mlp_v1.onnx --output /tmp/c3_mlp_dag.json` | `/tmp` JSON | exit 0; legal DAG preserving model inputs/outputs/nodes/edges | verified-fail: participant script absent |
| C3.2/C3.3 | same: `python3 benchmarks/c32_c33/bench_c32_c33.py --models mnist_mlp cifar_resnet18 --output-dir /tmp/c32_c33_results` | `/tmp` reports | exit 0, `scores.json` and report | verified-fail: released benchmark absent |
| Operator tests | unavailable | N/A | No operator-test runner exists in checkout | unavailable |
| Decompress ResNet data | `.../testcases/release_to_competitors`: `bash decompress_testdata.sh` | Creates `testdata/c35/resnet_v1/input/input.npy` (~117 MiB) | exit 0 and manifest-compatible NumPy file | not run: no inference runner and material write unnecessary |
| Single-model inference | `Track-C/C3-scheduler`: `python3 infer.py --onnx testcases/release_to_competitors/models/mlp_v1.onnx --input testcases/release_to_competitors/testdata/c35/mlp_v1/input --output /tmp/c3-mlp-output --batch-size 256` | `/tmp` manifest/logits | exit 0, FP32 logits shape `[10000,10]` | not verified: participant script/deps/GPU absent |
| Accuracy check | repo root or output-aware directory: `python3 -c 'import numpy as np; o=np.load("/tmp/c3-mlp-output/logits.npy"); g=np.load("Track-C/C3-scheduler/testcases/release_to_competitors/testdata/c35/mlp_v1/golden/logits.npy"); print(np.allclose(o,g,rtol=1e-3,atol=1e-3))'` | No | prints `True`; separately verify top-1 >=0.98 | not verified: NumPy/output absent |
| Full public models | run the same C3.1 and C3.5 CLIs for MLP, ResNet, Transformer | Output dirs | all exits 0, manifests/shapes/dtypes valid, allclose gates pass, MLP/ResNet accuracy gates pass | not verified |
| Peak VRAM/performance | remote formal runner with NVML around each full CLI | Reports | correct output first; then stable wall time and per-process NVML peak | not available locally; official runner unspecified |
| Submission check | clean environment using registered C3.1/C3.5 templates with `{onnx}`, `{input}`, `{output}` | Outputs | no fixed paths; arbitrary `--batch-size`; all source/deps/run instructions present offline | not verified; archive details deferred to platform |

The standard-library manifest/NumPy-header inspection recorded in `BASELINE_REPORT.md` is a data-integrity smoke check, not a C3 scoring test.
