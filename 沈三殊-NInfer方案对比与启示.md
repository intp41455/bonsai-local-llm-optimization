# 沈三殊 / NInfer 方案 vs 本机 llama.cpp 方案 · 对比与启示

> 资料来源（陛下 2026-09-26 提供）：
> 1. <https://ergeaia.github.io/aivault-site/docs/> —— AI Vault 工具文档（本地引擎=llama.cpp 的参数手册）
> 2. <https://www.modelscope.cn/models/shensanshu/ninfer-ada-ternary> —— 沈三殊的 NInfer on Ada 移植（4 篇工程文档 + patches）
> 3. <https://www.bilibili.com/opus/1251702496856899585> —— 「12G 显存跑 256K 上下文」（tancau/ninfer-kvmem-ring 的 ring KV 实战）
>
> 归档时间：2026-09-26

---

## 一、最重要的一件事：**NInfer 和 llama.cpp 是两套完全不同的引擎**

我们本机装的是 **llama.cpp（PrismML fork）**，跑 **GGUF**（PQ2_0）。
沈三殊装的是 **NInfer**，跑 **`.ninfer`** 原生制品。

| | **我们（llama.cpp / PrismML fork）** | **沈三殊（NInfer on Ada）** |
|---|---|---|
| 引擎 | llama.cpp fork，`llama-server` | NInfer（C++20/CUDA 自研引擎，独立于 llama.cpp） |
| 模型格式 | **GGUF**（`PQ2_0`，7.2 GB） | **`.ninfer`**（7.74 GB / 文本 6.696 GiB） |
| 硬件 | RTX 5060 Laptop **8 GB**（sm_120 Blackwell） | RTX 4080 SUPER（**sm_89 Ada**） |
| 解码速度 | **11–14 t/s** | **62–64 t/s**（纯解码）/ **96.7–130.8 t/s**（MTP K=2） |
| prefill | 359–368 t/s | **356–439 t/s** |
| 上下文 | 16K（我们定的） | 160K dense / **256K**（ring 模式） |
| 投机解码 | ❌ 无官方 drafter | ✅ **拼了 Qwen3.8 的 MTP 头**（K=2 接受率 59.4%） |
| 质量 | 98.2%（官方三元口径） | PPL 6.445（黄金参照 6.8196）、20 题基准 19/20 |

**NInfer 快 5–10 倍**，而且它把 MTP 头拼进了三元制品——这是「负收益 → 正收益」的转折点（没有它就只有 62 t/s 裸解码）。

---

## 二、「kvmem」这个词有两层含义 —— 必须分清

这是我们之前理解偏差的地方。

| | **PrismML 的 kvmem**（我们装的） | **沈三殊 / tancau 的 KVMem**（他们做的） |
|---|---|---|
| 是什么 | **4-bit KV cache**（`BONSAI_KV4=1` → `-ctk q4_0 -ctv q4_0`） | **KV 分层存储架构**：设备池 + 主机内存溢出 + 按需召回 |
| 类比 | 把 KV 压缩后仍全放显存 | **操作系统的虚拟内存 + 按需调页** |
| 效果 | KV 显存 64 → 18 KiB/token（3.5x） | 12 GB 卡跑 256K 上下文（设备池只 96K） |
| 质量代价 | KLD 0.001496 → **0.00129**（加校准偏置后，−14%） | **PPL 与 dense 逐 bit 一致**（delta = 0） |
| 加分项 | 可配 **mean-centering 偏置**校准 | 用 **IDF 词法检索**替代原版 mean-K 打分 |

**两者共享同一个技术源头（mean-K / mean-centering）**——PrismML 的工具就叫 `llama-kv-mean-center`。
所以叫法相同不是巧合：KVMem 是更大的概念，PrismML 只取了其中「居中偏置」这一小块，tancau 取了完整的「ring + 主机下沉」架构。

