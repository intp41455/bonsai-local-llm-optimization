<#
  bench_cache_checkpoints.ps1 -- 对比服务端 prompt cache 配置对 prefill 的影响

  为什么需要：
    PROMPT-CACHE.md 列出五个服务端控制项，但现有六套启动器一个都没传。
    关键权衡：--ctx-checkpoints 会把短请求的 prefill 拆成多批，可能反而更慢；
    所以不能无脑开，必须按真实负载分布（长对话 vs 短独立请求）分别选档。

  做法：
    对每个配置档启动一个临时 llama-server（端口 8090），
    把同一段提示词连发两次，读响应里的 timings：
      - 第 1 次：prompt_n 约为全量，cache_n 接近 0（首次 prefill）
      - 第 2 次：cache_n 应约等于 prompt_n（命中缓存），prompt_ms 应大幅下降
    比较各档的 prompt_ms / cache_n / 端到端 wall，选命中率与延迟最平衡的一档。

  前置条件：
    需在空闲机器上运行（8GB 显存不能与生产 server 并存）。
    先停掉生产 llama-server，再执行本脚本。

  用法：
    powershell -ExecutionPolicy Bypass -File bench_cache_checkpoints.ps1
    powershell -ExecutionPolicy Bypass -File bench_cache_checkpoints.ps1 -NPredict 8
#>
param(
  [int]   $Port    = 8090,
  [int]   $Ctx     = 32768,
  [int]   $NPredict = 16,
  [string]$Bin     = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin\llama-server.exe',
  [string]$Model   = 'D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf',
  [string]$Out     = 'D:\Bonsai-demo\optimization\20260927_160739'
)
$ErrorActionPreference = 'Stop'
$base = "http://127.0.0.1:$Port"

if (-not (Test-Path $Bin))   { throw "找不到 llama-server: $Bin" }
if (-not (Test-Path $Model)) { throw "找不到模型: $Model" }
if (Get-Process llama-server -ErrorAction SilentlyContinue) {
  throw "检测到 llama-server 正在运行。请先停掉，避免 8GB 显存冲突。"
}

$Configs = @(
  [pscustomobject]@{ Name = 'A_baseline';      Extra = @() },
  [pscustomobject]@{ Name = 'B_ckpt32_idle';   Extra = @('--cache-ram','4096','--ctx-checkpoints','32','--cache-idle-slots') },
  [pscustomobject]@{ Name = 'C_ckpt0';         Extra = @('--ctx-checkpoints','0') }
)

# 长提示词（模拟 agent 长上下文）+ 短提示词（模拟独立小请求）
$longPrompt  = '请详细说明本地大模型推理优化的要点。' + ('以下是背景资料，请先阅读再作答：本地推理需要在显存与上下文长度之间权衡。' * 80)
$shortPrompt = '用一句话说明什么是 KV cache。'

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$results = @()

function Start-BenchServer($extra) {
  $a = @('-m',$Model,'-ngl','99','-fa','on','-np','1','-c',$Ctx,'-b','2048','-ub','512',
         '-ctk','q4_0','-ctv','q4_0','--host','127.0.0.1','--port',"$Port",'--alias','bench') + $extra
  return Start-Process -FilePath $Bin -ArgumentList $a -PassThru -WindowStyle Hidden
}
function Wait-Health([int]$timeout = 240) {
  $t0 = Get-Date
  while (((Get-Date) - $t0).TotalSeconds -lt $timeout) {
    try { if ((Invoke-RestMethod "$base/health" -TimeoutSec 3).status -eq 'ok') { return $true } } catch {}
    Start-Sleep -Seconds 2
  }
  return $false
}
function Ask([string]$prompt) {
  $body = @{ messages = @(@{ role = 'user'; content = $prompt }); n_predict = $NPredict; stream = $false; cache_prompt = $true } | ConvertTo-Json -Depth 8
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $r  = Invoke-RestMethod "$base/v1/chat/completions" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 300
  $sw.Stop()
  [pscustomobject]@{
    wall_s    = [math]::Round($sw.Elapsed.TotalSeconds, 2)
    prompt_n  = $r.timings.prompt_n
    cache_n   = $r.timings.cache_n
    prompt_ms = [math]::Round([double]$r.timings.prompt_ms, 0)
  }
}

foreach ($c in $Configs) {
  Write-Host "`n=== 配置 $($c.Name)  extra=$($c.Extra -join ' ') ===" -ForegroundColor Cyan
  $proc = Start-BenchServer $c.Extra
  try {
    if (-not (Wait-Health)) { throw "服务未在超时内就绪" }
    Start-Sleep -Seconds 2
    $l1 = Ask $longPrompt
    $l2 = Ask $longPrompt
    $s1 = Ask $shortPrompt
    $s2 = Ask $shortPrompt
    $results += [pscustomobject]@{
      Config = $c.Name
      'Long#1_wall'   = $l1.wall_s; 'Long#1_prompt_n' = $l1.prompt_n; 'Long#1_prompt_ms' = $l1.prompt_ms
      'Long#2_wall'   = $l2.wall_s; 'Long#2_prompt_n' = $l2.prompt_n; 'Long#2_cache_n'  = $l2.cache_n; 'Long#2_prompt_ms' = $l2.prompt_ms
      'Short#1_wall'  = $s1.wall_s; 'Short#1_prompt_ms' = $s1.prompt_ms
      'Short#2_wall'  = $s2.wall_s; 'Short#2_cache_n'  = $s2.cache_n; 'Short#2_prompt_ms' = $s2.prompt_ms
    }
    Write-Host ("  long  1st: prompt_n={0} prompt_ms={1}  2nd: cache_n={2} prompt_ms={3}" -f $l1.prompt_n,$l1.prompt_ms,$l2.cache_n,$l2.prompt_ms)
    Write-Host ("  short 1st: prompt_ms={0}  2nd: cache_n={1} prompt_ms={2}" -f $s1.prompt_ms,$s2.cache_n,$s2.prompt_ms)
  } finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
  }
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$csv = Join-Path $Out "cache_checkpoints_$stamp.csv"
$results | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8
Write-Host "`n结果已保存 -> $csv" -ForegroundColor Green
Write-Host "判读：若 B 档 Long#1/Long#2 的 prompt_ms 明显低于 A 档且 short 档未变慢，则长对话负载选 B；" -ForegroundColor Green
Write-Host "      若 B 档 short 的 prompt_ms 反而升高，说明 checkpoint 拆批有代价，短请求为主的负载应选 C。" -ForegroundColor Green
