#!/bin/bash

# Conda environment setup script for Coding Agent

set -e

echo "🚀 Setting up Coding Agent with Conda..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Error: Conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first:"
    echo "https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Create conda environment
echo ""
echo "📦 Creating conda environment 'coding-agent'..."
conda env create -f environment.yml

echo ""
echo "✅ Conda environment created successfully!"
echo ""
echo "To activate the environment, run:"
echo "  conda activate coding-agent"
echo ""
echo "Then follow these steps:"
echo ""
echo "1. Setup Backend:"
echo "   cd backend"
echo "   cp .env.example .env"
echo "   # Edit .env to match your vLLM endpoints"
echo ""
echo "2. Setup Frontend:"
echo "   cd frontend"
echo "   npm install"
echo ""
echo "3. Start Backend:"
echo "   cd backend"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "4. Start Frontend (in another terminal):"
echo "   conda activate coding-agent"
echo "   cd frontend"
echo "   npm run dev"
echo ""
