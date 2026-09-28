# -*- coding: utf-8 -*-
"""以 GBK 编码重写两个 .bat（Windows cmd 默认按系统 ANSI=GBK 解析批处理）"""
import io
import os

BASE = r'D:\Bonsai-demo'

COMMON_HEAD = r'''@echo off
setlocal EnableDelayedExpansion
cd /d D:\Bonsai-demo

REM ===================================================================
REM  {TITLE}
REM  {DESC}
REM
REM  【关键】-ngl 用 52 而不是 99：
REM  8GB 显存装不下 7.2GB 的 PQ2_0 权重 + KV + 计算缓冲。强行 -ngl 99 会让
REM  Windows WDDM 显存溢出，权重每 token 经 PCIe 反复搬运，decode 速度从
REM  11 t/s 暴跌到 1.4 t/s，比纯 CPU 还慢。实测 RTX 5060 Laptop 8GB：
REM    ngl 48 =  9.7 t/s     ngl 52 = 11.1 t/s（显存余量 1000 MiB）
REM    ngl 56 = 13.4 t/s     ngl 58 = 14.2 t/s（余量只剩 600-750 MiB）
REM    ngl 62 = 12.8 t/s     ngl 64 =  1.4 t/s（悬崖档，禁止使用）
REM  想更快：关掉浏览器等占显存程序后，把 -ngl 改成 56 或 58
REM ===================================================================

set "BIN=bin\cuda"
set "MODELDIR=models\bonsai2-gguf\27B"

set BONSAI_KV4=1
set BONSAI_MMPROJ_CPU=1
set BONSAI_MODEL=27B
set BONSAI_FAMILY=bonsai2

set "NEWPATH=%CD%\%BIN%"
for /d %%d in ("%CD%\%BIN%\*") do set "NEWPATH=!NEWPATH!;%%d"
set "PATH=%NEWPATH%;%PATH%"

set "MODEL="
for %%f in ("%MODELDIR%\*PQ2_0.gguf") do set "MODEL=%%f"
set "MMPROJ="
for %%f in ("%MODELDIR%\*mmproj*.gguf") do set "MMPROJ=%%f"
set "BIASARG="
if exist "%MODELDIR%\Bonsai-2-27B-kv-bias.gguf" set "BIASARG=--kv-mean-center %MODELDIR%\Bonsai-2-27B-kv-bias.gguf"

if not defined MODEL (
  echo [ERR] 未找到 PQ2_0 模型文件，请检查 %MODELDIR%
  pause
  exit /b 1
)
if not exist "%BIN%\llama-server.exe" (
  echo [ERR] 未找到 llama-server.exe，请检查 %BIN%
  pause
  exit /b 1
)

echo ============================================
echo  {TITLE}
echo  模型: %MODEL%
echo  配置: {CONF}
echo  服务: http://localhost:8080
echo  提示: 关闭浏览器等占用显存的程序，避免触发显存溢出降速
echo ============================================
echo.
if defined BIASARG echo  kvmem 校准偏置: 已加载
if not defined BIASARG echo  kvmem 校准偏置: 未找到，精度略降（可运行校准生成）
echo.

{ARGS}

endlocal
'''

ARGS_MAIN = (r'"%BIN%\llama-server.exe" -m "%MODEL%" --host 127.0.0.1 --port 8080 '
             r'-a bonsai-27b -ngl 52 -fa on -c 16384 -np 1 '
             r'--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 '
             r'-rea on --reasoning-effort medium --reasoning-format deepseek '
             r'--jinja --mmproj "%MMPROJ%" --no-mmproj-offload '
             r'-ctk q4_0 -ctv q4_0 %BIASARG%')

ARGS_FAST = (r'"%BIN%\llama-server.exe" -m "%MODEL%" --host 127.0.0.1 --port 8080 '
             r'-a bonsai-27b -ngl 58 -fa on -c 8192 -np 1 '
             r'--temp 0.7 --top-p 0.80 --top-k 20 --min-p 0.0 '
             r'-rea off '
             r'--jinja --mmproj "%MMPROJ%" --no-mmproj-offload '
             r'-ctk q4_0 -ctv q4_0 %BIASARG%')

files = {
    'start_bonsai.bat': (COMMON_HEAD
                         .replace('{TITLE}', 'Bonsai 2 27B  -  推荐档（精度优先）')
                         .replace('{DESC}', 'kvmem(q4_0 KV) + 16K 上下文 + 部分层 offload + 思考 medium')
                         .replace('{CONF}', 'kvmem / 16K ctx / ngl 52 / 思考 medium / 校准偏置')
                         .replace('{ARGS}', ARGS_MAIN)),
    'start_bonsai_fast.bat': (COMMON_HEAD
                              .replace('{TITLE}', 'Bonsai 2 27B  -  速度档')
                              .replace('{DESC}', '8K 上下文 + ngl 58 + 关闭思考（instruct 采样）')
                              .replace('{CONF}', 'kvmem / 8K ctx / ngl 58 / 思考关闭')
                              .replace('{ARGS}', ARGS_FAST)),
}

for name, content in files.items():
    path = os.path.join(BASE, name)
    content = content.replace('\r\n', '\n').replace('\n', '\r\n')  # 转 CRLF
    data = content.encode('gbk', errors='strict')
    with open(path, 'wb') as f:
        f.write(data)
    print('WROTE %s (%d bytes, gbk)' % (path, len(data)))

# 校验：确认无 CRLF 问题并列出编码
for name in files:
    p = os.path.join(BASE, name)
    raw = open(p, 'rb').read()
    print('%s: crlf=%d lf_only=%d' % (name, raw.count(b'\r\n'), raw.count(b'\n') - raw.count(b'\r\n')))
