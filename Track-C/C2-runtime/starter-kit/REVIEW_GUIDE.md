# C2 Runtime Review Guide

## Recommended reading order

1. `IMPLEMENTATION_PLAN.md`: environment, frozen contracts, requirement status, and invariants.
2. `IMPLEMENTATION.md`: architecture, flows, parameter layouts, lifetimes, locks, and known limits.
3. `src/aec_runtime.cpp`: complete exported ABI and exception boundaries.
4. `src/command.cpp`, `src/allocation.cpp`, `src/registration.cpp`: device boundary and memory lifetime.
5. `src/kernel.cpp`, `src/numeric.cpp`, `src/library_ops.cpp`: fixed-image numeric execution.
6. `src/stream.cpp`, `src/event.cpp`: concurrency and opaque handle lifetimes.
7. `agents/*.py`: policy validation and cost models.
8. `TEST_REPORT.md` and `reports/device_update_public_report.json`: reproducible current evidence.

## File map

| File | Review focus |
|---|---|
| `src/aec_runtime.cpp` | Does every header symbol export? Can exceptions or invalid C enums cross into UB? |
| `src/error.cpp` | Success-preserves-error, Peek/Get, one centralized device mapping. |
| `src/allocation.cpp` | Exact-base free, subtraction span proof, free-waits lease. |
| `src/registration.cpp` | Half-open interval overlap/overflow and unregister-waits lease. |
| `src/command.cpp` | Global sequence, submit serialization, completion/status agreement. |
| `src/copy.cpp` | Direction fields, zero-copy flags, async deferred preflight. |
| `src/kernel.cpp` | Public Kernel ID mapping, exact native args, resolve metadata, command bytes. |
| `src/numeric.cpp` | Dtype storage, integer output sizing, overlap, variant legality. |
| `src/library_ops.cpp` | AXPY alias exception, reduction output overlap, layouts. |
| `src/stream.cpp` | FIFO, shutdown race, final-work lease release, first error recovery. |
| `src/event.cpp` | Reserve/cancel/complete generation and destroy waiting. |
| `agents/dma_agent.py` | Normative formula optimum and strict JSON protocol. |
| `agents/kernel_agent.py` | Candidate-only legality filter and general variant model. |
| `tests/test_immutable.py` | Manifest hashes, fixed-image count, extra/missing files, and initial-commit contract diff. |
| `tests/test_r204_max_length.py` | Historical DOT/NRM2 trap boundaries, maximum count, cycles, and max+1 preflight. |

## Requirement-to-function map

| Requirement | Primary functions |
|---|---|
| R101 | `aecDeviceCount`, `aecDeviceInfo`, `error.cpp::finish/get_last_error/error_name` |
| R102 | `allocation.cpp::allocate_device`, `free_device`, `acquire_device_span` |
| R103 | `copy.cpp::copy_sync`, `command.cpp::submit_dma`, `submit_and_validate_completion` |
| R104 | `kernel.cpp::prepare_vector_add`, `build_isa_command`, `launch` |
| R105 | `stream.cpp::enqueue_stream_work`, `StreamState::worker_loop/synchronize/shutdown` |
| R106 | `event.cpp::event_record`, `EventState::reserve_generation/complete/wait`, elapsed/query |
| R201-R203 | `numeric.cpp::storage_bytes`, `prepare_matmul`, `matmul`, `launch_matmul` |
| R204 | `library_ops.cpp::prepare_axpy/prepare_dot/prepare_nrm2` |
| R301 | `command.cpp::submit_and_validate_completion`, Runtime stats facade |
| R302 | `copy.cpp::copy_async`, Stream ID channel selection and recovery |
| R303 | `registration.cpp::host_register/host_unregister/acquire_registered_span` |
| R304 | submit status mapping plus `StreamState::worker_loop/synchronize` |
| R401 | `agents/dma_agent.py::policy` |
| R402 | `agents/kernel_agent.py::policy` |

## Highest-risk functions

