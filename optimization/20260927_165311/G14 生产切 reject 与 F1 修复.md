# G14 生产切 reject 与 F1 修复（chars_per_token_floor 3.0 → 1.5）

生成时间：2026-09-28 15:02　执行方：TRAE Agent

运行窗口：2026-09-28 15:01:18 → 15:01:32（配置已由 G14 步1 于前一窗口编辑并备份；本批为「重启代理使配置生效 + 端到端验收」）

## 一、本次做什么（对应方案/缺陷）

承接 G11/G12/G12b（F1：便宜路径 `est_upper=body_bytes/floor` 在 `d<3.0` 字节/token 素材上低估，
超硬上限也不告警）与 G13（reject 生成前 400、不占槽、不误杀预算内请求；且与 floor 修复**正交缺一不可**）。

G14 一次性完成两件事，**直接落到生产配置**：

1. **F1 修复**：`budget.gate.chars_per_token_floor` `3.0 → 1.5`（便宜路径上界改用真实下界，
   使其仅在「按最坏密度也不超预算」时才跳过精确计数）。
2. **切生产 reject**：`budget.gate.mode` `warn → reject`（超预算在生成前返回 400，不占槽、不消耗 GPU）。

并受控重启生产代理使新配置**生效**，用 G12b 同款 F1 假阴性素材做一键端到端验收。

## 二、配置变更（改动与备份，可回滚）

| 项 | 旧 | 新 |
|---|---|---|
| `budget.gate.mode` | `warn` | `reject` |
| `budget.gate.chars_per_token_floor` | `3.0` | `1.5` |
| 配置 sha256 | `a6876638…` | `f09a77be63c09dbe` |
| `budget.gate._note` / 顶层 `updated_at` | — | 同步更新（说明 floor 下调依据、reject 语义） |

- 备份（回滚源）：`backup\stageG14\bonsai-agent.json.preG14-reject`（旧 sha `a6876638…`）。
- 回滚方法：用备份覆盖 `config\bonsai-agent.json` 后按 §三 重启代理即可恢复到 warn + floor 3.0。

## 三、受控执行（生产现场操作）

| 步骤 | 结果 |
|---|---|
| 快照 before | :8080 pid 40480 / :8081 pid 30160、`/health` 双 200、reqlog 偏移 1,371,778 / timings 偏移 167,049 |
| 身份核对 | :8080 所有者 cmdline 含 `bonsai_proxy.py` 且 `--port 8080` **核对通过** → 才动手 |
| 停止旧代理 | `taskkill` 正常退失败（该进程需 /F），在身份已核对前提下 **/F 强制终止** pid 40480 |
| 启动新代理 | `python -u proxy\bonsai_proxy.py --port 8080 --upstream 8081 --config <生产配置> --effort medium`（DETACHED），pid **55872**，:8080 `/health` 就绪 |
| 后端 :8081 | **不涉及** gate/floor，**未重启**，pid 30160 前后一致 |

## 四、端到端验收（打 :8080，属授权验收探针）

| 探针 | 素材 | 期望 | 实测 |
|---|---|---|---|
| `probe-dense` | G12b 同款 dense 日志/符号素材 `reps=9`，body 127,199 B | **400** + `input_over_budget` | **400**，`mode=reject`、`method=exact(apply-template+tokenize)`、`input_tokens=62249`、`required=71465`、`headroom=−5929`、`est_upper_tokens=84181`、`input_pct_of_window=94.98`、`elapsed_ms=62`、wall **0.08 s** |
| `probe-small` | 预算内小消息（1+1） | 200（reject 不误杀） | **200**，wall 1.75 s，`prompt_n=147` |

自测（驱动侧精确投影）`probe-dense = 62,165 token`，与代理 exact 计数 62,249 一致（差异 84，来自模板/结构）。

**验收判定 `acceptance_ok=True`**。

## 五、为什么这是「一举证明 F1 修复 + reject 生效」

同一 `probe-dense` 素材（`d≈1.87` 字节/token）正是 G12b 判定的 F1 假阴性素材：

- **旧配置 `floor=3.0`**：便宜路径 `est_upper≈42,399`，`+9216 ≤ 65536` → **判「在预算内(便宜路径)」→ 放行**，
  实际 62,831 token 超阈值 56,320 也不告警（G12b 实测 200）。
- **新配置 `floor=1.5`**：`est_upper=84,181`，`+9216 = 93,397 > 65,536` → **不再满足便宜路径** → 走**精确计数**
  → `input_tokens=62,249` > 56,320 → `verdict=超预算` →（`mode=reject`）**生成前 400**（`headroom=−5,929`）。

即：floor 修复让同一素材从「看不到」转为「精确判出」，reject 让「判出即拒绝」落地 —— 两个修复在同一探针上串联生效。

## 六、生产复验与增量

| 项 | before | after |
|---|---|---|
| :8080 pid | 40480 | **55872** |
| :8081 pid（后端） | 30160 | 30160（未动） |
| `/health` :8080 / :8081 | 200 / 200 | 200 / 200 |
| config sha256 | — | `f09a77be63c09dbe`（== new_config_sha） |
| reqlog 行 | 偏移 1,371,778 | +5（含两条授权验收探针） |
| `/chat/completions` 增量 | — | **2**（含 `probe-dense`(被拒) + `probe-small`，均属授权验收） |
| timings 行 | 偏移 167,049 | +1（`probe-small` 的预填计时） |

说明：`probe-dense` 被 reject 占槽前 400，故 timings 无追加（后端未处理）；`probe-small` 正常一次预填计入。

## 七、结论与遗留

- 生产已生效：`mode=reject` + `floor=1.5`；F1 假阴性素材现已被正确判出并拒绝，reject 不误杀预算内请求。
- 遗留（未纳入本次）：reject 对**真实客户端**（WorkBuddy / Pi）触发率、400 后的重试/降级路径，需在真实业务观察；
  预算内请求无行为变化（§四未变化，probe-small 200 佐证）。

## 八、产物清单

| 产物 | 大小 | sha256 |
|---|---|---|
| `optimization\20260927_165311\baseline\g14_apply.json` | 10331 B | `db261824b81ef4c0` |
| `optimization\20260927_165311\backup\stageG14\bonsai-agent.json.preG14-reject` | 6297 B | `a68766381aaf1e32` |
