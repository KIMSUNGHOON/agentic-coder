#!/bin/bash

# Backend-only Conda environment setup script

set -e

echo "🚀 Setting up Backend with Conda..."

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Error: Conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first:"
    echo "https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Create conda environment
echo ""
echo "📦 Creating conda environment 'coding-agent-backend'..."
conda env create -f environment.yml

# Setup .env file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from .env.example"
else
    echo "ℹ️  .env file already exists"
fi

echo ""
echo "✅ Backend environment setup complete!"
echo ""
echo "To activate and run the backend:"
echo "  conda activate coding-agent-backend"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
