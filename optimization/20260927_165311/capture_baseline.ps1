# Stage A2 read-only baseline capture for Bonsai demo optimization
# Usage: powershell -ExecutionPolicy Bypass -File capture_baseline.ps1 -Root <workdir>
param([string]$Root = "D:\Bonsai-demo\optimization\20260927_165311")
$ErrorActionPreference = 'Continue'
$b = Join-Path $Root 'baseline'
New-Item -ItemType Directory -Force -Path $b | Out-Null
$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
Set-Content -LiteralPath (Join-Path $b 'captured_at.txt') -Value $stamp -Encoding UTF8

# 1) processes
Get-CimInstance Win32_Process -Filter "Name = 'llama-server.exe' OR Name = 'python.exe' OR Name = 'pythonw.exe'" |
  Select-Object ProcessId, Name, ExecutablePath, CommandLine |
  ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $b 'processes.json')

# 2) TCP listeners on 8080/8081
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { $_.LocalPort -in 8080,8081 } |
  Select-Object LocalAddress, LocalPort, OwningProcess |
  ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 (Join-Path $b 'listeners.json')

# 3) API endpoints (raw text preserved)
foreach ($ep in 'health','props','slots') {
  $out = Join-Path $b ("api_" + $ep + ".json")
  try {
    $c = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8081/$ep" -TimeoutSec 8
    Set-Content -LiteralPath $out -Value $c.Content -Encoding UTF8
  } catch {
    Set-Content -LiteralPath $out -Value ("ERROR: " + $_.Exception.Message) -Encoding UTF8
  }
}

# 4) GPU
$smi = & nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,clocks.current.graphics,clocks.current.memory,clocks.max.graphics --format=csv 2>&1
Set-Content -LiteralPath (Join-Path $b 'gpu_nvidia-smi.csv') -Value ($smi | Out-String) -Encoding UTF8

# 5) binary info + hash
$bin = 'D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin\llama-server.exe'
$bi = @()
if (Test-Path -LiteralPath $bin) {
  $fi = Get-Item -LiteralPath $bin
  $bi += "path=$bin"
  $bi += "bytes=$($fi.Length)"
  $bi += "last_write=$($fi.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
  $bi += "sha256=$((Get-FileHash -LiteralPath $bin -Algorithm SHA256).Hash)"
  $bi += "file_version=$($fi.VersionInfo.FileVersion)"
  $bi += "product_version=$($fi.VersionInfo.ProductVersion)"
  $bi += "company=$($fi.VersionInfo.CompanyName)"
} else { $bi += "MISSING: $bin" }
Set-Content -LiteralPath (Join-Path $b 'binary_info.txt') -Value ($bi -join "`n") -Encoding UTF8

# 6) model file info
$mdl = 'D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf'
$mi = @()
if (Test-Path -LiteralPath $mdl) {
  $mf = Get-Item -LiteralPath $mdl
  $mi += "path=$mdl"
  $mi += "bytes=$($mf.Length)"
  $mi += "GiB=" + [math]::Round($mf.Length/1GB,3)
  $mi += "last_write=$($mf.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
} else { $mi += "MISSING: $mdl" }
Set-Content -LiteralPath (Join-Path $b 'model_info.txt') -Value ($mi -join "`n") -Encoding UTF8

# 7) git commit of source tree
Push-Location 'D:\Bonsai-demo'
$g = @()
$g += "HEAD=" + (git rev-parse HEAD 2>&1)
$g += "date=" + (git log -1 --format=%cI 2>&1)
$g += "subject=" + (git log -1 --format=%s 2>&1)
$g += "dirty=" + ((git status --porcelain 2>&1) | Measure-Object).Count + " entries"
Pop-Location
Set-Content -LiteralPath (Join-Path $b 'git_info.txt') -Value ($g -join "`n") -Encoding UTF8
(git -C 'D:\Bonsai-demo' status --porcelain 2>&1) | Set-Content -Encoding UTF8 (Join-Path $b 'git_status_porcelain.txt')

# 8) LLAMA_ARG_* / BONSAI_* env vars (current shell + persisted)
$envrows = @()
$envrows += "--- current process env ---"
Get-ChildItem Env: | Where-Object { $_.Name -match '^(LLAMA|BONSAI|NO_PROXY|HTTP_PROXY|HTTPS_PROXY)' } |
  ForEach-Object { $envrows += ("{0}={1}" -f $_.Name, $_.Value) }
$envrows += "--- persisted User ---"
([Environment]::GetEnvironmentVariables('User').GetEnumerator() | Where-Object { $_.Key -match '^(LLAMA|BONSAI)' } | ForEach-Object { "{0}={1}" -f $_.Key, $_.Value }) | ForEach-Object { $envrows += $_ }
$envrows += "--- persisted Machine ---"
([Environment]::GetEnvironmentVariables('Machine').GetEnumerator() | Where-Object { $_.Key -match '^(LLAMA|BONSAI)' } | ForEach-Object { "{0}={1}" -f $_.Key, $_.Value }) | ForEach-Object { $envrows += $_ }
Set-Content -LiteralPath (Join-Path $b 'env_llama_bonsai.txt') -Value ($envrows -join "`n") -Encoding UTF8

# 9) capture effort.txt + verdict.txt
foreach ($f in 'capture\effort.txt','capture\verdict.txt','capture\timings.jsonl') {
  $src = Join-Path 'D:\Bonsai-demo' $f
  if (Test-Path -LiteralPath $src) {
    Copy-Item -LiteralPath $src -Destination (Join-Path $b ((Split-Path $f -Leaf))) -Force
  }
}

Write-Output "BASELINE_DONE $b"
