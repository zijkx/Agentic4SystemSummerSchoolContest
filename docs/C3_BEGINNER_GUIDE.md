# C3 新手教程：ONNX 图解析、算子调度与模型部署

> 适用范围：`Track-C/C3-scheduler/`。本文解释 C3.1-C3.5 如何连成一个可执行系统，并给出从零实现顺序。当前仓库只有规范、三个公开 ONNX 模型和测试数据，没有选手 starter code；文中的推荐目录均需后续新建。

## 1. 一句话理解 C3

C3 要做一个“小型深度学习编译/运行系统”：读取 ONNX 模型，把网络变成内部计算图，决定每个算子用哪些底层 kernel、哪些算子可以融合、张量放在哪里和何时释放，最后在 GPU 上执行完整模型并写出结果。

```text
model.onnx
    ↓ parse + shape/type information
内部 DAG
    ↓ graph passes
优化后的 DAG
    ↓ operator decomposition + kernel selection
kernel 执行计划
    ↓ lifetime / memory / stream scheduling
可执行 plan
    ↓ GPU backend
logits.npy + manifest.json
```

C3.1 看“能不能正确看懂图”，C3.2 看“能不能把算子拆成硬件 kernel”，C3.3 看“能不能减少不必要的 kernel 和中间张量”，C3.4 看“能不能规划内存与并行”，C3.5 看“整个模型最终跑得对不对、快不快、省不省显存”。

## 2. 它与普通模型推理有什么区别

直接调用成熟框架的一行 `session.run()` 可以作为 CPU/GPU reference，帮助确认模型和数据，但它没有证明你实现了题目要求的 graph representation、decomposition、fusion、memory planning 和 scheduling。

C3 的核心价值是自己掌握中间过程：图中有哪些节点和张量、shape/dtype/attribute 是什么、一个 Softmax 怎样拆成基础 kernel、哪些操作可以融合、哪些 buffer 可以复用、copy 与 compute 怎样重叠，以及 batch 怎样切分且保持样本顺序。

## 3. 前置知识学习路线

### 3.1 Python 工程基础

建议先用 Python 完成图层与调度层。至少掌握 dataclass、type hints、Enum、list/dict/set、异常、`argparse`、`pathlib`、JSON、NumPy `.npy`、pytest、venv 和依赖锁定。

当前系统 Python 3.9 低于规范 3.10+，Python 3.13 又没有依赖。应创建隔离的、wheel 兼容性较好的 Python 3.11/3.12 venv，不能改系统 Python。

### 3.2 张量、shape、stride 和 dtype

张量是多维数组。shape `[N, 3, 32, 32]` 表示 N 张三通道 32×32 图片。需要理解：

- rank 和 axis；
- dynamic dimension：这里的 N 可变化；
- dtype：FP32、FP16、INT64 等；
- contiguous/stride：元素怎样映射到线性内存；
- broadcast：不同 shape 如何合法扩展；
- reshape/transpose：可能只改 view，也可能要求实际重排。

内存 byte 数通常是元素数乘 dtype size，但必须检查动态维、overflow、alignment 和 backend layout。

### 3.3 神经网络推理基础

无需先训练模型，但要理解：

- MLP：Flatten 后多层 Gemm + Relu；
- CNN/ResNet：Conv 提取特征，残差 Add 保留信息，GlobalAveragePool 汇总空间；
- Transformer：embedding Gather、Q/K/V MatMul、Softmax attention、LayerNorm、残差和前馈网络；
- logits：最后的未归一化分数；
- top-1 accuracy：`argmax(logits)` 与 label 的匹配率。

### 3.4 ONNX 基础

ONNX 是 protobuf 序列化的模型交换格式。核心对象：

- `ModelProto`：整个模型和 opset；
- `GraphProto`：计算图；
- `NodeProto`：算子、inputs、outputs 和 attributes；
- `ValueInfoProto`：张量 dtype/shape；
- initializer：权重和常量；
- graph input/output：真正模型边界。

