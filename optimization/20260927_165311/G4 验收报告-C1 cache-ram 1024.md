# G4 验收报告 — C1 限制服务端宿主 prompt cache（`--cache-ram 1024`）

- 执行时间：2026-09-27 23:05–23:14（Asia/Shanghai）
- 执行方：TRAE Agent
- 授权：用户于 2026-09-27 明确批准「C1 + `--cache-ram 1024`，现在执行」
- 变更文件：**仅** `D:\Bonsai-demo\config\bonsai-agent.json`（`backend.extra_args`）
- 相关文档：`G4 处置候选清单.md`（候选与证据）、`baseline\stageG4_cram1024_readonly_v3.txt`（变更后原始快照）

---

## 1. 变更内容与生效

| 项 | 值 |
|---|---|
| 改动 | `backend.extra_args`: `[]` → `["--cache-ram", "1024"]`（定点改写，其余注释/结构未动） |
| config 变更前 | 6,276 B，sha256 `D678A79A1283496573E980DB1AB5397A08A63037CF2356774728F3F68CA815B7` |
| config 变更后 | 6,297 B，sha256 `A68766381AAF1E32DB0D5C3124911A6DF04753559C91D315960FCAD8D33B7E07` |
| 备份 | `backup\stageG4\bonsai-agent.json.preG4`（= 变更前字节，sha256 同 `D678A79A…`） |
| 生效方式 | `launcher up --no-prewarm` |
| 漂移检出 | 输出 `仅配置有: ['--cache-ram', '1024']` → 判定参数不一致 → 空闲受控重启后端 |
| 后端 | pid 35040 → **35084**；就绪耗时 7 s；新命令行末含 `--cache-ram 1024` |
| 冒烟 | 通过 0.59 s，`finish_reason=stop`，`prompt_tokens=20` |
| 代理 | pid 40480 **未重启**（命令行未变，符合预期） |
| 配置指纹 | `0b0d2806eb9a9d1a` → `96df0f5964452b3c` |
| n_ctx | 65536，**未改**（C4 经用户决定不纳入） |

未改动：`proxy\bonsai_proxy.py`（`6ACFB9C5…`）、`launcher\bonsai_launcher.py`（`F28AFFCC…`）、
页面文件、BIOS/驱动/VBS/电源/系统代理、模型权重。

---

## 2. 变更前 / 后 只读证据对照

**重要前提（可比性声明）**：变更前快照取自 uptime ≈ 81 min、且经历过真实长上下文使用
（`n_tokens_max = 64,358`）的进程；变更后快照取自 uptime 5 min、仅跑过 bench 任务 1/2
（`n_tokens_max = 7,096`）的新进程。**两者绝对内存值不可直接比较**。
下表中最具可比性的是 **perfmon `Private Bytes`（同一计数器、同一进程语义）** 与其
**与 `--cache-ram` 上限的差值吻合度**。

| 指标 | 变更前 (22:54，pid 35040，uptime ≈81 min) | 变更后 (23:13:36，pid 35084，uptime 7 min 57 s，跑完 t1+t2) | 来源 |
|---|---|---|---|
| llama-server `Private Bytes` (perfmon) | **17,796,993,024 B = 16.58 GiB** | **10,262,142,976 B = 9.56 GiB** | `\Process(llama-server)\Private Bytes` |
| llama-server `Private` (PSAPI) | 16,972.5 MB | 9,786.7 MB | `GetProcessMemoryInfo` |
| llama-server `WS` | 5,815.9 MB（另一次 4,210.2） | 7,361.2 MB (`7,718,789,120 B`；峰值 7,715.9 MB) | `Get-Process` / perfmon |
| llama-server `WS − Private` | 5,801 MB（≈ 总 WS → 文件页几乎不驻留） | 1,954,889,728 B = 1.82 GiB（文件页驻留） | perfmon |
| `PageFaultCount` 累计 | 31,750,279 | 见 v3 快照 | PSAPI |
| Memory Compression `WS` | 4,112.1 MB | 1,494.3 MB | `Get-Process` |
| 全机 `Available MBytes` | 5,780 | 6,809 | `\Memory\…` |
| 全机 `Committed Bytes` | 46,560,010,240 B = 43.36 GiB | 38,349,787,136 B = 35.71 GiB | `\Memory\…` |
| 全机 `pages input/sec` | 10,177 | 951（同进程另一次瞬时采样为 2，**波动大、不可用于归因**） | `\Memory\…` |
| 页面文件实际用量 | 746 MB | 638 MB（C: 338 + D: 300） | `Win32_PageFileUsage` |
| 日志中 prompt cache 淘汰条目数 | 12 | 14（净增 2） | `llama-server.log` |
| `/metrics` `n_tokens_max` | 64,358 | 7,096 | `/metrics` |
| `/metrics` `prompt_tokens_cached_total` | 807,001 | 76,061 | `/metrics` |

### 2.1 核心定量结论（本轮最强证据）

```
变更前 Private Bytes        = 17,796,993,024 B
变更后 Private Bytes        = 10,262,142,976 B
差值                        =  7,534,850,048 B = 7.017 GiB

--cache-ram 上限差          = 8192 − 1024 = 7,168 MiB = 7.000 GiB

吻合度                      = 7.017 vs 7.000 GiB  → 偏差 0.017 GiB ( 0.25% )
```

