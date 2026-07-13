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