有些 ONNX 会把 initializer 同时列入 graph input，但 C3.1 的 `graph_inputs` 明确不含权重。必须用 initializer name set 过滤，不能简单照抄 `graph.input`。

### 3.5 DAG 和拓扑排序

DAG 是有向无环图。数据从 producer node 的 output 流向 consumer node 的 input。执行前要保证拓扑顺序：一个节点的所有依赖完成后才能执行。

建议维护：

```text
producer_of[tensor_name] -> node_id 或 graph input/initializer
consumers_of[tensor_name] -> [node_id...]
```

它们支撑 edge 构造、未定义 tensor 检查、pattern matching 和 lifetime analysis。

### 3.6 算子语义

必须理解 attribute 和 shape 规则，而不只是节点名字：

- Gemm：`Y = alpha*A*B + beta*C`，还有 `transA/transB`；
- MatMul：支持 batch/broadcast；
- Conv：pads、strides、dilations、groups；
- Flatten：axis；
- Reshape：shape tensor 中 0/-1；
- Split：axis 与 output sizes；
- Softmax：axis 和数值稳定；
- LayerNormalization：axis、epsilon、scale/bias；
- Gather：indices dtype 和 axis；
- Transpose：perm；
- Constant：value 来自 attribute，不一定是 initializer。

### 3.7 GPU kernel 与 launch

算子是语义单位，kernel 是硬件执行单位。一个算子可能由一个或多个 kernel 完成，相邻算子也可能融合成一个 kernel。launch 配置通常包含 grid、block、shared memory 和 stream。

C3.2 明确检查：`block_x > 0` 且不超过硬件上限、`grid_x > 0`、`smem_bytes` 不超过硬件预算。

### 3.8 数值误差

浮点运算不满足严格结合律。换累加顺序、使用 TF32/FP16 或融合都可能改变结果。C3.5 要求：

```text
abs(out - golden) <= 1e-3 + 1e-3 * abs(golden)
```

先用完整 FP32 reference 跑通，再逐个降低精度。Softmax、LayerNorm 等敏感算子按评分要求保持 FP32。

## 4. 当前仓库里有什么

```text
Track-C/C3-scheduler/
├── spec.md
├── scoring.md
└── testcases/
    ├── README.md
    └── release_to_competitors/
        ├── README.md
        ├── decompress_testdata.sh
        ├── docs/COMPETITOR_GUIDE.md
        ├── models/
        │   ├── mlp_v1.onnx
        │   ├── resnet_v1.onnx
        │   └── transformer_v1.onnx
        └── testdata/c35/{mlp_v1,resnet_v1,transformer_v1}/
```

### 4.1 三个模型

- MLP：`Flatten/Gemm/Relu`，输入 `[N,1,28,28]`，输出 `[N,10]`。
- ResNet：`Conv/Relu/Add/GlobalAveragePool/Flatten/Gemm`，输入 `[N,3,32,32]`。
- Transformer：Gather、LayerNormalization、MatMul、Split、Reshape、Transpose、Softmax、Erf 等，输入 INT64 `[N,18]`，输出 `[N,18,14]`。

三者是 opset 17，batch N 动态。隐藏版结构相同、权重不同。

### 4.2 测试数据

每个模型有 input manifest/NumPy、golden manifest/logits、threshold；MLP/ResNet 还有 labels。ResNet 输入被压成 `.npy.gz`，脚本会生成约 117 MiB 文件，只有准备推理时再解压。

### 4.3 当前缺少什么

没有 `export_dag.py`、`infer.py`、scheduler source、dependency file、operator tests，也没有规范引用的 `benchmarks/c32_c33/bench_c32_c33.py`。规范提到 `GraphPassPipeline`、`KernelSpecRef`、`MockRuntime` 和 `scheduler/graph_passes/fusion.py`，但这些实现未出现在当前 Git tree。必须向主办方确认 benchmark/API 包，不能凭名字宣称兼容。

