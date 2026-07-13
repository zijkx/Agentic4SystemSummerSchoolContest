# C1 新手教程：从 PTX 风格 IR 到 AEC 机器码

> 适用范围：`Track-C/C1-compiler/`。本文先讲清编译器在做什么，再给出可以直接照着推进的实现顺序。事实依据是 `Track-C/C1-compiler/spec.md`、`scoring.md`、`testcases/` 和 `Track-B/spec.md`。

## 1. 一句话理解 C1

C1 要做的是一个“小型 GPU 编译器”：读取人类可读、类似 NVIDIA PTX 的程序，理解程序的运算和控制关系，把它翻译成 AEC GPGPU 能执行的 128-bit 二进制指令，同时尽量让生成的程序更快。

```text
PTX 风格文本
    ↓ 词法/语法解析
结构化 IR
    ↓ CFG、SSA、优化
目标相关 IR
    ↓ 寄存器分配、指令调度
AEC 128-bit 指令
    ↓ 文件封装
output.aecbin
```

还要做一个反方向的工具：`aec-objdump` 把 `.aecbin` 中的机器指令还原成人类可读的 AEC 汇编，便于调试。

## 2. 它在完整软件栈中的位置

高级框架或程序最终会产生计算任务。编译器负责把“要算什么”变成“硬件逐条执行什么”。C1 不负责分配主机内存、创建 Stream 或加载 ONNX；这些分别更接近 C2 和 C3。

可以用厨师类比：

- PTX IR 是步骤比较抽象的菜谱，例如“取数组第 i 个数并相加”。
- AEC ISA 是厨房设备只认识的按钮编码。
- 编译器把菜谱拆成按钮序列。
- 优化器在不改变菜品的前提下，减少重复步骤和等待。
- 寄存器分配决定有限的操作台分别放什么食材。
- 指令调度决定先按哪个按钮，尽量避免设备空等。

## 3. 最先要掌握的前置知识

不必先学完整本编译原理教材。按下面顺序掌握到“能解释、能写小例子”的程度即可。

### 3.1 C++17 与工程基础

建议使用 C++17，因为解析器、IR 和图算法需要可靠的数据结构与类型系统。至少掌握：

- `std::string`、`std::vector`、`std::unordered_map`、`std::variant`；
- 值语义、引用、智能指针和对象生命周期；
- 枚举、结构体、错误返回；
- 二进制文件读写和 little-endian 整数编码；
- Make/CMake 之一；
- 单元测试与命令行参数解析。

### 3.2 二进制与整数表示

必须理解 bit、byte、十六进制、补码、大小端。AEC 每条指令固定 128 bit，即 16 byte。`Track-B/spec.md` 规定 raw binary 按以下四个 little-endian `u32` 写出：

```text
w0 = bits [31:0]
w1 = bits [63:32]
w2 = bits [95:64]
w3 = bits [127:96]
```

例如“整个指令是 128-bit”不代表可以把宿主机的 C++ struct 直接写进文件。struct 可能有 padding，宿主机字节序也不应成为隐式前提。正确方法是显式移位、掩码并写入固定宽度整数。

### 3.3 汇编、ISA 与 ABI

ISA（Instruction Set Architecture）规定每条指令的编码与语义。AEC 通用布局是：

| 位段 | 含义 |
|---|---|
| `[127:112]` | 16-bit opcode |
| `[111:96]` | 类型、subop、memory space、predicate 等控制位 |
| `[95:80]` | 目的操作数 |
| `[79:64]` | 第一源操作数 |
| `[63:32]` | 第二源操作数或立即数的一部分 |
| `[31:0]` | 扩展立即数、分支目标、第三源等 |

ABI 是调用双方的契约，例如 kernel 参数怎样出现、special register 表示什么。PTX 中 `%tid.x`、`%ctaid.x`、`%ntid.x` 对应线程、CTA 和 block 维度；翻译时必须映射到 AEC 规范定义的 special selector 或等价指令序列。

### 3.4 GPU 执行模型

需要理解：

- thread：一个逻辑执行实例；
- warp：32 个 lane 锁步执行；
- CTA/block：最多 256 个 thread，即最多 8 个 warp；
- grid：多个 CTA；
- predicate：决定某些 lane 是否执行一条指令；
- GMEM/SMEM/CMEM/LMEM/PMEM：不同作用域的地址空间。

GPU 的分支不是简单的 CPU 跳转。warp 内 lane 可能有不同条件，编译器必须正确处理 predicate 和控制流，不能让本应关闭的 lane 产生寄存器或内存副作用。

