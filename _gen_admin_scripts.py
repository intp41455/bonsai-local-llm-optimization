# -*- coding: utf-8 -*-
"""
生成/加固 dist 目录下的管理脚本。

坑：cmd 默认代码页 936(GBK)，UTF-8 的中文注释会被当作命令执行
    （上轮把 `set MODELS=` 拆坏就是这原因）。所以这里统一用 GBK 落盘。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo"

# ------------------------------------------------------------------ 1. lock_clocks.bat
LOCK = r"""@echo off
setlocal
chcp 936 >nul

REM ============================================================
REM  Bonsai 2 27B - GPU 满频锁定（需管理员权限）
REM
REM  !! 默认不建议使用 !!  2026-09-27 05:00 起改为需二次确认
REM
REM  为什么默认不用：
REM    04:52 本机发生过一次整机蓝屏（bugcheck 0x20001 HYPERVISOR_ERROR）。
REM    当时 GPU 正被强制钉在显存 12001 MHz / SM 2600-3090 MHz，
REM    同时叠加了显存越线（计算缓冲被驱动偷偷搬进系统内存），
REM    满载跑了约 5 分钟。锁频去掉了驱动本来会做的降频自保动作，
REM    是这次事故的加重因素。
REM
REM  收益（实测）：
REM    decode 从 36~62 t/s 抖动  ->  稳定 56~66 t/s
REM
REM  代价：
REM    空闲不再降到 P4/9001 MHz；功耗与温度上升；复现蓝屏的加权因素。
REM
REM  ★ 只有在以下条件全部满足时才使用：
REM    1) 已改用 -ub 512（绝不能 -ub 2048，那是显存越线的直接原因）
REM    2) 机器接市电，且散热良好（温度 < 80 度）
REM    3) 一次连续推理不超过 10 分钟
REM    4) 你明确接受"可能再次蓝屏"的风险
REM
REM  解除锁定：运行 unlock_clocks.bat
REM ============================================================

net session >nul 2>&1
if errorlevel 1 (
    echo [!] 需要管理员权限。请右键本文件 -^> 以管理员身份运行
    pause
    exit /b 1
)

echo ============================================================
echo   !! 危险操作警告 !!
echo ============================================================
echo.
echo   本脚本会把 GPU 显存锁死在 12001 MHz、SM 锁在 2600-3090 MHz。
echo   这会取消驱动原有的降频自保，是 2026-09-27 04:52 整机蓝屏
echo   （HYPERVISOR_ERROR）的加重因素之一。
echo.
echo   正常使用（Agent 长上下文 / 日常对话）不需要它。
echo   只有在短上下文、要压榨速度时才考虑。
echo.
set /p CONFIRM=   确认要继续请输入 YES（其他任意键取消）:
if /i not "%CONFIRM%"=="YES" (
    echo.
    echo [已取消] 未做任何修改。
    pause
    exit /b 0
)

echo.
echo [1/2] 锁定显存频率到 12001 MHz（满频）...
nvidia-smi -i 0 -lmc 12001
if errorlevel 1 echo     [警告] 显存锁频失败（笔记本可能不支持）

echo.
echo [2/2] 锁定 SM 频率到 2600-3090 MHz...
nvidia-smi -i 0 -lgc 2600,3090
if errorlevel 1 echo     [警告] SM 锁频失败

echo.
echo ============================================================
echo   当前状态
echo ============================================================
nvidia-smi --query-gpu=name,clocks.sm,clocks.max.sm,clocks.mem,clocks.max.mem,temperature.gpu --format=csv
echo.
echo [完成] 现在可以启动 start_bonsai_8gb.bat。
echo        预期 decode 56~66 t/s（短上下文）
echo        记得用完运行 unlock_clocks.bat
echo.
pause
endlocal
"""

# ------------------------------------------------------------------ 2. disable_vbs.bat
DISVBS = r"""@echo off
setlocal
chcp 936 >nul

REM ============================================================
REM  关闭「内核隔离 / 内存完整性」(VBS + HVCI) —— 需管理员权限
REM
REM  为什么要做：
REM    2026-09-27 04:52 本机蓝屏，bugcheck = 0x00020001 HYPERVISOR_ERROR，
REM    即 Windows 虚拟机监控程序(hypervisor)自身发生致命错误。
REM    本机唯一在跑的 hypervisor 就是 VBS/HVCI（未启用 Hyper-V 功能，
REM    也未发现 VMware/VirtualBox 等第三方虚拟化）。
REM
REM    关掉 VBS 后：即使 GPU 驱动再出问题，后果会退化为
REM    单驱动重启(TDR/0x116)，而不会再演变成整机蓝屏。
REM
REM  !! 这不是"根治"：真正的触发源是 GPU 计算缓冲越界。
REM     根治手段是永不使用 -ub 2048，并保持显存余量。
REM
REM  安全代价（请知悉）：
REM    HVCI 关闭后，有漏洞的内核驱动将不再被虚拟化隔离保护。
REM    对本地跑大模型的开发机而言通常可接受，且完全可逆。
REM    若你依赖 Windows 沙盒 / WSL2 / 智能卡登录，请勿执行本脚本。
REM
REM  回滚：运行 restore_vbs.bat，然后重启。
REM ============================================================

