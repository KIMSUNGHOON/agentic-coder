#!/bin/bash
# Stop vLLM servers for Agentic 2.0

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛑 Stopping vLLM Servers${NC}"
echo "========================================"
echo ""

# Find all vLLM processes
PIDS=$(pgrep -f 'vllm serve' || true)

if [ -z "$PIDS" ]; then
    echo -e "${YELLOW}⚠️  No vLLM servers are currently running${NC}"
    echo ""
    exit 0
fi

echo "Found vLLM processes:"
ps aux | grep 'vllm serve' | grep -v grep
echo ""

# Kill processes
echo -e "${BLUE}Stopping servers...${NC}"
pkill -f 'vllm serve'

# Wait for processes to stop
sleep 2

# Verify all stopped
REMAINING=$(pgrep -f 'vllm serve' || true)
if [ -z "$REMAINING" ]; then
    echo -e "${GREEN}✅ All vLLM servers stopped successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Some processes still running, forcing stop...${NC}"
    pkill -9 -f 'vllm serve'
    sleep 1
    echo -e "${GREEN}✅ Forced stop complete${NC}"
fi

echo ""
