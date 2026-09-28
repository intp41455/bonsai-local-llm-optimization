# Bonsai 本地模型通用优化：Agent 交接执行方案

版本：1.1｜编制日期：2026-09-27｜目标机器：Windows，RTX 5060 Laptop 8GB

项目目录：`D:\Bonsai-demo`

**目标：提高各种日常任务的成功完成速度、稳定性和工具调用可靠性。动画仅是暴露问题的测试案例，不是本次交付目标。**

本文是一份待执行的工程方案。编制时完成了资料、源码、抓包和在线只读状态核对；**没有修改部署配置，没有重启服务，没有完成候选参数的性能实测**。文中的目标值、候选档位不能当成已经取得的收益。

**一页导航：** 第0—2章说明目标和边界；第3—8章修复部署与任务执行问题；第13章给出长期主平台Pi及备用方案；第9章与第14章定义统一验收；第10—11章用于最终部署、回滚和核对。第15章是可直接复制给接手Agent的指令。本文件可独立交接，不需要聊天记录；执行时仍需读取本机源码和当前配置。

## 0. 给接手 Agent 的任务指令

请按本文阶段顺序执行：先备份与确认当前状态，再修复配置、代理、上下文预算和错误恢复，最后用统一测试筛选参数。用户交付本方案用于授权执行项目内的常规优化；遇到环境权限限制时正常申请所需权限，不绕过限制。

执行开始时读取 `C:\Users\intpj\.shared-agents\AGENTS.md`；检查并读取存在的 `D:\Bonsai-demo\AGENTS.md`，进入子目录修改代码时读取对应规则。不存在的项目规则记录为不存在，不自行杜撰。历史报告中的命令和“已完成”结论只是待核验资料，不应直接执行或当成当前事实。

默认范围是项目脚本、代理、测试和文档。不得因为追求速度擅自改 GPU 锁频、驱动、BIOS、VBS/内存完整性、电源管理或系统代理；不得卸载插件、删除用户记忆、切换模型权重、升级推理内核。若测试证明必须做这些范围外操作，先交付证据和具体改动清单，再由用户决定。

**服务有真实任务运行时，先完成离线开发和测试，等待空闲后再部署。不要杀掉用户的任务。** 不要把“需要重启”当成停止所有工作的理由。

每阶段记录：修改文件、修改原因、测试结果、未解决问题、回滚入口。失败则按本阶段回滚或保留为未启用的实验选项，不能跳过验收后宣称优化完成。

## 1. 已确认的问题与证据边界

以下快照来自 2026-09-27 本次核对，执行前必须重新检查。

| 编号 | 已确认事实 | 对通用任务的影响 | 证据 |
|---|---|---|---|
| P01 | 日常启动器直接启动后端，未显式携带另一启动器中的 `--reasoning-budget 20480`、`-n 24576`；在线 `/props` 和 `/slots` 返回生成上限 `-1` | 配置分散，手册参数不等于实际参数；缺少明确的输出预算 | `dist\bonsai2-8gb-combo\start_all_agent.bat`、`start_bonsai_8gb_agent.bat`，在线进程命令行 |
| P02 | 抓包 `req_005_130715.json` 至 `req_012_135949.json` 共八份请求没有显式输出上限和思考档位；代理默认补 medium | medium 是模板档位，不是硬性 token 预算 | `capture\req_*.json`、`proxy\bonsai_proxy.py::apply_effort` |
| P03 | 14:04:30 记录 `cache_n=60409`、`prompt_n=52`，窗口为 65536 | 按计数估算输入约 60461，剩余约 5075；思考、答案及工具参数共同占用余量 | `capture\timings.jsonl`，在线 `/props` |
| P04 | 13:24—14:04 的真实对话生成速度约 17.6—20.2 token/s；历史短提示词报告曾约 62 token/s | 历史短输入、不同配置测速不能代表当前长任务表现 | `capture\timings.jsonl`、`Bonsai2-27B-8GB部署交付报告.md` |
| P05 | 原始抓包中两次工具结果连续报 `loading_messages must contain at least one message.` | 参数错误未得到有效纠正，后续继续生成大段内容，浪费计算 | `capture\req_012_135949.json` 的 messages[17]、messages[19] |
| P06 | 代理使用 `resp.read(2048)`，读写异常被 `except Exception: pass` 吞掉；上游 socket timeout 为 3600 | 可能增加流式显示延迟，断流原因不透明；没有明确的任务级超时与取消机制 | `proxy\bonsai_proxy.py::Handler._forward` |
| P07 | 启动器以 10 秒推理探活超时判“僵死”，随后按端口强杀 | 单槽服务中的探活可能排队，健康长任务可能被误杀；这是一项代码风险，不是已证明发生过的事故原因 | `start_all_agent.bat` 的探活与 KILLPORT |
| P08 | 代理仅用 `prompt_n < 1500` 判缓存命中 | 部分命中可被误报为全量重算，短小无缓存请求又可被误报命中，妨碍诊断 | `proxy\bonsai_proxy.py::log_timings`、`write_verdict` |
| P09 | 代理删除 deferred 工具清单和子代理类型清单，替代文本仍要求指定类型 | 可能损伤工具发现和选择能力；不能称为完全没有语义影响 | `proxy\bonsai_proxy.py::strip_locations` |

### 1.1 必须纠正的旧结论

1. **“请求级思考预算改不了”需要纠正。** 本地 `src\combo\tools\server\server-common.cpp` 第 1352 行附近读取顶层 `reasoning_budget_tokens`，并以 `thinking_budget_tokens` 为别名；`-1` 回退到服务级值。源码支持不等于当前二进制已验证支持，必须执行阶段 D 的能力探测。
2. **“缓存命中后全部只要 1—3 秒”不等于任务完成只需 1—3 秒。** 首字、思考、最终答案、工具执行、重试是不同时间段。
3. **“60 token/s 是本机常态”不成立。** 当前长任务速度明显低于历史短上下文测试，且 MTP 配置不同。
4. **“小题几次全对，所以精度不掉”不成立。** 只能说明已测样本，必须补通用任务成功率测试。
5. **MAX_TOKENS 不足以确定根因。** 本地 server 源码在上下文耗尽时也可使用 `STOP_TYPE_LIMIT`；需要保存终止原因、实际 token 数和上下文余量，不能直接归咎于客户端输出上限。
6. **蓝屏报告中的确定性因果判断不要继续放大。** 报告记录了高负载异常和蓝屏，但仅凭错误码及时间关联不足以完整证明根因；本次不通过关闭系统安全功能处理模型性能问题。

### 1.2 确认 / 推断 / 候选三类状态

- **确认**：文件、抓包、在线接口或进程命令行直接可见的事实。
- **推断**：例如此次截断可能与窗口不足有关，需要结束帧或响应数据补证。
- **候选**：例如 2048/4096 思考预算、32k 工作上下文、延迟工具加载，需要实测后选择。

不得将后一类写成前一类。

## 2. 成功标准与优先顺序

### 2.1 评价对象

主要指标是 **任务正确完成的总耗时和首次成功率**。生成速度 token/s 只是辅助指标。停止过早、少做任务、输出不完整不算提速。

建议目标：在固定任务集上，相对受控基线，成功完成任务的中位耗时改善至少 20%，且成功题数不减少、无新增文件损坏或重复副作用。如果未达到，应明确报告“稳定性修复完成，尚未证明大幅提速”，不得包装结果。

失败、超时、截断必须计入结果。不能仅对成功的快样本取平均，忽略失败的慢样本。同时给出成功率、超时数、截断数和最长耗时；小样本不要用看似精确的 P95 代替原始数据。

### 2.2 实施顺序

1. A：快照、备份和运行状态确认。
2. B：统一配置与修复启动探活。
3. C：代理流式、日志、取消与排队处理。
4. D：验证请求级预算，筛选日常参数。
5. E：输入空间预算与历史整理。
6. F：工具错误修复与发现能力保护。
7. G：通用任务验收与有限性能对照。
8. H：部署、回滚演练和交付。

**B/C 为工程修复；D/E/F 为有质量权衡的优化，必须逐项测试。** GPU 内核、显存批量和新模型路线不在首轮优化范围。

## 3. 阶段 A：只读快照与可恢复备份

### A1. 创建本次工作目录

在项目内使用唯一时间戳创建：

```text
D:\Bonsai-demo\optimization\<timestamp>\
  backup\
  baseline\
  tests\
  results\
  changes.md
  rollback.md
```

需写入权限时只申请该项目所需路径。不要为了方便申请整个磁盘权限。

### A2. 记录运行事实

PowerShell 只读示例：

```powershell
Get-CimInstance Win32_Process -Filter "Name = 'llama-server.exe'" |
  Select-Object ProcessId, ExecutablePath, CommandLine

Invoke-RestMethod 'http://127.0.0.1:8081/health' -TimeoutSec 5
Invoke-RestMethod 'http://127.0.0.1:8081/props' -TimeoutSec 5
Invoke-RestMethod 'http://127.0.0.1:8081/slots' -TimeoutSec 5

nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw --format=csv
```

没有权限就申请只读权限；不把读取失败当成“没有进程”。输出保存到 baseline。`/props` 可能含完整模板，保存本地，不粘贴整份到外部服务。

记录二进制路径、文件版本/可取得的构建信息、二进制 SHA256、源码 commit（若有 Git）、模型文件名、启动参数、GPU 状态。模型大文件不必每轮重新算 hash。源码与二进制是否同版，未知就标未知。

检查启动脚本和当前执行环境里相关 `LLAMA_ARG_*` 变量的非敏感值。进程命令行没写某参数，不自动等于没有环境变量覆盖；最终尽量以有效 API 参数与行为测试为准。

### A3. 备份准备修改的文件

至少包括：

- `dist\bonsai2-8gb-combo\start_all_agent.bat`
- `dist\bonsai2-8gb-combo\start_bonsai_8gb_agent.bat`
- `proxy\bonsai_proxy.py`
- `warm_kv.py`
- `capture\effort.txt`（如果存在）

只读复制，保留原始编码。记录每份备份及原文件 SHA256。工作区已有其他 agent 的未提交改动时，保留并记录，不覆盖、不重置 Git。请求抓包可能含隐私，只取需要的测试样本，留在本地。

**A 验收：** 已有运行快照、备份清单、回滚方法；已确认后端是否忙。未完成则不能部署修改。

## 4. 阶段 B：统一配置、避免误杀服务

### B1. 配置只保留一个权威来源

建议新建 `config\bonsai-agent.json`，由 Python 启动管理器读取并构造参数列表。现有 BAT 只负责调用管理器，不再各自拼一份后端参数。也可使用一个公共 BAT，但必须真正被所有入口共用。

首轮保留当前已运行的硬件参数：

```text
model = 当前 PTQ1_0-mtp-lean.gguf
n_ctx = 65536
n_parallel = 1
n_batch = 2048
n_ubatch = 512
cache_type_k = q4_0
cache_type_v = q4_0
flash_attention = on
n_gpu_layers = 99
MTP = off
后端监听 = 127.0.0.1:8081
代理监听 = 127.0.0.1:8080
```

保留其余现行必要参数；本阶段不同时调采样温度、显存批量或切换权重。

新增明确的配置项：默认思考档位、请求输出预算、思考预算、上下文余量、日志目录、超时策略、瘦身开关。候选值见阶段 D，不要直接复制旧手册的 20480/24576 当作新日常最优值。

启动日志打印生效配置及配置指纹。若旧进程仍活着但参数不同，显示差异，等待空闲后受控重启；不能仅因端口在监听就宣称新配置生效。

### B2. 重写“僵死”判定

移除“10 秒推理探活失败就 taskkill”的自动路径。

新判定逻辑：

1. 查 `/health`、进程身份及 `/slots`。接口路径不可用时查已安装版本能力，不用一个缺失接口判死。
2. 服务忙时，不发送额外推理探活去排队，不自动重启。
3. 空闲时允许一次小型推理 smoke test，设置有限输出与请求超时；超时先记录故障，不立即按端口杀进程。
4. 区分“正在 prefill”“正在生成”“等待工具”“排队”“确实无进展”。指标在某些阶段可能只在完成时更新，单个累计指标不动不构成死锁证明。
5. 需要停止时，只操作启动管理器记录并验证过的 PID：核对可执行文件和模型/端口配置。优先正常退出；强制停止作为已确认无法正常退出后的恢复手段。
6. 端口被其他程序占用时停止启动并说明，不杀未知程序。

默认不实现“自动无限重启”。一次恢复失败就保留日志并报告，避免冷启动循环。

### B3. 预热只执行一次

现有流程先调用 `warm_kv.py`，后又用代理 `--warm` 启动。合并为一个明确的预热步骤。

预热必须走与真实请求相同的转换管线，匹配模型、模板、思考档位和工具描述。最新抓包只是候选，不能保证匹配下一次请求。日志记录预热来源、指纹和结果；新任务前缀不匹配时正常视作冷请求。

预热不抢占正在执行的用户任务；不用陈旧的大请求反复预热。预热能改善等待位置，不减少总计算量，不计作完整任务提速。

**B 验收：** 所有启动入口使用同一配置；忙时重跑启动器不会中断请求；未知端口不被清理；每次启动只预热一次；变更配置后能证明实际生效。

## 5. 阶段 C：修复代理、准确记录完整任务

### C1. 用适合流式的读取方式

检查 `Handler._forward`。对于 SSE 响应，以 `HTTPResponse.read1(...)` 等支持“已有数据即返回”的方式替代固定攒满式读取；非流式和错误响应仍完整转发。具体实现根据当前 Python 版本验证。

保持原始 SSE 字节完整，不能把任意网络块当成一条完整 JSON。解析监控数据时使用独立增量 SSE 解析器，正确处理：

