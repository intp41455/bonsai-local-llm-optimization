# -*- coding: utf-8 -*-
"""生成抓包模式启动器（GBK 落盘，喂给 cmd 的中文才不会乱码）。"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo"

BAT = r"""@echo off
setlocal
chcp 936 >nul
title Bonsai 2 27B - 抓包模式（判定前缀稳定性）

REM ============================================================
REM  抓包模式：llama-server 挪到 :8081，代理接管 :8080
REM
REM  目的：WorkBuddy 的单次请求约 5.5 万 token，prefill 要 458 秒。
REM        实测已证明 llama-server 对"完全相同的前缀"能 100%% 复用 KV，
REM        但只要前缀有一个字节不同就 100%% 重算。
REM        所以必须抓真实请求体，判定 WorkBuddy 每轮前缀稳不稳。
REM
REM  用法：
REM    1. 以管理员身份双击本脚本（会自动清掉在跑的 llama-server）
REM    2. 等出现 "Bonsai 抓包代理" 字样
REM    3. 打开 WorkBuddy，对本模型连发 2~3 条消息
REM    4. 回到本窗口，按 Ctrl+C，会自动打印前缀稳定性判定
REM       判定文件同时在 D:\Bonsai-demo\capture\verdict.txt
REM
REM  客户端不用改：models.json 里就是 http://127.0.0.1:8080/v1/...
REM ============================================================

set BIN=%~dp0bin\llama-server.exe
set MODEL=D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf
set PY=C:\Users\intpj\AppData\Local\Programs\Python\Python310\python.exe
set LOG=D:\Bonsai-demo\capture\upstream.log

if not exist "D:\Bonsai-demo\capture" mkdir "D:\Bonsai-demo\capture"

echo ============================================================
echo   停止已有 llama-server ...
echo ============================================================
taskkill /F /IM llama-server.exe >nul 2>&1
timeout /t 4 /nobreak >nul

echo.
echo   启动上游 llama-server  :8081  (c65536 / MTP off)
echo   日志: %LOG%
start "bonsai-upstream" /MIN cmd /c ""%BIN%" -m "%MODEL%" -ngl 99 -fa on -np 1 -c 65536 -b 2048 -ub 512 -ctk q4_0 -ctv q4_0 --backend-sampling --jinja --metrics --host 127.0.0.1 --port 8081 --alias bonsai-2-27b > "%LOG%" 2>&1"

echo   等待模型加载 ...
set /a N=0
:waitloop
timeout /t 2 /nobreak >nul
set /a N+=2
curl -s --noproxy "*" --max-time 3 http://127.0.0.1:8081/health | findstr /C:"ok" >nul
if not errorlevel 1 goto ready
if %N% GEQ 180 goto timeout

goto waitloop

:ready
echo   上游就绪（约 %N% 秒）。显存：
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
echo.
echo ============================================================
echo   现在请在 WorkBuddy 里对本模型连发 2 到 3 条消息
echo   发完后回到本窗口按 Ctrl+C 看判定
echo ============================================================
echo.
"%PY%" -u D:\Bonsai-demo\proxy\bonsai_proxy.py --port 8080 --upstream 8081
goto done

:timeout
echo   [错误] 上游 180 秒内未就绪，请看日志: %LOG%
type "%LOG%"
pause
goto done

:done
echo.
echo   收尾：停止上游
taskkill /F /IM llama-server.exe >nul 2>&1
pause
endlocal
"""

p = os.path.join(D, "start_capture.bat")
if os.path.exists(p):
    os.replace(p, p + ".bak")
data = BAT.replace("\r\n", "\n").replace("\n", "\r\n")
with open(p, "wb") as f:
    f.write(data.encode("gbk"))
print("[写入] %s  %d B  GBK+CRLF" % (p, os.path.getsize(p)))
b = open(p, "rb").read()
try:
    b.decode("ascii"); enc = "ASCII"
except UnicodeDecodeError:
    try:
        b.decode("gbk"); enc = "GBK"
    except UnicodeDecodeError:
        enc = "!!未知!!"
print("编码校验:", enc)