**该 1:1 吻合同时完成两件事**：
1. 证实 C1 按预期生效；
2. **证实了变更前"16.58 GiB 私有提交中的主要构成是宿主 prompt cache"这一推断**——
   即 `--cache-ram` 的容量与宿主管存提交近似 1:1 对应（表现为按上限占用，而非随命中率弹性增长）。

> 注：变更前的"16.58 GiB 构成"在候选清单中曾被标注为**未验证的推断**（因地址空间分类探针失败）。
> 本轮通过"上限差 ↔ 提交差 1:1 吻合"这一独立途径**间接证实**了它，但仍**未做逐块拆解**。

---

## 3. 任务回归对照（bench 任务 1 / 2）

同一夹具、同一 `bench_harness.py`、同一 `check_tasks.py`；唯一受控变量 = `--cache-ram`。

| 任务 | 变更前基准 | 变更后 G4-1024 | 判定 |
|---|---|---|---|
| 任务 1 | `B-r3`：9.4 s / 3 轮 / 0 重试 / 验收 4 通过<br>`prompt_n=[516,74,123]`　`cache_n=[216,728,798]` | 9.2 s / 3 轮 / 0 重试 / 验收 4 通过<br>`prompt_n=[516,74,123]`　`cache_n=[216,728,798]` | **无回归**（token 与复用曲线逐项相同） |
| 任务 2 | `B-t2`：16.6 s / 4 轮 / 0 重试 / 验收 4 通过<br>`prompt_n=[535,64,116,87]`　`cache_n=[216,747,807,919]` | 15.9 s / 4 轮 / 0 重试 / 验收 4 通过<br>`prompt_n=[535,68,116,87]`　`cache_n=[216,747,811,923]` | **无回归**（耗时略优） |

结论：**C1 未造成任务成功率、轮数、重试或 KV 复用曲线的回归。**

### 3.1 需如实记录的中间失误（非 C1 问题）

首次运行使用了新 cfg 名 `G4-cram1024`，而 `bench\run_all.py` 的 `prep()` **不会复制夹具**，
导致 `read_file notes.txt => ERROR: file not found`，模型在缺文件环境中探索至 `max_rounds=16` 而失败
（任务 1：0 通过/1 失败，29 s/16 轮）。补齐夹具（新建 `runs\G4-1024\` 并复制 `fixtures\*`）后重跑即通过。
→ **该失败是执行脚手架疏漏，与被测的 `--cache-ram` 无关**；失败记录仍保留在 `bench\results.jsonl`（cfg=`G4-cram1024`）中未删除。

---

## 4. 结论

1. **C1 生效且达到预期**：宿主管存提交下降 **7.02 GiB**，与 `--cache-ram` 上限降幅 7.00 GiB 近似 1:1 吻合。
2. **短会话场景无功能/性能回归**：任务 1、2 的验收、轮数、重试、KV 复用曲线与耗时均与变更前一致或略优。
3. **宿主压力缓解**：Memory Compression WS 4,112 → 1,494 MB；全机 Available 5,780 → 6,809 MB；
   Committed 43.36 → 35.71 GiB。

## 5. 残余风险与未验证项（**不得当作已确认收益**）

1. **长上下文跨请求复用风险（未验证，最需关注）**：本轮 bench 序列仅到 ~7.6 K token
   （`n_tokens_max=7,096`），而变更前真实使用达到 **64,358** token。
   变更前观测到单个 64 K 序列的检查点约 **2,030 MiB** > 新上限 1024 MiB
   → **长上下文的服务端检查点将无法保留，跨请求复用可能丢失、TTFT 可能回归**。
   本项**未做实验**，需在真实 WorkBuddy 长会话中观察。
2. 仅跑 **2/12** 项任务，未跑全套。
3. 绝对内存值不可比（uptime 与序列长度差异）；结论主要建立在 §2.1 的差值吻合上。
4. `pages input/sec` 10,177 → 951（同进程另一次瞬时采样为 2）**波动大，不能单独归因于 C1**
   （负载与时长不同），仅作观测记录。
5. 变更前"16.58 GiB 的逐块构成"仍未拆解（探针缺陷未修复）。

## 6. 后续建议

1. **保留 `--cache-ram 1024`**，在真实长上下文使用中观察 TTFT；若出现回归，按候选清单升到 2048 / 4096。
2. 若要更稳，可择机补跑：全套 12 项任务；一条 ≥32 K token 的长上下文对话前后对照（专测风险 1）。
3. 回滚入口见 `rollback.md` **R8**。

---

## 附：原始快照

- 变更前（G4 首采）：`baseline\stageG_G4_hostmem_readonly.txt`
- 变更前（深采 v2）：`baseline\stageG_G4_hostmem_readonly_v2.txt`
- 变更后（v3）：`baseline\stageG4_cram1024_readonly_v3.txt`
- bench 记录：`D:\Bonsai-demo\bench\results.jsonl`（cfg=`G4-1024`；含一次失效的 `G4-cram1024`）
- bench 明细：`D:\Bonsai-demo\bench\runs\G4-1024\results\_run_task{1,2}.json`