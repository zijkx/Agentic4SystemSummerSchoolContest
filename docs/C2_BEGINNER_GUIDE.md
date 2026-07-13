# C2 新手教程：实现 `libaec.so` Host Runtime

> 适用范围：`Track-C/C2-runtime/`。C2 是三题中契约最完整、也最适合按公开 requirement 逐项推进的一题。开始前必须恢复缺失的官方 `starter-kit/lib/libaec_device.so`，并在与其架构匹配的 little-endian Linux 上工作。

## 1. 一句话理解 C2

C2 要实现一个供普通 C/C++ 程序调用的动态库 `libaec.so`。上层程序只调用简单 API，例如分配设备内存、复制数据、启动 kernel；你的 Runtime 在内部检查参数、维护对象生命周期、组织异步队列，再把规范化 command 提交给官方虚拟设备库。

```text
用户程序 / examples / grader
         ↓ C ABI: aecAlloc, aecCopyH2D, aecLaunch ...
      你实现的 libaec.so
         ↓ Device ABI: resolve kernel, submit command, get stats
      官方 libaec_device.so
         ↓
固定 AEC kernel image + 确定性虚拟周期/执行结果
```

这不是 Linux 内核驱动，也不接真实 PCIe/FPGA。设备是确定性的用户态虚拟设备，性能按虚拟周期评分，不按 Mac 或服务器的 wall-clock。

## 2. Runtime 到底解决什么问题

如果没有 Runtime，用户需要知道设备地址格式、command struct、kernel handle、参数块 byte layout、DMA 队列和错误状态。Runtime 把这些细节封装成稳定接口。

例如用户写：

```c
aecDevicePtr d_a;
aecAlloc(&d_a, bytes);
aecCopyH2D(d_a, host_a, bytes);
```

Runtime 要在背后完成：

1. 验证输出指针、大小和溢出；
2. 请求官方 device 分配；
3. 记录这段 allocation 的 base/size/live 状态；
4. 对 copy 验证整个 `[d_a, d_a + bytes)` 属于同一个 live allocation；
5. 生成 ABI version、全局递增 sequence、DMA channel/chunk/flags；
6. 调用 `aecDeviceSubmit`；
7. 把 device status 翻译为 Runtime error；
8. 更新当前 host thread 的 last error。

## 3. 前置知识学习路线

### 3.1 C ABI 与动态库

C ABI 是“编译后的函数怎样被找到和调用”的约定。`aec_runtime.h` 使用 `extern "C"`，避免 C++ name mangling。必须导出头文件声明的全部符号，即使高等级功能暂时返回 `AEC_ERROR_NOT_SUPPORTED`。

理解以下工具与概念：

- Linux ELF `.so` 与 macOS Mach-O `.dylib` 不同；
- `-fPIC` 生成位置无关代码；
- `-shared` 在 Linux 生成 shared object；
- RPATH/`LD_LIBRARY_PATH` 控制运行时找库；
- `nm -D --defined-only libaec.so` 检查导出符号；
- `readelf -h -d` 检查 CPU 架构和动态依赖。

当前 Mac 即使把文件命名成 `.so`，实测仍生成 arm64 Mach-O，不能作为正式提交。

### 3.2 指针、地址区间与整数溢出

`aecDevicePtr` 是 64-bit opaque offset，不是 host pointer，0 非法。不要对它解引用。

安全区间检查不能直接写：

```cpp
if (ptr + bytes <= base + size) { ... }
```

因为加法可能 overflow。应先检查 `bytes <= size`，再用减法形式验证：

```text
ptr >= base
ptr - base <= size
bytes <= size - (ptr - base)
```

而且 span 必须完整落在同一个 live allocation，不能跨越两个相邻 allocation。

### 3.3 生命周期与 handle registry

Stream/Event 对外是 opaque pointer，内部对象必须有明确状态和 live registry。需要理解：

- create：分配对象并注册；
- use：先在 registry 中验证 handle，不能直接信任传入指针；
- destroy：先从 registry 移除，阻止新操作，再等待已有工作，最后释放；
- stale/double destroy：返回 invalid handle，不能 use-after-free。

allocation、registration、Stream、Event 都是生命周期问题。

### 3.4 线程、互斥量、条件变量与 worker

Good 等级需要异步 Stream。至少掌握：

- `std::thread`；
- `std::mutex`、`std::lock_guard`、`std::unique_lock`；
- `std::condition_variable`；
- FIFO queue；
- stop/join；
- 错误如何从 worker 传回 `aecStreamSync`。

不要持有全局锁调用可能阻塞的 device submit，否则不同 Stream 无法并行，destroy 也容易死锁。

