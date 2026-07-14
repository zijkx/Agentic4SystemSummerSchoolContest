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

## 2026-07-13 - R203 packed integer GEMM

- Connected INT4 and INT8 APIs to the shared typed frozen-image GEMM path; both use INT32 output storage.
- Added `tests/test_r203_extra.py` with K=3 signed INT4 low-nibble packing/zero high tail, equivalent async INT8, and an undersized INT32 output preflight rejection.
- Official R203, custom R203, all prior official/custom regressions, build, and full grader exited 0.
- Public score is 78/100 but remains Basic because R204 and R303 are mandatory Good gates.
- Next: R204 AXPY, DOT, and NRM2 fixed-image operations.

## 2026-07-13 - R204 vector library operations

- Added prepared fixed-image AXPY, DOT, and NRM2 operations in `src/library_ops.*` with shared sync/async execution.
- Serialized exact 28/32/24-byte parameter blocks; alpha uses explicit FP32 bits and all unused bytes remain zero.
- Added count/storage checks and result/input overlap rules while permitting the documented AXPY `x == y` case.
- Added `tests/test_r204_extra.py` for in-place AXPY, async DOT, NRM2, partial overlap, zero count, undersized spans, and no-submit accounting; extended standalone serialization tests.
- Official R204, custom R204, serialization, all prior official/custom regressions, build, and full grader exited 0.
- Public score is 84/100. R303 is the only remaining non-Agent public failure.
- Next: R303 registration/zero-copy/pending lifetime, followed by dedicated R301/R302/R304 audits.

## 2026-07-13 - R303 and Good gate

- Added exact nonempty host interval registration with duplicate/overlap/overflow rejection and exact-base unregister.
- Complete registered subspans acquire pending leases and set both REGISTERED and ZERO_COPY; partial overlaps remain legal normal DMA.
- Unregister removes the interval from the live map and waits for prior async registration leases.
- Added `tests/test_r303_extra.py` for null/duplicate/contained/partial overlap, adjacent intervals, interior unregister, pointer overflow, subspan flags, partial normal flags, and pending async unregister.
- Clean build, all six examples, 16/16 public cases, all 11 custom scripts, serialization, symbols, ELF, and dependencies exited 0.
- Public score is 88/100, level Good, with Basic and Good gates true.
- Next: dedicated R301/R302/R304 custom audits, then Agent policy optimization.

## 2026-07-13 - R301 command accounting audit

- Added `tests/test_r301_extra.py`.
- Verified exact 4-command accounting (two H2D, one ISA launch, one D2H), Runtime/device stats byte equality, resolved frozen handle, retired instructions, digest, and cycle relationships.
- Verified invalid launch preflight leaves every stat byte unchanged.
- Verified stats reset zeros counters while preserving a live allocation, process command usability, and the resolved image handle.
- Official R301 was already public-pass; the dedicated custom test exited 0.
- Next: record R302 and R304 dedicated audit evidence.

## 2026-07-13 - R302 dual-DMA audit

- Added `tests/test_r302_extra.py`.
- Verified four live Streams enqueue independent H2D/D2H FIFO pairs and synchronize concurrently with exact byte results.
- Verified both official DMA channels receive commands under the stable Stream-ID policy.
- Verified an invalid queued span reports on Stream sync, the error is cleared after reporting, and later valid work succeeds.
- Verified invalid direction is immediate and a null Stream returns invalid handle.
- Official R302 and the dedicated custom test exited 0.
- Next: record R304 fault audit evidence.

## 2026-07-13 - R304 fault recovery audit

- Added `tests/test_r304_extra.py`.
- Verified NEXT_DMA faults the first of two queued DMA commands, the second writes data, Stream sync reports/clears the first error, and later work succeeds.
- Verified NEXT_KERNEL faults the first of two queued Vector Add launches, the second retires instructions and produces the correct output/digest.
- Verified NEXT_COMMAND faults one synchronous DMA and the immediately following DMA succeeds.
- Official R304 and the dedicated custom test exited 0.
- Every non-Agent requirement now has public-pass evidence and focused custom coverage; public level remains Good at 88/100.
- Next: implement and optimize generalized R401/R402 policies.