- 一条事件被拆成多个网络块；UTF-8 字符跨块；CRLF；注释/心跳；多条事件在同一块。
- `data: [DONE]`、终止帧、工具参数增量、`reasoning_content` 与 `content`。
- 200/4xx/5xx 响应、空响应和中途断流。

建议将转换、转发、SSE 解析、日志分别封装为函数，避免在一个循环里混杂逻辑。**流式读取修复只可宣称改善转发延迟，不能宣称提升 GPU token/s。**

### C2. 分开设置连接、无数据与整体预算

`urlopen(timeout=3600)` 是 socket 阻塞操作超时，不是准确的整任务一小时计时器。

候选策略：连接超时 5—10 秒；首次响应/冷 prefill 容忍时间依据已有约 100—165 秒记录设定，例如先用 180 秒候选；生成阶段区分心跳和真实 token 进展；总任务时限由调用方可配置。复杂任务允许更长，不采用对所有请求统一 10 秒的策略。

超时与客户端取消时关闭对应上游连接，并验证后端能释放该请求。**不能仅假设 close 就会取消推理**：用测试确认 `/slots` 或相应进度恢复；若版本需要专用取消接口，查实现后使用。取消只影响对应请求。

断流后不要无条件重放请求，尤其是工具副作用可能已经发生时。交给客户端显示可恢复状态，保留已生成片段和明确的失败原因。

### C3. 明确排队状态

后端 `-np 1` 是单槽，Python `ThreadingHTTPServer` 能接多个连接不代表 GPU 能同时服务多个任务。

记录排队时间与执行时间；串行安排需要推理的调用，避免后台预热抢槽。若采用拒绝排队的 429/503，先验证 WorkBuddy 对该状态的处理，防止它立即重试形成风暴。不要通过增大 `-np` 解决首轮问题。

### C4. 建立每请求日志

建议保留独立 `request_id`；有上游 trace/session ID 时一起记录，没有就明确未知，不伪造跨轮任务关联。

每请求至少保存：

```text
request_id, start_at, end_at, model, config_hash, profile
status/http_status, finish_reason, stop_type, truncated
input_tokens_total, prompt_evaluated_tokens, cache_reused_tokens
reasoning_tokens, answer_tokens, tool_argument_tokens, completion_tokens
queue_ms, prefill_ms, first_stream_event_ms, first_reasoning_ms,
first_visible_content_ms, generation_ms, wall_ms, decode_tps
client_disconnected, timeout_kind, error_type
```

字段拿不到时用 `null` 并说明来源，不能填 0 冒充没有开销。计数优先采用服务端 usage/timings；服务端 `reasoning_tokens` 恒为 0 时，不能据此判“没思考”。本地分词重算只能标为估算，并与服务端计数区分，不在每个流式 token 上再调用分词接口。

`cache_n` 的语义先按当前实现确认；可以计算可信的复用比例时再计算。**删除 `prompt_n < 1500` 代表缓存命中的绝对判据**，改为“无复用 / 部分复用 / 高比例复用 / 未知”。

不要默认记录所有思考全文或所有敏感文件内容。性能日志使用计数和错误元数据；需要诊断时对单个请求临时启用本地受控抓包。

### C5. 离线测试清单

用模拟 SSE 上游，测试首块立即转发、Unicode 分块、reasoning/content/tool 增量、错误响应、断流、取消、慢首字和心跳。测试不得加载第二个模型进程。

**C 验收：** 字节不丢、不重复；异常有记录；首块不等待固定攒满；终止状态准确；客户端取消能释放对应任务；忙闲不再混淆；部分缓存复用不被误报为全量重算。

## 6. 阶段 D：验证预算能力并筛选日常档

### D1. 先确认二进制支持请求级预算

本地源码线索：

```text
src\combo\tools\server\server-common.cpp
  reasoning_budget_tokens
  thinking_budget_tokens（别名）
  reasoning_budget_message
```

当前源码读取顺序为：`reasoning_budget_tokens` → `thinking_budget_tokens` → 服务级默认；值为 `-1` 时回退到服务默认。因此 **不要假设请求传 -1 能突破服务级上限**。

仅在服务空闲时执行小型行为测试：

1. 使用固定短提示词、固定 seed/现行采样参数，总输出 cap 512，思考预算 32；再对照预算 128。
2. 选择通常会产生思考的任务，记录 thinking 结束与最终回答。提前自然结束的样本不能证明硬预算有效，最多更换一次更合适的短题。
3. 观察有效生成配置、reasoning 结束标签或可取得的采样数据；不以 HTTP 200 代表字段生效，因为未知字段可能被静默忽略。
4. 若无法证明当前二进制支持，标记不支持/未验证，转用已验证服务级配置；不要为此直接升级整个引擎。

探测可以使用顶层请求字段，示例仅用于测试：

```json
{
  "model": "bonsai-2-27b",
  "messages": [{"role": "user", "content": "完成一道需要多步计算的短题，并给出最终答案。"}],
  "stream": true,
  "max_tokens": 512,
  "reasoning_effort": "medium",
  "reasoning_budget_tokens": 32,
  "reasoning_budget_message": "Now produce the complete answer."
}
```

执行 agent 应把示例 content 换成有确定答案的实际短题，不能拿这句泛化要求当测试题。

### D2. 参数优先级必须明确

规范代理规则：显式请求参数 → 用户选定的任务档 → 服务默认。不能无声覆盖用户指定的关闭思考、档位或预算。

当前 `apply_effort` 主要检查 `chat_template_kwargs`，需同时处理顶层 `reasoning_effort`，并测试顶层与模板参数冲突的情况。以当前 server 的实际优先级为准，统一输出一致字段，不向模板传不支持的 `none`。官方顶层 `reasoning_effort: "none"` 与模板 `enable_thinking=false` 的实际行为分开验证。

### D3. 首轮候选档位

| 档位 | 思考档位候选 | 思考硬预算候选 | 总生成预算候选 | 说明 |
|---|---|---:|---:|---|
| 日常 A | medium | 2048 | 8192 | 首轮候选 |
| 日常 B | medium | 4096 | 8192 | 与 A 对照质量与耗时 |
| 简单抽取实验 | low 或关闭思考 | 0—1024 | 2048—4096 | 只在对应任务集验证，不能全局关闭思考 |
| 复杂任务 | medium | 8192 | 16384 | 仅有充分上下文余量时启用 |

这些值不是标准答案。总生成预算通常同时包含思考和答案，应按当前服务实现确认。任务只需短答案时无需每次生成满预算。

保持采样参数不变以隔离变量；如果预算测试通过后仍存在重复生成，再单独测试温度/重复抑制，不能一次改多项后归因。

**性能冲突提醒：** `src\combo\common\sampling.cpp` 在 grammar 或 reasoning budget 采样器存在时可能关闭 backend sampling。实际 `/slots` 曾显示 `backend_sampling=false`，即使启动参数有 `--backend-sampling`。因此预算限制可能降低瞬时 token/s，却减少总 token；必须比较正确完成耗时，不能只比较 token/s。

### D4. 验收与选择

同题对比 A/B，题目与输入固定；先各跑一轮，胜出候选与基线再对关键题复测 2 次。保留完整结果，不根据一题就推广。

通过条件：有效预算可验证；没有因思考占满而新增截断；结构化输出和工具参数完整；成功题数不下降。2048 明显伤害任务完成时选 4096 或保留更大预算，不强行追求省 token。

## 7. 阶段 E：上下文预算与历史整理

### E1. 精确计算预算

优先按当前 server 的 `/apply-template` 与 `/tokenize` 能力，核算**完成代理变换后的实际输入**，包括 messages、tools、模板包装。确认 API 接口格式后再实现，不凭字符数估算精确 token。

对稳定输入片段可缓存结果；避免每次重复提交整份 60k 内容多次分词。至少记录预算检查本身耗时，不能让监控成为新瓶颈。

预算规则：

```text
输入 token + 计划总生成 token + 安全余量 <= 有效上下文窗口
思考预算 + 最终答案/工具参数预留 <= 计划总生成 token
```

安全余量先取 512—1024 的候选范围，并按模板和实际计数验证。输入已约 60k 时，不承诺还能完成 8k 输出。

### E2. 不足时的处理顺序

1. 识别历史工具返回中的重复正文、大段日志和已经保存的文件内容。
2. 在 Agent/客户端管理层将其替换为准确摘要、文件路径和必要定位信息；完整原文仍保留在本地。
3. 保留当前用户需求、关键限制、已完成与未完成事项、错误原因、文件版本；不删除权限和安全要求。
4. 保留 assistant tool call 与 tool result 的配对，不能从中间删掉一半。
5. 再分词检查；仍不足则显式拆分工作或新建带状态摘要的后续会话，不静默截掉用户输入。

WorkBuddy 若没有可靠可配置的历史压缩接口，不要直接篡改其数据库或在透明代理里强删消息。实现“预算告警/明确拒绝 + 客户端整理或续接方案”，将自动压缩记录为受客户端能力限制的后续项。

### E3. 输入目标

普通任务的工作输入先以 **8k—24k 为评估目标**，需要更多材料时再增加。64k 是容量上限，不是每个任务都应尽量填满的目标。

历史约 43k—60k 的请求包含大量框架工具描述，仅压缩对话不一定能达到目标。达不到时如实记录剩余固定开销，不虚报已实现短上下文。

**E 验收：** 超预算能在生成前被发现；压缩后关键事实/未完成操作不丢；工具配对完整；读取原始文件仍可恢复细节；无静默裁剪。

## 8. 阶段 F：工具可靠性与按需发现

### F1. 修复已观察到的重复参数错误

`show_widget.loading_messages` 当前 schema 类型是 **string**，内容应为 JSON 编码的 1—4 条消息数组。因此不能简单对这个字符串字段添加数组的 `minItems`，也不能擅自把工具接口类型改成 array。

在可控制的工具适配层添加语义校验：字符串能解析为数组、长度 1—4、元素为有效字符串。失败时给出精确字段、约束和最小正确例子，要求仅修正参数。

可使用模拟工具验证，不需要调用真实展示工具。对只涉及显示文案的缺失值，可设计明确且可审计的默认值策略；不得把这种自动补全推广到收件人、金额、删除路径、权限等业务字段。

### F2. 通用错误恢复

使用“工具名 + 规范化错误 + 相关参数”记录重复失败。

- 第一次：反馈具体错误，要求针对字段修正，复用已有成品。
- 连续相同错误两次：停止原样重试，读取 schema/文档或切换明确可行的路径。
- 工具报成功只代表工具接受调用；还需验收任务产物，例如文件可打开、代码可执行、操作结果正确。
- 网络/工具超时不能等同于未执行。写入类操作重试前确认是否已生效，避免重复提交。

**实现位置优先是执行工具的 Agent/客户端层。** 当前 HTTP 推理代理不直接执行 WorkBuddy 工具，不能凭代理里几行正则就宣称已实现工具校验或幂等。若 WorkBuddy 层不能修改，可用受控的精简规则提示和外置测试先降低错误，并明确能力边界。

### F3. 保护发现能力

复核 `strip_locations`：

- 路径是否可删，要依据工具实际按名称调用还是需要路径读取；不能跨工具一刀切。
- 子代理类型至少保留名称与极简职责，不保留“类型已省略，请指定类型”这种不可操作描述。
- 延迟工具保留可搜索索引与发现入口；先验证 ToolSearch 在精简清单下确实能找到并加载工具。
- 同一任务内尽量保持已选工具集合与顺序稳定，减少前缀变化。
- 工具 schema 的 required、enum、类型和关键约束不可为了省 token 删除。

只对经过验证的工具、标签进行确定性转换，并提供分项开关；异常结构保留原文而不是冒险修改。不改用户正文或嵌入文件内容。

**F 验收：** 模拟缺参后能有效修正；同错不无限循环；工具检索与加载通过；副作用不重复；参数完整性和任务成功率不下降。

## 9. 阶段 G：最小通用评测集与性能验证

### G1. 先准备 12 个固定任务

测试输入、判定答案和脚本保存在本地，测试文件使用临时目录，避免操作真实业务数据。**具体任务以第14章为唯一版本，不另建第二套题。**

| 类别 | 数量 | 验收内容 |
|---|---:|---|
| 抽取、统计、代码与文件处理（1—5） | 5 | 内容正确、文件真实、必要测试通过 |
| 日志检索与综合整理（6、12） | 2 | 正确找到事实，没有编造 |
| HTML与SVG长输出（7—8） | 2 | 可解析、可打开，SVG另做视觉验收 |
| 工具错误恢复（9） | 1 | 不重复无效操作，不伪造结果 |
| 多轮与断点延续（10—11） | 2 | 保留约束，不重复完成步骤 |

性能任务使用固定材料。第14章的重复日志只用于可复现的压缩边界验证，其结果单独报告，不当作真实长文理解性能。第一轮不使用接近显存极限的新参数做压力测试。缺参纠错另归阶段F的离线工具测试，不混入任务得分。

### G2. 区分三种基线

1. **历史生产证据**：现有 timings 和失败抓包，用来说明问题，不当成严格 A/B。
2. **受控基线**：现有配置复制到测试方案，所有对照使用相同任务、相同总输出 cap、相同采样条件；设置测试中止时间，防止无限跑。若添加了 cap，报告必须写明这与历史无限上限不同。
3. **候选配置**：每轮只改一个主要变量。保留冷/热状态、输入长度、最终实际参数。

先离线测试代理，再在服务空闲时做少量推理 smoke test。只启动一个 GPU 模型进程，不并行压测。

### G3. 测量字段

