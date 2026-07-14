# C2 Runtime Test Report

Report date: 2026-07-14 (Asia/Shanghai)

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
| Branch | `codex/c2-device-library-update` |
| Verified implementation commit | `d7c2a93` |
| Prior merged delivery commit | `2e65745` |

The initial tracked worktree was clean. Baseline commands generated untracked
`bin/` and `reports/`; `lib/` and `libaec.so` are ignored by the root rules.

## Device library

- Initial development artifact SHA-256: `295c47c51354a2e58b76cff18633b15daeea9f2e0e4115dccda338a9e66b01d5`.
- Official update commit: `c30b3f9eed11183fee8e33735e82cdf72a50cbe8`.
- Current installed path: `starter-kit/lib/libaec_device.so`.
- Current SHA-256: `b96b09e88ae160b659cf72bd079da8bc647d2bc55d377297a649d77c30ddcb0a` (matches the updated `RELEASE_MANIFEST.json`).
- Updated manifest SHA-256: `99f9867828f530605f1599fc7770da18f205aaf3ab831ff32899bc630915ba7f`.
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

## R304 audit

| Command | Exit | Result |
|---|---:|---|
| `python3 cases/test_r304.py --submission .` | 0 | PASS R304, 4/4 (Good-gate run). |
| `timeout 30s python3 tests/test_r304_extra.py --submission .` | 0 | PASS one-shot DMA/kernel/command faults and recovery. |

The custom check queued two matching commands after each injected DMA/kernel
fault, proving only the first failed and the second produced valid data/ISA
evidence. NEXT_COMMAND was also verified synchronously.

## R401/R402 Agent milestone

