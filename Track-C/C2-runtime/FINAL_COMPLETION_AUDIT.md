# C2 Final Goal Completion Audit

Audit date: 2026-07-14 (Asia/Shanghai)

## 1. Verdict

- Verdict: `PASS_WITH_RISKS`
- Safe to submit: `YES`
- Scoring-source commit: `049e8967dff4fbd1353b239298399a30b72f124e`
- Kernel implementation commit: `dc59a3f3ece954a4aba74abcec27bed863d86522`
- Official reference commit: `b2997a228d9446ff254cb324225b731df66c7546`
- Highest unresolved severity: `LOW`
- Open CRITICAL findings: 0
- Open HIGH findings: 0
- Pristine public score: 88/100, Good
- Basic gate: true
- Good gate: true
- R401/R402 correctness: pass, public diagnostics 1.0
- Hidden Agent performance: unavailable in the published profile

The two requested tasks and the final packaging workflow are complete. The only
unverifiable item is the organizer-only hidden Agent performance award; no local
result is presented as formal hidden 10/10 evidence.

## 2. Kernel full-score plan audit

| Acceptance criterion | Evidence | Result |
|---|---|---|
| AC-1 Oracle trust | Official device SHA `b96b09e...cb0a`; 100-call determinism, failed-input gating, and byte-identical stats before/after collection in `kernel_oracle_summary.json` | PASS |
| AC-2 Complete domain | 10 dtypes, complete `[1,256]^3` legality partition, 5,570,560 evaluator calls, 167,772,160 represented dtype/shape points | PASS |
| AC-3 Zero regret | Zero dominance violations, zero mismatch, argmin accuracy 1.0, max regret 0 | PASS |
| AC-4 Protocol/legality | 550 subset/permutation cases, arbitrary and empty IDs, raw malformed JSON negatives, Unicode, stable tie-break, 500-request old/new differential | PASS |
| AC-5 Offline Agent | Static certificate rejects forbidden imports/calls/text; submitted Agent reads no files, device library, grader, network, or subprocess | PASS |
| AC-6 Runtime | Five development-tree p99 trials 17.401-19.050 ms and three detached clean-commit ext4 trials 17.309-17.359 ms; all use 1,000 processes | PASS |
| AC-7 Regression | R402 diagnostic 1.0, pristine 16/16, custom suite, serialization, immutable audit, max reductions, and ten max-shape GEMMs | PASS |
| AC-8 Reproducible evidence | Oracle/policy/latency/public JSON reports contain device, Agent, model, call-count, mismatch, regret, and public-score evidence | PASS |

The final Agent is 5,854 bytes with SHA-256:

```text
610378d3d770374b3d2106b7499e967f4bd4724b9a4b75aa0d7f5b3135e8e7ed
```

It uses a strict structural parser plus CPython's standard `_json` string
scan/encode primitives. Duplicate keys, malformed integer syntax, trailing
data, invalid literals, malformed Unicode, isolated surrogates, extra fields,
wrong types, duplicate IDs, and no-legal-candidate inputs all fail without
stdout/stderr output.

A 45,199-byte request containing 300 legal candidates completed 200 times with
median 21.330 ms, p99 24.848 ms, and max 26.093 ms, far below the official
one-second timeout. During a separate host-load incident, an empty Python Agent
itself exceeded 20 ms p99; those overlay/high-load measurements are retained as
environment diagnostics and are not counted as acceptance evidence.

## 3. Independent correctness/compliance audit

The original read-only audit is commit `631f2a7`; remediation is `9f07ad0`; its
follow-up is `c10af9f`. The final incremental audit additionally checked
`dc59a3f` and the packaged source at `049e896`.

| Area | Final evidence | Result |
|---|---|---|
| Protected contracts | Spec, scoring, headers, device library, 34 images, manifests, grader, cases, golden, schemas, examples, and official docs byte-identical to official `b2997a2` | PASS |
| Device integrity | Candidate and official device SHA both `b96b09e...cb0a` | PASS |
| Anti-cheating | No Host numerical result path, case/hash/file-name lookup, custom image, stats fabrication, loader interposition, network, or hidden-file access | PASS |
| Fixed execution path | Runtime validation -> fixed image resolve -> canonical little-endian params -> official ISA submit -> completion/status | PASS |
| Stream race | Worker starts after complete member initialization; sanitizer and repeated concurrency evidence clean | PASS |
| Three-file loading | Runtime has no device `DT_NEEDED` or RUNPATH; pristine grader supplies the official ABI with `RTLD_GLOBAL` | PASS |
| ABI | 36 required C functions plus `AEC_2`; no unexpected participant exports | PASS |
| Build reproducibility | Clean minimal-environment build and all six examples pass | PASS |
| Sanitizers/stress | ASan+UBSan pristine grader clean; successful TSan runs clean; five concurrency/fault requirements passed 50 rounds each | PASS_WITH_ENV_NOTE |

Original F-001, F-002, F-004, and F-005 are resolved. Original F-003 remains
rejected: official `dma_agent_input.schema.json` explicitly sets concurrency
maximum 64, so 65 is not schema-valid.

## 4. Final artifact audit

The scoring directory contains exactly:

```text
libaec.so
agents/dma_agent.py
agents/kernel_agent.py
```

There are no symlinks, device files, setup scripts, caches, metadata files, or
organizer libraries. Final SHA-256 values are:

```text
e91303d2b20626b769f080a4f620406e126809491ad36250b0929d84c2d60835  libaec.so
ad313f6341d29c20db6d7d62efd69ea76f53b92e256aa634ce62f64f469c0e94  agents/dma_agent.py
610378d3d770374b3d2106b7499e967f4bd4724b9a4b75aa0d7f5b3135e8e7ed  agents/kernel_agent.py
```

`libaec.so` is an x86-64 little-endian ELF shared object. Its dynamic section
has no RPATH/RUNPATH and no `libaec_device.so` `DT_NEEDED`. The pristine official
grader and all official case wrappers both pass 16/16 against this exact
three-file directory.

The requested local backup was re-inventoried after removing Finder metadata;
it contains exactly the same three regular files and the same hashes.

## 5. Key commands

```bash
python3 tools/kernel_policy_generate.py --submission .
python3 tests/test_kernel_agent_optimality.py --submission .
python3 tests/test_agents.py --submission .
make clean && make -j2 && make examples
python3 <official>/grader/public_grade.py --submission <three-file-dir> --profile public
python3 <official>/cases/run_all.py --submission <three-file-dir>
readelf -d <three-file-dir>/libaec.so
nm -D --defined-only <three-file-dir>/libaec.so
sha256sum <three-file-dir>/libaec.so <three-file-dir>/agents/*.py
```

## 6. Residual risks

1. Only the organizer full profile can award and report hidden Agent performance
   and the Excellent gate. The submitted policy is oracle-optimal over the
   complete published domain, but the undisclosed case mix controls the formal
   performance points.
2. The latency implementation uses CPython's bundled `_json` accelerator,
   verified in the contest's current CPython environment. A non-CPython Python
   implementation would require revalidation, although the published grader
   and formal host both use CPython.
3. TSan on this host intermittently fails before startup with an address-mapping
   error. Completed non-PIE runs, ASan+UBSan, and process stress found no race.

## 7. Recommendation

Submit the audited three-file directory. Do not add the device library, fixed
images, reports, source tree, `.DS_Store`, or any other file to the scoring
artifact. No remaining implementation or compliance issue blocks submission.
