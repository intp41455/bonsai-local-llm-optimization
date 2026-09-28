# -*- coding: utf-8 -*-
"""把今天「最佳最优」的落地记录追加到项目记忆（用脚本文件，避开 shell 转义）。"""
import os

P = r"C:/Users/intpj/WorkBuddy/2026-09-26-18-59-35/.workbuddy/memory/2026-09-27.md"

ADD = r"""

---

## 12:25-12:40 「最佳最优」落地：僵死清理 + 预热源对齐 + 请求瘦身

用户问「按你建议的来，达到最佳最优该怎么操作」。实测后推翻了上一轮的两个前提，
并抓到一次真实的服务器僵死。三条发现 → 三个改动，全部已验证。

### 发现 1：上游会「僵死」，而旧启动器会一直沿用僵尸
12:21 的真实 Agent 请求卡在 prefill 边界。**连续 50 秒采样**：
`prompt_seconds_total=379.796` / `prompt_tokens_total=175077` / `requests_processing=1`
**三个指标纹丝不动**，而 GPU 100% 占用、功耗仅 38 W、显存 **7728/8151 MiB（顶格）**。
=> 该请求永远不会有结果。旧脚本只看「8081 在不在监听」-> 僵尸被无限沿用。
**改动**：启动器加 10 秒超时的微型推理探活，超时即判僵死，自动 taskkill :8080/:8081 重建。

### 发现 2：预热源过期 => 之前那次 125 秒是白等的
| | 05:31（预热用的） | 12:21（真实请求） |
|---|---|---|
| system | 35,369 字符 | **52,514 字符** |
| 路径 | `~//skills/`（变量被剥空） | `~/.workbuddy/skills/` |
| 语言段 | `MUST be English by default` | `当前处于中文环境` |
| Expert 入口 | `"Experts"` | `"专家"` |

**公共前缀只剩 1,382 字符** => 预热对实际请求**完全无效**。
=> WorkBuddy 的 system prompt 会随 **版本升级 / 界面语言 / 技能集 / memory** 漂移。
**改动**：`pick_newest_capture()` 从「体积最大」改为「**mtime 最新的大请求**」。

### 发现 3：prompt 54.3% 是 tools，其中 5,050 tok 是纯路径噪音
12:21 请求精确分词：tools **32,515**（54.3%）> system **14,464**（24.2%）> messages **12,860**（21.5%）。
tools 里 `Skill` 一个就 **11,538**；其 description 11,181，其中
**149 条 `(location: C:\Users\...)` = 5,050 tok（整条 prompt 的 8.4%）**。
模型按**技能名**调用技能，从不读路径 => 纯噪音。
**改动**：代理层剥离（默认开，`--keep-location` 可关）。
放在代理层而非改 WorkBuddy 安装文件的三个理由：不动用户文件 / 正则替换**确定性**（前缀稳定）/ 预热与实请求**同一管线**。

### 落地与验证
- `proxy/bonsai_proxy.py`：新增 `strip_locations()`（幂等 + 确定性，已单测）+ `--keep-location`
- `_restart_stack.py`（新）：探活 -> 按需清理 -> 起上游 -> 预热 -> 起代理；**并给 llama-server 补了日志**
- `_gen_chain_bat.py` + `start_all_agent.bat`：新增「0) 僵尸探测自动清理」；代理强制重启以带上瘦身
- 日志：`logs/llama-server.log`、`logs/proxy.log`（以前没有日志，排查全靠猜）
- **实测**：全量 57,873 tok -> 瘦身 52,902 tok（省 4,971）；预热 prefill **122.8 s**；
  端到端重放 **`prompt_n=4` / `cache_n=52,898` / prefill 0.12 s / wall 0.26 s**（约 472x）
- 文档：`Bonsai-2-27B-最优操作手册.md`（新）

### 踩坑（值得记）
- Python `subprocess(text=True)` 在中文 Windows 上按 UTF-8 解 `netstat` 输出 -> `UnicodeDecodeError: 0xbb`；**必须显式 `encoding="gbk"`**
- docstring 里写 `C:\Users` 会触发 `\U` 截断转义 -> 给 docstring 加 r 前缀，或改用正斜杠
- 启动器 GBK 回读校验「FAIL」是 `\n` vs `\r\n` 比较口径问题，不是编码问题（统一换行后 OK）

**一句话**：现在的最优 = **双击 `start_all_agent.bat`**（自动清僵死 + 对齐预热 + 瘦身 8.7%）；
能安全砍的 token 已经砍完，再往下要动 WorkBuddy 行为语义，不建议默认开。
"""

with open(P, "a", encoding="utf-8") as f:
    f.write(ADD)
print("已追加", len(ADD), "字符")
print("文件现在", os.path.getsize(P), "字节")
