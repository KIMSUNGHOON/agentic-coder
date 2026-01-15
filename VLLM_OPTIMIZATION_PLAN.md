# vLLM Optimization and Phase 5 Implementation Plan

## Overview
This document outlines the implementation plan for optimizing Agentic 2.0 to work efficiently with **NVIDIA H100 NVL 96GB** serving **2x GPT-OSS-120B via vLLM**.

## Hardware Setup
- **GPU**: NVIDIA H100 NVL 96GB
- **Model**: GPT-OSS-120B (2 instances)
- **Server**: vLLM with OpenAI-compatible API
- **Endpoints**:
  - Primary: `http://localhost:8001/v1`
  - Secondary: `http://localhost:8002/v1`

## Current Status

### ✅ Completed (Bug Fix #7.1)
1. **Streaming LLM Client**
   - Added `chat_completion_stream()` method to `DualEndpointLLMClient`
   - Supports real-time token-by-token streaming
   - Automatic failover across dual endpoints
   - Lines 301-407 in `agentic-ai/core/llm_client.py`

### ⏳ Pending Implementation

#### 1. Real-time Streaming to UI (CRITICAL)
**User requirement**: "실시간으로 출력되는 output을 streaming 방식으로 화면에 실시간 업데이트가 되어야 합니다"

**Current problem**:
- Backend bridge uses blocking `await orchestrator.execute_task()`
- No intermediate feedback during execution
- User sees only final result after completion

**Solution**:
```python
# cli/backend_bridge.py - Modify execute_task_stream()
async def execute_task_stream(self, ...):
    # Stream LLM responses in real-time
    async for chunk in llm_client.chat_completion_stream(messages):
        yield ProgressUpdate(
            type="llm_chunk",
            message=chunk,
            data={"stream": True}
        )

    # Stream workflow progress
    async for event in orchestrator.execute_task_stream(...):
        yield ProgressUpdate(
            type="workflow_event",
            message=event.message,
            data=event.data
        )
```

**Files to modify**:
- `cli/backend_bridge.py`: Add streaming support to `execute_task_stream()`
- `workflows/orchestrator.py`: Add `execute_task_stream()` method
- `workflows/base_workflow.py`: Yield intermediate events during execution
- `cli/app.py`: Update UI to handle streaming chunks

#### 2. vLLM Multi-Batch Optimization
**User requirement**: "vLLM은 다양한 성능 최적화, Continous Batching, Prefix Caching 다양한 최적화가 있기 때문에. 최대한 multi batch 를 사용하도록 request를 최적화 해야 합니다"

**Current problem**:
- LLM requests sent sequentially (one at a time)
- vLLM's continuous batching not fully utilized
- Prefix caching not configured

**Solution A: Request Batching**
Create a batching layer that groups multiple LLM requests:

```python
# agentic-ai/core/llm_batch_manager.py (NEW FILE)
class LLMBatchManager:
    """Batch multiple LLM requests for vLLM optimization"""

    def __init__(self, batch_size: int = 4, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_requests = []

    async def batch_request(self, messages, **kwargs):
        """Add request to batch and wait for batch processing"""
        # Accumulate requests until batch_size or timeout
        # Send as single batch to vLLM
        # Return individual results
```

**Solution B: Prefix Caching Configuration**
Configure vLLM to cache common prefixes (system prompts, context):

```yaml
# config/config.yaml
llm:
  vllm_config:
    enable_prefix_caching: true
    prefix_cache_size: 1024  # Cache size in tokens
    common_prefixes:
      - system_prompt
      - workflow_context
```

**Solution C: Parallel LLM Calls**
When workflow needs multiple LLM calls (e.g., plan + validate), execute in parallel:

```python
# workflows/base_workflow.py
async def parallel_llm_calls(self, call_configs):
    """Execute multiple LLM calls in parallel for vLLM batching"""
    tasks = [
        self.call_llm(**config)
        for config in call_configs
    ]
    return await asyncio.gather(*tasks)
```