## 5. 推荐代码结构

下面是建议新建的结构：

```text
Track-C/C3-scheduler/
├── pyproject.toml
├── requirements.lock
├── README.md
├── export_dag.py
├── infer.py
├── scheduler/
│   ├── ir/{dtype,tensor,node,graph}.py
│   ├── frontend/{onnx_loader,attributes,shape_inference}.py
│   ├── graph_passes/{pipeline,canonicalize,fusion,validate}.py
│   ├── lowering/{registry,elementwise,gemm,conv,softmax,layernorm}.py
│   ├── planning/{kernel_spec,tuning,lifetime,memory_pool,prefetch,streams}.py
│   ├── runtime/{backend,reference_cpu,gpu_backend}.py
│   └── io/{manifest,dag_json}.py
└── tests/{unit,operators,graph_passes,integration}/
```

CLI 只做参数和文件 I/O；模型逻辑进入 `scheduler/`。CPU reference 与正式 GPU backend 共享 graph/plan，但分开实现，防止把成熟框架捷径误当作最终 scheduler。

## 6. 内部 IR 怎样设计

```python
@dataclass
class TensorDesc:
    name: str
    dtype: DType
    shape: tuple[int | str | None, ...]
    is_initializer: bool = False
    data: np.ndarray | None = None

@dataclass
class Node:
    id: str
    op_type: str
    inputs: list[str]
    outputs: list[str]
    attributes: dict[str, object]

@dataclass
class Graph:
    inputs: list[str]
    outputs: list[str]
    tensors: dict[str, TensorDesc]
    nodes: list[Node]
```

lowering 后使用独立 plan：

```python
@dataclass
class KernelStep:
    kernel: str
    inputs: list[str]
    outputs: list[str]
    precision: str
    tuning_params: dict[str, int]
    stream: int = 0
```

不要在原始 ONNX Node 上混入所有 backend 字段。图语义和执行计划是不同层。

## 7. C3.1：先把图解析正确

### 7.1 CLI

```bash
python export_dag.py --onnx model.onnx --output dag.json
```

退出码必须为 0，评分读取 output 文件，不依赖 stdout。路径必须来自参数。

### 7.2 实现步骤

1. `onnx.load(path)`；
2. `onnx.checker.check_model(model)`；
3. 可用 `onnx.shape_inference.infer_shapes(model)`；
4. 记录 opset；
5. 建 initializer set；
6. 解析真正 graph inputs/outputs；
7. 按原始顺序解析 nodes；
8. 建 producer/consumer 与 edges；
9. 验证 tensor reference、唯一 ID 和 DAG；
10. 写合法 JSON。

### 7.3 细节

ONNX node.name 可以为空。内部 ID 要稳定唯一，可用 `op_type + original_index`，不能用不稳定的 Python hash。symbolic dimension 保留 `dim_param`，未知维用 `null`，不能把动态 N 写死成 10000。

只有 node producer 到 node consumer 才是普通 node edge。initializer 和 graph input 没有 producer node。一个 tensor 有多个 consumer 时要输出多条 edge。

### 7.4 最小验收

- 三个 public model 均能导出；
- JSON 可重新 parse；
- graph inputs 不含 initializer；
- outputs、tensor name 和 node op_type 保留；
- edge 引用都存在；
- 拓扑排序覆盖所有 node；
- dynamic N 未固化；
- 改权重/路径不影响结构解析。

## 8. 先做 CPU reference executor

优化前需要可信 reference。可以用 ONNX Runtime/PyTorch 生成总结果，再用自己的 NumPy operator reference 做 pass differential。

它用于确认 input name/dtype/shape、batch slicing、manifest 输出、pass 前后语义和第一个错误中间 tensor。它不是正式 GPU scheduler 得分证据，也不能替代 C3.2-C3.4。

## 9. C3.2：算子分解与 kernel 选择

### 9.1 decomposition

稳定 Softmax 可以拆成：

