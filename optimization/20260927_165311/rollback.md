# 回滚入口 — Bonsai 本地模型通用优化

工作目录: D:\Bonsai-demo\optimization\20260927_165311

## 铁律
- 停止服务只按“启动管理器记录并核对过的 PID”操作；禁止按端口盲杀（netstat 扫端口 -> taskkill）。
- 不得对仓库执行 reset / stash / checkout / clean：存在 175 处其他 agent 的未提交改动。
- 任何阶段失败：先停手，保留日志，按本文件对应条目回滚，再报告。

## 备份清单
optimization\20260927_165311\backup\MANIFEST.csv，含：
  dist\bonsai2-8gb-combo\start_all_agent.bat
  dist\bonsai2-8gb-combo\start_bonsai_8gb_agent.bat
  dist\bonsai2-8gb-combo\start-bonsai.ps1
  dist\bonsai2-8gb-combo\warm_kv.bat
  dist\bonsai2-8gb-combo\start_capture.bat
  proxy\bonsai_proxy.py
  warm_kv.py
  serve.py
  capture\effort.txt

## R0 阶段 A 回滚
阶段 A 未修改任何生产文件，无需回滚。

## R1 还原 start_all_agent.bat（撤销既有的 KILLPORT 修复）
Copy-Item -LiteralPath 'optimization\20260927_160739\backup\start_all_agent.bat' -Destination 'dist\bonsai2-8gb-combo\start_all_agent.bat' -Force
  备份 = 修复前原件，4850 字节，SHA256 39E14BEE8F2A56BB6C75BE6667B45937C3E1011371BBA86B4B59E4B0164306B2

## R2+（阶段 B–H 的还原指令，逐条追加）
格式：目标文件 / 备份来源 / 校验 SHA256 / 还原命令

## R2 阶段 B 回滚（统一配置 -> 恢复原来的多套启动器）
本阶段专属备份: optimization\20260927_165311\backup\stageB\（含 MANIFEST.csv，逐文件 SHA256）

一键还原 8 个被改写的文件（GBK 的 .bat 必须原样复制，不要用文本工具改写编码）:

$BD = 'D:\Bonsai-demo\optimization\20260927_165311\backup\stageB'
$map = @{
 'dist__bonsai2-8gb-combo__start_all_agent.bat'       = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_all_agent.bat'
 'dist__bonsai2-8gb-combo__start_bonsai_8gb_agent.bat' = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_bonsai_8gb_agent.bat'
 'dist__bonsai2-8gb-combo__start-bonsai.ps1'           = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\start-bonsai.ps1'
 'dist__bonsai2-8gb-combo__warm_kv.bat'                = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\warm_kv.bat'
 'dist__bonsai2-8gb-combo__start_capture.bat'          = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_capture.bat'
 'serve.py'                                            = 'D:\Bonsai-demo\serve.py'
 'warm_kv.py'                                          = 'D:\Bonsai-demo\warm_kv.py'
 '_restart_stack.py'                                   = 'D:\Bonsai-demo\_restart_stack.py'
}
foreach($k in $map.Keys){ Copy-Item -LiteralPath (Join-Path $BD $k) -Destination $map[$k] -Force }

回滚后校验（SHA256 必须与 backup\stageB\MANIFEST.csv 的 sha256 列一致）:
  Get-FileHash -LiteralPath 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_all_agent.bat' -Algorithm SHA256

新增文件（回滚时可保留；不属于生产依赖，删掉也不影响旧启动方式）:
  D:\Bonsai-demo\config\bonsai-agent.json
  D:\Bonsai-demo\launcher\bonsai_launcher.py
  D:\Bonsai-demo\state\launcher_state.json     （运行态 PID 记录）
  D:\Bonsai-demo\logs\                          （后端/代理日志目录）

