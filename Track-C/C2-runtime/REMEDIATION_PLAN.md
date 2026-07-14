# C2 Audit Remediation Plan

This plan is advisory. The independent audit did not modify implementation
files.

| Finding ID | Severity | Required change | Files likely affected | Regression tests | Must fix before submission? |
|---|---|---|---|---|---|
| F-001 | HIGH | Do not start the Stream worker in a member initializer. Default-construct `worker_`, finish initialization of every state member, then assign/start the thread in the constructor body. Preserve exception safety and join behavior. | `starter-kit/src/stream.cpp`; add a focused Stream-construction stress test | Standalone TSan Stream example; R105/R106/R302/R303/R304; ASan+UBSan; 50-round stress; official grader | Yes |
| F-002 | HIGH | Make the participant `libaec.so` load after the grader preloads the official device without requiring a fourth file in the submission. A likely implementation is leaving `aecDevice*` references unresolved in the shared library and adjusting only example linking; verify the exact loader contract rather than assuming. Do not embed an absolute path or copy the device into the submission. | `starter-kit/Makefile` | `readelf -d` shows no unsatisfied package-local device dependency; exact three-file directory passes pristine official grader; examples still build/run; all ABI checks | Yes |
| F-003 | MEDIUM | Remove the undocumented maximum of 64 from DMA `concurrency` validation. Any schema-valid positive integer must produce the same model-optimal depth once concurrency is at least 2. | `starter-kit/agents/dma_agent.py`, Agent tests | concurrency 64/65/large integer; schema/purity; R401; DMA brute-force/model checks | Yes for Excellent |
| F-004 | MEDIUM | Accept every candidate ID allowed by the input schema, including the empty string, and emit it with the existing JSON string encoder. Decide duplicate-ID behavior from the contract and add an explicit test rather than silently strengthening the schema. | `starter-kit/agents/kernel_agent.py`, Agent tests | Empty/escaped/Unicode IDs; candidate subsets/order; R402; full-domain certificate hash/Agent hash regeneration | Yes for Excellent |
| F-005 | LOW | Separate formal one-second protocol timeout from a non-scoring 20 ms benchmark. Either optimize with reproducible margin or report the measurement without making the full correctness suite fail on scheduler jitter. Correct documentation to reflect repeated clean-worktree data. | `tests/test_kernel_agent_optimality.py`, `IMPLEMENTATION*.md`, `TEST_REPORT.md`, `PROGRESS.md`, reports as needed | Repeated 1,000-run measurements in clean worktree; official R402 timeout; full custom suite | Recommended |

## Required remediation order

1. Fix F-001 and run TSan first; a clean TSan run may expose additional races
   previously hidden behind the constructor race.
2. Fix F-002 and prove the exact three-file package works with the pristine
   official grader.
3. Fix F-003 and F-004, then rerun both Agent correctness and policy-optimality
   suites.
4. Resolve F-005 without weakening the official one-second protocol check.
5. Rebuild from a clean commit, rerun every official/custom test, regenerate
   ELF/evidence reports, and follow up the audit against the remediated SHA.

## Acceptance criteria

- No TSan race from a standalone Stream create/use/destroy program.
- ASan+UBSan and 50-round concurrency stress remain clean.
- The exact three-file submission passes the independent official grader.
- Protected-file hashes remain byte-identical to official current.
- `concurrency=65` and a Kernel candidate ID of `""` both return legal JSON.
- R401/R402 public diagnostics remain 1.0 and the Kernel oracle certificate
  remains zero-regret.
- Minimal-environment clean build, 36/36 exports, and all 16 official cases pass.