### 3.5 TLS 错误状态

TLS（thread-local storage）让每个 host thread 拥有独立 last error：

```cpp
thread_local aecError_t last_error = AEC_SUCCESS;
```

规范特别规定：失败调用更新；成功调用不清除旧错误；`Peek` 只读；`Get` 读后清零。这和“每次调用都覆盖 error”不同。

### 3.6 序列化与 byte layout

kernel 参数块不能 `memcpy(native_struct)`，因为 native struct 可能 padding。必须按规定 offset 写 little-endian：

| Kernel     | byte 数 | 字段顺序                         |
| ---------- | ------: | -------------------------------- |
| Vector Add |      32 | A/B/C/count，均 u64              |
| GEMM       |      40 | A/B/C u64，M/N/K/dtype u32       |
| AXPY       |      28 | X/Y/count u64，alpha 的 f32 bits |
| DOT        |      32 | X/Y/result/count u64             |
| NRM2       |      24 | X/result/count u64               |

参数数组剩余未使用 byte 必须为 0。

### 3.7 浮点、packed dtype 和数值顺序

需要掌握 IEEE FP16/FP32/FP64、BF16、FP8、FP4、round-to-nearest-ties-to-even、NaN/Inf/signed zero。尤其注意：

- Runtime API dtype enum 数值不等于 ISA type selector；
- FP4 两个元素 packed 在一个 byte，低 index 在低 nibble；
- 奇数元素的最后高 nibble 必须为 0；
- INT4/INT8/INT32 输出为饱和 INT32；
- DOT/NRM2 按 index 递增顺序 FP32 累加；
- 不能为了方便在 Host 直接计算结果，必须走固定 image + ISA launch。

## 4. 当前仓库代码结构

```text
Track-C/C2-runtime/
├── spec.md
├── scoring.md
└── starter-kit/
    ├── Makefile
    ├── README.md
    ├── RELEASE_MANIFEST.json
    ├── include/
    │   ├── aec_runtime.h
    │   ├── aec_device_abi.h
    │   └── aec_isa.h
    ├── src/aec_runtime.cpp
    ├── lib/libaec_device.so       # manifest 要求，但当前 checkout 缺失
    ├── kernels/
    │   ├── manifest.json
    │   └── images/*.aecbin        # 34 个固定 image
    ├── examples/01...06_*.c
    ├── cases/
    ├── grader/public_grade.py
    ├── golden/
    ├── schemas/
    ├── agents/
    └── docs/01...06_*.md
```

### 4.1 三个头文件

- `aec_runtime.h`：上层用户调用的公开 API，是你必须实现的接口清单。
- `aec_device_abi.h`：你的 Runtime 调用官方设备库的底层接口和 command/completion 布局。
- `aec_isa.h`：AEC instruction/image header、opcode、type 和 encoder helper。

这三个文件都是评分契约，不要修改。

### 4.2 starter source

`src/aec_runtime.cpp` 当前实现了 device query、error name/TLS 基础和 stats；allocation、copy、Stream/Event、launch、GEMM/vector 等绝大部分函数返回 `AEC_ERROR_NOT_SUPPORTED`。它是空骨架，不是参考完整实现。

### 4.3 Makefile

`make -j2` 构建 `libaec.so` 并链接 `lib/libaec_device.so`；`make examples` 构建 6 个示例；`make public-cases` 和 `make public-test` 调 grader。当前因设备库缺失而在编译前停止。

### 4.4 examples

| 文件                     | 作用                                 |
| ------------------------ | ------------------------------------ |
| `01_device_query.c`    | 查询 device/ABI/ISA，最小 smoke test |
| `02_isa_encoding.c`    | 检查头文件 encoder 与 public golden  |
| `03_vector_add.c`      | alloc/copy/launch 完整同步链路       |
| `04_stream_event.c`    | Stream FIFO 与 Event                 |
| `05_fp32_gemm.c`       | Basic GEMM                           |
| `06_registered_copy.c` | host registration 与 zero-copy       |

### 4.5 grader 和 cases

`grader/public_grade.py` 是实际公开检查器。`cases/test_r101.py` 等只是调用 grader 的薄 wrapper。`public_cases.json` 描述公开 case；`manifest.json` 描述 requirement。不要修改它们来获得通过。

### 4.6 images、golden 和 schemas

- `kernels/images/`：只能使用这 34 个 image，不能新增自定义 image。
- `kernels/manifest.json`：semantic kernel、dtype、variant、shape/alignment/workspace 等映射。
- `golden/`：ISA encoding 与数值 public reference。
- `schemas/`：两个 Agent 的 JSON 输入输出约束。
- `agents/`：简单 starter 策略，只在 Good 完成后优化。

