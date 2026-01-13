#!/bin/bash
set -e

# Agentic Coder Server Startup Script
# Performs environment checks and starts the server

echo "🚀 Agentic Coder Server Startup"
echo "================================"
echo ""

# Color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
DOCKER_AVAILABLE=false
IMAGE_EXISTS=false
CONTAINER_RUNNING=false
WARNINGS=()

# 1. Check Docker installation
echo "🔍 Checking Docker installation..."
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null 2>&1; then
        echo -e "${GREEN}✅ Docker is installed and running${NC}"
        DOCKER_AVAILABLE=true
    else
        echo -e "${YELLOW}⚠️  Docker is installed but not running${NC}"
        echo -e "   ${BLUE}Solution:${NC} sudo systemctl start docker"
        WARNINGS+=("Docker not running")
    fi
else
    echo -e "${YELLOW}⚠️  Docker is not installed${NC}"
    echo -e "   ${BLUE}Info:${NC} Sandbox features will be unavailable"
    echo -e "   ${BLUE}Install:${NC} sudo apt-get update && sudo apt-get install -y docker.io"
    WARNINGS+=("Docker not installed")
fi
echo ""

# 2. Check Sandbox image (only if Docker available)
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "🔍 Checking Sandbox Docker image..."
    if docker images ghcr.io/agent-infra/sandbox:latest --format "{{.Repository}}" | grep -q "agent-infra/sandbox"; then
        IMAGE_SIZE=$(docker images ghcr.io/agent-infra/sandbox:latest --format "{{.Size}}")
        echo -e "${GREEN}✅ Sandbox image exists${NC} (size: ${IMAGE_SIZE})"
        IMAGE_EXISTS=true
    else
        echo -e "${YELLOW}⚠️  Sandbox image not found${NC}"
        echo -e "   ${BLUE}Download:${NC} docker pull ghcr.io/agent-infra/sandbox:latest"
        echo -e "   ${BLUE}Note:${NC} Python code will work via fallback mode"
        WARNINGS+=("Sandbox image missing")
    fi
    echo ""

    # 3. Check Sandbox container status
    echo "🔍 Checking Sandbox container..."
    if docker ps --filter "name=agentic-coder-sandbox" --format "{{.Names}}" | grep -q "agentic-coder-sandbox"; then
        CONTAINER_ID=$(docker ps --filter "name=agentic-coder-sandbox" --format "{{.ID}}")
        echo -e "${GREEN}✅ Sandbox container is running${NC} (ID: ${CONTAINER_ID})"
        CONTAINER_RUNNING=true
    elif docker ps -a --filter "name=agentic-coder-sandbox" --format "{{.Names}}" | grep -q "agentic-coder-sandbox"; then
        echo -e "${YELLOW}⚠️  Sandbox container exists but not running${NC}"
        echo -e "   ${BLUE}Starting container...${NC}"
        docker start agentic-coder-sandbox &> /dev/null && echo -e "${GREEN}✅ Container started${NC}" || echo -e "${RED}❌ Failed to start container${NC}"
    else
        echo -e "${BLUE}ℹ️  Sandbox container not found${NC}"
        echo -e "   ${BLUE}Note:${NC} Container will be created automatically on first use"
    fi
    echo ""
fi

# 4. Check Python environment
echo "🔍 Checking Python environment..."
if [ -d "backend/venv" ]; then
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment not found${NC}"
    echo -e "   ${BLUE}Create:${NC} cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    WARNINGS+=("venv not found")
fi
echo ""

# 5. Check .env file
echo "🔍 Checking configuration..."
if [ -f "backend/.env" ]; then
    echo -e "${GREEN}✅ .env configuration exists${NC}"
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo -e "   ${BLUE}Create:${NC} cp backend/.env.example backend/.env"
    WARNINGS+=(".env missing")
fi
echo ""

# Summary
echo "================================"
echo "📊 Environment Status Summary"
echo "================================"
echo ""

if [ ${#WARNINGS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Environment is ready.${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠️  ${#WARNINGS[@]} warning(s) detected:${NC}"
    for warning in "${WARNINGS[@]}"; do
        echo -e "   - ${warning}"
    done
    echo ""
    echo -e "${BLUE}ℹ️  Server can still start with limited functionality:${NC}"
    echo -e "   ${GREEN}✅${NC} File operations (read, write, search)"
    echo -e "   ${GREEN}✅${NC} Python code execution (fallback mode)"
    echo -e "   ${GREEN}✅${NC} Git operations"
    if [ "$DOCKER_AVAILABLE" = false ]; then
        echo -e "   ${YELLOW}⚠️${NC}  Sandbox (isolated execution) - unavailable"
    elif [ "$IMAGE_EXISTS" = false ]; then
        echo -e "   ${YELLOW}⚠️${NC}  Sandbox (isolated execution) - unavailable"
    fi
    echo ""
fi

# Ask to continue if warnings exist
if [ ${#WARNINGS[@]} -gt 0 ]; then
    read -p "Continue starting server? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Startup cancelled by user${NC}"
        exit 1
    fi
    echo ""
fi

# Start server
echo "================================"
echo "🚀 Starting Agentic Coder Server"
echo "================================"
echo ""
echo -e "${BLUE}Server will start on:${NC} http://0.0.0.0:8000"
echo -e "${BLUE}Health check:${NC} http://localhost:8000/health"
echo -e "${BLUE}API docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Change to backend directory and start server
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
