# C2 Execution Plan

This is the long-running execution entry point required by the repository
instructions. The authoritative requirement matrix and milestone checklist are
in `IMPLEMENTATION_PLAN.md`.

## Delivery sequence

1. Audit and baseline.
2. Basic correctness: R101-R104 and R201.
3. Good correctness: R105-R106, R202-R204, and R301-R304.
4. Excellent Agent correctness: R401-R402.
5. Agent virtual-cycle tuning only after all Runtime correctness passes.
6. Clean final regression, artifact inspection, immutable audit, and review docs.

For every requirement: implement one coherent capability, build on remote Linux,
run the narrow case, regress prior passes, run the public grader, inspect the
diff, update `PROGRESS.md` and `TEST_REPORT.md`, then create a focused commit.

## Completion gates

A requirement is complete only when its public case passes, prior passes do not
regress, the required device evidence is present, custom boundary/lifetime tests
pass, exported symbols and ELF remain valid, immutable contracts are unchanged,
and the exact commands/results are recorded.

## Status

All six delivery stages, the official-device update, and the independent-audit
remediation are complete. Final evidence is in `TEST_REPORT.md`,
`reports/device_update_public_report.json`, and the audit/follow-up reports.
The official `c30b3f9` device update is included, maximum-length DOT/NRM2 passes
without traps, and a strict three-file submission passes every public
requirement. The final Kernel parser passes the original process-level p99 below
20 ms gate in five development-tree trials and three detached clean-commit ext4
trials. Hidden Agent performance is outside the released profile and remains
unclaimed.