> tancau 仓库（<https://github.com/tancau/ninfer-kvmem-ring>，Apache-2.0）实测：
> RTX 3060 12GB / 96K 设备池 / 256K 逻辑上下文，**PPL 5.639521 与 dense 小数点后 6 位全同**，
> HumanEval+ 152/164 = 92.68%，NIAH 64K = 0.9591，能效 0.521 mWh/token。
> 他的三个开关：`NINFER_KV_RING=1` / `NINFER_KV_RETRIEVE=12288` / `NINFER_HOST_PAGEABLE=1`。

---

## 三、陛下的 8 GB 卡能上 NInfer 吗？—— **现在不能**

三重门槛：

| 门槛 | 现状 | 判断 |
|---|---|---|
| **显存** | NInfer 制品 7.74 GB，tancau 实测运行时 **10.2 GB / 12 GB 卡** | ❌ 我们只有 8 GB（可用 ~7.2 GB） |
| **架构** | 沈三殊的移植是 **sm_89（Ada）**，tancau 是 **sm_86** | ❌ 我们是 **sm_120（Blackwell）**，两个都不能直接用 |
| **上游匹配度** | `Neroued/ninfer` 上游针对 **sm_120a（RTX 5090）** | ⚠️ 架构对得上，但需自己从源码编译，且 8 GB 仍装不下 27B |

**结论**：NInfer 路线需要 **≥12 GB 显存**才能跑起 27B。陛下这台是 8 GB，NInfer 上不了。
我们现在这套（llama.cpp fork + 8 GB + kvmem）是**这个硬件下能跑通的最优解**。

> 若将来换卡（≥16 GB）或攒一台，NInfer 才是值得上的下一级台阶。

---

## 四、可以立刻用在陛下这套上的三条启示

### 启示 1：KV 量化 q4_0 vs q8_0 —— 我们被 kvmem 锁死了

AI Vault 的 llama.cpp 参数手册里，**KV 缓存 K 的默认值是 `q8_0`**，说明是「q8_0 相比 f16 省一半显存、质量损失极小」。
而我们用的是 **q4_0**（更激进，省 3.5x）。

**但这里有个硬约束**（实测确认）：

```
--kv-mean-center ... requires --cache-type-k q4_0 (see docs/kv-mean-center.md)
```

**`--kv-mean-center` 强制要求 `-ctk q4_0`。** 换 q8_0 就必须放弃校准偏置。所以是个二选一：

| 方案 | KV 显存 @16K | 质量 | 说明 |
|---|---|---|---|
| **A（当前）**: q4_0 + 校准偏置 | ~288 MB | KLD 0.00129 | 偏置已校准好，已验证加载 |
| B: q8_0 无偏置 | ~512 MB（+224 MB） | 理论更好（8bit） | 但要放弃偏置，且余量从 1000 降到 ~780 MiB |

**暂不改动。** 方案 A 是官方指定的组合（偏置只能在 q4_0 基下用），且已在悬崖边留了安全余量。
如果想验证 B，需要实测 PPL 对比——属于可选优化。

### 启示 2：投机解码 —— 我们暂时用不了

沈三殊的核心提速手段是**把 Qwen3.8-27B 自带的 MTP（NextN）头拼进三元制品**，用投机解码把 62 t/s 拉到 96.7–130.8 t/s。

**我们这边走不通**，原因：
- PrismML 的 `BONSAI_SPECULATIVE=1` 只支持**上一代** `ternary`/`bonsai` 27B（配套 DSpark drafter）
- **Bonsai 2 27B 没有官方 drafter**，官方明确说「its family launcher warns and runs without speculation」
- GGUF 里也没有 NextN 张量可供借用

> ⚠️ 这解释了速度差距的一大半：**不是我们的卡不行，是这条引擎线还没把 drafter 准备好。**

### 启示 3：AI Vault 的参数手册可以直接当调参参照

它把 llama.cpp 的参数分成了 **23 个分组、数百项**，且**默认值都是调好的**。几个跟我们配置对得上的：

