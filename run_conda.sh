#!/bin/bash

# Run the full stack using existing Conda environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Coding Agent (Conda mode)${NC}"
echo ""

# Check if conda environment exists
if ! conda env list | grep -q "coding-agent"; then
    echo -e "${RED}❌ Error: Conda environment 'coding-agent' not found${NC}"
    echo ""
    echo "Please create the environment first:"
    echo "  conda env create -f environment.yml"
    echo ""
    echo "Or activate an existing environment:"
    echo "  conda activate <your-env-name>"
    exit 1
fi

# Check if .env exists
if [ ! -f backend/.env ]; then
    echo -e "${YELLOW}⚠️  Creating backend/.env from .env.example${NC}"
    cp backend/.env.example backend/.env
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
fi

echo ""
echo -e "${GREEN}Starting services...${NC}"
echo ""
echo -e "${YELLOW}Backend will run on: http://localhost:8000${NC}"
echo -e "${YELLOW}Frontend will run on: http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    kill 0
}

trap cleanup EXIT INT TERM

# Start backend in background
echo -e "${GREEN}▶️  Starting Backend...${NC}"
cd backend
conda run -n coding-agent uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 3

# Start frontend in background
echo -e "${GREEN}▶️  Starting Frontend...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}✅ All services started!${NC}"
echo ""
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""

# Wait for both processes
wait
