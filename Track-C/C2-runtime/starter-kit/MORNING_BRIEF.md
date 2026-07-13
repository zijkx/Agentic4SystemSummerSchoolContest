# C2 Morning Brief

## Current state

Audit and baseline are complete on the formal remote Linux host. The official
device library was absent from Git but an exact manifest-hash copy already on the
server was verified and restored. R101 has now been hardened and independently
verified with official and custom TLS/error tests.

Public score is 44/100, level Basic. R101-R104 and R201 pass with focused custom
coverage; R301 also passes publicly but still needs dedicated completion/fault
coverage. Stream/Event and higher compute-library APIs remain explicit stubs.

## Where to review

1. `IMPLEMENTATION_PLAN.md` for the requirement matrix and invariants.
2. `TEST_REPORT.md` for reproducible environment/baseline evidence.
3. `PROGRESS.md` for the chronological log.
4. `reports/baseline_public_report.json` for the raw grader result.

## Next action

Implement R105 Stream FIFO and connect async DMA plus prepared numeric/launch
work. The key risks are stale handles, destroy/enqueue races, first-error
reporting/recovery, deep-copied launch arguments, and free waiting on queued work.

## Risks

- Hidden tests are expected to stress overflow, stale handles, pending async
  lifetimes, Event rerecording, and fault recovery beyond the public cases.
- `lib/libaec_device.so` is ignored and must be supplied alongside the workspace
  for every clean formal build.
- The host does not provide `file`; use `readelf` plus `ldd` for ELF evidence.
