# 变更前证据保全（管理员只读）：导出事件日志 / 复制 WER 归档 / 枚举驱动包
# 只读导出与复制，不修改任何系统设置，不停止任何服务。
$dest = 'D:\Bonsai-demo\optimization\20260927_165311\baseline\prechange_20260927_2036'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Start-Transcript -Path "$dest\_elevated_log.txt" -Force | Out-Null
Write-Output ("脚本启动 " + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + "  dest=" + $dest)

# 1) 导出 System / Application 事件日志（.evtx 原始文件，可离线复现查询）
try {
  wevtutil epl System "$dest\System.evtx" /ow:true
  Write-Output "System.evtx 导出完成"
} catch { Write-Output ("System.evtx 导出失败: " + $_.Exception.Message) }
try {
  wevtutil epl Application "$dest\Application.evtx" /ow:true
  Write-Output "Application.evtx 导出完成"
} catch { Write-Output ("Application.evtx 导出失败: " + $_.Exception.Message) }

# 2) 复制 WER 归档里那份 Kernel_20001 报告（含崩溃上下文）
$werSrc = Get-ChildItem 'C:\ProgramData\Microsoft\Windows\WER\ReportArchive' -Directory -ErrorAction SilentlyContinue |
          Where-Object { $_.Name -like 'Kernel_20001*' } | Select-Object -First 1
if ($werSrc) {
  $werDst = Join-Path $dest 'wer_reportarchive'
  New-Item -ItemType Directory -Force -Path $werDst | Out-Null
  Copy-Item $werSrc.FullName -Destination $werDst -Recurse -Force -ErrorAction SilentlyContinue
  Write-Output ("WER 归档 -> " + $werDst)
} else { Write-Output 'WER 归档：未找到 Kernel_20001 报告' }

# 3) 枚举已安装驱动包（记录变更前的 NVIDIA oem inf 与版本，供变更后对照）
try {
  pnputil /enum-drivers | Out-File -FilePath "$dest\17_drivers_enum.txt" -Encoding utf8
  Write-Output "驱动包清单已写入 17_drivers_enum.txt"
} catch { Write-Output ("pnputil 失败: " + $_.Exception.Message) }

# 4) 记录 bcdedit 全文（hypervisorlaunchtype / VBS 引导项，供变更后对照）
try {
  bcdedit /enum '{current}' | Out-File -FilePath "$dest\18_bcdedit_current.txt" -Encoding utf8
  Write-Output "bcdedit 已写入 18_bcdedit_current.txt"
} catch { Write-Output ("bcdedit 失败: " + $_.Exception.Message) }

Write-Output "完成。"
Stop-Transcript | Out-Null