# C2 Runtime Implementation Plan

Last updated: 2026-07-13 (Asia/Shanghai)

## Environment and repository

- Repository: `/home/mig19/c2/Agentic4SystemSummerSchoolContest`
- C2 root: `/home/mig19/c2/Agentic4SystemSummerSchoolContest/Track-C/C2-runtime`
- Starter kit: `/home/mig19/c2/Agentic4SystemSummerSchoolContest/Track-C/C2-runtime/starter-kit`
- Path resolution: the preferred path from the task exists; the concatenated fallback path does not.
- Initial commit: `abcaa940b107c153514d3cb162108090631cfdf6`
- Working branch: `codex/c2-runtime-implementation`
- Initial tracked worktree: clean. Baseline build later created untracked `bin/` and `reports/`; `lib/` and `libaec.so` are ignored by the repository.
- Host: Linux `x86_64`, 64-bit, little-endian; kernel `6.8.0-110-generic`.
- Toolchain: Python 3.12.3, GCC/G++ 13.3.0, GNU Make 4.3, glibc/ldd 2.39.
- `file` is not installed. ELF identity is verified with `readelf`; no system package was installed.

## Official device library

The checkout initially lacked `lib/libaec_device.so`. An existing artifact at
`/home/mig19/c2/test/libaec_device.so` was inspected before use. Its SHA-256 is
exactly the value frozen in `RELEASE_MANIFEST.json`:

```text
295c47c51354a2e58b76cff18633b15daeea9f2e0e4115dccda338a9e66b01d5
```

It is ELF64, little-endian, x86-64, and all dependencies resolve. The exact
artifact was restored to `starter-kit/lib/libaec_device.so`; it remains ignored
and must be present in the formal build environment.

## Immutable contracts

Do not modify:

- `include/aec_runtime.h`, `include/aec_device_abi.h`, `include/aec_isa.h`
- `lib/libaec_device.so`
- `kernels/images/`, `kernels/manifest.json`
- `grader/`, `cases/`, `golden/`, `schemas/`

The audit SHA-256 list was captured before implementation. Final verification
will compare every immutable tracked file with `RELEASE_MANIFEST.json` and the
device library with the hash above.

## Non-negotiable invariants

1. `aecDevicePtr` is an opaque 64-bit device offset and is never dereferenced by the host.
2. A device span must be wholly contained in one live allocation.
3. Addition, multiplication, span, and storage-size calculations are overflow checked.
4. Command sequence is process-wide, nonzero, and strictly increasing.
5. Successful APIs do not clear a prior thread-local error.
6. Runtime kernel IDs are resolved through `aecDeviceResolveKernel`; they are never device handles.
7. Parameter blocks are canonical little-endian byte arrays without native padding.
8. Every successful numeric operation uses a frozen image and `AEC_DEVICE_OP_ISA_LAUNCH`.
9. Work in one Stream is FIFO; different Streams have no implicit ordering.
10. Async launch metadata and argument bytes are owned by the queued work item.
11. Every opaque handle is validated through a live registry before dereference.
12. Destroyed and stale handles return an error without use-after-free.
13. No global registry lock is held while `aecDeviceSubmit` may block.
14. Stats reset does not reset allocations, registrations, sequence, handles, or images.
15. Runtime preflight failures submit no command, retire no instruction, and modify no device bytes.
16. Injected faults are reported once; subsequent legal commands remain usable.

## Requirement matrix

