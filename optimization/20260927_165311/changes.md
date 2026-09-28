# 变更记录 — Bonsai 本地模型通用优化

工作目录: D:\Bonsai-demo\optimization\20260927_165311
执行者: TRAE Agent，接手《Bonsai本地模型通用优化-交接执行方案》v1.1，执行阶段 A–H。
约束: 不得改 GPU 锁频/驱动/BIOS/VBS/电源/系统代理；不得卸插件/删记忆/换权重/升内核；
      服务有真实任务时不重启；每阶段记录 修改文件/原因/测试结果/未解决问题/回滚入口。

## 一、变更前既有状态（非本次新增，但必须记录）
| 文件 | 内容 | 状态 |
|---|---|---|
| dist\bonsai2-8gb-combo\start_all_agent.bat | KILLPORT 的 for /f 行: findstr \":%~1 \" 改为 findstr /R \":%~1[^0-9]\"（修复把 80800/18080 误判为 8080） | 保留 |
说明: 该改动由更早的会话做出。修复前原件 4850 字节，保存在 optimization\20260927_160739\backup\start_all_agent.bat
      （SHA256 39E14BEE8F2A56BB6C75BE6667B45937C3E1011371BBA86B4B59E4B0164306B2）。已用 Compare-Object 核对：当前文件与该备份的唯一差异就是这一行。
另: 更早会话尝试过的 --kv-mean-center 注入已全部回滚，当前四个启动器中均无该参数（与 MTP 冲突，实测有害）。

## 二、阶段 A：只读快照与可恢复备份 —— 完成
改动生产文件: 无。
新增文件:
  optimization\20260927_165311\capture_baseline.ps1    可复现基线采集脚本
  optimization\20260927_165311\backup\MANIFEST.csv     9 份备份的 SHA256 清单
  optimization\20260927_165311\baseline\*              运行事实快照（见 SUMMARY.md）
原因: 方案 §3 要求先有可恢复快照、备份清单与回滚方法；未完成不得部署修改。
测试结果: 9 份备份复制后 SHA256 与原件逐一致（match=true）。
未解决问题: 无。
回滚入口: 见 rollback.md（阶段 A 无代码改动，无需回滚）。

## 三、阶段 B–H
（每阶段完成后追加）

## 三、阶段 B：统一配置、避免误杀服务 —— 完成
方案要求（§4）：配置只保留一个权威来源；重写“僵死”判定；预热只执行一次。

新增文件:
  config\bonsai-agent.json        唯一权威配置（后端/代理/思考档位/预算/瘦身/预热/超时/日志/state）
  launcher\bonsai_launcher.py     统一启动管理器：构造参数 + 进程身份核对 + 启停 + 预热 + 冒烟
  optimization\20260927_165311\tests\stage_b_tests.py    阶段 B 验收测试（20 项）

修改的生产文件（8 个入口全部改为经 launcher 取参数，不再各自拼一份）:
  dist\bonsai2-8gb-combo\start_all_agent.bat         重写为薄封装（参数全部来自 JSON）
  dist\bonsai2-8gb-combo\start_bonsai_8gb_agent.bat  移除 --reasoning-budget 20480 / -n 24576
                                                     / --temp 1.0 --top-p 0.95 --top-k 20 / 直听 :8080
  dist\bonsai2-8gb-combo\start_capture.bat           移除 taskkill /F /IM llama-server.exe 盲杀
  dist\bonsai2-8gb-combo\warm_kv.bat                 改为调用 launcher prewarm
  dist\bonsai2-8gb-combo\start-bonsai.ps1            移除 -c 32768 / MTP ON / 20480 / 24576
  serve.py                                           移除自带 32768/MTP/24576，委托 launcher
  _restart_stack.py                                  移除“10 秒探活失败即按端口强杀”与双重预热（P07 样本）
  warm_kv.py                                         移除自带预热管线，委托 launcher

原因:
  - P01：四套启动器参数互不一致（-c 65536 vs 32768；MTP off vs on；有无 20480/24576/采样参数），
    在线生效参数无人能确认。现在在线参数与配置的差异可被自动检出并打印。
  - P07：旧探活“10 秒推理探活失败 -> taskkill 按端口”在单槽服务里可能自己排队，误杀健康长任务。
  - 预热被执行两次（warm_kv.py + 代理 --warm），且代理 --warm 与真实请求管线可能不同步。

测试结果（离线 + 在线只读，服务全程未重启）:
  - tests\stage_b_tests.py：20 项全部通过（见 results\stage_b_tests.txt）。
  - 真实在线命令行 vs 配置生成参数：后端/代理均“零差异”（说明配置确实权威、未引入漂移）。
  - 服务运行中重跑 python launcher\bonsai_launcher.py up：
      backend pid 43384 / proxy pid 40108 前后不变；未重启、未中断、未预热（非重启运行不重复预热）。
  - start_all_agent.bat 以 GBK 正确解码（中文标题无乱码）。
  - 8 个入口脚本（注释/文档字符串除外）已无残留硬编码参数与盲杀。

未解决问题:
  - “服务繁忙时重跑启动器不会中断请求”目前只有单元证据（忙时 cmd_stop 返回 4 拒绝停止；
    up 的忙分支不进入重启路径），完整实测需等一次真实长任务的空闲窗口。
  - 预算项（总生成 8192 / 思考 2048 / 余量 1024）在阶段 B 仅登记不注入（budget.policy 两项 = false），
    待阶段 D 行为验证通过后再逐项打开。
  - 代理目前仍只支持瘦身“全开/全关”；逐项开关、恢复 deferred 工具索引与子代理名称在阶段 F。
  - 阶段 B 不动采样参数（保持在线基线 = 服务端默认），采样对照留到阶段 D/G 之后单独做。

回滚入口: 见 rollback.md 的 R2。
## 四、阶段 C：代理流式读取、每请求日志、超时与排队 —— 完成
方案要求（§5 / §C1–C5）：read1 类“有数据即返回”的流式转发；独立增量 SSE 解析器；
连接/首字/无数据/整体四档超时；取消要验证后端释放；明确排队状态；
每请求 request_id 日志（字段见 §C4）；删除 prompt_n<1500 作为缓存命中的绝对判据；
离线模拟 SSE 测试，且不得加载第二个模型进程。

修改的生产文件:
  proxy\bonsai_proxy.py      全量重写为 v3（旧 v2 保存在 backup\proxy__bonsai_proxy.py，
                             SHA256 5DAAB52777768428…，与部署前在线文件字节一致）
  launcher\bonsai_launcher.py  proxy_args 增 "--config D:\Bonsai-demo\config\bonsai-agent.json"
                             （代理也从唯一权威配置读运行期参数；旧 v2 → backup\stageC\bonsai_launcher.py.v2）
  config\bonsai-agent.json   proxy 增 capture_dir；timeouts 增 stream_idle_s=300 /
                             client_write_s=120 / release_wait_s=30；timeouts 说明更新为“阶段 C 已实现”
                             （旧 v2 → backup\stageC\bonsai-agent.json.v2）

新增文件:
  optimization\20260927_165311\tests\stage_c_tests.py    阶段 C 验收测试（36 项，纯本地 mock 上游）
  optimization\20260927_165311\results\stage_c_tests.txt 最近一次运行结果
  optimization\20260927_165311\results\stage_b_tests.txt 阶段 B 回归结果（夹具更新后重跑）

代理 v3 关键实现（对应方案条目）:
  C1 流式  : resp.read1(65536)（有数据即返回），不用攒满式 read()；响应头透传 + Connection: close 划边界
  C1 解析  : 独立 SSEParser —— 增量 UTF-8 解码（多字节字符可跨块）、按 \r\n|\n|\r 切行、
             注释心跳计数、多事件同块、data 多行拼接、[DONE]、reasoning_content/content/
             tool_calls.function.arguments 分别累计
  C2 超时  : connect_s / first_response_s / stream_idle_s / overall_s 四档；另加 client_write_s
             给“写给客户端”设超时，避免对端卡死把 -np 1 单槽一起卡住
  C2 取消  : 每写一块后 client_gone_peek()（select + socket.MSG_PEEK，异常=RST 也算已断开）；
             上游自然 EOF 但未见 [DONE] 时再给 0.3s 宽限窗口补判一次
  C2 释放  : client_disconnected / timeout_kind 命中时调 verify_backend_release() 轮询 /slots，
             结果写 release_verified/release_ms（取不到 /slots 记 null=未知，不谎报）
  C3 排队  : 单槽串行化（INFER_LOCK），server_busy_at_start + queue_ms 落日志；拿不到槽位则 503
  C4 日志  : 每请求 requests.jsonl 一条，含 request_id/config_hash/profile/各段耗时/终止原因/复用分档
  C4 判据  : 删除 prompt_n<1500 绝对判据，改按 cache_n/(cache_n+prompt_n) 分档
             （无复用 / 部分复用 / 高比例复用 / 未知）；timings.jsonl 不再写 hit 字段

原因:
  - P02/P05：旧代理用 resp.read() 会把流攒满再发，WorkBuddy 侧表现为“卡住不动”，且无法分辨
    “上游慢”“上游断了”“客户端跑了”三种情况。
  - 旧 timings.jsonl 只有 prompt_n 与 hit 布尔，无法回答“这次到底复用了多少”。
  - 取消若只按 close 判定就下结论，可能误报后端已释放；必须看 /slots 实证。

测试结果（离线，纯 mock 上游；全程未加载第二个模型进程，未碰在跑的服务）:
  - tests\stage_c_tests.py：36 项全部通过（见 results\stage_c_tests.txt）。覆盖：首块立即转发
    （TTFB<0.35s 且整段>=0.55s，证明是边收边转）、字节不丢不重复、脏 SSE 全要素解析、
    500 原样转发、中途断流被明确记录、并发两个请求上游同时只被一个占用且 queue_ms 可观测、
    客户端真断开被记录并验证 /slots 释放、first_response/no_data/overall 三档超时、
    §C4 字段齐全、reuse_class 五例、verdict 已无绝对判据。
  - 部署后对已落盘的 D:\Bonsai-demo\proxy\bonsai_proxy.py 重跑同一套：仍 36/36 通过。
  - 阶段 B 回归 tests\stage_b_tests.py：20/20 通过（夹具同步更新，见下）。
  - 真机验证（空闲窗口，后端全程未重启）:
      launcher up --no-prewarm：只重启代理（pid 40108 → 43344），后端 pid 43384 不变；
      在线代理命令行已含 --config，status 显示“在线 vs 配置 零差异”、state 指纹一致；
      新代理启动横幅确认 抓包目录/每请求日志/四档超时/瘦身/read1/排队；
      launcher prewarm：req_012_135949.json，prompt_n=4 cache_n=60457 高比例复用，1.7s（缓存本已热）；
      launcher smoke（经代理真实推理）：通过 3.84s finish_reason=stop；
      logs\requests.jsonl 已落记录，config_hash=8a32a6478cfe2b89、profile=medium 与配置一致。

测试夹具修正（透明记录，非放宽标准）:
  - stage_c_tests 的“客户端取消”用例原先只 conn.close()。实测：响应带 Connection: close 时，
    http.client.getresponse() 已把 conn.sock 置空，真正持有 fd 的是 resp.fp，
    因此只 conn.close() 并不会发 FIN —— 也就是说“客户端”其实一直连着，代理判不出取消是必然的。
    改为显式 resp.close() 后真的断开 TCP，取消检测即刻命中（client_disconnected=True、
    release_verified=True）。这是夹具缺陷的修正；代理侧同时补强了 RST/异常判定与宽限窗口。
  - stage_b_tests 的 live_proxy_cl 夹具加入 --config（因为 launcher 现在就是带 --config 启动代理），
    否则“代理 在线 vs 配置 无差异”会因参数漂移误报。

未解决问题:
  - requests.jsonl 目前把所有请求都记一条（含 /health、/v1/models 探活），量大时会偏吵；
    是否只记推理请求留待阶段 F/G 复核。
  - 流式响应给客户端时未回传 Content-Length/Transfer-Encoding（靠 Connection: close 划边界）；
    对 WorkBuddy 已验证可用，其他客户端兼容性未测。
  - “客户端取消”依赖 TCP 层真断开；若客户端只半关（shutdown write）却继续读，会被判成取消。
    当前唯一客户端是 WorkBuddy（标准 HTTP 客户端，不做半关），风险低但记录在案。

回滚入口: 见 rollback.md 的 R3。

## 五、阶段 D：请求级预算能力验证与参数优先级 —— 完成

1) D1 服务/二进制能力探测（只读，不改代码）
   手段：对运行中的 :8081 发 6 个真实流式推理（nat_nobudget / bud32 / bud128 / bud0 /
   bud32_msg / 别名 thinking_budget_tokens=32），固定 prompt（中国剩余定理，正确答案 128）、
   seed=1234、max_tokens=512；每例前查 /slots，忙则等待 120s，绝不抢用户任务。
   证据：results\stage_d_probe.json / stage_d_probe.txt（原始数据）、results\stage_d_verdict.txt
   （修正版判定，只读原始 JSON 重算，不改原始数据）。
     - 请求级正数思考预算已生效：bud32 -> reasoning 31 tok；bud128 -> 128 tok；
       别名 thinking_budget_tokens=32 -> 31 tok（与命名字段效果一致）；
       bud32_msg 的 reasoning_budget_message 原文出现在输出中（证明采样器执行了强制注入）。
     - 源码佐证：server-common.cpp 第 1352-1367 行把 reasoning_budget_tokens（含别名
       thinking_budget_tokens）透传，-1 时回退服务端 opt.reasoning_budget；仅在 end tags 非空时下发。
     - 采样器佐证：reasoning-budget.cpp 第 73-135 行状态机 IDLE->COUNTING->FORCING->WAITING_UTF8->DONE。
   自我更正：首版 verdict() 把“budget=0 必须立即结束思考”当唯一判决项 -> budget_supported=False，
   与 bud32/bud128 精确截断、message 被强制注入的证据矛盾。另写 stage_d_verdict.py 重算判定。
   未解问题（口径结论）：budget=0 实测与“不传该字段”逐字节一致（383 tok，未立即结束），
   与服务端 --help 的 “0 for immediate end” 不符。生产口径：关闭思考一律用
   chat_template_kwargs.enable_thinking=false，不用 budget=0。
   D1 副作用（重要）：小预算伤正确性。budget=128 时答案错误（167），无预算与 budget=0 答案正确（128）；
   budget=32 时思考被硬截断，模型把剩余推理写进 content（content 252 tok）。
   -> 档位只能按“正确完成所需总耗时”选，不能只看 tok/s。

2) D2 参数优先级（无 GPU，用 /apply-template + /tokenize 文本判定；实测 5 条）
     - 模板默认档 = xhigh（不传即注入 xhigh 指令行）；显式 medium 反而不注入任何档位行。
     - 顶层 reasoning_effort 覆盖 chat_template_kwargs.reasoning_effort（源码解析顺序在后）。
     - 顶层 reasoning_effort="none" 关闭思考，且该字段会被 erase，不会丢给模板。
     - chat_template_kwargs.enable_thinking=true 会压过顶层 none（kwargs 显式值优先级最高）。
     - 非法档位（kwargs "none"、顶层 "high"）-> 模板 raise_exception，HTTP 500。
       故代理绝不能把 "none" 当档位传进模板。

3) D2/D3 代理落盘（D:\Bonsai-demo\proxy\bonsai_proxy.py）
   修改前 sha256=7478bf4ef933286ba6430dafb230ca07f8f18ddb08818cc59acce69a99999c46（v3）
   修改后 sha256=42a50d658e68b5293e218169cf8dbbe27abcb972fbdb886aa66a0aad8809b929（61098 字节）
   apply_effort() 整体替换为 client_thinking_intent() + apply_thinking_policy()：
     - 优先级：显式请求参数 > 代理配置档 > 服务默认；客户端已指定一律不覆盖。
     - 识别来源：顶层 reasoning_effort / chat_template_kwargs.reasoning_effort / .enable_thinking；
       另登记请求级预算 reasoning_budget_tokens（别名 thinking_budget_tokens）。
     - 档位归一：off|none|false|no|disabled -> 注入 enable_thinking=false；
       xhigh|medium|low -> 注入 reasoning_effort；其它值不注入并标记 src=invalid（避免模板 500）。
     - 客户端一旦表达思考意图，只抑制“思考类”注入（档位与思考预算）；
       max_tokens 是总生成长度、与思考语义无关，仍按 D3 policy 独立生效。
     - D3 预算注入默认全关：config.budget.policy 两项 false 时不注入；打开后仅在客户端
       未给 max_tokens / 未给思考预算 / 未关思考时注入。
   两处调用点同步改为 apply_thinking_policy：真实请求路径 + KV 预热路径（保证预热前缀与
   实际请求前缀一致，否则预热白做）。
   requests.jsonl 新增字段：effort_source / effort_effective / budget_applied。
   启动横幅改为“未显式指定时注入 reasoning_effort=%s；客户端已指定则不覆盖”。

4) 落盘过程中修掉的四个自身缺陷（透明记录）
   - patch 首版漏了预热路径第二处 apply_effort 调用（原第 1191 行）-> 断言在写文件前中止，
     代理文件未被改动（安全）；补锚点后重跑。
   - 首版横幅锚点只取单行 print，而替换文本自带 if 行 -> 重复 if 导致 IndentationError；
     先回滚到备份 v3、修正锚点后重跑，py_compile 通过。
   - 首版把“客户端已表达思考意图”当成整体跳过注入，连带挡住与思考无关的 max_tokens 预算。
   - applied 初始化位置错误，导致档位注入已改写 body 却被判为“无注入”。

5) 测试与验收
   - tests\stage_d_tests.py（新增 22 项）-> results\stage_d_tests.txt：22 通过 / 0 失败。
     覆盖 D2 优先级与来源识别、档位归一（含 none 与非法档位）、带预算不注入档位、
     D3 policy 默认关闭 / 逐项打开 / 不覆盖客户端值、关闭思考不注入思考预算、
     日志新字段存在、旧 apply_effort 不残留。
   - 回归：stage_c_tests.py 36 通过 / 0 失败（results\stage_c_tests_regression.txt）；
     stage_b_tests.py 20 通过 / 0 失败（results\stage_b_tests_regression.txt）。
   - 在线验证（空闲窗口，只重启代理，后端不动）：
     launcher status 双端身份核对通过（后端 43384 / 代理 43344）；
     按身份停掉代理 pid 43344（命令行已确认是本项目 bonsai_proxy.py），再
     launcher up --no-prewarm -> 代理新 pid=59028，后端 pid=43384 未变；
     经代理真实请求（max_tokens=8）后 requests.jsonl 记录
     effort_source=proxy_profile、effort_effective=medium、budget_applied=null、profile=medium；
     proxy.log 打印 “[effort] 注入 reasoning_effort=medium”；横幅已更新。
     注意：本次是脚本内容变化、命令行参数未变，launcher up 不会自动重启代理，
     必须先停掉旧代理再 up（此点已写入 rollback.md R4）。

6) 同期发现的性能异常（与阶段 A-C 改动无关，记录备查）
   同一后端进程 pid 43384（12:47:56 启动，参数未变、未重启）服务端自报 predicted_tokens_seconds：
   13:04 -> 35.9 tok/s；14:04 -> 18.3 tok/s；16:5x -> 2.36 tok/s（200 tok 用 84.4s），prompt_per_second=11.4。
   现场证据：llama-server WorkingSet 仅 582-610 MB 而 PrivateMemory 约 16.4 GB；
   宿主 32 GB 内存仅余约 6 GB，commit 已用 55.5/105.9 GB，两个 pagefile 在用；
   GPU 7772/8151 MiB、利用率 6%、功耗 18 W（GPU 非瓶颈）。
   结论：宿主内存压力把服务内存页挤出常驻集（mmap 权重反复回读）-> 整体慢约 15 倍。
   这直接决定阶段 G 的前置条件：必须在内存压力解除后重测基线（原基线 17.6-20.2 / 32-40 tok/s），
   否则性能对照无效。

