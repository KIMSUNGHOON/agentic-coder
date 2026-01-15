# vLLM Configuration Guide for H100 NVL 96GB

## Overview

This guide explains how to configure and optimize vLLM for serving **GPT-OSS-120B** on **NVIDIA H100 NVL 96GB** GPU.

## Hardware Specifications

- **GPU**: NVIDIA H100 NVL 96GB
- **Model**: GPT-OSS-120B (2 instances)
- **Framework**: vLLM (OpenAI-compatible API)
- **Endpoints**:
  - Primary: `http://localhost:8001/v1`
  - Secondary: `http://localhost:8002/v1`

## vLLM Server Configuration

### 1. Basic Server Startup

```bash
# Primary endpoint (port 8001)
vllm serve GPT-OSS-120B \
    --host 0.0.0.0 \
    --port 8001 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 4096 \
    --served-model-name gpt-oss-120b

# Secondary endpoint (port 8002)
vllm serve GPT-OSS-120B \
    --host 0.0.0.0 \
    --port 8002 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 4096 \
    --served-model-name gpt-oss-120b
```

### 2. Enable Continuous Batching (Automatic)

**Good news**: vLLM enables **continuous batching** by default!

Continuous batching allows vLLM to:
- Process multiple requests simultaneously
- Add new requests to batch as they arrive
- Maximize GPU utilization

**No additional configuration needed** - it's automatic.

Verify continuous batching is working:
```bash
# Check vLLM server logs
# You should see: "Batch size: X" where X > 1
tail -f vllm_server.log | grep "Batch size"
```

### 3. Enable Prefix Caching

Prefix caching dramatically improves performance by caching common prompt prefixes.

**Enable prefix caching**:
```bash
vllm serve GPT-OSS-120B \
    --host 0.0.0.0 \
    --port 8001 \
    --enable-prefix-caching \  # ← Enable prefix caching
    --gpu-memory-utilization 0.85 \  # ← Reduce slightly for cache
    --max-model-len 4096
```

**How it works**:
1. vLLM detects repeated prompt prefixes (e.g., system prompts)
2. Caches KV (key-value) tensors for these prefixes
3. Reuses cached tensors instead of recomputing
4. **Result**: 2-5x faster for requests with shared prefixes

**Best practices for prefix caching**:
- Use consistent system prompts across requests
- Structure prompts with common prefixes first
- Monitor cache hit rate in vLLM logs

### 4. Optimize Batch Size

For H100 NVL 96GB, optimal batch size is **4-8** concurrent requests.

```bash
vllm serve GPT-OSS-120B \
    --max-num-seqs 8 \  # ← Max concurrent requests per batch
    --max-num-batched-tokens 8192 \  # ← Max tokens per batch
    --enable-prefix-caching
```

**Why 4-8?**
- H100 has 96GB memory
- GPT-OSS-120B model size: ~240GB (BF16) → ~120GB with quantization
- Remaining memory: ~70GB for KV cache and activations
- Each request uses ~8-10GB KV cache
- Optimal: 4-8 concurrent requests

### 5. Enable Streaming (Critical for Real-time UX)

Streaming is **essential** for Agentic 2.0's real-time feedback requirement.

```bash
# vLLM supports streaming by default
# Just use stream=True in API calls
```

Client-side (already implemented in `llm_client.py`):
```python
async for chunk in llm_client.chat_completion_stream(messages):
    print(chunk, end="", flush=True)
```

### 6. Full Production Configuration

```bash
#!/bin/bash
# start_vllm_primary.sh

vllm serve GPT-OSS-120B \
    --host 0.0.0.0 \
    --port 8001 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 \
    --max-num-seqs 8 \
    --max-num-batched-tokens 8192 \
    --enable-prefix-caching \
    --disable-log-requests \
    --served-model-name gpt-oss-120b \
    --trust-remote-code
```

```bash
#!/bin/bash
# start_vllm_secondary.sh

vllm serve GPT-OSS-120B \
    --host 0.0.0.0 \
    --port 8002 \
    --tensor-parallel-size 1 \
    --gpu-memory-utilization 0.85 \
    --max-model-len 4096 \
    --max-num-seqs 8 \
    --max-num-batched-tokens 8192 \
    --enable-prefix-caching \
    --disable-log-requests \
    --served-model-name gpt-oss-120b \
    --trust-remote-code
```

## Agentic 2.0 Configuration

Agentic 2.0 is already configured to work optimally with vLLM:

### ✅ Implemented Optimizations

1. **Dual Endpoint Failover**
   - File: `agentic-ai/core/llm_client.py`
   - Automatic failover across 2 endpoints
   - Health checks every 30s
   - Round-robin load balancing

