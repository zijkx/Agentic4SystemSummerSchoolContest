# C2 Morning Brief

## Current state

Audit and baseline are complete on the formal remote Linux host. The official
device library was absent from Git but an exact manifest-hash copy already on the
server was verified and restored. R101 has now been hardened and independently
verified with official and custom TLS/error tests.

Public score is 64/100, level Basic. R101-R106 and R201 pass with focused custom
coverage. R301/R302/R304 pass publicly but still need dedicated audits. Higher
compute-library and registration APIs remain explicit stubs.

## Where to review

1. `IMPLEMENTATION_PLAN.md` for the requirement matrix and invariants.
2. `TEST_REPORT.md` for reproducible environment/baseline evidence.
3. `PROGRESS.md` for the chronological log.
4. `reports/baseline_public_report.json` for the raw grader result.

## Next action

Connect the already generic checked-storage GEMM path to FP4, both FP8 formats,
FP16, BF16, and FP64 for R202. Then add INT4/INT8 public APIs and packed-tail
tests for R203.

## Risks

- Hidden tests are expected to stress overflow, stale handles, pending async
  lifetimes, Event rerecording, and fault recovery beyond the public cases.
- `lib/libaec_device.so` is ignored and must be supplied alongside the workspace
  for every clean formal build.
- The host does not provide `file`; use `readelf` plus `ldd` for ELF evidence.
