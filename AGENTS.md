# Track C Development Rules

These rules apply to all work in this repository. Track C consists of three independently built, tested, and scored submissions. Do not assume that code from one subproblem is available to another during evaluation.

## Required reading

Before changing C1, C2, or C3, read the root `README.md`, `Track-C/README.md`, that subproblem's `spec.md` and `scoring.md`, its public tests/data, build files, starter code, and the following audit documents:

- `docs/PROJECT_OVERVIEW.md`
- `docs/REPOSITORY_MAP.md`
- `docs/SCORING_MAP.md`
- `docs/TEST_COMMANDS.md`
- `docs/ENVIRONMENT_REPORT.md`

For C1 also read the precise ISA in `Track-B/spec.md`. For C2, treat `include/`, `kernels/`, `grader/`, `cases/`, `golden/`, `schemas/`, and the supplied device library as immutable contracts. For C3, preserve the documented CLI, JSON, manifest, dtype, shape, and numerical contracts.

## Prohibited actions

- Do not hard-code public case names, IDs, hashes, inputs, or expected outputs.
- Do not modify or weaken specs, graders, tests, reference outputs, fixed images, models, or public ABI headers to manufacture a pass.
- Do not bypass required interfaces or execution paths, and do not use the reference framework as the final implementation.
- Do not claim a test passed unless that exact command completed successfully in the stated environment.
- Do not regress an already passing requirement.
- Do not guess ABI, ISA, binary format, operator, shape, dtype, or numerical semantics without evidence.
- Do not embed user-specific or absolute paths in project code.
- Do not use destructive Git commands or discard another session's changes.
- Do not add undeclared online dependencies; formal evaluation is offline.

## Implementation loop

For each scoring capability: read its contract and tests, implement the smallest coherent change, build, run the narrow target test, run all previously passing regression tests, inspect the diff, and record the exact command and result before moving on. Correctness gates performance work.

If one failure survives three materially different fixes without progress, restore or retain the last known working state, record the blocker and evidence, and switch to another independent scoring item.

## Long-running work

Each C1/C2/C3 worktree should maintain `EXECPLAN.md`, `PROGRESS.md`, `TEST_REPORT.md`, and `MORNING_BRIEF.md`. Record environment, commit, commands, exit status, and known failures. Use separate Git worktrees for concurrent agents; never let multiple agents edit one working tree.

The audited Mac is not the formal Linux/NVIDIA environment. Label results as host, Docker, or remote Linux results. Do not equate Mach-O with ELF, Apple MPS with CUDA/NVML, Docker CLI installation with a running daemon, or one public sample with full coverage.
