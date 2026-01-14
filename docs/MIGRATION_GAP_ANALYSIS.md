# Migration Gap Analysis: Current System vs. Agentic 2.0

**Date:** 2026-01-14
**Purpose:** 기존 시스템과 Agentic 2.0 명세서 간 차이점 명확화

---

## 1. Executive Summary

| Aspect | Current System | Agentic 2.0 Spec | Gap Level |
|--------|----------------|------------------|-----------|
| **Scope** | Coding-focused | Universal (coding/research/data/general) | 🔴 Major |
| **LLM Backend** | Single endpoint | Dual endpoints with failover | 🟡 Medium |
| **Framework Mix** | LangGraph + Microsoft + DeepAgents | LangGraph + DeepAgents only | 🟢 Minor |
| **Workflow Type** | 4 static strategies | Dynamic with sub-agent spawn | 🟡 Medium |
| **Intent Classification** | Rule-based + LLM (coding focus) | Multi-domain classification | 🟡 Medium |
| **Cross-Platform** | Partial (some OS-specific code) | Fully guaranteed identical | 🟡 Medium |
| **Observability** | Standard logging | JSONL structured logging | 🟢 Minor |
| **Tool Safety** | Basic | Explicit allowlist/denylist | 🟢 Minor |

---

## 2. Detailed Gap Analysis

### 2.1 System Scope

#### **Current System: Coding-Focused**

**Evidence:**
```python
# backend/core/supervisor.py
INTENT_CATEGORIES = [
    "simple_conversation",
    "simple_question",
    "capability_question",
    "coding_task",      # ← Coding focus
    "complex_task"      # ← Still coding-related
]

# backend/app/agent/handlers/
├── quick_qa.py
├── planning.py
├── code_generation.py    # ← Coding
```

**Characteristics:**
- Primary use case: Code implementation, debugging, refactoring
- Limited support for non-coding tasks
- Intent classification optimized for coding scenarios

---

#### **Agentic 2.0: Universal Agent**

**Requirement:**
> "Agentic Coding AI" ≠ Coding Only
> 지원 프롬프트 유형:
> - 코딩 / 디버깅 / 리팩토링
> - 기술 리서치 / 문서 요약 / 보고서 작성
> - 데이터 정리 / 분석 / 자동화
> - 일반 질의

**Target Intent Categories:**
```python
WORKFLOWS = {
    "coding": CodingWorkflow,      # ✅ 현재 있음
    "research": ResearchWorkflow,  # ❌ 없음
    "data": DataWorkflow,          # ❌ 없음
    "general": GeneralWorkflow     # ⚠️ 부분적
}
```

**Gap:** 🔴 **Major** - Need 2 new workflows (research, data) + enhance general

---

### 2.2 LLM Backend Architecture

#### **Current System: Single Endpoint (with basic routing)**

**Implementation:**
```python
# backend/app/core/config.py
llm_endpoint: str = "http://localhost:8001/v1"

# Optional load balancing
vllm_endpoints: Optional[str] = None  # "url1,url2,url3"

# Round-robin if multiple endpoints specified
def get_vllm_endpoints_list(self) -> List[str]:
    if self.vllm_endpoints:
        return [endpoint.strip() for endpoint in self.vllm_endpoints.split(",")]
    return [self.llm_endpoint]
```

**Characteristics:**
- Load balancing: YES (round-robin)
- Failover: NO (automatic)
- Health check: NO
- Retry logic: NO (systematic)

---

#### **Agentic 2.0: Dual Endpoints with Advanced Failover**

**Requirement:**
```yaml
llm:
  endpoints:
    - url: http://localhost:8001/v1
      name: primary
      timeout: 120
    - url: http://localhost:8002/v1
      name: secondary
      timeout: 120

  health_check:
    enabled: true
    interval_seconds: 30

  retry:
    max_attempts: 4
    backoff_base: 2  # exponential: 2^attempt seconds
```

**Required Features:**
1. ✅ Active-active OR Primary/Secondary
2. ✅ Health checks every 30s
3. ✅ Automatic failover on timeout/error
4. ✅ Exponential backoff (2s, 4s, 8s, 16s)
5. ✅ Per-endpoint status tracking

**Gap:** 🟡 **Medium** - Need systematic health check + retry logic

---

### 2.3 Framework Architecture