- `allocation.cpp::free_device`: remove-live, wait-pending, then device free.
- `command.cpp::submit_and_validate_completion`: sequence and failure completion agreement.
- `stream.cpp::StreamState::worker_loop`: error retention and last-work lease release.
- `stream.cpp::stream_destroy`: live removal before drain/join.
- `event.cpp::event_record`: generation reservation versus failed Stream enqueue.
- `event.cpp::event_destroy`: closing versus concurrent record and latest wait.
- `registration.cpp::acquire_registered_span`: partial overlap must not receive flags.
- `kernel.cpp::launch`: unaligned native field reads and every public ID mapping.
- `numeric.cpp::prepare_matmul`: packed/input/output byte distinctions and overlap.
- `library_ops.cpp::prepare_axpy`: exact same-span alias allowed, partial alias rejected.

## Invariants to check first

1. No host numeric computation or direct device-pointer dereference exists.
2. All command objects and parameter arrays start zeroed.
3. All successful launches use a resolved nonzero device handle.
4. Sequence assignment occurs immediately before submit under one mutex.
5. Allocation and registration live maps are not held during submit.
6. A queued valid work item owns leases until completion.
7. Destroyed Stream/Event shells cannot be reused as a new handle address.
8. Success never calls TLS clear.
9. Stats are official device counters, not estimated values.
10. Agent output contains only allowed schema fields and candidate IDs.

## Lock order

| Order | Locks | Blocking device call while held? |
|---|---|---|
| 1 | Allocation registry -> allocation record | No |
| 2 | Registration registry -> registration record | No |
| 3 | Stream registry, release, then Stream state | No |
| 4 | Event registry, release, then Event state | No |
| 5 | Event state reservation, release, then Stream enqueue | No |
| 6 | Submit mutex only | Yes, intentionally serializes sequence+submit |

There is no path from a record mutex back to its registry. Lease destruction
takes a record mutex only. Device submit owns no registry/Stream/Event mutex.

## Handle lifetimes

Stream/Event create allocates a shell and state, inserts the shell into a
process-lifetime tombstone vault, then publishes shell->state in a live map.
Destroy removes the live entry before closing/draining. Later calls find the
tombstone address absent from the live map and return invalid handle. State
remains shared only for calls/markers that linearized before destroy.

Allocation/registration handles are address bases rather than host objects.
Their live records are removed before wait, so new work cannot race into a
closing record. Accepted work keeps a pending lease.

## Parameter layouts

| Layout | Wire fields |
|---|---|
| Vector Add 32 | `u64 A,B,C,count` |
| GEMM 40 | `u64 A,B,C; u32 M,N,K,dtype` |
| AXPY 28 | `u64 X,Y,count; f32 alpha bits` |
| DOT 32 | `u64 X,Y,result,count` |
| NRM2 24 | `u64 X,result,count` |

Review `serialization.h` and `tests/test_serialization.cpp` together. Public
native structs for GEMM/AXPY are larger than wire layouts; their padding and
reserved fields must never be copied into command parameters.

## Dtype and storage map

| Dtype | Input bytes/elements | Output bytes/elements |
|---|---:|---:|
| FP4 | ceil(N/2) | ceil(N/2) |
| FP8 E4M3/E5M2 | N | N |
| FP16/BF16 | 2N | 2N |
| FP32 | 4N | 4N |
| FP64 | 8N | 8N |
| INT4 | ceil(N/2) | 4N |
| INT8 | N | 4N |
| INT32 | 4N | 4N |

Runtime dtype enum values are passed in GEMM parameter bytes and resolve calls;
they are not ISA type selector values.

## Stats and fault paths

For a valid command, inspect:

1. Runtime preflight and lease acquisition.
2. Sequence assignment under submit mutex.
3. Device submit return and completion status/sequence/ABI agreement.
4. Stream retention of first error, continued later work, sync return/clear.
5. Device-owned stats and trace evidence.

For an invalid preflight, verify no path reaches submit. For injected faults,
verify the next matching command fails without retired instructions and the
following matching command succeeds.

## Agent cost models

