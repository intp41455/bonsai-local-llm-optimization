@echo off
REM ============================================================
REM  Bonsai 2 27B - Agent long-context profile
REM  Window 65536 / MTP speculative decoding DISABLED
REM  Measured: decode 38.74 t/s, VRAM 7748 MiB
REM  Use for: WorkBuddy / OpenCode agents (prompt often 40k+ tokens)
REM  Want speed over window? use start_bonsai_8gb.bat (62 t/s / 32k)
REM ============================================================
setlocal
set "BIN=%~dp0bin"
set "MODELS=D:\Bonsai-demo\models\bonsai2-gguf\27B"
if "%PORT%"=="" set "PORT=8080"
if "%CTX%"==""  set "CTX=65536"

echo.
echo  Bonsai 2 27B (PTQ1_0) / llama.cpp bonsai-combo / sm_120a native
echo  [Agent profile] window %CTX% / q4_0 KV / MTP off
echo  listen http://127.0.0.1:%PORT%   alias bonsai-2-27b
echo.

"%BIN%\llama-server.exe" ^
  -m "%MODELS%\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf" ^
  -ngl 99 -fa on -np 1 ^
  -c %CTX% -b 2048 -ub 512 ^
  -ctk q4_0 -ctv q4_0 ^
  --backend-sampling ^
  --jinja ^
  --chat-template-kwargs "{\"reasoning_effort\":\"medium\"}" ^
  --reasoning-budget 20480 ^
  --reasoning-budget-message "Now produce the complete answer." ^
  -n 24576 ^
  --temp 1.0 --top-p 0.95 --top-k 20 ^
  --host 127.0.0.1 --port %PORT% --alias bonsai-2-27b ^
  --metrics

endlocal
