# vLLM Load Balancing Guide

## 📋 Overview

This guide explains how to configure and use load balancing when running multiple vLLM servers with the same model (e.g., 2x GPT-OSS-120B on different GPUs).

## 🎯 Use Case

**Your Scenario:**
- 2x H100 GPUs
- 2x GPT-OSS-120B vLLM servers (ports 8001 and 8002)
- Want to utilize BOTH servers to improve throughput

## 🔧 Configuration

### Option 1: Load Balancing Mode (Recommended ⭐)

Use this when you have **multiple servers running the SAME model**.

```bash
# .env file
LLM_ENDPOINT=http://localhost:8001/v1
LLM_MODEL=openai/gpt-oss-120b

# Enable load balancing with comma-separated endpoints
VLLM_ENDPOINTS=http://localhost:8001/v1,http://localhost:8002/v1
```

**How it works:**
- System uses round-robin load balancing
- Each request goes to the next available server
- Request 1 → Server 8001
- Request 2 → Server 8002
- Request 3 → Server 8001
- Request 4 → Server 8002
- ...and so on

**Benefits:**
- ✅ **2x throughput** - both servers handle requests
- ✅ Simple configuration - just list endpoints
- ✅ Automatic failover - if one server is busy, requests still flow
- ✅ Thread-safe - handles concurrent requests correctly

### Option 2: Task-Based Routing

Use this when you have **different models for different tasks**.

```bash
# .env file
LLM_ENDPOINT=http://localhost:8001/v1
LLM_MODEL=openai/gpt-oss-120b

# Different models per task
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder
```

**When to use:**
- Server 1: Large reasoning model (DeepSeek-R1, GPT-OSS-120B)
- Server 2: Fast coding model (Qwen-Coder, smaller model)

## 🚀 vLLM Server Startup

### Server 1 (Port 8001)
```bash
vllm serve openai/gpt-oss-120b \
  --host 0.0.0.0 --port 8001 \
  --tool-call-parser openai \
  --enable-auto-tool-choice \
  --gpu-memory-utilization 0.90 \
  --tensor-parallel-size 1
```

### Server 2 (Port 8002)
```bash
vllm serve openai/gpt-oss-120b \
  --host 0.0.0.0 --port 8002 \
  --tool-call-parser openai \
  --enable-auto-tool-choice \
  --gpu-memory-utilization 0.90 \
  --tensor-parallel-size 1
```

**Key Points:**
- Each server runs on separate GPU (CUDA_VISIBLE_DEVICES=0 vs 1)
- Same model, same parameters
- Different ports (8001 vs 8002)

## 📊 Monitoring

### Check Load Balancing Status

The system logs load balancing configuration at startup:

```
INFO     🔀 VLLMRouter initialized in LOAD BALANCING mode
INFO        📊 2 endpoints configured:
INFO           [1] http://localhost:8001/v1
INFO           [2] http://localhost:8002/v1
INFO        🔄 Strategy: Round-robin across all endpoints
```

### Check Which Server Handles Request

Each Tool Use workflow logs which endpoint is used:

```
INFO     Supervisor calling vLLM for tool decision...
INFO     Using endpoint: http://localhost:8001/v1
```

Next request:
```
INFO     Supervisor calling vLLM for tool decision...
INFO     Using endpoint: http://localhost:8002/v1
```

## 🔍 Verification

### Test Load Balancing

1. **Start both vLLM servers** (8001 and 8002)

2. **Configure .env with VLLM_ENDPOINTS:**
   ```bash
   VLLM_ENDPOINTS=http://localhost:8001/v1,http://localhost:8002/v1
   ```

3. **Run CLI:**
   ```bash
   cd backend
   python -m cli
   ```

4. **Check startup logs:**
   ```
   🔀 VLLMRouter initialized in LOAD BALANCING mode
      📊 2 endpoints configured:
         [1] http://localhost:8001/v1
         [2] http://localhost:8002/v1
   ```

5. **Send multiple requests:**
   - Request 1 should hit server 8001
   - Request 2 should hit server 8002
   - Alternates between servers

### Monitor GPU Usage

```bash
# Terminal 1: Monitor GPU 0 (Server 8001)
watch -n 1 nvidia-smi -i 0

# Terminal 2: Monitor GPU 1 (Server 8002)
watch -n 1 nvidia-smi -i 1
```

