@echo off
REM Agentic Coder Server Startup Script for Windows
REM Performs environment checks and starts the server

echo ================================
echo Agentic Coder Server Startup
echo ================================
echo.

REM Check Docker installation
echo Checking Docker installation...
docker --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Docker is installed
    docker ps >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Docker is running

        REM Check Sandbox image
        echo.
        echo Checking Sandbox Docker image...
        docker images ghcr.io/agent-infra/sandbox:latest --format "{{.Repository}}" | findstr "agent-infra/sandbox" >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [OK] Sandbox image exists
        ) else (
            echo [WARN] Sandbox image not found
            echo        Download: docker pull ghcr.io/agent-infra/sandbox:latest
            echo        Note: Python code will work via fallback mode
        )

        REM Check Sandbox container
        echo.
        echo Checking Sandbox container...
        docker ps --filter "name=agentic-coder-sandbox" --format "{{.Names}}" | findstr "agentic-coder-sandbox" >nul 2>&1
        if %ERRORLEVEL% EQU 0 (
            echo [OK] Sandbox container is running
        ) else (
            docker ps -a --filter "name=agentic-coder-sandbox" --format "{{.Names}}" | findstr "agentic-coder-sandbox" >nul 2>&1
            if %ERRORLEVEL% EQU 0 (
                echo [INFO] Starting Sandbox container...
                docker start agentic-coder-sandbox >nul 2>&1
                if %ERRORLEVEL% EQU 0 (
                    echo [OK] Container started
                ) else (
                    echo [WARN] Failed to start container
                )
            ) else (
                echo [INFO] Container will be created automatically on first use
            )
        )
    ) else (
        echo [WARN] Docker is installed but not running
        echo        Solution: Start Docker Desktop
    )
) else (
    echo [WARN] Docker is not installed
    echo        Info: Sandbox features will be unavailable
    echo        Install: https://docs.docker.com/desktop/install/windows-install/
)

REM Check Python virtual environment
echo.
echo Checking Python environment...
if exist "backend\venv\" (
    echo [OK] Virtual environment exists
) else (
    echo [WARN] Virtual environment not found
    echo        Create: cd backend ^&^& python -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
)

REM Check .env file
echo.
echo Checking configuration...
if exist "backend\.env" (
    echo [OK] .env configuration exists
) else (
    echo [WARN] .env file not found
    echo        Create: copy backend\.env.example backend\.env
)

REM Summary
echo.
echo ================================
echo Environment Status Summary
echo ================================
echo.
echo Server will start with available features.
echo For full functionality, ensure Docker is installed and running.
echo.

REM Start server
echo ================================
echo Starting Agentic Coder Server
echo ================================
echo.
echo Server will start on: http://0.0.0.0:8000
echo Health check: http://localhost:8000/health
echo API docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Change to backend directory and start server
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
