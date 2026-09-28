# 阶段 H2 回滚演练（备份恢复 -> 启动校验 -> smoke -> 前滚复原）
# 受控对象：只换 :8080 上的代理文件，后端 pid 35040 全程不动。
$ErrorActionPreference = "Stop"
$py   = "C:\Users\intpj\AppData\Local\Programs\Python\Python310\python.exe"
$base = "D:\Bonsai-demo"
$opt  = "$base\optimization\20260927_165311"
$log  = "$opt\baseline\stageH_rollback_drill.log"

function Log($m) { Write-Host $m; Add-Content -Path $log -Value ([string]$m) -Encoding utf8 }
function HashOf($p) { (Get-FileHash $p -Algorithm SHA256).Hash }
function ProxyPid {
  (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
     Where-Object { $_.CommandLine -like "*bonsai_proxy.py*" -and $_.CommandLine -like "*--port 8080*" } |
     Select-Object -First 1).ProcessId
}
function PortListen($p) {
  [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

Set-Content -Path $log -Value ("# 阶段 H2 回滚演练  " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -Encoding utf8

# ---------------- 0 前置：确认没有真实任务在跑 ----------------
$h = Invoke-RestMethod "http://127.0.0.1:8081/health" -TimeoutSec 5
$slots = Invoke-RestMethod "http://127.0.0.1:8081/slots" -TimeoutSec 5
$busy = @($slots | Where-Object { $_.is_processing }) -join ","
Log "[0] 后端 health=$($h.status)  忙槽=$([string]::IsNullOrEmpty($busy) ? '无' : $busy)"
if (-not [string]::IsNullOrEmpty($busy)) { throw "有任务在跑，按 H2.2 中止演练" }

# ---------------- 1 记录前态 ----------------
$proxyPath = "$base\proxy\bonsai_proxy.py"
$beforeHash = HashOf $proxyPath
$beforeLen  = (Get-Item $proxyPath).Length
$pidPre = ProxyPid
Log "[1] 前态：代理 sha256=$beforeHash  bytes=$beforeLen  pid=$pidPre  :8080 listening=$(PortListen 8080)"

# ---------------- 2 停本次管理器持有且已验证身份的代理 ----------------
$cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$pidPre").CommandLine
if ($cmdline -notlike "*bonsai_proxy.py*") { throw "身份核对失败，拒绝停止 pid=$pidPre" }
Log "[2] 身份核对通过：$cmdline"
Stop-Process -Id $pidPre -Force
Start-Sleep -Seconds 2
Log "[2] 已停止代理 pid=$pidPre；:8080 listening=$(PortListen 8080)"

# ---------------- 3 从本次 backup 恢复（只恢复本次修改的代理文件） ----------------
$rbSrc = "$opt\backup\stageF\bonsai_proxy.py.preF"
Copy-Item $rbSrc $proxyPath -Force
$rbHash = HashOf $proxyPath
Log "[3] 回滚源=$rbSrc"
Log "[3] 已恢复：代理 sha256=$rbHash  bytes=$((Get-Item $proxyPath).Length)（目标 A375F4F3...）"
$hasF = Select-String -Path $proxyPath -Pattern "harden_tool_schemas" -Quiet
Log "[3] 结构证据：恢复后的代理含 F 阶段 harden_tool_schemas = $hasF（应为 False）"

# ---------------- 4 用备份对应的启动方式启动 ----------------
Log "[4] 启动：launcher up"
& $py "$base\launcher\bonsai_launcher.py" up 2>&1 | ForEach-Object { Log "    $_" }

# ---------------- 5 校验端口/模型/上下文/实际参数 + smoke ----------------
$pidRb = ProxyPid
Log "[5] 回滚后代理 pid=$pidRb  :8080 listening=$(PortListen 8080)"
$hp = Invoke-RestMethod "http://127.0.0.1:8080/health" -TimeoutSec 5
Log "[5] 代理 /health = $($hp.status)"
$props = Invoke-RestMethod "http://127.0.0.1:8081/props" -TimeoutSec 5
Log "[5] 后端 build=$($props.build_info) n_ctx=$($props.default_generation_settings.n_ctx) alias=$($props.model_alias)"
& $py "$base\launcher\bonsai_launcher.py" status 2>&1 | ForEach-Object { Log "    $_" }
Log "[5] smoke（经代理真实推理）"
& $py "$base\launcher\bonsai_launcher.py" smoke 2>&1 | ForEach-Object { Log "    $_" }
Log "[5] 代理日志尾部："
Get-Content "$base\logs\proxy.log" -Tail 8 | ForEach-Object { Log "    $_" }

# ---------------- 6 前滚：恢复修复后代理并复验 ----------------
$pidRb2 = ProxyPid
if ($pidRb2) {
  $c2 = (Get-CimInstance Win32_Process -Filter "ProcessId=$pidRb2").CommandLine
  if ($c2 -notlike "*bonsai_proxy.py*") { throw "身份核对失败，拒绝停止 pid=$pidRb2" }
  Stop-Process -Id $pidRb2 -Force
  Start-Sleep -Seconds 2
  Log "[6] 已停止回滚态代理 pid=$pidRb2"
}
Copy-Item "$opt\backup\stageG\preA_proxy__bonsai_proxy.py" $proxyPath -Force
$fwHash = HashOf $proxyPath
Log "[6] 前滚完成：代理 sha256=$fwHash（应回到 $beforeHash）  一致=$($fwHash -eq $beforeHash)"
Log "[6] 结构证据：含 F 阶段 harden_tool_schemas = $(Select-String -Path $proxyPath -Pattern 'harden_tool_schemas' -Quiet)"
& $py "$base\launcher\bonsai_launcher.py" up 2>&1 | ForEach-Object { Log "    $_" }
$pidFw = ProxyPid
Log "[6] 前滚后代理 pid=$pidFw  :8080 listening=$(PortListen 8080)"
& $py "$base\launcher\bonsai_launcher.py" status 2>&1 | ForEach-Object { Log "    $_" }
& $py "$base\launcher\bonsai_launcher.py" smoke 2>&1 | ForEach-Object { Log "    $_" }
Log "[7] 演练结束 $(Get-Date -Format 'HH:mm:ss')"