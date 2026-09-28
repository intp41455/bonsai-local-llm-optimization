# Bonsai 2 27B (PTQ1_0 + MTP) -- 原生 sm_120a 构建，RTX 5060 Laptop 8GB 黄金配置
$ErrorActionPreference = 'Stop'
$Root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bin   = Join-Path $Root 'bin'
$Model = 'D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf'

# ---- 可调开关（环境变量）----
$Ctx    = if ($env:BONSAI_CTX)    { [int]$env:BONSAI_CTX } else { 32768 }
$Port   = if ($env:BONSAI_PORT)   { [int]$env:BONSAI_PORT } else { 8080 }
# 思考档：medium(chat 默认) / low / xhigh。智能体场景设 BONSAI_THINK=0 关思考。
$Effort = if ($env:BONSAI_EFFORT) { $env:BONSAI_EFFORT } else { 'medium' }
$Think  = $env:BONSAI_THINK -ne '0'
$ThinkBudget = if ($env:BONSAI_THINK_BUDGET) { [int]$env:BONSAI_THINK_BUDGET } else { 20480 }
# 草稿列数：1 = 8GB 实测最优（62.05 t/s，优于 2 的 45.04）；0 = 关投机
$Spec   = if ($env:BONSAI_SPEC) { [int]$env:BONSAI_SPEC } else { 1 }
# 深度截断：8GB 上草稿在 5k 深度就变负收益，4096 是实测拐点（官方 24576 不适用）
$SpecDepth = if ($env:BONSAI_SPEC_DEPTH) { [int]$env:BONSAI_SPEC_DEPTH } else { 4096 }

$Kw = if ($Think) { @{ reasoning_effort = $Effort } } else { @{ reasoning_effort = $Effort; enable_thinking = $false } }
$KwJson = $Kw | ConvertTo-Json -Compress

[string[]]$SpecArgs = @()
if ($Spec -gt 0) {
    $env:GGML_CUDA_BATCH_INVARIANT = '1'
    $SpecArgs = @('--spec-type','draft-mtp','--spec-draft-n-max',"$Spec",
                  '--spec-draft-depth-max',"$SpecDepth",
                  '-ctkd','q4_0','-ctvd','q4_0')
}

Write-Host "model  Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
Write-Host "window $Ctx / q4_0     spec=$Spec (depth-max $SpecDepth)  think=$Think effort=$Effort budget=$ThinkBudget"
Write-Host "listen http://127.0.0.1:$Port   alias bonsai-2-27b"

Set-Location $Bin
& .\llama-server.exe @SpecArgs `
    --backend-sampling `
    --chat-template-kwargs $KwJson `
    --reasoning-budget $ThinkBudget `
    --reasoning-budget-message 'Now produce the complete answer.' `
    -m $Model -ngl 99 -fa on -np 1 -c $Ctx -b 2048 -ub 512 `
    -ctk q4_0 -ctv q4_0 `
    -n 24576 `
    --temp 1.0 --top-p 0.95 --top-k 20 `
    --host 127.0.0.1 --port $Port --alias bonsai-2-27b --metrics --jinja
