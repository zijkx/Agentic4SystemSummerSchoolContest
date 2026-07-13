# Environment Report

Audit date: 2026-07-13 (Asia/Shanghai). Repository commit: `87a99a5c544c0d67282144fe2eda488f5049a287`. No packages or system settings were changed.

## Host and resources

| Item | Observed result |
|---|---|
| OS/kernel | macOS 14.5 (23F79), Darwin 23.5.0, arm64 |
| Endianness | little-endian |
| CPU/memory | 8 logical CPUs, 24 GiB RAM |
| Repository filesystem | 460 GiB total, 86 GiB available, 80% used |
| C1 stated minimum | Exactly 8 CPUs and more than 16 GB; host resource capacity meets it, but OS/ABI does not reproduce Docker evaluation |
| Concurrency assessment | Three source worktrees are inexpensive; three concurrent containers/builds plus C3 models can pressure 24 GiB and the 86 GiB free disk. Stagger heavy jobs. |

`/etc/os-release`, `nproc`, and `free` are not applicable/installed on macOS; `sw_vers` and `sysctl` supplied the equivalent facts.

## Toolchain

| Tool | Path/version | Assessment |
|---|---|---|
| Git | `/usr/bin/git`, 2.39.5 Apple Git-154 | Available |
| GNU Make | `/usr/bin/make`, 3.81 | Available; old but C2 Makefile syntax is basic |
| CMake / Ninja | Missing | Not currently required by checked-in code; likely useful for new C1/C3 build design |
| Apple clang/clang++ | `/usr/bin/clang`, 16.0.0, target arm64-apple-darwin | C++17 test succeeded |
| `gcc` / `g++` | Apple clang aliases, not GNU GCC 13.3 | Does not match stated formal GCC environment |
| Link/binutils | Apple `ld`, `ar`, LLVM `objdump`, `nm`, `otool`; no `readelf` | Mach-O inspection available, Linux ELF inspection absent |
| Default Python | `/usr/bin/python3` -> CommandLineTools Python 3.9.6 | Below required Python 3.10+ |
| Alternate Python | `/opt/homebrew/bin/python3.13`, 3.13.9 | Version sufficient, but package compatibility must be pinned/tested |

Both Python installations are global/non-venv and have none of NumPy, ONNX, ONNX Runtime, PyTorch, protobuf, pytest, jsonschema, or pynvml. `pip check` reports no broken installed requirements because these packages are simply absent. The repository declares no `requirements.txt`, `pyproject.toml`, Conda file, or lockfile.

## Docker and Linux ABI

Docker CLI 29.1.3, Buildx, and Compose 5.0.1 are installed. `docker info` failed because Docker Desktop's socket does not exist; the daemon is not running. Per task boundary it was not started. The repository has no Dockerfile or Compose configuration, so no Linux image was built or run.

A C++17 shared-library probe using the C2-style `-fPIC -shared` flags succeeded, but `file` and `otool` identified the result as an `arm64` Mach-O `DYLIB`. A `.so` suffix does not change this. The macOS host therefore cannot directly produce the Linux ELF `libaec.so` required by C2. A Linux container/host is required.

The required `Track-C/C2-runtime/starter-kit/lib/libaec_device.so` is absent. Although `RELEASE_MANIFEST.json` names it, neither the file nor a Git object exists in `HEAD`; `.gitignore` excludes all `.so`. A read-only hash audit verified the other 84/85 manifest entries and found no mismatches, isolating the release-integrity problem to this one missing file. Its ELF bitness, machine architecture, and dependencies are unknowable from current evidence. Do not assert it is x86-64. Once obtained, run `file`, `readelf -h/-d`, and `sha256sum`; if it is x86-64 ELF, an arm64 Linux container still cannot load it natively and `--platform linux/amd64` or an x86-64 host is required. Emulation may significantly slow builds/tests.

## GPU, CUDA, and NVML

`nvidia-smi` and `nvcc` are absent. PyTorch is absent, so CUDA availability could not be queried through it. The Mac has no NVIDIA CUDA/NVML stack available to the audited environment. Apple GPU/MPS is not CUDA and cannot satisfy the stated NVML per-process VRAM measurement. Docker Desktop on macOS cannot expose an NVIDIA GPU that the host does not have.

C3 graph parsing, shape inference, DAG serialization, planning, fusion logic, CPU reference checks, and manifest handling can be developed locally after installing Python dependencies in an isolated venv. Formal GPU execution, NVML peak memory, and performance ranking require a remote NVIDIA Linux machine.

## Feasibility matrix

| Item | C1 | C2 | C3 |
|---|---|---|---|
| Read/modify source | Yes (new implementation needed) | Yes | Yes (new implementation needed) |
| Build on host | Partial: future compiler can build, no starter exists | No formal artifact; only Mach-O possible and device lib missing | Partial: Python code can run after venv/deps |
| Build in Docker now | No: daemon stopped and no Dockerfile | No: same, plus device lib missing/architecture unknown | No: daemon stopped and no Dockerfile |
| Run public correctness tests | No executable public grader | No; build blocked before grader | Partial data inspection only; executable tests/participant code absent |
| Run public performance tests | No Cycle Model | No build; Agent diagnostics alone are not full performance | No NVIDIA/NVML and cited benchmark absent |
| Reproduce formal evaluation | No | No | No |
| Main missing items | Implementation, validator/Golden/Cycle models, Linux regression | Fixed device `.so`, Linux matching architecture, implementation | Python deps/implementation, C3.2/C3.3 benchmark, NVIDIA/NVML |
| Recommended location | Host development + Linux Docker/final server | Linux host/container matching device library | Mac venv for graph work + remote NVIDIA Linux |
| Blocker severity | P1 | P0 | P0 for C3.5; P1 for C3.1 |

Overall classification: **C1 partially meets**, because development resources/toolchain are adequate but there is no implementation/test oracle and no formal Linux run. **C2 does not meet**, because a mandatory binary is missing and macOS cannot produce/load the final Linux artifact. **C3 partially meets**, because source/data work is possible but dependencies, released benchmarks, participant code, CUDA, and NVML are absent.

## Missing dependency record

| Missing | Needed by | Why | Isolated recommendation | System-level change |
|---|---|---|---|---|
| Official `libaec_device.so` | C2 | Mandatory Make prerequisite and controlled execution backend | Obtain exact release artifact; verify manifest hash before placing under `starter-kit/lib/` | No, repository artifact |
| Python 3.10+ venv packages: NumPy, ONNX, ONNX Runtime and/or PyTorch, protobuf; pytest if tests use it | C3 | Parse models, arrays, CPU reference/inference/testing | `python3.13 -m venv .venv` then install a reviewed, pinned lockfile; Python 3.11/3.12 may have broader wheel support than 3.13 | No if venv used; network/download required |
| NVIDIA driver/CUDA/NVML | C3.5 | Required GPU execution and peak-memory measurement | Use a pre-provisioned remote NVIDIA Linux host/container; do not install on this Mac | Remote host only |
| Running Docker Desktop + reviewed Linux image | C1/C2/C3 CPU work | Linux ELF and closer ABI | User starts daemon; create a minimal pinned Dockerfile only after device architecture is known | Docker images consume local disk, no macOS system package install |
| GNU GCC 13.3 and Linux binutils | Formal C1/C2 compatibility | Match stated environment and inspect ELF | Install inside pinned container, not macOS host | Container-local |
