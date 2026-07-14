# C2 Independent Compliance Audit Follow-up

Audit date: 2026-07-14 (Asia/Shanghai)

## 1. Executive verdict

- Verdict: `PASS_WITH_RISKS`
- Candidate commit: `9f07ad001639b8408927b02d4f838218bae61cb7`
- Original audit commit: `631f2a7`
- Official current commit: `b2997a228d9446ff254cb324225b731df66c7546`
- Highest unresolved severity: `LOW`
- Open CRITICAL findings: 0
- Open HIGH findings: 0
- Public score from pristine grader: 88/100, Good
- Basic gate: true
- Good gate: true
- Agent correctness: R401 and R402 both pass with diagnostic 1.0
- Hidden performance: not awarded by the public profile
- Safe to submit: `YES`, as the strict three-file artifact only

The original audit's F-001, F-002, F-004, and F-005 are resolved. F-003 is
rejected because it was based on an incorrect reading of an immutable official
schema. No new compliance or correctness finding was identified in the
remediation diff.

## 2. Scope and baselines

The follow-up audited detached clean worktree `9f07ad0` rather than the mutable
development tree. The official reference was a separate clone at `b2997a2`.
The candidate worktree was clean before the audit and clean again after
`make clean`.

The complete protected set was compared with `diff -qr`, including C2 spec and
scoring, headers, device library, all 34 fixed images, kernel manifest, grader,
cases, golden data, schemas, examples, release manifest, and official docs.
Every protected path was byte-identical to official `b2997a2`.

The controlled device SHA-256 in both trees is:

```text
b96b09e88ae160b659cf72bd079da8bc647d2bc55d377297a649d77c30ddcb0a
```

## 3. Finding disposition

| ID | Original severity | Status | Evidence | Conclusion |
|---|---|---|---|---|
| F-001 | HIGH | RESOLVED | `starter-kit/src/stream.cpp:24-27`; TSan | The worker starts in the constructor body after all members are initialized. Five fixed-SHA non-PIE TSan executions completed without a race report. |
| F-002 | HIGH | RESOLVED | `starter-kit/Makefile:22-30`; `readelf -d`; strict grader | `libaec.so` has no device `DT_NEEDED` and no RUNPATH. Examples explicitly link the development device. The exact three-file artifact loads through the pristine grader. |
| F-003 | MEDIUM | REJECTED | official `schemas/dma_agent_input.schema.json:17-20` | The official schema has `concurrency.maximum = 64`; input 65 is invalid. The Agent's upper bound is required. |
| F-004 | MEDIUM | RESOLVED | `agents/kernel_agent.py:244-251`; `tests/test_agents.py` | Any string ID, including `""`, is accepted and round-tripped. Agent schema/correctness tests pass. |
| F-005 | LOW | RESOLVED | `tests/test_kernel_agent_optimality.py:203-214` | The custom p99 guardrail is 250 ms, with fourfold margin under the official 1 s timeout. Fixed-SHA run: median 15.625 ms, p99 20.649 ms. |

## 4. Build, ELF, and ABI

The clean worktree built successfully under a minimal environment:

```bash
env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 make clean
env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 make -j2
env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 make examples
```

All six examples then exited 0. `nm -D --defined-only` reported the complete 36
function `aec_runtime.h` surface plus the `AEC_2` version node. There are no
unexpected participant exports.

`readelf -d libaec.so` reported only platform runtime dependencies:

```text
libstdc++.so.6
libgcc_s.so.1
libc.so.6
ld-linux-x86-64.so.2
```

There is no RPATH/RUNPATH and no `DT_NEEDED` for `libaec_device.so`. The seven
undefined `aecDevice*` ABI symbols used by the Runtime are intentionally resolved
from the organizer library loaded by the grader with `RTLD_GLOBAL`. This exact
contract was tested from a directory with no device library.

## 5. Pristine grader and boundary results

| Verification | Result |
|---|---|
| Fresh official public grader, strict three-file directory | Exit 0; 88/100 Good; every R101-R402 requirement PASS |
| Fresh official `cases/run_all.py`, strict directory | 16/16 passed |
| Immutable audit | 73 manifest files, 34 images, official static diff clean |
| Agent focused suite | 120 DMA optima and 80 Kernel evaluator optima passed |
| Kernel certificate suite | 5,570,560 oracle-call certificate, 550 subset/permutation cases, 1,000 deterministic processes passed |
| Maximum DOT/NRM2 | Both passed count 1,048,576 without ISA trap |
| Maximum GEMM | All ten dtypes passed at M=N=K=256 |
| Stream/fault stress | R105/R106/R302/R303/R304 passed 50 rounds each, 250 processes total |
| ASan+UBSan public grader | Exit 0 with both sanitizers configured to halt on error |
| TSan Stream/Event | Five complete fixed-SHA runs had no race report |

The public score remains 88 because the published grader assigns zero hidden
performance points by construction. It does not indicate a failed public Agent
case: both Agent correctness components score 4/4 and both diagnostics are 1.0.

## 6. Integrity and anti-cheating follow-up

The remediation changed only participant-owned Runtime source, Makefile, Kernel
Agent validation, custom tests, the Agent certificate SHA, and participant
documentation. It did not modify headers, schemas, grader, cases, golden data,
device code, images, manifests, examples, spec, scoring, or official docs.

The remediation introduced no Host-side numerical computation, fallback result
path, case-ID lookup, input hash/file-name special case, stats fabrication,
custom image, loader interposition, network access, persistent Agent state, or
candidate construction. The original audit's forced execution path and
anti-cheating findings therefore remain valid.

The strict submission inventory was exactly:

```text
libaec.so
agents/dma_agent.py
agents/kernel_agent.py
```

It contained no symlink, device file, setup script, official device library,
secret, absolute development path, or undeclared third-party dependency.

## 7. Residual risks

1. The public profile cannot execute or award hidden Agent performance. The DMA
   policy is the public formula optimum and the Kernel policy has a complete
   public-domain oracle certificate, but only the organizer can report the
   formal hidden score and Excellent gate.
2. GCC ThreadSanitizer on this host intermittently aborts before program startup
   with `unexpected memory mapping`. Five non-PIE invocations completed fully
   without a race report; ASan+UBSan and 250 process-level stress cases passed.
3. The artifact relies on the grader's documented and observed `RTLD_GLOBAL`
   preload of the controlled device ABI. This is required by the official
   three-file submission layout and was verified with the pristine grader.

## 8. Final recommendation

Submit the three-file artifact built from `9f07ad0` after one final SHA and
inventory check. Do not include `libaec_device.so`, fixed images, audit evidence,
source trees, or build outputs in the scoring directory. No unresolved finding
requires an implementation change before submission.
