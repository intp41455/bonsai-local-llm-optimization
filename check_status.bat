@echo off
REM Check Bonsai deployment status
echo ============================================
echo   Bonsai 27B Deployment Status Check
echo ============================================
echo.

echo [1] Model files:
if exist "D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PQ2_0.gguf" (
  echo   [OK] Model file exists
  dir "D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PQ2_0.gguf" | findstr "File"
) else (
  echo   [MISSING] Model file not found
)

if exist "D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf" (
  echo   [OK] Vision projector exists
) else (
  echo   [MISSING] Vision projector not found
)

echo.
echo [2] Binary files:
if exist "D:\Bonsai-demo\bin\cuda\llama-server.exe" (
  echo   [OK] llama-server.exe found
) else (
  echo   [MISSING] llama-server.exe - need to extract zip
)

if exist "D:\Bonsai-demo\bin\cuda\cudart64_*.dll" (
  echo   [OK] CUDA runtime DLLs found
) else (
  echo   [MISSING] CUDA runtime DLLs - need to extract cudart.zip
)

echo.
echo [3] Download queue:
if exist "D:\Bonsai-demo\llama-cuda13.zip" (
  echo   [DOWNLOADING] llama-cuda13.zip:
  dir "D:\Bonsai-demo\llama-cuda13.zip" | findstr "File"
) else (
  echo   [NOT STARTED] llama-cuda13.zip
)

if exist "D:\Bonsai-demo\cudart.zip" (
  echo   [DOWNLOADING] cudart.zip:
  dir "D:\Bonsai-demo\cudart.zip" | findstr "File"
) else (
  echo   [NOT STARTED] cudart.zip
)

echo.
echo [4] GPU info:
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

echo.
echo ============================================
pause
