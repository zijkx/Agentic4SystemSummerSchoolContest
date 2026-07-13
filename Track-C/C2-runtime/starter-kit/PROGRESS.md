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

## 2026-07-13 - R105 asynchronous Stream FIFO

- Added process-lifetime Stream handle tombstones and a live registry, preventing stale pointer reuse after destroy.
- Added one worker/deque per Stream, strict FIFO, drain/join destroy, first-unreported async error, and recovery after `aecStreamSync` reports it.
- Connected async DMA and prepared Vector Add/FP32/INT32 GEMM work; launch parameters are fully materialized before enqueue.
- Work items own allocation leases. A queued H2D+D2H followed immediately by `aecFree` completed correctly before free returned.
- Added `tests/test_r105_extra.py` for null/stale/double handles, launch-args deep copy, FIFO, queued invalid-span propagation/recovery, free-waits, and 20 enqueue/destroy races.
- The first custom run found a test-only `ctypes` N versus N+1 buffer-length mistake; no Runtime change was made. After correcting the copy length, the test and full repeated regression passed.
- Public R105 passes. R302 and R304 also pass publicly through the dual-channel and unified async fault paths.
- Public score is 59/100, level Basic. R301/R302/R304 await dedicated custom audits before final completion status.
- Next: R106 Event generations and virtual-cycle FIFO markers.

## 2026-07-13 - R106 Event generations

- Added Event handle tombstones/live registry and an explicit `next_generation`/`latest_generation` state model.
- Event record reserves a generation and enqueues a Stream FIFO marker; the marker reads official device total virtual cycles only after prior work.
- Completion slots are allocated at reserve time, so marker completion cannot strand a waiter through a later allocation failure.
- Destroy removes the live handle, disables new records, snapshots the latest generation, and waits for it without stale pointer access.
- Added `tests/test_r106_extra.py` for unrecorded behavior, latest of consecutive records, NOT_READY-or-complete query, positive/zero/reversed elapsed cycles, invalid-stream rollback, stale/double handles, and 20 record/destroy races.
- Event example, official R106, custom R106, all prior official/custom regressions, build, and full grader exited 0.
- Public score is 64/100, level Basic.
- Next: R202 floating GEMM formats followed by R203 packed integer GEMM.

## 2026-07-13 - R202 floating GEMM formats

- Connected FP4 E2M1, FP8 E4M3/E5M2, FP16, BF16, and FP64 APIs to the existing checked generic GEMM path.
- FP8 API values are explicitly mapped to Runtime dtypes; unknown formats fail before allocation lookup or submit.
- Added `tests/test_r202_extra.py` for one-element FP4 low-nibble/high-zero output, invalid FP8 format, async FP16, and FP64.
- Official R202, custom R202, all prior official/custom regressions, build, and full grader exited 0.
- Public score is 74/100, still Basic because Good requires every named correctness requirement, not just a score threshold.
- Next: R203 INT4/INT8 packed inputs and saturated INT32 outputs.