```text
max = reduce_max(x, axis)
shifted = x - max
e = exp(shifted)
sum = reduce_sum(e, axis)
y = e / sum
```

LayerNorm 可以拆成 reduce_mean、sub、mul、第二次 reduce_mean、sqrt、div、scale 和 bias。每个 intermediate 都要有 TensorDesc，供 memory planner 使用。

### 9.2 lowering registry

建立 `op_type -> lowering function`。输入 node、tensor desc、hardware capabilities，输出 kernel steps 和 intermediates。未知算子必须明确报错并列出 node/opset，不能静默跳过。

### 9.3 precision routing

先做 `FULL_FP32` baseline：

- Softmax/LayerNorm 等敏感算子 FP32；
- MatMul/Gemm/Conv 再根据 hardware 和实验选择 FP16/FP8/FP4；
- 每次降精度都做 full allclose/accuracy；
- precision 是 plan 显式字段，不能只藏在 kernel 名里。

### 9.4 kernel sequence 与 tuning

评分关注 MatMul 的 `matmul_*`，Softmax 的 reduce-max/exp/reduce-sum/div，LayerNorm 的 reduce-mean/sub/mul/sqrt，Conv 的 im2col/Winograd。

每个可调 step 至少满足：

```text
0 < block_x <= max_threads_per_block
grid_x = ceil(work_items / block_x) > 0
smem_bytes <= hardware.smem_bytes，或按规范用 -1 表示不适用
```

这些名字和字段必须接入真实 plan，不能只打印出来骗检查。

### 9.5 Conv 策略

im2col 通用但需要较大中间 buffer；Winograd 适合部分小卷积条件，乘法少但变换复杂。先实现正确的 direct/im2col，再按 kernel size、stride、dilation、groups、shape 和 workspace 选择 Winograd，并始终保留 fallback。

## 10. C3.3：算子融合

融合减少 launch 与中间显存流量。以 MatMul → AddBias 为例，必须确认 MatMul output 的 consumer、bias broadcast、shape/dtype、graph output 语义和 backend kernel 都合法。

五个目标 pattern：

- `FusedMatMulBias`；
- `FusedConv2dBatchNorm`；
- `FusedEWChain`；
- `FusedSoftmaxDropout`；
- `FusedResidualNorm`。

公开 ResNet 的 BN 已折叠进 Conv，图中没有 BN node。规范提到预融合/code review；缺少官方 benchmark/API 时应先确认期望，不能凭空恢复不存在的 BN 参数。

安全 rewrite 流程：

1. 找匹配子图；
2. 验证 consumer/shape/dtype/attribute；
3. 建 fused node，保留外部 inputs/outputs；
4. 更新 producer/consumer；
5. 删除只在内部使用的 tensor；
6. 重新拓扑排序；
7. `graph.validate()`；
8. 原图/优化图做 FP32 differential；
9. 记录结构化 `fusion_log`。

每个 pass 最好 transactional，失败就保留原图，不留下半更新状态。

## 11. C3.4：内存规划与调度

### 11.1 lifetime

给执行计划中每个 tensor 计算 producer/first use、last consumer、size 和 alignment。生命周期不重叠的 tensor 才能共享 slot。graph output 要活到拷回；并行 Stream 下还要考虑 event 完成，而不只是 step index。

### 11.2 memory pool

最小 pool 需要 free list，释放后可再次命中。更完整实现使用 best-fit、size class 或相邻块 coalesce。planner 输出 tensor → slot/offset 后，executor 必须真的按 plan 分配，不能仍为每个 tensor 单独 malloc。

### 11.3 权重预取

全部权重在首个 kernel 前 bulk 上传不算预取。真正语义类似：copy stream 上传下一层权重时，compute stream 计算当前层，并通过 event 建依赖。

### 11.4 多 Stream

先找无数据依赖的节点，再分到不同 compute stream，用 event 表达必要依赖。第一版全部单 Stream 保正确，第二版只并行清晰独立支路，最后再做 copy/compute overlap。