#### **Current System: Multi-Framework Support**

**Structure:**
```python
# backend/app/core/config.py
agent_framework: Literal["microsoft", "langchain", "deepagent"] = "microsoft"

# backend/app/agent/factory.py
def get_agent_manager(framework: Optional[FrameworkType] = None):
    if fw == "microsoft":
        from app.agent.microsoft.agent_manager import agent_manager
        return agent_manager
    elif fw == "langchain":
        from app.agent.langchain.workflow_manager import workflow_manager
        return workflow_manager
    elif fw == "deepagent":
        from app.agent.langchain.deepagent_workflow import deepagent_workflow
        return deepagent_workflow
```

**Reality:**
- 3 framework options configured
- Actually using: **LangGraph** (via UnifiedAgentManager)
- Microsoft framework: Exists but not actively used
- DeepAgents: Code exists but not in production path

---

#### **Agentic 2.0: Single Framework Stack**

**Requirement:**
> Framework
> - LangChain
> - LangGraph
> - DeepAgents
> - **LangSmith 사용하지 않음**

**Target:**
```python
# Only one framework path
from langgraph.graph import StateGraph
from deepagents.middleware import TodoListMiddleware, SubAgentMiddleware
from langchain_core.tools import tool

# No framework switching, no factory pattern
```

**Gap:** 🟢 **Minor** - Just cleanup, core already uses LangGraph

---

### 2.4 Workflow Architecture

#### **Current System: Static Strategies**

**Implementation:**
```python
# backend/core/workflow.py
class DynamicWorkflowBuilder:
    def build_workflow(self, strategy, required_agents, enable_parallel):
        if strategy == "linear":
            return self._build_linear_workflow(required_agents)
        elif strategy == "parallel_gates":
            return self._build_parallel_gates_workflow(required_agents)
        elif strategy == "adaptive_loop":
            return self._build_adaptive_loop_workflow(required_agents)
        elif strategy == "staged_approval":
            return self._build_staged_approval_workflow(required_agents)
```

**Workflow Construction:**
1. Supervisor analyzes request
2. Selects one of 4 predefined strategies
3. Builds StateGraph with appropriate nodes
4. **All agents are predefined in registry**

**Limitation:**
- Cannot create new agent types at runtime
- Sub-agents must be registered beforehand
- No dynamic spawning based on complexity

---

#### **Agentic 2.0: Dynamic with Sub-Agent Spawning**

**Requirement:**
> Agentic 2.0 필수 조건
> - 동적 워크플로우 (Static chain ❌)
> - Agent 간 context sharing
> - Agent 간 협업/소통
> - **필요 시 sub-agent 동적 spawn**
> - 실패 시 self-reflection & retry

**Target:**
```python
# Core workflow stays similar
workflow = StateGraph(AgenticState)
workflow.add_node("planner", planner_agent)
workflow.add_node("executor", executor_agent)
workflow.add_node("reviewer", reviewer_agent)

# BUT: Executor can spawn sub-agents dynamically
class ExecutorAgent:
    async def execute_step(self, step):
        if self._is_complex(step):
            # Spawn specialist sub-agent
            result = await self.sub_agent_manager.spawn_specialist(
                task=step,
                agent_type="research",  # or "data", "coding", etc.
                tools=self._select_tools(step)
            )
        else:
            # Execute directly
            result = await self._execute_directly(step)
```

**Gap:** 🟡 **Medium** - Need SubAgentMiddleware integration

---

### 2.5 Intent Classification

#### **Current System: Coding-Biased Classification**

**Categories:**
```python
# backend/core/supervisor.py
def _is_quick_qa_request(self, request_lower: str) -> bool:
    # Check capability questions
    capability_patterns = [
        "가능합니까", "할 수 있어", "can you", "are you able"
    ]

    # Check code intent (PRIORITY!)
    if self._has_code_intent(request_lower):
        return False  # Route to coding workflow

def _has_code_intent(self, request_lower: str) -> bool:
    code_keywords = [
        "코드", "code", "프로그램", "program", "함수", "function",
        "클래스", "class", "api", "버그", "bug", "fix", "구현", "implement"
    ]
    return any(keyword in request_lower for keyword in code_keywords)
```

**Bias:**
- Checks code intent FIRST
- Other intents are secondary
- No explicit "research" or "data" categories

---