## 2026-07-13 - R401/R402 generalized Agent policies

- Replaced the DMA baseline with a strict-schema policy that uses the largest legal chunk, effective two-way queueing when concurrency permits, registered zero-copy, and a direction-based legal channel.
- Replaced the Kernel baseline with strict candidate validation, alignment/workspace/divisibility filtering, public diagnostic-cycle minimization when supplied, and highest legal variant selection otherwise.
- Neither policy uses `case_id`, candidate names, public input values, persistent state, network access, or non-stdlib dependencies.
- Added `tests/test_agents.py` for valid/invalid JSON, exact output keys, stdout/stderr purity, one-second timeout, determinism, arbitrary candidate IDs/order, and no-legal-candidate failure.
- Exhaustively matched 120 DMA requests against all legal action combinations and matched 80 dtype/shape Kernel requests against the official read-only evaluator's minimum cycles.
- Official R401/R402 correctness passed and both public performance diagnostics improved from 0.0 to 1.0. Public score remains 88/100 because public profile awards no performance points.
- Hidden average speedup and the Excellent gate cannot be executed or claimed with the released grader.
- Next: final hardening, sanitizer/stress regression, immutable audit, and documentation.

## 2026-07-13 - ABI and hidden-surface hardening

- Extended `aecLaunch` from Vector Add to every public Kernel ID: naive/tiled/vectorized GEMM, AXPY, DOT, and NRM2, with exact native argument sizes, field-wise reads, reserved checks, variant constraints, and canonical parameters.
- Added `tests/test_launch_extra.py`; every public Kernel ID, including async tiled GEMM argument deep-copy, passed through official fixed images.
- Changed unknown Kernel IDs from the implementation-stage `NOT_SUPPORTED` result to contract-appropriate invalid argument now that all public IDs are implemented.
- Added hidden-by-default compiler visibility and `src/libaec.map`; the ELF exports exactly 36 public `aec*` functions plus the `AEC_2` version node.
- Initial UBSan run exposed invalid C enum values being read as C++ enums. C ABI boundaries now copy raw enum bits to integers before validation for error names, copy direction, Kernel ID, and FP8 format.
- Repeated ASan+UBSan build and eight lifetime/concurrency/fault/launch tests passed with no diagnostics, then a clean default release build was restored.
- Release 16/16 public cases, all 16 custom scripts, serialization, Agent model sweeps, and public grader passed after hardening.
- Next: immutable/final artifact audit and review documentation.

## 2026-07-13 - Final release and review audit

- Added `tests/test_immutable.py`; it verified 73 manifest-controlled contract files, exactly 34 official images, the device-library hash, no missing/extra files, and no tracked immutable diff from `abcaa940`.
- Performed a clean warning-free default build and rebuilt all six examples; every example exited 0.
- Final `make public-cases` passed 16/16. All 17 custom Python scripts and the standalone serialization test exited 0 on the same release artifact.
- Final public grader produced `reports/final_public_report.json`: 88/100, level Good, Basic/Good true, Agent diagnostics 1.0.
- Final ELF audit found ELF64 little-endian x86-64, 36 public `aec*` functions plus `AEC_2`, `$ORIGIN/lib`, and fully resolved dependencies.
- Completed `IMPLEMENTATION.md` with five Mermaid diagrams and `REVIEW_GUIDE.md` with requirement/function mapping, commits, risks, and ten review questions.
- Runtime and Agent work is complete against all released contracts. Hidden Agent performance remains unavailable and is not claimed.

## 2026-07-14 - Official device-library update