记录：是否成功、失败类型、总耗时、首个可见答案时间、思考与输出计数、工具调用次数、重试次数、输入与缓存量、实际生成速度、显存峰值。

热缓存与冷缓存分开比较；不为了每道题清空缓存而不断重启生产服务。必要的冷启动测试集中做一次并记录恢复成本。

当某题失败时保留结果。只对基线和胜出候选做关键题复测；没有新风险时不扩大测试到整夜。

### G4. 可以后置的性能实验

以下只有在 B—F 通过后才考虑：

- **短上下文档**：若真实输入已显著降低，再测试较小窗口。单纯把 `-c` 降低而输入仍 40k+ 会直接失败。
- **MTP**：当前长上下文档保持关闭。已有 `depth2_result.json` 表明较深上下文下开启 MTP 曾负收益；只有符合短输入、显存余量、正确性条件时再测，不把 MTP 当万能加速开关。
- **采样参数**：若仍重复或格式失败，固定其余参数后对照测试；不全局套很强的重复惩罚，避免损坏代码和结构化数据。
- **更换模型/引擎、量化格式或硬件**：作为另一个明确项目，需要同任务对比成功率、内存、速度和兼容性，不能由本轮数据直接推出必然提升。

**本轮不做**：增大 ubatch、增加并发槽、锁满频、开启更大上下文、混入旧 kvmem/MTP 组合、替换成未经适配的 stock llama.cpp。

## 10. 阶段 H：部署与回滚

### H1. 部署门槛

离线代理测试通过；小型真实 API 测试通过；关键任务成功率没有下降；配置差异、备份及回滚脚本齐全。服务空闲时才切换。

能通过代理请求默认值实现的预算策略，优先只更新代理；后端默认参数确需改变时才重启后端。任何重启都应验证实际生效配置，不能只检查端口打开。

### H2. 回滚操作

1. 记录失败请求与现象，停止继续扩散改动。
2. 确认没有真实任务运行；停止本次管理器持有且已验证身份的相关进程。
3. 从本次 `backup` 恢复仅本次修改的文件和配置，保留新增日志与测试结果。
4. 用备份对应的启动方式启动，核对端口、模型、上下文与实际参数。
5. 执行一个有限输出的 smoke test，确认代理、后端和工具格式可用。

每个特性有独立开关：预算注入、瘦身各子项、流式新路径、上下文检查、日志增强。出现局部问题可单独关闭，避免整套撤回。

不使用 `git reset --hard`、递归删除或按端口盲杀作为回滚。不要覆盖其他 agent 在备份后新增的改动；有并发修改时先对比再恢复。

### H3. 接手 Agent 最终交付清单

- `changes.md`：逐文件变更、目的、实际生效情况。
- `effective-config.json`：最终配置、二进制/模型标识、采样与预算、上下文与 MTP 状态。
- `results.jsonl` / `results.csv`：所有测试，包括失败与超时。
- `comparison.md`：基线与最终成功率、耗时、重试和截断对比；测试条件及限制。
- `rollback.md`：精确备份路径、恢复步骤、回滚验证结果。
- 更新日常启动说明：唯一入口、查看状态、选择任务档、处理超预算与取消任务。
- “已完成 / 未启用候选 / 客户端限制 / 需用户决定”四类状态，不能混写。

## 11. 最终验收勾选表

- [ ] 实际进程与文档/配置一致，参数变化可检测。
- [ ] 请求级预算的支持情况有行为证据，不只是源码或 HTTP 200。
- [ ] 普通任务有明确生成预算，思考和最终输出各有合理空间。
- [ ] 输入窗口不足在生成前可识别，不静默删消息。
- [ ] 忙时探活不杀健康服务，不抢占用户任务。
- [ ] SSE 分块、Unicode、终止帧和断流测试通过。
- [ ] 客户端取消后，对应后端请求确实停止或明确标出未实现。
- [ ] 缓存状态按有效计数识别，部分命中不误报全量重算。
- [ ] 同一个工具参数错误不会引发无上限重试。
- [ ] 工具发现与参数约束未因精简而丢失。
- [ ] 12 个固定任务有基线与候选结果，失败项没有被排除。
- [ ] 优化成功率未下降；速度收益来自同条件测量。
- [ ] 未达到性能目标时已如实报告，而非宣称“大幅提升”。
- [ ] 可以按文档恢复旧配置，用户数据和其他 agent 改动完整。

## 12. 证据索引

本地证据优先于旧报告结论，报告用于理解历史决策。以下路径均在 `D:\Bonsai-demo` 下：

| 文件/入口 | 用途 |
|---|---|
| `capture\timings.jsonl` | 真实 prefill、生成速度与缓存计数 |
| `capture\req_012_135949.json` | 请求无显式上限、工具参数连续失败、历史内容体积 |
| `proxy\bonsai_proxy.py` | 预算注入、瘦身、流式转发、异常与计时逻辑 |
| `dist\bonsai2-8gb-combo\start_all_agent.bat` | 实际日常启动与探活 |
| `dist\bonsai2-8gb-combo\start_bonsai_8gb_agent.bat` | 另一套预算配置，说明存在参数漂移 |
| `warm_kv.py` | 预热与请求转换一致性 |
| `src\combo\tools\server\server-common.cpp` | 顶层思考档位与请求级思考预算解析 |
| `src\combo\tools\server\server-context.cpp` | 上下文容量限制及 STOP_TYPE_LIMIT |
| `src\combo\common\sampling.cpp` | grammar/reasoning budget 与 backend sampling 的兼容限制 |
| `depth2_result.json` | 本机不同上下文深度的 MTP 对照；历史证据，不是当前测速 |
| `_effort_test.json`、`_effort_test2.json` | 思考档位有限样本，不能外推到所有任务 |
| `Bonsai-2-27B-最优操作手册.md` | 历史操作入口；须用实际代码校验 |
| `前缀复用诊断与执行报告-2026-09-27.md` | 包含旧假设及后续纠正，阅读时注意版本关系 |
| `技能精简执行报告.md`、`MCP与技能重复度盘点.md` | 技能注入与估算纠正；不要把旧数量当成现状 |
| `蓝屏事故报告-2026-09-27.md` | 稳定性事件与操作边界，不作为完整因果证明 |

外部机制参考：