#### **Agentic 2.0: Multi-Domain Classification**

**Requirement:**
```python
class IntentRouter:
    WORKFLOWS = {
        "coding": CodingWorkflow,
        "research": ResearchWorkflow,
        "data": DataWorkflow,
        "general": GeneralWorkflow
    }

    async def route(self, user_prompt: str) -> str:
        classification_prompt = """
        Classify into:
        - coding: Code implementation, debugging, refactoring
        - research: Technical research, document analysis, report writing
        - data: Data processing, analysis, automation
        - general: General questions, planning, recommendations
        """
```

**Gap:** 🟡 **Medium** - Need multi-domain classifier

---

### 2.6 Cross-Platform Guarantee

#### **Current System: Mostly Cross-Platform**

**Good Practices (Already Present):**
```python
# ✅ Using pathlib
from pathlib import Path
workspace = Path.home() / "workspace"

# ✅ UTF-8 explicit
async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
    await f.write(content)
```

**Issues (Minor):**
```python
# ⚠️ Some shell=True usage exists
# backend/app/tools/process.py (if any)
result = subprocess.run(cmd, shell=True)  # Risky

# ⚠️ Some OS-specific paths
if platform.system() == "Windows":
    ...
```

---

#### **Agentic 2.0: Strict Cross-Platform**

**Requirement:**
> 공통 원칙
> - subprocess.run(shell=False)
> - pathlib 사용
> - encoding 명시 (utf-8)
> - OS별 분기 최소화

**Gap:** 🟢 **Minor** - Just audit and fix remaining issues

---

### 2.7 Tool Safety

#### **Current System: Basic Safety**

**Implementation:**
```python
# backend/app/tools/
# Tools exist but no explicit allowlist/denylist
```

---

#### **Agentic 2.0: Explicit Safety**

**Requirement:**
```yaml
tools:
  safety:
    command_allowlist:
      - python
      - pytest
      - pip
      - git

    command_denylist:
      - rm -rf /
      - dd if=
      - :(){ :|:& };:

    protected_files:
      - .env
      - secrets.yaml
```

**Gap:** 🟢 **Minor** - Need safety module

---

### 2.8 State Management

#### **Current System: Large Monolithic State**

**Problem:**
```python
# backend/app/agent/langgraph/schemas/state.py
class QualityGateState(TypedDict):
    user_request: str
    workspace_root: str
    task_type: str
    generated_code: Optional[str]
    review_feedback: Optional[str]
    security_issues: List[Dict]
    test_results: Optional[Dict]
    refinement_iteration: int
    review_approved: bool
    debug_logs: List[DebugLog]
    thinking_stream: List[str]
    # ... 20+ fields
```

**Issue:** All nodes see all fields → context pollution

---

#### **Agentic 2.0: Streamlined State**

**Requirement:**
```python
class AgenticState(TypedDict):
    # User input
    user_prompt: str
    intent: Literal["coding", "research", "data", "general"]

    # Planning
    plan: Annotated[List[str], operator.add]
    current_step: int

    # Execution
    messages: Annotated[List[Dict], add_messages]
    tool_results: Annotated[List[Dict], operator.add]
    artifacts: Annotated[List[Dict], operator.add]

    # Review
    review_feedback: str
    review_passed: bool
    iteration_count: int

    # Context
    workspace: str
    thread_id: str

    # Final
    final_report: str
    status: Literal["in_progress", "completed", "failed"]
```

**Gap:** 🟡 **Medium** - Need simplified state schema

---

## 3. Migration Strategy

### 3.1 What to Keep from Current System

✅ **Keep These Components:**
1. **LangGraph StateGraph** - Already correct framework
2. **SupervisorAgent pattern** - Good orchestration
3. **RAG integration** - Works well
4. **Streaming support** - Production-ready
5. **Tool implementations** - Most tools good
6. **Intent classification infrastructure** - Just extend it

---

### 3.2 What to Replace/Refactor

🔄 **Replace/Refactor:**
1. **LLM Client** → DualEndpointLLMClient with failover
2. **Intent Router** → Multi-domain classifier
3. **Workflow strategies** → Add sub-agent spawning
4. **State schema** → Simplified AgenticState
5. **Framework factory** → Remove, single stack only

---

### 3.3 What to Add (Net New)