| Command | Exit | Result |
|---|---:|---|
| `timeout 30s python3 tests/test_agents.py --submission .` | 0 | PASS schema/purity plus 120 DMA and 80 Kernel model optima. |
| `python3 cases/test_r401.py --submission .` | 0 | PASS correctness; public diagnostic 1.000000. |
| `python3 cases/test_r402.py --submission .` | 0 | PASS correctness; public diagnostic 1.000000. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/excellent_public_report.json` | 0 | Score 88/100, Good; all requirements pass, both Agent public diagnostics 1.0. |

Evidence: `reports/excellent_public_report.json`. The released grader exposes no
full/hidden profile, so hidden performance points and the Excellent gate remain
unverified even though the policies are optimal on the published models and
official evaluator sweep.

## ABI and sanitizer hardening

| Command | Exit | Result |
|---|---:|---|
| Initial ASan+UBSan build plus `tests/test_launch_extra.py` | 31 | UBSan found an invalid C `aecKernelId` value being loaded as a C++ enum for the unknown-ID test. |
| Rebuilt ASan+UBSan after raw-enum boundary fix | 0 | Sanitizer build succeeded without warnings. |
| Sanitized launch/R101/R105/R106/R301/R302/R303/R304 loop | 0 | All eight tests passed; no ASan or UBSan diagnostic. Leak detection was disabled for intentional process-lifetime handle tombstones. |
| `make clean && make -j2` after sanitizer run | 0 | Restored default release artifact. |
| `timeout 30s python3 tests/test_launch_extra.py --submission .` | 0 | PASS all public Kernel IDs and native argument structures. |
| `make public-cases` after hardening | 0 | 16/16 public cases passed. |
| All 16 custom Python scripts plus serialization | 0 | All passed; includes Agent 120+80 optimality sweep. |
| `python3 grader/public_grade.py --submission . --profile public --json-out reports/hardening_public_report.json` | 0 | Score 88/100, Good; public Agent diagnostics 1.0. |
| `nm -D --defined-only libaec.so` | 0 | Exactly 36 public `aec*` functions plus `AEC_2`; no project-internal C++ ABI symbols. |

Evidence: `reports/hardening_public_report.json` and
`reports/exported_symbols.txt`.

## Pre-update final release verification (2026-07-13)

Run from `Track-C/C2-runtime/starter-kit` on the remote Linux host at verified
implementation commit `d7c2a93`. The documentation and generated evidence are
committed afterward and do not change the verified Runtime or Agent sources.

Exact commands:

```bash
make clean
make -j2
make examples
./bin/01_device_query
./bin/02_isa_encoding
./bin/03_vector_add
./bin/04_stream_event
./bin/05_fp32_gemm
./bin/06_registered_copy
make public-cases
for test_path in tests/test_*.py; do python3 "$test_path" --submission . || exit $?; done
g++ -Iinclude -Isrc -std=c++17 -Wall -Wextra -Wpedantic tests/test_serialization.cpp -o /tmp/c2_test_serialization
/tmp/c2_test_serialization
python3 grader/public_grade.py --submission . --profile public --json-out reports/final_public_report.json
python3 tests/test_immutable.py --submission .
nm -D --defined-only libaec.so > reports/exported_symbols.txt
readelf -h -d libaec.so > reports/libaec_readelf.txt
objdump -f libaec.so > reports/libaec_objdump.txt
ldd libaec.so > reports/libaec_ldd.txt
sha256sum lib/libaec_device.so libaec.so
```

| Verification | Exit | Result |
|---|---:|---|
| Clean and release build | 0 | Warning-free C++17 shared-library build with default `-O2` flags. |
| Six examples | 0 | Query, ISA encoding, Vector Add, Stream/Event, FP32 GEMM, and registered copy all ran successfully. |
| `make public-cases` | 0 | 16/16 public cases passed. |
| All `tests/test_*.py` | 0 | 17/17 scripts passed, including immutable and Agent model audits. |
| Standalone serialization | 0 | All canonical layouts, endian fields, float bits, and unused zero bytes passed. |
| Final public grader | 0 | 88/100, level Good; Basic/Good true, Excellent false because hidden performance is absent. |
| Immutable audit | 0 | 73 manifest files, 34 images, device hash, no extras/missing files, and initial-commit diff all clean. |
| Symbol/ELF/dependency audit | 0 | 36 public `aec*` functions plus `AEC_2`; ELF64 little-endian x86-64; every dependency resolved. |

Final requirement evidence:

| Requirement | Public status | Earned in public profile | Focused custom evidence |
|---|---|---:|---|
| R101 | PASS | 4/4 | TLS isolation, error preservation, Peek/Get, unknown values. |
| R102 | PASS | 6/6 | OOM, reuse, alignment, interior/stale/double free. |
| R103 | PASS | 6/6 | Span arithmetic, reset invariants, 40 concurrent submissions. |
| R104 | PASS | 4/4 | Fixed image, rejection paths, stats, serialization. |
| R105 | PASS | 5/5 | FIFO, deep copy, recovery, free wait, 20 destroy races. |
| R106 | PASS | 5/5 | Latest generation, cycles, stale handles, 20 destroy races. |
| R201 | PASS | 10/10 | FP32, INT32 saturation, dimensions, overlap, spans. |
| R202 | PASS | 10/10 | FP4 odd tail, FP8 format, async FP16, FP64. |
| R203 | PASS | 4/4 | Odd INT4 packing, async INT8, INT32 output span. |
| R204 | PASS | 6/6 | AXPY aliasing, async DOT, NRM2, bounds. |
| R301 | PASS | 6/6 | Exact stats/resolve/reset and no-submit preflight. |
| R302 | PASS | 6/6 | Four Streams, both channels, concurrent FIFO, recovery. |
| R303 | PASS | 4/4 | Intervals, flags, partial overlap, pending unregister. |
| R304 | PASS | 4/4 | One-shot DMA/kernel/command faults and recovery. |
| R401 | PASS correctness | 4/10 | Schema/purity/determinism and 120 brute-force optima. |
| R402 | PASS correctness | 4/10 | Candidate legality and 80 official-evaluator optima. |

Pre-update artifacts:

- `reports/final_public_report.json`: machine-readable 88/100 result.
- `reports/exported_symbols.txt`: exact versioned public export surface.
- `reports/libaec_readelf.txt`: ELF header, `NEEDED` entries, and `$ORIGIN/lib` runpath.
- `reports/libaec_objdump.txt`: `elf64-x86-64`, dynamic shared object.
- `reports/libaec_ldd.txt`: all direct/transitive libraries resolved.
- `libaec.so` SHA-256: `2784fd96377c8ac4d1969e34c16dd216561195f7000fb497d345a1a0b7308fe4`.
- Device SHA-256: `295c47c51354a2e58b76cff18633b15daeea9f2e0e4115dccda338a9e66b01d5`.

## Residual risk

- Hidden Agent inputs, average speedup, and the Excellent gate are not available in the released grader and are not claimed passed.
- Hidden maximum-shape GEMM, special-floating-point, and unusual cross-Stream
  Event schedules remain possible coverage gaps despite public, custom, and
  sanitizer evidence.
- The host lacks `file`; `readelf`, `objdump`, and `ldd` were used and all passed.
- `lib/libaec_device.so` is force-tracked to match official upstream despite the global `*.so` ignore rule.

## Official device update verification

Official source: `ephonic/Agentic4SystemSummerSchoolContest@b2997a2`, with the
C2 update introduced by `c30b3f9`. Tree comparison found no other C2 contract
changes: headers, docs, fixed images, grader, cases, golden data, schemas,
`spec.md`, and `scoring.md` are byte-identical to the prior release.

| Command/check | Exit | Result |
|---|---:|---|
| Old-library `python3 tests/test_r204_max_length.py --submission .` | 1 | Reproduced defect: DOT count 90,909 returned status 9 (`AEC_ERROR_ISA_TRAP`). |
| New-library maximum-length test | 0 | DOT/NRM2 passed historical boundaries and 1,048,576; max+1 rejected without submit. |
| Maximum reduction virtual cycles | 0 | DOT 46,137,368; NRM2 33,554,466. |
| `make clean`, `make -j2`, `make examples` | 0 | Warning-free release build and all examples built. |
| Six example binaries | 0 | All produced expected results. |
| `make public-cases` | 0 | 16/16 requirements passed. |
| All `tests/test_*.py` | 0 | 18/18 custom scripts passed. |
| Standalone serialization test | 0 | All canonical parameter layouts passed. |
| Updated immutable audit | 0 | Exact official manifest/device hashes, 73 entries, 34 images, and all static contracts passed. |
| Public grader to `reports/device_update_public_report.json` | 0 | 88/100 Good; Basic/Good true; R401/R402 diagnostics 1.0. |
| Structured old/new public report comparison | 0 | Every requirement pass, score, detail, device evidence, and Agent case metric is identical. |
| Old/new ABI and evaluator comparison | 0 | Caps, 34 resolve records, and 30,210 GEMM evaluator completions are byte-identical. |

The Device ABI export set is unchanged (10 `aecDevice*` functions), and all
new-library dependencies resolve. No Runtime or Agent source change was needed;
the existing R204 path already performs one fixed-image launch with canonical
parameters and no Host computation or reduction chunking.

The updated library fixes correctness beyond the old reduction limits without
changing observed public-case or GEMM evaluator performance. The released
grader still cannot award hidden Agent performance, so 88/100 is the maximum
observable public score; Kernel Agent hidden full-score status remains
unverified.

## Kernel Agent full-domain oracle verification (2026-07-14)

The submitted Agent never calls the oracle. These commands run only during
pre-submission analysis on the remote Linux host:

```bash
python3 tools/kernel_oracle_collect.py --submission . --jobs 10 \
  --output reports/kernel_oracle_summary.json