DMA formula has monotonic choices: largest chunk removes chunk penalties, queue
depth 2 reaches the model's maximum parallelism when concurrency permits, and
registered zero-copy always lowers setup. Channel is cycle-neutral and selected
by direction.

Kernel candidates are filtered before ranking. Public diagnostic cycles, when
present on every legal candidate, are authoritative. Hidden-style inputs use
variant rank. The full-domain oracle certificate covers 5,570,560 candidate
evaluations, 2,621,440 multi-candidate shapes, all 10 dtypes, and the complete
`[1,256]^3` shape domain by legality partition. It found zero dominance
violations, zero mismatches, and zero regret. Candidate ID text and `case_id`
are never used for policy decisions.

Review the evidence chain in this order:

1. `tools/kernel_oracle_collect.py`: successful status gating, record hashing,
   isolated dtype workers, stats immutability, and complete loop bounds.
2. `reports/kernel_oracle_summary.json`: exact device hash, ten dtype reports,
   call counts, record digests, dominance, mismatch, and regret.
3. `tools/kernel_policy_generate.py`: certificate validation and static offline
   audit of the submitted Agent.
4. `agents/kernel_agent.py`: legality filtering, diagnostic-cycle path,
   highest-variant path, and stable tie-break.
5. `tests/test_kernel_agent_optimality.py`: candidate subsets/permutations,
   arbitrary IDs, thresholds, invalid inputs, Unicode JSON, determinism, and
   process-level latency.

## Milestone commits

| Commit | Milestone |
|---|---|
| `af32050` | Audit and frozen contracts |
| `7347437` | R101 query/TLS |
| `72893fb` | R102 allocation lifetime |
| `1c3da23` | R103 synchronous DMA |
| `5411e0c` | R104 Vector Add launch |
| `94d8169` | R201 and Basic gate |
| `2ae404a` | R105 Stream FIFO |
| `548e4b9` | R106 Event generations |
| `bede93a` | R202 floating GEMM |
| `f2a8209` | R203 integer GEMM |
| `e96eb23` | R204 vector operations |
| `4f639b4` | R303 registration and Good gate |
| `d613819` | R301 accounting audit |
| `bccda1c` | R302 dual-DMA audit |
| `92946d7` | R304 fault audit |
| `f4b638d` | R401/R402 optimized Agents |
| `d7c2a93` | Full `aecLaunch`, enum UB fix, visibility hardening |
| `c30b3f9` (official upstream) | Updated device library and release manifest |

## Ten questions for manual review

1. Does any successful numeric path avoid `build_isa_command` and official submit?
2. Can any `ptr/bytes` calculation wrap and pass a live-span check?
3. Can `free_device` or `host_unregister` miss a work item accepted before closing?
4. Can concurrent Stream workers submit sequences out of numeric order?
5. Can a stale Stream/Event pointer ever match a newly created shell address?
6. Can Event destroy wait on a generation that failed to enqueue and never completes?
7. Can native struct padding or a nonzero reserved field reach device parameters?
8. Do partial host-registration overlaps ever receive ZERO_COPY incorrectly?
9. Does an injected error stop later FIFO work or remain permanently reported?
10. Do either Agent use case identity, candidate names, or unavailable state?

## Remaining interpretation uncertainties

- Public score cannot exercise hidden Agent performance; model-optimal public evidence is not an Excellent result.
- Full-domain oracle optimality proves no legal candidate can improve the
  submitted Kernel policy. It does not prove the hidden case distribution will
  award a 1.0 average performance fraction.
- The spec requires process-global strict sequence but does not require parallel host submits; this implementation serializes them for correctness.
- Destroy is specified to drain Stream work; only `aecStreamSync` reports queued errors. Stream destroy therefore returns success after drain rather than replaying an unreported worker error.
- Partial overlap with a registered host interval is treated as legal normal DMA because only complete subspans qualify for flags.
- Undersized numeric spans are rejected by Runtime preflight as invalid address rather than intentionally reaching an ISA trap.
- Opaque handle tombstones intentionally trade bounded process-lifetime memory for unambiguous stale-handle rejection.