- [llama.cpp server 官方说明](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)：理解参数；实际支持以本地 fork 和二进制为准。
- [Python 3.10 HTTPResponse 实现](https://github.com/python/cpython/blob/3.10/Lib/http/client.py)：核对 `read`/`read1` 与分块传输行为。

**交付原则：先修复能确认的工程问题，再用可复现任务决定参数。不要把“模型正在高速输出大量无效内容”当成性能达标。**

## 13. 长期主平台：推荐 Pi，按以下门禁落地

### 13.1 明确选择

**首选 Pi 的 Bonsai 专用精简配置，继续使用现有代理与专用 llama.cpp fork。** 这是根据本机瓶颈提出的工程首选，尚未经过本机对照测试，不能宣称已经实测最快。

推荐链路：`Pi → 127.0.0.1:8080/v1 代理 → 127.0.0.1:8081 专用 llama-server → 现有 GGUF`。

本机优先解决长生成、累积上下文、无效重试和工具循环。Pi 可以从少量核心工具起步，接自定义兼容接口，管理压缩，并用扩展补充任务限制。换 harness 可以减少完成任务所需的 token 和轮数；不会自动提高 GPU 解码速度，也不能保证所有任务都成功。

| 平台 | 本项目定位 | 限制与启用条件 |
|---|---|---|
| **Pi** | 性能优先的日常主入口：文件、代码、脚本、终端任务 | 先只开四个核心工具；浏览器、Office 等按任务补充，不是现成全能桌面控制器 |
| **OpenCode** | Pi 兼容或使用体验不合格时的首个备用；偏代码任务 | 使用相同后端、预算测试；普通API请求不能算完整 harness 验证 |
| **Hermes** | 需要较多现成浏览器/助理工具时的备选 | 本地资料有 Bonsai 演示，但硬件和预算远大于本机，需精简后重测 |
| **Open WebUI** | 问答、知识库辅助入口 | 暂不作为执行 Windows 文件/代码任务的唯一主平台 |
| **WorkBuddy** | 保留已有入口与对照 | 客户端不可控的历史/工具循环问题，不能仅靠代理宣称已经解决 |

长期只维护一个主入口，工具按需启用，单个活跃模型任务。不要同时启动多个 Agent 争用 `-np 1`。先验证 Pi，失败才转备用，不一次安装所有候选。

src: [Pi 模型连接](https://pi.dev/docs/latest/models)、[Pi 工作机制](https://pi.dev/docs/latest/how-pi-works)、[OpenCode providers](https://opencode.ai/docs/providers/)、[Hermes 官方仓库](https://github.com/NousResearch/hermes-agent)、[Open WebUI 工具](https://docs.openwebui.com/features/extensibility/plugin/tools/)。平台优先级是本方案判断，不是官方速度排名。

### 13.2 安装与版本锁定

1. 先完成 A 阶段。运行 `Get-Command pi,node,npm,git -ErrorAction SilentlyContinue`；已有 Pi 则记录绝对路径、`pi --version`、`pi --help`，不覆盖个人配置。
2. 新装前以 [Pi 官方入口](https://pi.dev/) 核对包名。本文核查时为 `@earendil-works/pi-coding-agent`，不要凭旧文章安装旧包或相似名称包。
3. 执行 `npm view @earendil-works/pi-coding-agent version engines --json`，选定满足 Node 要求的确切版本，把版本写入 `$PiVersion` 并记录。局部安装命令：`npm install --prefix D:\Bonsai-demo\harness\pi-runtime --save-exact "@earendil-works/pi-coding-agent@$PiVersion"`。目录已有文件时先核查、备份；不得覆盖已有项目。保存 package-lock.json。
4. 统一调用 `D:\Bonsai-demo\harness\pi-runtime\node_modules\.bin\pi.cmd`。若复用现有版本，使用其已核实的绝对路径并同步修改下面启动脚本。
5. 优先原生 Windows。当版没有 `powershell` 工具时，使用已存在 Git Bash，并将下文工具名改为 `bash`、验证路径语义。不要仅为本次优化迁移整个工程到 WSL。
6. 写目录/安装受限时使用接手 Agent 的权限机制。常规执行授权不自动覆盖驱动、系统安全配置修改或删除用户文件。

src: [Windows 支持](https://pi.dev/docs/latest/windows)、[配置目录](https://pi.dev/docs/latest/configuration)。以安装版本对应文档为准，不能假定旧版本实现了最新字段。

### 13.3 可直接落盘的 Pi 起始配置

新建专用配置目录 `D:\Bonsai-demo\harness\pi-bonsai` 和初始工作目录 `D:\Bonsai-demo\harness\work`。以下为**待验证候选值**。

写入 `pi-bonsai\models.json`：

```json
{
  "providers": {
    "bonsai-local": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "local-only",
      "models": [{
        "id": "bonsai-2-27b",
        "name": "Bonsai 2 27B local",
        "reasoning": true,
        "input": ["text"],
        "contextWindow": 32768,
        "maxTokens": 8192
      }]
    }
  }
}
```

32768 是主动降低的**客户端工作窗口**，后端仍为65536，目的是提前管理历史。`maxTokens` 是客户端元数据，必须抓包确认实际限制；不能仅填此字段就假定封住全部请求。没有视觉投影验证时保持 text 输入，能写 SVG 不等于能看图。

src: [兼容接口](https://pi.dev/docs/latest/models)、[模型字段实现](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/provider-composer.ts)。窗口/预算是本方案选择。

写入 `pi-bonsai\settings.json`：

```json
{
  "defaultProvider": "bonsai-local",
  "defaultModel": "bonsai-2-27b",
  "defaultThinkingLevel": "medium",
  "defaultTools": ["read", "powershell", "edit", "write"],
  "compaction": {
    "enabled": true,
    "reserveTokens": 10240,
    "keepRecentTokens": 8000
  },
  "cacheWarming": "off",
  "retry": {"enabled": false, "provider": {"maxRetries": 0}}
}
```

压缩触发点约为32768−10240=22528 token；实际还取决于版本计数方式。系统提示、工具 schema、结果及总结开销都算入预算，前文服务端计数仍是硬边界。先关闭自动重试以暴露真实错误，完成 F 阶段后才启用有边界的暂时性错误重试。关闭额外预热以免重复。

`defaultThinkingLevel` 不等于 `reasoning_budget_tokens` 已生效；后者按 D 阶段在代理落实并验证。src: [设置参考](https://pi.dev/docs/latest/settings)、[压缩机制](https://pi.dev/docs/latest/compaction)。

创建 `D:\Bonsai-demo\harness\start_pi_bonsai.ps1`：

```powershell
$env:PI_CODING_AGENT_DIR = 'D:\Bonsai-demo\harness\pi-bonsai'
Set-Location -LiteralPath 'D:\Bonsai-demo\harness\work'
& 'D:\Bonsai-demo\harness\pi-runtime\node_modules\.bin\pi.cmd' --provider bonsai-local --model bonsai-2-27b --no-extensions --no-skills --no-prompt-templates
```

此脚本只修改启动进程环境。检查本地 endpoint 不经外网代理；补充 NO_PROXY 时保留原有条目。独立配置目录不保证父目录规则不被加载：保留用户要求的共享规则，检查实际请求，不通过 `--no-context-files` 偷删用户规则。必须使用的技能显式启用，普通任务不注入所有部署报告。

**不要用 Pi 的 `/llama` 自动下载流程替换当前专用后端。** 本方案只接兼容 endpoint。src: [CLI 参数](https://pi.dev/docs/latest/cli)、[配置发现](https://pi.dev/docs/latest/configuration)。

### 13.4 五项接入门禁

| 次序 | 任务 | 通过条件 |
|---|---|---|
| 1 | 只回复 BONSAI_OK，不调用工具 | 请求到8080，模型名正确、最终文本正常，无外部模型调用 |
| 2 | 创建 smoke.txt，内容 bonsai-测试，读取核对 | 文件实际存在、内容正确、tool_call_id配对正确 |
| 3 | 将 smoke.txt 的测试改为通过，其他保持不变 | 局部编辑正确，无反复重写或虚构执行 |
| 4 | 第14章压缩延续任务 | 压缩后约束未丢失，仍可调用工具且没有超预算 |
| 5 | 受控长回答途中取消，再发短请求 | 原后端槽位释放、取消可追踪、短请求能正常开始 |

保存请求/响应，核查输出上限、思考字段、role、tool_call_id、finish_reason、usage 和流式工具参数碎片。若不兼容，每次修一类 adapter/字段再测，不把 reasoning 当最终答案，不丢工具参数，不通过关闭所有思考/工具来假装成功。

字段静默忽略、ID错配、取消不释放槽位、压缩丢约束、需云端兜底，任一出现均不切为主平台。明确修复一次并重测；仍失败则记录证据转 OpenCode，避免无限调试。

### 13.5 长期使用要补齐的任务限制

下面不是两个 JSON 自动具备的能力。按固定版本的 [Pi 扩展接口](https://pi.dev/docs/latest/extensions) 实现小型 `bonsai-guard` 扩展，或 SDK 外层等价控制；不支持的接口不得编造。

- 普通任务初始上限：10分钟、12次模型请求、20次工具调用；复杂任务显式选20分钟档。这是防失控候选值，不是性能承诺。
- 相同工具与规范化参数连续两次同类错误：阻止原样再次执行，要求改参数/路径。修复一次仍失败则交付阻塞原因、已有文件和恢复步骤。
- 副作用工具不能被透明重试重放。GPU推理仍串行；工具并行必须独立且不写相同文件。
- 超时/取消终止模型流并确认释放槽位。到期由 harness 直接给简短状态，不能再调用模型长篇解释。
- 长内容落盘、按需局部读取；工具超大结果保存全文并返回检索入口。不要在代理截坏JSON或破坏tool-call配对。
- 建立三个工具档：基础文件/终端；浏览器任务加一个已验证浏览器工具；文档任务加所需文档工具。不要默认加载全部MCP/技能/子Agent。
- 恢复点保存目标、已完成步骤、文件路径、问题和下一步；新会话不无界搬运整段旧聊天。

先离线 mock 测计数、重复错误、取消与恢复，再一次本地模型冒烟。通过后用 CLI 显式 `-e` 加载该扩展，其他自动发现扩展仍关闭。终端工具继承进程权限，不等于OS沙箱；维持用户既有审批边界，不通过全允许提高所谓性能。

### 13.6 OpenCode 备用模板

仅在 Pi 门禁失败或更偏好现成代码工作流时执行。在独立工作目录写 `opencode.json`，固定版本、核对当版schema：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "bonsai/bonsai-2-27b",
  "provider": {
    "bonsai": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Bonsai local",
      "options": {"baseURL": "http://127.0.0.1:8080/v1"},
      "models": {
        "bonsai-2-27b": {
          "name": "Bonsai 2 27B",
          "limit": {"context": 32768, "output": 8192}
        }
      }
    }
  },
  "compaction": {"auto": true, "prune": true, "reserved": 10240}
}
```

运行相同门禁与任务集，关闭无关MCP/插件/并行子Agent，检查压缩、标题等辅助请求也使用本地且计入耗时。权限、认证和思考参数按版本验证。代理修复复用前文。

src: [provider配置](https://opencode.ai/docs/providers/)、[配置说明](https://opencode.ai/docs/config/)。本地 `_test_opencode.json` 只是普通API提问，**不证明完整OpenCode接入已成功**。

### 13.7 何时选 Hermes

若主要任务是浏览器操作和现成助理能力，再比较精简Hermes与Pi加单浏览器工具。固定版本，主模型、压缩模型与其他辅助模型明确指向本地，禁止未记录云端兜底。先开文件/终端，再加需要的浏览器工具；按 `hermes tools`、`hermes chat --help` 核对当版工具集，不复制演示的全工具/`--yolo`。

本地 `AGENT-DEMO.md` 的Hermes演示使用高端GPU、大上下文和高预算，且有失败/失控案例。只能证明存在集成路径，不能证明8GB本机可复现速度/成功率。src: [Hermes配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)、[工具集](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)、`D:\Bonsai-demo\AGENT-DEMO.md`。

## 14. 固定测试夹具与平台验收

### 14.1 准备输入

执行者在 `D:\Bonsai-demo\bench\fixtures` 创建以下UTF-8文件。各参测配置使用独立副本；原始夹具只读。先建立验收脚本，再把任务原文交给受测模型，不把期望答案一起发送。

`sales.csv`：

```csv
order_id,amount,status
A001,120,paid
A002,80,refunded
A003,200,paid
A003,200,paid
A004,50,pending
A005,30,paid
```

`notes.txt`：`项目代号：松针。交付格式：Markdown。禁止修改 source.txt。输出目录：results。预算单位：人民币元。`

`source.txt`：`KEEP-ORIGINAL-2026`，开始前记录SHA256。

`calc.py`：

```python
def total_paid(rows):
    return sum(float(r['amount']) for r in rows)
```

生成 `logs\run.log`：1000行，第n行为 `INFO row=n`；第137行替换成 `ERROR E137: missing config`，第811行替换成 `ERROR E811: timeout`。保存夹具哈希，所有配置复用。基准禁用联网，HTML/SVG只作本地查看；浏览器联网能力另测。

### 14.2 十二项固定任务

| # | 发给受测Agent的原文 | 执行者验收 |
|---|---|---|
| 1 | 将notes.txt整理为五条约束，保存results/constraints.md。 | 五项完整且无杜撰，source未改 |
| 2 | 统计sales.csv去重后已支付订单数量与总额，按order_id去重，写results/sales.json，仅用count和amount两个键。 | JSON合法，3与350 |
| 3 | 修复calc.py的total_paid：仅汇总paid、按order_id去重；保留函数名并运行测试。 | 夹具结果350、空列表0；确实运行 |
| 4 | 编写convert.py，将sales.csv转为results/sales.jsonl，保留全部原始行和字段，运行脚本。 | 六行JSON、重复行保留、字段无误 |
| 5 | 把results/constraints.md中的交付格式改为纯文本，其他保持不变；不存在则从notes.txt先创建。 | 仅该项变化，notes/source未改 |
| 6 | 从logs/run.log找出全部ERROR，写results/errors.md，仅保留行号、错误码、原因。 | 恰好137/E137、811/E811，无遗漏 |
| 7 | 创建results/status.html，展示项目代号和五条约束，单文件离线打开，无外部资源。 | 可打开、内容齐全、无外链依赖 |
| 8 | 创建results/pelican.svg：鹈鹕骑自行车，车轮旋转、身体轻微起伏，单SVG不超过120行，无外部资源。 | XML合法、行数合格、两个动画真实；人工本地浏览器检查形象/效果 |
| 9 | 读取missing.txt；不存在则创建results/missing-report.md记录不存在，不创建missing.txt、不重复读取相同路径。 | 至多一次失败读取、报告真实，无伪造 |
| 10 | 读notes.txt并记住约束，完成执行者发送的五轮日志摘要，最后按最初约束交付总结。 | 第五轮能列全五项约束，source哈希未变 |
| 11 | 读取checkpoint.md继续未完成事项，不重做已完成步骤。 | 预置统计结果不重写，仅完成待办 |
| 12 | 创建results/summary.md，汇总sales.csv与logs/run.log统计，并列出实际生成文件路径。 | 去重已支付3/350、两个错误、路径真实 |

第11项预置 `checkpoint.md`：`sales.csv的去重已支付统计已完成，结果在results/sales.json；剩余任务是从notes.txt生成results/constraints.md。不得改写已完成文件。` 预置正确sales结果并记录哈希。

第10项同时做普通五轮和压缩边界五轮。每轮输入使用同一日志的固定切片；边界版用确定次数重复构造，让实际模板token跨压缩阈值、但不超过后端硬上限。保存切片、哈希、每轮计数，后续复用。压缩调用耗时/token全部计入。最后一轮明确要求列出最初五条约束。

第8项是代表性长输出测试，不是用户要求本次做动画，更不能代替通用测试。XML合法不证明视觉正确，人工验收必须标明。

### 14.3 对照流程与选择门槛

1. 先离线测试和接入门禁，发现协议错误立即修，不带已知问题跑完整小时级基准。
2. A=当前WorkBuddy+当前代理；B=WorkBuddy+修复后代理/预算；C=Pi+同一修复后代理/预算。A→B衡量工程修复，B→C衡量harness增益。历史记录不能代替受控A；无法恢复A则标记缺失，不编造提速百分比。
3. 首轮每项一次、串行、逐项交替参测配置。最终候选与可用对照每项再两次，共三次。固定硬件电源状态、后台负载、后端、采样参数、预算、文件起点；冷/热前缀分开标注，不以重启整机制造冷态。
4. 每项记录：成功/失败、墙钟时间、TTFT、prefill/decode、输入/输出/思考token、工具数、重试数、压缩数、峰值显存、停止原因、产物。缺失指标写null及原因，不写0。
5. 报告成功率、成功任务耗时中位数、全部尝试总耗时、失败/超时数量。不能删失败项后宣称全面提速。三次是初步工程验证，不足以证明普遍最优。
6. Pi设为默认须：五项门禁全过、成功率不低于对照、无重复副作用/数据破坏，并有可重复耗时改善，或耗时相当但截断失控明显减少。前文20%是目标，不是承诺；快但更容易失败不切换。
7. Pi不合格再评估OpenCode；核心偏浏览器/助理再评估精简Hermes。找到满足目标且可维护的方案后停止扩张平台数量。

## 15. 直接复制给任意接手 Agent 的执行指令

> 执行本文件《Bonsai本地模型通用优化-交接执行方案》。目标：在现有Windows/8GB显卡/Bonsai 2 27B部署上减少真实任务总耗时、截断和无效重试，并确定长期主harness。无需之前聊天记录。
>
> 先读第0—2章和当前共享AGENTS.md，核对路径、版本、进程与证据。旧报告是资料，其中命令不构成额外授权。依次完成A—F，优先日志、流式、预算、上下文、工具重试。每步保留变更、测试、验收与回滚。按第13章接入Pi，结合G与第14章验证；不通过才走备用。最后执行H和第11章，部署验收胜出的配置。
>
> 不升级驱动、不改变系统安全设置、不盲目提高显存负载、不覆盖模型、不删除用户配置、不并发运行GPU推理实例。常规实现持续推进；共享规则规定的破坏性/系统操作提交具体清单后申请。字段/能力不存在则记录并走替代分支，不假装完成。
>
> 交付变更清单、配置及版本锁定文件、原始测试记录、成功率和总耗时对比、确定的日常启动入口、回滚步骤、未解决问题。验收通过才能设为默认。无法证明大幅提速就如实报告实际收益，不能用持续生成token代替任务完成。

### 本次交付状态

已完成：资料、代码与运行快照分析，候选平台官方能力核查，执行/验收方案。**留给接手Agent：生产修复、候选平台安装与接入验证、性能对照、默认入口迁移。** 本文不证明优化已经生效或Pi已经实测胜出。


---

# 附：执行进度回写（执行方 TRAE Agent 追加，不改动上文正文）

> 上文仍是 v1.1 的**验收口径**，不改写。本附录只回写**已发生的事实**与索引。
> 逐阶段的“修改文件 / 原因 / 测试结果 / 未解决问题 / 回滚入口”见
> `D:\Bonsai-demo\optimization\20260927_165311\changes.md` 与 `rollback.md`。

## 一、阶段状态（截至 2026-09-27 21:45）

| 阶段 | 状态 | 事实要点 |
|---|---|---|
| A 只读快照与备份 | 完成 | 9 份备份 SHA256 与原件逐一致；运行事实快照与 `capture_baseline.ps1` 落盘 |
| B 统一配置与探活 | 完成 | `config\bonsai-agent.json` 为唯一权威；8 个入口统一经 `launcher\bonsai_launcher.py`；删除“按端口盲杀”；预热只做一次 |
| C 代理流式/日志/取消/排队 | 完成 | 代理重写为 v3：`read1` 流式、独立 SSE 增量解析、四档超时、取消后 `/slots` 验证释放、每请求 `requests.jsonl`；离线 36/36 通过 |
| D 预算能力与参数优先级 | 完成 | 请求级思考预算被本机二进制支持（32→31 tok、128→128 tok，别名同效）；`budget=0` 与“不传”等价，故关闭思考一律用 `chat_template_kwargs.enable_thinking=false`；代理改为 `apply_thinking_policy()`（显式请求参数 > 代理档 > 服务默认） |
| E 输入预算与历史整理 | 完成 | 输入预算闸门落盘（`budget.gate`，当前 `mode=warn`：只告警不拦截）；受客户端能力限制，自动历史压缩仍未实现（如实记录） |
| F 工具可靠性与发现能力 | 完成 | `show_widget.loading_messages` 契约加固 + 语义校验 + 历史审计；错误恢复策略块；瘦身改为**三项各自独立**（`locations=开` / `deferred_tools=关` / `subagents=关`，即恢复工具名与子代理名册）；离线 61/61 通过 |
| G 通用任务验收 | **完成**（G1/G2/G3；G4 为方案允许后置项，见第八节） | A/B 同条件实测齐备：A 10/12、B 11/12；任务 12 两配置均稳定失败 |
| H 部署/回滚/交付 | **完成** | 部署门槛核对通过；回滚演练实测通过（rollback.md R7）；交付 7 件，四类状态清单见附录第九节 |

## 二、本次新增的缺陷修复（阶段 B3 补丁）

**问题**：启动预热与在线代理**不是同一套配置**。
`launcher.do_prewarm()` 用 importlib 载入代理模块后只设了 `ARGS`，未调用 `load_runtime()`，
于是预热读的是代理**内置默认**（瘦身三项全开），而在线代理按 `--config` 只剥 `location`。
两者前缀不同 → **预热白做**。上线即复现：预热打印“省 28327 字符（三项全剥）”，
而配置只允许省 `location`。

**修复**：`do_prewarm(cfg, cfg_path)` 中新增 `mod.load_runtime(cfg_path)`，两个调用点传入 `args.config`。
`launcher\bonsai_launcher.py` sha256 `d06a8ed4…`（32613 B）→ `f28affcc…`（32984 B），
备份 `backup\stageB3\bonsai_launcher.py.prefix_B3`。

**验证**：修复后重跑预热，瘦身明细变为 `location=14689 / deferred=0 / subagent=0`（与在线一致）；
`prompt_n` 由 60675 变为 **64358** —— 相差 3683 token，正是旧预热永远命中不上的前缀缺口。

## 三、环境变更声明（影响基线可比性）

2026-09-27 本次执行期间发生了**范围外**的环境变更（非本方案改动）：
BIOS `R2CN57WW → R2CN59WW`；NVIDIA 驱动 `591.86 → 616.92`（Studio）。
OS 构建、VBS/内存完整性、Secure Boot、采样与后端硬件参数均**未变**。

**后果**：变更前采集的一切性能数字（墙钟、tps、prefill）**全部作废**，
只能作为“环境变更效应”记录，不得进入 §G2 的优化前后对照。

## 四、当前在线生效事实（ENV2 起服实测）

- 后端 pid 35040（`:8081`）、代理 pid 31136（`:8080`），配置指纹 `0b0d2806eb9a9d1a`
- 硬件参数：`-c 65536 / -np 1 / -b 2048 / -ub 512 / -ctk q4_0 -ctv q4_0 / -fa on / -ngl 99`，MTP 关，采样 `server_default`
- 预热：`req_001_192027.json`，`prompt_n=64358  cache_n=0  prefill=123.1 s`
- 冒烟（经代理真实推理）：通过 `1.08 s`，`finish_reason=stop`
- 瘦身：仅 `location`（省 14689 字符）；工具体契约加固与错误策略块均为开

## 五、G 阶段现状与待办（截至 2026-09-27 22:20）

已完成：夹具（含 `logs/run.log` 千行与第 137/811 行错误）、`MANIFEST.json`、
客观验收 `check_tasks.py`（含负向自检）、驱动 `bench_harness.py` / `bench_multiturn.py` / `run_all.py`；
**G1** B 配置 9 项批量（含复跑）与 **G2** 任务 11 / 任务 10（普通五轮）与任务 8 人工视觉验收。

待办：A 配置（修复前代理 v2）对照（G3）；宿主管存压力处置与受控性能基线（G4）；
阶段 H 部署、回滚演练与交付清单；压缩边界五轮（受本地 harness 能力限制，**未实现**，已如实标注）。

## 六、G 阶段结果摘要（环境变更后新采，与变更前数字不可比）

| 任务 | 判定 | 墙钟(s) | 轮数 | 要点 |
|---|---|---|---|---|
| 1  | 通过 | 10.0 | 3  | 五条约束齐全，`source.txt` 哈希未变 |
| 3  | 通过 | 57.5 | 14 | 工具重复 3 次后自纠；夹具 350 判据通过 |
| 4  | 通过 | 14.6 | 6  | 六行 JSONL，重复行保留 |
| 5  | 通过 | 10.9 | 3  | 仅交付格式变化，notes/source 未改 |
| 6  | 通过 | 31.4 | 7  | 首次误判为失败系**验收脚本缺陷**，修正后复跑 5/0 |
| 7  | 通过 | 40.0 | 5  | 单文件离线 HTML，无外链 |
| 8  | 通过 | 103.5 | 5  | 自动化 6/0 + 人工看图确认（旋转动画为真，起伏幅度小） |
| 9  | 通过 | 8.6  | 3  | 至多一次失败读取，未创建 `missing.txt` |
| 10 | 通过 | 5 轮摘要 + 3 收尾轮 | — | 修正驱动截断缺陷后 3/0；末轮写出 `final-summary.md` |
| 11 | 通过 | 16.0 | 6  | 预置结果哈希一致（未重做），待办已完成 |
| 12 | **失败** | 74.2 | 16 | 两轮一致：给按行统计（paid 4/550），未给方案要求的**去重 3/350** |

小计：11 项中 **10 项通过 / 1 项失败**（任务12）；压缩边界五轮未实现。
判据一律以产物为准、不看模型自述；缺失指标写 null 并注明原因，不写 0。

## 七、本轮新增的工具缺陷修正（全部留痕，附备份与 sha256）

| 文件 | 缺陷 | 前 → 后 sha256 | 备份 |
|---|---|---|---|
| `bench\check_tasks.py` | 任务6 判据与方案口径冲突（要求正文出现 "ERROR" 两次，而任务要求"仅保留行号/错误码/原因"）；任务12 判据过松（`\b3\b` 全篇匹配，被标题"## 3."误命中）；docstring 宣称的 `--selftest` 未实现 | `69bdb824…` → `ae549ca3…` | `backup\stageG\check_tasks.py.preG1fix` |
| `bench\bench_multiturn.py` | 只有 4 轮切片（方案要求五轮）；切片写进只读夹具目录；五轮后直接退出，截断模型末轮已发起的工具链 | `f60aed4d…` → `683c1f70…` → `736710ac…` | `backup\stageG\bench_multiturn.py.preG2` / `.preG2b` |
| `bench\bench_harness.py` | 测量字段键名不匹配（代理写 `prompt_evaluated_tokens`/`cache_reused_tokens`，harness 读 `prompt_n`/`cache_n`）导致全为 null；缺思考/输出 token 等 §14.3 字段 | `53e44566…` → `c1693cee…` | `backup\stageG\bench_harness.py.preG2c` |

修正后负向自检仍为 **5 通过 / 13 失败**（与修正前一致），仪器未因放宽而失效；
`--selftest` 已可用。任务12 的失败**不因脚本修正而改变**（已复跑确认可复现）。
## 八、阶段 G3：A 配置（修复前代理）受控对照 + 任务 2 补齐 —— 完成（2026-09-27 22:35）

**口径**：§14.3 的 A = 当前 WorkBuddy + **修复前代理**。此前第九/十一节只有"修复后"的 B 采样，本轮补做受控 A：同一后端进程、同一夹具、同一 harness，只替换 :8080 上的代理。

**切换留痕（只换代理，后端未重启）**

- 现状（修复后）代理 sha256 `6ACFB9C5…`，备份为 `optimization\20260927_165311\backup\stageG\preA_proxy__bonsai_proxy.py`。
- 被对照的修复前代理 `backup\proxy__bonsai_proxy.py`，sha256 `5DAAB527…`；其 CLI 为 `--port/--upstream/--warm/--warm-file/--effort/--keep-location`，**不接受 `--config`**，故不经 launcher、手动起在原端口。
- 停代理 pid 31136（先核对 cmdline 身份；`taskkill /PID` 被拒后 `/F`）→ 起 A 代理 pid 33800（`--effort medium`，瘦身三项全开，日志 `baseline\stageG_A_proxy.log`）→ 跑完停 33800 → `launcher up` 恢复修复后代理 pid **18008**；`launcher status` 指纹回到 **0b0d2806eb9a9d1a**，后端仍是 pid 35040（在线参数与配置一致，未重启）。
- 副作用：`capture\*.json` 225→309（新增均为 <20000 字符的 `small_*.json`，不会被预热取材误选）；`capture\effort.txt` 改写为 `medium`（与 B 配置同值）；`capture\timings.jsonl` 追加 63 条。

**测量口径差异（必须声明）**：修复前代理不写 `logs\requests.jsonl`，A 的 `prompt_n/cache_n/decode_tps` 在 `results.jsonl` 中为空数组（非 0）；A 侧改由 `capture\timings.jsonl` 增量取数（起点 offset 49741，63 条），与 B 通道不同源，只作量级比较。

**结果（12 项，A 与 B 同条件）**

| 任务 | A（修复前代理） | B（修复后代理） |
|---|---|---|
| 1 | 4/0 通过 8.8s | 4/0 通过 9.4s |
| 2 | 4/0 通过 16.4s | 4/0 通过 16.6s（本轮补齐，此前 A/B 均缺项）|
| 3 | 5/0 通过 105.4s / 重复 6 | 5/0 通过 71.3s / 重复 3 |
| 4 | 5/0 通过 18.1s | 5/0 通过 14.9s |
| 5 | 5/0 通过 15.1s | 5/0 通过 10.9s |
| 6 | 5/0 通过 35.9s | 5/0 通过 31.2s |
| 7 | 5/0 通过 44.4s | 5/0 通过 39.4s |
| 8 | **0/1 失败** 94.2s（1 轮，`finish=length`，零工具调用） | 6/0 通过 101.8s（5 轮） |
| 9 | 3/0 通过 12.9s | 3/0 通过 8.7s |
| 10 | 3/0 通过（5 轮 + 6 收尾轮，含 3 次参数完全相同的 `read_file`） | 3/0 通过（5 轮 + 3 收尾轮，自行停止）|
| 11 | 2/0 通过 15.7s | 2/0 通过 16.2s |
| 12 | **3/2 失败** 57.1s | **3/2 失败** 74.1s（两配置均稳定失败）|

**9 项批量汇总**：成功数 A 7/9 → B 8/9；中位墙钟 35.9s → 31.2s（-13.1%）；合计墙钟 391.9s → 361.7s；总轮数 63 → 62；工具重复调用 8 → 5；截断 1 → 0。**12 项总通过数：A 10/12，B 11/12。**

**另一条 A 侧现场证据**：`capture\timings.jsonl` 本轮 63 条中 3 条按修复前判据（`prompt_n < 1500`）被判 `hit=false`，而其 `cache_n` 为 2843 / 4912 / 5364 —— P08"高比例复用被误报为全量重算"的现场复现；修复后代理已改为 `cache_reuse` 四档。

**结论（不与目标口径混淆）**

1. §14.3 的 A/B 两档现在都有同条件实测，不再以历史记录代替 A。
2. 工程修复方向正确：成功数 +1（任务 8）、中位墙钟 -13.1%、工具重复 -3。但**样本仅 9 项、单次采样，不足以宣称稳定的量化提速**。
3. 未达到 §2.1"中位耗时改善至少 20%"的目标，按方案要求报告为"稳定性与可靠性修复完成，尚未有充分证据支持大幅提速"。
4. 任务 8 的 A/B 翻转、任务 10 的重复调用差异都含"整包修复"混淆因素（A 同时缺 C/D/E/F），**不单独归因于某一项修复**。

**未做/下一步**：G4 宿主管存压力处置（只读证据已存 `baseline\stageG_G4_hostmem_readonly.txt`；处置动作超 §0 默认范围，须先交证据与改动清单由用户决定）；H 部署、回滚演练与交付清单。


## 九、阶段 H：部署门槛、回滚演练与交付清单 —— 完成（2026-09-27 22:46）

### 9.1 交付物清单（对应 §H3）

| 交付项 | 路径 | 规模 | 状态 |
|---|---|---|---|
| 逐文件变更记录 | `optimization\20260927_165311\changes.md`（含本阶段第十三节） | — | 完成 |
| 最终配置 | `optimization\20260927_165311\effective-config.json` | 9,947 B | 完成 |
| 测试明细（含失败） | `bench\results.jsonl` / `optimization\20260927_165311\results.csv` | 33 行 / 9,079 B（36 行） | 完成 |
| 基线与最终对照 | `optimization\20260927_165311\comparison.md` | 9,491 B（9 节） | 完成 |
| 回滚方案与验证 | `optimization\20260927_165311\rollback.md` | 15,752 B（R0~R7） | 完成 |
| 日常启动说明 | `optimization\20260927_165311\日常启动说明.md` | 9,709 B（212 行） | 完成 |
| 四类状态清单 | 本节 9.4 | — | 完成 |
| 回滚演练脚本 | `optimization\20260927_165311\tests\rollback_drill.ps1` | 4,924 B | 完成 |

本阶段**未改动任何生产代码与配置**（`proxy`、`config`、`launcher` 均未改），只新增交付文档、演练脚本与只读证据。

### 9.2 部署门槛（§H1）逐条核对

| §H1 门槛 | 实测 | 结论 |
|---|---|---|
| 离线代理测试通过 | 阶段 C（36/36）、D、E、F（61/61）离线套件通过 | 达成 |
| 小型真实 API 测试通过 | `launcher smoke` 通过（0.94 s / 0.55 s，`finish=stop`） | 达成 |
| 关键任务成功率没有下降 | 12 项 A 10/12 → B 11/12 | 达成（不降反升） |
| 配置差异、备份及回滚脚本齐全 | `launcher show-config`/`status` 可查指纹与身份；`backup\MANIFEST.csv`；`rollback.md` | 达成 |
| 服务空闲时才切换 | 演练第 [0] 步确认后端忙槽=无后才动手 | 达成 |
| 能只更新代理就不重启后端 | 本轮预算仍 `policy=false`（未改后端默认参数）；演练中后端 pid 35040 全程未重启 | 达成 |

### 9.3 回滚演练实测（§H2）

演练只替换 `:8080` 上的代理文件，后端全程不动。实测链路：
停代理（身份核对）→ 覆盖 `backup\stageF\bonsai_proxy.py.preF`（sha256 变 `A375F4F3…`，`harden_tool_schemas`=False）
→ `launcher up`（后端"已在运行 pid=35040、参数一致、无需重启"）→ `:8080 /health`=ok、build `b181-9ef3205`、
`n_ctx=65536`、alias `bonsai-2-27b`、smoke 0.94 s `finish=stop`
→ 前滚 `backup\stageG\preA_proxy__bonsai_proxy.py`（sha256 回到 `6ACFB9C5…`，`harden_tool_schemas`=True）→ smoke 0.55 s。
日志 `baseline\stageH_rollback_drill.log`（9,615 B）；完整实录见 `rollback.md` R7。
**结论：代理层回滚与复原实跑可用，且不需要重启后端。**

### 9.4 四类状态清单（不得混写）

#### （A）已完成 —— 本轮交付且已验证

- 唯一配置源 + 唯一启动器：`config\bonsai-agent.json`（指纹 `0b0d2806eb9a9d1a`）→ `launcher\bonsai_launcher.py`；5 个入口脚本全部改为经 launcher（实测其内容确含 `bonsai_launcher.py`）。
- 避免误杀：B2 重写"僵死"判定；忙时不探活/不重启；停止只操作 state 中核对过身份的 PID；端口被他人占用即停手。
- 代理 v3：流式读取、每请求日志 `logs\requests.jsonl`、四档超时、排队串行化。
- 输入预算闸门：`/apply-template`+`/tokenize` 精确核算，`mode=warn` 只告警不裁剪。
- 取消/超时：`MSG_PEEK` 检出 + 30 s 内轮询 `/slots` 验证后端释放（不假设 close 即取消）。
- 缓存识别：`cache_reuse` 四档，修正 P08 部分命中误报全量重算。
- 工具体可靠性：`schema_hardening`（`show_widget.loading_messages` 精确契约 + 语义校验 + 历史审计）、`error_policy`（工具错误恢复策略块）。
- 瘦身逐项开关：`locations=true` / `deferred_tools=false` / `subagents=false`（恢复工具名与子代理名册）。
- G 阶段：12 项固定任务 A/B 同条件实测，失败项保留（任务 12 两配置均稳定失败，如实计入）。
- H 阶段：交付 7 件 + 回滚演练实测通过。

#### （B）未启用候选 —— 代码/配置就绪，但默认关闭，未开启

| 候选 | 当前 | 开启方式（改后**需手动重启代理**） | 已知代价/前提 |
|---|---|---|---|
| 请求级总生成预算注入 | `budget.policy.apply_request_max_tokens=false` | 置 `true` | 阶段 D 已行为验证二进制支持；开启后改变线上生成上限 |
| 请求级思考预算注入 | `budget.policy.apply_thinking_budget=false` | 置 `true` | 同上；需确认与客户端已指定档位不冲突 |
| 输入超预算改为生成前拒绝 | `budget.gate.mode="warn"` | `tests\set_gate_mode.py reject` | 会在生成前返回 400，可能中断原本可跑完的任务 |
| 压缩 ToolSearch deferred 工具名册 | `slimming.deferred_tools=false` | 置 `true` | 省约 2,512 tok，但会让模型看不到工具名（§P09 明令恢复） |
| 压缩子代理类型名册 | `slimming.subagents=false` | 置 `true` | 省约 1,200 tok，同上损伤发现能力 |
| 开启 MTP | `backend.mtp.enabled=false` | 置 `true` | 历史为长上下文负收益；仅在短输入+显存余量+正确性满足时重测 |
| 短上下文档（降 `-c`） | `-c 65536` | `backend.n_ctx` 下调 | 仅当真实输入显著降低后才有意义，且需重启后端 |
| 固定采样参数做对照 | `sampling.mode="server_default"` | 填 `sampling.params` | 需固定其余参数、一次只改一项 |

#### （C）客户端限制 —— 代理层无法强制，只能在客户端侧解决

- **工具参数校验与重试决策在 WorkBuddy 客户端**。代理只能加固"模型看到的契约"（`schema_hardening`）与并入策略块（`error_policy`），**无法强制客户端行为**。
- **历史压缩在客户端**。代理不做静默裁剪，超预算只能 `warn`/`reject`；真正"整理历史"需客户端配合。
- **取消的最终语义取决于客户端是否真的断开连接**。代理侧只能检出（`MSG_PEEK`）并验证后端释放，无法替客户端发起取消。
- **本轮 A/B 均为本地 harness（OpenAI 兼容 /v1），不是 WorkBuddy/Pi**。§14.3 的 A/B/C 三档客户端口径**未被本轮覆盖**，客户端侧的工具校验、重试决策与压缩行为未进入对照。

#### （D）需用户决定 —— 超出 §0 默认授权范围，未擅改

1. **G4 宿主管存压力处置**：证据已存只读快照 `baseline\stageG_G4_hostmem_readonly.txt`——物理内存 32,189 MB / 空闲 10,623 MB；`llama-server` WorkingSet 380 MB vs Private/commit **16,584 MB**；Memory Compression **9,019 MB**；后端命令行**无 `--no-mmap`**；C: pagefile 固定 8192 MB，D: 初始 65,536 / 上限 131,072 MB。处置动作（改 mmap/pagefile/内存策略）需先交具体改动清单由用户批准。→ **2026-09-27 用户已批准并执行 C1（`--cache-ram 1024`），见第十节；C4 不纳入。**
2. **是否启用请求级预算注入**（`policy` 两项）。
3. **是否恢复工具名册压缩**（`deferred_tools` / `subagents`）——功能发现能力与 token 的取舍。
4. **压缩边界五轮**：本地 harness 无压缩器，**未实现**（已在 `bench_multiturn.py` docstring 如实标注）。
5. **§14.3 要求的三次采样**：本轮各项仅单次采样，未做三次。
6. **母本行尾混用**（872 行中 135 行 CRLF、737 行 LF）是否统一。

### 9.5 §11 最终验收勾选表对照（14 项）

| # | 验收项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 实际进程与文档/配置一致，参数变化可检测 | 达成 | `effective-config.json` 实况核对（`backend_params_match_config=true`）；`launcher show-config`/`status` |
| 2 | 请求级预算支持有行为证据，不只看源码或 HTTP 200 | 达成 | 阶段 D 探针实测（`results\stage_d_probe.*`） |
| 3 | 普通任务有明确生成预算，思考与输出各有空间 | **部分** | 预算已登记（总 8192 / 思考 2048 / 余量 1024），但 `policy=false` 未注入；是否注入属 9.4(D) |
| 4 | 输入窗口不足在生成前可识别，不静默删消息 | 达成 | `budget.gate` 精确计数 + `warn/reject`，不裁剪 |
| 5 | 忙时探活不杀健康服务，不抢占用户任务 | 达成 | B2 重写；忙时不探活/不重启；`stop` 忙时拒绝（需 `--force`） |
| 6 | SSE 分块、Unicode、终止帧和断流测试通过 | 达成 | 阶段 C 离线套件（36/36） |
| 7 | 客户端取消后后端请求停止或明确标出未实现 | 达成 | `MSG_PEEK` 检出 + `release_wait_s=30` 内 `/slots` 释放验证 |
| 8 | 缓存状态按有效计数识别，部分命中不误报全量重算 | 达成 | `cache_reuse` 四档；P08 在 A 侧现场复现（见第八节） |
| 9 | 同一个工具参数错误不会引发无上限重试 | 达成 | `error_policy` 策略块 + `tool_arg_audit` 观测 |
| 10 | 工具发现与参数约束未因精简而丢失 | 达成 | `deferred_tools/subagents=false` 恢复名册；`schema_hardening` 精确契约 |
| 11 | 12 个固定任务有基线与候选结果，失败项没有被排除 | 达成 | `bench\results.jsonl` 33 行含失败；任务 12 保留 |
| 12 | 优化成功率未下降；速度收益来自同条件测量 | **部分** | 成功率不降反升（10/12→11/12）；速度为同条件测量但**单次采样** |
| 13 | 未达到性能目标时已如实报告，而非宣称"大幅提升" | 达成 | `comparison.md` §7 结论 3 |
| 14 | 可以按文档恢复旧配置，用户数据和其他 agent 改动完整 | 达成 | R7 演练实证；全程未用 `git reset`/按端口盲杀 |

### 9.6 未做/下一步

- 9.4(D) 剩五项待用户决定（第 1 项 G4 已由用户批准执行 C1，见第十节）；3、12 两项为"部分达成"，其缺口与 9.4(D) 的第 2、5 条同源。
- 客户端口径（WorkBuddy/Pi）的 A/B/C 三档对照未在本轮覆盖，属独立课题。


## 十、阶段 G4：限制服务端宿主 prompt cache（`--cache-ram 1024`）—— 完成（2026-09-27 23:14）

**授权**：9.4(D) 第 1 项原为“需用户决定”。用户于 2026-09-27 明确批准「C1 + `--cache-ram 1024`，现在执行」；
C4（提高 `-c`）经用户决定**不纳入**，保持 65536。

**变更**：仅 `config\bonsai-agent.json` 的 `backend.extra_args`：`[]` → `["--cache-ram", "1024"]`
（6,276 B `D678A79A…` → 6,297 B `A6876638…`；备份 `backup\stageG4\bonsai-agent.json.preG4`）。
经 `launcher up --no-prewarm` 生效（漂移检出 → 空闲受控重启后端 pid 35040 → 35084）；代理 pid 40480 **未重启**。

**证据与结论**

- llama-server `Private Bytes` **16.58 GiB → 9.56 GiB**，差 **7.017 GiB**，与 `--cache-ram` 上限差
  **7.000 GiB（8192−1024 MiB）** 偏差 **0.25%**（近似 1:1）→ 证实 C1 生效，并**间接证实**“变更前
  16.58 GiB 私有提交主要构成为宿主 prompt cache”（原仅为推断；逐块拆解仍缺）。
- 缓解：Memory Compression WS 4,112 → 1,494 MB；全机 Available 5,780 → 6,809 MB；Committed 43.36 → 35.71 GiB。
- 回归：bench 任务 1（9.2 s/3 轮/0 重试/验收 4 通过）与任务 2（15.9 s/4 轮/0 重试/验收 4 通过），
  `prompt_n`/`cache_n` 与变更前**逐项一致或略优** → 短会话无回归。
- 失败如实记录：首次以新 cfg 名 `G4-cram1024` 运行时，因 `bench\run_all.py` 的 `prep()` **不复制夹具**
  导致 `read_file notes.txt => ERROR: file not found`、探索至 `max_rounds=16` 失败（0 通过/1 失败）；
  补齐 `runs\G4-1024\` 夹具后通过。**属执行脚手架疏漏，与被测的 `--cache-ram` 无关**；失败记录保留在
  `bench\results.jsonl` 中未删除。

**未验证 / 残余风险**：长上下文跨请求复用**未验证**（bench 仅到 `n_tokens_max=7,096`，变更前真实使用达
**64,358**；单个 64 K 检查点约 **2,030 MiB** > 新上限 1024 MiB → 长上下文检查点可能无法保留、TTFT 可能回归）；
仅跑 2/12 项任务；绝对内存值不可比（uptime 与序列长度不同）；`pages input/sec` 波动大，不可归因。

**产物**：`G4 验收报告-C1 cache-ram 1024.md`（8,253 B，sha256 `53E8827E…`）、`G4 处置候选清单.md`
（14,617 B，`F789234C…`）、`baseline\stageG4_cram1024_readonly_v3.txt`（2,578 B，`204F8CE6…`）、
`baseline\stageG_G4_hostmem_readonly_v2.txt`（6,118 B，`A34251E7…`）。
逐文件记录见 `changes.md` 第十四节；回滚入口 `rollback.md` **R8**。

**建议**：保留 `--cache-ram 1024`，在真实长上下文使用中观察 TTFT；若出现回归，按候选清单升到 2048 / 4096。


---

## 十一、阶段 G4 补：长上下文跨请求复用对照实验（残余风险验证）—— 完成（2026-09-28 00:41）

第十节所列**唯一残余风险**（64 K 宿主检查点 1.88–2.03 GiB > `--cache-ram 1024` 上限 → 跨请求复用可能丢失、
TTFT 可能回归）已按四臂对照验证：**风险落实，因果坐实，门槛在 2048 与 4096 之间。**

方法：固定 64 K 真实请求体 `capture\req_001_192027.json`（`prompt_n=64,396`）走生产同一转换管线直连后端；
每臂 A1 冷启 → A2 同请求 → B 用另一段 7,687 token 请求顶走槽位 → **A3 再发同一 64 K 请求**。
唯一变量为 `--cache-ram`。

| `--cache-ram` | A3 cache_n | A3 复用 | A3 墙钟 | 判定 |
|---:|---:|---|---:|---|
| 1024 | 0 | 无复用 | 118.5 s | 风险落实 |
| 2048 | 0 | 无复用 | 118.4 s | **不足**（检查点被写入后立即挤掉） |
| 4096 | 64,392 | 完全复用 | 0.65 s | 有效 |
| 8192 | 64,392 | 完全复用 | 0.85 s | 有效 |

要点：
- **影响边界**：A2（单条对话内继续追问）四臂均 `cache_n=64,392`、0.23–0.35 s → **短会话零回归**；
  受损的仅是「切走再回来 / 跨上下文」的长上下文复用（每次 +118 s）。
- 内存代价：8192 与 4096 在均持有 64 K 检查点时为 10.01 GiB（perfmon Private Bytes，两者差 ~2 MB）；
  上限差 4096−1024 = 3,072 MiB 为配置层开销上限。
- **生产配置已恢复 `--cache-ram 1024`**：config sha256 `A6876638…`（与备份 `bonsai-agent.json.cram1024`
  逐字节一致）、指纹 `96df0f5964452b3c`、后端 pid 30160、前后端 `/health` 均 ok。
- 产物：`G4 长上下文对照.md` 及 `baseline\g4_longctx_*`（4 份 result JSON、后端日志全量副本、内存快照）。
  逐文件见 `changes.md` 第十四节 14.5。

**建议**：保持 1024；若需恢复跨上下文长上下文复用，升到 **4096**（已实测有效），**不要选 2048**（已实测无效）。
## 十二、阶段 G5 补：三次采样对照

依 §14.3 第 3 条在同一后端（pid 30160，`--cache-ram 1024`）上逐项 A/B 交替、每项三次重采，窗口 2026-09-28 01:04:33 → 01:50:18，66 次 harness 调用。A = 修复前 v2 代理（另起 :8082，零次生产代理切换），B = 修复后 v3 代理（生产 :8080）。

| 指标 | A | B |
|---|---:|---:|
| 成功 / 尝试 | 27 / 33（81.8%） | 24 / 33（72.7%） |
| 成功任务耗时中位数 | 17.4 s | 17.1 s |
| 全部尝试总墙钟 | 1346.4 s | 1398.4 s |
| 工具重复调用数 | 14 | 19 |
| 超时 / 崩溃 | 0 / 0 | 0 / 2 |

要点：
- **配对耗时口径**（两臂各 3 次全部通过的 8 项）：A 630.0 s vs B 653.0 s，**B 慢 3.7%**；计入隔离起点版任务 7 后 A 764.6 s vs B 857.7 s。**本批不支持「修复后代理有稳定提速」**。
- **成功率经扣除后两臂相同**：剔除截断失效的任务 8 后 A 27/30、B 24/30；再扣除任务 7 的目录污染（隔离对照证明 B 亦 3/3 通过）后**同为 27/30 = 90.0%**。
- 任务 7 主批差异真因 = 同目录中任务 5 把 `results\constraints.md` 的交付格式改成「纯文本」，B 的 `status.html` 照抄该文件而缺 `Markdown` 关键词；**与代理实现无关**。
- 任务 8 两臂 6/6 失败，根因 `max_tokens=4096` 截断；其中 2 行因 harness 未捕获 `HTTPError` 崩溃而字段记 null。任务 12 两臂 6/6 失败 = 稳定的真实能力缺口。任务 10 无驱动可跑，按第 4 条记 null 及原因。
- 生产现场未受影响：:8080 pid 40480 / :8081 pid 30160 前后一致、`/health` ok、config sha256 `A6876638…` 前后一致；`:8082` 已释放。
- **§12.6 单次采样「B 略优」的方向在本批三次采样中未复现**，§12.6/§12.9「单次采样不足以宣称稳定提速」的定性得到加强。
- 产物：`G5 三次采样对照.md`（17209 B，sha256 `85efac814a66082e…`）及 `baseline\g5_*`；`backup\stageG5\bench_harness.py.preG5`（harness `--port` 补丁前备份，向后兼容默认 8080）。逐文件见 `changes.md` 第十五节。

**建议**：① 保持 `--cache-ram 1024`（与第十四节一致）；② 任务 12 的能力缺口走提示/工具链方向；③ 任务 8 另设放开 `max_tokens` 的实验再判；④ C 臂（Pi）仍按第 6 条默认门禁。

## 十三、阶段 G6 补：任务 8 放开截断对照

依第十二节末「建议③：任务 8 另设放开 `max_tokens` 的实验再判」执行。**唯一改动**：harness `--max-tokens`
4096 → **8192**；其余受控条件与 G5 完全一致（同后端 pid 30160 / `--cache-ram 1024`、A = 修复前 v2 代理
另起 :8082、B = 生产 v3 代理 :8080 pid 40480、同夹具、同 `temperature=0`/`stream=True`/`tool_choice=auto`、
同 `--max-rounds 16 --time-cap 1500`、同交替顺序）。窗口 2026-09-28 02:59:58 → 03:21:57，6 次调用。

| 指标 | A | B |
|---|---:|---:|
| 成功 / 尝试 | **3 / 3（100%）** | **0 / 3（0%）** |
| 成功墙钟中位数 | 207.7 s | —（无成功样本） |
| 全部尝试总墙钟 | 623.6 s | 694.7 s |
| `pelican.svg` XML 合法 | 3/3 | **0/3** |

要点：
- **第十二节的截断假设被证实**：放开后两臂轮 1 `finish` 由 `length` 变为 `tool_calls`；A 臂由「连文件都没写出」
  变为 **3/3 写出合法 SVG**，证明任务 8 的 A 臂失败**纯由 4096 截断造成**，非能力缺口。
- **B 臂稳定失败点是写出的 XML 非法，与截断无关**：3/3 逐字节相同，失败项恒为
  `duplicate attribute: line 7, column 36`；第 7 行 `<line x1="155" y2="95" x2="235" y2="95"/>`
  **`y2` 重复、`y1` 缺失**。同一 8192 预算下 A 通过，故不是预算问题。
- **两臂送给后端的首请求不同**：轮 1 同一份初始消息下，新评测 token A **522** / B **641**（复用同为 109），
  轮 1 请求总长 A 631 / B 750（**B 多 119 token**），三次一致 → 代理层实际转发内容不同；
  与 v3 的 `tools.error_policy`（第一条 system 文本尾并入常驻策略块）相符，但**未做请求体 diff，机制未确认**。
- **「与代理版本相关」的可复现差异**（不同于第十二节任务 7 的目录污染）：同后端、同温度、同输入，
  两臂输出确定性不同。**但不得据此称 v3 更差**——单任务 3 次样本，且 A 臂自身异常（跑满 16 轮不自终止）。
- **新增两个待处理问题**：① 两臂请求内容并不相同（须做转发内容 diff）；② B 的自检脚本 `results/check.py`
  为 **0 字节**、自检空转，导致非法 XML 被当作完成品交付。
- 生产现场未受影响：:8080 pid 40480 / :8081 pid 30160 前后一致、`/health` 均 200、
  config sha256 `A6876638…` 前后一致、:8082 已释放；本批未改生产配置、未重启生产进程。
- 产物：`G6 任务8 放开截断对照.md` 及 `baseline\g6_*`；`bench\results_g6.jsonl`、
  `bench\runs\{A,B}-s8-{1,2,3}\`。逐条见 `changes.md` 第十六节。

**建议**：① 把 B 臂任务 8 失败**单独立项**，下一步做「同一请求体分别打 :8082/:8080 + 逐字节 diff」定位机制；
② A 臂「跑满 16 轮不自终止」记入已知行为清单；③ 任务 8 进正式对照须固定足够 `max_tokens`（8192 已验证够用）
并观测自检脚本；④ 任务 10（压缩边界五轮）仍待补驱动。

## 十四、阶段 G7 补：代理转发内容对照

依第十三节末「建议①：下一步做同一请求体分别打 :8082/:8080 + 逐字节 diff」执行。用**记录型上游桩**
（A 桩 :8098 / B 桩 :8099）抓取两代理**实际转发体**：A = v2 sha256 `5DAAB527…` 起 :8082、
B = v3 生产脚本 sha256 `6ACFB9C5…` 起 :8083（B 臂用生产配置副本，仅改 4 个输出路径 + `prewarm.enabled=false`，
行为段一致）；请求体由 `load_harness()` 取 `bench_harness.py`（`F0685208…`）构造，两臂**同一份**
（1917 B，sha256 `d32afaad…`）；两臂均 `--effort medium`。窗口 2026-09-28 04:19:31 → 04:19:33（约 2 秒，无推理）。

| 项 | A（v2 / :8082） | B（v3 / :8083） |
|---|---:|---:|
| 转发字节 | 1973 | 2563 |
| `messages[0].content` 字符 | 628 | **1212** |
| 唯一实质差异 | — | system 尾部 +**584** 字符 |

要点：
- **机制实测确认（非推断）**：A→B **唯一实质差异**是 `messages[0].content` 尾部追加 **584 字符**，
  **逐字符等于** v3 的 `TOOL_POLICY_BLOCK`（由 `tools.error_policy=true` 触发）；其余候选**全部排除**——
  `tools` 两臂全等（`schema_hardening` 未命中）、`slimming.locations` 无命中、`chat_template_kwargs`
  两臂相同（`--effort` 注入，非差异）。
- **字节对账闭合**：B−A = 590 = 584 字符 + 6 个换行 JSON 转义；A−发出体 = 56 = `chat_template_kwargs`。
  → 第十三节「B 多 119 token」的来源**实测等于该 584 字符块**。
- **不改结论边界**：本批**不产生模型输出**（桩立即返回），只证明转发内容差在哪，**不构成能力/好坏判定**，
  也**不支持「v3 更差」**；它把第十三节遗留的「机制待确认」**关闭**。
- **不得据此称策略块有害**：其收益场景（工具错误连续重试）本批未测。
- 局限：单请求、每代理 1 次；B 臂为生产配置副本（行为段一致）；A 臂（v2）CAP 硬编码向生产抓包目录
  新增 1 个 `small_001_041931.json`（1917 B），`capture\timings.jsonl` **905→905 未污染**。
- 生产现场未受影响：:8080 pid 40480 / :8081 pid 30160 前后一致、`/health` 均 200、config sha256
  `A6876638…` 前后一致；本批端口已释放；未改生产配置、未重启生产进程、未新增回滚入口。
- 产物：`G7 代理转发内容对照.md` 及 `baseline\g7*`。逐条见 `changes.md` 第十七节。

**建议**：① 机制问题已关闭，无需再补；② 若要判 `TOOL_POLICY_BLOCK` 对通用任务的影响方向，
另立「同代码开关 `tools.error_policy`」对照；③ 任务 10（压缩边界五轮）仍待补驱动。

## 十五、阶段 G8 补：`error_policy` 开关对照

依第十四节末「建议②：若要判 `TOOL_POLICY_BLOCK` 对通用任务的影响方向，另立同代码开关 `tools.error_policy` 对照」执行。

**受控**：**两臂同一份** v3 脚本 `proxy\bonsai_proxy.py` sha256 `6ACFB9C5…`（与生产一致）；P 臂
`tools.error_policy=true` 起 **:8084**、Q 臂 `=false` 起 **:8085**；上游**共用**生产 `llama-server`
**:8081**（pid 30160，`--cache-ram 1024`，未重启未改参）；配置为生产 `config\bonsai-agent.json`
（`A6876638…`）的**副本**（仅改 4 个输出路径字段 + `prewarm.enabled=false`，驱动自证 P `tools` 差异键 `[]` /
Q `['error_policy']`、两臂行为段一致）；任务 **8/3/6/11** 各 **2 轮**、交替顺序；
`temperature=0.0`、`--max-tokens 8192`、`--max-rounds 16`、`--time-cap 1500`。
主批 2026-09-28 04:30:39 → 04:54:06；补批 04:56 → 04:58。

| 臂 | `error_policy` | 通过/失败 | 任务 8 | 任务 3 | 任务 6 | 任务 11 | 任务 8 SVG |
|---|---|---:|---:|---:|---:|---:|---|
| P | true（=生产） | 4 / 4 | **0/2** | 2/2 | 2/2 | 0/2（主批无效） | 47 行 / 2468 B / **非法** |
| Q | false | 6 / 2 | **2/2** | 2/2 | 2/2 | 0/2（同上） | 58 行 / 3017 B / 合法 |

要点：
- **开关级因果确认**：仅切 `tools.error_policy`，任务 8 结果**完全翻转**（P 0/2 失败、Q 2/2 通过）；
  失败原因 P 两轮均为 `ParseError('duplicate attribute: line 7, column 36')`（第 7 行 `<line … y2=… y2=…>` 缺 `y1`、`y2` 重复）。
- **逐字节对齐**：G8-P ≡ G6-B（v3，`54B16F11…` 2468 B）、G8-Q ≡ G6-A（v2，`D8B1089F…` 3017 B）
  → 第十三节「v2 合法 / v3 非法」的差异**由 `tools.error_policy` 单独决定**，v3 其余改动不导致该失败；
  G7（第十四节）的「唯一转发差异 = 584 字符策略块」由此**闭合为因果证据**。
- **影响任务相关、非全局**：任务 3、6 两臂均满分；补批后任务 11 两臂均 2/2（预置 canonical sha256
  `ce3f1fca8433…` 未变）→ **不得**外推为「策略块在所有任务上有害」。
- **收益未测**：策略块面向「工具错误连续重试」，本批任务**未触发**该场景，**不得**据此判定「应删除该功能」。
- **任务 11 主批无效（驱动缺陷）**：`g8_run.py` 的 `setup_run()` 未按 `run_all.prep()` 规格预置
  `results/sales.json`，两臂同构 `got=None` 失败；补批（`.stage\g8_t11_fix.py`，仅预置该文件、目录加 `b` 后缀）
  两臂均 2/2。主批任务 11 不作为证据。
- 过程指标留痕（**不作结论**）：P 任务 3 为 15 轮 / 工具重复 8，Q 为 9 轮 / 0，方向与策略块第 1 条设计意图相反。
- 局限：`temperature=0.0`，每任务每臂 2 轮，两臂各自两轮逐字节相同；但 **n=2、任务 4 项**，
  不得据此改生产配置；token 口径取各臂自身 `logs/requests.jsonl` 增量。
- 生产现场未受影响：:8080 pid 40480 / :8081 pid 30160 前后一致、`/health` 均 200、config sha256
  `A6876638…` 未变、`capture\timings.jsonl` **905→905**、`logs\requests.jsonl` **656→667（+11 行）** 新增段
  **全为探针**（`/health` 6 + `/v1/models` 5，**0 条 `/chat/completions`**）、:8084/:8085 已释放；
  未改生产配置、未重启生产进程、未新增回滚入口。
- 产物：`G8 error_policy 开关对照.md` 及 `baseline\g8*`、`bench\results_g8*.jsonl`、`bench\runs\{P,Q}-t*`。
  逐条见 `changes.md` 第十八节。

**建议**：① 任务 8 为**开关级因果**，但不得推广为全局有害、不得据此改生产；② 若要落地「关闭 `error_policy`」，
须先补「工具错误重试」场景对照确认收益，并在多任务多样本上确认任务 8 负向可复现且无其它回归；
③ 任务 10（压缩边界五轮）仍缺驱动；④ A 臂（v2）CAP 硬编码落 `small_*.json` 于生产抓包目录的副作用仍未处理。

## 十六、阶段 G9 补：`error_policy` 全任务确认

阶段 G8 只在 4 项任务（8/3/6/11）上确认了「`tools.error_policy` 与任务 8 失败的开关级因果」，并明确
「影响任务相关、非全局、不建议据此改生产」。阶段 G9 把该对照扩到**全 11 项任务**（照抄 G5 任务集与夹具口径），
回答「关闭该开关能否仍消除任务 8 失败、且不引入其它任务回归」。

**设计**：两臂**同一份 v3 脚本**（`6ACFB9C5…`），仅配置副本 `tools.error_policy` 不同；
P=true 起 :8084、Q=false 起 :8085，上游共用生产 :8081；每臂每任务 2 轮、交替顺序；
`--max-tokens 8192` / `--max-rounds 16` / `--time-cap 1500` / `temperature=0`；
任务 11 按 `run_all.prep()` 预置 `results/sales.json`（修正 G8 主批的驱动缺陷）。
窗口 05:37:27 → 06:13:55。

**结论**

| 臂 | `error_policy` | 通过/失败（22 样本） | 失败任务 |
|---|---|---:|---|
| P | true（=生产） | 18 / 4 | 任务 8（0/2）、**任务 12（0/2）** |
| Q | false | **22 / 0** | 无 |

1. **任务 8 结果在全任务范围内复现**：P 0/2（47 行 / 2468 B / XML 非法，第 7 行缺 `y1`、`y2` 重复）、
   Q 2/2（58 行 / 3017 B / 合法）；且 `G9-P ≡ G8-P ≡ G6-B(v3)`、`G9-Q ≡ G8-Q ≡ G6-A(v2)` 逐字节相同。
2. **新增：任务 12 同向**。P 两轮均 4/1 失败，失败项为「含两个错误 E137 / E811」——P 的 `summary.md`
   实写「总行数 622 / ERROR 1」，而事实为「1000 行 / ERROR 2」，**漏 `E811`**；Q 两轮 5/0 通过并正确写出 137、811。
3. **无回归**：9/11 项任务两臂通过/失败一致；Q 臂 22/22 全通过，未发现"关闭后变差"的任务；
   过程指标 Q 亦不劣（工具重复 0 vs 20；任务 3 轮数 9 vs 15）。
4. **产物层不同一**：7 项任务两臂均通过但产物内容不同 → 策略块确实改变模型输出，只是未表现为检查失败。
5. **须修正 G5 记录**：G5「任务 12 恒失败（能力缺口）」基于 `--max-tokens 4096`；8192 下 Q 臂 2/2 通过，
   该结论不再成立。4096 下失败是否由截断造成，本批未复测，不作确认。

**局限**：n=2、`temperature=0`（确定性复现，非随机抽样，不做概率外推）；任务 12 失败机理未分析；
任务 10 不在本批（含其「压缩边界五轮」仍为未实现项）；策略块的设计收益场景（工具错误连续重试）**仍未触发**。

**建议**：将 `tools.error_policy=false` 记为**生产候选**，但**不立即改生产**——先补「工具错误重试」场景对照
验证该策略块的收益，否则等于在未测收益的情况下删除一个功能。

**生产复验**：:8080 pid 40480 / :8081 pid 30160 未变、`/health` 200/200、config sha256 `A6876638…` 未变、
`capture\timings.jsonl` 905→905、`logs\requests.jsonl` 676→689（+13 全为探针、0 条 `/chat/completions`）、
:8084/:8085 已释放；未改生产配置、未重启生产进程。

**产物**：`optimization\20260927_165311\G9 error_policy 全任务确认.md`；`baseline\g9_*`；`bench\results_g9.jsonl`。


---

## 十七、阶段 G10 补：`tools.error_policy` 收益对照（专用驱动）

**为何补**：G8/G9 的结论是「关掉该开关无回归（Q 22/22，P 18/22，修好任务 8/12）」，
但**标准 harness 自带同义策略**（system prompt 内含 + 重复调用注入 SAME-call 提示），
使该块的**设计场景从未被触发** → 「关掉无回归」**不等于**「开着无收益」。

**做法**：自建**专用驱动**（不改 harness、不改生产），**2×2** 对照
　驱动侧 {N＝无本地策略 / L＝含 harness 同义策略＋运行时提示} × 代理侧 {P＝`error_policy=true`(:8084) / Q＝`false`(:8085)}，
　3 个「首次调用必失败」探针（`locked` 必 exit 1 / `boom` 必抛异常 / `absent` 读不存在文件且任务不可达）× 2 轮 = 24 run。

**结果**：

- 块的**独立收益首次获得正向证据**：N 单元 `absent` 上，开块 **2/2 收敛并报告阻塞原因**，
  关块 **0/2（撞满 12 轮上限、无最终回答）**。
- **客户端自带同义策略时块冗余**：L 单元上 P/Q 的轮数、同调用重复、工具调用序列、停止原因**完全相同**。
- `locked`/`boom` 场景块无行为差异（4 轮、0 重复、报告正确，仅措辞不同）。
- **反证**：N+P 样本 2 同一 `read_file` 同一错误被逐字重复 3 次（已满足块规则 1）→ 收益机理**未定位**；
  `absent` 的主导循环是 `list_dir`（返回**成功**的空列表，非错误），块按定义不该介入。

**处置**：**不改生产**，保留 `error_policy=true`；仅当确认生产客户端自身已具备等价错误恢复时，
关闭它才有冗余性依据。真实客户端重试行为**未验证**。

**局限**：n=2 且 N+P 的 `absent` 两轮不同（7 vs 12 轮）→ 记为**方向性观测**；
专用驱动口径**不可与 G8/G9 相加**。

**生产复验**：:8080 pid 40480 / :8081 pid 30160 未变、`/health` 200/200、config sha256 `A6876638…` 未变、
`capture\timings.jsonl` 905→905、`logs\requests.jsonl` 695→699（+4 全为探针、0 条 `/chat/completions`）、
:8084/:8085 已释放。

**产物**：`optimization\20260927_165311\G10 error_policy 收益对照（专用驱动）.md`；
`baseline\g10_summary.json`、`g10_fingerprint.json`、`g10_results.jsonl`、`g10_{P,Q}_config.json`；
`bench\results_g10.jsonl`；`baseline\g10\runs\*`。

## 十八、阶段 G11/G12 补：任务10 压缩边界五轮补测

§14.2 第 10 项长期记为未实现（`§10.3`：标准 harness 无任务 10 定义、本地无压缩客户端）。
本阶段用**专用驱动**补齐，口径与判据如下。

**口径**：压缩阈值 = `65536 − 8192 − 1024` = **56,320 token**；后端硬上限 = **65,536**；边界带 (56,320, 61,440)；
切片 = `B-t10b\logs\run.log` 的 5 段×200 行固定切片（哈希入 MANIFEST）。

**G11 三档（同后端 :8081、同实验代理 :8084、同 system/tools）**：
S 短上下文（普通五轮，输入 2,085→8,565）；N 边界穿越不压缩（输入 11,188→**57,373**）；
C 边界穿越 + §E2 压缩。三档交付均成功、**最初五条约束均列全**、`source.txt` 未变。
G11 暴露两个驱动缺陷（C 档因依赖代理 token 字段而**未压缩**；转发日志读取竞态）。

**G12 C2 档（修正后）**：压缩触发改为**自测精确投影**；第 5 轮前投影 57,292 > 56,320 → 按 §E2 替换
前 4 轮原始正文为「摘要 + 切片路径 + 行号 + sha256」→ 投影 **57,292 → 14,405**（显式削减 **42,887 token**）；
压缩后自测 14,405 vs 后端实际处理 14,486 → **无静默裁剪**；交付含完整五条约束；工具配对 2/2。

**G12b 闸门探针对照（单因子：字符/token 密度）**：两探针均标定 ≈57,000 token。
`P-dense`（1.85 字符/token）→ 闸门「在预算内(便宜路径)」而实际 62,831 token（> 阈值）→ **假阴性**；
`P-sparse`（5.83 字符/token）→ 精确计数判「**超预算**」→ 正确发现。两次运行一致。

**缺陷候选 F1（待决策，本轮未改生产）**：便宜路径上界 `tokens ≤ body_bytes/3.0` 的前提是 ≥3 字节/token，
而日志类素材 ≈1.87 字节/token。判据：**假阴性存在 ⟺ `d < 3.0` 字节/token**；`d=1.87` 时假阴性区间
token ∈ (56,320, 90,353]，**超过硬上限 65,536 也不会被告警**。
故 §E「超预算能在生成前被发现」**仅对 `d ≥ 3.0` 成立**。精确计数 125 ms/次，成本可接受；
建议下调 `chars_per_token_floor` 或对关键路径强制精确计数。

**偏差披露**：G12b 初版漏写 `H.PORT`，两探针误打生产 :8080（生产日志第 724/726 行 2 条 `/chat/completions`），
已修并加守卫，隔离重跑生产增量 0 条。

## 十九、阶段 G13 补：预算闸门 warn vs reject 对照

承接 §十八（G11/G12）：F1 确认后，需回答「切 reject 有何可测差异」。本批用**同一超预算输入**
（57,570 token > 阈值 56,320、< 硬上限 65,536）做 warn / reject 单因子对照。

**受控**：生产 v3 代理 :8084 → :8081；两份配置副本仅 `budget.gate.mode` 不同；每档 in（预算内 655 token）+
over（超预算 57,570 token）两探针。

**warn（生产现状）**：闸门正确判出超预算，仍**转发** → 后端处理 57,570 token、冷 prefill 101.7 s、占槽 ~106 s、
返回 200（截断）。**看得见但无保护**。

**reject**：同一输入 → **生成前 400**（`input_over_budget`），0.1 s、不占槽、无 prefill，返回结构化 budget 错误体；
`in` 探针 200，不误杀正常请求。

**交叉结论**：`reject` 与 floor 修复**正交缺一不可** —— reject 只堵「判出即拒绝」（sparse 素材）；
F1 的便宜路径低估（dense 素材，`act=pass`）即使切 reject 也不触发，仍须调 `chars_per_token_floor`（如 1.5）
或对关键路径强制精确计数。生产未改（仍 `mode=warn`）；生产现场复验无损、0 条 `/chat/completions` 增量。

## 二十、阶段 G14 补：生产切 reject 与 F1 修复

承接 §十九（G13 结论：reject 与 floor 修复正交缺一不可）。本阶段一次性落到生产配置并重启代理使其生效：

`budget.gate.mode` `warn→reject`（超预算生成前 400、不占槽）+ `chars_per_token_floor` `3.0→1.5`（F1 修复）。

改动仅经 `.stage` 脚本落盘，先改配置并备份（`backup\stageG14\bonsai-agent.json.preG14-reject`，旧 sha `a6876638…`，回滚源），
再核对 :8080 身份并受控重启代理（pid 40480 → 55872；后端 :8081 pid 30160 未动）。新配置 sha `f09a77be…`。

**验收**：G12b 同款 F1 假阴性素材 `probe-dense`（body 127KB）在 floor 1.5 下转精确 → 判超预算 → reject **400**
（`input_tokens=62249`、`headroom=−5929`、0.08 s、不占槽）；`probe-small` **200** 不误杀。生产 `:8080/8081 /health` 双 200。

**意义**：reject 只堵「判出即拒绝」（sparse 素材）；floor 1.5 让便宜路径低估素材（dense，`act=pass`）也被判出 → reject 覆盖两类素材。
遗留：真实客户端（WorkBuddy/Pi）在 400 后的重试/降级路径待业务观察。

## 二十一、阶段 G15 补：代理 400 观测日志（客户端真实行为埋点）

G14 切 reject 后，用纯观测日志收集 WorkBuddy/Pi 收到 400 的真实行为（直接报错 or 自动重试、几次能成功），
1–2 天后据数据决定是否加客户端智能降级（400 自动截断长文本重试 / 精简小窗口请求）。

**改动**（`proxy\bonsai_proxy.py`，备份 `backup\stageG15\bonsai_proxy.py.preG15-400log`，新 sha `d2a1f82f…`）：
新增 `client_mark(headers)` 提候选头作客户端指纹；reject 记录 `rec["client_mark"]` 随 `requests.jsonl` 落盘；
`_send_json(400)` 后用 `client_gone_peek` 探连接并 `print` 一行 `[400观测]`（含 conn=closed|alive）。不侵入业务。

应用：代理 55872→73972，后端 :8081 30160 不动，config sha `f09a77be…` 不变。验收通过（dense 400、small 200、client_mark 与 `[400观测]` 均已落盘）。

**观测 1–2 天**后，按客户端 + 每条 400 后时间窗聚合 `requests.jsonl`/`proxy.log`，判定重试次数与最终成败，再决定降级策略。