#### 3. Context Optimization
**User requirement**: "현재 agent간 context sharing 및 context window 최적화, conversation history 등 다양한 프롬프트 엔지니어링 기법이 적용 되있는가"

**Current problem**:
- No conversation history management
- No context sharing between agents
- No context window size optimization
- Each request starts fresh (no memory)

**Solution A: Conversation History Manager**
```python
# agentic-ai/core/conversation_history.py (NEW FILE)
class ConversationHistory:
    """Manage conversation history with context window limits"""

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens
        self.messages = []
        self.shared_context = {}

    def add_message(self, role: str, content: str):
        """Add message and trim if exceeds context window"""
        self.messages.append({"role": role, "content": content})
        self._trim_to_context_window()

    def _trim_to_context_window(self):
        """Keep only recent messages within context window"""
        # Implement token counting and trimming
        # Keep system prompt + recent messages

    def get_messages_for_llm(self) -> List[Dict]:
        """Get formatted messages for LLM call"""
        return self.messages

    def share_context(self, key: str, value: Any):
        """Share context across agents"""
        self.shared_context[key] = value

    def get_shared_context(self, key: str) -> Any:
        """Retrieve shared context"""
        return self.shared_context.get(key)
```

**Solution B: Context Window Optimization**
```python
# For GPT-OSS-120B, optimize token usage
CONTEXT_WINDOW_SIZE = 4096  # GPT-OSS-120B context window
RESERVED_FOR_RESPONSE = 1024  # Reserve tokens for response
MAX_PROMPT_TOKENS = CONTEXT_WINDOW_SIZE - RESERVED_FOR_RESPONSE  # 3072

def optimize_prompt(messages: List[Dict]) -> List[Dict]:
    """Trim messages to fit context window"""
    # Keep system prompt (always)
    # Keep most recent user message (always)
    # Trim older messages from middle
```

**Solution C: Prompt Engineering Techniques**
```python
# workflows/base_workflow.py
SYSTEM_PROMPT_TEMPLATE = """You are Agentic 2.0, an AI coding assistant.

<context>
Previous steps: {completed_steps}
Current task: {current_task}
Shared context: {shared_context}
</context>

<instructions>
- Focus on the current step only
- Reference previous steps if needed
- Use shared context for consistency
</instructions>
"""
```

#### 4. Phase 5: Sub-Agent Workflow Integration
**User requirement**: "Phase 5도 진행 해"

**Current status**:
- ✅ Sub-agent infrastructure exists (Phase 2 complete)
- ❌ NOT integrated into workflows
- See: `docs/PHASE_2_COMPLETION.md` lines 299-303

**Architecture**:
```
User Request (e.g., "Build full stack app")
         ↓
   WorkflowOrchestrator
         ↓
   [Complexity Check]
         ↓
   High Complexity → Spawn Sub-Agents
         ├─ Sub-Agent 1: Backend API
         ├─ Sub-Agent 2: Frontend UI
         ├─ Sub-Agent 3: Database Schema
         └─ Sub-Agent 4: Tests
         ↓
   Parallel Execution (vLLM batching!)
         ↓
   Results Aggregation
         ↓
   Final Result
```

**Implementation Steps**:

**Step 1: Add Sub-Agent Decision Logic**
```python
# workflows/base_workflow.py
async def should_spawn_sub_agents(self, state: AgenticState) -> bool:
    """Decide if task should be decomposed into sub-agents"""
    task = state["task_description"]

    # Estimate complexity
    complexity = await self._estimate_complexity(task)

    # Check threshold
    threshold = state.get("sub_agent_complexity_threshold", 0.7)

    return complexity > threshold

async def _estimate_complexity(self, task: str) -> float:
    """Estimate task complexity (0.0 - 1.0)"""
    # Use LLM to estimate complexity
    prompt = f"""Estimate task complexity (0.0 - 1.0):
    Task: {task}

    Factors:
    - Number of components needed
    - Technical scope (frontend/backend/db/tests)
    - Lines of code estimate

    Return only a number between 0.0 and 1.0."""

    response = await self.call_llm([{"role": "user", "content": prompt}])
    return float(response.strip())
```