旧入口的 SHA256（回滚后应恢复成这些值）:
  start_all_agent.bat          22EA602F2E638CC654B3FCF88E64CE359C2D988163EC14810C4B27D4E0B41C8E
  start_bonsai_8gb_agent.bat   4E59A0DBEAD36144D3C71C3C86A35D33D4401738E2199C2AF9FFA28648981D31
  start-bonsai.ps1             408EB10CCE70247416B9391C72A0C6211EE17D2265709B0AED9F4DAC0E3B67E3
  warm_kv.bat                  DF2BD6B7128BE586430CEEF332BB61E74153BE0B83DBC04F41A83A9F0782E4E1
  start_capture.bat            534A45B16E15378C43607243D12AECC5640B1ECE699CC879C1B77851D432037A
  serve.py                     129E1C1928B8577116CC554D4817FF40D24FC269391912B2029DD968EA37DF5B
  warm_kv.py                   E0B9BDAAD46241492CCA8D4FE6D81BFAA900B55F5A2EFF26BEFBC5A138062AE5
  _restart_stack.py            83465DDDE7AC025ECB495CD716D0AD234E53237D5C409A1D2DA6C24E884610C2

注意: 本阶段未改 GPU 锁频/驱动/BIOS/VBS/电源/系统代理，未改模型权重与推理内核；
      回滚不需要重启服务（这些文件只在下次启动时生效；当前在线进程仍按旧参数运行）。
## R3 阶段 C 回滚（代理 v3 -> 恢复旧代理 v2 与旧配置/launcher）

本阶段专属备份: optimization\20260927_165311\backup\stageC\（含 SHA256.txt）
旧代理 v2 备份: optimization\20260927_165311\backup\proxy__bonsai_proxy.py
  （与部署前在线文件字节一致，SHA256 5DAAB52777768428…，24,086 字节）

备份清单与校验:
  backup\stageC\bonsai_launcher.py.v2   SHA256 B31A2555C705E921602251AB227A05AFE96EDC049AE2E6DA6D665EB27498E288
  backup\stageC\bonsai-agent.json.v2    SHA256 5750751F9A7CC85A759BB1ABCFF2A257B90B532D6D4462B60E7528DE25376729
  backup\stageC\stage_b_tests.py.v2     SHA256 3F531008C4F95462AF5CCB35EEBBEA12C5B6CE87A5EE9E9E158E05020F799101
  backup\proxy__bonsai_proxy.py         SHA256 5DAAB52777768428(见 MANIFEST.csv 全值)

一键还原（代理 + launcher + 配置 + 阶段 B 测试夹具）:

$SC = 'D:\Bonsai-demo\optimization\20260927_165311\backup\stageC'
Copy-Item -LiteralPath 'D:\Bonsai-demo\optimization\20260927_165311\backup\proxy__bonsai_proxy.py' -Destination 'D:\Bonsai-demo\proxy\bonsai_proxy.py' -Force
Copy-Item -LiteralPath (Join-Path $SC 'bonsai_launcher.py.v2') -Destination 'D:\Bonsai-demo\launcher\bonsai_launcher.py' -Force
Copy-Item -LiteralPath (Join-Path $SC 'bonsai-agent.json.v2')  -Destination 'D:\Bonsai-demo\config\bonsai-agent.json' -Force
Copy-Item -LiteralPath (Join-Path $SC 'stage_b_tests.py.v2')   -Destination 'D:\Bonsai-demo\optimization\20260927_165311\tests\stage_b_tests.py' -Force

还原后校验:
  Get-FileHash -LiteralPath 'D:\Bonsai-demo\proxy\bonsai_proxy.py' -Algorithm SHA256
    -> 必须等于 5DAAB52777768428… （backup\MANIFEST.csv 里 proxy\bonsai_proxy.py 的值）

还原后让在线生效（代理参数已变回旧形态）——空闲时执行一次:
  python launcher\bonsai_launcher.py up --no-prewarm
  预期: 代理命令行不再含 --config，up 会检出漂移并只重启代理；后端不动。
  若不想用 launcher，也可手动: 停掉当前代理进程（只按 state 记录的 PID），
  再按旧命令行启动 proxy\bonsai_proxy.py --port 8080 --upstream 8081 --effort medium

注意:
  - 阶段 C 未改 GPU 锁频/驱动/BIOS/VBS/电源/系统代理，未改模型权重与推理内核；
    回滚只涉及代理脚本 + 两个参数文件，后端 llama-server 无需重启。
  - 新增文件（tests\stage_c_tests.py、results\stage_c_tests.txt、logs\requests.jsonl、
    capture\ 下的 timings.jsonl/effort.txt）可保留，不属于旧路径的依赖。
  - requests.jsonl 只由 v3 代理写；还原到 v2 后不再产生（旧版写 timings.jsonl）。


