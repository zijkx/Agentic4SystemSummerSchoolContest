# Project Overview

## Objective and scope

The repository defines the 2026 Agentic4Systems GPGPU contest. Track C requires a three-person team to deliver the software stack above the AEC GPGPU: a compiler (C1), a host runtime (C2), and ONNX graph scheduling/deployment (C3). The root overview and normalization rule are in `README.md`; Track C's relationship and navigation are in `Track-C/README.md`.

This audit establishes a reproducible baseline and agent rules. It deliberately does not implement the three submissions because the current tree lacks complete build/runtime prerequisites, because correctness contracts must be understood before optimization, and because broad simultaneous implementation would obscure whether failures are caused by environment, missing release artifacts, or participant code.

## Position in the stack

| Subproblem | Stack position | Input | Output / submission |
|---|---|---|---|
| C1 compiler | Front end through target code generation | PTX-style text IR | `aec-cc` produces an AEC binary with header/code/data/relocation/symbol sections; `aec-objdump` disassembles it. See `Track-C/C1-compiler/spec.md`. |
| C2 runtime | Host API and controlled virtual-device bridge | Calls to the C ABI in `aec_runtime.h`, fixed kernel images, optional Agent JSON | Linux `libaec.so`; optional `agents/dma_agent.py` and `agents/kernel_agent.py`. See `Track-C/C2-runtime/spec.md` and `starter-kit/docs/06_提交与公开测试指南.md`. |
| C3 scheduler | Graph/runtime layer above kernels | ONNX opset-17 models and manifest-described NumPy tensors | C3.1 DAG JSON; C3.5 output manifest plus FP32 `logits.npy`; source, run instructions, and two command templates. See `Track-C/C3-scheduler/spec.md`. |

The three tasks are conceptually adjacent but evaluation does not establish a source-level dependency between them. `Track-C/README.md` says they are independently scored and equally averaged. C1 refers to the precise ISA in `Track-B/spec.md`; C2 uses its own frozen images and device ABI; C3 defines abstract hardware/kernel selection but the released tree contains no integration with C1 or C2.

## Scoring and independence

Each subproblem is worth 100 raw points and Track C is `(C1 + C2 + C3) / 3`; see `README.md` and `Track-C/README.md`. Their build entry points, tests, and deliverables are separate:

- C1: correctness 50, generated-code efficiency 35, robustness 5, optimization Agent 10 (`Track-C/C1-compiler/scoring.md`). Correctness gates cycle scoring.
- C2: Runtime 30, compute library 30, virtual driver 20, Agents 20 (`Track-C/C2-runtime/scoring.md` and the more precise requirement table in `starter-kit/docs/05_Agent与评分标准.md`).
- C3: graph parsing 10, decomposition 15, fusion 15, memory/scheduling 10, end-to-end 50 (`Track-C/C3-scheduler/scoring.md`). C3.5 accuracy is a gate; time and peak VRAM are ranking components.

No C1 submission layout beyond the two required CLI tools and output format is stated. C2's final artifact directory contains `libaec.so` and optionally two Agent scripts. C3 requires source/build/run instructions and command templates; archive limits and deadlines are deferred to the contest platform. These omissions must not be guessed.

## Why baseline comes first

The contest is only two days. Correctness gates C1 performance and C3.5 scoring, while C2 requirements are mostly all-or-zero and tier-gated. The fastest reliable route is therefore: make a minimal legal artifact, run one narrow public requirement, preserve every pass, then add the next scoring capability. Performance work before a repeatable baseline risks optimizing invalid output or an unavailable platform.

## Recommended agent isolation

Create `worktree-c1`, `worktree-c2`, and `worktree-c3` from a common audited commit and assign one Codex Goal to each. C1 can be developed on macOS but must regress in Linux; C2 should build and test in the exact Linux architecture matching the missing device library; C3 can do graph work in a Python virtual environment but needs a remote NVIDIA Linux host for C3.5/NVML performance. Share findings through committed audit/progress documents, not concurrent edits to one worktree.

Before starting Goals, obtain the omitted C2 device library, clarify the formal Linux CPU architecture, and provision a Python 3.10+ environment plus an NVIDIA test host. Starting broad implementation now would mix these hard blockers with ordinary code defects and make overnight results unreliable.