python3 tools/kernel_policy_generate.py --submission .
python3 tests/test_kernel_agent_optimality.py --submission .
python3 tests/test_agents.py --submission .
python3 cases/test_r402.py --submission .
```

| Verification | Exit | Result |
|---|---:|---|
| Oracle determinism | 0 | 100 repeated calls produced byte-identical completions. |
| Invalid oracle probes | 0 | All failed status; failed completion payloads were discarded and never labeled. |
| Device stats immutability | 0 | Full `aecDeviceStats` remained byte-identical before/after evaluator use in every worker. |
| Alignment/workspace audit | 0 | 3,240 calls across thresholds and representative shapes proved successful cycles are constant within each legal class. |
| Full domain collection | 0 | 10 dtypes, 5,570,560 calls, 167,772,160 represented shapes, streaming record SHA `73426caf...f67c`. |
| Independent FP32 replay | 0 | A fresh 557,056-call shard reproduced record SHA `b8319815...3191ba` and every aggregate exactly. |
| Dominance/argmin | 0 | 0 violations, 0 mismatches, 100% argmin accuracy, max regret 0, no ties. |
| Candidate metamorphic tests | 0 | 550 subset/permutation cases across all dtypes plus arbitrary IDs and threshold changes passed. |
| Protocol negatives | 0 | Unknown dtype, bounds, duplicates, extra fields, no-legal candidate, and Unicode escaping passed. |
| Determinism/latency | 0 | 1,000 independent runs; median 15.411 ms, p99 18.934 ms, no stderr. |
| Existing Agent suite | 0 | 120 DMA brute-force optima and 80 Kernel evaluator probes passed. |
| Public R402 | 0 | Correctness PASS, public diagnostic 1.0. |
| Full custom Python suite | 0 | 19/19 scripts passed on the final clean build. |
| Standalone serialization | 0 | All canonical parameter layouts passed without warnings. |
| Full public grader | 0 | 88/100 Good; all correctness passed and both public diagnostics are 1.0. |

The full-domain result selects path A from the implementation plan: the highest
legal variant is always the oracle argmin, so a fitted performance model and an
exception table would add complexity without improving a single legal choice.
Per dtype, 261,192 of 262,144 multi-candidate shapes reach full performance
fraction and 952 have a partial fraction. Vectorized speedup is at least about
1.653x; tiled speedup ranges from about 1.421x to 1.666x. The policy is therefore
the maximum achievable implementation under the published candidates, while
the exact hidden R402 points remain dependent on the undisclosed case mix.

Machine-readable evidence:

- `reports/kernel_oracle_summary.json`
- `reports/kernel_policy_report.json`

## Independent audit remediation verification (2026-07-14)

The independent audit snapshot is preserved in `../AUDIT_REPORT.md` and
`../AUDIT_EVIDENCE/`. This section records the separate remediation run. The
official upstream HEAD was rechecked as
`b2997a228d9446ff254cb324225b731df66c7546`; no newer release appeared during
the run.

| Verification | Exit | Result |
|---|---:|---|
| Forced release rebuild | 0 | Warning-free build after deferring worker start and changing the loader contract. |
| `readelf -d libaec.so` | 0 | No `libaec_device.so` `DT_NEEDED` and no RUNPATH; only declared platform C/C++ runtime dependencies remain. |
| `make -B examples` and six binaries | 0 | Examples link the development device explicitly and all six run successfully. |
| Fresh official grader against strict three-file directory | 0 | 88/100 public; 16/16 requirements PASS; Runtime/compute/driver 80/80 and both Agent correctness checks 4/4. |
| Fresh official `cases/run_all.py` against strict directory | 0 | 16/16 cases passed. |
| `tests/test_agents.py` | 0 | 120 DMA optima, 80 Kernel optima, and empty candidate-ID round trip passed. |
| `tests/test_kernel_agent_optimality.py` | 0 | Certificate, 550 subset/permutation cases, and 1,000 runs passed; median 17.121 ms, p99 31.838 ms. |
| Runtime-focused custom tests with official preload contract | 0 | Launch plus R101-R106, R201-R204, and R301-R304 all passed. |
| Maximum reduction | 0 | DOT/NRM2 count 1,048,576 passed; cycles 46,137,368 / 33,554,466. |
| Maximum GEMM matrix | 0 | All ten dtypes passed at M=N=K=256. |
| Stream/fault stress | 0 | R105/R106/R302/R303/R304 each passed 50 rounds, 250 case processes total. |
| Non-PIE TSan driver | 0 | Three complete instrumented executions had no data-race report. |
| ASan+UBSan official grader | 0 | Full public grader completed with both sanitizers set to halt on error and no diagnostics. |
| Standalone serialization | 0 | Compile and execution both passed without warnings. |

The custom runtime tests load `libaec.so` directly, while the official grader
first loads `libaec_device.so` with `RTLD_GLOBAL`. After removing the forbidden
submission dependency, equivalent local invocations use:

```bash
env LD_PRELOAD="$PWD/lib/libaec_device.so" \
  python3 tests/test_r105_extra.py --submission .
```

This preload is test infrastructure only. The strict artifact contains exactly
the three allowed files, and the official grader supplies the controlled device
library. TSan on this host intermittently aborts before program startup with
`unexpected memory mapping`; successful non-PIE runs are reported separately
and produced no race finding.

Audit F-003 required no code change. Contrary to the finding, the immutable
`schemas/dma_input.schema.json` contains `maximum: 64` for `concurrency`, so 65
is schema-invalid. F-001, F-002, F-004, and F-005 are remediated; the follow-up
audit records formal closure against the committed remediation SHA.