### 3.5 编译器 IR

IR 是源代码和机器码之间的内部表示。不要边读字符串边直接吐机器码，否则很快无法处理 label、类型检查、优化和寄存器压力。

最小 IR 可以包含：

```cpp
struct Operand {
    OperandKind kind;       // virtual register, immediate, symbol, memory
    ValueType type;         // u32, u64, f16, f32, pred ...
    std::string text;
};

struct Instruction {
    Opcode opcode;
    std::optional<Predicate> guard;
    std::vector<Operand> outputs;
    std::vector<Operand> inputs;
    SourceLocation location;
};

struct BasicBlock {
    std::string label;
    std::vector<Instruction> instructions;
    std::vector<BlockId> successors;
};
```

这里是推荐设计，不是仓库已有代码。

### 3.6 CFG、基本块和支配关系

基本块是一段“只能从开头进入、执行到末尾才离开”的直线指令。遇到 label、条件跳转、无条件跳转、`ret` 时要划分基本块。

CFG（Control Flow Graph）以基本块为节点，以可能发生的跳转为边。例如：

```text
ENTRY ──条件真──> DONE
  │
 条件假
  ↓
 BODY ──────────> DONE
```

很多优化必须知道一条定义是否支配某个使用、某段代码是否在循环内，因此 CFG 是 T2 以后能力的基础。

### 3.7 SSA

SSA（Static Single Assignment）要求一个虚拟值只被定义一次：

```text
r = 1             r1 = 1
r = r + 1   →     r2 = r1 + 1
```

不同控制流汇合时使用 phi 概念选择来源。即使最终不保留显式 SSA，也应理解 def-use 链。DCE、CSE、常量传播和寄存器活跃区间都依赖“谁定义、谁使用”。

### 3.8 数据流分析

至少需要掌握：

- use-def / def-use；
- live-in / live-out；
- reaching definitions；
- 循环与 back edge；
- 数据依赖图 DDG。

可以把它们理解为在图上反复传播集合，直到结果不再变化。

## 4. 先看懂一个公开输入

从 `PTX-01_vector_add.ptx` 开始。它完成 `c[i] = a[i] + b[i]`：

1. `ld.param` 读取 kernel 参数；
2. `%tid.x`、`%ctaid.x`、`%ntid.x` 算全局线程编号；
3. `setp.ge` 判断线程是否越界；
4. `@%p1 bra DONE` 对越界线程提前结束；
5. `mul.wide` 把元素下标换成 byte offset；
6. `ld.global.f32` 读取两个输入；
7. `add.f32` 相加；
8. `st.global.f32` 写回；
9. `ret` 返回。

新手练习：手工列出每条指令的定义和使用，画出 `ENTRY` 与 `DONE` 两个基本块，再标出跳转边。能完成这个练习，才开始写 parser。

## 5. 赛题要求究竟是什么

### 5.1 必须提供的命令

```bash
aec-cc input.ptx -o output.aecbin
aec-cc input.ptx -O0 -o output.aecbin
aec-cc input.ptx -O2 -o output.aecbin
aec-cc input.ptx -O3 -o output.aecbin
aec-objdump output.aecbin
```

命令必须接受任意合法路径，不能依赖当前用户名或公开文件名。

### 5.2 二进制要求

`spec.md` 要求至少包含 Header、Code、Data、Relocation 和 Symbol Table。当前仓库没有给出这些 section 的完整 byte-level 容器布局，也没有公开 validator。因此：

- 不能擅自宣称某个自创 layout 就是正式格式；
- 应先向主办方获取正式格式或 validator；
- 内部可设计版本化容器用于开发，但必须隔离在 `BinaryFormat` 模块中，便于替换；
- AEC 单条 ISA 的编码可以依据 `Track-B/spec.md` 实现和单测。

### 5.3 必须实现的 pass

- 解析、基本块、CFG、SSA；
- 常量传播、DCE、CSE、LICM、基本块合并；
- 合并内存访问、predicate 优化、shared-memory promotion；
- 多精度 GEMM 识别、精度与 tile 选择；
- linear scan 或 graph coloring register allocation；
- spill；
- DDG、list scheduling、延迟隐藏和 dual issue；
- 目标编码与反汇编。

这些是最终范围，不是第一天全部一起写。

## 6. 当前仓库有什么

```text
Track-C/C1-compiler/
├── spec.md
├── scoring.md
└── testcases/
    ├── README.md
    ├── PTX-01_vector_add.ptx
    ├── PTX-02_invariant_poly.ptx
    ├── PTX-03_repeated_reuse.ptx
    ├── PTX-04_reg_schedule.ptx
    └── PTX-05_gemm_f16.ptx
```