net session >nul 2>&1
if errorlevel 1 (
    echo [!] 需要管理员权限。请右键本文件 -^> 以管理员身份运行
    pause
    exit /b 1
)

echo ============================================================
echo   关闭 VBS / HVCI（内核隔离·内存完整性）
echo ============================================================
echo.

echo [0/3] 备份当前设置到 %~dp0vbs_backup.txt ...
(
  echo ==== VBS backup  %DATE% %TIME% ====
  reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity
  reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v RequirePlatformSecurityFeatures
  reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled
) > "%~dp0vbs_backup.txt" 2>&1
type "%~dp0vbs_backup.txt"
echo.

echo [1/3] 关闭内存完整性 HVCI ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 0 /f

echo [2/3] 关闭 VBS 主体 ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity /t REG_DWORD /d 0 /f
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v RequirePlatformSecurityFeatures /t REG_DWORD /d 0 /f

echo [3/3] 校验 ...
reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity
reg query "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled

echo.
echo ============================================================
echo   [完成] 需要重启才会生效。
echo ============================================================
echo.
echo   重启后请验证（在 PowerShell 里执行）：
echo     Get-CimInstance Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard ^|
echo       Select-Object VirtualizationBasedSecurityStatus
echo     预期输出 0（关闭）。若仍为 2，说明被策略或"设置-安全中心"顶回，
echo     需到 [Windows 安全中心] - [设备安全性] - [内核隔离] 手动关闭。
echo.
echo   若重启后仍出现 HYPERVISOR_ERROR 蓝屏，说明 hypervisor 仍被
echo   VirtualMachinePlatform 拉起，可再执行（需管理员，风险更高）：
echo     bcdedit /set hypervisorlaunchtype off
echo   注意：该命令会一并禁用 WSL2 / Windows 沙盒 / Hyper-V。
echo.
pause
endlocal
"""

# ------------------------------------------------------------------ 3. restore_vbs.bat
RESTVBS = r"""@echo off
setlocal
chcp 936 >nul

REM ============================================================
REM  恢复「内核隔离 / 内存完整性」(VBS + HVCI) —— 需管理员权限
REM  这是 disable_vbs.bat 的回滚脚本。
REM ============================================================

net session >nul 2>&1
if errorlevel 1 (
    echo [!] 需要管理员权限。请右键本文件 -^> 以管理员身份运行
    pause
    exit /b 1
)

echo ============================================================
echo   恢复 VBS / HVCI（内核隔离·内存完整性）
echo ============================================================
echo.

echo [1/3] 恢复内存完整性 HVCI ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity" /v Enabled /t REG_DWORD /d 1 /f

echo [2/3] 恢复 VBS 主体 ...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v EnableVirtualizationBasedSecurity /t REG_DWORD /d 1 /f
reg add "HKLM\SYSTEM\CurrentControlSet\Control\DeviceGuard" /v RequirePlatformSecurityFeatures /t REG_DWORD /d 1 /f

echo [3/3] 恢复 hypervisor 启动类型 ...
bcdedit /set hypervisorlaunchtype auto

echo.
echo ============================================================
echo   [完成] 需要重启才会生效。
echo ============================================================
echo.
pause
endlocal
"""

FILES = [
    ("lock_clocks.bat", LOCK),
    ("disable_vbs.bat", DISVBS),
    ("restore_vbs.bat", RESTVBS),
]

for name, body in FILES:
    p = os.path.join(D, name)
    if os.path.exists(p):
        bak = p + ".bak-20260927-0505"
        if not os.path.exists(bak):
            os.replace(p, bak)
            print("[备份] %s -> %s" % (name, os.path.basename(bak)))
    # 关键：用 GBK 落盘，并用 CRLF 换行（.bat 必须 CRLF）
    data = body.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(p, "wb") as f:
        f.write(data.encode("gbk"))
    print("[写入] %-22s %6d B  GBK+CRLF" % (name, os.path.getsize(p)))

# 验证编码
print()
print("=== 编码校验 ===")
for name, _ in FILES:
    p = os.path.join(D, name)
    b = open(p, "rb").read()
    try:
        b.decode("ascii")
        enc = "ASCII"
    except UnicodeDecodeError:
        try:
            b.decode("gbk")
            enc = "GBK"
        except UnicodeDecodeError:
            enc = "!! 未知 !!"
    print("  %-22s %s" % (name, enc))
