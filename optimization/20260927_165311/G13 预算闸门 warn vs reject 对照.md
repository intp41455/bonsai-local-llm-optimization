# G13 预算闸门 mode「warn vs reject」行为对照

生成时间：2026-09-28 15:00　执行方：TRAE Agent

运行窗口：2026-09-28 14:46:12 → 14:48:21（warn 档 + reject 档连续完成，两次隔离启动实验代理）

## 一、为什么做这一批

G11/G12/G12b 已确认缺陷候选 F1：便宜路径 `est_upper = body_bytes/3.0` 在日志/密集符号素材上**低估**
（`d ≈ 1.87` 字节/token < 3.0），使「超预算」输入被误判为「在预算内」，从而**闸门根本不会告警**。
而生产当前 `budget.gate.mode=warn` —— 即便闸门**正确判出**「超预算」，也只是打日志并**照常转发**。

这条链路留下一个必须回答的问题：**切到 `reject` 到底能带来什么可测差异？warn 阶段现跑在挡住什么？**
G12b 的 `P-sparse`（英文语段，5.83 字符/token）正是「闸门**能正确判出**超预算」的素材；
本批就用它做 warn / reject 单因子对照，把两种预算模式在**同一超预算输入**下的行为差异量化。

本批特意加一个「预算内」小探针，验证 reject 不至于误杀正常请求。

## 二、口径定义（来源可查）

| 量 | 值 | 来源 |
|---|---|---|
| 压缩阈值 | **56,320 token** | `65536 − request_max_tokens(8192) − context_reserve_tokens(1024)`；= `check_input_budget()` 判「超预算」界线 |
| 后端硬上限 | **65,536 token** | 后端 `n_ctx`（`/props`，`window_source="server /props"`） |
| 生产 gate.mode | **warn** | `config\bonsai-agent.json` `budget.gate.mode`（本批不改生产） |
| 超预算输入（over 探针） | 精确 **57,570 token**（`required 66,786`，`headroom −1,250`） | 稀疏英文段重复 reps=152 标定（精确 `/apply-template`+`/tokenize`），> 阈值、< 硬上限 |
| 预算内输入（in 探针） | 精确 **655 token** | 小消息，便宜路径 |

## 三、受控条件

| 项 | 本批实际 |
|---|---|
| 驱动 | 专用驱动 `.stage\g13_warn_reject.py`；复用 `g11_run/g12_run/g12b_probe` 的取件与几何回退标定 |
| harness | `bench\bench_harness.py` sha256 `F0685208…` **未修改** |
| 代理 | 生产 v3：`proxy\bonsai_proxy.py` sha256 `6ACFB9C5…`，实验端口 **:8084** → 上游共用生产 :8081（pid 30160） |
| 配置副本 | 深拷贝 `config\bonsai-agent.json`；**warn 档** = 生产配置（仅重定向 logging/prewarm/proxy，budget 与原配置**逐键完全一致**）；**reject 档** = 同副本 + `budget.gate.mode="reject"`（隔离自证：budget 除 `gate.mode` 外其余键完全一致） |
| 隔离自证 | warn 档顶层改动 `['logging','prewarm','proxy']`、tools 差异 `[]`、budget 与源完全一致；reject 档顶层改动 `['budget','logging','prewarm','proxy']`、tools 差异 `[]`、仅 `budget.gate.mode` 差 —— 两档全部通过 |
| 探针 | 每档 2 探针：`in`（预算内 655 token）、`over`（超预算 57,570 token）；均 `max_tokens=64`、`temperature=0.0`、`stream=true` |
| 生产现场 | 前后 `:8080 pid 40480` / `:8081 pid 30160`、`/health` 双 200、config sha256 `A6876638…` 一致；实验窗口进生产 `0 条 /chat/completions`；:8084 结束后释放 |

## 四、warn 档（= 生产现状，mode=warn）

| 探针 | 自测 token | 闸门判定 | 客户状态 | 记录状态 | 后端处理 | prefill | client wall |
|---|---|---|---|---|---|---|---|
| in | 655 | 在预算内(便宜路径) | 200 | 200 | 736 | 11,928 ms | 13.4 s |
| over | **57,570** | **超预算**(精确，`required 66,786 / headroom −1,250 / 125 ms`) | **200** | 200 | **57,570** | **101,708 ms** | **105.7 s** |

`over` 探针的 proxy_notes 原话：
> 输入超预算：输入 57570 + 计划生成 8192 + 余量 1024 = 66786 > 窗口 65536（超 1250 tok）；**按配置 warn，仍转发**

即：闸门**正确判出超预算**，但 warn 仍把 57,570 token **完整送入后端**，做了一次 101.7 s 冷 prefill、
占满 `-np 1` 单槽 ~106 s，返回 200（产出在 `max_tokens=64` 下 `finish=length` 截断）。

## 五、reject 档（mode=reject）

| 探针 | 自测 token | 闸门判定 | 客户状态 | 记录状态 | 后端处理 | prefill | client wall |
|---|---|---|---|---|---|---|---|
| in | 655 | 在预算内(便宜路径) | **200** | 200 | 736 | 207 ms | 1.9 s |
| over | **57,570** | **超预算**(精确，`required 66,786 / headroom −1,250 / 109 ms`) | **400** | 400 / `input_over_budget` | **None** | **None** | **0.11 s** |