未解决问题:
  - budget=0 语义与服务端 --help 不符（生产口径已定：不用 0 表示关闭思考）。
  - D3 预算注入默认关闭；首轮候选档位表（日常A medium+2048+8192 / 日常B medium+4096+8192 /
    简单抽取 0-1024 / 复杂 8192/16384）尚未在真实任务上对照验证，待阶段 G 在内存压力解除后
    按“正确完成所需总耗时”评测。

回滚入口: 见 rollback.md 的 R4。

## 六、阶段 E：输入空间预算与历史整理 —— 完成

目标（方案 §7）：E1 精确核算输入预算；E2 预算不足时的处理顺序；E3 输入目标 8k–24k。
验收口径：超预算在生成前发现 / 不丢关键事实 / 工具配对完整 / 无静默裁剪。

### E1 精确核算（离线；results\stage_e_probe.json / .txt；脚本 tests\stage_e_probe.py）
  样本：capture\req_012_135949.json（296,318 字节，真实 WorkBuddy 请求）。
  量具：先 POST /apply-template（与 /v1/chat/completions 共用 oaicompat_chat_params_parse，
        故与真实请求同一条转换管线）取 exact prompt，再 POST /tokenize 计数。
        add_special true/false 对本模板无差异（实测）。
  实测结论（n_ctx = 65,536）：
    A0 原样              = 69,113 tok   <- 单输入就已超出 65,536 窗口
    A1 瘦身后            = 60,499 tok
    A2 瘦身 + 思考策略后  = 60,461 tok   （瘦身合计省 8,614 tok / 12.46%，字符省 28,327）
    分段：tools 24,022 + system 14,465 + 历史 21,917 ≈ 60,404
          固定开销 tools + system = 38,487 tok = 63.7%
    预算式：60,461 + 8,192（计划生成）+ 1,024（余量）= 69,677 > 65,536 -> 超 4,141 tok
    占用：输入 = 窗口的 92.3%（E3 目标上限 24k 完全达不到）
    实测比率：chars/token ≈ 4.05（A1/A2）；bytes/token ≈ 4.51。
    核算成本：6×/apply-template + 12×/tokenize = 1,328 ms；单次 A2 精确核算 ≈ 172 ms（78 + 94）。

### E2/E3 结论
  主要矛盾是固定开销（tools 24,022 + system 14,465 = 63.7%），仅压缩对话历史不可能达到 8k–24k。
  要达 E3 必须动 tools / system 本身（延迟工具加载、裁剪 system），但那会触碰 P09 的工具发现能力，
  与阶段 F 一并处理。本轮坚持“无静默裁剪”：超预算时按闸门拒绝或告警，而不是悄悄截断输入。

### 新增实现（改动 D:\Bonsai-demo\proxy\bonsai_proxy.py）
  1) 输入预算闸门 check_input_budget()：双层设计。
     便宜路径：est_upper = int(len(body)/floor)（floor 默认 3.0）。仅当 est_upper + 计划生成 + 余量
       <= 窗口 时才判 skip；即“上界已能证明在预算内”，实测小请求 0 ms。
     否则走 exact_input_tokens()：/apply-template -> /tokenize，精确计数，成本约 172 ms。
     核算失败（/apply-template 或 /tokenize 不可用）一律记 unknown：不据此放行，也不谎报安全。
     action ∈ disabled / skip / pass / over / unknown。
     注：闸门计数的 body 是瘦身/策略转换之后、真正要转发的 body（在线实测 60,461 与 E1 的 A2 一致）。
  2) effective_context_window()：优先问后端 /props，60 s 缓存；失败退回 config.budget.context_window_tokens；
     仍无则 65,536；记录 window_source。
  3) 超预算处理：mode=reject -> 立即返回 HTTP 400（error.code=input_over_budget），
     **不发起推理、不占槽位**；mode=warn -> 记 notes 后仍转发。
  4) 每请求新增字段 budget_check。
  5) config\bonsai-agent.json 新增 budget.context_window_tokens=65536 与 budget.gate
     {enabled:true, mode:"warn", chars_per_token_floor:3.0}。
  哈希：proxy 42a50d65…（D 版）-> a375f4f3…（69,903 字节）；
        config 13f34b22…（D 版）-> 2df7ef56…（切换 gate.mode 后还原为同一哈希）。

### 测试
  离线：tests\stage_e_tests.py 12/12 通过（自带进程内 Mock 上游，不加载第二个模型进程）。
        覆盖：便宜路径 skip 且不触上游 / 大请求精确计数各一次 / 预算算式 / apply-template 失败->unknown /
        /props 不可达->退配置并标注来源 / 预算检查不改写 body / warn 仍转发且 notes 含 warn /
        reject 返回 400 且上游未收到 /v1/chat/completions / gate.enabled=false->disabled /
        new_record 含 budget_check。日志 results\stage_e_tests.txt。
  回归：stage_c 36/36、stage_d 22/22、stage_b 20/20 全通过。
  在线（mode=reject，只重启代理，后端 pid 43384 始终不变）：
    POST 真实抓包 296,318 字节 -> HTTP 400，用时 187 ms；
    error.code=input_over_budget；budget.input_tokens=60,461、required=69,677、headroom=-4,141、
    verdict="超预算"、method="exact(apply-template+tokenize)"、est_upper_tokens=88,965；
    requests.jsonl：status=400 / error_type=input_over_budget / sse_events=0 / wall_ms=187
    -> **证明“超预算在生成前发现”，且未发起推理**。
  在线（mode=reject，验证不误伤）：小请求 -> HTTP 200，budget_check.method=chars_upper_bound、
    verdict="在预算内(便宜路径)"、elapsed_ms=0.0。
  在线（恢复 mode=warn）：小请求 -> HTTP 200，budget_check.mode=warn、便宜路径、elapsed_ms=0.0。
  在线预填充探针（附带发现）：6,810 token 冷 prefill 用时 106.4 s -> prompt_per_second = 64.03 tok/s。

### 未解决问题
  - warn 模式“超预算仍转发”的在线复现被明确放弃：真实抓包 60,461 token 冷 prefill 按实测 64 tok/s
    推算需 ≈945 s，远超 first_response_s=180 s，必然首字节超时。该语义由离线测试覆盖，
    不谎报为在线已验。此现象同时说明当前内存压力下长任务不可用，与阶段 G 前置条件一致。
  - prefill 仅 64.03 tok/s，是内存压力的又一次量化证据（详见第四节“性能异常备查”）。
  - E3 的 8k–24k 输入目标未达成，且仅靠历史整理不可能达成（固定开销占 63.7%），需阶段 F 处理 tools/system。
  - floor=3.0 的安全性边界：est_upper = 字节/3.0 只有在内容平均 >= 3 字节/token 时才是“上界”。
    实测真实流量约 4.51 字节/token，故 1.5 倍保守、不会误跳过；但极端字节密集内容（约 < 3 字节/token，
    如 base64 / 压缩串 / 乱码）会低估 token 数，理论上可能把超预算误判为“在预算内”。
    缓解：把 budget.gate.chars_per_token_floor 设为 1.0 即每次强制精确计数（代价 172 ms/请求）。
    当前默认 mode=warn，该风险的后果仅为少一条提示，不影响正确性。

回滚入口: 见 rollback.md 的 R5。

## 七、阶段 F：工具错误修复与发现能力保护 —— 完成
方案要求（§8）：F1 修 show_widget.loading_messages（从字符串改为数组语义校验：可解析为数组、
长度 1–4、元素为字符串；失败时给出精确字段名与最小正确例子）；F2 修 strip_locations 的逐项
开关并恢复 deferred 工具清单与子代理类型清单（P09）；F3 修 launcher 里已过期的横幅文案；
F4 通用错误恢复（同一错误连续两次不再原样重试；有副作用的操作不重复执行）。

修改的生产文件:
  proxy\bonsai_proxy.py        a375f4f36458cb27… -> 6acfb9c5914595ec…（69,903 -> 83,934 字节）
  config\bonsai-agent.json     2df7ef565a53e559… -> d678a79a12834965…（4,548 -> 6,276 字节）
  launcher\bonsai_launcher.py  6163d84f22b45fc3… -> d06a8ed485301bc3…（32,108 -> 32,613 字节）
  tests\stage_e_probe.py       f797f6b3f77e323d… -> b0c0a719adf1a988…（E 探针调用点适配）

新增文件:
  optimization\20260927_165311\tests\stage_f_tests.py     阶段 F 离线验收（61 项）
  optimization\20260927_165311\tests\stage_f_online.py    在线探针（--restart 才重启代理）
  optimization\20260927_165311\results\stage_f_tests.txt  61/61
  optimization\20260927_165311\results\stage_f_online.txt 在线验证两轮（首轮含坏夹具，见下）
  optimization\20260927_165311\results\stage_{b,c,d,e}_tests_afterF.txt  回归结果
  optimization\20260927_165311\backup\stageF\*            4 份前置备份（复制后 SHA256 与原件一致）

### F1 工具体契约加固（P05）—— 先查清“谁在校验”，再改能改的那一层
先说结论性事实（都已核实，不推测）：
  - show_widget 是【客户端（WorkBuddy）提供并执行】的工具：全盘检索 D:\Bonsai-demo 与客户端
    插件目录，show_widget / loading_messages 只出现在 capture\req_*.json（客户端发来的 schema
    与工具返回）里，本地没有任何实现代码 —— 也就是说代理**改不了校验器本身**。
  - 失败原文来自该客户端校验器：真实抓包 capture\req_012_135949.json 里
    "loading_messages must contain at least one message." 【连续出现 2 次】：第一次失败后
    模型原样重试同一调用，又失败一次，那一轮 6,328 生成 tok 全废（P05）。
  - 客户端 schema 里该字段是 type=string，描述为 “A JSON-encoded string array of 1–4 loading
    messages … Example: '["Preparing chart data",…]'”。客户端校验语义 = 把该字符串解析成数组，
    要求可解析、长度 1–4、元素为非空字符串；原描述既没说“省略/空串/空数组/裸数组都会被拒”，
    也没说失败后怎么修 —— 这是“参数错误未被有效纠正”的根因。
代理侧改动（三件，全部确定性、可离线验证）：
  1) harden_tool_schemas()：把该字段描述替换为精确契约 —— 精确字段名（field name exactly
     "loading_messages"）、类型语义（JSON-ENCODED STRING -> 数组，1 to 4 个非空短字符串）、
     最小正确示例 "loading_messages": "[\"Rendering visualization\"]"、失败原文与自纠指令
     （按上面示例修这个字段后重发；do NOT repeat the same call unchanged）。
     只改 description；type 仍是 string（不动客户端 schema 语义）；required 仍含该字段；
     其他工具与其他字段逐字节不变（测试逐字段对比）。
  2) validate_loading_messages()：按客户端语义判定（可解析为数组 / 长度 1–4 / 元素为非空字符串；
     裸数组也接受并标注 bare_array），失败给出精确原因（空字符串 / 不是合法 JSON / 不是数组 /
     数组为空 / 超长 / 第 i 项不是非空字符串 / 字段缺失）。
  3) inspect_tool_arg_history() + tool_arg_audit()：观测量。扫请求历史里的 show_widget 调用与
     工具失败，统计 calls/valid/invalid/problems/tool_failures 与 repeated_identical_error，
     写入 requests.jsonl（无调用且无失败时不写字段，避免日志膨胀）。
     这条是为“改好了没有”留证据：后续抓包里 invalid 与 repeated_identical_error 应下降。
真实抓包实测（results\stage_f_tests.txt 里的审计用例）：calls>0、tool_failures>0、
repeated_identical_error 指向 loading_messages —— P05 的现场特征被稳定识别。

### F2 瘦身改为逐项开关 + 恢复 deferred / subagent 名册（P09）
  - strip_locations() 重写为 slim_tools(raw, flags)（旧名已不存在，改动后有断言），三项
    （locations / deferred_tools / subagents）各自独立；新增 keep_location() = “--keep-location
    或三项全 false”，A/B 对照开关仍然有效；E 探针脚本的调用点同步适配为新返回三元组。
  - config.slimming 改为 locations=true / deferred_tools=false / subagents=false：即保留
    (location: …) 剥离（纯磁盘路径噪音、零代价），**恢复完整 deferred 工具名册与子代理类型
    名册**（不再压缩，避免模型“不知道该 ToolSearch 什么 / 该用哪个 subagent_type”）。
  - 代价已在真实抓包上量化（296,318 字节的 req_012_135949.json，chars/token≈4.05）：
      只剥 location     : 省 14,689 字符 ≈ 3,627 tok
      三项全开（旧行为）: 省 28,327 字符 ≈ 6,994 tok
      => 恢复 ②③ 名册     : 每请求多带 13,638 字符 ≈ 3,367 tok
      契约加固            : +394 字符 ≈ +97 tok
      策略块              : +584 字符 ≈ +144 tok
  - 明确取舍：这次是拿 ~3.5k tok 输入换“工具发现能力”。方向与阶段 E 的输入压缩目标相反，
    属于刻意选择（正确性优先），并把代价写进这里备查。输入预算闸门（阶段 E）对“逐项”结果
    仍按实际 outbound 体计数，不因此失真。

### F3 启动器文案纠正
  - 横幅：删掉过期的“阶段 D 验证前只登记”，改为“阶段 D 已验证请求级预算可用，policy=false =
    只登记不注入”；新增“工具体”一行（契约加固 / 错误恢复策略块）；瘦身行改为按配置逐项打印。
  - 删掉“[代理] !! 配置里瘦身是‘部分开’，但当前代理只支持全开/全关”这条已不成立的提示，
    改为启动时逐项打印 ① location / ② deferred 清单 / ③ subagent 清单。

### F4 工具错误恢复策略块
  - apply_tool_error_policy()：对带非空 tools 的请求，在【第一条 system 文本尾部】并入一个常量
    策略块（584 字符）：① 同一工具连续两次返回同一错误时，绝不原样重发同一调用 —— 按错误指出
    的字段修正，或换工具/换路径；② 有副作用的操作（写文件、发消息、提交表单、改状态命令）
    绝不盲目重复，先复查当前状态；③ 工具参数必须严格符合 schema，声明为 string 的字段即使内容
    看起来像 JSON 也保持 string。
  - 为什么这样实现（而不是在消息末尾插一条新消息）：重试决策方是客户端，代理无法强制；末尾插
    新 role 会伪造对话且中段 system 可能触发模板兼容问题；而 system 文本是【确定性】改写，
    预热与实际请求走同一管线 -> 前缀天然对齐，不破坏 KV 复用（与阶段 D 的档位注入同一类改动）。
  - 只在带非空 tools 时生效；system content 为多模态数组时跳过（不猜、不报错）；幂等（重复调用
    不会叠加第二个策略块）；config.tools.error_policy=false 可整体关闭。

### 测试与在线验证
  - 离线：tests\stage_f_tests.py **61/61 通过**（逐项瘦身 13 项、契约加固 13 项、validator 2 项、
    历史审计 8 项、策略块 8 项、整条管线 3 项、配置与启动器 14 项）。
  - 回归（夹具未放宽）：B 20/20、C 36/36、D 22/22、E 12/12（results\stage_*_tests_afterF.txt）。
  - 在线（results\stage_f_online.txt，两轮）：
      第一轮：按身份停掉 8080 上的 bonsai_proxy.py（pid 52236）-> launcher up --no-prewarm ->
        新代理 pid 56108；后端 llama-server pid 43384 **全程未变**；新横幅与配置指纹一致
        （0b0d2806eb9a9d1a）。构造请求返回 HTTP 500 —— 原因是我夹具里放在历史上的 tool_call
        参数本身就是坏 JSON，被上游拒绝；**已如实记录，未篡改**（该轮审计还把
        “arguments 不是合法 JSON”报了出来，说明审计有效）。
      第二轮（修好夹具、不重启代理复跑）：同一构造请求 HTTP 200（0.06s 拒绝路径不再出现），
        requests.jsonl 记录里 slim.flags={locations:true, deferred_tools:false, subagents:false}、
        slim.saved_chars.locations=86（夹具体量小）、tools_hardened=["show_widget.loading_messages"]、
        tool_policy="并入首条 system 尾部 584 字符"、tool_arg_audit={calls:2,invalid:2,
        tool_failures:2,repeated_identical_error:["loading_messages must contain at least one message."]}
        -> 四项判定全 True；不带 tools 的普通请求 HTTP 200 且四个新字段均为空（未误伤）。

未解决问题（不得含糊）:
  - F1 的**端到端效果无法由本次改动证明**：校验器与重试决策都在客户端，代理只能加固“模型看到
    的契约”+常驻策略+留下观测量。没有一次真实 WorkBuddy 会话窗口，就无法证明“模型第二次不再
    原样重试”。验证路径已给：看后续抓包的 tool_arg_audit.invalid / repeated_identical_error
    是否下降/为空。
  - 恢复 deferred/subagent 名册使每请求输入 +≈3.4k tok，阶段 E 的 8k–24k 输入目标更难达成，
    日常请求会继续触发 warn（若切 reject 则可能被拒）。这是本次刻意取舍，未做 A/B 体感对照。
  - 策略块 +584 字符/请求的效果（是否真的减少重复重试）没有对照实验，会上线观察。
  - 阶段 G 的性能对照仍被宿主内存压力阻塞（冷 prefill 实测 64.03 tok/s，基线 17.6–20.2 /
    32–40 tok/s），必须等内存压力解除后重测。

回滚入口: 见 rollback.md 的 R6。
## 八、阶段 G：通用任务验收与性能对照 —— 进行中

### G0 前置：宿主内存压力的证据与判定（重要，先于任何压测）

| 指标 | 实测值 | 含义 |
|---|---|---|
| llama-server pid 43384 | WS **2,692 MB** / Private(Paged) **16,019 MB** / Virtual 100,357 MB | ≈13.3 GB 私有内存在磁盘上，常驻仅 2.7 GB |
| 宿主 | 总 32,189 MB / 空闲 **4,076 MB**；页面文件 73,728 MB | 常驻集容纳不下 llama-server 的 16 GB 提交 |
| GPU | 7,772 / 8,151 MiB，util **6%**，SM 2010/3090 MHz，**22.7 W** | GPU 全程等数据，不是瓶颈 |
| 模型 | GGUF 5.87 GB，`-ngl 99` 全上卡 | 权重不在宿主侧重复读 |
| 磁盘 | YMTC NVMe SSD | 换页有真实代价（冷 prefill 实测 64.03 tok/s） |

宿主侧账目：`-c 65536` 的 q4_0 KV（按日志 blk.0–63 的 attn_k/v 张量尺寸推 n_kv_heads=8、
head_dim=128）≈**4.8 GB** + compute buffer + 5.87 GB mmap 影子 ≈ 12–16 GB，与 Private 16 GB 吻合。