2. **Streaming Support**
   - File: `agentic-ai/core/llm_client.py:301-407`
   - Real-time token streaming via `chat_completion_stream()`
   - Backend bridge propagates streaming to UI
   - Workflow events streamed in real-time

3. **Exponential Backoff Retry**
   - 4 retry attempts with backoff (2s, 4s, 8s, 16s)
   - Matches vLLM's continuous batching timing
   - Prevents overwhelming the server

4. **Conversation History Management**
   - File: `agentic-ai/core/conversation_history.py`
   - Automatic context window management (3072 tokens)
   - Token counting and trimming
   - Preserves system prompts for prefix caching

5. **Optimal Batch Size Configuration**
   - Config: `config/config.yaml:50`
   - `max_concurrent: 4` sub-agents
   - Matches vLLM optimal batch size

### 📋 To Maximize vLLM Performance

#### 1. Use Consistent System Prompts

For maximum prefix cache benefit, use the same system prompt across requests:

```python
from core.conversation_history import create_conversation_history

# Create with default system prompt (cached by vLLM)
history = create_conversation_history()

# Or use custom but consistent prompt
SYSTEM_PROMPT = "You are Agentic 2.0, an AI coding assistant..."
history = create_conversation_history(system_prompt=SYSTEM_PROMPT)
```

#### 2. Batch Parallel Requests (Phase 5 Implementation)

When Phase 5 is complete, sub-agents will execute in parallel:

```python
# Future: Phase 5 implementation
# This will send 4 parallel requests to vLLM
async def spawn_sub_agents():
    subtasks = [
        "Create frontend UI",
        "Create backend API",
        "Create database schema",
        "Create tests"
    ]

    # Execute in parallel → vLLM batches them!
    results = await asyncio.gather(*[
        sub_agent.execute(task) for task in subtasks
    ])
```

#### 3. Monitor vLLM Performance

Check vLLM server logs for optimization metrics:

```bash
# Continuous batching metrics
tail -f vllm_server.log | grep "Batch size"

# Prefix cache hits
tail -f vllm_server.log | grep "cache hit"

# Throughput
tail -f vllm_server.log | grep "tokens/s"
```

#### 4. GPU Memory Monitoring

```bash
# Watch GPU utilization
watch -n 1 nvidia-smi

# Target metrics for H100:
# - GPU Utilization: 80-95%
# - Memory Usage: 75-85GB (85-90% of 96GB)
# - Power Draw: 650-700W (max 700W)
```

## Benchmarking vLLM Performance

### Test 1: Sequential vs Parallel Requests

```python
#!/usr/bin/env python3
"""Benchmark sequential vs parallel LLM requests"""
import asyncio
import time
from core.llm_client import DualEndpointLLMClient, EndpointConfig

async def benchmark():
    client = DualEndpointLLMClient(
        endpoints=[
            EndpointConfig(url="http://localhost:8001/v1", name="primary"),
            EndpointConfig(url="http://localhost:8002/v1", name="secondary"),
        ],
        model_name="gpt-oss-120b"
    )

    messages = [{"role": "user", "content": "Write a Python function to sort a list."}]

    # Sequential (no batching)
    start = time.time()
    for i in range(4):
        await client.chat_completion(messages)
    sequential_time = time.time() - start

    # Parallel (vLLM batching)
    start = time.time()
    await asyncio.gather(*[
        client.chat_completion(messages) for _ in range(4)
    ])
    parallel_time = time.time() - start

    print(f"Sequential: {sequential_time:.2f}s")
    print(f"Parallel: {parallel_time:.2f}s")
    print(f"Speedup: {sequential_time / parallel_time:.2f}x")

    # Expected results with continuous batching:
    # Sequential: ~40s (4 requests × 10s each)
    # Parallel: ~12s (4 requests batched)
    # Speedup: ~3.3x

if __name__ == "__main__":
    asyncio.run(benchmark())
```

### Test 2: Prefix Caching Benefit

