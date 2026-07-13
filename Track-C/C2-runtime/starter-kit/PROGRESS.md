# C2 Progress Log

## 2026-07-13 - Audit and baseline

- Located C2 at `/home/mig19/c2/Agentic4SystemSummerSchoolContest/Track-C/C2-runtime`.
- Recorded clean tracked state at commit `abcaa940b107c153514d3cb162108090631cfdf6`.
- Created branch `codex/c2-runtime-implementation`.
- Verified Linux x86-64, 64-bit, little-endian, Python 3.12.3, G++ 13.3.0, GNU Make 4.3, and glibc 2.39.
- Found the checkout missing the ignored device library; restored an existing exact-hash official artifact.
- Verified device SHA-256, ELF64 x86-64 header, dynamic section, and dependencies.
- Read repository instructions and all required C2 specifications, headers, starter source, public grader/cases, manifests, examples, and Agent schemas.
- Captured immutable contract hashes.
- Baseline build/examples/query succeeded; R101 passed; public score is 12/100.
- Next: shared Runtime state, R101 hardening, R102 allocation, and R103 DMA.

## 2026-07-13 - R101 query and TLS errors

- Added centralized TLS error storage, stable error names, and Device-to-Runtime status mapping in `src/error.*`.
- Wrapped public C entry points in a no-throw exception boundary; success still preserves prior TLS error.
- Changed the Makefile to compile all Runtime source modules while preserving `make -j2` and example entry points.
- Added `tests/test_r101_extra.py` for unknown error names, Peek/Get behavior, success-preserves-error, and two-thread isolation.
- `make -j2`, official R101, custom R101, full public grader, `nm`, `readelf`, and `ldd` all exited 0.
- Public score remains the expected 12/100 because later APIs are still explicit stubs.
- Next: R102 allocation registry, exact-base free, span ownership, and pending references.

## 2026-07-13 - R102 allocation lifetime

- Added a live allocation registry around the official `aecDeviceAlloc`/`aecDeviceFree` calls.
- Device offsets remain opaque; complete spans are checked against one allocation with overflow-safe subtraction.
- Exact-base free removes the allocation from the live registry before waiting for pending leases, preventing new async references.
- Added `tests/test_r102_extra.py` for zero-byte/null output, OOM, 64-byte alignment, lowest-address reuse, interior/unknown/stale/double free, and unchanged outputs on failure.
- Official R102, custom R102, official/custom R101 regression, build, and full public grader all exited 0.
- Public score is now 18/100: R101, R102, and both baseline Agent correctness portions.
- Next: R103 synchronous DMA, global sequence, command/completion validation, and span tests.

## 2026-07-13 - R103 synchronous DMA

- Added one process-wide command sequence and a serialized submit/completion validator in `src/command.*`.
- Built zero-initialized ABI-v2 H2D/D2H commands with legal chunk, queue depth, channel, host address, and device offset fields.
- Added synchronous copy entry points that validate null/zero inputs and acquire a complete single-allocation lease before submit.
- Added `tests/test_r103_extra.py` for interior spans, adjacent-allocation crossing, near-`UINT64_MAX`, no-submit-on-preflight-failure, stats reset preserving allocations, round-trip bytes, and 40 concurrent submits.
- Official R103, all custom/basic regressions, build, and full public grader exited 0.
- Public score is now 24/100; R101-R103 pass.
- Next: R104 canonical Vector Add parameters, fixed-image resolve, launch validation, and ISA evidence.

## 2026-07-13 - R104 fixed-image Vector Add

- Added reusable explicit little-endian parameter serialization; command bytes never come from native-struct `memcpy` and unused bytes remain zero.
- Added dimension/block-volume checks, vector count/storage checks, complete allocation leases, and output/input overlap rejection.
- Resolved `(VECTOR_ADD_F32, FP32, default)` through the official device and validated ABI, ISA, handle, parameter size, and instruction hash before submit.
- Added `tests/test_serialization.cpp` and `tests/test_r104_extra.py`, including a 33-element launch, invalid kernels/dimensions/args/spans/overlap, and no-submit preflight accounting.
- Official R104, custom R104, serialization test, example, all earlier official/custom regressions, build, and full public grader exited 0.
- Public score is 34/100. R301 also passes publicly through the shared command/stats path, but remains pending dedicated audit and fault-path coverage.
- Next: R201 generic GEMM spans/serialization/image selection for FP32 and INT32; Basic gate.

## 2026-07-13 - R201 and Basic gate

- Added checked GEMM element/storage sizing for packed, byte, 16-bit, 32-bit, and 64-bit dtypes; integer outputs use INT32 storage.
- Added three-span non-overlap validation and allocation leases.
- Serialized exact 40-byte GEMM parameters and submitted typed naive frozen images resolved through the official device.
- Connected FP32 and INT32 public APIs; no host-side numeric implementation exists.
- Added `tests/test_r201_extra.py` for FP32, INT32 saturation, invalid/over-limit dimensions, overlap, undersized spans, and no-submit accounting; extended the byte-layout test through offset 39 and unused zero bytes.
- Official R201, custom R201, FP32 example, serialization, all Basic regressions, build, and full grader exited 0.
- Public score is 44/100, level Basic, with the Basic gate true.
- Next: R105 Stream FIFO, async DMA/launch ownership, errors, recovery, destroy races, and pending allocation free.
