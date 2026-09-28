<#
  bench_ngl_scan.ps1 -- llama-bench 扫描生产模型的 ngl 悬崖点（RTX 5060 Laptop 8GB 专属）

  为什么需要：
    start_bonsai.bat 注释里有一张针对 PQ2_0 权重的实测表（ngl 62 开始掉速、64 跌到 1.4 t/s）。
    但生产的模型是更小的 PTQ1_0-mtp-lean.gguf，它自己的悬崖点从未实测——生产启动器却都用 -ngl 99。
    本脚本用 llama-bench 隔离出纯后端吞吐（不受代理/工具/传输影响），找出真实上限。

  前置条件：
    必须先停掉正在运行的 llama-server。整机仅 8GB 显存，无法与新实例并存。
    停法：关闭 start_all_agent.bat 窗口，或 taskkill /f /im llama-server.exe

  用法（在 PowerShell 中）：
    powershell -ExecutionPolicy Bypass -File bench_ngl_scan.ps1
    powershell -ExecutionPolicy Bypass -File bench_ngl_scan.ps1 -Ngl 48,52,56,58,62,99 -Reps 3

  判读：
    ~-p 列为 prefill t/s，n 列为 decode t/s。逐档对比，出现断崖式下跌（如骤降 5~10 倍）
    的那个 ngl 就是上限，取上限下方最接近的一档作为生产值。
#>
param(
  [int[]] $Ngl    = @(48,52,56,58,62,99),
  [int]   $Prompt = 512,
  [int]   $Gen    = 128,
  [int]   $Batch  = 2048,
  [int]   $Ubatch = 512,
  [int]   $Reps   = 3,
  [int]   $Threads = 8,
  [string]$Bench  = 'D:\Bonsai-demo\hybrid-test\llama-bench.exe',
  [string]$Model  = 'D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf',
  [string]$Out    = 'D:\Bonsai-demo\optimization\20260927_160739'
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Bench)) { throw "找不到 llama-bench: $Bench" }
if (-not (Test-Path $Model)) { throw "找不到模型: $Model" }

$running = Get-Process llama-server -ErrorAction SilentlyContinue
if ($running) {
  Write-Warning "检测到 llama-server 正在运行 (PID: $($running.Id -join ', '))。8GB 显存无法并行。"
  $ans = Read-Host "仍要继续？(y/N)"
  if ($ans -ne 'y') { Write-Host "已取消。"; exit 1 }
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log   = Join-Path $Out "ngl_scan_$stamp.md"
$nglArg = ($Ngl -join ',')

Write-Host "扫描 ngl=$nglArg  p=$Prompt n=$Gen b=$Batch ub=$Ubatch r=$Reps t=$Threads" -ForegroundColor Cyan
Write-Host "输出 -> $log"

& $Bench -m $Model `
  -ngl $nglArg -p $Prompt -n $Gen `
  -b $Batch -ub $Ubatch -t $Threads `
  -ctk q4_0 -ctv q4_0 -fa on -r $Reps -o md *>&1 | Tee-Object -FilePath $log

Write-Host "`n完成。对比各档 t/s，骤降点为悬崖；生产 ngl 取悬崖下方一档。" -ForegroundColor Green
