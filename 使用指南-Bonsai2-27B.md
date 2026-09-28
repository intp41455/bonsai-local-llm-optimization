# Bonsai 2 27B @ RTX 5060 Laptop 8GB —— 使用指南

> 实测环境：2026-09-27 03:52~04:00
> 服务：`llama.cpp bonsai-combo`（自编译，sm_120a 原生 + 23 补丁 + MTP 嫁接）

---

## 一、当前状态（实测结论）

### ✅ 已就绪

| 项目 | 实测值 |
|---|---|
| 推理服务 | **运行中** → `http://127.0.0.1:8080/v1` |
| 健康检查 | `{"status":"ok"}` |
| 模型别名 | `bonsai-2-27b` |
| 模型元数据 | 273.2 亿参数 / `PTQ1_0 - 1.75 bpw ternary (group 128)` / 6.29 GB |
| 上下文窗口 | 32768（服务端）/ 262144（原生训练） |
| 显存占用 | 7680 MiB / 8151 MiB（吃满，正常） |
| GPU 频率 | 显存 12001 MHz、SM 2692 MHz（**锁频生效中**） |
| 端到端推理 | HTTP 200，1.75 s，**decode 49.4 t/s**，草稿接受 28/49 |
| 无损性 | 开/关 MTP greedy 输出 **3/3 逐字节一致** |
| KV 精度 | top-1 一致率 **97.93%**、KL 0.00218（官方 `kl_*.log`） |
| OpenCode 配置 | **已修正**（原为旧路线残留，见第四节） |
| 分发目录 | `D:\Bonsai-demo\dist\bonsai2-8gb-combo\`（二进制 + CUDA DLL 齐全） |

### ⚠️ 尚缺

| 项目 | 说明 | 影响 |
|---|---|---|
| 服务不自启 | 当前由我的会话挂载，会话结束可能被回收 | 需你双击 bat 自己启动（见 2.1） |
| 锁频不持久 | `nvidia-smi` 锁频**重启后失效** | 重启后需重跑 `lock_clocks.bat`（管理员） |
| Cherry Studio 未配 | 需 GUI 操作（API Key 经系统密钥加密存储，改文件无效） | 见 3.1，2 分钟可完成 |
| 无多模态 | 启动未挂 `--mmproj` | 发图会失败，纯文本模型 |

---

## 二、启动与停止

### 2.1 启动（推荐：双击）—— 按场景二选一

| 场景 | 脚本 | 窗口 | 实测速度 |
|---|---|---|---|
| 普通对话 / 追求速度 | `start_bonsai_8gb.bat` | 32768 | **62 t/s** |
| **Agent（WorkBuddy / OpenCode）** | `start_bonsai_8gb_agent.bat` | **65536** | 38.7 t/s |

```bat
:: 普通对话（默认，带 MTP 投机解码）
D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_bonsai_8gb.bat

:: Agent 长上下文（关 MTP，换双倍窗口）
D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_bonsai_8gb_agent.bat
```

启动后看到 `model loaded` + `listening on http://127.0.0.1:8080` 即就绪（约 5 秒，文件已缓存时）。

> ⚠️ **为什么 Agent 必须用 65536？**
> WorkBuddy 作为 Agent 会在**每次请求**里带上系统提示 + 全部工具定义 + 对话历史，
> 实测单次 **48937 token**，超过 32768 直接报 `exceed_context_size_error`。
> 而 MTP 投机解码的 compute buffer 在 64k 窗口下会撑爆（测速崩到 **1.67 t/s**），
> 所以长窗口配置**必须关掉 MTP**——这是 8GB 卡上唯一的取舍点。

实测对照（详见 `ctx_probe.py`）：

| 配置 | 可用 | decode | 显存 |
|---|---|---|---|
| MTP on / c32768 | ✅ | **62 t/s** | 7767 MiB |
| MTP on / c65536 | ❌ 崩 | 1.67 t/s | 7816 MiB |
| **MTP off / c65536** | ✅ | **38.74 t/s** | 7748 MiB |
| MTP off / c65536 / ngl80 | ✅ | 39.18 t/s | 7706 MiB |
| MTP off / c49152 | ✅ | 38.35 t/s | 7410 MiB |

### 2.2 一次性搞定（锁频 + 启动）

**每次开机后**按顺序执行：

```bat
:: 1. 右键 → 以管理员身份运行（重启后必须重跑）
D:\Bonsai-demo\dist\bonsai2-8gb-combo\lock_clocks.bat

:: 2. 启动服务
D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_bonsai_8gb.bat
```

> 锁频收益：decode 从 36~62 t/s 漂移 → **稳定 56~66 t/s**。不锁也能用，就是慢且不稳。

### 2.3 PowerShell 版（支持环境变量调参）

```powershell
cd D:\Bonsai-demo\dist\bonsai2-8gb-combo
.\start-bonsai.ps1
```

### 2.4 停服

```bash
taskkill /F /IM llama-server.exe
```

---

## 三、三种使用方式

### 3.1 Cherry Studio（GUI，最直观）

已安装 → 打开后：

1. **设置 → 模型服务 → 添加提供商**，类型选 **OpenAI**
2. 填写：

| 字段 | 值 |
|---|---|
| 名称 | `Bonsai 本地` |
| API 密钥 | `sk-local-no-key`（本地服务不校验，随便填非空即可） |
| API 地址 | `http://127.0.0.1:8080/v1` |

