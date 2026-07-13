# Scoring Map

Track C score is the equal average of three independent 100-point raw scores (`README.md`, `Track-C/README.md`). Priorities below reflect dependency and score reliability, not implementation effort alone.

## C1 compiler

| Scoring module | Points | Corresponding tests/grader | Required capability | Prerequisite | Difficulty | Hidden-test risk | Priority |
|---|---:|---|---|---|---|---|---|
| T1 correctness | part of 50 across 20 cases | Hidden binary validator + Golden Model; five public PTX files have no runner | Parse PTX, lower basic integer/FP/memory/control instructions, emit complete legal binary | CLI, binary writer, ISA encoder | High | Syntax, parameters, names, bounds | P0 |
| T2 correctness + performance | correctness share + 5 | 20 hidden cases, Cycle Model | CFG/SSA, predicate/control lowering, constant propagation, DCE/CSE/LICM | T1 correctness | High | Block reorder, loop changes, dead insertion | P1 |
| T3 correctness + performance | correctness share + 9 | 20 hidden cases, Cycle Model | Memory lowering, coalescing, load reuse/shared-memory promotion | T1 plus memory semantics | High | Address/reuse changes | P1 |
| T4 correctness + performance | correctness share + 10 | 20 hidden cases, Cycle Model | <=256-register allocation, spill, DDG/list scheduling, dual issue | Broad correct lowering | High | Increased pressure/dependencies | P1 |
| T5 correctness + performance | correctness share + 11 | 20 hidden cases, Cycle Model | TMUL/tensor load-store, tiling, nine dtypes and boundary shapes | Correct binary + numeric/ISA semantics | High | Nonmultiples of 16, dtype/shape mutation | P2 |
| Robustness | 5 | 50 generated mutations | General algorithms independent of public identity/structure | Correct T1-T5 | High | All listed renaming/reordering/type mutations | P1 |
| Optimization Agent | 10 | Hidden performance loop | Read report, recompile with adjusted config, validate, report; >=1.25x gets 8 performance points | Stable optimized compiler and report interface | High | Unpublished workloads/report harness | P3 |

The spec does not assign the 50 correctness points among individual classes, so no per-class correctness value should be invented. Minimum submit-capable means both required CLIs exist and emit/inspect a structurally valid binary; a meaningful lowest-score target is general T1 correctness. There are no named Basic/Good/Excellent C1 tiers. High-return sequencing is legal binary + T1, then reusable CFG/register infrastructure; optimization and Agent work only follow correctness. TMUL/multi-dtype and Agent tuning can consume large time with uncertain return.

## C2 runtime

The exact requirement weights and tier gates come from `starter-kit/docs/05_Agent与评分标准.md`, which is more precise than the summary `scoring.md`.

| Module | Points | Public test | Required capability | Prerequisite | Difficulty | Hidden-test risk | Priority |
|---|---:|---|---|---|---|---|---|
| R101 | 4 | `cases/test_r101.py` | Device/ISA metadata, error names, TLS last error | Load controlled device library | Low | Thread isolation, invalid inputs | P0 |
| R102 | 6 | `test_r102.py` | Allocation/free, OOM, reuse, invalid/double free | Allocation bookkeeping | Medium | Span/lifetime boundaries | P0 |
| R103 | 6 | `test_r103.py` | Sync H2D/D2H and allocation-relative bounds | R102, device submit | Medium | Offset/overflow/zero sizes | P0 |
| R104 | 4 | `test_r104.py` | Vector image resolve, canonical params, ISA launch/evidence | R102-R103, image manifest | High | launch dimensions/parameter rejection | P0 |
| R105 | 5 | `test_r105.py` | Stream FIFO and async operations | Correct sync path | High | concurrency/lifetime | P1 |
| R106 | 5 | `test_r106.py` | Event generations/cycles/async errors | R105 | High | reuse and fault ordering | P1 |
| R201 | 10 | `test_r201.py` | FP32/INT32 GEMM via fixed images | Memory + launch | High | shapes, saturation, evidence | P0 |
| R202 | 10 | `test_r202.py` | FP4/FP8/FP16/BF16/FP64 formats | R201 generic GEMM path | High | encoding/rounding/overflow | P1 |
| R203 | 4 | `test_r203.py` | Packed INT4/INT8 and saturated INT32 output | R201 | High | packing/tails/overflow | P1 |
| R204 | 6 | `test_r204.py` | AXPY, DOT, NRM2 | Generic vector launch | Medium | reduction order/numerics | P1 |
| R301 | 6 | `test_r301.py` | Exact ABI sequence, completion, stats | Sync DMA + launch | Medium | accounting and failed commands | P1 |
| R302 | 6 | `test_r302.py` | Two DMA channels, async bounds/recovery | Streams/fault handling | High | race/fault recovery | P1 |
| R303 | 4 | `test_r303.py` | Host registration and zero-copy cycle benefit | DMA path | Medium | exact range/lifecycle | P1 |
| R304 | 4 | `test_r304.py` | DMA/ISA fault propagation and recovery | Unified reset/error model | High | injected trap sequencing | P1 |
| R401 | 10 | `test_r401.py` diagnostics | Legal DMA Agent; hidden virtual-cycle speedup | Good tier | Medium | unseen sizes/alignment/concurrency | P3 |
| R402 | 10 | `test_r402.py` diagnostics | Legal candidate-only image Agent; hidden speedup | Good tier | Medium | constraints/workspace/shapes | P3 |

