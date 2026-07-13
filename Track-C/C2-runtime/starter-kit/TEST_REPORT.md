# C2 Runtime Test Report

Report date: 2026-07-13 (Asia/Shanghai)

## Environment

| Field | Observed value |
|---|---|
| Hostname | `99b3bed1bfe8` |
| OS/kernel | Linux 6.8.0-110-generic, Ubuntu kernel build |
| Architecture | `x86_64`, 64-bit |
| Endian | little |
| Python | 3.12.3 |
| C++ compiler | G++ 13.3.0 |
| Make | GNU Make 4.3 |
| glibc/ldd | 2.39 |
| Initial commit | `abcaa940b107c153514d3cb162108090631cfdf6` |
| Branch | `codex/c2-runtime-implementation` |

The initial tracked worktree was clean. Baseline commands generated untracked
`bin/` and `reports/`; `lib/` and `libaec.so` are ignored by the root rules.

## Device library

- Checkout state: initially missing because `*.so` is ignored.
- Restored source: `/home/mig19/c2/test/libaec_device.so`.
- Installed path: `starter-kit/lib/libaec_device.so`.
- SHA-256: `295c47c51354a2e58b76cff18633b15daeea9f2e0e4115dccda338a9e66b01d5` (matches `RELEASE_MANIFEST.json`).
- ELF: ELF64, two's complement little-endian, System V, x86-64 shared object.
- Dependencies: `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6`, and the x86-64 loader; all resolved by `ldd`.
- The host lacks `file`; `readelf -h/-d` and `ldd` were used instead.

## Baseline commands and results

Run from `Track-C/C2-runtime/starter-kit` against the original starter source:

| Command | Exit | Result |
|---|---:|---|
| `make clean` | 0 | Removed prior generated `bin/` and `libaec.so`. |
| `make -j2` | 0 | Built Linux `libaec.so`. |
| `make examples` | 0 | Built all six example binaries. |
| `./bin/01_device_query` | 0 | Reported Runtime ABI 2, ISA 2/profile 1, 64 MiB. |
| `python3 cases/test_r101.py --submission .` | 0 | PASS R101, 4/4. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/baseline_public_report.json` | 0 | Score 12/100, level Not passed. |

The grader command exits zero after producing a report even when requirements
fail; pass/fail is therefore read from the JSON and printed requirement status.

## Baseline requirements

| Requirement | Status | Earned | Detail |
|---|---|---:|---|
| R101 | PASS | 4/4 | Device metadata and TLS isolation verified. |
| R102-R106 | FAIL | 0 | Starter returns `AEC_ERROR_NOT_SUPPORTED`. |
| R201-R204 | FAIL | 0 | Allocation is unsupported. |
| R301-R304 | FAIL | 0 | Allocation or Stream creation is unsupported. |
| R401 | PASS correctness | 4/10 | Legal baseline JSON; public performance diagnostic 0. |
| R402 | PASS correctness | 4/10 | Legal naive candidate; public performance diagnostic 0. |

Machine-readable evidence: `reports/baseline_public_report.json`.

## R101 milestone

Run from `Track-C/C2-runtime/starter-kit` after the error/query refactor:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built `src/aec_runtime.cpp` and `src/error.cpp` without diagnostics. |
| `python3 cases/test_r101.py --submission .` | 0 | PASS R101, 4/4. |
| `python3 tests/test_r101_extra.py --submission .` | 0 | PASS TLS isolation, success-preserves-error, Peek/Get, and unknown name. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r101_public_report.json` | 0 | Score remained 12/100; no baseline regression. |
| `nm -D --defined-only libaec.so > reports/exported_symbols.txt` | 0 | Dynamic symbol inspection completed. |
| `readelf -h -d libaec.so > reports/libaec_readelf.txt` | 0 | ELF64 little-endian x86-64 shared object. |
| `ldd libaec.so > reports/libaec_ldd.txt` | 0 | All dependencies resolved. |

Evidence: `reports/r101_public_report.json`, `reports/exported_symbols.txt`,
`reports/libaec_readelf.txt`, and `reports/libaec_ldd.txt`.