## R4 阶段 D 回滚（代理 v3 -> 回到未打 D 补丁的 v3）

触发条件：D 落盘后出现档位注入异常 / 客户端已指定的值被覆盖 / 代理启动失败 / 想复现阶段 C 行为。

步骤（空闲时执行；只涉及代理脚本，后端 llama-server 无需重启）:
  $SD = 'D:\Bonsai-demo\optimization\20260927_165311\backup\stageD'
  Copy-Item -LiteralPath (Join-Path $SD 'bonsai_proxy.py.v3') -Destination 'D:\Bonsai-demo\proxy\bonsai_proxy.py' -Force

还原后校验:
  Get-FileHash -LiteralPath 'D:\Bonsai-demo\proxy\bonsai_proxy.py' -Algorithm SHA256
    -> 必须等于 7478BF4EF933286BA6430DAFB230CA07F8F18DDB08818CC59ACCE69A99999C46
  还原后仍是阶段 C 的 v3（read1 流式 / 增量 SSE / 四档超时 / 排队 / 每请求日志）。

让在线生效（空闲窗口，只重启代理，后端 PID 必须不变）:
  - 注意：阶段 D 只改了脚本内容、命令行参数未变，因此 launcher up 会判定“参数与配置一致”，
    不会自动重启代理。必须手动重置代理进程：
      1. python launcher\bonsai_launcher.py status     # 记下 [代理] 的 PID
      2. 核对命令行确为本项目 proxy\bonsai_proxy.py 后停掉该 PID
      3. python launcher\bonsai_launcher.py up --no-prewarm   # 只拉起代理
  - 预期：代理换新 PID，后端 PID 不变；status 显示两端身份匹配。

注意:
  - 阶段 D 未改 GPU 锁频/驱动/BIOS/VBS-内存完整性/电源管理/系统代理，未改模型权重与推理内核；
    也未改 config\bonsai-agent.json 的 budget.policy（仍为两项 false，默认不注入预算）。
  - 可保留文件（不属于旧路径依赖）：tests\stage_d_tests.py、results\stage_d_probe.json、
    results\stage_d_probe.txt、results\stage_d_verdict.txt、results\stage_d_tests.txt、
    results\stage_c_tests_regression.txt、results\stage_b_tests_regression.txt。
  - requests.jsonl 中新增字段 effort_source / effort_effective / budget_applied 在还原后消失，
    属预期（v3 无此字段）。
## R5 阶段 E 回滚（输入预算闸门 -> 关闭/移除）

改了什么：
  - D:\Bonsai-demo\proxy\bonsai_proxy.py：新增 CTX_WIN / budget_gate_cfg / effective_context_window /
    upstream_json / exact_input_tokens / check_input_budget，并在 _forward 内、排队之前接入；
    new_record 增加 budget_check 字段。
  - D:\Bonsai-demo\config\bonsai-agent.json：budget 下新增 context_window_tokens 与 gate。

最快回退（推荐，先撤功能再考虑撤代码）：
  1. 把 config\bonsai-agent.json 的 budget.gate.enabled 改为 false。
     -> 闸门立即变 disabled（info.verdict="闸门已关闭"），不发 /props、不计 token、不改 body，
        功能上与未打 E 补丁等价；这是零风险回退，不需要动代码。
  2. 只重启代理使配置生效（与 R4 同法，launcher up 不会自动重启代理）：
     python launcher\bonsai_launcher.py status            # 记下 [代理] PID
     核对命令行确为本项目 proxy\bonsai_proxy.py 后停掉该 PID
     python launcher\bonsai_launcher.py up --no-prewarm    # 只拉起代理
     预期：代理换新 PID，后端 PID 不变。

彻底回到 E 之前的字节（若必须）：
  - 代理：用 backup\stageE\bonsai_proxy.py.stageD 覆盖 proxy\bonsai_proxy.py
    （即阶段 D 结束时版本，sha256 42a50d658e68b529…；再往前见 R4/R3）。
  - 配置：用 backup\stageE\bonsai-agent.json.stageD 覆盖 config\bonsai-agent.json
    （即阶段 D 结束时版本，sha256 13f34b22049f9a6e…）。
  - 覆盖后同样需要手动重启代理（见上）。
  - 临时切换 gate.mode 的辅助脚本：tests\set_gate_mode.py（warn|reject，只做一处文本替换 + JSON 校验）。

