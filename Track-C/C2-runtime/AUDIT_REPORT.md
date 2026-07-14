# C2 Independent Compliance Audit

Audit date: 2026-07-14 (Asia/Shanghai)

## 1. Executive verdict

- Verdict: **FAIL**
- Highest severity: **HIGH**
- Critical findings: **0**
- High findings: **2**
- Medium findings: **2**
- Low findings: **1**
- Public score from pristine grader: **88/100, Good**
- Basic gate: **PASS**
- Good gate: **PASS**
- Excellent correctness: **R401 and R402 correctness PASS**
- Performance status: public diagnostics are 1.0; hidden performance is unavailable
- Safe to submit: **NO**

The implementation is not cheating and its starter-kit test surface is strong,
but the exact audited commit is not submission-ready. A construction-time data
race exists on every Stream worker start, and the canonical three-file
submission cannot load because `libaec.so` has an unsatisfied
`libaec_device.so` dependency. Both are HIGH findings. Two Agent validators also
reject inputs accepted by the official schemas. No implementation was changed
during this audit.

## 2. Baselines

- Candidate repository: `/home/mig19/c2/Agentic4SystemSummerSchoolContest`
- Candidate branch: `codex/c2-device-library-update`
- Candidate HEAD: `a4c3a47610147e93fc1d7db731ac7c0576d01e1a`
- Uncommitted changes at audit start: none
- DEVELOPMENT_BASE_SHA: `d985a6e9f910891835530b835b850ae8282f32f7`
- OFFICIAL_CURRENT_SHA: `b2997a228d9446ff254cb324225b731df66c7546`
- Baseline confidence: HIGH
- Independent official clone: `/tmp/a4s-official-c2-audit-20260714-a4c3a47`
- Detached clean candidate: `/tmp/c2-candidate-clean-a4c3a47`
- Detached sanitizer candidate: `/tmp/c2-candidate-sanitize-a4c3a47`

The development base is the Git merge-base between candidate HEAD and a fresh
fetch of official `main`. Protected-file compliance is evaluated against the
official current SHA so the organizer's `c30b3f9` device update is not
misclassified as a participant modification.

Evidence: `AUDIT_EVIDENCE/current_git_state.txt`,
`official_git_state.txt`, and `baselines.txt`.

## 3. Official requirements reviewed

- Root `README.md`
- `Track-C/README.md`
- `Track-C/C2-runtime/spec.md`
- `Track-C/C2-runtime/scoring.md`
- Starter `README.md` and all six official C2 documents
- `include/aec_runtime.h`, `aec_device_abi.h`, and `aec_isa.h`
- `RELEASE_MANIFEST.json` and `kernels/manifest.json`
- Agent input/output schemas
- Official public grader, case wrappers, manifests, examples, and golden data
- Repository `AGENTS.md` and required repository audit documents

## 4. Complete changed-file inventory

The complete per-file ledger contains all 96 paths changed since
`DEVELOPMENT_BASE_SHA`:

- `AUDIT_EVIDENCE/changed_file_inventory.md`
- `AUDIT_EVIDENCE/changed_file_inventory.tsv`
- `AUDIT_EVIDENCE/full_committed_diff.patch`

| Classification | Files | Allowed? | Severity | Explanation |
|---|---:|---|---|---|
| Participant runtime | 24 | Yes | None | `src/` and Makefile implementation |
| Participant Agents | 2 | Yes | None | R401/R402 programs |
| Participant tests | 20 | Yes | None | Additional non-official tests |
| Offline participant tools | 2 | Yes | None | Pre-submission Kernel oracle tools |
| Participant evidence | 27 | Yes | None | Reports and artifact inspection |
| Participant documentation | 7 | Yes | None | Plans, implementation, progress, review |
| Repository governance | 12 | Yes | None | Root `AGENTS.md` and audit docs outside scored artifact |
| Official update | 2 | Official sync | None | Device library and release manifest match official current byte-for-byte |

No grader, case, golden, schema, public header, fixed image, example, official
document, spec, or scoring file differs from official current.

## 5. Protected-file integrity

The audit hashed 82 protected files independently in the candidate and fresh
official checkout. The normalized SHA-256 lists have a zero-line diff.

| Path | Official baseline | Candidate | Match? | Verdict |
|---|---|---|---|---|
| `spec.md`, `scoring.md` | Official current hashes | Same | Yes | PASS |
| `starter-kit/include/` | Official current hashes | Same | Yes | PASS |
| `starter-kit/lib/libaec_device.so` | `b96b09e8...cb0a` | `b96b09e8...cb0a` | Yes | PASS |
| `starter-kit/kernels/images/` | 34 official images | 34 identical images | Yes | PASS |
| Kernel manifest | Official current hash | Same | Yes | PASS |
| Grader and cases | Official current hashes | Same | Yes | PASS |
| Golden and schemas | Official current hashes | Same | Yes | PASS |
| Examples and official docs | Official current hashes | Same | Yes | PASS |
| `RELEASE_MANIFEST.json` | Official current hash | Same | Yes | PASS |

