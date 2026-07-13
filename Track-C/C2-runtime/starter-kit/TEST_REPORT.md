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

## Current verification gaps

- Custom coverage currently includes R101 TLS/error semantics and R102 allocation boundaries/lifetime.
- Pending-reference free behavior will be stress-tested once async Stream work exists in R105.
- No concurrency stress loop has run yet.
- Final exported-symbol, Runtime ELF, dependency, clean-build, and immutable audits remain pending.
- Public Agent diagnostics cannot prove hidden speedup.
