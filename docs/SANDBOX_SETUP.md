# Sandbox Setup Guide

Complete guide for setting up isolated code execution environment using Docker and AIO Sandbox.

---

## Overview

The Sandbox provides isolated, secure code execution for:
- **Python** (via Jupyter API)
- **Node.js** (via Shell API)
- **TypeScript** (via ts-node)
- **Shell commands** (via bash)

**Benefits:**
- ✅ Secure isolated execution
- ✅ Resource limits (CPU, memory)
- ✅ Network isolation
- ✅ Automatic cleanup

---

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 22.04 LTS recommended), macOS, or Windows with WSL2
- **RAM**: 2GB+ available (1GB for container)
- **Disk**: 10GB+ free space
- **Network**: Internet access (for initial image download only)

### Software Requirements
- **Docker**: 19.03 or later
- **Python**: 3.8+

---

## Installation

### Step 1: Install Docker

#### Ubuntu/Debian
```bash
# Update package list
sudo apt-get update

# Install Docker
sudo apt-get install -y docker.io

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group (requires re-login)
sudo usermod -aG docker $USER

# Verify installation
docker --version
docker ps
```

#### macOS
```bash
# Install Docker Desktop
brew install --cask docker

# Start Docker Desktop application
open /Applications/Docker.app

# Verify installation
docker --version
docker ps
```

#### Windows (WSL2)
1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
2. Enable WSL2 backend
3. Verify in PowerShell:
   ```powershell
   docker --version
   docker ps
   ```

---

### Step 2: Pull Sandbox Image

```bash
# Pull the official AIO Sandbox image
docker pull ghcr.io/agent-infra/sandbox:latest

# Verify image is downloaded
docker images | grep sandbox
```

**Expected output:**
```
ghcr.io/agent-infra/sandbox   latest   abc123def456   2 weeks ago   1.2GB
```

**Note**: First download may take 5-10 minutes depending on network speed.

---

### Step 3: Verify Setup

#### Automated Check (Recommended)
```bash
# Run smart startup script
cd /home/user/agentic-coder
./scripts/start_server.sh
```

The script will automatically check:
- ✅ Docker installation and running status
- ✅ Sandbox image existence
- ✅ Container status
- ✅ Python environment
- ✅ Configuration files

#### Manual Check
```bash
# Check Docker
docker ps

# Check image
docker images ghcr.io/agent-infra/sandbox:latest

# Check container (if exists)
docker ps -a | grep agentic-coder-sandbox
```

#### Health Check API
```bash
# Start server (if not already running)
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Check health endpoint
curl http://localhost:8000/health | jq .components.sandbox
```

**Healthy response:**
```json
{
  "status": "operational",
  "docker": {
    "available": true,
    "status": "running",
    "message": "Docker is available and running"
  },
  "image": {
    "exists": true,
    "image": "ghcr.io/agent-infra/sandbox:latest",
    "size": "1.2GB",
    "created": "2 weeks ago"
  },
  "container": {
    "running": true,
    "exists": true,
    "container_id": "abc123",
    "status": "Up 2 hours"
  },
  "recommendations": []
}
```

---

## Configuration

### Environment Variables

Create or update `backend/.env`:

```bash
# Sandbox Configuration
SANDBOX_IMAGE=ghcr.io/agent-infra/sandbox:latest
SANDBOX_HOST=localhost
SANDBOX_PORT=8080
SANDBOX_TIMEOUT=60
SANDBOX_MEMORY=1g
SANDBOX_CPU=2.0

# Custom registry (for offline environments)
# SANDBOX_REGISTRY=harbor.company.com
```

### Custom Registry (Offline Environments)

If you're in an air-gapped environment:

```bash
# 1. Push to internal registry
docker tag ghcr.io/agent-infra/sandbox:latest your-registry.com/sandbox/aio:latest
docker push your-registry.com/sandbox/aio:latest

# 2. Update .env
SANDBOX_REGISTRY=your-registry.com
```

---

## Usage

### Automatic Container Management

The Sandbox container is managed automatically:

1. **First use**: Container is created automatically
2. **Subsequent uses**: Existing container is reused
3. **Restart**: Container restarts automatically if stopped

No manual container management needed!

### Manual Container Management (Optional)

If you need to manually control the container:

```bash
# Start container
docker start agentic-coder-sandbox

# Stop container
docker stop agentic-coder-sandbox

# Restart container
docker restart agentic-coder-sandbox

# View container logs
docker logs agentic-coder-sandbox

# Remove container (will be recreated on next use)
docker rm -f agentic-coder-sandbox
```

---

## Fallback Mode

If Docker is unavailable, Agentic Coder automatically falls back:

| Language | Fallback Behavior |
|----------|------------------|
| **Python** | ✅ Uses `execute_python` (non-isolated) |
| **Node.js** | ❌ Returns error (requires Docker) |
| **TypeScript** | ❌ Returns error (requires Docker) |
| **Shell** | ❌ Returns error (requires Docker) |

