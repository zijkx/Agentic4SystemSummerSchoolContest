# C2 Morning Brief

## Current state

Audit and baseline are complete on the formal remote Linux host. The official
device library was absent from Git but an exact manifest-hash copy already on the
server was verified and restored. R101 has now been hardened and independently
verified with official and custom TLS/error tests.

Public score is 78/100, level Basic. R101-R106 and R201-R203 pass with focused
custom coverage. R301/R302/R304 pass publicly but still need dedicated audits.
The vector library and registration APIs remain explicit stubs.

## Where to review

1. `IMPLEMENTATION_PLAN.md` for the requirement matrix and invariants.
2. `TEST_REPORT.md` for reproducible environment/baseline evidence.
3. `PROGRESS.md` for the chronological log.
4. `reports/baseline_public_report.json` for the raw grader result.

## Next action

Implement R204 AXPY, DOT, and NRM2 using their 28/32/24-byte canonical parameter
blocks, fixed images, FP32 span/count checks, output overlap rules, and async
Stream execution.

## Risks

- Hidden tests are expected to stress overflow, stale handles, pending async
  lifetimes, Event rerecording, and fault recovery beyond the public cases.
- `lib/libaec_device.so` is ignored and must be supplied alongside the workspace
  for every clean formal build.
- The host does not provide `file`; use `readelf` plus `ldd` for ELF evidence.
