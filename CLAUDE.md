# CLAUDE.md

Guidance for AI agents working in this repository.

## 1. Project purpose

Bonsai-demo is an **experiment in running a 27B reasoning LLM with 64k (65,536)
token context on an 8 GB consumer GPU** (NVIDIA RTX 5060 Laptop). The focus is
**stability and memory budgeting**, not raw speed.

The repo contains:

- A Python reverse-proxy gateway (`proxy/bonsai_proxy.py`) that enforces an input
  token budget before requests reach the inference backend, plus streaming
  (SSE) hardening and per-request observability.
- A single-source-of-truth launcher (`launcher/bonsai_launcher.py` +
  `config/bonsai-agent.json`) that manages the `llama-server` backend and the
  proxy, so no two start scripts can disagree on backend flags.
- A 12-task local benchmark harness (`bench/`) that drives fixed tasks through
  the live proxy and records pass/fail + timing data.
- A vendored Windows `llama-server` bundle with CUDA (`dist/bonsai2-8gb-combo/`,
  `bundle/`, `hybrid-test/`) and model weights under `models/` (both gitignored).
- Extensive docs, delivery reports, and timestamped optimization records
  (G1~G15) under `docs/`, root-level `.md` files, and `optimization/`.

Key measured numbers (README §4, RTX 5060 Laptop 8 GB, CUDA 12.8):

- Peak VRAM 7.88 GB (no OOM), 65,536 usable tokens, 18.2–20.4 tok/s at long
  context, 100% rejection of over-budget prompts from the test set, gateway
  interception in ~0.3 ms (chars) / ~1.2 ms (token count).

## 2. Tech stack

- **Language**: Python 3.10+ (proxy, launcher, bench harness, tests). No
  framework — stdlib `http.client` / `urllib` for the proxy; `unittest` for
  tests.
- **Inference backend**: a `llama-server` binary (llama.cpp fork, PrismML)
  prebuilt for Windows x64 + CUDA 13. The binary and its DLLs live under
  `dist/bonsai2-8gb-combo/bin/`, `bundle/bin/`, and `hybrid-test/`. The repo
  does **not** build llama.cpp from source here — `src/llama/` (gitignored) is
  a reference checkout.
- **Model**: `Ternary-Bonsai-2-27B` (PTQ1_0 / PQ2_0 ternary-quantized GGUF),
  weights downloaded into `models/bonsai2-gguf/27B/` (gitignored, *.gguf).
- **OS**: Windows 11 (primary, per `state/launcher_state.json` and
  `config/bonsai-agent.json` absolute paths); the proxy is also exercised on
  Linux.
- **No package manifest** (no `requirements.txt` / `pyproject.toml` / `setup.py`)
  at the repo root — the tracked Python code is stdlib-only.
- **Docs web**: static HTML under `docs-web/` (deployed to Cloudflare Pages).

## 3. Directory structure

```
Bonsai-demo/
├── README.md               # 主说明：架构、预算推导、压测数据、工程结构
├── AGENTS.md               # 给 AI 代理的调参/行为指南（flag 含义、实测结论）
├── LICENSE                 # Apache 2.0
├── .gitignore              # models/、dist/、logs/、capture/、*.gguf 等不入库
│
├── proxy/
│   └── bonsai_proxy.py     # 核心网关：预算闸门、SSEParser、分档超时、每请求日志
├── config/
│   └── bonsai-agent.json   # 唯一权威配置（后端+代理+思考档位+超时+状态）
├── launcher/
│   └── bonsai_launcher.py  # up/status/smoke/prewarm/stop，只按 state 里核对过的 PID 操作
├── state/
│   └── launcher_state.json # 运行时 PID + config fingerprint（launcher 写）
│
├── bench/
│   ├── bench_harness.py    # 单任务执行（--run-dir … --task N）
│   ├── check_tasks.py      # 单任务验收
│   ├── run_all.py          # 批量驱动 12 任务，结果写 results.jsonl
│   ├── fixtures/           # 任务输入文件
│   ├── runs/               # 每次运行的工作目录（gitignored）
│   └── results*.jsonl      # 历次运行结果（G5~G13 各一档）
│
├── tests/                  # unittest：MLX seed、Open WebUI seed、4 个 MCP 工具
│
├── scripts/
│   ├── start_llama_server.sh / .ps1   # 后端启动（BONSAI_* 环境变量见 AGENTS.md）
│   ├── start_mlx_server.sh            # Apple Silicon 路径
│   ├── start_openwebui.sh             # Open WebUI 前端
│   ├── openwebui/                     # MCP 工具（tool_sql、tool_weather、
│   │                                  #   tool_web_fetch、tool_code_interpreter）
│   └── agent/                         # 代理演示（hermes_z.py、daemonize.py 等）
│
├── docs/                   # 架构手册、8GB 交付报告、蓝屏复盘（中文）
├── docs-web/               # 交互式 HTML 文档站（已部署 Cloudflare Pages）
├── optimization/           # G1~G15 各阶段变更记录（带时间戳的子目录）
│
├── dist/                   # 预构建 llama-server 发行物（gitignored）
├── bundle/                 # Windows + CUDA 运行包（gitignored）
├── hybrid-test/            # 混合精度测试二进制（gitignored）
├── models/                 # GGUF 权重（gitignored；*.gguf）
├── capture/                # 请求抓包 req_*.json（gitignored）
├── logs/                   # requests.jsonl 等运行日志（gitignored）
└── surgery/                # 早期 CUDA 排障工具集
```