➕ **Add:**
1. **ResearchWorkflow** - Document analysis, report writing
2. **DataWorkflow** - Data processing, analysis
3. **SubAgentManager** - Dynamic spawning via DeepAgents
4. **Safety module** - Command allowlist/denylist
5. **Health check system** - Endpoint monitoring
6. **JSONL logging** - Structured observability

---

## 4. Implementation Approach

### Option 1: Fork & Build Fresh (Recommended)

**Approach:**
```
agentic-coder/           # Current system (keep running)
    ├── backend/
    ├── frontend/
    └── ...

agentic-ai/              # Agentic 2.0 (new project)
    ├── core/            # DualEndpointLLMClient, router, state_graph
    ├── agents/          # Planner, Executor, Reviewer
    ├── tools/           # Copied from current + safety added
    ├── workflows/       # coding (reuse) + research + data + general
    └── config/
```

**Benefits:**
- ✅ Clean slate, follows spec exactly
- ✅ No risk to current system
- ✅ Can copy/reuse good components
- ✅ Easier to test

**Drawbacks:**
- ⚠️ Some duplication of effort
- ⚠️ Need to copy tools, RAG, etc.

---

### Option 2: In-Place Migration

**Approach:**
```
agentic-coder/
    ├── backend/
    │   ├── core/
    │   │   ├── llm_client.py       # Replace with DualEndpointLLMClient
    │   │   ├── supervisor.py       # Extend with multi-domain
    │   │   └── workflow.py         # Add sub-agent support
    │   ├── workflows/              # Add research, data
    │   └── ...
```

**Benefits:**
- ✅ No duplication
- ✅ Preserve RAG, streaming, etc.

**Drawbacks:**
- ⚠️ Risk of breaking current system
- ⚠️ Harder to test
- ⚠️ Migration complexity

---

### Recommendation: **Option 1 (Fork & Build Fresh)**

**Rationale:**
1. Spec is comprehensive and prescriptive
2. New project structure is cleaner
3. Can cherry-pick best parts of current system
4. Lower risk
5. Easier to follow "single source of truth" spec

---

## 5. Phase 0 Starting Point

Given the gaps, Phase 0 should focus on **foundation that differs most:**

### Phase 0 Tasks (Prioritized)

**Week 1:**
1. **Project Setup** (0.5 day)
   - New `agentic-ai/` directory
   - Dependencies: LangChain, LangGraph, DeepAgents
   - Copy config structure from current

2. **DualEndpointLLMClient** (1 day) 🔴 **CRITICAL DIFFERENCE**
   - Health check system
   - Exponential backoff retry
   - Failover logic

3. **Multi-Domain Intent Router** (1 day) 🔴 **NEW CAPABILITY**
   - 4-way classification (coding, research, data, general)
   - Test with diverse prompts

4. **Tool Safety Module** (0.5 day) 🟢 **NEW**
   - Allowlist/denylist enforcement
   - Protected file checks

5. **Basic Tools** (1 day)
   - Copy FS tools from current (already good)
   - Copy Git tools (already good)
   - Audit for cross-platform (subprocess shell=False)
   - Add safety wrappers

6. **Simplified State Schema** (0.5 day)
   - Define AgenticState
   - Test with basic workflow

7. **Testing** (0.5 day)
   - Unit tests for LLM client
   - Integration test for intent router
   - Cross-platform validation

---

## 6. Summary Table

| Component | Current | Agentic 2.0 | Action | Priority |
|-----------|---------|-------------|--------|----------|
| **Scope** | Coding-focused | Universal | Add research + data workflows | 🔴 High |
| **LLM Backend** | Single/round-robin | Dual + failover | Build DualEndpointLLMClient | 🔴 High |
| **Intent Classifier** | Coding-biased | Multi-domain | Extend classifier | 🔴 High |
| **Sub-Agents** | Static registry | Dynamic spawn | Integrate SubAgentMiddleware | 🟡 Medium |
| **State Schema** | 20+ fields | ~15 fields | Simplify state | 🟡 Medium |
| **Tool Safety** | Basic | Explicit allowlist | Add safety module | 🟢 Low |
| **Cross-Platform** | Mostly | Guaranteed | Audit subprocess calls | 🟢 Low |
| **Observability** | Standard | JSONL | Add structured logging | 🟢 Low |

---

**Next:** Ready to start Phase 0 implementation with this gap analysis in mind.
