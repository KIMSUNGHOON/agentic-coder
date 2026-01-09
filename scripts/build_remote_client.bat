@echo off
REM Build Remote CLI Client as standalone executable (Windows)

echo 🔨 Building Agentic Coder Remote Client...

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo ❌ PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Navigate to project root
cd /d "%~dp0\.."

REM Create dist directory if it doesn't exist
if not exist dist mkdir dist

REM Build the executable
echo 📦 Packaging executable...
pyinstaller ^
    --name agentic-coder-client ^
    --onefile ^
    --console ^
    --clean ^
    --noconfirm ^
    --add-data "backend/cli/remote_client.py;." ^
    backend/cli/remote_client.py

echo.
echo ✅ Build complete!
echo.
echo 📍 Executable location:
echo    dist\agentic-coder-client.exe
echo.
echo 📋 Usage:
echo    dist\agentic-coder-client.exe
echo    dist\agentic-coder-client.exe ^<server-ip^> ^<port^>
echo.
echo 📤 Distribution:
echo    Copy the .exe file to any Windows machine (no Python required!)
echo.
pause
