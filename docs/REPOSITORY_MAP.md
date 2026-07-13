# Repository Map

## Top level

```text
.
|-- README.md                 contest rules, scoring normalization, environment summary
|-- LICENSE
|-- Track-A/                  independent EDA track
|-- Track-B/                  independent RTL track and precise AEC ISA specification
|-- Track-C/
|   |-- README.md             Track C overview
|   |-- C1-compiler/          specification plus five PTX samples only
|   |-- C2-runtime/           specification, scoring, and complete-looking starter tree
|   `-- C3-scheduler/         specification plus C3.1/C3.5 public models/data
`-- docs/                     reproducible audit and handoff documents
```

Generated/cache directories were excluded during inventory. At audit time there were no `build/`, `dist/`, `.venv/`, `node_modules/`, or project `__pycache__/` trees.

## C1 compiler

| Path | Responsibility and importance |
|---|---|
| `Track-C/C1-compiler/spec.md` | Normative CLI, AEC binary sections, required compiler passes, five test classes, and 8-core/16-GB/180-second Docker environment. |
| `Track-C/C1-compiler/scoring.md` | 100 hidden correctness cases, 35-point cycle allocation, 50 mutations, and Agent score. |
| `Track-C/C1-compiler/testcases/README.md` | Explains the five representative public PTX programs and warns against fixed-structure assumptions. |
| `testcases/PTX-01_vector_add.ptx` ... `PTX-05_gemm_f16.ptx` | Public inputs covering basic lowering, scalar optimization, memory reuse, register scheduling, and GEMM. They are inputs, not executable tests or an oracle. |
| `Track-B/spec.md` | Precise 128-bit ISA and little-endian raw encoding referenced by C1. It is not C1 source code. |

There is no C1 starter source, Makefile/CMake file, public validator, Golden Model, Cycle Model, `aec-cc`, or `aec-objdump` in the repository. Consequently there is no build/grader entry point to execute. The current implementation completion is 0% in this checkout; only requirements and inputs exist. The specs do not state the final archive layout or dependency allowlist.

## C2 runtime

`Track-C/C2-runtime/spec.md` and `scoring.md` summarize the task. The deeper starter-kit documents are the practical contract:

| Path | Responsibility and importance |
|---|---|
| `starter-kit/Makefile` | Builds `libaec.so`, six examples, and invokes public tests. It requires `lib/libaec_device.so`. |
| `starter-kit/src/aec_runtime.cpp` | Starter implementation. Device query/error/stats are present; allocation, copy, stream/event, launch, all GEMM and vector APIs return `AEC_ERROR_NOT_SUPPORTED`. |
| `starter-kit/include/aec_runtime.h` | Required public C ABI and complete exported-symbol list. |
| `starter-kit/include/aec_device_abi.h` | Runtime-to-controlled-device ABI. |
| `starter-kit/include/aec_isa.h` | ISA constants and canonical encoders used by examples/runtime. |
| `starter-kit/docs/01_...` through `06_...` | Detailed fixed platform, observable behavior, ISA/numerics, exact R101-R402 weights/gates, build/test, and final submission layout. |
| `starter-kit/kernels/manifest.json` and `kernels/images/*.aecbin` | Frozen mapping and 34 immutable images; custom images are forbidden. |
| `starter-kit/examples/*.c` | Six smoke programs from query and encoding through vector add, streams, GEMM, and registered copy. |
| `starter-kit/grader/public_grade.py` | Public grader; loads the participant library and compiles/runs generated probes. Must not be modified. |
| `starter-kit/cases/` | One wrapper per R101-R402 plus public machine-readable case definitions. |
| `starter-kit/golden/`, `schemas/` | Public ISA/numeric reference data and strict Agent JSON contracts. Immutable. |
| `starter-kit/agents/*.py` | Legal but simplistic starter policies for Excellent-level work. |
| `starter-kit/RELEASE_MANIFEST.json` | Frozen hashes. It lists `lib/libaec_device.so` with SHA-256 `295c47...01d5`, proving the release expected the file. |

Critical discrepancy: `lib/libaec_device.so` is absent, its directory does not exist, and it is not in Git's `HEAD`. A SHA-256 audit verified all 84 other manifest entries with no mismatch; this `.so` is the only missing entry. The root `.gitignore` ignores every `*.so`, so a normal commit could silently omit it. Its ELF class, CPU architecture, dependencies, and loadability cannot be audited from this checkout. The starter Runtime is only a query/error/stats skeleton and cannot reach Basic until R102-R104/R201 are implemented.

## C3 scheduler

| Path | Responsibility and importance |
|---|---|
| `Track-C/C3-scheduler/spec.md` | Normative C3.1-C3.5 CLI, DAG/manifest formats, decomposition/fusion review criteria, model shapes, gates, and submission checklist. |
| `Track-C/C3-scheduler/scoring.md` | Exact 10/15/15/10/50 allocation and sub-dimensions. |
| `testcases/README.md` | Public model architecture and 17-operator union. Example commands refer to participant-created programs. |
| `testcases/release_to_competitors/docs/COMPETITOR_GUIDE.md` | Released C3.1/C3.5 participant contract. |
| `.../models/{mlp,resnet,transformer}_v1.onnx` | Three public opset-17 models (documented as such; weights differ in hidden versions). |
| `.../testdata/c35/*` | Manifests, inputs, golden logits, labels, and thresholds. ResNet input is gzip-compressed. |
| `.../decompress_testdata.sh` | Materializes the 117 MiB ResNet `input.npy`; it writes a new ignored/untracked-sized artifact and was not run in this audit. |

There is no participant scheduler/inference source, Python dependency declaration, `export_dag.py`, or test runner. The `benchmarks/c32_c33/bench_c32_c33.py` cited by spec/scoring is absent from `HEAD`. Released data supports future C3.1/C3.5 development, but there are no executable public C3.1 checks or C3.2/C3.3 benchmarks here. Current implementation completion is 0%.

## Dependency boundaries and immutable files

C1, C2, and C3 share AEC/GPGPU concepts, not checked-in participant code. C1's output is not consumed by the C2 public tests, which use fixed images. C3 has no checked-in call to C1 or C2. Build and score each independently.

Never edit specs/scoring to resolve ambiguity. Treat all C1 PTX inputs; C2 `include/`, `docs/`, `grader/`, `cases/`, `golden/`, `schemas/`, fixed images/manifest, and device library; and C3 released models, inputs, goldens, labels, thresholds, and competitor guide as read-only contracts. Participant implementation should live in new source/build files or the explicitly provided C2 `src/`/Agent files.