reject `over` 在**生成前**返回 400：`record_wall_ms=109`（仅闸门精确计数耗时）、`prefill_ms=None`、
`processed_tokens_backend=None`、`server_busy_at_start` 缺失 —— 即请求在**排队/占槽之前**即被拒绝。客户端收到结构化错误体（含 `budget` 全量字段，`input_pct_of_window=87.84`）。

## 六、逐维度差异对比（同一 over 输入 57,570 token）

| 维度 | warn（生产现状） | reject |
|---|---|---|
| 闸门判定 | 正确判出「超预算」(exact) | 同左（判定环节与 mode 无关） |
| 客户端结果 | **200**，继续推理 | **400**，`input_over_budget` |
| 是否送入后端 | **是**：后端实际处理 57,570 token | **否**：`processed=None` |
| 是否占推理槽 `-np 1` | **是**：~106 s | **否**：0.1 s 即返回 |
| 冷 prefill 成本 | **101.7 s** | 0 |
| 闸门判定耗时 | 125 ms | 109 ms（两者均为精确计数开销，可忽略） |
| 返回给客户端的补救信息 | 无（只有 200 + 截断产出） | **结构化 budget 错误体**（含 required/headroom/窗口占比） |
| 预算内请求是否受影响 | 不受 | **不受**（in 探针 200） |

**核心结论**：`reject` 的安全性来自「在排队/占槽**之前**判定并拒绝」，把 warn 模式下本会空耗的
一次 ~106 s 冷 prefill + 单槽占用，压缩为 ~0.1 s 的 400；且不误杀预算内请求。

## 七、与 F1 的关系（关键交叉结论）

必须并行考察两个缺陷：

1. **mode=warn 的「不保护」**（本批实证）：闸门即便正确判出超预算，warn 也只记录、仍转发 ——
   超预算输入照样 101 s 占槽推理后给客户端一份**可能截断**的产出。warn 是「看得见的记录」，不是「保护」。
2. **F1 便宜路径的「看不见」**（G12b 实证）：日志/密集素材（`d≈1.87` 字节/token）下，超预算输入
   被便宜路径误判为「在预算内」→ `act=pass`。此时**即使切到 reject 也不会触发**（reject 只在 `act=over` 时生效）。

因此：

- **切 `reject` 只能堵住「闸门正确判出超预算」这一路**（本批的 sparse 类素材）。它把已检测到的超预算
  从「空耗 106 s + 可能截断」变成「0.1 s 拒绝 + 结构化提示」，收益明确。
- **F1 的便宜路径低估仍然独立存在**：对 `d<3.0` 的素材，走出便宜路径、`act=pass`，**reject 也救不了**。
  要真正防止「超硬上限输入直接进后端」，仍需按 G11 建议调整 `chars_per_token_floor`（如 1.5）或对关键路径强制精确计数。

**结论**：`reject` 与 `chars_per_token_floor` 修复是**正交、缺一不可**的两件事 ——
reject 负责「判出即拒绝」，floor 修复负责「判得准」。

## 八、对照方案 §E 判据的验收

| 判据 | 结论 |
|---|---|
| §E：超预算能在生成前被发现 | ⚠️ 判定环节：**是**（本批 over 探针 exact 判「超预算」）；但守卫效果取决于 mode —— `warn` 仍转发（§四）、`reject` 生成前 400（§五）。且 F1 下便宜路径连「被发现」都做不到 |
| §E：压缩/拒绝调用耗时、不占槽 | ✅ reject 0.1 s 返回、`processed/prefill=None`，不经队列（占槽前拒绝） |
| §E：不误杀正常请求 | ✅ reject 下 in 探针 200、正常 prefill |
| §E：给客户端的处理依据可查 | ✅ reject 返回结构化 `budget` 错误体（`enabled/mode/window/planned_gen/reserve/input/required/headroom/verdict/elapsed_ms/est_upper/input_pct_of_window`） |

## 九、诚实标注与口径边界

1. **专用驱动**：本批只验证**代理预算闸门的机械行为**，不改模型、不推模型能力；口径不可与 G5/G9 成功率相加。
2. **over 探针 n=1/档**（单次冷 prefill 昂贵）：warn 档耗时 ~106 s、reject 档即时 400 —— 结论形态稳定，但只证明本次。
3. **只测了「闸门能正确判出超预算」的路**（sparse 素材）；F1 覆盖的「便宜路径低估」路（dense 素材）不在本批重跑，
   其行为由 G12b（n=2）独立证明。
4. **未改生产**：生产仍为 `mode=warn`（与 §四 warn 档完全一致的配置）；本批两档均为实验 :8084 上的配置副本。

## 十、产物清单

| 产物 | 大小 | sha256 |
|---|---|---|
| `optimization\20260927_165311\baseline\g13_summary.json` | 7155 B | `858f60076208314d` |
| `optimization\20260927_165311\baseline\g13_fingerprint.json` | 1851 B | `4d730e8c54a932bd` |
| `bench\results_g13.jsonl` | 5009 B | `87743cc8b2f719f7` |
| `optimization\20260927_165311\baseline\g13\warn\config.json` | 6665 B | `2648da7533346bf4` |
| `optimization\20260927_165311\baseline\g13\reject\config.json` | 6675 B | `85c75372d4f60251` |
