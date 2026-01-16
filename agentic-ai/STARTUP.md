# Agentic 2.0 Startup Guide

This guide explains how to properly start and run Agentic 2.0 CLI.

## Architecture Overview

Agentic 2.0 requires **two separate components** to run:

1. **vLLM LLM Servers** (localhost:8001 and localhost:8002) - Provides AI inference
2. **Agentic CLI** (cli.app) - User interface and orchestration

**CRITICAL**: You MUST start the vLLM servers BEFORE running the CLI!

## Quick Start (Recommended)

### 1. Start vLLM Servers

```bash
cd /home/user/agentic-coder/agentic-ai
./start_vllm.sh
```

This will:
- Start primary vLLM server on port 8001
- Start secondary vLLM server on port 8002
- Log output to `logs/vllm_primary.log` and `logs/vllm_secondary.log`

**Wait 30-60 seconds** for models to load into memory.

### 2. Verify vLLM is Running

```bash
# Check primary endpoint
curl http://localhost:8001/v1/models

# Check secondary endpoint
curl http://localhost:8002/v1/models
```

You should see JSON response with model information.

### 3. Run Agentic CLI

```bash
python -m cli.app
```

You should see:
```
🚀 Agentic 2.0 - Universal AI Coding Assistant
================================================
Session ID: abc12345
Workspace: /home/user/workspace/abc12345
================================================
```

### 4. Test with "Hello"

Type `Hello` and press Enter. You should get a conversational greeting response, NOT:
```json
{"action":"COMPLETE", "summary":"Hello"}  ❌ WRONG!
```

Correct response should be:
```
Hello! I'm Agentic 2.0, your AI coding assistant. How can I help you today?
```

## Manual Start (Advanced)

If the automated script doesn't work, start vLLM manually:

### Start Primary Server
```bash
vllm serve openai/gpt-oss-120b --port 8001 --host 0.0.0.0
```

### Start Secondary Server (Optional)
Open a new terminal:
```bash
vllm serve openai/gpt-oss-120b --port 8002 --host 0.0.0.0
```

## Stopping Servers

```bash
./stop_vllm.sh
```

Or manually:
```bash
pkill -f 'vllm serve'
```

## Troubleshooting

### Error: "All 4 attempts failed on all endpoints"

**Cause**: vLLM servers are not running or not reachable.

**Solution**:
1. Check if vLLM is running: `ps aux | grep vllm`
2. Check ports: `lsof -i :8001` and `lsof -i :8002`
3. Check logs: `cat logs/vllm_primary.log`
4. Restart: `./stop_vllm.sh && ./start_vllm.sh`

### Error: "object of type 'NoneType' has no len()"

**Status**: FIXED in commit 36a6ce4

**Solution**:
1. Stop the CLI (Ctrl+C)
2. Restart: `python -m cli.app`
3. If error persists, check vLLM servers are running

### Error: Port Already in Use

**Cause**: vLLM servers already running or another process using ports 8001/8002.

**Solution**:
```bash
# Check what's using the port
lsof -i :8001
lsof -i :8002

# Kill existing vLLM
./stop_vllm.sh

# Restart
./start_vllm.sh
```

### Greeting Returns JSON Instead of Conversation

**Status**: FIXED in commit e003138

**Solution**:
1. Stop the CLI
2. Pull latest changes: `git pull origin claude/fix-hardcoded-config-QyiND`
3. Restart: `python -m cli.app`

### File Operations Not Working

**Status**: FIXED in commits a02ea84, c8cd8b3, 43a644f

All issues fixed:
- ✅ File content now displays in UI
- ✅ Absolute paths shown
- ✅ File browser (LIST_DIRECTORY) works
- ✅ Proper error messages for permission errors
- ✅ Session workspace isolation

## Configuration

### config/config.yaml

```yaml
llm:
  endpoints:
    - url: http://localhost:8001/v1
      name: primary
      timeout: 120
    - url: http://localhost:8002/v1
      name: secondary
      timeout: 120

workspace:
  default_path: ~/workspace
  isolation: true  # Each session gets own directory
  cleanup: false   # Keep workspace after session ends

logging:
  level: DEBUG     # Set to DEBUG for verbose logging
  file: logs/agentic.log
  log_llm_requests: true   # Log all LLM prompts/responses
```