注意：
  - 阶段 E 未改 GPU 锁频/驱动/BIOS/VBS-内存完整性/电源管理/系统代理，未改模型权重与推理内核；
    未开启 budget.policy（仍为两项 false，不注入请求级预算）。
  - requests.jsonl 中新增字段 budget_check 在还原后消失，属预期。
  - 可保留文件（不属于旧路径依赖）：tests\stage_e_tests.py、tests\stage_e_probe.py、
    tests\stage_e_online.py、tests\set_gate_mode.py、results\stage_e_tests.txt、
    results\stage_e_probe.json、results\stage_e_probe.txt。

## R6 — 阶段 F（工具体契约加固 / 瘦身逐项开关 / 策略块 / 启动器文案）
改动范围（详见 changes.md「七、阶段 F」）:
  proxy\bonsai_proxy.py、config\bonsai-agent.json、launcher\bonsai_launcher.py、
  optimization\20260927_165311\tests\stage_e_probe.py（仅探针调用点）

回滚命令（把备份覆盖回去，SHA256 见括注）:
  copy "D:\Bonsai-demo\optimization\20260927_165311\backup\stageF\bonsai_proxy.py.preF" "D:\Bonsai-demo\proxy\bonsai_proxy.py"
        # a375f4f36458cb27…（阶段 E 版）
  copy "D:\Bonsai-demo\optimization\20260927_165311\backup\stageF\bonsai-agent.json.preF" "D:\Bonsai-demo\config\bonsai-agent.json"
        # 2df7ef565a53e559…（阶段 E 版，gate.mode=warn）
  copy "D:\Bonsai-demo\optimization\20260927_165311\backup\stageF\bonsai_launcher.py.preF" "D:\Bonsai-demo\launcher\bonsai_launcher.py"
        # 6163d84f22b45fc3…
  copy "D:\Bonsai-demo\optimization\20260927_165311\backup\stageF\stage_e_probe.py.preF" "D:\Bonsai-demo\optimization\20260927_165311\tests\stage_e_probe.py"
        # f797f6b3f77e323d…
回滚后必须重启**代理**（按身份停 8080 上的 bonsai_proxy.py，再 launcher up --no-prewarm）；
后端 llama-server 不需要重启（阶段 F 完全没动后端参数）。
注意：launcher 的“在线参数 vs 配置”差异检测只看命令行参数，不看脚本内容 —— 改了代理脚本
不重启的话，在线跑的仍是旧代码（本次就是这样发现并修正的）。

不改代码的单项关闭（只改 config，然后重启代理即可生效）:
  tools.schema_hardening=false   -> 停止 show_widget.loading_messages 契约加固
  tools.error_policy=false       -> 不再并入“工具错误恢复”策略块
  slimming.deferred_tools=true   -> 重新压缩 ToolSearch deferred 工具名册（省 ≈2,512 tok）
  slimming.subagents=true        -> 重新压缩子代理类型名册（省 ≈1,200 tok）
  slimming 三项全 false          -> 整体关闭瘦身（等价于旧的 --keep-location 效果）


## R7 — 回滚演练实录（阶段 H2 要求，实跑 2026-09-27 22:45）

演练目的：验证“从本次 backup 恢复 -> 用备份对应的启动方式启动 -> 核对端口/模型/上下文/实际参数 ->
有限输出 smoke -> 前滚复原”这条链路真实可用（方案 §H2 第 2、3 条）。

