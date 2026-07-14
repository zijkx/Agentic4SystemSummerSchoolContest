# C2 Morning Brief

## Current state

Implementation and updated-device review are complete on the formal remote
Linux host. The final clean build is warning-free; all six examples, 16/16
public cases, 18/18 custom Python scripts, and standalone
serialization passed.

Public score is 88/100, level Good, with Basic and Good gates true. Every
released correctness requirement passes. R101-R304 have focused boundary,
lifetime, concurrency, accounting, serialization, and fault-recovery coverage.

Both Agents now pass correctness with public performance diagnostic 1.0. The
DMA policy matched 120 brute-force optima and the Kernel policy matched 80
official evaluator optima. Public score remains 88/100 because public Agent
performance is diagnostic only; hidden Excellent evidence is unavailable.

All public `aecLaunch` Kernel IDs work. ASan+UBSan found and drove a fix for
invalid C enum handling; the repeated sanitizer suite is clean. The final ELF
is little-endian x86-64 with 36 public C functions plus `AEC_2`, and every
dependency resolves.

Official upstream commit `c30b3f9` updated only the device library and release
manifest. The old DOT 90,909 trap was reproduced; the new library passes DOT and
NRM2 at count 1,048,576 without traps. The immutable audit passes 73 manifest
files and all 34 images. The current device library hash is
`b96b09e88ae160b659cf72bd079da8bc647d2bc55d377297a649d77c30ddcb0a`.

## Where to review

1. `IMPLEMENTATION_PLAN.md` for the requirement matrix and invariants.
2. `IMPLEMENTATION.md` for architecture, flows, layouts, locks, and lifetimes.
3. `REVIEW_GUIDE.md` for the requirement/function/commit map and review questions.
4. `TEST_REPORT.md` for exact commands, artifacts, and residual risks.
5. `reports/device_update_public_report.json` for the current machine-readable grader result.

## Handoff

Review the official-device update on branch `codex/c2-device-library-update`.

## Risks

- Hidden maximum-shape GEMM, special-float, and cross-Stream Event cases may
  exceed the released public/custom coverage.
- The official device library is force-tracked despite the global `*.so` ignore.
- Hidden Agent speedup and the Excellent gate are unavailable and unclaimed.
- The host does not provide `file`; `readelf`, `objdump`, and `ldd` evidence passed.
