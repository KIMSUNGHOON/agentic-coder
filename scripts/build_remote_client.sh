#!/bin/bash
# Build Remote CLI Client as standalone executable

set -e

echo "🔨 Building Agentic Coder Remote Client..."

# Check if PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "❌ PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Navigate to project root
cd "$(dirname "$0")/.."

# Create dist directory if it doesn't exist
mkdir -p dist

# Build the executable
echo "📦 Packaging executable..."
pyinstaller \
    --name agentic-coder-client \
    --onefile \
    --console \
    --clean \
    --noconfirm \
    --add-data "backend/cli/remote_client.py:." \
    backend/cli/remote_client.py

echo ""
echo "✅ Build complete!"
echo ""
echo "📍 Executable location:"
echo "   Linux/Mac: dist/agentic-coder-client"
echo "   Windows: dist/agentic-coder-client.exe"
echo ""
echo "📋 Usage:"
echo "   ./dist/agentic-coder-client"
echo "   ./dist/agentic-coder-client <server-ip> <port>"
echo ""
echo "📤 Distribution:"
echo "   Copy the executable to any machine (no Python required!)"
echo "   Example: scp dist/agentic-coder-client user@remote-machine:~/"
echo ""
