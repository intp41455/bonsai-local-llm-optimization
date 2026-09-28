# -*- coding: utf-8 -*-
"""生成「精简技能清单预算」的 WorkBuddy 启动器（GBK 落盘，防中文乱码）。"""
import os, sys

sys.stdout.reconfigure(encoding="utf-8")

OUT = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_workbuddy_slim.bat"

BAT = """@echo off
chcp 936 >nul
title WorkBuddy (slim skill budget)

rem ============================================================
rem  以「精简技能清单预算」启动 WorkBuddy
rem
rem  背景：WorkBuddy 会把 Skill 工具里的技能清单
rem        （<available_skills>，148 条）压到固定字符预算，
rem        默认约 3 万字符 = 1.08 万 token，占单次 prompt 的 19%。
rem        本脚本把预算降到 12000 字符，并给最长的两条技能
rem        单独设 120 字符上限。
rem
rem  预期收益：约省 5400 token（占 prompt 约 9%），
rem            零能力损失（技能名仍可被调用）。
rem
rem  生效条件：环境变量是「进程级」的，
rem            必须用本脚本启动 WorkBuddy 才生效。
rem  回滚：   直接双击原来的 WorkBuddy.exe 即可。
rem ============================================================

set "CODEBUDDY_SKILL_TOOL_CHAR_BUDGET=12000"
set "CODEBUDDY_SKILL_DESC_MAX_OVERRIDES={"tencent-docs-routing":120,"tencent-docs-sheetagent":120}"

echo.
echo   CODEBUDDY_SKILL_TOOL_CHAR_BUDGET   = %CODEBUDDY_SKILL_TOOL_CHAR_BUDGET%
echo   CODEBUDDY_SKILL_DESC_MAX_OVERRIDES = %CODEBUDDY_SKILL_DESC_MAX_OVERRIDES%
echo.
echo   正在启动 WorkBuddy ...
echo.

start "" "D:\下载的\WorkBuddy\WorkBuddy.exe"
exit /b 0
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="gbk", newline="\r\n") as f:
    f.write(BAT)

# 校验：按 GBK 回读
with open(OUT, "r", encoding="gbk") as f:
    back = f.read()
ok = back == BAT
print("写入:", OUT)
print("字节数:", os.path.getsize(OUT))
print("GBK 回读一致:", ok)
print("含 BOM:", open(OUT, "rb").read(3) == b"\xef\xbb\xbf")
print()
print("---- 前 12 行 ----")
for l in back.split("\r\n")[:12]:
    print(l)