- Audited official upstream `ephonic/Agentic4SystemSummerSchoolContest@b2997a2`; C2 changed only in commit `c30b3f9`: `lib/libaec_device.so` and the matching `RELEASE_MANIFEST.json` hash.
- Reproduced the old library defect exactly: DOT count 90,908 succeeded and 90,909 returned `AEC_ERROR_ISA_TRAP`.
- Replaced old device hash `295c47c...` with official hash `b96b09e...`; exported Device ABI symbols and dynamic dependencies are unchanged.
- Added `tests/test_r204_max_length.py`. DOT and NRM2 now pass at both historical boundaries and count 1,048,576, with maximum-count cycles 46,137,368 and 33,554,466; max+1 is rejected before submit.
- No Runtime numeric source change was required: the existing fixed-image, single-launch implementation already matched the specification.
- Clean build, six examples, 16/16 public cases, all 18 custom scripts, serialization, immutable audit, and public grader passed.
- The new and pre-update public reports are structurally identical for every requirement, including device evidence and Agent case cycles; score remains 88/100 public, with both diagnostics 1.0.
- A separate old/new comparison found byte-identical caps, all 34 resolve records, and 30,210 GEMM evaluator completions across 10 dtypes and boundary/seeded shapes.

## 2026-07-14 - Kernel Agent full-domain oracle certificate

- Added an offline oracle collector with device-hash pinning, 100-call
  determinism, failed-status label rejection, stats immutability, threshold
  equivalence checks, isolated dtype workers, checkpoints, and streaming record
  hashes.
- Enumerated 5,570,560 legal candidate evaluations covering all 10 dtypes and
  every multi-candidate point in `M/N/K=[1,256]`; the legality partition
  represents 167,772,160 dtype/shape combinations.
- Found zero variant-dominance violations, zero policy mismatches, 100% argmin
  accuracy, zero maximum regret, and no ties. The compact highest-legal-variant
  policy is therefore the full-domain optimum; no fitted model is needed.
- Replayed the complete 557,056-call FP32 shard in a fresh checkpoint directory;
  record SHA `b8319815...3191ba` and all aggregate fields matched the initial
  parallel collection exactly.
- Strengthened Kernel Agent dtype/bounds/intrinsic-variant validation and stable
  tie-breaking. A strict self-contained JSON codec reduced process-level
  latency from p99 26.127 ms to 18.934 ms.
- Added `tests/test_kernel_agent_optimality.py`: 550 candidate
  subset/permutation cases across all dtypes, arbitrary IDs, threshold and
  invalid-input cases, Unicode escaping, offline static checks, and 1,000-run
  determinism all passed.
- Existing Agent tests and public R402 continue to pass with diagnostic 1.0.
  Hidden performance remains unavailable; the implementation is oracle-optimal
  but does not claim an undisclosed full-profile score.
- Final clean build, six examples, 16/16 public cases, 19/19 custom Python
  scripts, standalone serialization, immutable audit, and the public grader all
  passed after integration.

## 2026-07-14 - Independent audit remediation

- Preserved the independent audit as commit `631f2a7`; it reported two HIGH,
  two MEDIUM, and one LOW finding, with no CRITICAL integrity finding.
- Fixed the Stream constructor race by starting the worker in the constructor
  body, after every member has completed initialization. A non-PIE TSan driver
  completed three instrumented runs without a race report; other invocations
  hit the host's known TSan `unexpected memory mapping` startup failure.
- Removed the device library from `libaec.so` `DT_NEEDED` and removed its
  development RUNPATH. Examples now link the device explicitly. A strict
  submission containing only `libaec.so` and the two Agents loaded through a
  fresh official grader and passed 16/16 requirements.
- Allowed empty candidate IDs because the official Kernel input/output schemas
  permit any string. The focused Agent suite now covers an empty-ID round trip.
- Rejected audit finding F-003 as a false positive: the immutable official DMA
  schema explicitly sets `concurrency.maximum` to 64, so the existing bound is
  required and was not changed.
- Reissued `reports/kernel_policy_report.json` for the updated Agent SHA. The
  full-domain oracle result is unchanged: 5,570,560 calls, zero mismatches,
  100% argmin accuracy, and zero regret. The 1,000-process regression passed
  with median 17.121 ms and p99 31.838 ms under the stable 250 ms guardrail.
- Re-ran the strict official grader (88/100 public, all correctness PASS),
  16/16 case wrappers, all focused custom tests, maximum DOT/NRM2, all ten
  256-cubed GEMMs, standalone serialization, and ASan+UBSan without errors.
- R105/R106/R302/R303/R304 passed 50 consecutive rounds each, totaling 250
  process-level case runs after the Stream fix.
