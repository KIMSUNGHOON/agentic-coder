#!/bin/bash
# Start vLLM servers for Agentic 2.0
#
# Usage:
#   ./start_vllm.sh              # Start both endpoints
#   ./start_vllm.sh primary       # Start primary only
#   ./start_vllm.sh secondary     # Start secondary only

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration (from config/config.yaml)
MODEL_NAME="${VLLM_MODEL:-openai/gpt-oss-120b}"
PRIMARY_PORT=8001
SECONDARY_PORT=8002

# Determine which servers to start
START_PRIMARY=true
START_SECONDARY=true

if [ "$1" = "primary" ]; then
    START_SECONDARY=false
elif [ "$1" = "secondary" ]; then
    START_PRIMARY=false
fi

echo -e "${BLUE}🚀 Starting vLLM Servers for Agentic 2.0${NC}"
echo "=========================================="
echo ""

# Check if vLLM is installed
if ! command -v vllm &> /dev/null; then
    echo -e "${RED}❌ vLLM is not installed${NC}"
    echo ""
    echo "Install with:"
    echo "  pip install vllm"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ vLLM is installed${NC}"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to start vLLM server
start_vllm() {
    local name=$1
    local port=$2
    local log_file="logs/vllm_${name}.log"

    # Create logs directory
    mkdir -p logs

    echo -e "${BLUE}Starting ${name} endpoint on port ${port}...${NC}"

    # Check if port is already in use
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port ${port} is already in use${NC}"
        echo -e "   Assuming ${name} vLLM server is already running"
        echo ""
        return
    fi

    # Start vLLM in background
    nohup vllm serve ${MODEL_NAME} \
        --port ${port} \
        --host 0.0.0.0 \
        > ${log_file} 2>&1 &

    local pid=$!
    echo -e "${GREEN}✅ Started ${name} vLLM server (PID: ${pid})${NC}"
    echo -e "   Port: ${port}"
    echo -e "   Log: ${log_file}"
    echo ""

    # Wait a moment for server to start
    sleep 2

    # Check if process is still running
    if ! ps -p $pid > /dev/null; then
        echo -e "${RED}❌ Failed to start ${name} server${NC}"
        echo -e "   Check log: ${log_file}"
        echo ""
        return 1
    fi
}

# Start servers
if [ "$START_PRIMARY" = true ]; then
    start_vllm "primary" $PRIMARY_PORT
fi

if [ "$START_SECONDARY" = true ]; then
    start_vllm "secondary" $SECONDARY_PORT
fi

echo "=========================================="
echo -e "${GREEN}✅ vLLM servers started successfully${NC}"
echo ""
echo "Endpoints:"
if [ "$START_PRIMARY" = true ]; then
    echo -e "  ${GREEN}●${NC} Primary:   http://localhost:${PRIMARY_PORT}/v1"
fi
if [ "$START_SECONDARY" = true ]; then
    echo -e "  ${GREEN}●${NC} Secondary: http://localhost:${SECONDARY_PORT}/v1"
fi
echo ""
echo "To check status:"
echo "  curl http://localhost:${PRIMARY_PORT}/v1/models"
echo ""
echo "To stop servers:"
echo "  pkill -f 'vllm serve'"
echo ""
echo "Now you can run the CLI:"
echo -e "  ${BLUE}python -m cli.app${NC}"
echo ""