## 5. 建议怎样拆分源码

单文件继续写也能工作，但并发和生命周期混在一起会很难审查。建议在不改公开头文件的前提下拆分：

```text
starter-kit/src/
├── aec_runtime.cpp          # extern "C" API 薄入口
├── runtime_state.h/.cpp     # singleton、sequence、全局 registry
├── error.h/.cpp             # TLS 与 status 映射
├── allocation.h/.cpp       # live allocation/span validation
├── command.h/.cpp          # DMA/ISA command builder + submit
├── stream.h/.cpp           # queue、worker、async error
├── event.h/.cpp            # generation、cycle marker
├── registration.h/.cpp     # host interval registry
├── kernel.h/.cpp           # resolve、manifest constraints、params
├── numeric.h/.cpp          # dtype size/packed span helpers
└── library_ops.cpp         # GEMM、AXPY、DOT、NRM2 API
```

公开 API 入口只负责验证最外层参数、调用内部对象并设置 error；底层模块不应通过全局字符串猜测 requirement。

## 6. 两层 API 要分清

### Runtime API

用户看到 `aecAlloc`、`aecCopyH2D`、`aecLaunch` 等。错误码是 `aecError_t`，Stream/Event 是 Runtime handle。

### Device ABI

Runtime 内部看到 `aecDeviceAlloc`、`aecDeviceResolveKernel`、`aecDeviceSubmit` 等。错误码是 `aecDeviceStatus`，提交的是 `aecDeviceCommand`，得到 `aecDeviceCompletion`。

需要集中实现 status 映射。例如 device invalid address 应映射到 Runtime 的 `AEC_ERROR_INVALID_ADDRESS`，ISA trap 映射 `AEC_ERROR_ISA_TRAP`。不要散落在每个 API 中。

## 7. 从零开始的实现顺序

### 第 0 步：恢复环境

1. 获取官方 `lib/libaec_device.so`；
2. SHA-256 必须匹配 `RELEASE_MANIFEST.json`；
3. `file`/`readelf` 查 ELF 架构；
4. 在匹配 CPU 的 little-endian Linux 构建；
5. 先运行未改 starter 的 `make`、`01_device_query`、R101，记录真实 baseline。

这是 P0。没有设备库时不要用假的 Host 实现替代，否则会绕开强制执行路径。

### 第 1 步：R101 query/error/TLS

starter 已有基础，但需要逐项核对：

- count 必须是 1；
- device 0 metadata 精确；
- invalid device/null pointer 错误；
- 已知/未知 error name；
- 成功不清旧 error；
- Peek 不清、Get 清；
- 两个 host thread 相互隔离。

通过：

```bash
python3 cases/test_r101.py --submission .
```

### 第 2 步：R102 allocation/free

维护 allocation map，建议按 base 排序以便 span 查找。设备规则：64 MiB、前 64 byte 保留、64-byte 对齐、deterministic lowest-address first-fit、free block 合并。

即使官方 device 自己分配，Runtime 仍需要 live metadata，才能识别 interior/stale/double-free 和 copy span。

测试：正常 alloc/free、0 byte、OOM、reuse、unknown/interior/stale/double free。`aecFree` 必须等此前 enqueue 使用该 allocation 的工作。

### 第 3 步：R103 同步 copy

写一个统一 `validate_device_span(ptr, bytes)`。然后构造 H2D/D2H command：

- ABI version 2；
- 全进程严格递增且非零的 sequence；
- 合法 opcode、channel、chunk、queue depth；
- host address 放正确字段；
- completion sequence 必须匹配；
- status 翻译；
- 返回前完成。

同步路径先固定合法、保守策略，例如一个 channel 和 queue depth 1；性能优化以后做。

### 第 4 步：stats 与 command helper

统一封装：

```text
next_sequence()
build_dma_command(...)
submit_and_validate_completion(...)
map_device_status(...)
```

不要自己伪造 stats；`aecGetRuntimeStats` 应镜像受控 device counters。reset stats 不得清 allocation、registration、sequence、handle 或 image registry。

### 第 5 步：R104 Vector Add launch

完整路径：

1. 验证 kernel ID、grid/block、args pointer 和 exact `args_size`；
2. 验证所有 device span；
3. 调 `aecDeviceResolveKernel`，不能自己从 ID 算 handle；
4. 按 32-byte canonical layout 写 A/B/C/count；
5. 其余 parameter byte 清零；
6. command 使用 resolve 返回的 handle/ISA/entry/parameter bytes；
7. 提交 `AEC_DEVICE_OP_ISA_LAUNCH`；
8. 验证 completion；
9. 由 D2H 检查数值及 stats evidence。

