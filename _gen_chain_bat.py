# 生成「一键启动链」启动器（GBK 编码，避免中文注释在 GBK 控制台被当命令执行）
#
# v2 —— 2026-09-27 12:30 升级
#   起因：12:21 的一次真实 Agent 请求，上游卡在 prefill 边界僵死（GPU 100% 空转、
#         功耗仅 38W、显存 7728/8151 MiB 顶格，prompt_seconds_total 与
#         requests_processing 双双冻住），请求永远不出结果。旧版脚本看到
#         "8081 已在监听" 就直接跳过，僵尸会被一直沿用。
#   本版新增：
#     0) 僵尸上游探测 —— 用一个 10 秒超时的微型推理请求探活；超时即判定僵死，
#        自动清掉 :8080 / :8081 再重建（不用手工 taskkill）。
#     3) 代理强制重启 —— 保证 --strip-location 瘦身开关一定生效，不会留着旧行为。
import os

BAT = r"""@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title Bonsai 2 27B - Agent 一键启动（上游 + 预热 + 代理）

set "BIN=D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin"
set "MODEL=D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
set "PY=C:\Users\intpj\AppData\Local\Programs\Python\Python310\python.exe"
set "DEMO=D:\Bonsai-demo"

rem ---------------- 思考档位（治"雷霆大思考"）----------------
rem 模型模板原生支持 reasoning_effort，三档 xhigh / medium / low，【默认 xhigh】。
rem xhigh 会往 system 里注入"请仔细思考、验证假设、考虑替代方案"——"雷霆"就是它催的。
rem medium 不注入任何指令（模型自然行为）；low 注入"保持简短"；off 关闭思考。
rem 本机实测（_effort_test.py，同一批 4 档对照）：
rem   xhigh 默认 : 思考 1000 / 1034 tok   28.2 / 29.7 s   两轮全对
rem   medium     : 思考  612 /  442 tok   18.8 / 14.3 s   两轮全对  ← 推荐
rem   low        : 思考  758     tok      22.1 s          对，但思维链漂成英文
rem   off 关思考 : 思考    0     tok      21.6 / 3.8 s    一次答错(第3题写 66)，方差极大
rem 想恢复默认行为：把下一行的 medium 改成 xhigh。
rem 注意：档位是拼在 system 前缀里的，所以一轮会话里【固定一档】，
rem       中途切换会让整个 KV 前缀作废（要重跑一次全量 prefill）。
set "EFFORT=medium"

rem Python 子进程的输出编码：本窗口是 chcp 936(GBK)，
rem 不设这一项时 Python 按 UTF-8 输出 → 中文乱码。
set "PYTHONIOENCODING=gbk"

echo ============================================================
echo   Bonsai 2 27B  Agent 一键启动
echo     0) 僵尸上游探测 + 自动清理
echo     1) llama-server  :8081
echo     2) 预热 KV 缓存（把约 113 秒冷启动挪到现在）
echo     3) 预热代理      :8080  ← WorkBuddy 指向这里（含请求瘦身）
echo     4) 思考档位      %EFFORT%（默认档是 xhigh，最啰嗦）
echo ============================================================
echo.

rem ---------------- 0) 僵尸探测 ----------------
set "NEED_UP=1"
netstat -ano | findstr /r /c:"127.0.0.1:8081 .*LISTENING" >nul 2>&1
if errorlevel 1 goto START_UP

echo [0/3] :8081 在监听，探活中（最长 10 秒）...
curl -s --noproxy "*" --max-time 10 -X POST http://127.0.0.1:8081/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"bonsai-2-27b\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1,\"stream\":false}" >nul 2>&1
if not errorlevel 1 (
  echo       健康：上游可用，跳过启动。
  set "NEED_UP=0"
) else (
  echo       !! 探活超时 —— 判定为僵死（显存顶格导致的 GPU 空转）。
  echo          自动清理 :8080 / :8081 后重建。
  call :KILLPORT 8080
  call :KILLPORT 8081
)

:START_UP
if "%NEED_UP%"=="1" (
  echo [1/3] 启动 llama-server ...
  start "bonsai-upstream" /min "%BIN%\llama-server.exe" -m "%MODEL%" -ngl 99 -fa on -np 1 -c 65536 -b 2048 -ub 512 -ctk q4_0 -ctv q4_0 --backend-sampling --jinja --metrics --host 127.0.0.1 --port 8081 --alias bonsai-2-27b
) else (
  echo [1/3] 复用已在运行的上游。
)

:WAIT
echo       等待模型加载（首次约 30~60 秒）...
set /a N=0
:LOOP
set /a N+=1
curl -s --noproxy "*" --max-time 3 http://127.0.0.1:8081/health 2>nul | findstr /c:"ok" >nul 2>&1
if not errorlevel 1 goto UP
if %N% GEQ 60 goto TIMEOUT
ping -n 3 127.0.0.1 >nul 2>&1
goto LOOP

:UP
echo       上游就绪。
echo.
echo [2/3] 预热 KV 缓存（用【最新一份】真实请求体重放，max_tokens=1）...
rem 注意：预热源必须是"与当前 WorkBuddy 版本一致"的最新请求。
rem   实测 05:31 的 system 35,369 字符 vs 12:21 的 52,514 字符，公共前缀只剩
rem   1,382 字符 —— 拿旧版预热等于完全没热。warm_kv.py 会自动取 mtime 最新的大请求。
"%PY%" -u "%DEMO%\warm_kv.py"
echo.
echo [3/3] 启动预热代理 :8080 ...
netstat -ano | findstr /r /c:"127.0.0.1:8080 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo       :8080 已在监听 —— 重启代理，确保请求瘦身开关生效。
  call :KILLPORT 8080
)
start "bonsai-proxy" /min "%PY%" -u "%DEMO%\proxy\bonsai_proxy.py" --port 8080 --upstream 8081 --warm --effort %EFFORT%
echo.
echo ============================================================
echo   就绪：在 WorkBuddy 里把模型选为 "Bonsai 2 27B (本地)"
echo   代理 :8080 --^> 上游 :8081     KV 缓存已预热
echo   思考档位 %EFFORT%（由代理注入，WorkBuddy 侧无需任何配置）
echo   请求瘦身 开（剥离 (location: ...) 约省 5,050 tok/次，约 11 秒 prefill）
echo   体检缓存冷热：  python -u "%DEMO%\warm_kv.py" --check
echo ============================================================
pause
exit /b 0

:TIMEOUT
echo.
echo ！！等待上游超时。请检查 llama-server 是否闪退（显存不足常见）。
echo    可先用 nvidia-smi 确认空闲显存，再重跑本脚本。
pause
exit /b 1

:KILLPORT
rem 按端口号(%~1)反查 PID 并强杀。netstat 输出里端口后紧跟空格，可避免 8080 误匹配 80800。
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%~1 " ^| findstr "LISTENING"') do (
  echo       kill :%~1  pid=%%p
  taskkill /f /pid %%p >nul 2>&1
)
exit /b 0
"""

out = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_all_agent.bat"
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="gbk", newline="\r\n") as f:
    f.write(BAT)

# 校验编码可逆 + 行尾
raw = open(out, "rb").read()
print("已写出:", out)
print("字节数:", len(raw))
print("CRLF 行数:", raw.count(b"\r\n"))
print("GBK 回读校验:", "OK" if raw.decode("gbk").replace("\r\n", "\n") == BAT else "FAIL")

# 把已被实验否证的 slim 启动器标记为弃用（不删除，保留可追溯）
old = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\start_workbuddy_slim.bat"
dep = old + ".DEPRECATED"
if os.path.exists(old) and not os.path.exists(dep):
    os.rename(old, dep)
    print("已改名(弃用):", dep)
elif os.path.exists(dep):
    print("弃用标记已存在:", dep)