**Step 2: Create Sub-Agent Spawning Node**
```python
# workflows/base_workflow.py
async def spawn_sub_agents_node(self, state: AgenticState) -> AgenticState:
    """Spawn sub-agents for complex tasks"""
    logger.info("🌟 Spawning sub-agents for complex task")

    # Decompose task
    subtasks = await self._decompose_task(state["task_description"])

    # Create sub-agent manager
    from agents.sub_agent_manager import SubAgentManager
    manager = SubAgentManager(
        llm_client=self.llm_client,
        max_concurrent=state.get("max_concurrent_sub_agents", 3)
    )

    # Spawn sub-agents
    sub_agent_results = await manager.execute_parallel_tasks(subtasks)

    # Aggregate results
    state["sub_agent_results"] = sub_agent_results
    state["task_status"] = TaskStatus.COMPLETED.value
    state["task_result"] = self._aggregate_sub_agent_results(sub_agent_results)
    state["should_continue"] = False

    return state

async def _decompose_task(self, task: str) -> List[Dict]:
    """Decompose complex task into subtasks"""
    prompt = f"""Decompose this task into 2-5 independent subtasks:
    Task: {task}

    Return JSON array of subtasks:
    [
      {{"id": "1", "description": "...", "priority": "high"}},
      {{"id": "2", "description": "...", "priority": "medium"}}
    ]
    """

    response = await self.call_llm([{"role": "user", "content": prompt}])
    return json.loads(response)
```

**Step 3: Update Workflow Graph**
```python
# workflows/base_workflow.py
def _build_graph(self):
    """Build workflow graph with sub-agent support"""
    workflow = StateGraph(AgenticState)

    # Add nodes
    workflow.add_node("plan", self.plan_node)
    workflow.add_node("check_complexity", self.check_complexity_node)  # NEW
    workflow.add_node("spawn_sub_agents", self.spawn_sub_agents_node)  # NEW
    workflow.add_node("execute", self.execute_node)
    workflow.add_node("reflect", self.reflect_node)

    # Add edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "check_complexity")

    # Conditional edge: spawn sub-agents OR execute normally
    workflow.add_conditional_edges(
        "check_complexity",
        self._route_based_on_complexity,
        {
            "spawn_sub_agents": "spawn_sub_agents",
            "execute": "execute"
        }
    )

    workflow.add_edge("spawn_sub_agents", END)
    workflow.add_edge("execute", "reflect")
    workflow.add_conditional_edges(
        "reflect",
        self._should_continue,
        {True: "plan", False: END}
    )

    return workflow.compile()

def _route_based_on_complexity(self, state: AgenticState) -> str:
    """Route to sub-agents or normal execution"""
    return "spawn_sub_agents" if state.get("use_sub_agents", False) else "execute"
```

**Step 4: Update Config**
```yaml
# config/config.yaml
workflows:
  max_iterations: 50  # Increased for complex tasks
  timeout_seconds: 1200  # 20 minutes for large tasks
  recursion_limit: 100

sub_agents:
  enabled: true
  complexity_threshold: 0.7  # Spawn if complexity > 0.7
  max_concurrent: 4  # Max 4 parallel sub-agents (matches vLLM batch size)
  subtask_max_iterations: 10  # Each sub-agent gets 10 iterations
```

## Implementation Order

### Phase A: Streaming (CRITICAL - Week 1)
**Priority**: HIGHEST - User explicitly requested real-time feedback

1. ✅ Add `chat_completion_stream()` to LLM client (DONE)
2. ⏳ Add streaming to backend bridge
3. ⏳ Add streaming to workflows
4. ⏳ Update UI to display streaming chunks

**Expected outcome**: User sees real-time LLM output as it's generated

### Phase B: Context Management (Week 1-2)
**Priority**: HIGH - Required for conversation history

1. Create `ConversationHistory` class
2. Integrate with backend bridge
3. Add context window optimization
4. Add shared context for agents

**Expected outcome**: Conversations maintain history, agents share context

### Phase C: vLLM Optimization (Week 2)
**Priority**: HIGH - Performance critical for H100