至此形成最重要的 alloc → H2D → resolve → ISA launch → D2H 闭环。

### 第 6 步：R201 FP32/INT32 GEMM

先做 span size helper，注意 `M*N` 乘法 overflow、dtype storage size、packed 类型 ceil division。GEMM 规则：row-major、non-transposed、unbatched，M/N/K 在 `[1,256]`，A/B/C 不重叠。

R201 复用 Vector Add 的 resolve/param/submit 框架，只更换 semantic ID、dtype、shape、40-byte参数块和 candidate variant。完成 R101-R104/R201 且总分 30 才满足 Basic gate。

### 第 7 步：R105 Stream FIFO

每个 Stream 有稳定 ID、FIFO 队列、worker、first unreported async error。enqueue 必须复制 command 所需数据，特别是 launch args bytes；不能保存调用者 stack struct 指针。

同一 Stream 严格 FIFO。不同 Stream 无隐式顺序。同步 null Stream 可直接 submit；非空 Stream enqueue 后返回。

destroy 顺序：从 live registry 移除 → 阻止 enqueue → drain/stop worker → join → 释放。

### 第 8 步：R106 Event

Event 不是简单 bool。重复 `record` 会产生 generation，所有 query/sync/destroy/elapsed 观察最新 generation。

推荐状态：

```text
generation
recorded
completed_generation
cycle
status
condition_variable
```

record 向 Stream 队尾插入 marker；前面的工作完成后 marker 记录虚拟 cycle。未 record 是 invalid argument，未完成 query 是 NOT_READY。

### 第 9 步：R202/R203/R204 计算库

不要在 Host 算结果。对每个 API：验证 shape/span/overlap → 选择合法 fixed image → canonical params → ISA launch。

- R202：FP4、FP8 两格式、FP16、BF16、FP64；
- R203：packed INT4/INT8，INT32 饱和；
- R204：AXPY/DOT/NRM2，严格的 FP32 累加顺序由固定 image 执行。

Runtime 主要负责正确 storage byte 数、dtype mapping、image/params，不应自己重写数值 kernel。

### 第 10 步：R301-R304 driver 行为

- R301：严格 command/stat accounting；失败 preflight 不应退休指令或改数据。
- R302：两个 DMA channel、异步非法 span、错误后恢复。
- R303：精确 host interval registration，duplicate/overlap/overflow 失败；合法完整子区间加 REGISTERED+ZERO_COPY flags。
- R304：injected DMA/ISA fault 只消费一次，传播后设备可继续合法 command。

此阶段要补压力测试：并发 enqueue/destroy、allocation lifetime、fault 后下一条正常 command。

### 第 11 步：R401/R402 Agents

Good 全部通过后再做：

- DMA Agent 从固定合法值选 channel/chunk/queue depth/zero-copy；
- Kernel Agent 只能从输入 `candidates` 返回一个 candidate ID；
- stdin 一条 JSON，stdout 只能一条 JSON；
- 1 秒内结束，不访问网络、grader 或跨 case 保存状态。

Agent 公开性能只诊断，隐藏平均 speedup 决定 performance 分。不要为了公开 case ID 特判。

## 8. Basic、Good、Excellent 的精确路线

| 等级      | 硬门槛                                                   | 最适合的工作方式                           |
| --------- | -------------------------------------------------------- | ------------------------------------------ |
| Basic     | >=30 且 R101-R104、R201 全过                             | 只做同步、正确、通用闭环                   |
| Good      | >=75，Basic 且 R105/R106/R202-R204/R301-R304 全过        | 再引入并发、全部 dtype、fault/registration |
| Excellent | >=90，Good、两 Agent correctness、两者 hidden speedup >0 | 最后才调虚拟周期策略                       |

全部非 Agent requirement 合计 80 分。两个 Agent 即使合法但无 hidden speedup，文档说明上限 88/Good。

## 9. 测试循环

每完成一个 requirement：

```bash
make -j2
python3 cases/test_r10N.py --submission .
# 再运行此前所有 PASS requirement
python3 grader/public_grade.py --submission . --profile public --json-out /tmp/report.json
nm -D --defined-only libaec.so
```

必须阅读 grader detail 和 device stats，不能只看数值。计算结果对但没有 `isa_launches`、retired、handle/digest evidence，仍然失败。

建议补自己的测试：