**Warning**: Fallback mode runs code directly on the system without isolation!

---

## Troubleshooting

### Docker Not Found

**Symptom:**
```
docker: command not found
```

**Solution:**
```bash
# Install Docker (Ubuntu)
sudo apt-get update && sudo apt-get install -y docker.io

# Verify
docker --version
```

---

### Docker Permission Denied

**Symptom:**
```
Got permission denied while trying to connect to the Docker daemon socket
```

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and log back in, then verify
docker ps
```

---

### Docker Not Running

**Symptom:**
```
Cannot connect to the Docker daemon
```

**Solution:**
```bash
# Ubuntu/Linux
sudo systemctl start docker
sudo systemctl enable docker

# macOS
open /Applications/Docker.app

# Windows
# Start Docker Desktop application
```

---

### Image Pull Failed

**Symptom:**
```
Error response from daemon: Get "https://ghcr.io/v2/": net/http: request canceled
```

**Solutions:**

1. **Check network connection:**
   ```bash
   ping ghcr.io
   ```

2. **Try with proxy (if behind corporate firewall):**
   ```bash
   # Configure Docker proxy in /etc/systemd/system/docker.service.d/http-proxy.conf
   [Service]
   Environment="HTTP_PROXY=http://proxy.company.com:8080"
   Environment="HTTPS_PROXY=http://proxy.company.com:8080"

   # Restart Docker
   sudo systemctl daemon-reload
   sudo systemctl restart docker
   ```

3. **Use alternative registry:**
   ```bash
   # Update .env with custom registry
   SANDBOX_REGISTRY=your-registry.com
   ```

---

### Container Won't Start

**Symptom:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:8080: bind: address already in use
```

**Solution:**
```bash
# Find process using port 8080
sudo lsof -i :8080

# Kill the process or change port
# Update .env:
SANDBOX_PORT=8081
```

---

### Container Crash Loop

**Symptom:**
Container starts but immediately stops.

**Solution:**
```bash
# Check container logs
docker logs agentic-coder-sandbox

# Remove and recreate
docker rm -f agentic-coder-sandbox

# Next use will recreate with fresh state
```

---

## Performance Tuning

### Resource Limits

Adjust in `backend/.env`:

```bash
# High-performance (for heavy workloads)
SANDBOX_MEMORY=2g
SANDBOX_CPU=4.0
SANDBOX_TIMEOUT=120

# Low-resource (for limited environments)
SANDBOX_MEMORY=512m
SANDBOX_CPU=1.0
SANDBOX_TIMEOUT=30
```

### Persistent Storage (Optional)

To preserve files between container restarts:

```bash
docker run -d \
  --name agentic-coder-sandbox \
  -p 8080:8080 \
  -v /path/to/persistent:/workspace \
  --memory=1g \
  --cpus=2.0 \
  ghcr.io/agent-infra/sandbox:latest
```

---

## Security Considerations

### Isolation

The Sandbox provides:
- ✅ Process isolation (separate container)
- ✅ Filesystem isolation (no access to host)
- ✅ Network isolation (optional)
- ✅ Resource limits (CPU, memory)

### Limitations

The Sandbox does NOT provide:
- ❌ Protection against malicious code (use with trusted code only)
- ❌ Full security audit (not suitable for untrusted user code)
- ❌ Multi-tenancy guarantees

**Recommendation**: Use Sandbox for development and testing, not for production execution of untrusted code.

---

## Verification Checklist

After setup, verify:

- [ ] Docker installed and running: `docker ps`
- [ ] Sandbox image downloaded: `docker images | grep sandbox`
- [ ] Server starts without errors: `./scripts/start_server.sh`
- [ ] Health check shows "operational": `curl http://localhost:8000/health`
- [ ] Python execution works: Test via CLI or API
- [ ] Container auto-starts on first use

---

## Next Steps

1. **Start using Sandbox:**
   ```bash
   # Via CLI
   cd backend
   python cli/cli.py

   # Ask: "Run this Python code: print('Hello from Sandbox!')"
   ```

2. **Monitor health:**
   ```bash
   # Check status anytime
   curl http://localhost:8000/health | jq .components.sandbox
   ```

3. **Read more:**
   - [Current Issues](CURRENT_ISSUES.md) - Known issues and resolutions
   - [Remote Client](REMOTE_CLIENT_BINARY.md) - Remote client setup
   - [Troubleshooting](TROUBLESHOOTING.md) - Common problems

---

## Support

**Issues?**
- Check [CURRENT_ISSUES.md](CURRENT_ISSUES.md) for known problems
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common fixes
- Report new issues on GitHub

**Questions?**
- Review health check output: `/health`
- Check server logs: `backend/logs/`
- Review Docker logs: `docker logs agentic-coder-sandbox`

---

**Last Updated**: 2026-01-13
**Version**: Phase 2
**Status**: Production Ready ✅
