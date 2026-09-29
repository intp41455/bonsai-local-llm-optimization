# Bonsai: 本地大模型推理网关与长上下文工程优化实验

> 💡 **工程概览**：在 RTX 5060 Laptop 8GB 上探索 27B 模型的 64k 上下文推理。网关以 56,320 tokens 为输入预算，结合请求预筛、增量 SSE 解析和异常观测；指定测试集中的超限请求均被拦截。文中速度数据对应各自的测试配置，并非所有任务的统一吞吐。
> ⚡ **8GB 显存与 64k 上下文** ｜ 📐 **56k 输入预算** ｜ 🛡️ **Reject+Floor 预筛** ｜ 🔄 **SSE 增量解析** ｜ 🎯 **异常链路观测**

[![Cloudflare Pages Docs](https://img.shields.io/badge/Docs-Cloudflare%20Pages-orange?style=flat-square&logo=cloudflare)](https://bonsai-optimization.pages.dev/)
[![Hardware](https://img.shields.io/badge/Hardware-RTX%205060%20Laptop%208GB-76B900?style=flat-square&logo=nvidia)](https://bonsai-optimization.pages.dev/)
[![Model](https://img.shields.io/badge/Model-Bonsai--2--27B%20(Ternary%2FPQ2)-blueviolet?style=flat-square)](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)
[![Context](https://img.shields.io/badge/Context-65%2C536%20Tokens-blue?style=flat-square)](https://bonsai-optimization.pages.dev/)
[![Throughput](https://img.shields.io/badge/Throughput-18~20%20token%2Fs-success?style=flat-square)](https://bonsai-optimization.pages.dev/)

面向消费级算力设备（NVIDIA RTX 5060 Laptop 8GB VRAM）部署 27B 参数级大语言模型、开启 64k（65,536 tokens）超长上下文并保障服务稳定性的系统级优化实验。

本项目完整记录并沉淀了从**启动器冲突排查、流式传输断流优化、探活防误杀到 56k 空间硬预算、Reject+Floor 两级预筛闸门与客户端异常观测（G1~G15 演进）**的完整技术链路与实测记录。

---

## 🌐 线上技术架构与交互式全流程复盘手册

交互式技术手册已上线，欢迎查看与参考：
👉 **[https://bonsai-optimization.pages.dev/](https://bonsai-optimization.pages.dev/)**

![Bonsai 架构与工程全景](docs/images/docs_preview.png)

---

## 1. 业务痛点与硬件物理瓶颈

在单张消费级显卡（8GB VRAM）上承载 27B 思考型大模型并开启 64k 上下文，面临严苛的物理资源挤压：

1. **静态权重显存刚性占满**：采用混合量化/三值化（Ternary/PQ2）后，模型静态权重占用约为 **6.15 GB**；
2. **动态显存预算极度逼仄**：系统与宿主桌面渲染底噪占用约 0.4 GB，留给推理上下文（KV Cache + Scratch Workspace）的物理显存仅剩 **1.45 GB**；
3. **KV Cache 显存激增风险**：若不加约束直接打入 60k+ 历史上下文，KV-Cache 极易引发 CUDA OOM 导致推理后端崩溃；
4. **单槽位并发争抢与排队**：为确保 64k 上下文安全，底层推理后端固定为单槽位（`-np 1`）。多客户端并发请求排队时极易触发客户端超时；
5. **增量流式传输的跨网络断流**：在边缘环境及长链路下，缺乏状态机防护的 SSE 分块极易在多字节 UTF-8 字符处截断，引发客户端 JSON 语法解析致命错误。

---

## 2. 系统核心架构：生产双层解耦拓扑

系统解耦了“底层算力推理加速”与“上游网关流量治理”，构建了双层反向代理拓扑：

```mermaid
flowchart TD
    A["API 客户端 / IDE"] --> B["Bonsai 网关 :8080"]
    B --> C["输入预算预筛"]
    C --> D["请求转发"]
    D --> E["模型推理 :8081"]
    E --> F["SSE 解析与响应"]
```

图中展示请求主路径；下方文字框图列出预算阈值、接口端口和流式处理细节。

```
[OpenAI API 客户端 / IDE / 多智能体框架]
         │
         ▼  HTTP / SSE 流式传输
┌───────────────────────────────────────────────────────────────┐
│ Bonsai Proxy (反向代理网关服务，端口 8080)                    │
│ 文件：proxy/bonsai_proxy.py                                    │
│                                                               │
│ ├── 1. 空间硬预算与 Reject+Floor 两级预筛                     │
│ │    ├── 字符级地板粗筛 (chars_floor = 1.5, 约 0.3ms 拦截)     │
│ │    └── 严格 Token 预算预估 (56,320 上限，约 1.2ms 拦截)      │
│ ├── 2. 上下文结构瘦身与提示词净化 (Prompt Sanitization)        │
│ ├── 3. 独立增量 SSEParser 流式状态机                          │
│ │    └── 多字节 UTF-8 安全拼接、Keep-Alive 周期心跳保活       │
│ └── 4. 客户端异常感知与全链路追踪 (ClientDisconnect 观测)      │
└───────────────────────────────────────────────────────────────┘
         │
         ▼  Unix Socket / Localhost 纯净代理转发
┌───────────────────────────────────────────────────────────────┐
│ llama-server (底层推理加速内核，端口 8081)                    │
│                                                               │
│ ├── 模型权重：Bonsai-2-27B (PQ2_0 / Ternary)                  │
│ ├── 显卡卸载：-ngl 99 (RTX 5060 Laptop 8GB 全层卸载)           │
│ ├── 槽位隔离：-np 1 (单发并发槽位，物理杜绝 OOM 争抢)          │
│ └── 显存驻留：静态权重 6.15GB + 运行时 KV Cache ≈ 7.88GB      │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. 关键核心工程突破与机制设计

### 3.1 56k 空间硬预算推导 (Hard Budget Mechanism)

* **设计上下文总窗口**：65,536 tokens；
* **推理生成预留空间**：思考型大模型思考链与最终回答预留 **8,192 tokens**；
* **安全冗余缓冲**：预留 **1,024 tokens** 应对分词器误差、系统特殊标记（Special Tokens）与会话包裹开销；
* **网关准入红线推导**：
   **输入预算 = 65,536 − 8,192 − 1,024 = 56,320 tokens。**
  输入超过 56,320 tokens 的请求在网关层即行拦截，避免超额请求进入 GPU 阶段引发显存崩溃。

### 3.2 Reject + Floor 双重动态预筛闸门 (Two-Stage Gate)

针对长上下文分词计算本身占用 CPU 与阻塞事件循环的瓶颈，设计两级拦截流水线：

```
[传入请求 messages]
        │
        ├─► 第一级：字符地板拦截 (Chars Floor Check)
        │      prompt_chars = len(messages_text)
        │      floor_budget = 56,320 × 1.5 = 84,480 字符
        │      若 prompt_chars > 84,480：
        │          └── 立即在约 0.3ms 内返回 HTTP 400（免除分词开销）
        │
        └─► 第二级：高精度分词校验 (Accurate Token Budget Check)
               计算准确 token 数量 (耗时约 1.2ms)
               若 estimated_tokens > 56,320：
                   └── 返回标准化 OpenAI 错误载荷：context_length_exceeded
```

### 3.3 无损增量 SSE 流式解析状态机 (SSEParser)

为解决长上下文下的分块截断问题，手写非阻塞流式增量解析器：
* 维护多字节 UTF-8 字符跨 chunk 缓冲区，消除乱码风险；
* 标准化提取 `delta.content` 与 `delta.reasoning_content`，兼容 OpenAI SDK 与下游智能体框架；
* 内置 Keep-Alive 周期性空帧保活，防止反向代理因超时强制掐断长连接。

### 3.4 客户端异常与 400 Bad Request 全链路观测 (G15 封版)

针对生产环境下客户端因超时或取消发送提前断开（ClientDisconnect）的痛点：
* 在代理层中引入 `asyncio.shield` 保护核心状态更新，同时捕获客户端连接重置；
* 记录请求耗时、prompt token 数、生成 token 数、网络状态码与拦截原因；
* 提供统一的排障日志与监控埋点，实现异常链路可追溯。

---

## 4. 关键压测性能与硬件实测指标

在 NVIDIA GeForce RTX 5060 Laptop（8GB VRAM / 驱动版本 572.16 / CUDA 12.8）物理硬件上的实测基准数据：

| 评估指标 | 实测表现 | 优化前基线 / 行业默认方案 | 工程改善效果 |
| :--- | :--- | :--- | :--- |
| **显存峰值占用** | **7.88 GB** | 8.00 GB（直接爆显存 CUDA OOM） | 稳定受控在物理上限之内 |
| **实测可用上下文** | **65,536 Tokens (64k)** | 仅能维持 8k~16k | **有效提升 400%~800%** |
| **长上下文生成速度** | **18.2 ~ 20.4 token/s** | 频繁内存交换下降至 1~2 token/s | **纯 GPU 显存内高效推理** |
| **超长输入拦截率** | **100.0%** (指定压力测试集) | 0%（直接击穿后端引发服务宕机） | **测试集内全部超限请求拦截成功** |
| **网关拦截平均延迟** | **0.3 ms** (字符预筛) / **1.2 ms** (Token校验) | > 800 ms（请求完全发送至后端后报错） | **请求拦截开销显著降低 99.8%** |

---

## 5. 项目工程结构

```
Bonsai-demo/
├── proxy/                          # 高性能反向代理核心
│   ├── bonsai_proxy.py             # 核心网关：预算控制、Reject+Floor 闸门、SSEParser
│   ├── config.json                 # 生产配置：56,320 预算阈值与端口映射
│   └── test_proxy.py               # 网关端到端测试与容灾演练
├── docs/                           # 架构设计与复盘报告沉淀
│   ├── images/                     # 系统架构图与文档高清预览图
│   │   └── docs_preview.png
│   ├── Bonsai-2-27B-最优操作手册.md # 生产级启动与维护 SOP
│   ├── Bonsai2-27B-8GB部署交付报告.md# 8GB 显存极限压榨交付验收报告
│   └── 蓝屏事故与防范复盘-2026-09.md # Windows 底层驱动稳定性排障复盘
├── docs-web/                       # 在线知识库网页源码 (暖色淡色雅致版)
│   └── index.html                  # 交互式技术全景文档站 (已上线 Pages)
├── bench/                          # 基准测试与压力评测工具集
│   ├── bench_final2.py             # 64k 长上下文吞吐与时延评测
│   └── multiturn_test.py           # 多轮对话与并发压力验证
├── config/                         # 推荐运行参数与模型配置
├── launcher/                       # 一键式守护进程与自启动控制脚本
├── .gitignore                      # 工业级代码与大文件隔离配置
└── README.md                       # 本工程主说明文档
```

---

## 6. 快速开始与使用指南

### 6.1 运行环境要求
* **操作系统**：Windows 11 / Linux (Ubuntu 22.04+)
* **硬件配置**：NVIDIA GPU (>= 8GB 显存，推荐 RTX 4060/5060 Laptop 及以上)
* **驱动与工具链**：CUDA 12.4+ / 12.8，Python 3.10+

### 6.2 启动服务
1. **启动底层推理内核 (llama-server)**：
   ```bash
   llama-server -m models/bonsai2-27b-pq2.gguf      --host 127.0.0.1 --port 8081      -ngl 99 -c 65536 -np 1
   ```

2. **启动 Bonsai Proxy 治理网关**：
   ```bash
   python proxy/bonsai_proxy.py --port 8080 --backend-port 8081 --budget 56320
   ```

3. **客户端接入（兼容标准 OpenAI 接口）**：
   ```python
   from openai import OpenAI

   client = OpenAI(
       base_url="http://127.0.0.1:8080/v1",
       api_key="bonsai-local"
   )

   response = client.chat.completions.create(
       model="bonsai2-27b",
       messages=[{"role": "user", "content": "请分析长上下文架构中的显存预算控制策略。"}],
       stream=True
   )

   for chunk in response:
       if chunk.choices[0].delta.content:
           print(chunk.choices[0].delta.content, end="", flush=True)
   ```

---

## 7. 架构工程权衡与反思 (Engineering Trade-offs)

1. **为什么当前配置不采用动态内存交换（Offload to RAM）？**
   在移动端设备上，频繁的 CPU–GPU 权重与 KV 交换会增加传输开销。本项目优先使用量化权重和输入预算控制，减少运行时显存压力；是否采用 offload 仍应按具体模型、上下文长度和硬件实测比较。
2. **为什么在网关层执行 Reject 而非由后端自行排队截断？**  
   底层推理引擎一旦接收超额 prompt，其内部的 prefill 计算会瞬间拉高 Scratch 缓冲区显存，可能产生数秒的 GPU 阻塞。网关层通过约 0.3ms 字符地板粗筛与 1.2ms 分词闸门，将风险隔离在算力之外。

---

## 8. 开源协议

仓库采用 [Apache License 2.0](LICENSE)；引用第三方模型、依赖或素材时，请分别遵循各自的许可。

---

## 9. 后续优化与验证状态

多轮会话的前缀复用、推理内核适配和任务级质量仍在持续验证。不同配置的速度样本不能直接当作同一生产配置的交付指标。

- **当前任务基线**：本地固定的 12 项任务各运行 3 次，30/36 次运行通过；失败集中在任务 8 和任务 12。任务 8 涉及 SVG 属性错误，任务 12 涉及日志错误码漏报。统计口径为完整任务通过次数。
- **前缀复用与内核适配**：保留为独立研究方向；只有在固定模型、输入、配置和硬件下完成对照，才将结果写为可复现的性能结论。
- **MTP 投机解码**：当前生产配置保持关闭。已有对照中，关闭 MTP 的任务完成速度更好；不将早期单次最高 token/s 宣称为现行生产吞吐。
- **质量门禁**：任务 8/12 的候选修复仍需端到端完成及全量回归，尚未达到 12/12 任务通过。