- size/offset 接近 `UINT64_MAX`；
- interior/stale/double-free；
- two threads TLS；
- enqueue 后修改原 args；
- destroy 与 enqueue 竞争；
- Event 连续 record；
- registration 子区间、overlap、exact unregister；
- fault 后合法 command；
- dtype packing 的奇数元素。

## 10. 锁和所有权设计建议

建立清晰锁顺序，例如：global registry lock 不与 Stream queue lock 反向嵌套。对象从 registry 取出时应获得安全引用，避免 unlock 后对象被 destroy。

可以使用 `std::shared_ptr<StreamState>` 作为内部所有权，但公开 `aecStream_t` 仍需通过 registry 验证。不要把 shared_ptr 地址或裸对象地址当作永久可信 handle。

allocation 与 async work 的依赖可用 pending reference count 或全局 sequence fence 表示。`aecFree`/unregister 要等待此前引用它的工作，而不是粗暴 reset 整个设备。

## 11. 最常见的错误

- 在 macOS 构建出 Mach-O，却因后缀 `.so` 误认为是 Linux ELF；
- 修改 `include/`、grader、fixed image 或 device library；
- 直接在 Host 计算 GEMM/vector 输出；
- 把 Runtime kernel ID 当 device handle/opcode/code address；
- native struct `memcpy` 形成带 padding 的参数块；
- sequence 对每个 Stream 分开计数，而规范要求进程全局严格递增；
- 只检查 device 全局范围，不检查单个 live allocation；
- 成功 API 清除了旧 TLS error；
- async launch 保存 caller args 指针而不复制；
- Stream destroy 先 free 后 join，造成 use-after-free；
- Event 只有 completed bool，无法处理重复 record generation；
- ZERO_COPY 没有 REGISTERED flag 或超出注册 interval；
- reset stats 顺便清了 allocation/sequence；
- Agent stdout 打 debug 日志导致 JSON invalid；
- 公开 case 全过就宣称隐藏边界和并发一定通过。

## 12. 新手最先做的练习

1. 阅读 `aec_runtime.h`，把每个 API 分到 query/memory/async/compute。
2. 阅读 `aec_device_abi.h`，手写一张 Runtime API → Device ABI 表。
3. 阅读 `03_AEC_ISA规范.md` 并运行 `02_isa_encoding`（恢复环境后）。
4. 手算 Vector Add 32-byte 和 GEMM 40-byte 参数块。
5. 写不依赖 device 的 span validator unit test。
6. 写两个 thread 的 TLS last-error unit test。
7. 画出同步 copy 和异步 copy 的时序图。
8. 画出 Event record generation 状态机。
9. 恢复 device library 后，从 R101 开始逐项通过。

## 13. 完成定义

一个 requirement 只有在以下条件全部满足时完成：

- public case exact command exit 0；
- 此前通过的 cases 仍通过；
- 所有公开符号仍导出；
- 设备 stats/evidence 符合强制路径；
- invalid/lifetime/concurrency 自测通过；
- Linux ELF 架构和依赖正确；
- diff 未触碰 immutable contracts；
- `TEST_REPORT.md` 记录环境、commit、命令、退出码和 detail。

## 14. 术语速查

| 术语             | 简明解释                                          |
| ---------------- | ------------------------------------------------- |
| Runtime          | 给上层程序提供设备操作抽象的用户态库              |
| C ABI            | C 函数在二进制层的名称、参数和调用契约            |
| ELF              | Linux 常用可执行文件/动态库格式                   |
| opaque handle    | 调用者不能解释、只能交还给 Runtime 的句柄         |
| allocation span  | 某设备分配内部的一段连续合法地址                  |
| DMA              | host 与 device 之间的数据搬运命令                 |
| Stream           | 保证本队列 FIFO 的异步工作序列                    |
| Event            | 插入 Stream 的可查询完成/周期 marker              |
| TLS              | 每个 host thread 独立的数据                       |
| canonical params | 无 padding、固定 little-endian 顺序的参数 byte 串 |
| kernel image     | 官方提供的 AEC 指令镜像                           |
| completion       | device 对 command 的状态、周期、retired 等回执    |
| zero-copy        | 已注册 host 区间使用更低虚拟周期的传输模式        |
| virtual cycles   | 确定性设备模型给出的性能单位，不是 wall-clock     |
| fault injection  | 让下一条匹配 command 可控失败的测试机制           |

对 C2 来说，最正确的起点非常明确：先拿到并验证官方设备库，在匹配的 Linux 上让原始 starter 构建起来；然后只盯 R101-R104/R201，完成 Basic 的 30 分闭环，再引入异步与多精度复杂度。
