#!/bin/bash

# Development server startup script

# Copy .env.example to .env if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file from .env.example"
fi

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run the server
echo "Starting FastAPI server..."
cd /home/user/TestCodeAgent/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