- `spec.md`：输入输出、pass、环境和评测流程。
- `scoring.md`：正确性、性能、鲁棒性和 Agent 分值。
- `PTX-01`：基础 lowering。
- `PTX-02`：循环不变量、CSE、DCE。
- `PTX-03`：重复 load 与 shared memory。
- `PTX-04`：寄存器活跃区间、调度、dual issue；样例里还存在先使用后定义的虚拟寄存器，parser/validator 必须能给出明确诊断或按正式语义处理，不能崩溃。
- `PTX-05`：FP16 GEMM 和 tiling。

仓库没有实现源码、构建文件、公开 Golden/Cycle Model，也没有正式 `.aecbin` 容器说明。这就是实际起点。

## 7. 推荐代码结构

下面是建议新建的结构，不表示仓库当前已有：

```text
Track-C/C1-compiler/
├── CMakeLists.txt
├── README.md
├── include/aec_compiler/
│   ├── diagnostic.h
│   ├── token.h
│   ├── ast.h
│   ├── ir.h
│   ├── cfg.h
│   ├── pass.h
│   ├── target_ir.h
│   ├── isa.h
│   └── binary_format.h
├── src/
│   ├── cli/aec_cc_main.cpp
│   ├── cli/aec_objdump_main.cpp
│   ├── frontend/lexer.cpp
│   ├── frontend/parser.cpp
│   ├── frontend/semantic.cpp
│   ├── ir/cfg.cpp
│   ├── ir/ssa.cpp
│   ├── passes/const_prop.cpp
│   ├── passes/dce.cpp
│   ├── passes/cse.cpp
│   ├── passes/licm.cpp
│   ├── target/lowering.cpp
│   ├── target/regalloc.cpp
│   ├── target/scheduler.cpp
│   ├── target/encoder.cpp
│   ├── target/decoder.cpp
│   └── binary/binary_format.cpp
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── tools/
    └── inspect_ir.cpp
```

模块边界的核心原则是：parser 不知道机器码 layout；优化 pass 不直接处理字符串；encoder 不重新推断类型；objdump 复用 decoder 和 binary reader。

## 8. 循序渐进的实现路线

### 第 0 步：建立可构建空壳

目标：生成两个可执行文件，能输出 `--help`，错误路径返回非零。

验收：

```bash
aec-cc --help
aec-objdump --help
aec-cc missing.ptx -o /tmp/x.aecbin   # 必须清晰失败
```

不要一开始引入 LLVM。两天比赛里，针对限定 PTX 子集的轻量结构更可控；除非队伍已有 LLVM 后端经验。

### 第 1 步：lexer

lexer 把字符流变成 token，例如 directive、identifier、register、integer、float bit literal、标点、label。必须保存行列号。

重点：

- 跳过空白和注释；
- 区分 `%r1`、`%rd1`、`%p1`；
- 保留 `.global`、`.f32` 等 suffix；
- 解析 `0f00000000` 这类 bit literal 时保留 bit pattern；
- 未知字符产生诊断，不能无限循环。

先对 PTX-01 token 序列写 golden unit test，再覆盖所有五个文件。

### 第 2 步：parser 和语义检查

parser 构造 kernel、参数、寄存器声明、label、instruction。先接受五个公开文件用到的语法，再扩展合法变体。

语义检查包括：

- label 是否重复/存在；
- 寄存器类别和编号是否合法；
- opcode 的参数个数；
- source/destination type 是否兼容；
- memory operand 的括号形式；
- predicate guard 是否引用 predicate register。

诊断必须带源位置。隐藏测试会重命名寄存器和重排 block，所以不能依靠字符串固定位置。

### 第 3 步：基本块和 CFG

划分 block，解析 fallthrough 和 branch successor，并检查终结指令。实现：

```text
build_basic_blocks(linear_instructions)
resolve_labels()
build_successors_and_predecessors()
validate_reachability_and_terminators()
```

为 PTX-01、PTX-02 输出可读 CFG 文本，人工对照。

### 第 4 步：最小 O0 lowering

先不优化，保证语义。把 PTX instruction 转成更接近 AEC 的 target instruction。复杂 PTX 操作可以展开成多条 AEC 指令。

关键问题逐条做映射表：

- PTX opcode + suffix；
- source/destination 类型；
- AEC opcode/type；
- 是否需要临时值；
- predicate 如何保留；
- memory space 如何编码；
- unsupported 时怎样明确报错。

不要用一个巨大的 `if` 同时解析、分配寄存器和编码。