- 脚本：`optimization\20260927_165311\tests\rollback_drill.ps1`（sha256 `899317E67E21053BAD5238BC3ECF35BF63DD62C7630FBF14F6C33FA49CAFA6A6`；与演练当时在 TRAE 工作目录 `.stage\` 下执行的副本逐字节相同）
- 日志：`optimization\20260927_165311\baseline\stageH_rollback_drill.log`（9,615 B）
- 受控范围：**只替换 :8080 上的代理文件**，后端 `llama-server` pid 35040 全程不动（未重启、未换 pid）。

实测步骤与结果：

| 步 | 动作 | 实测 |
|---|---|---|
| 0 | 前置：确认无在途任务 | 后端 health=ok，忙槽=无 |
| 1 | 记录前态 | 代理 sha256 `6ACFB9C5...`、83,934 B、pid 18008 |
| 2 | 身份核对后停代理 | 命令行含 `bonsai_proxy.py --port 8080`，核对通过后停止；`:8080 listening=False` |
| 3 | 恢复 `backup\stageF\bonsai_proxy.py.preF` | sha256 变为 `A375F4F3...`、69,903 B；`harden_tool_schemas` 检测=**False**（与预期一致） |
| 4 | `launcher up` 启动 | 后端“已在运行 pid=35040 / 在线参数与配置一致，无需重启” -> **后端 pid 未变**；代理新起 pid 41316 |
| 5 | 校验 | :8080 `/health`=ok；后端 build=`b181-9ef3205`、n_ctx=`65536`、alias=`bonsai-2-27b`；`launcher status` 身份匹配；smoke 通过 0.94 s `finish=stop`，decode 36.92 t/s |
| 6 | 前滚复原（`backup\stageG\preA_proxy__bonsai_proxy.py`）+ 复验 | 代理 sha256 回到 `6ACFB9C5...`，一致=**True**；`harden_tool_schemas`=**True**；代理 pid 40480；:8080 ok；smoke 通过 0.55 s `finish=stop` |

结论：本仓的代理层回滚与复原**实跑可用**，且不需要重启后端。

局限（如实记录）：
- 本次只演练了**代理文件**这一条（R6 改动中的 4 个文件只覆盖了代理）；`config\bonsai-agent.json`、
  `launcher\bonsai_launcher.py`、`tests\stage_e_probe.py` 的覆盖回滚**未在本次演练中实跑**，其命令见 R6。
- 回滚态代理为修复前版本，**不写 `requests.jsonl`**（预期行为），故 observability 字段在回滚态缺失。
- 演练期间的 smoke 为短输出（max_tokens=24），非负载测试；性能数字不用于任何结论。


## R8 — 回滚 C1（`--cache-ram 1024`，阶段 G4 / 2026-09-27 23:05 实施）

适用：若真实长上下文被观测到 TTFT/复用回归，或需要恢复变更前的宿主管存上限。

变更内容：`config\bonsai-agent.json` 的 `backend.extra_args`：`[]` → `["--cache-ram", "1024"]`

sha256 对照：
  变更前（= 备份 `backup\stageG4\bonsai-agent.json.preG4`）  6,276 B  D678A79A1283496573E980DB1AB5397A08A63037CF2356774728F3F68CA815B7
  变更后（当前生效）                                        6,297 B  A68766381AAF1E32DB0D5C3124911A6DF04753559C91D315960FCAD8D33B7E07
  配置指纹：0b0d2806eb9a9d1a → 96df0f5964452b3c

回滚步骤（择一）：
  方式 A（清空 extra_args，恢复 llama-server 默认 8192 MiB）：
      把 `backend.extra_args` 改回 `[]`，或整文件覆盖回 `backup\stageG4\bonsai-agent.json.preG4`；
      然后： `python D:\Bonsai-demo\launcher\bonsai_launcher.py up --no-prewarm`
      预期：输出「仅配置有 / 仅在线有」差异 → 判定参数不一致 → 空闲受控重启后端；新命令行不再含 `--cache-ram`。
  方式 B（改用其它上限，如 2048 / 4096）：
      把 `backend.extra_args` 改为 `["--cache-ram", "2048"]`，同样执行 `launcher up --no-prewarm`。

核验：
  `launcher status` / `show-config` 显示新配置指纹；
  `(Get-CimInstance Win32_Process -Filter "ProcessId=<pid>").CommandLine` 中 `--cache-ram` 值已变化；
  **代理无需重启**（本改动不涉及代理脚本，代理 pid 不变）。

注意（坑）：
  - launcher 的“在线参数 vs 配置”差异检测**只看命令行参数**；只改 config 而不重启，在线仍是旧参数。
    本次正是靠该差异检测自动重启后端（见 `G4 验收报告-C1 cache-ram 1024.md` §1）。
  - 回滚只需重启后端；不要按端口盲杀，停止只操作 launcher state 中核对过身份的 PID。
