# C2 Morning Brief

## Current state

Audit and baseline are complete on the formal remote Linux host. The official
device library was absent from Git but an exact manifest-hash copy already on the
server was verified and restored. R101 has now been hardened and independently
verified with official and custom TLS/error tests.

Public score is 34/100: R101-R104, a public R301 pass, and 4 correctness points
from each legal baseline Agent. R301 still needs dedicated completion/fault
coverage before final completion. Stream/Event and compute-library APIs remain
explicit stubs.

## Where to review

1. `IMPLEMENTATION_PLAN.md` for the requirement matrix and invariants.
2. `TEST_REPORT.md` for reproducible environment/baseline evidence.
3. `PROGRESS.md` for the chronological log.
4. `reports/baseline_public_report.json` for the raw grader result.

## Next action

Generalize the prepared fixed-image launch for R201 FP32 and INT32 GEMM: checked
storage sizes, non-overlap, exact 40-byte parameters, typed resolve, and numeric
evidence. Passing R201 will close the Basic gate.

## Risks

- Hidden tests are expected to stress overflow, stale handles, pending async
  lifetimes, Event rerecording, and fault recovery beyond the public cases.
- `lib/libaec_device.so` is ignored and must be supplied alongside the workspace
  for every clean formal build.
- The host does not provide `file`; use `readelf` plus `ldd` for ELF evidence.