### 第 5 步：ISA encoder/decoder

为每个已支持的 AEC opcode实现纯函数：结构化字段进，四个 `u32` 出。decoder 做逆变换并验证 MBZ（must be zero）字段。

最重要的测试是不依赖完整编译器的 round trip：

```text
Instruction → encode → 16 bytes → decode → Instruction
```

还要测试非法 type/opcode、过大寄存器编号、predicate 组合和 branch target。`R0` 是普通可写寄存器，不能当常量零。

### 第 6 步：临时 binary container 和 objdump

把 binary container 的读写集中到一处，做 bounds/overflow/magic/version 检查。由于正式 section layout 缺失，先标注开发格式并保留替换能力，不得把它宣称成正式合规。

`aec-objdump` 应完成：文件检查、section 列表、逐条 decode、显示 PC/bytes/mnemonic。畸形文件必须安全失败，不能越界读取。

### 第 7 步：虚拟寄存器和 linear-scan allocation

先计算每个虚拟值的 live interval，再按起点排序：

1. 释放已经结束的物理寄存器；
2. 分配空闲物理寄存器；
3. 无空闲时选择 spill；
4. 插入 load/store spill code；
5. 重新计算 interval，直到稳定。

AEC 每 thread 最多 256 个 32-bit GPR。64-bit 值占 pair，base 可以是奇数但最大 254。predicate register 是独立的 8 个 P 寄存器，不能和 GPR 混分配。

### 第 8 步：O2 标量优化

建议顺序：

1. 常量传播和 constant folding；
2. DCE；
3. local CSE；
4. basic-block merge；
5. 循环识别与 LICM；
6. 再做 DCE。

每个 pass 都要保持 verifier 通过，并提供 `changed` 结果。用 `-print-ir-before/after` 一类内部选项调试，但不要污染正式 stdout 契约。

PTX-02 是学习样例：两次 `%f1 + %f2` 可 CSE；循环不变表达式可外提；未影响输出的 `%f15` 可 DCE。

### 第 9 步：DDG 和 list scheduling

DDG 节点是指令，边表示依赖：

- RAW：读依赖于此前写；
- WAR：后写不能越过此前读；
- WAW：两次写保持顺序；
- memory dependency：可能别名的 load/store；
- control/barrier dependency。

List scheduling 每轮从 ready set 选优先级最高的指令。优先级可以考虑 critical path、latency、寄存器压力和 dual-issue 配对。先保证依赖绝不破坏，再优化周期。

### 第 10 步：memory 与 GEMM 优化

内存优化前先实现保守 alias analysis。无法证明地址不同，就不能随意删除或移动 load/store。

GEMM 优化要识别的是通用索引/归约模式，而不是文件名或固定变量名。逐层推进：

1. 识别 `C[m,n] += A[m,k] * B[k,n]`；
2. 验证 shape、dtype 和边界；
3. 选择 scalar 或 TMUL lowering；
4. 选择 tile；
5. 处理非 tile 整除的尾部；
6. 扩展到 9 种隐藏 dtype。

### 第 11 步：O3 与 Agent

只有 O0/O2 正确和稳定后才做。Agent 必须独立读取性能报告、选择合法配置、重新编译、验证正确性并输出报告。不要让 Agent 根据 case 名字硬编码答案。

## 9. 每个公开样例该怎样使用

| 样例 | 首要用途 | 不应得出的结论 |
|---|---|---|
| PTX-01 | parser、CFG、基础 lowering、predicate、load/store | 通过不代表 PTX 语法已完整支持 |
| PTX-02 | CSE/DCE/LICM 与循环 | 不能假定循环总是 32 次 |
| PTX-03 | alias/load reuse/shared promotion | 不能按变量名识别复用 |
| PTX-04 | liveness/regalloc/DDG/scheduling和诊断鲁棒性 | 不能为了样例顺序写特判 |
| PTX-05 | GEMM pattern、FP16、tail/tile | 隐藏会换 dtype 与非整除 shape |

公开 PTX 只是输入，没有公开正确输出 runner。自行写单测可以证明内部性质，不能声称通过官方正确性。

## 10. 测试策略

### 单元测试

- lexer token 和源位置；
- parser AST/IR；
- CFG predecessor/successor；
- dominance/loop/liveness；
- 每个 pass 的 before/after；
- encoder/decoder round trip；
- little-endian byte 序；
- binary reader 畸形输入；
- linear scan 和 spill；
- scheduler 保持依赖。

### 性质测试