## R102 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built allocation, error, and public API modules without diagnostics. |
| `python3 cases/test_r102.py --submission .` | 0 | PASS R102, 6/6. |
| `python3 tests/test_r102_extra.py --submission .` | 0 | PASS zero/OOM/alignment/reuse/interior/stale/double-free checks. |
| `python3 cases/test_r101.py --submission .` | 0 | PASS prior official requirement. |
| `python3 tests/test_r101_extra.py --submission .` | 0 | PASS prior custom coverage. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r102_public_report.json` | 0 | Score 18/100; R101/R102 pass. |

Evidence: `reports/r102_public_report.json`.

## R103 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built command/copy/allocation/error/API modules without diagnostics. |
| `python3 cases/test_r103.py --submission .` | 0 | PASS R103, 6/6. |
| `python3 tests/test_r103_extra.py --submission .` | 0 | PASS spans/accounting/reset and 40 concurrent DMA submits. |
| `python3 cases/test_r102.py --submission .` | 0 | PASS prior official requirement. |
| `python3 tests/test_r102_extra.py --submission .` | 0 | PASS prior custom coverage. |
| `python3 cases/test_r101.py --submission .` | 0 | PASS prior official requirement. |
| `python3 tests/test_r101_extra.py --submission .` | 0 | PASS prior custom coverage. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r103_public_report.json` | 0 | Score 24/100; R101-R103 pass. |

The custom case verified that invalid copy preflight left `submitted_commands`
unchanged and that `aecResetRuntimeStats` did not invalidate a live allocation.
Evidence: `reports/r103_public_report.json`.

## R104 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built kernel/serialization path without diagnostics. |
| `make examples` | 0 | Built all six examples. |
| `./bin/03_vector_add` | 0 | Produced the five expected FP32 sums through the fixed image. |
| `g++ -Iinclude -Isrc -std=c++17 -Wall -Wextra -Wpedantic tests/test_serialization.cpp -o /tmp/c2_test_serialization` | 0 | Built standalone byte-layout test. |
| `/tmp/c2_test_serialization` | 0 | Exact 32-byte little-endian layout and 32 unused zero bytes passed. |
| `python3 cases/test_r104.py --submission .` | 0 | PASS R104, 4/4. |
| `python3 tests/test_r104_extra.py --submission .` | 0 | PASS fixed image, 33 elements, rejection paths, no-submit preflight. |
| Official/custom R101-R103 regression loops | 0 | All prior coverage passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r104_public_report.json` | 0 | Score 34/100; R101-R104 and R301 pass publicly. |

R301's public pass is useful evidence but is not yet treated as full completion;
dedicated status/fault/reset tests remain. Evidence: `reports/r104_public_report.json`.

## R201 / Basic gate milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built generic numeric/GEMM path without diagnostics. |
| `make examples` | 0 | Built all examples. |
| `./bin/05_fp32_gemm` | 0 | Printed the expected 2x3 FP32 result through the fixed image. |
| Serialization compile and `/tmp/c2_test_serialization` | 0 | Exact GEMM offsets 0-39 and unused zero bytes passed. |
| `python3 cases/test_r201.py --submission .` | 0 | PASS R201, 10/10. |
| `python3 tests/test_r201_extra.py --submission .` | 0 | PASS FP32, INT32 saturation, dimensions, overlap, and spans. |
| Official/custom R101-R104 regression loops | 0 | All prior coverage passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/basic_gate_report.json` | 0 | Score 44/100, level Basic, Basic gate true. |

Evidence: `reports/basic_gate_report.json`.

## R105 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built Stream/async integration without diagnostics. |
| `python3 cases/test_r105.py --submission .` | 0 | PASS R105, 5/5. |
| Initial `timeout 30s python3 tests/test_r105_extra.py --submission .` | 1 | Test bug: target created with integer size N was compared as N-1 against a source bytes buffer of N+1. Runtime operations returned success. |
| Corrected `timeout 30s python3 tests/test_r105_extra.py --submission .` | 0 | PASS FIFO/deep-copy/recovery/free-waits and 20 destroy races. |
| Official/custom R101-R105/R201 regression loops | 0 | All prior coverage passed. |
| `python3 cases/test_r302.py --submission .` | 0 | Public dual-channel/async recovery diagnostic passed. |
| `python3 cases/test_r304.py --submission .` | 0 | Public DMA/kernel fault recovery diagnostic passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r105_public_report.json` | 0 | Score 59/100; R105/R301/R302/R304 public-pass. |

The custom test was run with exactly 20 destroy-race iterations. R302/R304 public
passes are recorded but dedicated requirement-level custom tests are still
pending. Evidence: `reports/r105_public_report.json`.

## R106 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built Event generation/marker module without diagnostics. |
| `make examples` | 0 | Built all examples. |
| `./bin/04_stream_event` | 0 | Reported a positive 241 virtual-cycle copy interval. |
| `python3 cases/test_r106.py --submission .` | 0 | PASS R106, 5/5. |
| `timeout 30s python3 tests/test_r106_extra.py --submission .` | 0 | PASS latest generation/cycles/stale handles and 20 destroy races. |
| Official/custom R101-R106/R201 regression loops | 0 | All prior coverage passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r106_public_report.json` | 0 | Score 64/100; R101-R106/R201/R301/R302/R304 public-pass. |

Evidence: `reports/r106_public_report.json`.

