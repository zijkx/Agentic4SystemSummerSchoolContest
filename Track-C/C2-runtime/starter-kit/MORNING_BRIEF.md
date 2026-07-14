# C2 Morning Brief

## Current state

Implementation, official-device review, and independent-audit remediation are
complete on the formal remote Linux host. The release build is warning-free;
all six examples, 16/16 public cases, focused custom tests, standalone
serialization, maximum reductions, and maximum-shape GEMMs passed.

Public score is 88/100, level Good, with Basic and Good gates true. Every
released correctness requirement passes. R101-R304 have focused boundary,
lifetime, concurrency, accounting, serialization, and fault-recovery coverage.

Both Agents pass correctness with public performance diagnostic 1.0. The DMA
policy matched 120 brute-force optima. The Kernel policy now has a full-domain
certificate: 5,570,560 official evaluator calls over all 10 dtypes produced
zero dominance violations, zero mismatches, 100% argmin accuracy, and zero
regret. Candidate subset/permutation tests and 1,000-run determinism passed. The
final 5,854-byte parser passed five development-tree trials at p99
17.401-19.050 ms and three detached clean-commit ext4 trials at p99
17.309-17.359 ms, satisfying the original 20 ms gate. Public score remains
88/100 because public Agent performance is diagnostic only; hidden Excellent
evidence is unavailable.

All public `aecLaunch` Kernel IDs work. ASan+UBSan and successful non-PIE TSan
runs are clean. The final ELF is little-endian x86-64 with 36 public C functions
plus `AEC_2`. It intentionally has no device `DT_NEEDED` or development RUNPATH:
the official grader supplies `libaec_device.so` with `RTLD_GLOBAL` before
loading the three-file submission.

Official upstream commit `c30b3f9` updated only the device library and release
manifest. The old DOT 90,909 trap was reproduced; the new library passes DOT and
NRM2 at count 1,048,576 without traps. The immutable audit passes 73 manifest
files and all 34 images. The current device library hash is
`b96b09e88ae160b659cf72bd079da8bc647d2bc55d377297a649d77c30ddcb0a`.

The independent audit is preserved at commit `631f2a7`. Its Stream constructor
race, strict-package loading failure, and empty candidate-ID rejection are
fixed. A later completion audit replaced the temporary 250 ms latency workaround
with a compact parser that passes the original 20 ms gate. The DMA
`concurrency=65` finding was a false positive because the immutable schema sets
a maximum of 64. A strict three-file directory passes the fresh official grader,
and five concurrency/fault requirements passed 50 rounds each after remediation.

## Where to review

1. `IMPLEMENTATION_PLAN.md` for the requirement matrix and invariants.
2. `IMPLEMENTATION.md` for architecture, flows, layouts, locks, and lifetimes.
3. `REVIEW_GUIDE.md` for the requirement/function/commit map and review questions.
4. `TEST_REPORT.md` for exact commands, artifacts, and residual risks.
5. `reports/device_update_public_report.json` for the current machine-readable grader result.
6. `reports/kernel_oracle_summary.json` and
   `reports/kernel_policy_report.json` for the Kernel full-domain certificate.
7. `reports/kernel_ac6_latency_report.json` for the final latency gate evidence.

## Handoff

Review the official-device update on branch `codex/c2-device-library-update`.

## Risks

- Hidden maximum-shape GEMM, special-float, and cross-Stream Event cases may
  exceed the released public/custom coverage.
- The official device library is force-tracked despite the global `*.so` ignore.
- Hidden Agent speedup and the Excellent gate are unavailable and unclaimed.
- Some oracle-optimal small tiled shapes have less than 1.5x speedup, so exact
  hidden R402 performance points still depend on the organizer's case mix.
- The host does not provide `file`; `readelf`, `objdump`, and `ldd` evidence passed.
- GCC TSan intermittently fails before startup with `unexpected memory mapping`;
  three complete non-PIE instrumented runs were clean.