- 寄存器随机重命名后结果结构等价；
- block 合法重排后 CFG 等价；
- encode/decode 对所有合法字段 round trip；
- 优化前后解释器结果一致；
- 同一输入多次编译 byte-for-byte deterministic。

建议写一个内部 IR interpreter 或 differential checker。它不能替代官方 AEC Golden Model，却能在官方工具缺失时尽早发现优化误编译。

### 回归层次

```text
修改 parser → parser unit + 5 文件 parse
修改 pass   → 对应 unit + IR verifier + O0/O2 differential
修改 regalloc/scheduler → liveness/DDG unit + 全部 codegen
修改 encoder/binary → 全部 round trip + objdump + 所有集成测试
```

## 11. 评分导向的优先级

正确性 50 分是门禁，性能 35 分只统计正确 case。推荐：

- P0：稳定 CLI、parser、CFG、O0、合法机器指令、objdump；
- P1：T1 通用正确性，然后 T2 的标量优化和 T4 基础 regalloc；
- P1：鲁棒诊断和 mutation tests；
- P2：memory、scheduling、GEMM/TMUL；
- P3：Agent 自动调优。

不要因为 T5 性能分高就跳过 T1。没有合法 binary 和正确执行，任何调度加速都得不到性能分。

## 12. 最常见的错误

- 用正则表达式拼凑整门语法，遇到空格、换行、suffix 组合即失败；
- 直接把 C++ bit-field struct 写入 binary；
- 把 `R0` 当零寄存器；
- 忘记清零 reserved/MBZ bit；
- branch target 使用 byte offset，但规范要求 instruction index；
- 64-bit pair 越界或错误要求偶数 base；
- 优化跨过可能 alias 的 memory operation；
- DCE 删除有 store、branch、trap 等副作用的指令；
- scheduler 只看 RAW，遗漏 WAR/WAW/memory/control；
- spill 插入后不重新分析；
- 用公开文件名、变量名或固定 N 匹配优化；
- 把能反汇编误认为能正确执行；
- 没有官方 validator 却声称 `.aecbin` 格式合规。

## 13. 新手的第一周学习与动手清单

1. 阅读 `spec.md` 和 `testcases/README.md`，逐行注释 PTX-01。
2. 阅读 `Track-B/spec.md` 的执行模型、binary 通用字段、type matrix、operand placement。
3. 手画 PTX-01/PTX-02 CFG，列 def-use。
4. 写 128-bit 字段 pack/unpack 小程序和 round-trip test。
5. 建两个 CLI 空壳与测试框架。
6. 完成 lexer 和 PTX-01 parser。
7. 完成所有五个文件的 parse-only 模式。
8. 完成 CFG verifier 和可视化文本输出。
9. 建 target instruction 结构与第一批 encoder tests。
10. 获取/确认正式 `.aecbin` container 和官方 validator，再接完整 O0 codegen。

## 14. 完成定义

一个阶段只有同时满足以下条件才算完成：

- 合法输入得到确定输出；
- 非法输入清晰失败且不崩溃；
- 有针对隐藏变体的通用测试；
- 机器编码可被独立 decoder 还原；
- 优化前后语义经 differential test 一致；
- exact command、exit code 和结果记录在 `TEST_REPORT.md`；
- 正式环境中的官方验证结果与本地内部测试分开陈述。

## 15. 术语速查

| 术语 | 简明解释 |
|---|---|
| frontend | 读取源 IR 并理解语法/语义的部分 |
| IR | 编译器内部、便于分析和变换的程序表示 |
| lowering | 把高级操作拆成目标硬件能表达的低级操作 |
| basic block | 中间没有跳入跳出的直线代码段 |
| CFG | 基本块之间可能控制转移的图 |
| SSA | 每个虚拟值只定义一次的表示 |
| pass | 对 IR 做一次分析或变换的模块 |
| liveness | 某个值在程序位置之后是否还会被使用 |
| spill | 物理寄存器不够时，把值暂存到内存 |
| DDG | 指令间数据/顺序依赖组成的图 |
| list scheduling | 从当前可执行指令中按优先级排程 |
| predicate | 控制某条指令在哪些 lane 生效的条件 |
| ISA | 机器指令编码和行为的正式契约 |
| ABI | 不同组件怎样传参、调用、交换二进制的契约 |
| little-endian | 低有效 byte 先存储 |
| relocation | 链接/装载时需要修正的地址引用信息 |

读完本文后，最正确的第一步不是写高级 GEMM pass，而是：确认正式 binary 容器契约，搭好两个 CLI、IR、诊断和 encoder 单测，然后让五个公开 PTX 全部稳定通过 parse-only。