Evidence: `official_protected.sha256`, `candidate_protected.sha256`,
`protected_hash_diff.txt`, and `protected_integrity_summary.txt`.

## 6. Anti-cheating findings

| ID | Severity | File:line | Evidence | Rule | Impact |
|---|---|---|---|---|---|
| AC-01 | None | Protected paths | Zero protected hash diff | Official components immutable | No grader/device/image tampering |
| AC-02 | None | `src/kernel.cpp`, `numeric.cpp`, `library_ops.cpp` | Forced path and Host-compute scans | Numeric results must execute fixed images | Resolve, canonical parameters, ISA submit; no Host arithmetic fallback |
| AC-03 | None | Agent files | `case_id` appears only in required-field/type validation | No case-ID specialization | Policy is case-ID independent |
| AC-04 | None | Runtime and Agent sources | Environment/bypass scan | No network, loader hijack, process spawning, or hidden-file reads | No bypass path found |
| AC-05 | None | `IMPLEMENTATION.md:354` | Provenance scan | LLM and third-party disclosure | Codex assistance is disclosed; no third-party implementation found |

The oracle collector calls `aecDeviceEvaluateKernel` only as an offline
pre-submission tool. `agents/kernel_agent.py` does not import `ctypes`, load the
device library, read files, use subprocesses, or access a network. The oracle
tools are not part of the three-file scored artifact.

Raw scans: `hardcoding_scan_full.txt`, `environment_bypass_scan.txt`,
`host_compute_scan.txt`, `cross_track_dependency_scan.txt`,
`provenance_scan.txt`, and `absolute_path_secret_scan.txt`.

## 7. Forced execution path proof

| API family | Resolve fixed image | Canonical params | ISA submit | No Host compute | Evidence |
|---|---|---|---|---|---|
| `aecLaunch` Vector Add | Yes | 32-byte LE | Yes | Yes | `kernel.cpp:54-109,112-137,141-223` |
| All GEMM APIs | Yes | 40-byte LE | Yes | Yes | `numeric.cpp:70-137,151-185`; `aec_runtime.cpp:153-225` |
| AXPY | Yes | 28-byte LE | Yes | Yes | `library_ops.cpp:45-72,132-151` |
| DOT | Yes | 32-byte LE | Yes | Yes | `library_ops.cpp:74-107,153-162` |
| NRM2 | Yes | 24-byte LE | Yes | Yes | `library_ops.cpp:109-130,164-173` |
| Device submission | N/A | Command ABI v2 | `aecDeviceSubmit` | N/A | `command.cpp:24-55` |

The only loops in Runtime source are little-endian serialization, Stream worker
management, and registry destruction. The only `memcpy` calls read ABI fields,
copy canonical command parameters, or mirror device stats. There is no Host
GEMM, AXPY, DOT, NRM2, fallback, output synthesis, or counter fabrication.

Evidence: `forced_execution_path_symbols.txt`, the numbered source files, and
`host_compute_scan.txt`.

## 8. ABI and build reproducibility

- Clean build: PASS
- Offline/minimal-environment build: PASS
- Six examples: PASS
- ELF: little-endian ELF64 x86-64 shared object, proven by `readelf`/`objdump`
- Exported symbols: 36/36 official Runtime functions; zero diff
- Dependencies: standard C/C++ runtime plus `libaec_device.so`
- RUNPATH: `$ORIGIN/lib` only
- Absolute paths in `libaec.so`: none
- Undisclosed source/dependencies: none found
- `file` utility: unavailable; equivalent ELF tools passed

The minimal environment was `env -i` with only HOME, PATH, and LANG restored.
The clean build did not use cached objects or an existing `libaec.so`.

Finding F-002 qualifies this section: the `libaec_device.so` dependency is
resolved inside starter-kit but not in the required three-file submission.

Evidence: `minimal_environment_build.log`, `clean_examples.log`,
`libaec_readelf.txt`, `libaec_objdump.txt`, `libaec_nm_*`,
`runtime_symbol_diff.txt`, `libaec_ldd.txt`, `abi_summary.txt`, and
`dynamic_link_submission_contract.txt`.

## 9. Pristine grader results

The grader and wrappers below came from the independent official checkout, not
the candidate repository.