| 参数 | AI Vault 默认 | 我们当前 | 评价 |
|---|---|---|---|
| `--ctx-size` | 32768（**8GB 以下建议 4096–8192**） | 16384 | ✅ 靠 kvmem 撑住了 |
| `--cache-type-k` | q8_0 | q4_0 | ⚠️ 见启示 1 |
| `--flash-attn` | auto | on | ✅ |
| `--fit` / `--fit-target` | auto / **1024 MiB** | 手动 `-ngl 52` | ✅ 等价（我们手动留了 ~1000 MiB 余量） |
| `--reasoning` / `--reasoning-budget` | auto / -1 | `-rea on --reasoning-effort medium` | ✅ 更细粒度 |
| `--kbatch-size` / `--batch-size` / `--ubatch-size` | 2048 / 512 | 默认 | 可试 2048 提 prefill |
| `--temperature` | 0.80（**思考类模型建议 0.60**） | 1.0（模型卡口径） | 模型卡优先 |

---

## 五、附：NInfer 移植的技术要点（备查）

### 5.1 三元格式（与 ggml 逐字一致）
| 格式 | group | base/组 | high/组 | scale/组 | 合计 |
|---|---:|---:|---:|---:|---:|
| `PTQ1_0_G128` | 128 | 24 B (`qs[24]`) | 2 B (`qh[2]`) | 2 B (`d`) | **28 B/128** |
| `PQ2_0_G128` | 128 | 32 B (`qs[32]`) | 0 | 2 B (`d`) | **34 B/128** |

- `PQ2_0`：`code = (qs[j>>2] >> (2*(j&3))) & 3`，值 `= (code − 1) · d`（码本 {−1,0,+1,+2}）
- Hadamard 旋转完整序列是 **P → s → H**（块宽 1024 的归一化 Sylvester–Walsh–Hadamard + 符号向量 + 置换）
- **正向**：`y = W'·(H·(s ⊙ (P·x)))`

### 5.2 微调 → NInfer 的链路（**这条修正了我之前的结论**）
NInfer 自带 `tools/convert/` 配方框架，按架构分目录（`qwen3_6_27b` / `qwen3_8_27b` / `qwen3_6_35b_a3b`）：
```bash
python -m tools.convert.qwen3_8_27b.convert --model <SRC> --dflash2-model <D> --out <OUT>.ninfer --device cuda
```
- **只要是这些骨架的微调/去审/融合版（架构不变），就能直接转，零引擎改动**
- 实测：RTX 4080 SUPER / Windows，转一个 27B 去审微调版 **114.2 秒**，产物 18.21 GB
- ⚠️ 但**训练**仍是大显存活儿（本机 8 GB 不可能）

**⇒ 结论修正**：在 **NInfer 路线**下，「微调模型 → 本地跑」是**完整闭环**（转换只要 2 分钟）。
在 **GGUF 三元路线**下才有障碍（需要 PrismML 未公开的三元赋值算法）。
两条路的难度差在这里，不在训练本身。

### 5.3 值得抄的方法学（docs/04 工程实录）
- **「搬运无损」类判据对偏移错误完全盲** —— 必须加分布指纹旁证
  - `zero_share` 精确 = **0.3278**（PQ2_0 理论零码占比）是格式指纹
  - scale 高位字节种数应 11~32/256（偏移错误时会接近 250/256）
- **任何 GEMM/布局改动必须有 T>1 用例，且在引擎侧验证**（T=1 时两种排布重合，全绿也测不出错）
- **行级比对必须比「多重集」+ 直接比对**，不能「搜第一个匹配」
- **负控必须存在**；对照组全零是方法失效信号，不是结论
- **端到端数值口径用 PPL**（正确个位数~十几，错则几百）
- 已否定路线：离线把旋转折回权重（`W` 变稠密浮点，不再三值可表示）

### 5.4 AI Vault 的本地模型评测提示词（可直接拿来测我们的机器）
涵盖 9 类：冒烟+性能、数学算数、知识与幻觉、指令遵循、工具调用、多轮记忆、拒答尺度、代码修复、前端图形生成、长上下文 NIAH。
经典题：鹈鹕骑自行车 SVG、递归分形树、Boids 群体模拟、A* 寻路、落沙元胞自动机、Minecraft 体素世界、贪吃蛇 bug 最小 diff 修复。
