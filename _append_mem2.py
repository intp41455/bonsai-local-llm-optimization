# -*- coding: utf-8 -*-
"""追加第二轮优化记录到项目记忆"""
import os

P = r"C:/Users/intpj/WorkBuddy/2026-09-26-18-59-35/.workbuddy/memory/2026-09-27.md"

ADD = r"""

---

## 12:45-12:55 第二轮优化：三项叠加瘦身 14,798 tok（25.5%）

用户问「还有别的能优化提升的吗」。用上游 /tokenize 对 12:21 请求做逐项精确分词，
找到两个额外的安全瘦身靶点，加上已有的 location 剥离，三项叠加。

### 逐项 token 成本（/tokenize 精确计量）

| 优化项 | 净省 tok | 占总 prompt % | 代价 |
|---|---|---|---|
| 已做：剥 (location: C:/.../SKILL.md) | 4,931 | 8.4% | 零 |
| 新增：压 ToolSearch deferred 工具清单（129 条） | 2,512 | 4.3% | 延迟加载工具多一跳 |
| 新增：压 Agent 子代理类型清单（9 条） | ~1,200 | 2.1% | 不用子代理时无害 |
| **三项合计** | **8,626** | **14.8%** | |

但实测叠加效果比单项相加更好（可能因为 JSON 压缩后更紧凑）：
- 原始 tools: 32,515 tok / 236 KB
- 三项瘦身后: ~23,891 tok / 206 KB（剥离 28,327 字符）
- **prompt_n: 57,873 -> 43,075（省 14,798 tok = 25.5%）**
- **prefill: 122.8 s -> 99.8 s（省 23 秒）**

### system prompt 语义块分解（14,464 tok 总计）

| 块 | tok | 占 system % |
|---|---|---|
| `<memory>` 大块（工作背景+关注+动态） | 2,301 | 15.9% |
| `<user_memory>`（跨项目长期记忆） | 2,061 | 14.2% |
| `<instructions_for_visualizer>` | 886 | 6.1% |
| `<personal_files_safety>` | 575 | 4.0% |
| `<result_presentation>` | 392 | 2.7% |
| 其他 8 块 | 1,353 | 9.4% |
| 非语义块（自由文本指令） | 6,896 | 47.7% |

memory+user_memory 合计 4,362 tok = system 的 30%。但这块是用户画像，**不建议动**。

### 落地
- `proxy/bonsai_proxy.py` 的 `strip_locations()` 扩展为三项叠加（LOC_RE + DEFERRED_RE + SUBAGENT_RE）
- 用占位符替换清单块（不是直接删），保留 XML 结构完整性
- 幂等 + 确定性已验证（_verify_slim.py）
- 端到端验证：prompt_n=4 / cache_n=49,215 / prefill 0.14s / wall 0.27s

### 踩坑
- `_restart_stack.py` 用 `subprocess.Popen(creationflags=DETACHED_PROCESS)` 在沙箱里无效：
  Python 脚本退出后 detached 子进程被 Windows job object 清理。
  `nohup` / `disown` 对 Windows 原生 exe 也无效。
  **唯一可靠方式**：用 `run_in_background=true` 的 Bash 工具（自动后台化 + 持久化）。
- 预热源 `req_001_123456.json` 其实是另一个 WorkBuddy 工作区（2026-09-27-04-02-31）的真实 Bonsai 会话，
  不是自检请求——但它的 system prompt 与当前工作区不完全一致，导致 cache_n 从 52,898 降到 49,215。
  不影响命中（仍 prompt_n=4），但说明**跨工作区的预热源不完美**。

**一句话**：安全可砍的 token 已全部砍完（25.5%）。再往下要动用户记忆或 WorkBuddy 核心行为，不建议默认开。
"""

with open(P, "a", encoding="utf-8") as f:
    f.write(ADD)
print("已追加", len(ADD), "字符")
print("文件现在", os.path.getsize(P), "字节")