1. Create `LLMBatchManager` for request batching
2. Configure prefix caching in config.yaml
3. Add parallel LLM call support
4. Test with vLLM server to verify batching

**Expected outcome**: 2-4x throughput improvement with continuous batching

### Phase D: Phase 5 Sub-Agent Integration (Week 2-3)
**Priority**: HIGH - Required for large tasks

1. Add complexity estimation logic
2. Add task decomposition logic
3. Create `spawn_sub_agents_node()`
4. Update workflow graph with conditional routing
5. Test with "full stack development" request

**Expected outcome**: Large tasks decomposed into parallel sub-agents

### Phase E: Testing and Optimization (Week 3)
1. Test calculator creation (should complete in 15-20 iterations)
2. Test full stack development (should spawn 3-4 sub-agents)
3. Verify vLLM batching with parallel requests
4. Benchmark performance improvements

## Success Metrics

### Streaming
- ✅ User sees LLM output within 100ms of generation
- ✅ UI updates in real-time during workflow execution
- ✅ No blocking calls in backend bridge

### vLLM Optimization
- ✅ Continuous batching active (check vLLM server logs)
- ✅ Prefix caching hit rate > 50%
- ✅ 2-4x throughput improvement for parallel requests

### Context Management
- ✅ Conversation history maintained across requests
- ✅ Context window stays under 3072 tokens (prompt limit)
- ✅ Agents share context successfully

### Phase 5 Sub-Agents
- ✅ Complex tasks (complexity > 0.7) spawn sub-agents
- ✅ Sub-agents execute in parallel
- ✅ Results aggregated correctly
- ✅ Full stack development request completes successfully

## Configuration Changes

### Immediate (Bug Fix #7.1)
```yaml
workflows:
  max_iterations: 30  # Current
```

### After Phase 5 Complete
```yaml
workflows:
  max_iterations: 50  # For complex tasks without sub-agents
  timeout_seconds: 1200  # 20 minutes

sub_agents:
  enabled: true
  complexity_threshold: 0.7
  max_concurrent: 4  # Match vLLM optimal batch size
```

## Testing Plan

### Test Case 1: Simple Task (No Sub-Agents)
```
Input: "python 언어로 구현된 계산기를 만들고 싶은데"
Expected:
- Complexity < 0.7
- Normal workflow (no sub-agents)
- Complete in 15-20 iterations
- Streaming output visible in UI
```

### Test Case 2: Complex Task (With Sub-Agents)
```
Input: "Build a full stack web application with React frontend, FastAPI backend, PostgreSQL database, and unit tests"
Expected:
- Complexity > 0.7
- Spawn 4 sub-agents (frontend, backend, db, tests)
- Sub-agents execute in parallel (vLLM batching active)
- Complete in 20-30 minutes
- Streaming output for each sub-agent
```

### Test Case 3: vLLM Batching Verification
```
Test: Execute 4 LLM calls simultaneously
Check vLLM server logs for:
- Batch size = 4
- Continuous batching active
- Prefix cache hits
```

## Risk Mitigation

### Risk 1: vLLM Server Overload
**Mitigation**:
- Limit `max_concurrent_sub_agents` to 4
- Add request throttling
- Monitor vLLM server GPU memory

### Risk 2: Context Window Overflow
**Mitigation**:
- Implement token counting
- Trim old messages automatically
- Reserve 1024 tokens for response

### Risk 3: Sub-Agent Coordination Failures
**Mitigation**:
- Add sub-agent timeout (5 minutes each)
- Graceful degradation if sub-agent fails
- Aggregate partial results

## References

- vLLM Continuous Batching: https://docs.vllm.ai/en/latest/serving/performance.html
- vLLM Prefix Caching: https://docs.vllm.ai/en/latest/automatic_prefix_caching.html
- H100 Performance Guide: https://docs.nvidia.com/deeplearning/performance/index.html

---

**Status**: Implementation in progress (Phase A: Streaming)
**Last Updated**: 2026-01-15
**Next Milestone**: Complete streaming to UI (Phase A)