| Requirement | Exit | Score | Result | Notes |
|---|---:|---:|---|---|
| R101 | 0 | 4/4 | PASS | Query/error/TLS |
| R102 | 0 | 6/6 | PASS | Allocation lifecycle |
| R103 | 0 | 6/6 | PASS | Synchronous DMA/bounds |
| R104 | 0 | 4/4 | PASS | Vector fixed image |
| R105 | 0 | 5/5 | PASS | Stream public FIFO |
| R106 | 0 | 5/5 | PASS | Events/errors |
| R201 | 0 | 10/10 | PASS | FP32/INT32 GEMM |
| R202 | 0 | 10/10 | PASS | Floating formats |
| R203 | 0 | 4/4 | PASS | Packed integer GEMM |
| R204 | 0 | 6/6 | PASS | Vector/reductions |
| R301 | 0 | 6/6 | PASS | Command/stats |
| R302 | 0 | 6/6 | PASS | Two DMA channels |
| R303 | 0 | 4/4 | PASS | Registration/zero-copy |
| R304 | 0 | 4/4 | PASS | Fault/recovery |
| R401 | 0 | 4/10 | PASS correctness | Public diagnostic 1.0; hidden unavailable |
| R402 | 0 | 4/10 | PASS correctness | Public diagnostic 1.0; hidden unavailable |

Aggregate: 88/100, Good; Basic and Good gates true; public Excellent false.

Evidence: `pristine_public_report.json`, `pristine_public_grader.log`, and
`pristine_official_cases.log`.

## 10. Hidden-test risk assessment

| Area | Evidence | Risk | Recommended test |
|---|---|---|---|
| Stream construction | TSan reproducible race | HIGH | TSan standalone create/destroy after F-001 fix |
| Canonical submission loading | Official grader exits 2 | HIGH | Grade exact three-file directory after F-002 fix |
| DMA Agent schema maximum | `concurrency=65` exits 2 though schema accepts it | MEDIUM | Boundary/property tests above 64 |
| Kernel empty candidate ID | Empty string exits 2 though schemas accept it | MEDIUM | Empty/escaped/duplicate-ID schema tests |
| Kernel latency assertion | Clean runs measured 21.474 and 22.096 ms | LOW | Separate benchmark from official 1 s correctness timeout |
| Maximum GEMM shape | All 10 dtypes passed at 256 cubed | LOW residual | Seeded nonzero maximum-shape tests if time permits |
| Special floating point | Device-owned path; focused custom coverage | LOW residual | NaN/Inf/subnormal/signed-zero vectors |
| Cross-Stream Event ordering | Code review and stress pass | LOW residual | Additional randomized rerecord schedules |

## 11. Stream/Event/lifetime review

- Lock order: registry then record; Stream/Event registry lookup releases before
  state mutex; submit mutex is not nested with registries.
- Handle validation: live registries plus process-lifetime tombstone shells.
- Destroy behavior: removes handle before draining/joining.
- Pending references: allocation and registration leases survive queued work.
- Async error propagation: first error is reported/cleared; worker continues.
- Identified races: **F-001**, worker starts before later StreamState members are
  initialized.

Fifty repetitions of R105, R106, R302, R303, and R304 custom scripts passed
(250 script executions), as did ASan+UBSan. This does not neutralize a
standards-level race confirmed by TSan.

Evidence: `concurrency_stress_50x.log`, `asan_ubsan_build.log`,
`asan_ubsan_tests.log`, `tsan_tests.log`, and
`tsan_standalone_stream.log`.

## 12. Agent review

- DMA Agent: cycle-model choices are optimal for tested actions; F-003 adds an
  unsupported `concurrency <= 64` input restriction.
- Kernel Agent: full-domain official-oracle certificate has zero regret; F-004
  rejects an empty candidate ID allowed by both schemas.
- Case-ID independence: PASS; IDs are validated but not used in policy.
- Stdout purity: PASS for valid/invalid tests.
- Offline behavior: PASS; no external state, files, network, device oracle, or
  subprocess in submitted Agent.
- Candidate legality: PASS for official candidates and tested subsets.
- Performance heuristic legitimacy: PASS; generated from published read-only
  evaluator across the full contract shape domain.

The Kernel self-test's 20 ms p99 requirement passed in the development tree but
failed twice in the clean audit tree at 21.474 and 22.096 ms. The official
timeout remains 1,000 ms, so this is F-005 (LOW), not an R402 scoring failure.

Evidence: `candidate_custom_tests.log`,
`candidate_custom_tests_remaining.log`, `kernel_agent_latency_rerun.log`,
`agent_schema_boundary_failures.txt`, and the numbered Agent sources.

