# Next Step Plan

## Recommended architecture

Use a hybrid of A and B: macOS worktrees for editing and fast unit tests, a pinned Linux container for C1 and C2 ABI regression, and a remote NVIDIA Linux machine for C3.5. Do not choose an amd64 versus arm64 container until the official C2 device library's ELF architecture is inspected.

### Option A: Mac host plus Linux Docker

Good for C1 compiler development/CLI tests, Linux ELF builds, and C3 graph/CPU reference work. It does not provide NVIDIA GPU/NVML on this Mac. Apple Silicon can run native `linux/arm64`; use `--platform linux/amd64` only if the fixed C2 binary or formal target requires it. Rosetta/QEMU emulation can be substantially slower and is not a performance reference.

Prerequisites: user starts Docker Desktop; a minimal reviewed Dockerfile pins Linux, GCC/G++ 13.3, GNU Make/binutils, Python 3.10+ and locked Python packages. Mount only the relevant worktree and use an external build directory. No repository Dockerfile currently exists.

### Option B: Mac development plus remote NVIDIA Linux

Recommended overall. Sync source, build descriptions, lockfiles, and small tests; do not repeatedly sync generated builds, `.venv`, full result directories, or redundant public model data. Run C3.5 correctness, CUDA/NVML, timing, and peak-VRAM tests remotely. The same host can handle C2 if its CPU architecture matches `libaec_device.so` and C1 final Linux regression.

Use the exact SSH Host alias supplied by the user and its `~/.ssh/config` entry; no default remote host is defined by this repository. Create a project directory below the user-approved remote workspace, use timestamped result directories, and start with `pwd`, `hostname`, tool versions, and `git status`.

### Option C: all development on remote Linux

Use this if the device library is incompatible with Apple Silicon containers, Docker emulation is too slow, or dependency/model transfer dominates iteration. It maximizes environment fidelity but raises the risk of one shared working tree and long-running remote jobs. Retain three remote worktrees and timestamped results.

## Required preflight, in order

1. Obtain the official C2 starter artifact containing `lib/libaec_device.so`. Verify SHA-256 against `RELEASE_MANIFEST.json`, then inspect `file` and `readelf -h -d` before choosing architecture.
2. Obtain organizer clarification/artifacts for C1's public validator/Golden/Cycle models and C3's cited `benchmarks/c32_c33/bench_c32_c33.py`. Absence must remain explicit if they are intentionally private.
3. Start Docker Desktop if local Linux work is desired, then prove `docker info` and a same-architecture Linux hello-world/toolchain probe. No audit result currently establishes Docker execution.
4. Create three Git worktrees from the audited commit. Keep audit docs committed on the common base before branching.
5. Create an isolated C3 Python environment. Prefer a version with available framework wheels (3.11 or 3.12 unless 3.13 compatibility is verified), pin exact versions/hashes, and record `pip check` plus imports.
6. Provision a user-approved remote NVIDIA Linux alias and run read-only OS/CPU/GPU/NVML/disk checks before transferring or launching tests.

## Suggested worktrees and Goals

```bash
git worktree add ../worktree-c1 -b track-c/c1
git worktree add ../worktree-c2 -b track-c/c2
git worktree add ../worktree-c3 -b track-c/c3
```

These commands mutate Git metadata and should run once after the audit-doc commit; they were not run during this audit.

- `worktree-c1`: implement general PTX parser -> IR -> legal O0 binary and objdump first. Run host unit tests, Linux container builds, and official Golden/Cycle tests when obtained.
- `worktree-c2`: do not begin until the device library is restored and architecture-matched. Target the exact Basic gate R101-R104/R201, then Good; Linux only for authoritative builds/tests.
- `worktree-c3`: first implement C3.1 and a CPU FP32 reference path in a pinned venv. Use the remote NVIDIA host for GPU C3.5, then decomposition/fusion/memory optimization.

Each Goal starts by creating `EXECPLAN.md`, `PROGRESS.md`, `TEST_REPORT.md`, and `MORNING_BRIEF.md` in its worktree and following root `AGENTS.md`.

## Minimal tool/dependency set

| Environment | Minimum |
|---|---|
| Linux C1/C2 | little-endian Linux matching device CPU, GCC/G++ 13.3, GNU Make, binutils (`readelf`, `nm`, `objdump`), Python 3.10+, Git |
| C3 graph/CPU | isolated Python 3.10+ (prefer compatible 3.11/3.12), NumPy, ONNX, protobuf, one reviewed CPU reference runtime (ONNX Runtime or PyTorch), pytest if used |
| C3 GPU | NVIDIA driver, CUDA-compatible framework, NVML tooling/binding, same pinned Python dependencies |

Exact Python versions cannot responsibly be selected because the repository provides no dependency declaration. Establish them by testing all three public opset-17 models, then commit a lockfile. Do not modify system Python.

Potential environment variables should be few and documented: `PATH` for built CLIs, `LD_LIBRARY_PATH` only if unavoidable for local C2 development (prefer RPATH as the starter Makefile does), and framework-specific deterministic settings during reference validation. Never store absolute user paths in code.

## One-command checks to add after setup

Create repository scripts only in the implementation phase after review. Their intended behavior is:

```text
scripts/check-env.sh       print OS/arch/tool/dependency/device facts and fail on required mismatches
scripts/baseline-c1.sh     clean build, PTX-01 compile, structural validation, objdump
scripts/baseline-c2.sh     device hash/ELF check, build, examples, R101 then Basic suite
scripts/baseline-c3.sh     imports, three ONNX parse checks, one-sample CPU reference; GPU section only when detected
```

They must be offline, relative-path based, non-destructive, and preserve complete logs with exit codes.

## Residual risks

Even after setup, C1 formal binary semantics cannot be proven without the official models, C2 may bind to only one Linux CPU architecture, C3 performance is rank-based, and public models/cases do not cover hidden mutations. A clean offline rebuild in the final architecture remains mandatory before submission.