```python
#!/usr/bin/env python3
"""Benchmark prefix caching benefit"""
import asyncio
import time
from core.llm_client import DualEndpointLLMClient, EndpointConfig

LONG_SYSTEM_PROMPT = """You are Agentic 2.0, an AI coding assistant.
Your capabilities include code generation, bug fixing, research, data processing, and more.
You have access to tools for file operations, command execution, etc.
Always prioritize correctness, best practices, and code quality.
""" * 10  # Make it long to see caching benefit

async def benchmark_prefix_caching():
    client = DualEndpointLLMClient(
        endpoints=[EndpointConfig(url="http://localhost:8001/v1", name="primary")],
        model_name="gpt-oss-120b"
    )

    # First request (cold - no cache)
    messages1 = [
        {"role": "system", "content": LONG_SYSTEM_PROMPT},
        {"role": "user", "content": "Write a Python function to sort a list."}
    ]

    start = time.time()
    await client.chat_completion(messages1)
    first_time = time.time() - start

    # Second request (warm - cache hit on system prompt)
    messages2 = [
        {"role": "system", "content": LONG_SYSTEM_PROMPT},  # ← Same prefix!
        {"role": "user", "content": "Write a Python function to reverse a string."}
    ]

    start = time.time()
    await client.chat_completion(messages2)
    second_time = time.time() - start

    print(f"First request (cold): {first_time:.2f}s")
    print(f"Second request (cached): {second_time:.2f}s")
    print(f"Speedup: {first_time / second_time:.2f}x")

    # Expected results with prefix caching:
    # First: ~12s
    # Second: ~3s (cache hit on long system prompt)
    # Speedup: ~4x

if __name__ == "__main__":
    asyncio.run(benchmark_prefix_caching())
```

## Common Issues and Solutions

### Issue 1: Low GPU Utilization (<50%)

**Symptoms**: GPU utilization below 50%, slow responses

**Causes**:
- Batch size too small
- Not enough concurrent requests

**Solutions**:
```bash
# Increase max_num_seqs
vllm serve GPT-OSS-120B --max-num-seqs 8  # ← Increase from 4 to 8

# Or send more concurrent requests from Agentic 2.0
# (Phase 5 will do this automatically)
```

### Issue 2: Out of Memory (OOM)

**Symptoms**: `CUDA out of memory` errors

**Causes**:
- gpu-memory-utilization too high
- Batch size too large
- Prefix caching using too much memory

**Solutions**:
```bash
# Reduce memory utilization
vllm serve GPT-OSS-120B --gpu-memory-utilization 0.80  # ← Reduce from 0.90

# Or reduce batch size
vllm serve GPT-OSS-120B --max-num-seqs 4  # ← Reduce from 8

# Or reduce max model length
vllm serve GPT-OSS-120B --max-model-len 2048  # ← Reduce from 4096
```

### Issue 3: Prefix Cache Not Working

**Symptoms**: No speedup on repeated system prompts

**Causes**:
- Prefix caching not enabled
- System prompts vary slightly (cache misses)

**Solutions**:
```bash
# Ensure prefix caching is enabled
vllm serve GPT-OSS-120B --enable-prefix-caching

# Check logs for cache hits
tail -f vllm_server.log | grep "prefix cache"
```

Fix inconsistent system prompts in code:
```python
# Bad: Different prompts → cache miss
prompt1 = "You are an AI assistant."
prompt2 = "You are an AI coding assistant."  # ← Different!

# Good: Same prompt → cache hit
from core.conversation_history import DEFAULT_SYSTEM_PROMPT
prompt1 = DEFAULT_SYSTEM_PROMPT
prompt2 = DEFAULT_SYSTEM_PROMPT  # ← Same!
```

## Performance Targets

With proper configuration, expect:

| Metric | Target | Method |
|--------|--------|--------|
| **Latency (single)** | ~10s per request | Enable prefix caching |
| **Throughput (batch)** | ~4 requests/10s | Enable continuous batching |
| **GPU Utilization** | 80-95% | Batch size 4-8 |
| **Memory Usage** | 75-85GB | gpu-memory-utilization 0.85 |
| **Cache Hit Rate** | >50% | Consistent system prompts |
| **Speedup (cached)** | 3-5x | Prefix caching on |

## Next Steps

### Immediate Actions

1. ✅ **Enable prefix caching** on vLLM servers:
   ```bash
   --enable-prefix-caching
   ```

2. ✅ **Configure optimal batch size**:
   ```bash
   --max-num-seqs 8
   ```

3. ✅ **Use consistent system prompts** in Agentic 2.0 (already implemented in `conversation_history.py`)

### Phase 5 Implementation (Pending)

Once Phase 5 is complete, sub-agents will automatically benefit from:
- **Parallel execution** → vLLM batching
- **Shared system prompts** → Prefix caching
- **4 concurrent sub-agents** → Optimal batch size

Expected improvement: **3-5x faster** for complex tasks.

## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [vLLM Continuous Batching](https://docs.vllm.ai/en/latest/serving/performance.html)
- [vLLM Prefix Caching](https://docs.vllm.ai/en/latest/automatic_prefix_caching.html)
- [H100 Performance Guide](https://docs.nvidia.com/deeplearning/performance/index.html)
- [Agentic 2.0 Implementation Plan](VLLM_OPTIMIZATION_PLAN.md)

---

**Last Updated**: 2026-01-15
**Status**: Ready for production use with prefix caching and continuous batching