Note: `README.md` §5 lists a slightly older layout (e.g. `proxy/config.json`
and `bench/bench_final2.py`); the canonical layout is the one above. When
something seems missing, trust the tree, not the README diagram.

## 4. Install / run / test

All paths in `config/bonsai-agent.json` and `state/launcher_state.json` are
**absolute Windows paths** rooted at `D:\Bonsai-demo`. If the repo is checked
out elsewhere, update those two files before running.

### 4.1 Prerequisites

- Windows 11, NVIDIA GPU with ≥ 8 GB VRAM, CUDA 12.4+ (the `dist` bundle ships
  CUDA 13 DLLs; the tested machine used CUDA 12.8).
- Python 3.10+ on PATH (the config pins a specific interpreter; adjust
  `"python"` in `config/bonsai-agent.json` if yours differs).
- `llama-server.exe` and its DLLs under `dist/bonsai2-8gb-combo/bin/`
  (prebuilt — not part of the repo, downloaded separately).
- Model weights at `models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-*.gguf`
  (from https://huggingface.co/prism-ml — no token needed).

### 4.2 Run

The **only supported entry point** is the launcher. It reads
`config/bonsai-agent.json` and spawns both processes, so flags cannot drift:

```powershell
# From repo root (D:\Bonsai-demo)
python launcher\bonsai_launcher.py up            # 后端 :8081 + 代理 :8080，完成后预热一次
python launcher\bonsai_launcher.py status        # 查看 PID、端口、fingerprint
python launcher\bonsai_launcher.py smoke         # 一次有限输出冒烟推理
python launcher\bonsai_launcher.py stop          # 只按 state 里核对过的 PID 停止
```

The proxy listens on **:8080** and exposes an OpenAI-compatible API
(`http://127.0.0.1:8080/v1`); the backend on **:8081**.

Quick check that both are up:

```powershell
curl -s http://127.0.0.1:8080/props | python -m json.tool | Select-Object -First 30
```

### 4.3 Use the gateway

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="bonsai-local")
resp = client.chat.completions.create(
    model="bonsai-2-27b",
    messages=[{"role": "user", "content": "…"}],
    stream=True,
)
```

Per-request budget gate (56,320 token input ceiling) is enforced by the proxy;
over-budget requests return a standardized OpenAI `context_length_exceeded`
error **before** any GPU work.

### 4.4 Test

Two independent test suites:

**a) Unit tests** (no GPU / no running server required):

```powershell
python -m unittest discover -s tests
```

Covers the Open WebUI MCP tool scripts (`tool_sql`, `tool_weather`,
`tool_web_fetch`, `tool_code_interpreter`) and the MLX/Open WebUI seed
scripts.

**b) End-to-end task bench** (requires the launcher to have started backend +
proxy, and a model loaded):

```powershell
# 全量 12 任务（串行，后端 -np 1，每任务 3 轮），结果写 bench/results.jsonl
python bench\run_all.py B

# 单任务 + 单轮快速验证
python bench\bench_harness.py --run-dir bench\runs\B --task 2
```

Current baseline (README §9): 30/36 runs pass; failures concentrate on task 8
(SVG attribute) and task 12 (log error-code miss).

The proxy's own offline tests (simulated SSE upstream, no second model
process) live under `optimization/<timestamp>/tests/` for each G-stage.

### 4.5 What NOT to do

- Do **not** edit backend or proxy flags inside the legacy start scripts
  (`dist/*/start_*.bat`, `start-bonsai.ps1`). The launcher +
  `config/bonsai-agent.json` is the single source of truth; the launcher
  refuses to touch processes it did not start itself (it kills only PIDs it
  recorded and verified in `state/launcher_state.json`).
- Do **not** point users at the Bonsai 2 `Q2_0` GGUF band: it loads on
  mainline llama.cpp and silently produces gibberish (see AGENTS.md "Do not
  run Bonsai 2 on stock llama.cpp").
- Do **not** commit `models/`, `dist/`, `bundle/`, `capture/`, `logs/`,
  `state/launcher_state.json` (all gitignored; `state/` itself is tracked
  only for the JSON shape, not for runtime PIDs — re-check before pushing).