| Requirement | API/capability | Points | Status | Primary implementation | Public test | Custom coverage | Main risk |
|---|---|---:|---|---|---|---|---|
| R101 | Query, error names, TLS error | 4 | PASS verified | `src/aec_runtime.cpp`, `src/error.*` | `cases/test_r101.py` | `tests/test_r101_extra.py` | ABI exception/error consistency |
| R102 | Allocation/free/lifetime | 6 | PASS verified | `src/allocation.*` | `cases/test_r102.py` | `tests/test_r102_extra.py` | pending async free and external device reset |
| R103 | Synchronous H2D/D2H | 6 | PASS verified | `src/command.*`, `src/copy.*`, allocation leases | `cases/test_r103.py` | `tests/test_r103_extra.py` | fault completion validation deferred to R304 |
| R104 | Vector Add fixed image | 4 | PASS verified | `src/kernel.*`, `src/serialization.h` | `cases/test_r104.py` | `tests/test_r104_extra.py`, `test_serialization.cpp` | async integration deferred to R105 |
| R105 | Stream FIFO/async | 5 | PASS verified | `src/stream.*`, queued work in copy/kernel/numeric | `cases/test_r105.py` | `tests/test_r105_extra.py` (20 destroy races) | host buffer lifetime remains caller-owned by contract |
| R106 | Event generations/cycles | 5 | PASS verified | `src/event.*`, Stream markers | `cases/test_r106.py` | `tests/test_r106_extra.py` (20 destroy races) | cross-Stream rerecord ordering |
| R201 | FP32/INT32 GEMM | 10 | PASS verified | `src/numeric.*`, shared kernel path | `cases/test_r201.py` | `tests/test_r201_extra.py`, serialization test | async integration deferred to R105 |
| R202 | FP4/FP8/FP16/BF16/FP64 GEMM | 10 | PASS verified | generic `src/numeric.cpp` path | `cases/test_r202.py` | `tests/test_r202_extra.py` | hidden special-float/rounding breadth |
| R203 | INT4/INT8/INT32 GEMM | 4 | PASS verified | generic `src/numeric.cpp` path | `cases/test_r203.py` | `tests/test_r203_extra.py` | hidden maximum-shape saturation breadth |
| R204 | AXPY/DOT/NRM2 | 6 | PASS verified | `src/library_ops.*` | `cases/test_r204.py` | `tests/test_r204_extra.py`, serialization test | hidden maximum-count reduction breadth |
| R301 | ABI sequence/completion/stats | 6 | PASS verified | `src/command.*`, stats API | `cases/test_r301.py` | `tests/test_r301_extra.py` | sequence exhaustion is theoretical only |
| R302 | Dual DMA/async recovery | 6 | PASS verified | stream-id channel policy | `cases/test_r302.py` | `tests/test_r302_extra.py` | submits serialize for sequence correctness |
| R303 | Host registration/zero-copy | 4 | PASS verified | `src/registration.*`, copy flags | `cases/test_r303.py` | `tests/test_r303_extra.py` | concurrent new normal copy after unregister linearization |
| R304 | Fault propagation/recovery | 4 | PASS verified | command + async error path | `cases/test_r304.py` | `tests/test_r304_extra.py` | hidden ISA-trap PC variants |
| R401 | DMA Agent | 10 | correctness PASS; public diagnostic 1.0 | `agents/dma_agent.py` | `cases/test_r401.py` | `tests/test_agents.py`: 120 brute-force optima | hidden speedup profile unavailable |
| R402 | Kernel Agent | 10 | correctness PASS; public diagnostic 1.0 | `agents/kernel_agent.py` | `cases/test_r402.py` | 80 official-evaluator optima | hidden candidate distribution unavailable |

## Milestones

- [x] Audit repository instructions, specs, scoring, public ABI, device ABI, ISA, docs, starter source, public tests, manifests, examples, and Agents.
- [x] Verify Linux toolchain, endian, repository state, device artifact, and immutable hashes.
- [x] Run and archive the unmodified-source public baseline.
- [x] R101 hardening and custom TLS tests; regress baseline pass.
- [x] R102 allocation registry and synchronous lifetime tests; async free-waits coverage remains attached to R105.
- [x] R103 synchronous DMA, process sequence, and unified completion/status handling.
- [x] Stats-reset invariants and command-accounting tests.
- [x] R104 Vector Add fixed-image launch and serialization tests.
- [x] R201 FP32/INT32 GEMM and Basic gate report (`44/100`, Basic).
- [x] R105 Stream FIFO, async DMA/launch, handle tombstones, error recovery, and pending allocation lifetime.
- [x] R106 Event generation, virtual-cycle markers, tombstones, and latest-generation tests.
- [x] R202 floating multi-dtype GEMM, FP4 odd tail, format validation, and async coverage.
- [x] R203 packed integer GEMM, odd nibble tail, async INT8, and INT32 output-span tests.
- [x] R204 fixed-image vector library operations, layouts, aliases, async, and preflight tests.
- [x] Dedicated R301 command/stat/reset/preflight audit.
- [x] Dedicated R302 four-Stream/channel/error-recovery audit.
- [x] Dedicated R304 DMA/kernel/next-command one-shot fault and recovery audit.
- [x] R303 registration, zero-copy flags, interval boundaries, and pending unregister.
- [x] Good gate clean full regression (`88/100`, Good, 16/16 public cases).
- [x] R401/R402 valid generalized policies, invalid-input handling, purity, determinism, and policy tests.
- [x] Agent public/model virtual-cycle optimization after all correctness requirements passed; hidden performance remains unverifiable.
- [ ] Final clean build, all examples, all public cases, symbols, ELF/dependencies, immutable audit, documentation, and review audit.

## Baseline

The original starter source builds once the exact official device library is
present. `R101` passes. `R102-R106`, `R201-R204`, and `R301-R304` return
`AEC_ERROR_NOT_SUPPORTED`. Both baseline Agents receive only their 4-point
correctness portions. Public score: `12/100`, level `Not passed`.

Evidence: `reports/baseline_public_report.json` and `TEST_REPORT.md`.

## Current blockers and next step

There is no active implementation blocker. The checkout omission of the device
library was resolved from an exact-hash official artifact. The missing `file`
utility affects only one inspection command; `readelf`, `nm`, and `ldd` provide
the required ELF evidence.

Next: perform ABI visibility hardening, sanitizer/concurrency regression, immutable
hash audit, final clean build, and complete implementation/review documentation.