Tier thresholds are exact: Basic requires >=30 and all R101-R104 plus R201 (these gates total 30); Good requires >=75, Basic, and all R105-R106/R202-R204/R301-R304 (all non-Agent requirements total 80); Excellent requires >=90, Good, both Agent correctness checks, and positive hidden average speedup for both Agents. A legal minimum artifact exports every `aec_runtime.h` symbol, returning `AEC_ERROR_NOT_SUPPORTED` for unimplemented higher tiers. The high-return route is exactly the 30-point Basic gate. Do not tune Agents before Good; two legal Agents without hidden speedup cap the documented score at 88/Good.

## C3 scheduler

| Module | Points | Corresponding test/review | Required capability | Prerequisite | Difficulty | Hidden-test risk | Priority |
|---|---:|---|---|---|---|---|---|
| C3.1 model load | 4 | Automatic CLI check | Read arbitrary provided ONNX path | Python/ONNX parser | Low | Hidden weights/names/dynamic N | P0 |
| C3.1 graph parse | 6 | DAG JSON automatic check | Inputs excluding initializers, outputs, nodes, tensor edges, valid JSON/exit 0 | Model load | Medium | unnamed nodes, attributes, symbolic shapes | P0 |
| C3.2 decomposition | 15 | Cited `bench_c32_c33.py` (absent) | Precision routing, complete kernel sequences/intermediates, valid tuning, hardware coverage | Internal graph/hardware abstraction | High | Hidden graph shapes/capabilities | P1 |
| C3.3 fusion | 15 | Same absent benchmark + MockRuntime | Five patterns, fewer launches/buffers, valid/numerically aligned graph | C3.2 execution representation | High | BN pre-folding and pattern variants | P1 |
| C3.4 memory/scheduling | 10 | Code review, five items x2 | Device pool/preload, lifetime reuse, reusable/coalescing pool, staged prefetch, independent compute streams | Executable plan | High | Empty stubs explicitly score zero | P2 |
| C3.5 accuracy gate | 15 | Three public/hidden models | FP32-equivalent output (`allclose` 1e-3); MLP >=98%, ResNet >=85% | All 17 operators and CLI/manifest I/O | High | Hidden weights, arbitrary batch N | P0 |
| C3.5 runtime | 25 | Whole-process timing rank | Fast end-to-end GPU inference | Accuracy gate | High | Relative rank/hardware | P2 |
| C3.5 peak VRAM | 10 | NVML per-process sampling rank | Low peak GPU memory | Accuracy gate | High | Relative rank/process attribution | P2 |

C3.2 subdimensions are five 3-point items: precision routing, kernel sequence, intermediate tracking, tuning validity, and hardware coverage. C3.3 is pattern coverage 5, launch reduction 3, buffer reduction 3, fusion correctness 4. C3.4 levels are 0-3 fail, 4-5 basic, 6-7 good, 8-10 excellent. The only S/A/B/C reference is for combined C3.2+C3.3: >=25 S, 20-24 A, 14-19 B, 8-13 C, below 8 fail.

A minimum submit-capable C3 has legal C3.1 and C3.5 command templates and output formats; the cheapest reliable points are C3.1. A CPU reference inference path is valuable for correctness development but C3.5 explicitly says inference runs on GPU, so it is not evidence of a formal C3.5 pass. Performance and memory ranking must follow all accuracy gates. Premature multi-precision/fusion and low-level scheduling are costly until graph parse and FP32 end-to-end reference behavior are stable.