### Environment Variables

```bash
# Override model name
export VLLM_MODEL="openai/gpt-oss-120b"

# Override endpoints (not recommended)
export LLM_PRIMARY_URL="http://localhost:8001/v1"
export LLM_SECONDARY_URL="http://localhost:8002/v1"
```

## Health Check Script

Create `check_health.sh`:

```bash
#!/bin/bash
echo "Checking vLLM servers..."
echo ""

echo "Primary (8001):"
curl -s http://localhost:8001/v1/models | jq '.data[0].id' || echo "❌ Not reachable"

echo ""
echo "Secondary (8002):"
curl -s http://localhost:8002/v1/models | jq '.data[0].id' || echo "❌ Not reachable"
```

## Logs

All logs are in the `logs/` directory:

- `logs/agentic.log` - Main application logs (JSONL format)
- `logs/vllm_primary.log` - Primary vLLM server logs
- `logs/vllm_secondary.log` - Secondary vLLM server logs
- `logs/prompts/` - Saved LLM prompts (if `save_prompts: true`)

### Viewing Logs

```bash
# Follow main logs
tail -f logs/agentic.log

# Follow vLLM logs
tail -f logs/vllm_primary.log

# Search logs
grep "ERROR" logs/agentic.log
grep "LLM Request" logs/agentic.log | jq
```

## Complete Workflow

```bash
# 1. Start vLLM servers
cd /home/user/agentic-coder/agentic-ai
./start_vllm.sh

# 2. Wait for models to load (30-60s)
sleep 30

# 3. Verify health
curl http://localhost:8001/v1/models
curl http://localhost:8002/v1/models

# 4. Run CLI
python -m cli.app

# 5. Test
# Type: Hello
# Expected: Conversational greeting response

# 6. When done, stop servers
./stop_vllm.sh
```

## Recent Fixes (Session claude/fix-hardcoded-config-QyiND)

### Bug Fix #1-6 (Previous sessions)
- ✅ Various foundational fixes

### Bug Fix #7: Missing Metadata (a02ea84)
- **Issue**: File paths, sizes, content not showing in UI
- **Root Cause**: `workflows/coding_workflow.py` not returning metadata
- **Fix**: All actions now return metadata

### Bug Fix #8: LIST_DIRECTORY Not Implemented (a02ea84, c8cd8b3)
- **Issue**: File browser completely broken
- **Root Cause**: LIST_DIRECTORY action not implemented in workflows
- **Fix**: Full implementation + added to prompts

### Bug Fix #9: No Logging Configuration (43a644f)
- **Issue**: No logs appearing despite logger.info() calls
- **Root Cause**: No `logging.basicConfig()` configured
- **Fix**: Added proper Python logging setup in backend_bridge.py

### Bug Fix #10: Greeting Misclassification (e003138)
- **Issue**: "Hello" returned JSON task completion
- **Root Cause**: IntentRouter classified greetings as CODING
- **Fix**: Improved classification prompt + defensive handling

### Bug Fix #11-12: LLM Client Crashes (1b22e54, 36a6ce4)
- **Issue**: "object of type 'NoneType' has no len()"
- **Root Cause**: Logging code called len() on None values
- **Fix**: Added None checks throughout llm_client.py

## Next Steps After Startup

1. **Test Greeting**: Type "Hello" → Should get conversational response
2. **Test File Creation**: "Create a Python file test.py with hello world"
3. **Test File Browser**: "Show me the files in the workspace"
4. **Test File Content**: After creating file, content should display in UI
5. **Check Logs**: `tail -f logs/agentic.log` should show detailed request/response

## Support

If you encounter issues:
1. Check this guide's Troubleshooting section
2. Review logs in `logs/` directory
3. Check recent commits for relevant fixes
4. See `CRITICAL_BUGFIX_LOG.md` for detailed fix history

---

**Last Updated**: 2026-01-16
**Branch**: claude/fix-hardcoded-config-QyiND
**Status**: All critical bugs fixed ✅
