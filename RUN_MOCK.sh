#!/bin/bash

# Mock Mode Launcher for macOS and Linux
# This script runs the application with mock API (no vLLM required)

set -e

echo "════════════════════════════════════════════════════════════"
echo "  🎭 Coding Agent - Mock Mode"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  Starting application with mock API server..."
echo "  No vLLM server required!"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Change to frontend directory
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

# Start the application
echo "🚀 Starting servers..."
echo ""
echo "  Mock API: http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

npm start