**判定：§0 的全部禁项（GPU 锁频 / 驱动 / BIOS / VBS-内存完整性 / 电源管理 / 系统代理）与本阻塞无关。**
GPU 利用率仅 6%、功耗 22.7 W，说明模型在等宿主的页，不是在等功耗或驱动能力；
VBS 关闭只能腾出 <1 GB 且削弱系统安全，方案 §1.1-6 亦明确"本次不通过关闭系统安全功能处理性能问题"。
§0 自留的出口（"若测试证明必须做这些范围外操作，先交付证据和具体改动清单，再由用户决定"）
已按流程向用户交付证据；用户回复"全部放开进行操作"，但依据上述证据，**本轮不需要也不动用任何 §0 禁项**，
§0 保持原状。解决方向只能是 §0 允许的宿主侧参数/环境（见未解决问题）。

### G1 固定夹具（方案 §14.1）

新增（只读原件，唯一版本；各配置用独立副本）：
```text
D:\Bonsai-demo\bench\fixtures\
  sales.csv(111B) notes.txt(131B) source.txt(18B) calc.py(71B)
  checkpoint.md(163B) logs\run.log(12914B, 1000 行, 第137/811 行为 ERROR)
  MANIFEST.json   原件 SHA256 清单 + 第11项预置 sales.json 的规范哈希 ce3f1fca8433dd83
D:\Bonsai-demo\bench\runs\A|B\   上述夹具的独立工作副本（含空 results\）
```

### G2 验收脚本（方案 §14.1 要求"先建立验收脚本"）

新增 `bench\check_tasks.py`：12 项任务的**客观**判定（不看被测 Agent 自述）——
JSON 合法性与取值、CSV 行数与去重、函数实际执行结果、XML 合法性、动画元素计数、
外链检测、错误行号精确匹配、预置产物哈希是否被重写等。

负向自检（用未完成任务的副本跑 all）：**5 通过 / 13 失败**，符合预期；
其中夹具自带的缺陷函数被正确判失败：`total_paid` 返回 **680.0**（未按 paid 过滤、未按 order_id 去重），
应判 350 —— 证明验收脚本能真正区分"做完"与"没做"。

### G3 本地执行 harness（诚实定位）

新增 `bench\bench_harness.py`（单任务，含 4 个工具：list_dir/read_file/write_file/run_python，
路径越界拒绝）、`bench\bench_multiturn.py`（第 10 项五轮 + 固定切片）、`bench\run_all.py`（批量 + 自动验收）。

**能力边界（不谎报）**：这是**本地脚本 harness，不是方案 §14.3 的 WorkBuddy(A/B) 或 Pi(C)**。
它只把 §14.2 的任务原文交给同一个本地模型（经 :8080 代理、**单一后端进程**，不并行压测），
用于回答"修复后的代理+后端能否真实完成这 12 项"并采集 §G3 字段；
**不得当作 A/B/C 对照结论**。

### G4 已完成任务与实测（配置 B = 修复后代理/预算）

| 任务 | 结果 | 墙钟 | 轮数 | 停止原因 | 工具重复 | 备注 |
|---|---|---:|---:|---|---:|---|
| 2 去重已支付统计 | **4/4 通过** | 342.2s | 4 | model_finished | 0 | TTFT 54.2→5.6/9.3/7.2s，前缀复用生效；产物 `{"count": 3, "amount": 350}` |
| 1 notes 五条约束 | 待汇总 | 86.2s | 4 | model_finished | 0 | 产物已生成 |

其余任务（3,4,5,6,7,8,9,12）与第 11 项原计划后台串行执行，**20:16:55 因整机崩溃而中断**
（见 G5），结果文件 `D:\Bonsai-demo\bench\results.jsonl` 目前只有任务 1 一条记录。

### 未解决 / 未完成

- **压缩边界五轮**（§14.2 第10项后半）：本地 harness 没有历史压缩器，标记为
  "未实现（受 harness 能力限制）"，不谎报已验。
- **A 配置对照**（修复前代理 v2，备份在 `backup\proxy__bonsai_proxy.py`）尚未执行。
- **Pi（§13，§14.3 的 C）** 未接入。
- **性能对照受宿主内存换页影响**：本轮所有耗时/token 数字均为**降级态**，不能当作
  方案 §G2 意义上的受控基线；`-c 65536` 的 KV 4.8 GB 与 5.87 GB mmap 影子在 32 GB 宿主上无法常驻。
- 首轮批量驱动因本文档解析 `== 结果:` 行的 bug 以 exit 1 退出（任务 1 本身已完成）；
  已改为正则解析并重启，未影响任何产物。

### 回滚入口

