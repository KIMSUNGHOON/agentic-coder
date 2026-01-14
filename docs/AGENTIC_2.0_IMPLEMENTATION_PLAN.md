# Agentic 2.0 Implementation Plan
## On-Premise Universal Agentic AI with LangChain Ecosystem

**Date:** 2026-01-14
**Version:** 1.0
**Status:** Implementation Ready
**Based on:** Project Specification + LangChain/LangGraph/DeepAgents Best Practices

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Requirements Analysis](#2-requirements-analysis)
3. [Architecture Design](#3-architecture-design)
4. [LangGraph State Machine](#4-langgraph-state-machine)
5. [Implementation Phases](#5-implementation-phases)
6. [Code Structure](#6-code-structure)
7. [Configuration Management](#7-configuration-management)
8. [Testing Strategy](#8-testing-strategy)
9. [Deployment Guide](#9-deployment-guide)

---

## 1. Executive Summary

### 1.1 Project Goal

Build a **production-ready, on-premise, universal Agentic AI system** that:
- Operates completely offline (no external SaaS dependencies)
- Supports multiple use cases (coding, research, data analysis, general QA)
- Uses LangChain/LangGraph/DeepAgents best practices
- Runs identically on Windows/macOS/Linux

### 1.2 Key Features

✅ **Dynamic Workflow** - No static chains, adaptive execution
✅ **Sub-Agent Spawning** - Dynamic agent creation based on task complexity
✅ **Self-Reflection** - Automatic retry with self-correction
✅ **Cross-Platform** - Identical behavior across OSes
✅ **Dual LLM Endpoints** - Active-active or primary/secondary with failover
✅ **Tool Safety** - Allowlist/denylist for commands

### 1.3 Technology Stack

| Component | Technology |
|-----------|-----------|
| **LLM** | GPT-OSS-120B via vLLM |
| **Orchestration** | LangGraph StateGraph |
| **Agents** | LangChain + DeepAgents |
| **Tools** | Custom Python tools (FS, Git, Search, Process) |
| **Persistence** | SQLite (default) / PostgreSQL (optional) |
| **Observability** | JSONL structured logging |

---

## 2. Requirements Analysis

### 2.1 Absolute Requirements

#### **R1: On-Premise Only**
- ✅ No external API calls except configured vLLM endpoints
- ✅ No LangSmith, OpenAI API, or cloud services
- ✅ Works in air-gapped environments

**Implementation:**
```python
# config/config.yaml
mode: on-premise
external_services:
  enabled: false

llm:
  endpoints:
    - url: http://localhost:8001/v1
      name: primary
    - url: http://localhost:8002/v1
      name: secondary
```

---

#### **R2: Dual vLLM Endpoints with Failover**
- ✅ Active-active load balancing OR primary/secondary failover
- ✅ Health checks every 30s
- ✅ Automatic failover on timeout/error
- ✅ Exponential backoff retry (2s, 4s, 8s, 16s)

**Implementation:**
```python
# core/llm_client.py
class DualEndpointLLMClient:
    def __init__(self, endpoints: List[EndpointConfig]):
        self.endpoints = endpoints
        self.health_status = {ep.name: True for ep in endpoints}
        self.current_index = 0

    async def chat_completion(self, messages, **kwargs):
        for attempt in range(4):  # Max 4 retries
            endpoint = self._get_next_healthy_endpoint()
            try:
                response = await self._call_endpoint(endpoint, messages, **kwargs)
                return response
            except (TimeoutError, ConnectionError) as e:
                self.health_status[endpoint.name] = False
                backoff = 2 ** attempt
                await asyncio.sleep(backoff)
                continue
        raise Exception("All endpoints failed")

    def _get_next_healthy_endpoint(self):
        # Round-robin through healthy endpoints
        for _ in range(len(self.endpoints)):
            ep = self.endpoints[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.endpoints)
            if self.health_status[ep.name]:
                return ep
        raise Exception("No healthy endpoints available")
```

---

#### **R3: Cross-Platform Support**
- ✅ Python 3.10+ (consistent across OSes)
- ✅ `pathlib` for all file operations
- ✅ `subprocess.run(shell=False)` for safety
- ✅ UTF-8 encoding explicit everywhere

**Implementation Principles:**
```python
# ✅ Good: Cross-platform
from pathlib import Path
workspace = Path.home() / "workspace"
file_path = workspace / "project" / "file.txt"

# ❌ Bad: OS-specific
workspace = "C:\\Users\\name\\workspace"  # Windows only
file_path = workspace + "/project/file.txt"  # String concat

# ✅ Good: Safe subprocess
result = subprocess.run(
    ["python", "-m", "pytest"],
    cwd=workspace,
    capture_output=True,
    text=True,
    encoding="utf-8",
    shell=False  # CRITICAL
)

# ❌ Bad: Shell injection risk
result = subprocess.run(
    f"python -m pytest {test_file}",
    shell=True  # DANGEROUS
)
```

---

#### **R4: Universal Agent (Not Coding-Only)**

**Supported Task Types:**
1. **Coding** - Implementation, debugging, refactoring
2. **Research** - Technical research, document summarization, report generation
3. **Data** - Data cleaning, analysis, automation
4. **General** - Q&A, recommendations, planning

**Implementation:**
```python
# agents/router_agent.py
class IntentRouter:
    """Route user prompts to appropriate workflow"""

    WORKFLOWS = {
        "coding": CodingWorkflow,
        "research": ResearchWorkflow,
        "data": DataWorkflow,
        "general": GeneralWorkflow
    }

    async def route(self, user_prompt: str) -> str:
        """Classify intent using GPT-OSS-120B"""
        classification_prompt = f"""
        Classify the following user request into one of these categories:
        - coding: Code implementation, debugging, refactoring
        - research: Technical research, document analysis, report writing
        - data: Data processing, analysis, automation
        - general: General questions, planning, recommendations

        User request: {user_prompt}

        Category:
        """

        response = await self.llm.chat_completion([
            {"role": "system", "content": "You are an intent classifier."},
            {"role": "user", "content": classification_prompt}
        ])

        intent = response.choices[0].message.content.strip().lower()
        return intent if intent in self.WORKFLOWS else "general"
```

---

#### **R5: Agentic 2.0 Requirements**

| Requirement | Implementation |
|-------------|----------------|
| **Dynamic Workflow** | LangGraph StateGraph with conditional edges |
| **Context Sharing** | Shared state dict across all agents |
| **Sub-Agent Spawn** | DeepAgents SubAgentMiddleware |
| **Self-Reflection** | Critic agent + retry loop |

---

### 2.2 Reference Architecture Mapping

**From Comprehensive Guide → Specification:**

| Guide Pattern | Spec Requirement | Implementation |
|--------------|------------------|----------------|
| **Supervisor Pattern** | Agent Router | Intent classification + workflow dispatch |
| **Hierarchical Teams** | Dynamic Sub-Agents | DeepAgents SubAgentMiddleware |
| **State Management** | Context Sharing | LangGraph shared state with reducers |
| **Tool-Calling** | Tool Layer | LangChain @tool decorator |
| **TodoListMiddleware** | Planner Agent | Explicit planning step |
| **FilesystemMiddleware** | FS Tools | read_file, write_file, apply_patch |

---

## 3. Architecture Design

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                          │
│                   (CLI / API / Web UI)                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Intent Router Agent                        │
│        (GPT-OSS-120B via DualEndpointLLMClient)             │
│   Classifies: coding | research | data | general            │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬──────────────┐
         ▼               ▼               ▼              ▼
   ┌─────────┐    ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ Coding  │    │ Research │   │   Data   │   │ General  │
   │Workflow │    │ Workflow │   │ Workflow │   │ Workflow │
   └─────────┘    └──────────┘   └──────────┘   └──────────┘
         │               │               │              │
         └───────────────┴───────────────┴──────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph State Machine                         │
│  INIT → ROUTE → PLAN → ACT → REVIEW → ITERATE → FINAL      │
│                                                              │
│  Agents:                                                     │
│  - Planner Agent (DeepAgents TodoListMiddleware)           │
│  - Executor Agent (Task-specific)                          │
│  - Critic/Reviewer Agent                                    │
│  - Sub-Agents (Dynamic spawn via SubAgentMiddleware)       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     Tool Layer                               │
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │   FS    │  │   Git   │  │ Search  │  │ Process │       │
│  │ Tools   │  │  Tools  │  │  Tools  │  │  Tools  │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
│                                                              │
│  read_file, write_file, apply_patch, search, run_cmd...    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           Persistence Layer (LangGraph Checkpointer)         │
│                 SQLite / PostgreSQL                          │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          LLM Layer (Dual Endpoint with Failover)            │
│                                                              │
│   ┌──────────────────┐        ┌──────────────────┐         │
│   │  vLLM Primary    │◄──────►│  vLLM Secondary  │         │
│   │  GPT-OSS-120B    │        │  GPT-OSS-120B    │         │
│   │ localhost:8001   │        │ localhost:8002   │         │
│   └──────────────────┘        └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

### 3.2 Workflow Comparison

#### **Coding Workflow**
```
PLAN: Break down coding task into steps
  ↓
ACT: Read existing code, understand context
  ↓
ACT: Generate implementation
  ↓
REVIEW: Check for bugs, style issues, tests
  ↓
ITERATE: Fix issues if found
  ↓
FINAL: Apply patch, run tests, write report
```

#### **Research Workflow**
```
PLAN: Define research scope and questions
  ↓
ACT: Search documents, web (if enabled), codebase
  ↓
ACT: Read and analyze sources
  ↓
REVIEW: Check completeness and accuracy
  ↓
ITERATE: Fill gaps if needed
  ↓
FINAL: Write summary report
```

#### **Data Workflow**
```
PLAN: Understand data structure and requirements
  ↓
ACT: Load and inspect data
  ↓
ACT: Clean, transform, or analyze
  ↓
REVIEW: Validate results
  ↓
ITERATE: Correct errors if found
  ↓
FINAL: Save results, write report
```

---

## 4. LangGraph State Machine

### 4.1 State Schema

```python
# core/state_graph.py
from typing import TypedDict, Annotated, List, Dict, Any, Literal
from langgraph.graph.message import add_messages

class AgenticState(TypedDict):
    """Shared state across all agents in the workflow"""

    # User input
    user_prompt: str
    intent: Literal["coding", "research", "data", "general"]

    # Planning
    plan: Annotated[List[str], operator.add]  # List of planned steps
    current_step: int

    # Execution
    messages: Annotated[List[Dict], add_messages]  # Conversation history
    tool_results: Annotated[List[Dict], operator.add]  # Tool call results
    artifacts: Annotated[List[Dict], operator.add]  # Generated files/data

    # Review & Iteration
    review_feedback: str
    review_passed: bool
    iteration_count: int
    max_iterations: int  # Default: 3

    # Context
    workspace: str
    thread_id: str
    session_id: str

    # Final output
    final_report: str
    status: Literal["in_progress", "completed", "failed"]
```

---

### 4.2 State Graph Definition

```python
from langgraph.graph import StateGraph, END

def create_agentic_workflow(workflow_type: str) -> StateGraph:
    """Create workflow based on type (coding, research, data, general)"""

    workflow = StateGraph(AgenticState)

    # Add nodes (agents)
    workflow.add_node("planner", planner_agent)
    workflow.add_node("executor", executor_agent)
    workflow.add_node("reviewer", reviewer_agent)
    workflow.add_node("finalizer", finalizer_agent)

    # Define edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")
    workflow.add_edge("executor", "reviewer")

    # Conditional edge: review decision
    workflow.add_conditional_edges(
        "reviewer",
        should_iterate,
        {
            "iterate": "planner",  # Re-plan based on feedback
            "finalize": "finalizer",  # All good, wrap up
            "fail": END  # Max iterations exceeded
        }
    )

    workflow.add_edge("finalizer", END)

    return workflow.compile(checkpointer=checkpointer)

def should_iterate(state: AgenticState) -> str:
    """Decide whether to iterate or finalize"""
    if state["iteration_count"] >= state["max_iterations"]:
        return "fail"

    if state["review_passed"]:
        return "finalize"

    return "iterate"
```

---

### 4.3 Agent Implementations

#### **Planner Agent (with TodoListMiddleware)**

```python
# agents/planner.py
from deepagents.middleware import TodoListMiddleware
from langchain_core.tools import tool

class PlannerAgent:
    """Plans the task execution using GPT-OSS-120B"""

    def __init__(self, llm_client):
        self.llm = llm_client
        self.middleware = TodoListMiddleware(
            system_prompt="Use write_todos to break down complex tasks"
        )

    async def __call__(self, state: AgenticState) -> Dict:
        """Generate execution plan"""

        # Extract user request and context
        user_prompt = state["user_prompt"]
        intent = state["intent"]
        workspace = state["workspace"]

        # Generate plan using LLM
        planning_prompt = f"""
        You are a task planner. Break down the following {intent} task into concrete steps.

        Task: {user_prompt}
        Workspace: {workspace}

        Provide 3-7 specific, actionable steps. Be concrete and detailed.
        """

        response = await self.llm.chat_completion([
            {"role": "system", "content": "You are an expert task planner."},
            {"role": "user", "content": planning_prompt}
        ])

        plan_text = response.choices[0].message.content
        plan_steps = self._parse_plan(plan_text)

        return {
            "plan": plan_steps,
            "current_step": 0,
            "messages": [{"role": "assistant", "content": f"Plan:\n{plan_text}"}]
        }

    def _parse_plan(self, plan_text: str) -> List[str]:
        """Parse plan text into list of steps"""
        lines = plan_text.strip().split('\n')
        steps = []
        for line in lines:
            line = line.strip()
            # Remove numbering (1., 2., -, etc.)
            if line and (line[0].isdigit() or line.startswith('-')):
                step = line.lstrip('0123456789.-) ').strip()
                if step:
                    steps.append(step)
        return steps
```

---

#### **Executor Agent (with Tool Calling)**

```python
# agents/executor.py
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

class ExecutorAgent:
    """Executes planned steps using available tools"""

    def __init__(self, llm_client, tools: List):
        self.llm = llm_client
        self.tools = tools

        # Create ReAct agent with tools
        self.agent = create_react_agent(
            model=llm_client,
            tools=tools
        )

    async def __call__(self, state: AgenticState) -> Dict:
        """Execute current step in plan"""

        current_step = state["current_step"]
        plan = state["plan"]

        if current_step >= len(plan):
            return {"status": "completed"}

        step_description = plan[current_step]

        # Execute step using ReAct agent
        execution_prompt = f"""
        Execute the following step:
        {step_description}

        Use available tools to complete this step.
        Be thorough and verify your work.
        """

        result = await self.agent.ainvoke({
            "messages": [{"role": "user", "content": execution_prompt}]
        })

        # Extract tool results and artifacts
        tool_results = self._extract_tool_results(result)
        artifacts = self._extract_artifacts(result)

        return {
            "current_step": current_step + 1,
            "messages": result["messages"],
            "tool_results": tool_results,
            "artifacts": artifacts
        }
```

---

#### **Reviewer Agent (Critic)**

```python
# agents/reviewer.py
class ReviewerAgent:
    """Reviews execution results and provides feedback"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def __call__(self, state: AgenticState) -> Dict:
        """Review execution and decide if iteration needed"""

        plan = state["plan"]
        messages = state["messages"]
        artifacts = state["artifacts"]

        # Create review prompt
        review_prompt = f"""
        Review the execution of this task:

        Plan: {plan}

        Execution messages: {self._summarize_messages(messages)}

        Artifacts generated: {len(artifacts)}

        Check for:
        1. Completeness - All steps executed?
        2. Correctness - Results accurate?
        3. Quality - Code/output meets standards?

        Respond with:
        - PASS: If everything looks good
        - FAIL: If issues found, with specific feedback
        """

        response = await self.llm.chat_completion([
            {"role": "system", "content": "You are a critical reviewer."},
            {"role": "user", "content": review_prompt}
        ])

        review_text = response.choices[0].message.content
        passed = review_text.strip().upper().startswith("PASS")

        return {
            "review_feedback": review_text,
            "review_passed": passed,
            "iteration_count": state["iteration_count"] + 1
        }
```

---

#### **Finalizer Agent**

```python
# agents/finalizer.py
class FinalizerAgent:
    """Generates final report and wraps up"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def __call__(self, state: AgenticState) -> Dict:
        """Generate final report"""

        user_prompt = state["user_prompt"]
        plan = state["plan"]
        artifacts = state["artifacts"]
        tool_results = state["tool_results"]

        report_prompt = f"""
        Generate a final summary report for this task:

        User Request: {user_prompt}

        Plan Executed: {plan}

        Artifacts Generated: {len(artifacts)} files/outputs

        Tool Results: {len(tool_results)} tool calls

        Provide a concise summary in markdown format with:
        1. What was accomplished
        2. Key artifacts generated
        3. Any important notes or recommendations
        """

        response = await self.llm.chat_completion([
            {"role": "system", "content": "You are a report writer."},
            {"role": "user", "content": report_prompt}
        ])

        report = response.choices[0].message.content

        return {
            "final_report": report,
            "status": "completed"
        }
```

---

### 4.4 Sub-Agent Spawning

```python
# agents/sub_agent_manager.py
from deepagents.middleware import SubAgentMiddleware
from deepagents import CompiledSubAgent

class SubAgentManager:
    """Manages dynamic sub-agent spawning"""

    def __init__(self, llm_client):
        self.llm = llm_client
        self.middleware = SubAgentMiddleware(
            default_model=llm_client,
            default_tools=[],
            subagents=[]  # Start empty, spawn dynamically
        )

    async def spawn_specialist(
        self,
        task_description: str,
        agent_type: str,
        tools: List
    ) -> Dict:
        """Spawn a specialized sub-agent for isolated task"""

        # Define sub-agent
        subagent_config = {
            "name": f"{agent_type}_specialist",
            "description": f"Specialized agent for {agent_type} tasks",
            "system_prompt": f"You are an expert in {agent_type}. {task_description}",
            "tools": tools,
            "model": self.llm
        }

        # Spawn and execute
        result = await self.middleware.execute_subagent(
            subagent_config,
            task_description
        )

        return {
            "subagent_type": agent_type,
            "task": task_description,
            "result": result
        }
```

**When to Spawn Sub-Agents:**
- Task complexity score > threshold (determined by Planner)
- Multiple distinct expertise areas needed
- Context isolation beneficial (large file processing)

---

## 5. Implementation Phases

### Phase 0: Foundation (Week 1)

**Goal:** Core infrastructure and basic workflow

**Tasks:**
1. **Project Setup** (1 day)
   - Repository structure
   - Dependencies (LangChain, LangGraph, DeepAgents)
   - Configuration system

2. **LLM Client with Dual Endpoints** (2 days)
   - `DualEndpointLLMClient` with failover
   - Health check system
   - Retry logic with exponential backoff

3. **Basic Tools** (2 days)
   - Filesystem tools (read_file, write_file)
   - Git tools (git_diff, git_status)
   - Process tools (run_cmd with safety)
   - Search tools (ripgrep integration)

**Deliverables:**
- ✅ Working dual endpoint LLM client
- ✅ 10+ tools implemented
- ✅ Cross-platform tested (Win/Mac/Linux)

---

### Phase 1: Core Workflow (Week 2)

**Goal:** Single workflow end-to-end

**Tasks:**
1. **Intent Router** (1 day)
   - Classification logic
   - Workflow dispatch

2. **LangGraph State Machine** (2 days)
   - State schema definition
   - Graph construction (INIT → PLAN → ACT → REVIEW → FINAL)
   - Conditional edges

3. **Core Agents** (2 days)
   - Planner Agent
   - Executor Agent (ReAct)
   - Reviewer Agent
   - Finalizer Agent

**Deliverables:**
- ✅ Coding workflow end-to-end
- ✅ One complete execution with iteration
- ✅ Final report generated

---

### Phase 2: Multi-Workflow Support (Week 3)

**Goal:** All 4 workflows operational

**Tasks:**
1. **Research Workflow** (1.5 days)
   - Document search and analysis
   - Report generation

2. **Data Workflow** (1.5 days)
   - Data loading and inspection
   - Transformation and analysis

3. **General Workflow** (1 day)
   - Q&A handling
   - Recommendation generation

4. **Workflow Testing** (1 day)
   - End-to-end tests for each workflow
   - Cross-workflow integration

**Deliverables:**
- ✅ 4 workflows operational
- ✅ Intent routing accurate (>90%)
- ✅ All workflows tested

---

### Phase 3: Advanced Features (Week 4)

**Goal:** Sub-agents, persistence, observability

**Tasks:**
1. **Sub-Agent Spawning** (1.5 days)
   - DeepAgents SubAgentMiddleware integration
   - Dynamic spawn logic
   - Context isolation

2. **Persistence** (1 day)
   - LangGraph Checkpointer (SQLite)
   - Thread/session management
   - State recovery

3. **Observability** (1 day)
   - JSONL structured logging
   - Agent decision tracking
   - Tool call logging

4. **Safety & Security** (0.5 day)
   - Command allowlist/denylist
   - Sensitive file protection
   - Network access control

**Deliverables:**
- ✅ Sub-agent spawning working
- ✅ Persistent state across sessions
- ✅ Complete audit trail in logs
- ✅ Safety controls active

---

### Phase 4: Production Readiness (Week 5)

**Goal:** Polish, optimize, document

**Tasks:**
1. **Performance Optimization** (1 day)
   - Endpoint selection optimization
   - Context filtering
   - Parallel tool calls

2. **Error Handling** (1 day)
   - Graceful degradation
   - User-friendly error messages
   - Recovery mechanisms

3. **Documentation** (2 days)
   - User guide
   - API documentation
   - Configuration guide
   - Troubleshooting guide

4. **Deployment Packaging** (1 day)
   - Docker images
   - Installation scripts
   - Health check endpoints

**Deliverables:**
- ✅ Production-ready system
- ✅ Complete documentation
- ✅ Deployment artifacts
- ✅ Performance benchmarks

---

## 6. Code Structure

### 6.1 Repository Layout

```
agentic_ai/
├── README.md
├── requirements.txt
├── setup.py
├── config/
│   ├── config.yaml                 # Main configuration
│   ├── config.dev.yaml             # Development overrides
│   └── config.prod.yaml            # Production overrides
│
├── core/
│   ├── __init__.py
│   ├── llm_client.py               # DualEndpointLLMClient
│   ├── router.py                   # IntentRouter
│   ├── state_graph.py              # LangGraph StateGraph definitions
│   ├── memory.py                   # Checkpointer & persistence
│   └── logging_config.py           # Structured logging setup
│
├── agents/
│   ├── __init__.py
│   ├── planner.py                  # PlannerAgent
│   ├── executor.py                 # ExecutorAgent (ReAct)
│   ├── reviewer.py                 # ReviewerAgent (Critic)
│   ├── finalizer.py                # FinalizerAgent
│   ├── router_agent.py             # IntentRouter logic
│   ├── sub_agent_manager.py        # SubAgentMiddleware wrapper
│   └── specialized/                # Workflow-specific agents
│       ├── coding_agent.py
│       ├── research_agent.py
│       ├── data_agent.py
│       └── general_agent.py
│
├── tools/
│   ├── __init__.py
│   ├── fs.py                       # read_file, write_file, apply_patch
│   ├── git.py                      # git_diff, git_status, git_log
│   ├── process.py                  # run_cmd (with safety)
│   ├── search.py                   # ripgrep, code search
│   └── safety.py                   # Allowlist/denylist enforcement
│
├── workflows/
│   ├── __init__.py
│   ├── coding.py                   # Coding workflow definition
│   ├── research.py                 # Research workflow definition
│   ├── data.py                     # Data workflow definition
│   └── general.py                  # General workflow definition
│
├── utils/
│   ├── __init__.py
│   ├── cross_platform.py           # OS compatibility helpers
│   ├── health_check.py             # Endpoint health monitoring
│   └── markdown.py                 # Report generation helpers
│
├── tests/
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── e2e/                        # End-to-end tests
│
├── cli.py                          # Command-line interface
├── api.py                          # (Optional) FastAPI server
└── main.py                         # Entry point
```

---

### 6.2 Key Files Implementation

#### **config/config.yaml**

```yaml
# Agentic 2.0 Configuration

mode: on-premise

llm:
  model_name: gpt-oss-120b
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

  parameters:
    temperature: 0.7
    top_p: 0.95
    max_tokens: 4096

workflows:
  max_iterations: 3
  timeout_seconds: 600

tools:
  safety:
    command_allowlist:
      - python
      - pytest
      - pip
      - git
      - ls
      - cat
      - grep

    command_denylist:
      - rm -rf /
      - dd if=
      - :(){ :|:& };:

    protected_files:
      - .env
      - secrets.yaml
      - credentials.json

persistence:
  backend: sqlite  # or postgresql
  database_url: sqlite:///./agentic.db

logging:
  level: INFO
  format: jsonl
  file: logs/agentic.log

workspace:
  default_path: ~/workspace
  isolation: true
```

---

#### **core/llm_client.py**

```python
# core/llm_client.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
import time

logger = logging.getLogger(__name__)

@dataclass
class EndpointConfig:
    url: str
    name: str
    timeout: int = 120

class DualEndpointLLMClient:
    """LLM client with dual endpoint support and failover"""

    def __init__(
        self,
        endpoints: List[EndpointConfig],
        model_name: str = "gpt-oss-120b",
        health_check_interval: int = 30,
        max_retries: int = 4,
        backoff_base: int = 2
    ):
        self.endpoints = endpoints
        self.model_name = model_name
        self.health_check_interval = health_check_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        # Health status tracking
        self.health_status = {ep.name: True for ep in endpoints}
        self.last_health_check = {ep.name: 0.0 for ep in endpoints}

        # Round-robin index
        self.current_index = 0

        # Create OpenAI clients for each endpoint
        self.clients = {
            ep.name: AsyncOpenAI(
                base_url=ep.url,
                api_key="not-needed",  # vLLM doesn't require API key
                timeout=ep.timeout
            )
            for ep in endpoints
        }

        logger.info(f"Initialized DualEndpointLLMClient with {len(endpoints)} endpoints")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        **kwargs
    ) -> Any:
        """Make chat completion request with automatic failover"""

        for attempt in range(self.max_retries):
            endpoint = self._get_next_healthy_endpoint()

            if not endpoint:
                logger.error("No healthy endpoints available")
                await asyncio.sleep(self.backoff_base ** attempt)
                continue

            try:
                logger.info(f"Attempting request on {endpoint.name} (attempt {attempt + 1}/{self.max_retries})")

                client = self.clients[endpoint.name]
                response = await client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    **kwargs
                )

                logger.info(f"Request successful on {endpoint.name}")
                return response

            except (TimeoutError, ConnectionError, Exception) as e:
                logger.warning(f"Request failed on {endpoint.name}: {e}")
                self.health_status[endpoint.name] = False

                if attempt < self.max_retries - 1:
                    backoff = self.backoff_base ** attempt
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                continue

        raise Exception(f"All {self.max_retries} attempts failed on all endpoints")

    def _get_next_healthy_endpoint(self) -> Optional[EndpointConfig]:
        """Get next healthy endpoint using round-robin"""

        # Check if health checks needed
        current_time = time.time()
        for ep in self.endpoints:
            if current_time - self.last_health_check[ep.name] > self.health_check_interval:
                self._check_endpoint_health(ep)
                self.last_health_check[ep.name] = current_time

        # Round-robin through healthy endpoints
        for _ in range(len(self.endpoints)):
            ep = self.endpoints[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.endpoints)

            if self.health_status[ep.name]:
                return ep

        return None

    def _check_endpoint_health(self, endpoint: EndpointConfig):
        """Check if endpoint is healthy (simple test)"""
        try:
            # TODO: Implement actual health check (e.g., /health endpoint)
            self.health_status[endpoint.name] = True
            logger.debug(f"Health check passed for {endpoint.name}")
        except Exception as e:
            self.health_status[endpoint.name] = False
            logger.warning(f"Health check failed for {endpoint.name}: {e}")

    async def embed(self, text: str) -> List[float]:
        """Get embeddings (if supported by vLLM)"""
        # Note: GPT-OSS-120B may not support embeddings
        # This is a placeholder for future models
        raise NotImplementedError("Embeddings not yet supported")
```

---

#### **agents/planner.py** (Complete)

```python
# agents/planner.py
import logging
from typing import Dict, List
from core.state_graph import AgenticState

logger = logging.getLogger(__name__)

class PlannerAgent:
    """Plans task execution by breaking down user request into steps"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def __call__(self, state: AgenticState) -> Dict:
        """Generate execution plan based on user prompt and intent"""

        user_prompt = state["user_prompt"]
        intent = state["intent"]
        workspace = state["workspace"]

        # Build planning prompt based on intent
        planning_prompt = self._build_planning_prompt(user_prompt, intent, workspace)

        # Get plan from LLM
        response = await self.llm.chat_completion([
            {"role": "system", "content": self._get_system_prompt(intent)},
            {"role": "user", "content": planning_prompt}
        ])

        plan_text = response.choices[0].message.content
        plan_steps = self._parse_plan(plan_text)

        logger.info(f"Generated plan with {len(plan_steps)} steps")
        for i, step in enumerate(plan_steps, 1):
            logger.info(f"  Step {i}: {step}")

        return {
            "plan": plan_steps,
            "current_step": 0,
            "messages": [{"role": "assistant", "content": f"Plan:\n{plan_text}"}]
        }

    def _get_system_prompt(self, intent: str) -> str:
        """Get system prompt based on intent"""
        prompts = {
            "coding": "You are an expert software architect. Break down coding tasks into clear, testable steps.",
            "research": "You are an expert researcher. Structure research tasks into systematic investigation steps.",
            "data": "You are a data analysis expert. Organize data tasks into loading, processing, and analysis steps.",
            "general": "You are a helpful assistant. Break down tasks into clear, actionable steps."
        }
        return prompts.get(intent, prompts["general"])

    def _build_planning_prompt(self, user_prompt: str, intent: str, workspace: str) -> str:
        """Build planning prompt"""
        return f"""
Break down the following {intent} task into 3-7 concrete, actionable steps.

Task: {user_prompt}

Workspace: {workspace}

Requirements:
- Each step should be specific and executable
- Steps should be in logical order
- Include verification/testing steps where appropriate
- Be realistic about what can be accomplished

Provide your plan as a numbered list. Be concise but clear.
"""

    def _parse_plan(self, plan_text: str) -> List[str]:
        """Parse plan text into list of steps"""
        lines = plan_text.strip().split('\n')
        steps = []

        for line in lines:
            line = line.strip()
            # Skip empty lines
            if not line:
                continue

            # Remove numbering (1., 2., -, *, etc.)
            step = line.lstrip('0123456789.-*)# ').strip()

            if step:
                steps.append(step)

        return steps
```

---

## 7. Configuration Management

### 7.1 Configuration Loading

```python
# core/config_loader.py
import yaml
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, field

@dataclass
class LLMConfig:
    model_name: str
    endpoints: List[Dict[str, Any]]
    health_check: Dict[str, Any]
    retry: Dict[str, int]
    parameters: Dict[str, float]

@dataclass
class Config:
    mode: str
    llm: LLMConfig
    workflows: Dict[str, Any]
    tools: Dict[str, Any]
    persistence: Dict[str, str]
    logging: Dict[str, str]
    workspace: Dict[str, str]

    @classmethod
    def load(cls, config_path: str = "config/config.yaml") -> "Config":
        """Load configuration from YAML file"""
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Parse LLM config
        llm_config = LLMConfig(
            model_name=data["llm"]["model_name"],
            endpoints=data["llm"]["endpoints"],
            health_check=data["llm"]["health_check"],
            retry=data["llm"]["retry"],
            parameters=data["llm"]["parameters"]
        )

        return cls(
            mode=data["mode"],
            llm=llm_config,
            workflows=data["workflows"],
            tools=data["tools"],
            persistence=data["persistence"],
            logging=data["logging"],
            workspace=data["workspace"]
        )
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# tests/unit/test_planner.py
import pytest
from agents.planner import PlannerAgent
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_planner_generates_valid_plan():
    # Mock LLM client
    mock_llm = Mock()
    mock_llm.chat_completion = AsyncMock(return_value=Mock(
        choices=[Mock(message=Mock(content="""
1. Read existing code
2. Identify bug location
3. Write fix
4. Test fix
5. Apply patch
"""))]
    ))

    planner = PlannerAgent(mock_llm)

    state = {
        "user_prompt": "Fix the bug in auth.py",
        "intent": "coding",
        "workspace": "/tmp/test"
    }

    result = await planner(state)

    assert "plan" in result
    assert len(result["plan"]) == 5
    assert result["current_step"] == 0
```

### 8.2 Integration Tests

```python
# tests/integration/test_workflow_end_to_end.py
import pytest
from core.state_graph import create_agentic_workflow
from core.llm_client import DualEndpointLLMClient

@pytest.mark.asyncio
async def test_coding_workflow_end_to_end():
    # Setup
    endpoints = [
        {"url": "http://localhost:8001/v1", "name": "primary"},
    ]
    llm_client = DualEndpointLLMClient(endpoints)
    workflow = create_agentic_workflow("coding")

    # Initial state
    initial_state = {
        "user_prompt": "Write a function to calculate fibonacci numbers",
        "intent": "coding",
        "workspace": "/tmp/test_workspace",
        "max_iterations": 2
    }

    # Execute workflow
    final_state = await workflow.ainvoke(initial_state)

    # Assertions
    assert final_state["status"] == "completed"
    assert len(final_state["artifacts"]) > 0
    assert final_state["final_report"] != ""
```

---

## 9. Deployment Guide

### 9.1 Prerequisites

1. **vLLM Servers Running:**
   ```bash
   # Terminal 1: Primary endpoint
   vllm serve openai/gpt-oss-120b \
       --port 8001 \
       --tensor-parallel-size 4

   # Terminal 2: Secondary endpoint (optional)
   vllm serve openai/gpt-oss-120b \
       --port 8002 \
       --tensor-parallel-size 4
   ```

2. **Python 3.10+ installed**
3. **Git installed**

### 9.2 Installation

```bash
# Clone repository
git clone https://github.com/your-org/agentic-ai.git
cd agentic-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Create configuration
cp config/config.yaml.example config/config.yaml
# Edit config/config.yaml with your vLLM endpoints

# Initialize database
python -m core.memory init

# Run tests
pytest tests/
```

### 9.3 Usage

```bash
# CLI mode
python cli.py "Write a function to sort a list of dictionaries by key"

# With specific workflow
python cli.py --workflow coding "Fix the bug in auth.py"

# Interactive mode
python cli.py --interactive

# API server mode
python api.py
# Access at http://localhost:8000
```

---

## 10. Next Steps

Based on your preference, I can immediately provide:

### Option 1: **Complete Planner Agent Code**
Full implementation with TodoListMiddleware integration

### Option 2: **Complete Executor Agent Code**
ReAct agent with all tools integrated

### Option 3: **Tool Implementation Code**
All 10+ tools (fs, git, process, search) with cross-platform support

### Option 4: **Main Entry Point Code**
`main.py` and `cli.py` to tie everything together

### Option 5: **Start Phase 0 Implementation**
Begin actual coding with project setup

---

**Which option would you like me to proceed with?**

Or let me know if you'd like to:
- Refine any section of this plan
- See more detailed examples
- Discuss architecture trade-offs
- Start implementation immediately