## 12. C3.5：端到端 inference

### 12.1 CLI 和输出

```bash
python infer.py \
  --onnx model.onnx \
  --input input_dir \
  --output output_dir \
  --batch-size 256
```

`--batch-size` 不能写死。读取 manifest 后验证 name/file/dtype/shape 与实际 `.npy` 和模型 input 一致。输出 `manifest.json` 和 FP32 `logits.npy`，覆盖全部 N 且保持顺序。

### 12.2 batching

```text
for start in range(0, N, batch_size):
    end = min(start + batch_size, N)
    对所有 input 切 [start:end]
    用 concrete batch 生成/实例化 plan
    执行并收集 output
沿 axis 0 concatenate
```

最后一个 batch 可能不足。shape、grid 和 memory size 必须用实际 batch。

### 12.3 correctness gate

每个模型先做：

```python
np.allclose(out, golden, rtol=1e-3, atol=1e-3)
```

MLP/ResNet 再做 top-1，分别 >=98% 和 >=85%。Transformer 没有 accuracy gate，但仍需逐元素精度通过。

调试时记录 max abs/relative error、首个失败 index 与对应值，并用中间 tensor 定位第一个偏离算子。

### 12.4 性能和显存

正确后再优化：权重只上传一次、合理 batch、内存复用、融合、async copy/compute、kernel tuning、非敏感算子降精度。正式峰值显存由 NVML 按进程和子进程采样；Mac MPS/host RSS 不能替代。时间与显存是排名分，本地绝对值不保证得分。

## 13. 三个模型的推进顺序

1. MLP：先打通 ONNX → graph → Gemm/Relu plan → manifest → golden。
2. ResNet：加入 Conv、残差、GlobalAveragePool，重点处理 NCHW、pads/strides、im2col workspace。
3. Transformer：最后加入 INT64 Gather、dynamic reshape/transpose、Split、多维 MatMul、stable Softmax、LayerNorm、Erf 和 causal mask。

## 14. 分阶段实现计划

### 阶段 A：环境和数据

1. 建 Python 3.10+ venv 和 lock；
2. 安装 NumPy/ONNX/reference runtime；
3. 三模型通过 checker/shape inference；
4. 校验 manifest、npy dtype/shape；
5. CPU reference 与 golden 对齐。

### 阶段 B：C3.1

Graph/Tensor/Node IR → ONNX loader → producer/consumer → validator/toposort → DAG JSON → 三模型与 mutation tests。

### 阶段 C：最小执行

manifest/batching → MLP 三算子 → FULL_FP32 单 Stream → MLP full data → ResNet → Transformer。

### 阶段 D：C3.2/C3.3

KernelStep/HardwareCapabilities → lowering/intermediates → valid tuning → fusion/log → differential → 获取官方 benchmark 后适配且不修改 benchmark。

### 阶段 E：C3.4/性能

lifetime slots → memory pool → weight upload → prefetch → multi-stream → remote NVIDIA correctness → profiler/NVML → 每次优化全回归。

## 15. 测试策略

### Parser/graph

- initializer 过滤；
- unnamed node 稳定 ID；
- one tensor multiple consumers；
- symbolic/unknown dims；
- graph output 直接来自 input；
- cycle/missing tensor；
- attribute types；
- deterministic JSON。

### Operator

每种 operator 测标准 shape、broadcast、axis、边界、非法输入，并对 NumPy/PyTorch/ORT reference。Conv、MatMul、Softmax、LayerNorm 最关键。

### Pass/planner

- 应匹配与不应匹配的 fusion；
- 多 consumer 安全性；
- inputs/outputs 保留；
- 优化前后 max error <=1e-3；
- lifetime 交叉/不交叉、alignment、free reuse/coalesce；
- output/weight 不被过早复用；
- stream dependency；
- final short batch。

### End-to-end