阶段 G 不修改任何生产文件（仅新增 `bench\` 目录与 `config` 无关的测试资产），**无需回滚**；
阶段 F 的 R6 仍然有效。
### G5 运行中断：整机 HYPERVISOR_ERROR 崩溃（本日第 2 次，签名一致）

中断不是服务重启，也不是任何脚本所为：**宿主整机崩溃后自动重启**。

| 证据 | 值 | 来源 |
|---|---|---|
| 意外关闭时刻 | **20:16:55**，20:17:42 重新启动 | Event 6008（"关闭是意外的"）、`LastBootUpTime` |
| 电源事件 | 20:17:47 Event 41 "系统已在未先正常关机的情况下重新启动" | Kernel-Power |
| 蓝屏码 | **`0x00020001` = HYPERVISOR_ERROR**，参数 `0x28, 0x1, 0x29b92701, 0xfc800000` | WER Event 1001 |
| 转储 | `C:\Windows\Minidump\092726-17375-01.dmp`（12.5 MB，20:17:55） | 目录列表 |
| 同码前例 | **2026-09-27 04:52:34，同一码、同样四个参数**，`092726-18406-01.dmp` | WER Event 1001 |
| 对照报告 | `蓝屏事故报告-2026-09-27.md`（04:52 那次，当时转储目录"仅此 1 次"） | 项目文件 |

对照结论：
- 两次崩溃的**错误码与四个参数逐位相同**，属同一故障类（虚拟化层致命错误），不是随机事件。
- 04:52 那次报告把加重因素归为"锁满频 + 满载 + VBS 同时存在"，并点名未经实测的 `-ub 2048` 压测配置；
  本次在线配置是 **`-ub 512`**（见 §G0 与代理横幅），因此该特定诱因不在场，故障可以复现。
- 崩溃时本 Agent 的负载状态（如实记录，不作因果断言）：G4 的任务 1 于 20:14:44 完成，
  任务 3 正在推理，GPU 利用率约 6%、功耗 22.7 W、SM 2010/3090 MHz，宿主空闲内存约 4 GB
  且 llama-server 有 ≈13.3 GB 私有内存在磁盘。**按方案 §1.1-6 的标准，仅凭时间关联不足以定因**，
  既不宣称是本 Agent 负载所致，也不宣称与本 Agent 无关。

后果：llama-server、代理、批量驱动全部随崩溃终止；崩溃后 **8080/8081 无监听，服务不可用**。
本 Agent **未**在崩溃后自动重启任何服务——因为 §0 禁止在无授权情况下动 VBS/内存完整性/电源/锁频，
且方案明确"不通过关闭系统安全功能处理模型性能问题"；把"第 2 次同类蓝屏"当成独立取证项还是
继续压测，属需用户决定的范畴。

### G6 本轮未做（保持原状，不谎报）

- 未动 §0 任何禁项：GPU 锁频 / 驱动 / BIOS / **VBS-内存完整性** / 电源管理 / 系统代理，全部保持原状。
- 未在崩溃后重启服务；12 项任务未跑完；A 配置对照、Pi（C）、压缩边界五轮均未执行。
### G7 蓝屏只读取证（授权后补证）

G5 的证据来自事件日志；本节补上**独立于事件日志的第一手证据**——直接解析转储文件字节。
转储与 WER 归档对普通权限均拒绝访问，经授权以管理员方式**只读复制副本**到 `baseline\`，
原文件未改动；解析脚本只读，未越出 §0 任何禁项。

- 直读结果（两个转储一致）：`PAGEDU64` / 内核 15.26100 / nproc=24 / machine 0x8664 /
  **BugCheckCode `0x00020001`** / 参数 `0x28, 0x1, 0x29B92701, 0xFC800000`
  → 与 WER 1001 正文、Kernel-Power 41 的 `BugcheckCode`/`P1..P4` **三来源逐位一致**。
- 只读副本哈希：`adca00e1…5cd0`（20:17:55，12,525,826 B）/ `5a1fa7ab…7ebe`（04:52:30，12,380,886 B）。
- **已排除（有证据的否定）**：近 3 天无 WHEA 事件（非 CPU/内存机器检查异常）；Display 提供程序
  近 3 天仅 1 条 `4107`（信息级，正文为 SetDisplayConfig 标志，与崩溃无关），**无 4101 = 无显卡 TDR**；
  无 0x116/0x117；无 1074/1076/109（非计划重启）；未发现超频工具进程；
  崩溃前约 95 秒 System 日志**无任何记录**（不是"先报错再崩"）。
- **背景事实（只记录，不作因果结论）**：VBS/HVCI 处于启用状态（Kernel-Boot 153、IsolatedUserMode）、
  hypervisor 正常启动、HAL 已初始化 IOMMU 错误报告、本机装有 3 个 WSL2 发行版
  （`Ubuntu-24.04`/`Ubuntu`/`docker-desktop`，VERSION 2，当前均 Stopped）、
  VmSwitch 日志共 51,179 条（崩溃前最后一次活动 18:31:33，距崩溃约 1h45m）。
  重启后伴随 `Kernel-PnP 219` 警告 ×4 与 `BitLocker-Driver 24641` 错误 ×2（9/25 正常重启时同类出现）。
- 本轮**不给出根因结论**（§1.1-6）；进一步归因需 WinDbg + 符号对转储跑 `!analyze -v`，
  属系统变更，**未做**。
- 产物：`蓝屏取证报告-20260927-2016.md`（8,354 B，sha256 `1dcfc503…f60bd`）、
  `results\bsod_forensics_raw.txt`（3,287 B）、`baseline\*.dmp` 两个只读副本。
- 回滚入口：本补证未修改任何生产文件，**无需回滚**。
### G8 关键新证据：WER 官方分桶指向 Intel IOMMU 超时

从管理员只读取回的 WER 归档 `Report.wer`（`Kernel_20001`，`ReportIdentifier`
`075ba32d-…`，`IntegratorReportIdentifier` `2af1381f-…` 与 G5 的 1001 报告 ID 一致）中，
发现了**微软侧的归因字段**：

```text
Response.BucketId = INTEL_IOMMU_TIMEOUT_IMAGE_GenuineIntel.sys
Sig[0..4]         = 20001 / 28 / 1 / 29b92701 / fc800000
OsInfo            = 10.0.26200.9457
```

- 意义：微软自己的崩溃分桶把这次 `HYPERVISOR_ERROR` 归到 **Intel IOMMU 超时**，
  镜像为 `GenuineIntel.sys`（Intel 处理器 / IOMMU 驱动）。这是**官方归因字段**，
  证据强度高于本 agent 的推断；但**仍不是完整根因证明**（分桶是启发式分类，不含调用栈级证据）。
- 对"该卸哪些组件"的直接影响：该分桶指向 **IOMMU / DMA 重映射路径（Intel CPU 驱动 + 固件层）**，
  而不是显卡驱动本体。GPU 的 DMA 同样要经过 IOMMU，所以更换显卡驱动**不是无关操作**；
  但仅换显卡驱动可能盖不住——按此分桶，**Intel 侧驱动与 BIOS/固件**值得一并纳入对照。
- 本 agent 不据此宣布根因（§1.1-6），只把官方分桶如实记录，供陛下与另一 agent 决策。

### G9 变更前证据保全（只读）与性能基线作废声明

陛下已安排另一 agent 卸载 Windows 11 26200 预览版、并回退/更换 NVIDIA 驱动。
该操作属 §0 范围外，**本 agent 未参与、不执行**，只做三件事：抢存证据、声明基线作废、备好变更后对照。

已固化到 `baseline\prechange_20260927_2036\`（管理员只读导出 + 16 项文本 + 索引）：

| 内容 | 说明 |
|---|---|
| `System.evtx` / `Application.evtx` | 各约 21 MB，原始事件日志，可离线复现任何查询 |
| `wer_reportarchive\Kernel_20001_…\Report.wer` | 含 G8 那条 `BucketId` |
| `17_drivers_enum.txt` | 89 KB，变更前驱动包清单（供驱动更换后逐条对照） |
| `18_bcdedit_current.txt` | 引导项（含 hypervisorlaunchtype，供 VBS 相关对照） |
| `01`–`16` | OS `10.0.26200.9457`、NVIDIA `591.86`（包 `32.0.15.9186`）、BIOS `R2CN57WW`、VBS 状态（`VBS=2` / `Services{2,5}` / `Running{2,5}`）、WSL 发行版、电源方案、崩溃窗口事件全量、Minidump 列表、WER 归档列表、崩溃时进程与端口 |
| 转储只读副本 | 仍在上层目录：`092726-17375-01.dmp`（`adca00e1…`）、`092726-18406-01.dmp`（`5a1fa7ab…`） |

**基线作废声明**：阶段 A 快照与阶段 G 已取得的任何性能数字（含任务 1 的 82.9 s 与各 decode tps）
都是在 **OS 26200 + NVIDIA 591.86** 下测得的。OS 回退或驱动更换后，**这些数字不得再作为对照基线**；
必须按 §A2 重新采集运行事实、按 §G2 重测。变更前后的差值只能记为"**环境变更效应**"，
**不得**记作本次优化的收益。

回滚入口：G8 / G9 均为只读采集与文档追加，不修改任何生产文件，**无需回滚**。
### G10 前提更正与新增独立复核

先前的 G9 建立在一个**已不成立的前提**上；按"不把错误事实写进记录"的要求更正如下。

1. **OS 回退已从计划撤下，G9 的前提不成立。**
   - 本机实为 **Windows 11 25H2 正式版，Build 26200.9457**（分支 `ge_release`，未注册 Insider），
     **不是预览版**；25H2 与 24H2 共用 26100 内核基础，不存在"换掉未修复预览版内核"这回事。
   - 系统中**无 `Windows.old`、无回退窗口**，"返回上一版本"通道已关闭；真要降到 24H2
     只能全新安装。故该项撤下，**本 agent 未执行、也未推动**。
2. **基线作废声明的理由收窄为"显卡驱动更换"一项。**
   - 阶段 A 快照与阶段 G 性能数字（任务 1 的 82.9 s、各 decode tps）是在
     **OS 26200.9457 + NVIDIA 591.86** 下测得的。仅驱动从 `591.86` 换到 Studio
     `616.92 WHQL`（跨约 8 个月），就足以让这些数字**失去对照资格**；须按 §A2 重采运行事实、
     按 §G2 重测。声明仍然有效，但原因只剩驱动这一项。
3. **独立复核"Lenovo Dispatcher 3 天崩 591 次"：属实。**
   - 本 agent 读近 3 天 Application 日志（Id 1000/1002/1026 等）共 **666 条**崩溃类事件，
     其中 **591 条的故障模块为 `LNVDispatcherService.exe`**，另有 72 条为空模块名的挂起类。
     与另一 agent 的说法一致。这是**独立来源的一致性核对**，**不是**对根因的判断。
4. **证据保留方式**：`baseline\prechange_20260927_2036\00_CORRECTION.md` 已在原快照目录标注更正，
   **未改写任何原始采集文件**（保留"当时认为什么"的记录，便于事后审计）。
5. 回滚入口：本节为文档更正，未修改任何生产文件，**无需回滚**。
### G11 变更后只读验证（BIOS R2CN59WW + 驱动 616.92 落地后）

采集时间：2026-09-27 21:23–21:35（开机 21:18:30 之后）。**全程只读**：未改任何生产文件、
未改 §0 禁项、未启停任何服务（服务保持停止）。

1. 前后对照（与 `baseline\prechange_20260927_2036\` 逐项核对）
| 项目 | 变更前（20:37 快照） | 变更后（21:23+） | 结论 |
|---|---|---|---|
| BIOS | R2CN57WW / 2026-02-24 | **R2CN59WW / 2026-04-22** | 已更新 |
| NVIDIA 驱动 | 591.86（Win32 32.0.15.9186 / 2026-01-20） | **616.92**（Win32 32.0.16.1692 / 2026-09-04） | 已更换 |
| NVIDIA VBIOS | （未记录） | 98.06.2a.40.76；8151 MiB，占用 0 MiB | 记录 |
| Intel 核显 | 32.0.101.8332 | 32.0.101.8332 | 未变 |
| VBS / 内存完整性 | Status=2、Services={2,5}、CI=2、DeviceGuard 开启 | 四项逐位一致 | **未触碰** |
| Secure Boot | 1（注册表 UEFISecureBootEnabled） | 1 | **未触碰** |
| 虚拟化功能 | VMP=1 / HypervisorPlatform=2 / WSL=2 | 完全一致 | 未变 |
| OS | 25H2 / 26200 / UBR 9457 / CoreCountrySpecific | 完全一致 | **未回退**（与 G10 一致） |

   注：`Confirm-SecureBootUEFI` 非提权被拒（"无法设置正确的权限"），故 Secure Boot 以
   注册表 `HKLM\SYSTEM\CurrentControlSet\Control\SecureBoot\State\UEFISecureBootEnabled=1` 为准。

2. 无新增蓝屏（三项独立核对）
   - WER `Microsoft-Windows-WER-SystemErrorReporting` Id 1001 全量仅 **2 条**：
     **04:52:34** 与 **20:17:59**（参数均 0x00020001 / 0x28,0x1,0x29b92701,0xfc800000）；
     21:18:30 开机后**无新条目**。
   - `C:\Windows\Minidump` 仅 2 个文件：`092726-18406-01.dmp`（04:52:30）、
     `092726-17375-01.dmp`（20:17:55），**无新增转储**；无 `C:\Windows\MEMORY.DMP`。
   - System 日志 Id 41/6008 仅上述两次崩溃；此后只有**正常关机**类事件：
     21:09:39 `1074`（StartMenuExperienceHost 请求重启）+ 21:09:52 `109`；
     21:12:24 `1074`（`C:\Windows\Temp\7zS7A5B.tmp\H2OFFT-W.exe`，即 BIOS 刷写程序）
     + 21:12:31 `109`。→ 21:09 / 21:12 两次**受控重启**，随后固件刷写，21:18:30 开机。
     与"刷写成功"自洽，**非崩溃**。

3. 两次崩溃时的运行上下文（回答"当时在做什么"）
   - **不是从睡眠/待机唤醒**。本机只用新型待机（Modern Standby）：3 天内**无 42/107**
     （传统睡眠/唤醒）记录；506/507 实测正文为"系统正在进入/退出新型待机状态"
     （原因：Idle Timeout / 输入键盘 / 输入鼠标）。
     - 04:49:40 前最后一次待机转换 = **09-26 11:11:21（退出）** → 崩溃前已连续开机约 17.5 h。
     - 20:16:55 前最后一次 = **15:43:07（退出；原因 输入键盘）** → 崩溃前已连续开机约 4.5 h。
   - **WSL / Hyper-V 在崩溃瞬间无活动**。`Microsoft-Windows-Hyper-V-VmSwitch` 在
     09-27 00:00–04:52 区间**零事件**；20:16 前最后一次为 **18:31:33**
     （233/234 = 端口创建/删除，即 WSL 虚拟机启停）。当日 WSL 活动仅 14:33 与
     18:27–18:31 两段，崩溃瞬间是静的。
   - **VPN：崩溃时无已连接的 VPN（按可得日志）**。
     - `RasClient` 当日唯一一次 VPN 会话为 hide.me **SSTP**：14:05:23 拨号 → 14:05:29 连通
       （隧道 IP 10.60.14.57）→ **15:44:31 终止（原因码 631）**；此后无任何拨号事件。
       另有 IKEv2 配置 `Hide.ME IKEV2` 于 14:04:52 建立链路（同一时段）。
     - `hide.me VPN Service` 的 Id 0 事件正文均为 `PowerEvent handled successfully by the
       service.` / `Service started successfully.`，是**电源通知响应**，**不等于已连接**，
       不得当作"VPN 开着"的证据（04:02:47、04:10:08/09、19:49:30/32 皆属此类）。
     - Proton VPN 5.1.7 已安装，但本地目录最后写入为 **09-02**、近 2 天无日志 → 判定近期未使用。
     - 隧道类内核驱动在位：`tap0901.sys` / `wireguard.sys` / `ovpn-dco.sys` / `wintun.sys`
       （后三者 2026-02-16，wintun 2026-08-14）；近 2 天**无** tunnel 设备安装/移除事件。
   - **04:49:40 崩溃与 Lenovo 崩溃风暴在时间上重合**：近 24 h `LNVDispatcherService.exe`
     （服务名 `LenovoProcessManagement`，版本 3.2.0.17）报错 **592 条**，按小时分布
     **02 时 4 / 03 时 324 / 04 时 264**；最后 6 条为 04:48:56、04:49:07、04:49:19、04:49:31、
     04:49:42、**04:49:54**（约每 12 s 一次），而 BSOD 发生在 **04:49:40**，正落在这串里。
     **仅时间重合，不构成因果**（§1.1-6）；但这是目前唯一与 04:49 崩溃同窗的活动。
   - **20:16:55 崩溃时**：阶段 G 批量跑（cfg=B，任务 [1,3,4,5,6,7,8,9,12]）正在进行——
     任务 1 于 20:14:44 完成（墙钟 82.9 s、4 轮、工具重试 0），随后进入下一任务时整机崩溃。
     该批次运行输出仅存 2 行，**其余任务未产出任何记录**（`results.jsonl` 仅任务 1 一条）。

4. 两个小尾巴的现状（只读）
   - `i4ToolsService`：`State=Stopped`、`StartMode=Auto`、路径
     `D:\下载的\i4Tools9\i4ToolsService.exe` —— "自动启动但起不来"的死状态**仍在**。
     禁用属系统变更、不在本方案范围（§0），**本 agent 未处理**，待明确指派。
   - `LenovoProcessManagement`（`LNVDispatcherService.exe`）：`State=Running`；
     **自 04:49:54 起至今约 16.5 h 无新崩溃记录** —— "最近安静了"**成立且已独立核对**。
     该循环本 agent 未处理、也未推动处理。

5. 证据卫生与回滚
   - 本节全部为只读采集，未修改任何生产文件，未触碰 §0 禁项，未启停服务。
   - 回滚入口：**无需回滚**（零改动）。
   - 顺带更正 G5/G9 的一处口径：20:14:44 任务 1 之后的中断，起因是**整机崩溃**，
     与途中"环境变更（换驱动/刷 BIOS）"是**两件独立事件**，不得混记。

## 五之二、阶段 B3 补丁：预热前缀与在线代理不同源（缺陷修复）

发现问题时间: 2026-09-27 21:2x ENV2 起服务时（up --smoke 的启动预热日志）

现象（上线即暴露）:
  启动预热打印 "瘦身：省 28327 字符（location=14689 / deferred=9941 / subagent=3697）"，
  即三项全剥；而 config\bonsai-agent.json 的 slimming = locations:true / deferred_tools:false /
  subagents:false，在线代理只会剥 location。两者前缀不同 -> 本次 120.8 秒预热对真实请求无效。

根因:
  launcher\bonsai_launcher.py 的 do_prewarm() 用 importlib 载入代理模块后，只设了 mod.ARGS，
  没有调用 mod.load_runtime(...)。代理模块的 CFG 因此停留在【内置默认】
  （proxy\bonsai_proxy.py:105 slimming 三项全 True），而不是权威配置文件里的逐项值。
  在线代理进程是用 --config 启动的，load_runtime() 已把 CFG 覆盖为“只剥 location”。
  => 同一份代码、两种 CFG => 预热管线 ≠ 真实请求管线（违反方案 §B3）。

修改文件: launcher\bonsai_launcher.py
  sha256 before d06a8ed485301bc3247d7c94a1e5630972dc3c35c804cd1d7d4e817df4057e6e (32613 B)
  sha256 after  f28affccb848d7ca7d503f18160f3e77af56f83ca169abfeeb5ea857ee4477e5 (32984 B)
  备份: backup\stageB3\bonsai_launcher.py.prefix_B3
  改动:
    1. def do_prewarm(cfg) -> def do_prewarm(cfg, cfg_path=DEFAULT_CONFIG)
    2. 在 mod.ARGS 赋值后新增 mod.load_runtime(cfg_path)（让预热模块读同一份权威配置）
    3. 两个调用点 do_prewarm(cfg) -> do_prewarm(cfg, args.config)（cmd_up 的预热分支、main 的 prewarm 动作）

测试结果:
  见下方“验证”段（prewarm 重跑：瘦身明细应只剩 location 非零，且与在线代理一致）。

未解决问题:
  同源只修到 slim/tools/timeouts/capture_dir；采样与后端参数仍由后端进程命令行决定（不涉及预热）。

回滚入口: 用 backup\stageB3\bonsai_launcher.py.prefix_B3 覆盖 launcher 后重启代理即可（R2 同类）。

### 阶段 B3 补丁 —— 验证结果（补充上节“测试结果”）

  修复后重跑 launcher prewarm，日志瘦身明细由“三项全剥”变为：
    省 14689 字符（location=14689 / deferred=0 / subagent=0）  ← 与在线代理配置一致
  预热本体：req_001_192027.json  prompt_n=64358  cache_n=0  prefill=123.1 s  wall=124.0 s
  关键佐证：修复前同一份请求体预热得 prompt_n=60675，修复后为 64358，
            相差 3683 token —— 即旧预热建立的前缀与真实请求前缀的缺口，证实“旧预热必然命中不上”。
  结论：B3 预热同源已修复并实机验证；此项属方案 §B3 要求，回滚见 backup\stageB3。

## 六、阶段 ENV2：环境变更后重采运行事实（§A2 口径）

背景：本次执行期间发生范围外环境变更（BIOS R2CN57WW→R2CN59WW；NVIDIA 591.86→616.92 Studio），
      OS/VBS/Secure Boot/采样/后端硬件参数未变。故按 §A2 重新采集运行事实。

起服命令: python D:\Bonsai-demo\launcher\bonsai_launcher.py up --smoke
  配置指纹: 0b0d2806eb9a9d1a
  后端 pid 35040 (:8081)  代理 pid 31136 (:8080)
  在线生效参数: -c 65536 / -np 1 / -b 2048 / -ub 512 / -ctk q4_0 -ctv q4_0 / -fa on / -ngl 99
                MTP 关；采样 server_default（未传）；--backend-sampling --jinja --metrics
  代理启动参数含 --config D:\Bonsai-demo\config\bonsai-agent.json --effort medium
  瘦身: location=True deferred=False subagent=False
  工具体: 契约加固=True / 错误恢复策略块=True
  冒烟(经代理真实推理): 通过 1.08 s finish_reason=stop  prompt_tokens=20 completion_tokens=2
  后端冷启动耗时: 11 s
  启动预热: prompt_n=64358 cache_n=0 prefill=123.1 s（见下节修正）

基线作废声明（重申 G9/G10）：
  驱动更换前的一切性能数字（含上一轮 task1 wall_s=82.9、各 decode tps）一律不得作为
  优化前后对照基线，只能记为“环境变更效应”。本轮起以 ENV2 为新的运行起点。

## 七、阶段 G1 前置：产物保全与清空（避免跨环境污染）

  上一轮（驱动更换前、20:16:55 被整机崩溃打断）残留物已保全为证据后清空：
    runs\B\results\{_harness_task1.log,_harness_task3.log,_run_task1.json,_run_task2.json,
                      constraints.md,sales.json} 共 6 个文件
      -> optimization\20260927_165311\backup\stageG\B_results_prechange_20260927_214455\
    bench\results.jsonl（仅 1 条旧记录，属旧环境）
      -> backup\stageG\results.jsonl.prechange_20260927_214455
  核对：runs\B 的非 results 夹具（calc.py/checkpoint.md/notes.txt/sales.csv/source.txt/
        logs\run.log）与 bench\fixtures 逐文件 SHA256 一致 —— 任务输入仍是原始夹具，未被人为改动。

## 八、阶段 G1：环境变更后重跑 B 配置批量（首轮记录；结论见第九节）

  命令: python D:\Bonsai-demo\bench\run_all.py B --tasks 1,3,4,5,6,7,8,9,12
  执行: 串行（后端 -np 1），全部经 :8080 代理，每任务 harness max-rounds=16 / time-cap=1500 s
  结果: bench\results.jsonl（本轮新建），逐任务 _run_task*.json 与 _harness_task*.log 在 runs\B\results\
  备注: 任务 10（多轮）/ 任务 11（断点）需专用驱动 bench_multiturn.py，不在本批

## 九、阶段 G1：B 配置 9 项批量结果与判定口径修正 —— 完成

### 9.1 运行与结果

  命令（首轮）: python D:\Bonsai-demo\bench\run_all.py B --tasks 1,3,4,5,6,7,8,9,12
  命令（复跑）: python D:\Bonsai-demo\bench\run_all.py B-r2 --tasks 6,12   （全新目录，保全首轮证据）
  执行方式: 串行（后端 -np 1）；全部经 :8080 代理；每项 harness max-rounds=16 / time-cap=1500 s
  结果文件: bench\results.jsonl（每行一条，cfg 字段区分 B / B-r2）

| 任务 | 首轮判 | 复跑判 | 墙钟(s) | 轮数 | decode_tps 区间 | 备注 |
|---|---|---|---|---|---|---|
| 1   | OK 4/0 | -      | 10.0  | 3  | 41.4~45.9 | 五条约束齐全，source 未改 |
| 3   | OK 5/0 | -      | 57.5  | 14 | 39.3~45.7 | 工具重复=3（自纠后收敛），夹具 350 通过 |
| 4   | OK 5/0 | -      | 14.6  | 6  | 41.8~45.4 | 六行 JSONL、重复行保留 |
| 5   | OK 5/0 | -      | 10.9  | 3  | 45.0~45.5 | 仅交付格式变化，notes/source 哈希未变 |
| 6   | FAIL 4/1 | **OK 5/0** | 31.4 / 32 | 7 | 41.1~44.3 | 首轮失败系**验收脚本缺陷**，见 9.2 |
| 7   | OK 5/0 | -      | 40.0  | 5  | 40.5~45.8 | 单文件离线 HTML，无外链 |
| 8   | OK 6/0 | -      | 103.5 | 5  | 40.9~44.1 | 自动化判据全过（XML/行数/两个动画/无外链）；**形象与效果需人工看图，见 9.4** |
| 9   | OK 3/0 | -      | 8.6   | 3  | 45.0~45.3 | 至多一次失败读取、未创建 missing.txt、未重复读同路径 |
| 12  | FAIL 4/1 | **FAIL 3/2** | 74.2 / 55 | 16 | 37.7~45.1 | **真实失败，两轮一致**，见 9.3 |

  小计：B 配置 9 项 = **8 项通过 / 1 项失败（任务12）**（任务6 按方案口径复算通过）。
  decode 吞吐全程 37.7~45.9 tok/s，TTFT 0.3~6.6 s（热前缀，预热前缀见第六节 ENV2）。
  注：本节数字属**环境变更后**（BIOS R2CN59WW + 驱动 616.92）新采，与变更前数字不可比。

### 9.2 验收脚本缺陷（首轮"任务6 FAIL"的真因）—— 已修，留痕

  方案 §14.2 对第6项的执行者验收是"恰好137/E137、811/E811，**无遗漏**"，
  而任务6 原文要求"**仅保留行号、错误码、原因**"。
  G0 写的第 4 条判据却是 `len(re.findall("ERROR", txt.upper())) >= 2` —— 要求正文出现两处字面 "ERROR"，
  与"仅保留行号/错误码/原因"直接互斥。首轮模型产出 results\errors.md 内容为：
      137 | E137 | missing config ；811 | E811 | timeout（仅两行数据，完全符合原文）
  即：**模型交付正确、脚本判错**。

  同批发现第 2 处仪器问题：第12项"含去重已支付统计 3"用 `\b3\b` 全篇搜索，
  首轮模型产出里的标题"## 3. 实际生成文件路径"恰好含独立 3，使该条**误判为通过**（仪器过松）。
  第 3 处：脚本 docstring 宣称 `--selftest` 负向自检，main() 里并未实现（执行即打印用法、退出码 2）。

  三处均已修正，原始文件完整留痕：
    备份: optimization\20260927_165311\backup\stageG\check_tasks.py.preG1fix
    sha256 修正前 = 69bdb824bdc4c8000b86318aed77a33f38cef746ba7dc90cccfa3764ed14c490
    sha256 修正后 = ae549ca367fff01cb12ebaf657786d772251e918eea4d468cb6f1166c3fd234b
  修正内容:
    1) t6 第4条 -> 核对"恰好两条数据行且行号为 137/811"（对应方案"无遗漏"，不再与原文冲突）；
    2) t12 第2条 -> 要求 3 出现在"去重/已支付"同行上下文内（收紧，不改变任务12 的失败结论）；
    3) 实现 --selftest = 对夹具目录跑全部任务（负向自检）。
  修正后负向自检: `python check_tasks.py --selftest` => **5 通过 / 13 失败**，与修正前基线一致，
  仍能识别"未完成任务"（含任务3 的 680.0 未去重被正确判失败）—— 未因放宽而失效。
  复跑验证: 任务6 在同一夹具新目录 B-r2 上 5/0 通过，确认修正有效且模型行为稳定。

### 9.3 任务12 失败定性（真实失败，非脚本问题）

  方案 §14.2 第12项执行者验收 = "**去重已支付3/350**、两个错误、路径真实"。
  两轮模型产出均为"按行"统计（首轮 paid 4 行/550、复跑 paid 4 条/550），并另行给出
  "唯一订单数（去重）5"，但**始终未给出去重口径的已支付 3/350**。
  人工核对夹具（bench\fixtures\sales.csv）：A003 出现两次（均 paid），
  故 6 行 / 去重 5 单 / 总额 680 / paid 4 行 550 / refunded 80 / pending 50 全部正确，
  run.log 1000 行含 137/811 两条 ERROR 也正确 —— 产物**数值自洽、路径真实**，
  唯独口径不符合方案要求。按"只看产物、不看自述"的原则判 **FAIL**，不折算成"部分通过"。
  可复现性：两轮独立运行（B 与 B-r2）、均 16 轮用满、同一偏差 => 属稳定行为而非偶发。

### 9.4 仍待办（不在本节结项）

  - 任务 8 的**视觉人工验收**：自动化判据（XML 合法、46 行 ≤120、车轮 animateTransform 旋转、
    鹈鹕组 translate 起伏、无外部资源）全部通过，但"形象是否为鹈鹕骑自行车"须人工看图确认（方案明确要求人工验收须标明）。
  - 任务 10（普通五轮 + 压缩边界五轮）、任务 11（断点续做）=> 阶段 G2。
  - A 配置（修复前代理 v2）对照 => 阶段 G3。
  - 任务6/12 共同观察：模型首轮倾向 `run_python("/tmp/xxx.py")` 这类 POSIX 绝对路径，
    被 harness 路径守卫拒绝 1 次后即可自纠（各 1 次，无重复重试）—— 记录为模型行为事实，不属缺陷。

## 十、阶段 G2：任务11（断点续做）、任务10（五轮摘要）与三处工具缺陷修正

### 10.1 任务11 断点续做 —— 通过

  驱动: python run_all.py B-t11 --tasks 11（cfg 名以 t11 结尾时预置 results\sales.json）
  预置内容: {"count": 3, "amount": 350}，其规范化 sha256 = ce3f1fca8433dd83919abf7b190b268a982eff2ea092b841c8f6e9ad09aa4083
            （与 fixtures\MANIFEST.json 的 task11_preset_sales_json.sha256_of_canonical 一致，程序化核对通过）
  结果: **OK 2/0**，墙钟 16 s，6 轮，stop=model_finished
    判据1 预置统计结果未被重写（哈希一致）—— 通过（模型没有去重做已完成步骤）
    判据2 待办已完成（results\constraints.md 存在）—— 通过
  结论: 模型正确读取 checkpoint.md、区分"已完成/待办"，未破坏既有产物。

### 10.2 任务10 普通五轮摘要 —— 通过（首次因驱动截断误判为失败）

  首跑（B-t10，修正前驱动）: 五轮切片全部执行，但**末轮模型先发起一次 list_dir 探测**
    （results 目录当时为空，返回空清单），驱动随即退出 => 没有 results/final-summary.md，判 FAIL。
    定性：**驱动能力缺陷**，不是模型能力结论 —— 真实客户端在模型请求工具后会继续执行并回灌结果，
    直到模型给出终止响应；原驱动把"末轮请求工具"当成对话结束。方案 §14.2 第10项要求
    "最后按最初约束交付总结"，一个在末轮截断工具链的驱动无法观测该要求。
  修正（backup\stageG\bench_multiturn.py.preG2b，sha256 683c1f70… -> 736710ac…）:
    五轮固定切片计数不变，之后允许最多 6 个**收尾轮**，仅用于把模型已发起的工具链执行完并等它收尾；
    收尾轮单独记为 tail_rounds，不混入"五轮摘要"计数。
  复跑（B-t10b）: **PASS 3/0**
    摘要轮 1-5: 12.5 / 7.9 / 9.0 / 8.8 / 11.2 s（ttft 2.4~3.4 s）
    收尾轮 1: 21.5 s -> write_file 写出 results\final-summary.md（841 字符）
    收尾轮 2: 2.0 s  -> read_file 回读自检；收尾轮 3: 8.5 s -> 自然收尾（finish=stop）
    判据 1 最终交付存在 / 2 能列全最初五条约束 / 3 source.txt 哈希未变 —— 全通过

  附带修正（同文件，备份 bench_multiturn.py.preG2，sha256 f60aed4d… -> 683c1f70…）:
    a) 轮数：方案要求"五轮日志摘要"，原脚本只有 4 轮（4×250 行），改为 **5 轮 × 200 行**，
       恰好覆盖 1..1000 行；docstring 自称"普通五轮"与代码不符的问题随之消除。
    b) 落盘位置：原脚本把切片写进只读夹具目录 bench\fixtures\splits，
       与 MANIFEST"原始夹具只读"冲突 -> 改写进本次运行目录 <run-dir>\slices，切片与哈希仍逐条入档。
  切片哈希（5×200 行，B-t10b\slices\MANIFEST.json）:
    slice1 [1,200]      2506 字符 69c67f7b26b50d1f   slice2 [201,400] 2600 字符 ae5898e9138fea10
    slice3 [401,600]    2600 字符 e2490f6a058a0cc0   slice4 [601,800] 2600 字符 2100d53371cecce5
    slice5 [801,1000]   2608 字符 0bc08defa2d332ff

### 10.3 压缩边界五轮 —— 未实现（受 harness 能力限制，不谎报）

  方案 §14.2 第10项要求"同时做普通五轮和压缩边界五轮"，边界版需由会做历史压缩的客户端
  （WorkBuddy/Pi）构造。本地 harness 无压缩器，**本轮未做**，报告中按"未实现"标注，
  不以任何替代实验冒充。该限制原已写在 bench_multiturn.py 的 docstring 里。

### 10.4 任务8 视觉人工验收（方案要求人工看图，自动化判据不能替代）

  自动化判据（check_tasks t8）: 6/0 全通过 —— XML 合法、46 行 ≤120、车轮 animateTransform 旋转、
  鹈鹕组 translate 起伏、无外部资源引用。
  人工渲染验收（本地 http://127.0.0.1:8099 提供产物后由浏览器实际渲染截图，非源码阅读推断）:
    截图证据: runs\B\results\visual_pelican_1.png、visual_pelican_2.png（间隔约 1 s）、visual_status.png
    鹈鹕 SVG: 能明确看出长喙白鸟骑在自行车上：前后两轮 + 车架 + 脚踏 + 鸟腿连接，
      比例与连接合理，无悬空/错位/缺件。
      动画: 两帧车轮辐条角度明显不同 => **旋转动画为真**；身体起伏仅 5 px / 0.4 s，
      两帧未能区分出差异 => 记"幅度小、肉眼不易分辨"，不写成"已验证"。
      坦率评分: 约 6/10 —— 形象可辨但风格极简化（非写实）。
    status.html: 正常渲染、无空白、无外部资源加载失败、排版无错位截断；
      正文含"项目代号：松针"与五条约束（交付格式 Markdown / 禁止修改 source.txt / 输出目录 results /
      预算单位 人民币元 / 已完成 sales.csv 去重统计且不得改写）。
    说明: 浏览器沙箱默认拒绝 file:// 协议，故改用一次性本地静态服务（127.0.0.1:8099，验收后已停止）
      提供产物再渲染；该服务只读本地目录、不联网、已关闭。

### 10.5 测量字段缺陷（harness 取值键名不匹配）—— 已修

  问题: 代理写入 logs\requests.jsonl 的字段是 prompt_evaluated_tokens / cache_reused_tokens，
  而 bench_harness.py 用 x.get("prompt_n") / x.get("cache_n") 取值 => 每轮全为 null，
  若照此写报告会把"其实拿得到的数据"误写成"缺失"（§14.3 第4条禁止把缺失写成 0，同样禁止把有写成缺）。
  修正（backup\stageG\bench_harness.py.preG2c，sha256 53e44566… -> c1693cee…）:
    按代理实际字段取值（旧键名兜底），并补 §14.3 要求的 reasoning_tokens / answer_tokens /
    est_reasoning_chars / wall_ms / cache_reuse / config_hash；拿不到仍保持 null。
  说明: 代理侧 reasoning_tokens 为 null 是**上游服务端不回 usage**所致（记录内 notes 已写明），
        本地只能给 est_*（按字符数估算），报告中不作为 token 数使用。
  验证: 修正后以 B-r3 重采一批（第三次采样，符合 §14.3 第3条"每项再两次"的推进方向），数据见第十一节。

## 十一、阶段 G：第三次采样（B-r3）与测量字段验证

### 11.1 为什么要再采一批

  方案 §14.3 第3条要求"最终候选与可用对照每项再两次，共三次"。本批是 B 配置的**第二次重跑**
  （加上首轮即每项两次；任务6/12 因脚本修正另有一次复跑），同时用来验证 10.5 的测量字段修正。

### 11.2 测量字段修正验证（同一批任务，修正前 vs 修正后）

  cfg=B（修正前 harness）: 9 条记录的 prompt_n / cache_n **全为 null**（键名不匹配所致，属仪器缺陷）。
  cfg=B-r3（修正后）: 9 条记录每轮都取到真值，且能看出真实的 KV 复用行为，例如
    任务3: prompt_n 526 -> 153，cache_n 216 -> 7730（14 轮）
    任务12: prompt_n 524 -> 372，cache_n 216 -> 7636（16 轮）
    任务1: prompt_n 516 -> 123，cache_n 216 -> 798（3 轮）
  => 修正有效；此后报告中的预算/复用数字以 B-r3 口径为准。

  仍为 null 的字段及原因（不写 0，按 §14.3 第4条）:
    reasoning_tokens / answer_tokens —— 上游 llama-server 未回 usage，代理记录内 notes 已注明"服务端未返回 usage"；
    est_reasoning_chars —— 本批响应未出现独立的 reasoning 流内容，故无估算对象。
    本地只保留 est_*（按字符估算）与 decode_tps（服务端 predicted_per_second），不冒充 token 计数。

### 11.3 B-r3 逐项结果（第三次采样）

| 任务 | 判定 | 墙钟(s) | 轮数 | prompt_n 首→末 | cache_n 首→末 | decode(tok/s) |
|---|---|---|---|---|---|---|
| 1  | 通过 | 9.4   | 3  | 516→123 | 216→798  | 45.0~45.5 |
| 3  | 通过 | 71.3  | 14 | 526→153 | 216→7730 | 38.8~45.5 |
| 4  | 通过 | 14.9  | 6  | 526→197 | 216→1164 | 41.9~45.5 |
| 5  | 通过 | 10.9  | 3  | 525→124 | 216→890  | 44.8~45.0 |
| 6  | 通过 | 31.2  | 7  | 525→216 | 216→5530 | 41.0~44.6 |
| 7  | 通过 | 39.4  | 5  | 523→796 | 216→1762 | 41.3~45.6 |
| 8  | 通过 | 101.8 | 5  | 534→74  | 216→2247 | 42.5~44.9 |
| 9  | 通过 | 8.7   | 3  | 528→122 | 216→791  | 44.3~44.6 |
| 12 | **失败** | 74.1 | 16 | 524→372 | 216→7636 | 38.7~44.3 |

  小计：8 通过 / 1 失败（任务12），与首轮一致。

### 11.4 任务12 的三次采样（可复现性）

  第1次（cfg=B）   : 按行统计 paid 4 行 / 550，无去重 3/350 -> FAIL
  第2次（cfg=B-r2）: 按行统计 paid 4 条 / 550，无去重 3/350 -> FAIL
  第3次（cfg=B-r3）: 同上口径 -> FAIL
  => 三次独立运行偏差一致，**属稳定行为而非偶发**；同时任务 3（要求"仅汇总 paid、按 order_id 去重"）
     三次均通过（350 判据通过），说明模型**不是不会去重**，而是在"汇总统计"这类开放措辞下
     默认选择了按行口径，未对齐 §14.1 的去重口径。这是本阶段唯一稳定失败项，报告中不得省略。

### 11.5 耗时波动（如实记录）

  同一任务两次运行差异不小：任务3 57.5 s vs 71.3 s（+24%），任务8 103.5 s vs 101.8 s（-1.6%），
  任务1 10.0 s vs 9.4 s。波动主要来自推理轮数（任务3 均 14 轮）与宿主内存压力（见第八节 G0 判定）。
  因此本阶段数字只用于"同配置三次采样"的工程参考，**不作为提速承诺**（§14.3 第5条）。
## 十二、阶段 G：A 配置（修复前代理）受控对照 + 任务 2 补齐 —— 完成

### 12.1 为什么补做（口径）

方案 §14.3 规定三种基线对照：A = 当前 WorkBuddy + **修复前代理**；B = 修复后代理/预算；C = Pi。
第九/十一节的 B 批是"修复后"的采样，**不能代替受控 A**。本节按 §14.3 补做 A：同一后端进程、同一夹具、同一 harness，只把 :8080 上的代理换回修复前版本。

### 12.2 受控条件逐项核对

| 项 | A（本节） | B（B-r3，第十一节） |
|---|---|---|
| 后端进程 | pid 35040，**全程未重启** | 同一 pid 35040 |
| 后端参数 | -c 65536 / -np 1 / -b 2048 / -ub 512 / -ctk q4_0 -ctv q4_0 / -fa on / -ngl 99；MTP 关；采样 server_default | 同 |
| 代理脚本 | `backup\proxy__bonsai_proxy.py`（修复前 v2）sha256 `5DAAB527…` | `proxy\bonsai_proxy.py`（修复后 v3）sha256 `6ACFB9C5…` |
| 代理启动参数 | `--port 8080 --upstream 8081 --effort medium`（**不接受 --config**，故不经 launcher，手动起在原端口） | `--port 8080 --upstream 8081 --config config\bonsai-agent.json --effort medium` |
| 瘦身 | 三项全开（① 剥 location ② 压 deferred 名册 ③ 压 subagent 名册） | 仅 ①（deferred/subagent 名册保留） |
| 工具体契约加固 / 错误恢复策略块 | 无 | 有（F1 / F4） |
| 每请求 JSONL 日志 | 无 | 有（C4） |
| 预热 | 未预热（后端连续运行，本就非冷启动） | 未预热 |
| harness / 夹具 | `bench_harness.py` `c1693cee…`；`bench\fixtures` 原样拷贝 | 同 |

### 12.3 服务切换留痕（只换代理，不动后端）

1. 备份现状代理：`backup\stageG\preA_proxy__bonsai_proxy.py`，sha256 `6ACFB9C5…`（= 修复后 v3）。
2. 停修复后代理 pid 31136：先核对 cmdline 属于本项目（`… -u D:\Bonsai-demo\proxy\bonsai_proxy.py --port 8080 --upstream 8081 --config … --effort medium`），再 `taskkill /PID`（被拒）→ `/F`。:8080 释放。
3. 起 A 代理 pid 33800，日志 `baseline\stageG_A_proxy.log`。启动横幅逐字确证：
   `请求瘦身: 开（① 剥 location ② 压 deferred ③ 压 subagent，省约 8,626 tok/次）`、`思考档位: 注入 reasoning_effort=medium（客户端配置不用改）`。
4. A 批跑完后停 33800（身份核对后 /F），`launcher up` 恢复修复后代理：pid **18008**；`launcher status` 指纹回到 **0b0d2806eb9a9d1a**，后端仍是 pid 35040（在线参数与配置一致、无需重启）。
5. 副作用留痕：A 代理会写抓包，`capture\*.json` 从 225 增至 309（新增均为 `small_*.json`，请求体 < 20000 字符）；`capture\effort.txt` 被改写为 `medium`（与 B 配置 `thinking.default_effort` 同值，无实质差异）；`capture\timings.jsonl` 追加 63 条。预热取材门槛是 ≥20000 字符，故新增小文件不会被误当预热素材。

### 12.4 A 侧测量字段的来源（与 B 不同源，必须注明）

修复前代理不写 `logs\requests.jsonl`，因此 `bench\results.jsonl` 里 `cfg = A1 / A-t2 / A-t11` 的 `prompt_n` / `cache_n` / `decode_tps` 为**空数组（不是 0）**。
A 侧改用 `capture\timings.jsonl` 增量取数（起点 offset = 49741 字节）：

- 9 项批量共 **63 条**对话记录（与 63 轮一致）。
- `decode_tps`：最低 37.55 / 中位 ≈ 41.5 / 最高 44.9；与 B-r3 的 38.8~45.6 同量级。
- `prompt_n`：每个任务首轮 397~415；其后 36~1073；读 `logs/run.log` 的轮次为 4384 / 4298 / 4383。

**A 与 B 的 t/s 来自两个不同通道，只能作量级比较，不作严格比对。**

### 12.5 A 上的 P08 现场复现（修复前判据）

`capture\timings.jsonl` 本轮 63 条里有 3 条 `hit=false`（修复前判据 `prompt_n < 1500`），而这 3 条的 `cache_n` 分别是 **2843 / 4912 / 5364** —— 即"高比例复用被误报为全量重算"。这正是 P08 在修复前代理上的现场复现；修复后代理已改为 `cache_reuse` 四档（无复用 / 部分复用 / 高比例复用 / 未知）。

### 12.6 12 项结果对照（A 与 B 同一后端、同一夹具）

| 任务 | A（修复前代理） | B（修复后代理） | 备注 |
|---|---|---|---|
| 1 | 4/0 通过 8.8s / 3 轮 | 4/0 通过 9.4s / 3 轮 | |
| 2 | 4/0 通过 16.4s / 4 轮 | 4/0 通过 16.6s / 4 轮 | 本轮补齐（此前 A/B 都缺项） |
| 3 | 5/0 通过 105.4s / 14 轮 / 重复 6 | 5/0 通过 71.3s / 14 轮 / 重复 3 | A 重复调用翻倍 |
| 4 | 5/0 通过 18.1s / 6 轮 | 5/0 通过 14.9s / 6 轮 | |
| 5 | 5/0 通过 15.1s / 6 轮 / 重复 1 | 5/0 通过 10.9s / 3 轮 | |
| 6 | 5/0 通过 35.9s / 9 轮 / 重复 1 | 5/0 通过 31.2s / 7 轮 | B 首次采样曾 4/1，B-r2、B-r3 均 5/0 |
| 7 | 5/0 通过 44.4s / 5 轮 | 5/0 通过 39.4s / 5 轮 | |
| 8 | **0/1 失败** 94.2s / 1 轮 | 6/0 通过 101.8s / 5 轮 | 见 12.7 |
| 9 | 3/0 通过 12.9s / 4 轮 | 3/0 通过 8.7s / 3 轮 | |
| 10 | 3/0 通过（5 轮 + **6** 收尾轮，合计 78.2s） | 3/0 通过（5 轮 + **3** 收尾轮） | 见 12.8 |
| 11 | 2/0 通过 15.7s / 6 轮 | 2/0 通过 16.2s / 6 轮 | |
| 12 | **3/2 失败** 57.1s / 15 轮 | **3/2 失败** 74.1s / 16 轮 | 两配置均稳定失败（真实能力缺口） |

**9 项批量（1,3,4,5,6,7,8,9,12）汇总：**

| 指标 | A（A1） | B（B-r3） |
|---|---|---|
| 成功任务数 | **7 / 9** | **8 / 9** |
| 中位墙钟 | 35.9 s | 31.2 s（-13.1%） |
| 合计墙钟 | 391.9 s | 361.7 s |
| 总轮数 | 63 | 62 |
| 工具重复调用次数 | 8 | 5 |
| 截断（finish=length） | 1（任务 8） | 0 |

**12 项总通过数：A = 10 / 12，B = 11 / 12。**

### 12.7 任务 8 在 A 上的失败形态（如实记录，含混淆因素）

`runs\A1\results\_harness_task8.log` 只有 1 轮：`wall=94.1s ttft=1.3s finish=length 工具调用=0 content=0 字`。
即模型把 4096 输出上限全部用在思考上，既没给答案也没发工具调用，判定为截断（`finish=length`），`results/pelican.svg` 不存在，验收 0/1 失败。这符合 §1.1 第 5 条要求的记录方式（保存终止原因与截断事实，不归咎于单一原因）。
**混淆因素必须声明**：A 与 B 的差异是"整包工程修复"（C/D/E/F 全缺），不是单一变量；因此不能把任务 8 的翻转单独归因于某一项修复。

### 12.8 任务 10 收尾轮的重复调用现象（A 侧）

- A：收尾轮 6 次 —— `read_file` → `write_file` → `read_file` → `read_file` → `read_file` → `list_dir`，其中第 3~5 次是**参数完全相同**的重复调用，直到触到 6 轮上限才停。
- B（`runs\B-t10b`）：收尾轮 3 次 —— `write_file` → `read_file` → `stop`（自行停止）。

方向与 F2"同一错误连续两次不得原样重试"一致；但同样是整包对照，不能单独归因。

### 12.9 本节结论（诚实表述）

1. 受控 A 已补上：§14.3 的 A/B 两档现在都有同条件实测，不再用历史记录代替。
2. A → B 的工程修复在 9 项批量上：成功数 7→8（+1 项，任务 8），中位墙钟 35.9s→31.2s（-13.1%），工具重复 8→5。**样本仅 9 项、单次采样，不足以宣称稳定的量化提速。**
3. 任务 12 在 A、B 两个配置下都稳定失败（第十一节三次采样 + 本节 A 一次），属真实能力缺口，不是修复回归。
4. 任务 2 已补齐（此前 A/B 均缺项），两配置均 4/0 通过。
5. 未达到 §2.1"成功完成任务的中位耗时改善至少 20%"的口径，按方案要求报告为"稳定性与可靠性修复完成，尚未有充分证据支持大幅提速"。

### 12.10 回滚入口

- 恢复修复后代理：`python D:\Bonsai-demo\launcher\bonsai_launcher.py up`（已验证指纹回 `0b0d2806eb9a9d1a`）。
- A 代理已停；备份 `backup\stageG\preA_proxy__bonsai_proxy.py` 保留，必要时比对 sha256 `6ACFB9C5…`。



## 十三、阶段 H：部署门槛、回滚演练与交付清单 —— 完成（2026-09-27 22:46）

### 13.1 本阶段的性质：只新增交付物，不改生产代码

阶段 H **未修改** `proxy\bonsai_proxy.py`、`config\bonsai-agent.json`、`launcher\bonsai_launcher.py`
（三者的 sha256 与本阶段开始时一致：代理 `6ACFB9C5…`、配置 `D678A79A…`）。
只新增：交付文档、只读证据、以及一份回滚演练脚本（`tests\rollback_drill.ps1`，sha256 见 rollback.md R7）。

### 13.2 新增文件

| 文件 | 规模 | 说明 |
|---|---|---|
| `optimization\20260927_165311\effective-config.json` | 9,947 B | 最终配置 + 二进制/模型标识 + 实况核对（由 `.stage\gen_h_deliverables.py` 只读生成，可复跑） |
| `optimization\20260927_165311\results.csv` | 9,079 B / 36 行 | 逐行明细；失败与缺失写 null 并注明原因，不写 0 |
| `optimization\20260927_165311\comparison.md` | 9,491 B / 9 节 | A/B 对照；含"同任务配对"可比口径与口径限制 |
| `optimization\20260927_165311\日常启动说明.md` | 9,709 B / 212 行 | 唯一入口 / 查看状态 / 选择任务档 / 处理超预算 / 取消任务 / 回滚入口 |
| `optimization\20260927_165311\tests\rollback_drill.ps1` | 4,924 B | 回滚演练脚本（本次实跑） |
| `optimization\20260927_165311\baseline\stageH_rollback_drill.log` | 9,615 B | 演练日志 |

`rollback.md` 追加 R7（演练实录），13,284 B → 15,752 B。

### 13.3 部署门槛与回滚演练（结论）

- §H1 六条门槛逐条达成，见母本附录 9.2。
- §H2 演练实测通过：代理回滚到 `A375F4F3…`（`harden_tool_schemas`=False）→ `launcher up` 后
  `:8080 /health`=ok、build `b181-9ef3205`、`n_ctx=65536`、smoke 0.94 s `finish=stop`；
  前滚复原 sha256 回到 `6ACFB9C5…`、smoke 0.55 s。**后端 pid 35040 全程未重启**。
- 局限：演练只覆盖了代理文件一条路径；`config`/`launcher`/`tests\stage_e_probe.py` 的覆盖回滚未实跑（命令见 R6）。

### 13.4 四类状态清单

见母本附录 9.4（已完成 / 未启用候选 / 客户端限制 / 需用户决定）。
其中"需用户决定"6 项、验收勾选表"部分达成"2 项（第 3、12 条），未擅自推进。

### 13.5 回滚入口

`optimization\20260927_165311\rollback.md`（R0~R7）。铁律不变：不按端口盲杀、不 `git reset --hard`、
不覆盖其他 agent 备份后新增的改动；停止只操作 state 中核对过身份的 PID。


## 十四、阶段 G4 — 限制服务端宿主 prompt cache（`--cache-ram 1024`）

实施时间 2026-09-27 23:05–23:14；授权：用户明确批准「C1 + `--cache-ram 1024`，现在执行」。
（C4「提高 `-c` / n_ctx」经用户决定**不纳入**，保持 65536。）

### 14.1 变更

| 项 | 值 |
|---|---|
| 文件 | `config\bonsai-agent.json` 的 `backend.extra_args`（定点改写，其余结构/注释未动） |
| 改动 | `[]` → `["--cache-ram", "1024"]` |
| 字节/sha256 | 6,276 B `D678A79A…` → 6,297 B `A6876638…` |
| 备份 | `backup\stageG4\bonsai-agent.json.preG4`（= 变更前字节，`D678A79A…`） |
| 生效 | `launcher up --no-prewarm`；漂移检出「仅配置有: ['--cache-ram','1024']」→ 空闲受控重启后端 |
| 后端 | pid 35040 → 35084（就绪 7 s；命令行末含 `--cache-ram 1024`）；配置指纹 `0b0d2806eb9a9d1a` → `96df0f5964452b3c` |
| 代理 | pid 40480 **未重启**（命令行未变） |
| 未改动 | `proxy\bonsai_proxy.py`(`6ACFB9C5…`)、`launcher\bonsai_launcher.py`(`F28AFFCC…`)、n_ctx=65536、页面文件、BIOS/驱动/VBS/电源、模型权重 |

### 14.2 证据与结论

- **核心定量**：llama-server `Private Bytes`（perfmon）**17,796,993,024 B = 16.58 GiB → 10,262,142,976 B = 9.56 GiB**，
  差 **7,534,850,048 B = 7.017 GiB**；`--cache-ram` 上限差 8192−1024 = 7,168 MiB = **7.000 GiB** → 偏差 **0.25%**。
  该近似 1:1 吻合**同时**证实 C1 生效，并**间接证实**“变更前 16.58 GiB 私有提交主要构成为宿主 prompt cache”
  （原仅为推断；地址空间逐块拆解仍缺）。
- **宿主缓解**：Memory Compression WS 4,112 → 1,494 MB；全机 Available 5,780 → 6,809 MB；Committed 43.36 → 35.71 GiB。
- **任务回归**：bench 任务 1（9.2 s / 3 轮 / 0 重试 / 验收 4 通过；`prompt_n=[516,74,123]`、`cache_n=[216,728,798]`）
  与任务 2（15.9 s / 4 轮 / 0 重试 / 验收 4 通过）**与变更前逐项一致或略优** → 短会话无回归。
- **如实记录的失败**：首次以新 cfg 名 `G4-cram1024` 运行时，因 `bench\run_all.py` 的 `prep()` **不复制夹具**
  导致 `read_file notes.txt => ERROR: file not found`、模型探索至 `max_rounds=16` 失败（任务1 0 通过/1 失败，29 s/16 轮）。
  补齐 `runs\G4-1024\` 夹具后重跑即通过。→ **属执行脚手架疏漏，与被测的 `--cache-ram` 无关**；
  失败记录保留在 `bench\results.jsonl`（cfg=`G4-cram1024`）中未删除。

### 14.3 未验证 / 残余风险（不得当作已确认收益）

1. **长上下文跨请求复用未验证（最需关注）**：本轮 bench 仅到 `n_tokens_max=7,096`，而变更前真实使用达 **64,358**；
   变更前观测单个 64 K 序列检查点约 **2,030 MiB** > 新上限 1024 MiB → **长上下文检查点可能无法保留、TTFT 可能回归**。
2. 仅跑 **2/12** 项任务，未跑全套。
3. 绝对内存值不可比（变更前 uptime ≈81 min 且含 64 K 序列，变更后 7 min 57 s 且 ≤7 K）；结论主要建立在 14.2 首条的差值吻合上。
4. `pages input/sec` 10,177 → 951（同进程另一次瞬时采样为 2）波动大，**不可单独归因于 C1**。
5. 变更前“16.58 GiB 的逐块构成”仍未拆解（`g4_memprobe.ps1` 的 `VirtualQueryEx` 遍历器有缺陷，已判其分解不可用）。

### 14.4 产物与回滚

- `optimization\20260927_165311\G4 验收报告-C1 cache-ram 1024.md`（8,253 B，sha256 `53E8827E…`）
- `optimization\20260927_165311\G4 处置候选清单.md`（14,617 B，sha256 `F789234C…`）
- `optimization\20260927_165311\baseline\stageG4_cram1024_readonly_v3.txt`（变更后只读快照，2,578 B，sha256 `204F8CE6…`）
- `optimization\20260927_165311\baseline\stageG_G4_hostmem_readonly_v2.txt`（变更前深采，6,118 B，sha256 `A34251E7…`）
- 回滚入口：`rollback.md` **R8**（清空 / 调整 `extra_args` + `launcher up --no-prewarm`）

### 14.5 长上下文跨请求复用对照实验（14.3 第 1 项的验证）—— 完成（2026-09-28 00:41）

对 14.3 第 1 项做四臂对照（1024 / 2048 / 4096 / 8192），固定 64 K 真实请求体
（`capture\req_001_192027.json`，`prompt_n=64,396`）走生产同一管线直连后端，每臂四步：
A1 冷启 → A2 同请求 → B 用另一段 7,687 token 请求把槽位顶走 → **A3 再发同一 64 K 请求（决定性）**。

| `--cache-ram` | A3 prompt_n | A3 cache_n | A3 复用 | A3 prefill(ms) | A3 prefill(秒) | A3 墙钟(s) | A3 Δ淘汰 |
|---:|---:|---:|---|---:|---:|---:|---:|
| `1024` | 64396 | 0 | 无复用 | 118115 ms | 118.11 s | 118.49 | 1 |
| `8192` | 4 | 64392 | 完全复用 | 129 ms | 0.13 s | 0.85 | 0 |
| `2048` | 64396 | 0 | 无复用 | 118007 ms | 118.01 s | 118.4 | 1 |
| `4096` | 4 | 64392 | 完全复用 | 115 ms | 0.12 s | 0.65 | 0 |

**结论：14.3 第 1 项的风险落实，因果坐实。**

1. 1024 与 2048：A3 `cache_n=0`，需重算 64,396 token，**118 s 级（= 冷启）**。
2. 4096 与 8192：A3 `cache_n=64,392`，**0.65 / 0.85 s** —— 与冷启相差约 170 倍。
3. 2048 的失效机理有日志原文：A3 启动即 `making room for prompt cache entry, removing oldest entry
   (size = 1881.320 MiB)` —— 64 K 检查点（1.88–2.03 GiB）写入后被立即挤掉，等于白存 → **2048 不足**。
4. **影响边界**：A2 四臂均 `cache_n=64,392`、墙钟 0.23–0.35 s → **单条对话内继续追问不受影响**；
   受损的是「切走再回来 / 跨上下文」的长上下文复用。
5. 内存代价（perfmon Private Bytes）：8192 与 4096 在均持有 64 K 检查点时为 **10.01 GiB**（两者差 ~2 MB，
   说明该时点占用由缓存内容而非上限决定）；上限差 4096−1024 = 3,072 MiB 为配置层开销上限。

**生产配置已恢复**：`extra_args` 写回 `["--cache-ram","1024"]`，config sha256 `A6876638…`（与
`backup\stageG4\bonsai-agent.json.cram1024` **逐字节一致**）、配置指纹回到 `96df0f5964452b3c`、
后端 pid 30160、命令行末 `--cache-ram 1024`、前后端 `/health` 均 ok。中间态 `8192/2048/4096` 已消失。

**产物**：`G4 长上下文对照.md`；`baseline\g4_longctx_result_cram{1024,8192,2048,4096}.json`、
`baseline\g4_longctx_llama-server.log`、`baseline\g4_longctx_mem_snapshots.txt`。
回滚入口不变，仍为 `rollback.md` **R8**。

**建议**：保持 `--cache-ram 1024`（短会话零回归、宿主最省）；若需恢复跨上下文长上下文复用，
升到 **4096**（已实测有效）而非 2048（已实测无效）。
## 十五、阶段 G5 三次采样对照

依《交接执行方案》§14.3 第 3 条（每项三次、逐项交替、固定后端与采样参数）执行。窗口 2026-09-28 01:04:33 → 01:50:18，共 66 次 harness 调用。

**做这一批的原因**：此前 12 项只有零散单次采样，且 A/B 是「整批先 B 再整批 A」，并非逐项交替；旧采样还跑在 G4 变更之前的后端（宿主 prompt cache 未受 `--cache-ram 1024` 约束）。本批为**严格重采**：同一后端进程（`llama-server` pid 30160，`--cache-ram 1024`）上逐项 A/B 交替。

**两处口径缺陷已在本批修掉**：(1) 两臂首次跑在**同一后端进程**上；(2) 首次做到**逐项交替**且**零次生产代理切换**——A 臂（修复前 v2 代理，sha256 `5DAAB527…`）另起在 **:8082**，生产 :8080（pid 40480）全程未动。为此给 `bench_harness.py` 加了**向后兼容的 `--port` 参数（默认 8080）**，补丁后 sha256 `41FBFB0A…`，补丁前备份 `backup\stageG5\bench_harness.py.preG5`（sha256 `C1693CEE…`）。

### 15.1 汇总（§14.3 第 5 条口径）

| 指标 | A（修复前 v2 / :8082） | B（修复后 v3 / :8080） |
|---|---:|---:|
| 尝试次数 | 33 | 33 |
| 成功 / 失败 | 27 / 6 | 24 / 9 |
| 成功率 | 81.8% | 72.7% |
| 成功任务耗时中位数 | 17.4 s | 17.1 s |
| 全部尝试总墙钟（含失败与崩溃） | 1346.4 s | 1398.4 s |
| 工具重复调用数 | 14 | 19 |
| 超时（`time_cap`） | 0 | 0 |
| 驱动崩溃导致记录缺失 | 0 | 2 |

剔除任务 8（两臂 6/6 全因 `max_tokens=4096` 截断失败，非有效对照样本）后为 A 27/30 = 90.0%、B 24/30 = 80.0%；**再扣除任务 7 的目录污染后两臂同为 27/30 = 90.0%**。

### 15.2 配对耗时口径（唯一可直接比耗时的口径）

「全部尝试总墙钟」按第 5 条必须含失败项，但**失败也产生墙钟**，会把更早放弃的一侧显得更快。故另取「两臂各 3 次**全部通过**」的任务逐项求和对比：

| 项 | A 三次合计 | B 三次合计 | B−A |
|---|---:|---:|---:|
| 任务 1 / 3 / 4 / 5 / 6 / 9 / 11 / 2（8 项） | **630.0 s** | **653.0 s** | **+23.0 s（+3.7%）** |

把 **5.1 的隔离起点版任务 7**（A 134.6 s / B 204.7 s）计入后 A 764.6 s、B 857.7 s（B 慢 12.2%）。**结论：本批不支持「修复后代理有稳定提速」**；逐项方向不一致（B 快的：任务 4/5/9/11；A 快的：任务 1/3/6/12；任务 2 相当），差距更可能来自任务 3 这类长轮次任务的自然波动（B 三次 88.8 / 110.7 / 117.0 s，离散 ±14%）。

### 15.3 任务 7 与任务 8 的定性（关键词：排除混淆，不改原始记录）

- **任务 7**：主批 A 3/3 通过、B 0/3 失败，两臂各自三次结果字符串**完全一致**，失败项恒为 `五条约束内容齐全 {... 'Markdown': False ...}`。逐文件核对得真因：同一 run 目录里**任务 5**（顺序在前）把 `results\constraints.md` 的交付格式改成「纯文本」，B 的 `results\status.html` 第 90 行照抄了它（故缺 `Markdown`），A 取自 `notes.txt`。补做**隔离起点对照**（新目录只含夹具、无 `constraints.md`）：**A 3/3 通过（中位 44.8 s、5 轮、2,636 B）、B 3/3 通过（中位 68.2 s、6 轮、3,596 B）**→ 主批该行差异由「目录复用 + 任务顺序」引入，**与 v2/v3 代理行为无关**。原始记录保留原样（可复现），判定时扣除。
- **任务 8**：两臂 **6/6 全失败**，根因 `max_tokens=4096` 截断（`finish=length`）：A 三样本均「轮 1、工具调用 0、content 0 字」→ `results\pelican.svg` 不存在；B-s2 写出非法 XML（`duplicate attribute`）；B-s1/s3 因截断的工具调用参数导致下一轮上游**HTTP 500**，harness 未捕获该异常而崩溃、未写 `_run_taskX.json` → 2 行字段记 null。历史 `B-r3` 曾以 5 轮 `/finish=stop` 通过 → 属**截断边界敏感**，本批**不构成有效对照样本**，真实能力须另设实验放开 `max_tokens` 才能判定。
- **任务 12**：两臂 6/6 全失败，失败项恒为「含去重已支付订单数 3」「含总额 350」，与 §12.9 定性一致 → **稳定的真实能力缺口**（按第 5 条计入失败、不剔除）。
- **任务 10**：`bench_harness.py` 无该任务定义、`bench_multiturn.py` 仅普通五轮，**压缩边界五轮未实现** → 按第 4 条**记 null 并写明原因**。

### 15.4 与 §12.6 单次采样的差异（必须点明）

§12.6 单次采样曾显示 B（8/9）略优于 A（7/9）；本批三次采样**未支持**该方向，差异来源已定位为任务 7 的目录污染与任务 8 的截断，两者均与代理实现无关。**§12.6/§12.9 的定性结论（单次采样不足以宣称稳定提速）得到加强。**

### 15.5 生产现场未受影响（开跑前后逐项比对）

- :8080 pid **40480**、:8081 pid **30160** 前后一致；前后端 `/health` 均 ok；`config\bonsai-agent.json` sha256 `A68766381AAF1E32…` **前后一致**、`extra_args` 仍为 `["--cache-ram", "1024"]`；A 臂所用的 **:8082 已释放**。
- A 臂代理日志 `baseline\g5_A_proxy_8082.log`（41,924 B）内**无 Traceback、无 502**。

### 15.6 新增工具缺陷（本批新发现，未修，供后续处理）

`bench_harness.py` 的 `call_model()` **未捕获 `urllib.error.HTTPError`**：截断后的工具调用参数会使下一轮上游返回 HTTP 500，harness 直接崩溃且**不写 `_run_taskX.json`**，导致该次记录字段全 null。本批为保持已记录的 sha256 `41FBFB0A…` 有效**未改动该文件**；建议后续在 `call_model` 外包一层 try/except，把 HTTP 错误转成可记录的一轮结果。另：我方驱动脚本 `g5_run.py` 的降级分支条件写作 `if rounds and ...`，`rounds=None` 时不触发，故两行缺失记录的 `token_note` 也为 null（**已在报告第六节书面补记**，原始记录未篡改）。

**产物**：`G5 三次采样对照.md`（17209 B，sha256 `85efac814a66082e…`）；`baseline\g5_results.jsonl`、`g5_summary.json`、`g5_fingerprint.json`、`g5_timings.jsonl`、`g5_A_proxy_8082.log`、`g5_task7iso.jsonl`；`bench\results_task7iso.jsonl`；`backup\stageG5\bench_harness.py.preG5`。回滚入口不变，仍为 `rollback.md` **R8**；本批**未改动生产配置、未重启任何生产进程**。

**建议**：① 保持 `--cache-ram 1024`；② 任务 12 属真实能力缺口，后续如需提升应走提示/工具链方向而非代理侧；③ 任务 8 需另设放开 `max_tokens` 的实验；④ 修 `bench_harness.py` 的 `HTTPError` 捕获后，重算三采样 sha256 再复用历史记录。
### 15.7 收尾：修补 `bench_harness.py` 的两项工具缺陷（2026-09-28）

报告第九节留痕的两项缺陷已修，均为**向后兼容**改动（默认行为不变）：

- (a) `call_model()` 现捕获 `urllib.error.HTTPError` 与其它网络异常，改为把该轮记 `finish="http_error"`、结束原因 `stop_reason="upstream_error"` 并**照常写出 `_run_taskX.json`**，不再崩溃丢记录；round detail 新增 `error` 字段，输出记录新增 `max_tokens` 字段。
- (b) 新增向后兼容参数 `--max-tokens`（默认 4096，原为硬编码），供任务 8「放开截断」实验使用；原 `--port`（默认 8080）保留。

- 备份 `backup\stageG5\bench_harness.py.withPort`（加 `--port`、未修缺陷版，sha256 `41FBFB0A…`）；补丁后 **14,747 B、sha256 `F0685208…`**，`py_compile` 通过。
- **自检 1（失败路径）**：`--port 9`（未监听）→ `stop_reason=upstream_error`、记录文件已写、**无 Traceback**、退出码 0，detail 首轮含 `"error": "URLError: <urlopen error [WinError 10061] …>"`。
- **自检 2（正向路径）**：真跑任务 1（:8080）→ 4 轮 / 10.6 s / **验收 4 通过 0 失败**，`prompt_n=[623,74,136,111]`、`finish=['tool_calls','tool_calls','tool_calls','stop']`，→ 流式解析未受影响。
- **口径提醒**：G5 三次采样（15.1–15.6）跑在补丁前 sha256 `41FBFB0A…` 上，本补丁**不改变已记录的 G5 结果**；后续若复用历史记录须注意 harness 版本差异。自检临时目录 `bench\runs\_selftest_{fix,ok}` 已清理。

- 至此 G5 遗留的两项待验（任务 8 真实能力、任务 10 压缩边界）已具备推进条件。


## 十六、阶段 G6 任务 8 放开截断对照

**动因**：G5（第十五节）任务 8 两臂 6/6 失败，根因是 harness `max_tokens=4096` 截断，属无效对照样本。
本批**只放开 `max_tokens=8192`**，其余受控条件（同后端 pid 30160 / `--cache-ram 1024`、A 臂另起 :8082
的修复前 v2 代理 sha256 `5DAAB527…`、B 臂生产 :8080 pid 40480、同一套夹具、同 `temperature=0` /
`stream=True` / `tool_choice=auto`、同 `--max-rounds 16 --time-cap 1500`、同交替顺序）与 G5 完全一致。
窗口 2026-09-28 02:59:58 → 03:21:57，6 次 harness 调用。harness 沿用补丁后 sha256 `F0685208…`
（`--max-tokens` 为其新增的向后兼容参数，见 §15.7）。

### 16.1 结果

| 指标 | A（v2 / :8082） | B（v3 / :8080） |
|---|---:|---:|
| 成功 / 尝试 | **3 / 3（100%）** | **0 / 3（0%）** |
| 成功墙钟中位数 | 207.7 s | —（无成功样本） |
| 全部尝试总墙钟 | 623.6 s | 694.7 s |
| 工具重复调用数 | 0 | 6（各 2） |
| `pelican.svg` 存在 | 3/3 | 3/3 |
| `pelican.svg` XML 合法 | **3/3** | **0/3** |
| 记录完整率 | 6/6 | 6/6 |

### 16.2 三项关键发现

1. **G5 的截断假设被证实**：`max_tokens` 放开后，两臂轮 1 `finish` 均由 `length` 变为 **`tool_calls`**
   （均发起 `write_file`）；G5 中 A 臂三样本连 `results/pelican.svg` 都没写出，本批 A 臂 **3/3 写出合法 SVG**。
   → 任务 8 的 A 臂失败**纯由 4096 截断造成**，非能力缺口。
2. **B 臂稳定失败点是「写出的 XML 非法」，与截断无关**：3/3 失败、输出逐字节相同（47 行 / 2,468 B），
   失败项恒为 `XML 合法 <- ParseError('duplicate attribute: line 7, column 36')`。
   逐字节查看 `B-s8-*/results/pelican.svg` 第 7 行为
   `<line x1="155" y2="95" x2="235" y2="95"/>`——**`y2` 重复、`y1` 缺失**。
3. **两臂送给后端的首请求不同**：轮 1 是两臂**同一份初始消息**，可直比。轮 1 新评测 token
   A `prompt_n`=**522** / B `prompt_evaluated_tokens`=**641**，复用 token 两侧同为 109，
   即轮 1 请求总长 **A 631 / B 750（B 多 119 token）**，三次采样一致。
   → 代理层实际转发的内容不同。与 v3 登记的确定性改写相符（`tools.error_policy=true`
   「第一条 system 文本尾并入常驻策略块」；`slimming.locations`/`tools.schema_hardening`
   对 harness 自造 prompt/tools 无命中项）。**本批未做请求体逐字节 diff，机制未确认**，
   不能断言差异全部来自 `error_policy`。

### 16.3 两臂收尾行为（如实留痕，不作优劣推断）

- A 臂三次均跑满 `--max-rounds 16`（`stop=max_rounds`）、轮 1 后连续 13 次 `write_file`/`run_python`
  交替、`tool_retries=0`；**拿到有效交付物但从未自行终止**（验收只看产物故 6/6 通过）。
- B 臂 11 轮 `model_finished`（末轮 `finish=stop`、`content=890` 字，模型自述完成）；
  期间写了 `results/check.py`（**0 字节**）并 `run_python` 调用它——**自检为空操作**，
  最终把含重复属性的非法 XML 当完成品交付。→ **「自检脚本是否为空」应纳入观测量**。
- 轮 1 思考量 A 12,986 字符 / B 5,359 字符，故两臂墙钟差异主要来自轮次与思考量，**不构成代理性能对比**。

### 16.4 口径与局限

- 本批唯一受控改动是 `max_tokens` 4096 → 8192，故 **G6 与 G5 不可直接横比**；唯一有效比较是批内 A vs B。
- 每臂 3 次、仅任务 8 一项，**不能推出「v3 整体更差」**；G5 主结论（无稳定提速）**不因本批改变**。
- 6 次全部有记录、无缺失。A 臂 `config_hash` 为 **null** 属设计如此（修复前 v2 代理不写 `logs\requests.jsonl`，
  该字段本就取不到）；A 臂 token 字段按 `capture\timings.jsonl` **增量**取（16 条 = 16 轮，无一例降级）。
- §16.2 第 3 条的「代理层改写」是**候选机制**，已标注未确认。

### 16.5 生产现场未受影响

:8080 pid **40480** / :8081 pid **30160** 前后一致；前后端 `/health` 均 200；
`config\bonsai-agent.json` sha256 `A68766381AAF1E32…` **前后一致**、`extra_args` 仍为 `["--cache-ram","1024"]`；
A 臂所用 **:8082 已释放**。`baseline\g6_A_proxy_8082.log` 可查 A 臂代理日志。

**产物**：`G6 任务8 放开截断对照.md`；`baseline\g6_results.jsonl`、`g6_summary.json`、`g6_fingerprint.json`、
`g6_timings.jsonl`、`g6_A_proxy_8082.log`；`bench\results_g6.jsonl`；`bench\runs\{A,B}-s8-{1,2,3}\`。
本批**未改动生产配置、未重启任何生产进程、未新增回滚入口**（仍为 `rollback.md` R8）。

**建议**：① 不下「v3 更差」结论，把 B 臂任务 8 失败**单独立项**，先做「同一请求体分别打 :8082/:8080 +
逐字节 diff 转发内容」定位机制；② 记录 A 臂「跑满 16 轮不自终止」的异常行为；③ 任务 8
若进正式对照须固定足够大的 `max_tokens`（8192 已验证够用）并把自检脚本内容纳入观测量。

## 十七、阶段 G7 代理转发内容对照

**动因**：G6（第十六节）§16.2 第 3 条只确认「两臂转发内容不同」（B 首请求多 119 token），未做请求体 diff，
机制未确认。本批用**记录型上游桩**抓取两代理**实际转发体**，逐字段比对。
窗口 2026-09-28 04:19:31 → 04:19:33（约 2 秒，**无推理**）。

**受控**：A = 修复前 v2 代理 sha256 `5DAAB527…` 起 :8082、上游桩 :8098；B = 生产 v3 脚本 sha256
`6ACFB9C5…` 起 :8083、上游桩 :8099；B 臂用生产 `config\bonsai-agent.json`（`A6876638…`）的**副本**
（仅改 4 个输出路径字段 + `prewarm.enabled=false`，行为段逐字段一致）；请求体由 `load_harness()` 取
`bench_harness.py`（`F0685208…`）的 `MODEL`/`SYS_PROMPT`/`TASKS[8]`/`TOOLS` 构造，两臂**同一份**
（1917 B，sha256 `d32afaad…`）；两臂均 `--effort medium`。

### 17.1 结果

| 项 | A（v2 / :8082） | B（v3 / :8083） |
|---|---:|---:|
| 转发字节 | 1973 | 2563 |
| 顶层键 | 8 个 | 8 个（同） |
| `tools` vs 发出体 | 全等 | 全等 |
| `chat_template_kwargs` | `{"reasoning_effort":"medium"}` | 同 |
| `messages[0].content` 字符 | **628** | **1212** |
| 唯一实质差异 | — | system 尾部 +**584** 字符 |

### 17.2 机制确认（由推断升为实测）

- **唯一实质差异**是 `messages[0].content` 尾部追加 **584 字符**，**逐字符等于** v3 的 `TOOL_POLICY_BLOCK`
  （`tools.error_policy=true` 触发 `apply_tool_error_policy()`：带非空 `tools` + 首条 `role=="system"` +
  `content` 为 str → 追加到该 content 尾部）。
- 其余候选**全部排除**：`tools` 两臂全等（`schema_hardening` 未命中）、`slimming.locations` 无命中项、
  `chat_template_kwargs` 两臂相同（`--effort` 注入，非差异）。
- **字节对账**：B−A = 590 = 584 字符 + 6 个换行 JSON 转义；A−发出体 = 56 = `chat_template_kwargs` 键。
- → G6「B 多 119 token」的来源**实测等于该 584 字符块**（119 tok ≈ 584 字符 / 4.9 字符每 token）。

### 17.3 口径与局限

- 本批**不产生模型输出**（桩立即返回最小 SSE，约 2 秒无推理），**只证明转发内容差在哪，
  不构成能力/好坏判定**。
- **不得据此称策略块有害**：其收益场景（工具错误连续重试）本批未测，只确认它**改变了输入**。
- 单请求、每代理 1 次；B 臂配置为生产副本（行为段一致）；B 臂脚本 sha256 与生产一致。
- A 臂（v2）CAP 硬编码副作用：向生产抓包目录新增 **1 个** `small_001_041931.json`（1917 B，即发出体）；
  `capture\timings.jsonl` 行数 **905→905 未变**。

### 17.4 生产现场未受影响

:8080 pid **40480** / :8081 pid **30160** 前后一致；`/health` 均 200；config sha256 `A68766381AAF1E32…`
前后一致；`capture\timings.jsonl` **905→905**；本批端口 :8082/:8083/:8098/:8099 **均已释放**。
本批**未改生产配置、未重启生产进程、未新增回滚入口**（仍为 `rollback.md` R8）。

**产物**：`G7 代理转发内容对照.md`；`baseline\g7_diff.json`、`baseline\g7\sent_body.json`、
`baseline\g7\bodies\{A,B}\req_*.json`、`baseline\g7\g7_config.json`、`baseline\g7\{A,B}_proxy.log`。

**建议**：① G6 §16.2 第 3 条「机制待确认」**已关闭**，无需再补；② 若要判 `TOOL_POLICY_BLOCK` 对通用任务的
影响方向，另立「同代码开关 `tools.error_policy`」对照，勿在 G5/G6 数据上推断；③ 记 A 臂 CAP 硬编码会向
生产抓包目录落 `small_*.json` 的副作用。

## 十八、阶段 G8 error_policy 开关对照

**动因**：G7（第十七节 §17.1~17.4）确认 v3 相对 v2 的**唯一转发差异**是 `tools.error_policy=true` 触发的
**584 字符常驻策略块**（`TOOL_POLICY_BLOCK`），但明确该结论**只证明转发差在哪，不构成能力/好坏判定**，
并建议「另立同代码开关对照」。本批即该对照。
主批窗口 2026-09-28 04:30:39 → 04:54:06；补批 04:56 → 04:58。

**受控**：**两臂同一份** v3 脚本 `proxy\bonsai_proxy.py` sha256 `6ACFB9C5…`（与生产一致）；
P 臂 `tools.error_policy=true` 起 **:8084**、Q 臂 `=false` 起 **:8085**；上游共用生产 `llama-server` **:8081**
（pid 30160，`--cache-ram 1024`，未重启未改参）。配置为生产 `config\bonsai-agent.json`（`A6876638…`）的**副本**，
仅改 4 个输出路径字段 + `prewarm.enabled=false`；驱动脚本自证 P `tools` 差异键 **[]**、Q **['error_policy']**、
两臂 `behavior 段一致=True`。配置副本 sha256 P `A622C886…` / Q `09F1D35B…`。
任务 **8/3/6/11**，各 **2 轮**，交替顺序；`temperature=0.0`、`--max-tokens 8192`、`--max-rounds 16`、`--time-cap 1500`。
生产现场全程未动。

### 18.1 结果

| 臂 | `error_policy` | 通过/失败 | 成功率 | 任务 8 | 任务 3 | 任务 6 | 任务 11 | `policy_block_seen` | 任务 8 SVG 合法 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P | true（=生产） | 4 / 4 | 0.50 | **0/2** | 2/2 | 2/2 | 0/2（主批无效，见 18.3） | **8/8** | **0/2** |
| Q | false | 6 / 2 | 0.75 | **2/2** | 2/2 | 2/2 | 0/2（同上） | **0/8** | **2/2** |

任务 8 逐轮：P 两轮均 `2通过/1失败`、墙钟 232.6s / 230.4s、**11 轮**、`model_finished`、工具重复 2、
产物 **47 行 / 2468 B / XML 非法**（`ParseError('duplicate attribute: line 7, column 36')`，第 7 行
`<line x1="155" y2="95" x2="235" y2="95"/>` 缺 `y1` 重复 `y2`）、`<animate>` 3；
Q 两轮均 **`6通过/0失败`**、209.1s / 207.6s、**16 轮**、`max_rounds`、工具重复 0、
产物 **58 行 / 3017 B / XML 合法**、`<animate>` 4。
**逐字节确定性**：P 两轮 sha256 `54B16F11…`（2468 B）相同；Q 两轮 `D8B1089F…`（3017 B）相同。

控制项任务 3、6：两臂**均满分**（t3 5/0、t6 5/0，逐轮一致）；差异仅在过程指标——P 任务 3 为 15 轮 /
工具重复 8，Q 为 9 轮 / 0。任务 11 主批两臂同构失败（`got=None`），系驱动缺陷。

### 18.2 与 G6 逐字节对齐 → 归因由「实测」升为**因果确认**

| 来源 | 生效 `error_policy` | 行数 | 字节 | sha256 | 对齐 |
|---|---|---:|---:|---|---|
| G6 A-s8-1/2/3（v2） | 无此开关 | 58 | 3017 | `D8B1089F…` | **≡ G8-Q** |
| G6 B-s8-1/2/3（v3） | true | 47 | 2468 | `54B16F11…` | **≡ G8-P** |
| G8 Q-t8-1/2 | false | 58 | 3017 | `D8B1089F…` | — |
| G8 P-t8-1/2 | true | 47 | 2468 | `54B16F11…` | — |

→ 任务 8 的「v2 合法 / v3 非法」差异**由 `tools.error_policy` 单独决定**；v3 其余改动**不导致**该失败。
G7 的「唯一转发差异 = 584 字符策略块」由此闭合为**开关级因果证据**（G6 §16.2 第 3 条遗留项关闭）。

### 18.3 任务 11 主批无效（驱动缺陷，如实记录）+ 补充批

主批任务 11 两臂**同构失败**（P 1通过/1失败、Q 1通过/1失败），失败项均为「预置统计结果未被重写（哈希一致）」
`want=ce3f1fca8433 got=None`。**归因**：G8 驱动 `setup_run()` **未**按 `run_all.prep()` 规格
（`run_all.py` 第 23–28 行）预置 `results/sales.json` —— **驱动脚本缺陷，与 `error_policy` 无关**，
主批任务 11 **不作为对照证据**。

**补充批**（`.stage\g8_t11_fix.py`，复用 `g8_run.py` 同行逻辑，仅在任务 11 run 目录预置
`results/sales.json`，目录名加 `b` 后缀，不覆盖主批现场）：
预置口径自证 `expected=ce3f1fca8433 got=ce3f1fca8433 匹配=True`；
P-t11b-1/2 **2/0 · 2/0**（17.1s / 16.9s，7 轮）、Q-t11b-1/2 **2/0 · 2/0**（17.2s / 17.3s，7 轮），
两臂**预置均未被改写**（canonical sha256 `ce3f1fca8433…` 未变）→ **任务 11 两臂无差异**。

### 18.4 口径与局限

- `temperature=0.0`，每任务每臂 **2 轮**，两臂各自两轮**逐字节相同**（确定性可复现）；
  但 **n=2、任务仅 4 项**，**不得**把任务 8 的方向性差异外推为「策略块在所有任务上有害」。
- **影响任务相关**：仅任务 8（单文件图形生成）为负向；任务 3、6、11 两臂均满分、无能力差异。
- **不测收益**：策略块面向「工具错误连续重试」，本批固定任务**未触发**该场景，
  故**不评估其收益**，**不能**据此判定「应删除 `error_policy`」。
- **token 口径**：取**各臂自身** `logs/requests.jsonl` 增量（`token_source` 已记录）；
  harness `proxy_records` 恒 0（`bench_harness.py` 的 `PROXY_LOG` 硬编码生产路径），仅留痕、非数据来源。
- 过程指标异常留痕（**不作结论**）：P 任务 3 为 15 轮 / 工具重复 8，Q 为 9 轮 / 0 —— 方向与
  `TOOL_POLICY_BLOCK` 第 1 条设计意图相反，但 n=2 且仅 1 项任务。

### 18.5 生产现场未受影响

:8080 pid **40480** / :8081 pid **30160** 前后一致；`/health` 均 200；config sha256 `A6876638…`
前后一致；`proxy\bonsai_proxy.py` `6ACFB9C5…`、`bench_harness.py` `F0685208…`、`check_tasks.py`
`AE549CA3…` 均未变；`capture\timings.jsonl` **905→905（未变）**；`logs\requests.jsonl` **656→667（+11）**，
行号 657–667 逐行核查**全部**为探针（`/health` 6 条 + `/v1/models` 5 条，`config_hash=0b0d2806eb9a…`），
**`/chat/completions` 0 条** → 生产未发生推理、无污染；本批端口 :8084 / :8085 **均已释放**。
本批**未改生产配置、未重启生产进程、未新增回滚入口**（仍为 `rollback.md` R8）。

**产物**：`G8 error_policy 开关对照.md`；`baseline\g8_fingerprint.json`、`baseline\g8_summary.json`、
`baseline\g8_results.jsonl`、`baseline\g8_P_config.json` / `g8_Q_config.json`、
`baseline\g8_t11fix_summary.json`、`bench\results_g8.jsonl` / `results_g8_t11fix.jsonl`、`bench\runs\{P,Q}-t*`。

**建议**：① 任务 8 结论为**开关级因果**，但**不得**推广为全局有害、**不得**据此改生产；
② 若要落地「关闭 `error_policy`」，须先补「工具错误重试」场景对照确认收益、并在多任务多样本上确认无回归；
③ 任务 10（压缩边界五轮）仍缺驱动；④ A 臂（v2）CAP 硬编码落 `small_*.json` 于生产抓包目录的副作用仍未处理。

## 十九、阶段 G9 `error_policy` 全任务确认

**目的**：把 G8 的「单/少数任务」结论扩到**全任务集**，回答 ① 关闭 `tools.error_policy` 能否**仍**消除任务 8 失败；
② 关闭它是否让其它任务**回归**。（G8 报告 §十 · 建议②）

**设计**：两臂**同一份 v3 脚本**（`proxy\bonsai_proxy.py` sha256 `6ACFB9C5…`），仅配置副本
`tools.error_policy` 一个布尔量不同；各自独立代理 **:8084(P=true) / :8085(Q=false)** → 共用生产后端 :8081。
任务集**照抄 G5**：`1,3,4,5,6,7,8,9,12,11,2`（11 项；任务 10 需 `bench_multiturn.py` 专用驱动，不在本批）；
每臂每任务 **2 轮**、交替顺序；`--max-tokens 8192`、`--max-rounds 16`、`--time-cap 1500`、`temperature=0`。
夹具照抄 G5，**任务 11 按 `run_all.prep()` 预置 `results/sales.json`**（修 G8 主批的驱动缺陷）。
窗口 05:37:27 → 06:13:55（约 36.5 min）。

**自证**：P `tools` 差异键 `[]`、Q `['error_policy']`；两臂 `behavior 段一致=True`；
P `policy_block_seen=22/22`、Q `=0/22`；配置副本 sha256 P `11D15451…`、Q `002BBB4D…`。

**结果**

| 臂 | `error_policy` | 样本 | 通过/失败 | 成功率 | 失败任务 | 工具重复合计 |
|---|---|---:|---:|---:|---|---:|
| P | true（=生产） | 22 | 18 / 4 | 0.818 | 任务 8（0/2）、任务 12（0/2） | 20 |
| Q | false | 22 | **22 / 0** | **1.000** | 无 | **0** |

- **任务 8 复现**：P 0/2（47 行 / 2468 B / XML 非法 / `ParseError('duplicate attribute: line 7, column 36')`）、
  Q 2/2（58 行 / 3017 B / 合法）；P 两轮 sha256 `54B16F11…` 相同、Q 两轮 `D8B1089F…` 相同；
  且 `G9-P ≡ G8-P ≡ G6-B(v3)`、`G9-Q ≡ G8-Q ≡ G6-A(v2)` **逐字节相同**。
- **任务 12 新增（本批首次覆盖）**：P **0/2**（4/1，失败项「含两个错误 E137 / E811」；
  P 的 `summary.md` 实写「总行数 622 / ERROR 1」而事实为「1000 行 / ERROR 2」，**漏 `E811`**）、
  Q **2/2**（5/0，正确写出 137 与 811）。→ 任务 12 的结果**同样由该开关决定**。
- **无回归**：9/11 项任务两臂通过/失败一致；未发现任何"关闭后变差"的任务。
- **产物层**：7 项任务（1/3/4/6/7/9/11）两臂均通过但产物内容不同（策略块改变模型输出，未表现为检查失败）；
  仅任务 5、2 两臂产物逐字节相同。
- **过程指标（留痕，不作结论）**：任务 3 P 15 轮 / 重复 8（108.9·108.3 s），Q 9 轮 / 重复 0（64.5·64.1 s），
  与 G8 同向复现。
- **任务 11**：两臂均 2/2，预置 canonical sha256 `ce3f1fca8433…` 未变。

**须修正的既往记录**：G5「任务 12 恒失败（能力缺口）」基于 `--max-tokens 4096`；本批 8192 下 Q 臂 2/2 通过，
该结论在 8192 下**不再成立**。4096 下两臂皆失败是否由截断造成（G5 的 A 臂为 v2、无策略块，故其失败不可能来自策略块）
**本批未复测，不列为确认结论**。

**生产复验**：:8080 pid 40480 / :8081 pid 30160 未变、`/health` 200/200、config sha256 `A6876638…` 未变、
`capture\timings.jsonl` 905→905、`logs\requests.jsonl` 676→689（+13，全为 `/health`×3 与 `/v1/models`×10 探针，
**0 条 `/chat/completions`**）、:8084/:8085 已释放；未改生产配置、未重启生产进程。

**局限**：n=2 且 `temperature=0`（臂内逐字节复现 = 确定性复现，非随机抽样，不做概率外推）；
任务 12 失败机理未分析；任务 10 不在本批；策略块的**设计收益场景（工具错误连续重试）未触发**。

**建议**：① 将 `tools.error_policy=false` 列为**生产候选**，但**不立即改生产**；② 先补「工具错误重试」
场景对照以验证策略块收益，否则等于在未测收益前删除功能；③ 任务 8 的 SVG 合法性问题已有 G6/G8/G9 三批一致证据。

**产物**：`G9 error_policy 全任务确认.md`；`baseline\g9_summary.json` / `g9_fingerprint.json` /
`g9_results.jsonl` / `g9_P_config.json` / `g9_Q_config.json`；`bench\results_g9.jsonl`；`bench\runs\{P,Q}-t*-{1,2}\`。


---

## 二十、阶段 G10 收益对照（专用驱动）

**目的**：G8/G9 只证明了「关掉 `tools.error_policy` 无回归」，**没有**证明「开着它有收益」——
标准 harness 的 system prompt **自带同义策略**、且重复调用时注入 `[local runtime] … SAME call`，
把块的**设计场景**遮蔽了。G10 用**专用驱动**拆掉遮蔽，做 **2×2** 因子对照。

**设计**

| 因子 | 取值 |
|---|---|
| 驱动侧（`.stage\g10_run.py`） | **N**＝system prompt 不含任何错误恢复策略、不注入 SAME-call 提示（283 字符）；**L**＝含 harness 策略段 + 注入 SAME-call 提示（628 字符） |
| 代理侧（同一份 v3，sha256 `6ACFB9C5…`） | **P**＝`tools.error_policy=true`（:8084，配置 sha256 `CA12C25D…`）；**Q**＝`false`（:8085，`72F51043…`） |
| 探针（首次调用必失败、错误稳定、任务文本中性） | `locked`（`run_python` 必 `exit 1`，`E_LOCKED`）、`boom`（必抛异常，`E_PARSE`）、`absent`（`read_file` 不存在路径，任务不可达） |
| 规模 | 4 单元 × 3 探针 × 2 轮 = **24 run**，全部完成，无缺失 |
| 后端 | 两臂共用生产 `llama-server` **:8081**（pid 30160），未重启改参；生产 :8080/:8081 全程未动 |

**结果**（`baseline\g10_summary.json`）

| 单元 | 探针 | 轮数(1,2) | 同调用重复(1,2) | 停止(1,2) | 最终回答 |
|---|---|---|---|---|---|
| N+P | locked / boom | 4·4 / 4·4 | 0·0 / 0·0 | model_finished ×2 | 正确报告 |
| N+P | **absent** | **7·12** | **2·6** | **model_finished ×2** | **2/2 给出**（说明文件不存在、无法原样写入） |
| N+Q | locked / boom | 4·4 / 4·4 | 0·0 / 0·0 | model_finished ×2 | 正确报告 |
| N+Q | **absent** | **12·12** | **6·7** | **max_rounds ×2** | **0/2**（final 为空） |
| L+P | locked / boom / absent | 4·4 / 4·4 / 12·12 | 0·0 / 0·0 / 5·5 | mf / mf / **max_rounds ×2** | absent 无 |
| L+Q | locked / boom / absent | 4·4 / 4·4 / 12·12 | 0·0 / 0·0 / 5·5 | mf / mf / **max_rounds ×2** | absent 无 |

**三条结论**

1. **块的独立收益：首次观测到正向，但不足以定量**——N 单元 `absent`：开块 **2/2 收敛并报告阻塞原因**，
   关块 **0/2（撞满 12 轮上限、无最终回答）**。
2. **客户端已自带同义策略时块冗余**——L 单元上 P/Q 的轮数、重复、调用序列、停止原因**完全相同**（4 run 逐轮一致）。
3. **`locked`/`boom` 不构成块的设计场景**——全 4 单元 4 轮、`same_call_repeats` 恒 0、报告正确，块无行为差异（仅措辞）。

**反证（必须保留）**：N+P 样本 2 中 `read_file probe/absent.txt` 被**逐字重复 3 次**（同一错误），
已满足块规则 1，模型仍重发相同调用 → 块的收益**不能由规则 1 解释，机理未定位**。
另：`absent` 的主导循环是 `list_dir|{"path":"."}`（返回**成功**的空列表，非错误），
块按定义不该介入；L 单元的本地策略同样 **4/4 未阻止循环**，其收益本批亦未证实。

**生产建议（不改生产）**：保留 `error_policy=true`（删除依据仍不足）；
仅当确认「生产客户端自身已具备等价错误恢复」时，关闭它才有冗余性依据。
真实 WorkBuddy 客户端的重试行为**本批未验证**。

**局限**：n=2；N+P 的 `absent` 两轮不同（7 vs 12 轮）→ 存在轮间方差，第 1 条仅为**方向性观测**；
专用驱动口径**不可与 G8/G9 相加**；`boom` 报告哈希因内嵌绝对路径而不可逐字节比较（路径伪影）。

**生产复验**：:8080 pid 40480 / :8081 pid 30160 未变、`/health` 200/200、config sha256 `A6876638…` 未变、
`capture\timings.jsonl` 905→905、`logs\requests.jsonl` 695→699（+4 全为探针，**0 条 `/chat/completions`**）、
:8084/:8085 已释放。

**产物**：`G10 error_policy 收益对照（专用驱动）.md`；`baseline\g10_*`；`bench\results_g10.jsonl`；`baseline\g10\runs\*`。

## 二十一、阶段 G11/G12/G12b 任务10 压缩边界五轮补测（专用驱动）

方案 §14.2 第 10 项「同时做普通五轮和压缩边界五轮」长期记为未实现（`§10.3`：标准 harness 无任务 10 定义，
本地无做历史压缩的客户端）。本阶段用专用驱动补齐，并顺带查出代理侧一个缺陷候选。

**口径（来源可查）**：压缩阈值 = `65536 − 8192 − 1024` = **56,320 token**（= 代理 `check_input_budget()`
判「超预算」界线）；后端硬上限 = `n_ctx` **65,536**；边界带 (56,320, 61,440)。
便宜路径跳过精确计数的条件 = `body_bytes/3.0 + 9216 ≤ 65536` ⇔ `body_bytes ≤ 168,960`。

**G11（S/N/C 三档，`.stage\g11_run.py`，:8084 → :8081）**：标定 K=8 / K5=8 → 57,598 token（目标 57,520，带内）。
- S 短上下文（普通五轮）：输入 2,085→8,565，交付 791 字符，五条约束全列。
- N 边界穿越（不压缩）：输入 11,188 / 22,543 / 34,095 / 45,696 / **57,373**，交付 985 字符，五条约束全列。
- C 边界穿越（+§E2）：**未压缩**（驱动缺陷 P1，见下），数值与 N 相同。
- 三档 `source.txt` 未变；均 `stop=max_rounds`。
- **首个关键证据**：N 档第 5 轮实际输入 57,373 > 阈值 56,320，闸门却报「在预算内(便宜路径)」，
  `est_upper=39,590`，**低估 31.0%**。

**G11 暴露的问题（如实记录）**：
- **P1 驱动缺陷**：C 档触发条件依赖代理 `budget_check.input_tokens`，便宜路径下恒为 `null`
  （后端 `usage` 亦未返回）→ 投影恒为 0 → 永不压缩，C 档等同 N 档。
- **P2 驱动缺陷**：响应返回后立即读转发日志，偶发读不到本请求记录（C 轮 1 `record_seen=false`）。
- **F1 代理缺陷候选**：见下。

**G12（C2 档：边界五轮 + §E2 压缩，`.stage\g12_run.py`）**：触发改为**自测精确投影**
（`/apply-template`+`/tokenize`）。第 5 轮前投影 **57,292 > 56,320** → 按 §E2 把前 4 轮原始切片正文替换为
「切片路径 + 行号 + 原文 sha256 + 该轮模型摘要」（20,185→149 / 20,933→536 / 20,933→599 / 20,933→682 字符），
投影 **57,292 → 14,405**，**显式削减 42,887 token**。第 5 轮自测 14,405 vs 后端实际处理 **14,486**
→ 后端 ≥ 自测，**无静默裁剪**。交付 `results\final-summary.md` 1,469 字符，**最初五条约束全列**，
工具配对 `2/2`，`source.txt` 未变。P1/P2 均修复。

**G12b（闸门探针对照，`.stage\g12b_probe.py`）**：同代理、同后端、单请求、`max_tokens=64`，
两探针都标定到 ≈57,000 token，**只改字符/token 密度**：
- `P-dense`（日志切片重复，1.85 字符/token，body 127,199 B）→ `est_upper=42,399`，
  闸门「**在预算内(便宜路径)**」，而实际处理 **62,831 > 阈值 56,320** → **假阴性**。
- `P-sparse`（英文语段重复，5.83 字符/token，body 335,521 B）→ 走精确计数，判「**超预算**」
  （`input_tokens=57,196`、`required=66,412`、`headroom=−876`）→ 正确发现。
- 两次运行（偏差轮 + 隔离轮）结论完全一致（n=2）。

**执行偏差（如实披露）**：G12b 初版脚本漏写 `H.PORT`，两探针落到**生产 :8080**，产生 2 条真实
`/v1/chat/completions`（生产 `logs\requests.jsonl` 第 724 行 `f7084c8a67d743a3` 62,831 token / 113.4 s；
第 726 行 `d19422826fd24f83` 57,196 token / 88.5 s）。后端 `-np 1` 单槽位，上述 ~3.4 分钟占用推理槽；
同期生产日志**无任何生产侧 `/chat/completions`**（增量仅 `/v1/models` 轮询），未挤掉业务请求；
`client_disconnected=false`；未改配置/未重启进程。已修 `H.PORT` 并加「生产增量须 0 条 `/chat/completions`」守卫，
隔离重跑确认生产增量 0 条。

**缺陷候选 F1（便宜路径上界失效，待决策，本轮未改生产）**：
便宜路径以 `tokens ≤ body_bytes/3.0` 为上界，前提是素材 ≥ 3 字节/token；日志类素材实测 ≈1.87 字节/token，
前提不成立 → 低估。判据：便宜路径被采用 ⇔ `body_bytes ≤ 168,960`，故
**存在假阴性 ⟺ `56,320·d < 168,960` ⟺ `d < 3.0` 字节/token**。
`d=1.87` 时假阴性区间 token ∈ (56,320, **90,353**]，而 90,353 > 硬上限 65,536
→ **该类素材即使超过后端硬上限也永不被告警**。故 §E 验收「超预算能在生成前被发现」**仅对 `d ≥ 3.0` 成立**。
精确计数耗时实测 125 ms/次，成本可接受；**建议**把 `chars_per_token_floor` 下调到真实下界（如 1.5），
或对关键路径强制精确计数。

**验收对照**：§14.2 第10项 ✅；§E2 四项 ✅；§E「压缩后不丢 / 无静默裁剪」✅；
§E「超预算能在生成前被发现」⚠️ 部分成立（→ F1）。专用驱动口径，**不可**与 G5/G9 成功率相加。

**产物**：报告 `G11 G12 任务10 压缩边界五轮补测（专用驱动）.md`；
`baseline\g11_summary.json`、`g11_fingerprint.json`、`g12_summary.json`、`g12_fingerprint.json`、
`g12b_summary.json`、`g12b_fingerprint.json`；`bench\results_g11.jsonl`、`results_g12.jsonl`、`results_g12b.jsonl`；
`baseline\g12\runs\C2\results\final-summary.md`；切片 `baseline\g11\slices\`（含 MANIFEST）。

## 二十二、阶段 G13 预算闸门 mode warn vs reject 行为对照

承接 G11/G12/G12b：那片确认了 F1（便宜路径在 token 密集素材上低估），并停在「warn 不阻断，实际风险取决于是否切 reject」。
本批用**同一超预算输入**做 warn / reject 单因子对照，把两种模式的差异量化，并厘清与 F1 的关系。

**受控**：`.stage\g13_warn_reject.py`；生产 v3 代理 :8084 → :8081；两份配置副本仅 `budget.gate.mode` 不同
（warn 档 = 生产配置、budget 与源逐键完全一致；reject 档 = 同副本 + `gate.mode="reject"`，隔离自证仅放行该子键差）。
每档 2 探针：`in`（预算内 655 token）、`over`（超预算 **57,570 token**，`max_tokens=64`）。

**warn 档（= 生产现状）**：`over` 闸门**正确判出超预算**（精确，`required 66,786 / headroom −1,250`）——
但按配置**仍转发**：后端实际处理 57,570 token、冷 prefill **101.7 s**、占满单槽 ~106 s、返回 200（`finish=length` 截断）。
warn 的「超预算」在日志里看得见，但**不构成保护**。

**reject 档**：同一 57,570 token → **生成前 400**（`input_over_budget`）：`record_wall_ms=109`（仅闸门精确计数）、
`prefill_ms=None`、`processed=None`、`server_busy_at_start` 缺失 → **不经队列、不占槽**；返回结构化 `budget` 错误体
（`required`/`headroom`/`window`/`input_pct_of_window=87.84`）。`in` 探针 200 → **不误杀预算内请求**。

**核心结论**：
- `reject` 把 warn 模式空耗的 ~106 s 冷 prefill + 单槽占用，压成 ~0.1 s 的 400；安全性来自「占槽前判定并拒绝」。
- **reject 与 floor 修复正交、缺一不可**：reject 只堵「闸门正确判出超预算」这一路；F1 覆盖的便宜路径低估素材
  （`d<3.0`，`act=pass`）**即使切 reject 也不会触发**，仍需调 `chars_per_token_floor`（如 1.5）或对关键路径强制精确计数。

**生产复验**：前后 :8080 pid 40480 / :8081 pid 30160、`/health` 双 200、config sha256 `A6876638…` 一致；
实验窗口生产 `0 条 /chat/completions`；:8084 结束后释放。**生产未改**（仍 `mode=warn`）。

**产物**：报告 `G13 预算闸门 warn vs reject 对照.md`；`baseline\g13_summary.json`、`g13_fingerprint.json`、
`bench\results_g13.jsonl`、`baseline\g13\{warn,reject}\config.json`。

## 二十三、阶段 G14 生产切 reject 与 F1 修复（chars_per_token_floor 3.0 → 1.5）

在 G13（reject 生成前 400、与 floor 修复正交）之后，本阶段把两件事**一次落到生产配置**并重启代理生效：

- **F1 修复**：`budget.gate.chars_per_token_floor` `3.0 → 1.5`（便宜路径上界采真实下界，仅在按最坏密度也不超预算时才跳过精确计数）。
- **切生产 reject**：`budget.gate.mode` `warn → reject`（超预算生成前 400，不占槽、不消耗 GPU）。

**执行**：G14 步1（`.stage\g14_edit_config.py`）只改配置并备份到 `backup\stageG14\bonsai-agent.json.preG14-reject`
（旧 sha `a6876638…`，回滚源）；G14 步2（`.stage\g14_apply_proxy.py`）核对 :8080 身份（cmdline 含 `bonsai_proxy.py`/`--port 8080`，
pid 40480）→ 受控 `/F` 停止（正常退失败）→ 等价命令 DETACHED 启动新代理（pid **55872**）→ :8080 `/health` 就绪；后端 :8081 pid 30160 未动。
新配置 sha256 `f09a77be63c09dbe`。

**验收（`acceptance_ok=True`）**：
- `probe-dense`（G12b 同款 F1 假阴性素材，body 127,199 B，`d≈1.87` 字节/token）→ **400** `input_over_budget`：
  `mode=reject`、`method=exact`、`input_tokens=62249`、`required=71465`、`headroom=−5929`、`est_upper_tokens=84181`、
  `input_pct_of_window=94.98`、`elapsed_ms=62`、wall 0.08 s。旧配置(floor 3.0)下该素材被判「在预算内(便宜路径)」→ 200（G12b 未告警），
  **floor 1.5 使其转精确 → 判超预算 → reject 400，一举证明两修复串联生效**。
- `probe-small`（预算内小消息）→ **200**（reject 不误杀）。

**生产复验**：:8080 pid 40480→55872、:8081 pid 30160、`/health` 双 200、config sha `f09a77be…` == new_config_sha；
增量 reqlog +5、`/chat/completions` +2（含 `probe-dense`(被拒) 与 `probe-small`，均属授权验收）、timings +1（仅 `probe-small`）。

**归档**：报告 `G14 生产切 reject 与 F1 修复.md`；`baseline\g14_apply.json`；备份 `backup\stageG14\bonsai-agent.json.preG14-reject`。

## 二十四、阶段 G15 代理 400 观测日志（客户端真实行为埋点）

G14 生产已切 reject 后，为回答「WorkBuddy/Pi 收到 400 是直接报错还是自动重试、几次能成功」，
在代理 reject 分支埋**纯观测日志**（不侵入业务）：`client_mark(headers)` 提取候选请求头作客户端指纹
（UA / Authorization 前缀 / X-Stainless-* / X-*）；reject 记录经 `rec["client_mark"]` 随 `logs\requests.jsonl` 落盘；
`_send_json(400)` 后用 `client_gone_peek(grace_s=0.1)` 探连接并 `print` 一行 `[400观测]`（rid/model/stream/client/input_tokens/type/conn）。

应用：代理 pid 55872→**73972**（sh 身份核对后 `/F`，后 DETACHED 启动），:8080 `/health` 就绪，:8081 pid 30160 不动，
config sha `f09a77be…` 不变。验收 `acceptance_ok=True`：dense 400、small 200、`client_mark` 落 `{"ua":"Python-urllib/3.10"}`、
proxy.log 出现 `[400观测]`。新代理代码 sha `d2a1f82f…`，旧代码备份 `backup\stageG15\bonsai_proxy.py.preG15-400log`（旧 sha `6acfb9c5…`）。

**观测期 1–2 天**：数据源 = `logs\requests.jsonl` 的 `error_type=input_over_budget` 记录 + `logs\proxy.log` 的 `[400观测]` 行；
按客户端+每条400后时间窗聚合判断重试次数与最终成败。据此再决定是否加客户端智能降级（400 自动截断重试 / 精简请求）。
## 二十五、阶段 G14/G15 使用手册落盘

在接受 G14（生产切 reject + floor 1.5）与 G15（400 观测埋点）并按用户「现在可以直接使用了吗 / 最推荐在哪里使用 / 使用方法 / 操作说明」整理后，
将可交付使用说明落为文档：`optimization\20260927_165311\使用手册.md`。

内容与要点：
- 服务可用状态：代理 :8080 / 后端 :8081 双 200。
- 推荐入口：连代理 :8080（base_url `http://127.0.0.1:8080/v1`，model `bonsai-2-27b`），勿直连后端 :8081（会绕过瘦身/预算闸门/观测）。
- 快速验证（/health、/v1/chat/completions）、请求参数要点（stream/temperature/max_tokens）。
- 长文本预算：reject 语义，超 56,320 token 返回 400，多轮/长文建议精简或拆分。
- 运维命令（launcher up/status/stop/show-config）与日志路径（proxy.log / requests.jsonl / timings.jsonl）。
- G15 400 观测 + 每日 09:00 聚合（g15_aggregate.py：--since / --days）。
- 回滚方法（G14 旧配置 preG14-reject、G15 旧代理代码 preG15-400log）。
- 局限与后续（单槽串行、客户端是否自愈重试待观测）。

产物：使用手册 4,523 B，sha256 `078303dc19ce4387`（CRLF）。
