@echo off
REM ============================================
REM Mock Server Runner for Windows
REM ============================================
REM vLLM 없이 Frontend UI/UX 테스트 가능

echo.
echo ========================================
echo     Mock Server for TestCodeAgent
echo ========================================
echo.

cd /d "%~dp0frontend"

REM Check if node_modules exists
if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
)

echo [INFO] Starting Mock API Server + Frontend...
echo.
echo   Mock API: http://localhost:8000/api
echo   Frontend: http://localhost:5173
echo.
echo Press Ctrl+C to stop.
echo.

call npm start