## R202 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built all floating GEMM API mappings without diagnostics. |
| `python3 cases/test_r202.py --submission .` | 0 | PASS R202, 10/10. |
| `timeout 30s python3 tests/test_r202_extra.py --submission .` | 0 | PASS FP4 odd tail, FP8 format, async FP16, and FP64. |
| Official/custom R101-R106/R201 regression loops | 0 | All prior coverage passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r202_public_report.json` | 0 | Score 74/100, level Basic. |

Evidence: `reports/r202_public_report.json`.

## R203 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built INT4/INT8 API mappings without diagnostics. |
| `python3 cases/test_r203.py --submission .` | 0 | PASS R203, 4/4. |
| `timeout 30s python3 tests/test_r203_extra.py --submission .` | 0 | PASS odd INT4 packing, async INT8, and INT32 output span. |
| Official/custom R101-R106/R201-R202 regression loops | 0 | All prior coverage passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r203_public_report.json` | 0 | Score 78/100, level Basic; Good gate false. |

Evidence: `reports/r203_public_report.json`.

## R204 milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make -j2` | 0 | Built vector library module without diagnostics. |
| Serialization compile and `/tmp/c2_test_serialization` | 0 | AXPY float bits, DOT/NRM2 offsets, and unused zero bytes passed. |
| `python3 cases/test_r204.py --submission .` | 0 | PASS R204, 6/6. |
| `timeout 30s python3 tests/test_r204_extra.py --submission .` | 0 | PASS AXPY alias, async DOT, NRM2, and preflight bounds. |
| Official/custom R101-R106/R201-R203 regression loops | 0 | All prior coverage passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/r204_public_report.json` | 0 | Score 84/100; only R303 non-Agent public failure remains. |

Evidence: `reports/r204_public_report.json`.

## R303 / Good gate milestone

Run from `Track-C/C2-runtime/starter-kit`:

| Command | Exit | Result |
|---|---:|---|
| `make clean && make -j2 && make examples` | 0 | Clean warning-free build of Runtime and all examples. |
| `./bin/01_device_query` through `./bin/06_registered_copy` | 0 | All six examples passed; registered copy reported one zero-copy command. |
| `python3 cases/test_r303.py --submission .` | 0 | PASS R303, 4/4. |
| `timeout 30s python3 tests/test_r303_extra.py --submission .` | 0 | PASS intervals/subspan/partial flags/pending unregister. |
| `make public-cases` | 0 | 16/16 public cases passed. |
| Custom R101-R106/R201-R204/R303 loop | 0 | All 11 scripts passed; R105/R106 each include 20 races. |
| Serialization compile and run | 0 | All canonical layout tests passed. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/good_gate_report.json` | 0 | Score 88/100, level Good, Basic/Good gates true. |
| `nm -D --defined-only libaec.so` | 0 | Dynamic symbols captured in `reports/exported_symbols.txt`. |
| `readelf -h -d libaec.so` | 0 | ELF64 little-endian x86-64 shared object. |
| `ldd libaec.so` | 0 | All dynamic dependencies resolved. |

Evidence: `reports/good_gate_report.json`, `reports/exported_symbols.txt`,
`reports/libaec_readelf.txt`, and `reports/libaec_ldd.txt`.

## R301 audit

| Command | Exit | Result |
|---|---:|---|
| `python3 cases/test_r301.py --submission .` | 0 | PASS R301, 6/6 (Good-gate run). |
| `timeout 30s python3 tests/test_r301_extra.py --submission .` | 0 | PASS exact stats/resolve/reset and no-submit preflight. |

The custom check compared the entire `aecRuntimeStats` object byte-for-byte with
the official device stats and verified reset preserved allocation/image state.

## R302 audit

| Command | Exit | Result |
|---|---:|---|
| `python3 cases/test_r302.py --submission .` | 0 | PASS R302, 6/6 (Good-gate run). |
| `timeout 30s python3 tests/test_r302_extra.py --submission .` | 0 | PASS four Streams/both channels/concurrent FIFO/recovery. |

The custom check ran four Stream workers concurrently and verified both channel
counters, exact round-trip bytes, deferred invalid-span reporting, and recovery.

## Current verification gaps

- Custom coverage currently includes R101 TLS/error semantics, R102 allocation boundaries/lifetime, R103 DMA spans/accounting/concurrent sequence, and R104 parameter/launch boundaries.
- Pending-reference free behavior passed with queued 1 MiB H2D+D2H work in R105.
- Basic correctness has public and focused custom evidence; hidden tests remain unknown and are not claimed passed.
- No concurrency stress loop has run yet.
- Final exported-symbol, Runtime ELF, dependency, clean-build, and immutable audits remain pending.
- Public Agent diagnostics cannot prove hidden speedup.