1 sample → small batch → uneven batch → full 10000；MLP → ResNet → Transformer；CPU reference → remote GPU。记录 shape、dtype、allclose、accuracy、time、peak memory。

## 16. 评分导向优先级

- P0：C3.1 10 分，接口清晰且不依赖 GPU；
- P0：C3.5 FP32 correctness，15 分门禁；
- P1：C3.2 decomposition 与 valid tuning；
- P1：C3.3 安全融合和 differential；
- P2：C3.4 memory/prefetch/streams；
- P2：C3.5 时间 25 和显存 10 的排名优化。

不要先做低精度和多 Stream。它们最容易制造难定位的精度/竞态错误，未过 gate 时性能分也无意义。

## 17. 最常见的错误

- 把 initializer 当模型输入；
- 把动态 N 固化成 10000；
- 按 node list 相邻融合，不检查 DAG consumer；
- 忽略 Gemm alpha/beta/transA/transB；
- 忽略 Conv pads/strides/dilations/groups；
- Softmax 直接 `exp(x)` overflow；
- Reshape 0/-1、Transpose perm、Split axis 处理错；
- Transformer INT64 input 被转成 FP32；
- pass 删除或改名 graph output；
- planner 做了 lifetime，但 executor 仍每 tensor malloc；
- bulk upload 却声称 prefetch；
- 多 Stream 没 event；
- 最后不足 batch 沿用完整 batch shape；
- 输出 FP16 或样本顺序改变；
- 只验证 accuracy，不验证 logits allclose；
- 使用 public golden 直接输出；
- 用 ORT/PyTorch 一行推理冒充自研调度；
- 在没有 NVIDIA/NVML 的 Mac 上声称完成正式性能测试；
- benchmark 缺失时猜测接口并声称通过。

## 18. 新手第一周清单

1. 用 Netron 或 ONNX API 查看 MLP 并手画 graph。
2. 打印三模型 opset、I/O、op histogram、initializer 数。
3. 用 reference runtime 跑一个 sample 对 golden。
4. 写 manifest loader 和 dtype/shape checker。
5. 实现 Tensor/Node/Graph 与 validator。
6. 完成 MLP，再完成三模型 DAG JSON。
7. 写 MLP Flatten/Gemm/Relu reference。
8. 打通 small/uneven batch output manifest。
9. 取得 remote NVIDIA 环境。
10. 取得缺失 benchmark 后再做正式评分适配。

## 19. 完成定义

某一能力只有在以下证据齐全时完成：CLI 遵守路径/退出码契约；graph/plan validator 通过；有正常/边界/非法测试；CPU differential 通过；public model allclose/accuracy 通过；正式 GPU 结果单独记录；性能优化后全回归；依赖可离线复现；未修改 model/golden/label/threshold/grader；`TEST_REPORT.md` 记录环境、commit、命令和结果。

## 20. 术语速查

| 术语 | 简明解释 |
|---|---|
| ONNX/opset | 模型交换格式及其算子语义版本 |
| initializer | 模型内置权重/常量 |
| DAG | 无环数据依赖图 |
| producer/consumer | 产生/使用 tensor 的节点 |
| shape inference | 推导中间 tensor shape/dtype |
| lowering | 把高层算子拆成 backend kernel steps |
| tuning params | grid/block/shared-memory 配置 |
| fusion | 多操作合成更少 kernel |
| lifetime | tensor 从产生到最后使用的区间 |
| memory pool | 管理并复用设备内存块 |
| prefetch | 当前计算时提前传后续数据 |
| Stream/Event | GPU 有序队列及其同步点 |
| logits | 模型原始输出分数 |
| allclose | 带绝对/相对容差的逐元素比较 |
| NVML | NVIDIA 显存/设备管理库 |

对 C3 来说，最正确的起点是建立隔离 Python 环境，用 reference runtime 确认三个 public model 和数据，再自己实现稳健的 C3.1 Graph IR/导出器。图没看对之前，不要进入融合、异步和低精度优化。