3. **添加模型** → 模型 ID 填 `bonsai-2-27b`（必须完全一致，这是服务端别名）
4. 点「检查」应显示连接成功
5. 回到对话页，顶部模型选择器切到「Bonsai 本地 / bonsai-2-27b」

> ⚠️ Cherry Studio 的 API Key 走系统密钥加密存储，**只能 GUI 里配，改配置文件无效**。

### 3.2 OpenCode（编码 Agent）

**已配好**（本次修正），provider 键 `bonsai`，模型 `bonsai-2-27b`：

```bash
# 指定模型启动
opencode --model bonsai/bonsai-2-27b

# 或在 TUI 内
/models          # 列表里选 Bonsai 2 27B
```

适合：**轻量代码任务**（写函数、改单文件、解释代码、生成测试）。
不适合：跨 10+ 文件的大型重构（27B 三元模型长链路工具调用会掉链）。

### 3.3 API 直调

**curl：**

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bonsai-2-27b",
    "messages": [{"role":"user","content":"你好"}],
    "max_tokens": 512,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

**Python（OpenAI SDK）：**

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="sk-local-no-key")

r = client.chat.completions.create(
    model="bonsai-2-27b",
    messages=[{"role": "user", "content": "用 Python 写一个快速排序"}],
    max_tokens=2048,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},  # 关思考，快
)
print(r.choices[0].message.content)
```

**开思考（默认 medium，复杂推理用）：**

```python
extra_body={"chat_template_kwargs": {"reasoning_effort": "medium"}}
```

> 关键：**medium 思考只在生成上限 ≥20k 时才有优势**，短上限下比关思考更差。日常问答用 `enable_thinking: false`。

**其他端点：**

| 端点 | 用途 |
|---|---|
| `GET /health` | 健康检查 |
| `GET /v1/models` | 模型列表 |
| `GET /metrics` | Prometheus 指标 |
| `POST /v1/chat/completions` | 对话（OpenAI 兼容） |
| `POST /completion` | 原生补全 |

---

## 四、本次修正的配置问题

`C:\Users\intpj\.config\opencode\opencode.jsonc` 里的 `bonsai` provider 是**旧路线残留**，已修正：

| 字段 | 修正前 | 修正后 |
|---|---|---|
| 模型 ID | `bonsai-27b` ❌ 与服务端别名不匹配 | **`bonsai-2-27b`** |
| 名称 | `ternary PQ2_0 + kvmem`（已淘汰路线） | `PTQ1_0 ternary + MTP` |
| context | 8192 | **32768** |
| output | 4096 | **24576** |
| `attachment` | `true` ❌ 未加载 mmproj | 已移除 |

备份：`opencode.jsonc.bak-before-bonsai-fix-20260927-035657`

---

## 五、参数速查

`start_bonsai_8gb.bat` 里的黄金配置，**不要随意改动这几项**：

| 参数 | 值 | 原因 |
|---|---|---|
| `--spec-draft-n-max` | **1** | 8GB 实测最优：K=1 → 62 t/s，K=2 → 45 t/s |
| `--spec-draft-depth-max` | **4096** | 官方 24576 不适用 8GB；>5k 深度草稿变负收益 |
| `-c` | **32768** | 硬上限，40960 会因 MTP compute buffer OOM 崩到 2 t/s |
| `-ctk/-ctv` | **q4_0** | KV 量化，省显存 |
| `--kv-mean-center` | **绝对不要加** | 属 kvmem 路线，与 MTP 互斥，会让接受率崩到 0.000 |
| `GGML_CUDA_BATCH_INVARIANT` | **1** | MTP 严格无损开关 |

环境变量覆盖（PowerShell 版）：`BONSAI_CTX` / `BONSAI_PORT` / `BONSAI_THINK` / `BONSAI_EFFORT` / `BONSAI_SPEC` / `BONSAI_SPEC_DEPTH`

---

## 六、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 连接被拒 | 服务没起 | 跑 `start_bonsai_8gb.bat` |
| `model not found` | 模型 ID 写错 | 必须写 `bonsai-2-27b` |
| GPU 利用率显示 0 | 任务管理器默认显示 "3D" 引擎，**CUDA 不计入** | 点图表上的 "3D" → 切换为 **"Cuda"** |
| 速度为 30 多 t/s | 锁频失效（重启后） | 管理员跑 `lock_clocks.bat` |
| 显存不足 / 崩 | context 超 32768 | 改环境变量 `BONSAI_CTX=16384` |
| 输出乱码 / 重复 | 温度过高 | 已是 `temp 1.0 / top-p 0.95 / top-k 20`，勿再调高 |

---

## 七、相关文件

| 路径 | 内容 |
|---|---|
| `D:\Bonsai-demo\dist\bonsai2-8gb-combo\` | 分发目录（二进制 + 脚本） |
| `D:\Bonsai-demo\serve.py` | Python 启动器（`--smoke` 冒烟测试 / `--stop` 停服） |
| `D:\Bonsai-demo\Bonsai2-27B-8GB部署交付报告.md` | 完整部署报告（7 章） |
| `D:\Bonsai-demo\提示词模板与调参手册.md` | 提示词工程与参数调优（6 章） |
| `D:\Bonsai-demo\surgery\` | 官方补丁集 + 基准脚本 + 质量证据 |
| `~\.workbuddy\skills\ternary-gguf-8gb-deploy\SKILL.md` | 可复用技能（8 章） |