You should see **both GPUs actively processing** during Tool Use workflows.

## 🎛️ Advanced Configuration

### 3+ Servers

Load balancing works with any number of servers:

```bash
VLLM_ENDPOINTS=http://localhost:8001/v1,http://localhost:8002/v1,http://localhost:8003/v1
```

Round-robin cycles through all 3 servers.

### Mixed Setup

You can combine load balancing with multiple models:

```bash
# Primary load-balanced pool for main tasks
VLLM_ENDPOINTS=http://localhost:8001/v1,http://localhost:8002/v1

# Separate fast model for specific tasks
VLLM_CODING_ENDPOINT=http://localhost:8003/v1
CODING_MODEL=Qwen/Qwen3-8B-Coder
```

## 🐛 Troubleshooting

### Only One Server Being Used

**Symptom:** Logs show only `http://localhost:8001/v1` being used.

**Check:**
1. Is `VLLM_ENDPOINTS` set in .env?
   ```bash
   grep VLLM_ENDPOINTS .env
   ```

2. Are commas correct? (no spaces inside)
   ```bash
   # ✅ Correct
   VLLM_ENDPOINTS=http://localhost:8001/v1,http://localhost:8002/v1

   # ❌ Wrong (spaces)
   VLLM_ENDPOINTS=http://localhost:8001/v1, http://localhost:8002/v1
   ```

3. Restart backend to reload config:
   ```bash
   # CLI mode: just restart
   python -m cli

   # API mode: restart uvicorn
   uvicorn main:app --reload
   ```

### Connection Refused on Port 8002

**Symptom:** Error connecting to second server.

**Check:**
1. Is vLLM server 2 running?
   ```bash
   curl http://localhost:8002/v1/models
   ```

2. Is port 8002 occupied?
   ```bash
   netstat -tuln | grep 8002
   ```

3. Check vLLM server logs:
   ```bash
   # Check if server started successfully
   ps aux | grep vllm
   ```

### Performance Not Improved

**Symptom:** Still slow even with 2 servers.

**Possible Causes:**
1. **Sequential Tool Calls**: GPT-OSS doesn't support parallel tool calling
   - Each tool call must complete before next one
   - Load balancing helps but not 2x improvement

2. **Small Tasks**: If each request is very quick (<1s), overhead dominates

3. **GPU Memory**: Both GPUs might be near capacity
   ```bash
   nvidia-smi
   ```

## 📈 Performance Expectations

### With Load Balancing (2 servers):

**Workload: Tool Use Pattern (Sequential Tool Calls)**
- **Before:** 1 server, 100% utilized during workflow
- **After:** 2 servers, alternating ~50% each
- **Throughput:** ~1.5-1.8x improvement (not full 2x due to sequential nature)

**Workload: Parallel Requests (Multiple Users)**
- **Before:** 1 server, queue builds up
- **After:** 2 servers, requests distributed
- **Throughput:** ~2x improvement (near-linear scaling)

### Why Not 2x for Tool Use?

Tool Use pattern is sequential:
```
Request 1: LLM decides tool → Server A
Request 2: LLM sees result  → Server B
Request 3: LLM decides tool → Server A
...
```

Each step depends on previous result, so can't fully parallelize. But load balancing still helps by:
- Reducing queue time
- Better GPU utilization
- Faster response when multiple tasks running

## 🎓 Best Practices

1. **Use VLLM_ENDPOINTS for identical servers**
   - Same model = load balancing
   - Different models = task-based routing

2. **Monitor both GPUs**
   - Ensure both are being utilized
   - Check memory isn't exhausted

3. **Optimize vLLM flags**
   - Enable prefix caching: `--enable-prefix-caching`
   - Adjust batch size: `--max-num-batched-tokens 8192`

4. **Consider Continuous Batching**
   - vLLM automatically batches requests
   - More concurrent users = better throughput

## 🔗 Related Documentation

- [Remote CLI Design](./REMOTE_CLI_DESIGN.md) - For multi-client access
- [.env.example](../.env.example) - Full configuration reference
- [vLLM Optimization Guide](https://docs.vllm.ai/en/latest/performance/) - Official vLLM docs