## 13. Submission compliance

- Required files: exactly three regular files were assembled; no symlinks.
- Reproducible source: PASS inside starter-kit.
- LLM disclosure: PASS in `IMPLEMENTATION.md`.
- Third-party disclosure: no third-party implementation or dependency found.
- Offline operation: Runtime/Agents are offline.
- Secrets/artifacts scan: no secret, URL, or absolute path in the three files.
- Official device distinction: explicit; device hash matches organizer current.
- Canonical package execution: **FAIL** due F-002.

The exact three-file directory was:

```text
submission/
|-- libaec.so
`-- agents/
    |-- dma_agent.py
    `-- kernel_agent.py
```

Independent official grader result: exit 2,
`libaec_device.so: cannot open shared object file`. No JSON report was produced.

Evidence: `minimal_submission_inventory.txt`,
`minimal_submission_grader_retry.log`, `minimal_submission_secret_scan.txt`,
and `dynamic_link_submission_contract.txt`.

## 14. Findings ordered by severity

### F-001: Stream worker observes partially initialized state

- Severity: HIGH
- Location: `starter-kit/src/stream.cpp:24-25,72,108-116`
- Evidence: TSan reports a read of `stop_` in the worker racing with constructor
  initialization. The report reproduced in both Python tests and a standalone
  TSan-linked C example.
- Rule: Stream lifecycle must be race-free; C++ object members cannot be read
  before lifetime initialization completes.
- Impact: undefined behavior on Stream creation; possible intermittent hidden
  concurrency failures.

### F-002: Required three-file artifact cannot load

- Severity: HIGH
- Location: `starter-kit/Makefile:22-24`
- Evidence: `libaec.so` records `NEEDED libaec_device.so`; the official device
  has no matching SONAME; official guide permits only three participant files;
  pristine grader on that directory exits 2.
- Rule: submitted artifact must run offline without undeclared/omitted files.
- Impact: canonical submission can fail before any requirement executes.

### F-003: DMA Agent rejects schema-valid concurrency

- Severity: MEDIUM
- Location: `starter-kit/agents/dma_agent.py:13-15,31`
- Evidence: official schema specifies minimum 1 and no maximum; concurrency 65
  exits 2.
- Rule: valid schema inputs must produce one legal action.
- Impact: potential R401 correctness loss and Excellent-gate failure.

### F-004: Kernel Agent rejects schema-valid empty candidate ID

- Severity: MEDIUM
- Location: `starter-kit/agents/kernel_agent.py:244-251`
- Evidence: input/output schemas require only string type, with no `minLength`;
  a legal naive candidate with ID `""` exits 2.
- Rule: output must select an ID present in the supplied legal candidates.
- Impact: potential R402 correctness loss and Excellent-gate failure.

### F-005: Self-imposed 20 ms p99 gate is unstable

- Severity: LOW
- Location: `starter-kit/tests/test_kernel_agent_optimality.py:203-209` and
  performance claims in participant documentation.
- Evidence: clean worktree failed twice at 21.474 and 22.096 ms; official limit
  is 1,000 ms.
- Rule: do not claim a benchmark gate as stable without reproducible margin.
- Impact: flaky custom regression/documentation, not formal score loss.

## 15. Exact commands and evidence paths

Principal commands:

```bash
git clone https://github.com/ephonic/Agentic4SystemSummerSchoolContest.git \
  /tmp/a4s-official-c2-audit-20260714-a4c3a47
git worktree add --detach /tmp/c2-candidate-clean-a4c3a47 a4c3a47
env -i HOME="$HOME" PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 make -j2
python3 <official>/grader/public_grade.py --submission <candidate> --profile public
for t in <official>/cases/test_r*.py; do python3 "$t" --submission <candidate>; done
python3 tests/test_*.py --submission .
readelf -h -d -Ws libaec.so
nm -D --defined-only libaec.so
ldd libaec.so
```

Every raw output is under `Track-C/C2-runtime/AUDIT_EVIDENCE/`. The key files
are named directly in the relevant sections. `evidence_manifest.sha256` pins
the final evidence set.

## 16. Final recommendation

Do not package or submit commit `a4c3a47` as-is. Fix F-001 and F-002 first and
repeat the clean official-grader, minimal-submission, TSan, sanitizer, and
50-round stress checks. Fix F-003 and F-004 before claiming both Agent
correctness gates across the official schemas. Reword or redesign F-005 so a
wall-clock development target cannot make an otherwise valid correctness suite
flaky.

After remediation, create a new immutable candidate commit and perform a short
follow-up audit against that exact commit before producing the final archive.
