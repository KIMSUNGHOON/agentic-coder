# DeepAgent Phase 1: Foundation - Development Plan

**Version:** 1.0
**Date:** 2025-12-08
**Status:** In Development
**Branch:** claude/deepagent-phase-1-dev-01UGmmX3LGdT2LUwqe2SEjPW

---

## Executive Summary

This document outlines the Phase 1 implementation plan for **Next DeepAgent**, building upon the comprehensive planning document (DEEPAGENT_PLAN.md) and the current system capabilities. Phase 1 focuses on establishing the **foundation** for advanced autonomous coding capabilities through:

1. **Tool Execution Framework** - Safe, sandboxed execution of development tools
2. **Agent Registry & Spawner** - Dynamic creation and management of specialized agents
3. **Enhanced Memory System** - Improved context management with knowledge graphs

**Timeline:** 4 weeks
**Objective:** Transform the current 3-stage workflow system into a flexible, tool-enabled multi-agent platform

---

## Current System Baseline

### Existing Capabilities ✓
- **Multi-Agent Workflow**: Planning → Coding → Review (3 stages)
- **Dual-Model Routing**: DeepSeek-R1 (reasoning) + Qwen3-Coder (coding)
- **Real-Time Streaming**: SSE streaming for all agent outputs
- **Conversation Persistence**: SQLite with full history
- **Vector Search**: ChromaDB for semantic code search
- **LM Cache**: Response caching with TTL
- **Modern Frontend**: React + TypeScript with workflow visualization

### Key Limitations to Address
- ❌ **No Tool Execution**: Agents cannot read files, execute code, or use Git
- ❌ **Fixed Workflow**: Rigid 3-agent pipeline, no dynamic adaptation
- ❌ **Limited Context**: Only conversation history, no knowledge graphs
- ❌ **No Agent Spawning**: Cannot create specialized agents on-demand
- ❌ **Basic Memory**: Simple sliding window, no structured knowledge

---

## Phase 1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    DeepAgent Phase 1                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │          Tool Execution Layer (NEW)                │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐     │   │
│  │  │File Tools  │ │Code Tools  │ │Git Tools   │     │   │
│  │  │- read      │ │- execute   │ │- status    │     │   │
│  │  │- write     │ │- sandbox   │ │- diff      │     │   │
│  │  │- search    │ │- test      │ │- commit    │     │   │
│  │  └────────────┘ └────────────┘ └────────────┘     │   │
│  │  ┌────────────────────────────────────────┐        │   │
│  │  │  Tool Executor (Sandbox + Safety)      │        │   │
│  │  └────────────────────────────────────────┘        │   │
│  └────────────────────┬───────────────────────────────┘   │
│                       │                                    │
│  ┌────────────────────┴───────────────────────────────┐   │
│  │      Agent Registry & Spawner (NEW)                │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐     │   │
│  │  │Research    │ │Planning    │ │Coding      │     │   │
│  │  │Agent       │ │Agent       │ │Agent       │     │   │
│  │  └────────────┘ └────────────┘ └────────────┘     │   │
│  │  ┌────────────┐ ┌────────────┐                    │   │
│  │  │Testing     │ │Review      │                    │   │
│  │  │Agent       │ │Agent       │                    │   │
│  │  └────────────┘ └────────────┘                    │   │
│  │  ┌──────────────────────────────────────┐         │   │
│  │  │  Agent Spawner & Registry            │         │   │
│  │  └──────────────────────────────────────┘         │   │
│  └────────────────────┬───────────────────────────────┘   │
│                       │                                    │
│  ┌────────────────────┴───────────────────────────────┐   │
│  │    Enhanced Memory System (ENHANCED)               │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐     │   │
│  │  │Context Mgr │ │Knowledge   │ │Learning DB │     │   │
│  │  │(enhanced)  │ │Graph (new) │ │(new)       │     │   │
│  │  └────────────┘ └────────────┘ └────────────┘     │   │
│  └────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         Existing Infrastructure                     │  │
│  │  - VLLMRouter (DeepSeek-R1 + Qwen3-Coder)          │  │
│  │  - Vector DB (ChromaDB)                            │  │
│  │  - LM Cache (Redis + File)                         │  │
│  │  - Conversation DB (SQLite)                        │  │
│  │  - Streaming (SSE)                                 │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Week 1: Tool Execution Framework

#### Objectives
- Create safe, sandboxed tool execution environment
- Implement core file, code, and Git tools
- Add API endpoints for tool invocation

#### Tasks

**1.1 Base Tool Infrastructure**

Create `backend/app/tools/` directory structure:

```
backend/app/tools/
├── __init__.py
├── base.py              # Base tool interface and types
├── executor.py          # Tool execution engine with safety
├── sandbox.py           # Docker-based sandbox (Phase 2)
├── file_tools.py        # File operations
├── code_tools.py        # Code execution
├── git_tools.py         # Git operations
└── registry.py          # Tool registry and discovery
```

**File: `tools/base.py`**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum

class ToolCategory(Enum):
    FILE = "file"
    CODE = "code"
    GIT = "git"
    WEB = "web"

@dataclass
class ToolResult:
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None

class BaseTool(ABC):
    def __init__(self, name: str, category: ToolCategory):
        self.name = name
        self.category = category
        self.description = ""
        self.parameters = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass

    @abstractmethod
    def validate_params(self, **kwargs) -> bool:
        """Validate parameters before execution"""
        pass

    def get_schema(self) -> Dict:
        """Return JSON schema for tool parameters"""
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "parameters": self.parameters
        }
```

**File: `tools/executor.py`**
```python
import asyncio
from typing import Dict, Optional
from .base import BaseTool, ToolResult
from .registry import ToolRegistry

class ToolExecutor:
    def __init__(self, timeout: int = 30, max_memory_mb: int = 512):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.registry = ToolRegistry()

    async def execute(
        self,
        tool_name: str,
        params: Dict,
        session_id: str
    ) -> ToolResult:
        """Execute a tool with safety checks"""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{tool_name}' not found"
            )

        # Validate parameters
        if not tool.validate_params(**params):
            return ToolResult(
                success=False,
                output=None,
                error="Invalid parameters"
            )

        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(**params),
                timeout=self.timeout
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool execution exceeded {self.timeout}s timeout"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )
```

**1.2 File Tools Implementation**

**File: `tools/file_tools.py`**
```python
import os
import pathlib
from typing import List, Optional
from .base import BaseTool, ToolCategory, ToolResult

class ReadFileTool(BaseTool):
    def __init__(self):
        super().__init__("read_file", ToolCategory.FILE)
        self.description = "Read contents of a file"
        self.parameters = {
            "path": {"type": "string", "required": True},
            "max_size_mb": {"type": "number", "default": 10}
        }

    def validate_params(self, path: str, **kwargs) -> bool:
        return isinstance(path, str) and len(path) > 0

    async def execute(self, path: str, max_size_mb: int = 10) -> ToolResult:
        try:
            file_path = pathlib.Path(path)

            # Security checks
            if not file_path.exists():
                return ToolResult(False, None, f"File not found: {path}")

            if not file_path.is_file():
                return ToolResult(False, None, f"Not a file: {path}")

            # Size check
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > max_size_mb:
                return ToolResult(False, None, f"File too large: {size_mb:.2f}MB")

            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return ToolResult(
                success=True,
                output=content,
                metadata={"size_mb": size_mb, "lines": len(content.splitlines())}
            )
        except Exception as e:
            return ToolResult(False, None, str(e))

class WriteFileTool(BaseTool):
    def __init__(self):
        super().__init__("write_file", ToolCategory.FILE)
        self.description = "Write content to a file"
        self.parameters = {
            "path": {"type": "string", "required": True},
            "content": {"type": "string", "required": True},
            "create_dirs": {"type": "boolean", "default": True}
        }

    def validate_params(self, path: str, content: str, **kwargs) -> bool:
        return isinstance(path, str) and isinstance(content, str)

    async def execute(
        self,
        path: str,
        content: str,
        create_dirs: bool = True
    ) -> ToolResult:
        try:
            file_path = pathlib.Path(path)

            # Create parent directories if needed
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"File written: {path}",
                metadata={"bytes": len(content)}
            )
        except Exception as e:
            return ToolResult(False, None, str(e))

class SearchFilesTool(BaseTool):
    def __init__(self):
        super().__init__("search_files", ToolCategory.FILE)
        self.description = "Search for files by pattern"
        self.parameters = {
            "pattern": {"type": "string", "required": True},
            "path": {"type": "string", "default": "."},
            "max_results": {"type": "number", "default": 100}
        }

    def validate_params(self, pattern: str, **kwargs) -> bool:
        return isinstance(pattern, str) and len(pattern) > 0

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 100
    ) -> ToolResult:
        try:
            base_path = pathlib.Path(path)
            results = list(base_path.rglob(pattern))[:max_results]

            file_list = [str(p) for p in results if p.is_file()]

            return ToolResult(
                success=True,
                output=file_list,
                metadata={"count": len(file_list), "truncated": len(results) >= max_results}
            )
        except Exception as e:
            return ToolResult(False, None, str(e))
```

**1.3 Code Execution Tools**

**File: `tools/code_tools.py`**
```python
import subprocess
import tempfile
import pathlib
from .base import BaseTool, ToolCategory, ToolResult

class ExecutePythonTool(BaseTool):
    def __init__(self):
        super().__init__("execute_python", ToolCategory.CODE)
        self.description = "Execute Python code in a safe environment"
        self.parameters = {
            "code": {"type": "string", "required": True},
            "timeout": {"type": "number", "default": 30}
        }

    def validate_params(self, code: str, **kwargs) -> bool:
        return isinstance(code, str) and len(code) > 0

    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                temp_path = f.name

            try:
                # Execute in subprocess with timeout
                result = subprocess.run(
                    ['python3', temp_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

                return ToolResult(
                    success=result.returncode == 0,
                    output={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode
                    }
                )
            finally:
                # Clean up temp file
                pathlib.Path(temp_path).unlink(missing_ok=True)

        except subprocess.TimeoutExpired:
            return ToolResult(False, None, f"Execution timeout ({timeout}s)")
        except Exception as e:
            return ToolResult(False, None, str(e))

class RunTestsTool(BaseTool):
    def __init__(self):
        super().__init__("run_tests", ToolCategory.CODE)
        self.description = "Run pytest tests"
        self.parameters = {
            "test_path": {"type": "string", "required": True},
            "timeout": {"type": "number", "default": 300}
        }

    def validate_params(self, test_path: str, **kwargs) -> bool:
        return isinstance(test_path, str)

    async def execute(self, test_path: str, timeout: int = 300) -> ToolResult:
        try:
            result = subprocess.run(
                ['pytest', test_path, '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return ToolResult(
                success=result.returncode == 0,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "passed": result.returncode == 0
                }
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, None, f"Test timeout ({timeout}s)")
        except Exception as e:
            return ToolResult(False, None, str(e))
```

**1.4 Git Tools**

**File: `tools/git_tools.py`**
```python
import subprocess
from .base import BaseTool, ToolCategory, ToolResult

class GitStatusTool(BaseTool):
    def __init__(self):
        super().__init__("git_status", ToolCategory.GIT)
        self.description = "Get git repository status"
        self.parameters = {}

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(self) -> ToolResult:
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=10
            )

            return ToolResult(
                success=True,
                output=result.stdout
            )
        except Exception as e:
            return ToolResult(False, None, str(e))

class GitDiffTool(BaseTool):
    def __init__(self):
        super().__init__("git_diff", ToolCategory.GIT)
        self.description = "View git changes"
        self.parameters = {
            "cached": {"type": "boolean", "default": False}
        }

    def validate_params(self, **kwargs) -> bool:
        return True

    async def execute(self, cached: bool = False) -> ToolResult:
        try:
            cmd = ['git', 'diff']
            if cached:
                cmd.append('--cached')

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            return ToolResult(
                success=True,
                output=result.stdout
            )
        except Exception as e:
            return ToolResult(False, None, str(e))
```

**1.5 Tool Registry**

**File: `tools/registry.py`**
```python
from typing import Dict, List, Optional
from .base import BaseTool, ToolCategory
from .file_tools import ReadFileTool, WriteFileTool, SearchFilesTool
from .code_tools import ExecutePythonTool, RunTestsTool
from .git_tools import GitStatusTool, GitDiffTool

class ToolRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
        self._initialized = True

    def _register_default_tools(self):
        """Register all default tools"""
        default_tools = [
            # File tools
            ReadFileTool(),
            WriteFileTool(),
            SearchFilesTool(),
            # Code tools
            ExecutePythonTool(),
            RunTestsTool(),
            # Git tools
            GitStatusTool(),
            GitDiffTool(),
        ]

        for tool in default_tools:
            self.register(tool)

    def register(self, tool: BaseTool):
        """Register a new tool"""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[BaseTool]:
        """List all tools, optionally filtered by category"""
        if category:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict]:
        """Get schemas for all tools"""
        return [tool.get_schema() for tool in self._tools.values()]
```

**1.6 API Endpoints**

Add to `backend/app/api/routes.py`:

```python
# Tool execution endpoints
@app.post("/api/tools/execute", response_model=Dict)
async def execute_tool(
    tool_name: str,
    params: Dict,
    session_id: str = "default"
):
    """Execute a tool with given parameters"""
    from app.tools.executor import ToolExecutor

    executor = ToolExecutor()
    result = await executor.execute(tool_name, params, session_id)

    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "execution_time": result.execution_time,
        "metadata": result.metadata
    }

@app.get("/api/tools/list", response_model=List[Dict])
async def list_tools(category: Optional[str] = None):
    """List available tools"""
    from app.tools.registry import ToolRegistry
    from app.tools.base import ToolCategory

    registry = ToolRegistry()

    if category:
        tools = registry.list_tools(ToolCategory(category))
    else:
        tools = registry.list_tools()

    return [tool.get_schema() for tool in tools]

@app.get("/api/tools/{tool_name}/schema", response_model=Dict)
async def get_tool_schema(tool_name: str):
    """Get schema for a specific tool"""
    from app.tools.registry import ToolRegistry

    registry = ToolRegistry()
    tool = registry.get_tool(tool_name)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return tool.get_schema()
```

#### Deliverables (Week 1)
- ✅ Complete tool execution framework
- ✅ 7 working tools (file, code, git)
- ✅ API endpoints for tool management
- ✅ Basic safety and timeout mechanisms

---

### Week 2: Agent Registry & Spawner

#### Objectives
- Create dynamic agent creation system
- Implement specialized agent types
- Add agent lifecycle management

#### Tasks

**2.1 Agent Base Classes**

Create `backend/app/agent/specialized/` directory:

```
backend/app/agent/specialized/
├── __init__.py
├── base_specialized_agent.py    # Base class for specialized agents
├── research_agent.py             # Research & exploration
├── planning_agent.py             # Enhanced planning
├── coding_agent.py               # Code generation (refactored)
├── testing_agent.py              # Test generation
├── review_agent.py               # Code review (refactored)
└── debug_agent.py                # Debugging assistance
```

**File: `agent/specialized/base_specialized_agent.py`**
```python
from typing import List, Dict, Any, Optional, AsyncGenerator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..agent_manager import CodingAgent
from ...tools.executor import ToolExecutor

@dataclass
class AgentCapabilities:
    """Defines what an agent can do"""
    can_use_tools: bool = True
    allowed_tools: List[str] = None  # None = all tools
    can_spawn_agents: bool = False
    max_iterations: int = 5
    requires_human_approval: bool = False

class BaseSpecializedAgent(ABC):
    """Base class for all specialized agents"""

    def __init__(
        self,
        agent_type: str,
        model_name: str,
        capabilities: AgentCapabilities,
        session_id: str
    ):
        self.agent_type = agent_type
        self.model_name = model_name
        self.capabilities = capabilities
        self.session_id = session_id
        self.tool_executor = ToolExecutor() if capabilities.can_use_tools else None
        self.history: List[Dict] = []

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent"""
        pass

    @abstractmethod
    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task and return results"""
        pass

    async def use_tool(self, tool_name: str, params: Dict) -> Any:
        """Execute a tool if permitted"""
        if not self.capabilities.can_use_tools:
            raise PermissionError(f"Agent {self.agent_type} cannot use tools")

        if self.capabilities.allowed_tools and tool_name not in self.capabilities.allowed_tools:
            raise PermissionError(f"Tool {tool_name} not allowed for {self.agent_type}")

        result = await self.tool_executor.execute(tool_name, params, self.session_id)
        return result
```

**2.2 Specialized Agent Implementations**

**File: `agent/specialized/research_agent.py`**
```python
from .base_specialized_agent import BaseSpecializedAgent, AgentCapabilities
from typing import Dict, Any

class ResearchAgent(BaseSpecializedAgent):
    """Agent specialized in code exploration and research"""

    def __init__(self, session_id: str):
        capabilities = AgentCapabilities(
            can_use_tools=True,
            allowed_tools=["read_file", "search_files", "git_status"],
            can_spawn_agents=False,
            max_iterations=3
        )
        super().__init__(
            agent_type="research",
            model_name="deepseek-r1",  # Use reasoning model
            capabilities=capabilities,
            session_id=session_id
        )

    def get_system_prompt(self) -> str:
        return """You are a Research Agent specialized in exploring codebases.

Your responsibilities:
1. Read and analyze existing code files
2. Search for relevant code patterns
3. Understand project structure and architecture
4. Gather requirements and context
5. Identify similar implementations

You have access to these tools:
- read_file: Read file contents
- search_files: Search for files by pattern
- git_status: Check repository status

Always provide thorough analysis and context for other agents."""

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Research task and gather context"""
        results = {
            "findings": [],
            "relevant_files": [],
            "context": {}
        }

        # Example: Search for relevant files
        if "search_pattern" in context:
            search_result = await self.use_tool(
                "search_files",
                {"pattern": context["search_pattern"]}
            )
            results["relevant_files"] = search_result.output if search_result.success else []

        return results
```

**File: `agent/specialized/testing_agent.py`**
```python
from .base_specialized_agent import BaseSpecializedAgent, AgentCapabilities
from typing import Dict, Any

class TestingAgent(BaseSpecializedAgent):
    """Agent specialized in test generation"""

    def __init__(self, session_id: str):
        capabilities = AgentCapabilities(
            can_use_tools=True,
            allowed_tools=["read_file", "write_file", "run_tests"],
            can_spawn_agents=False,
            max_iterations=5
        )
        super().__init__(
            agent_type="testing",
            model_name="qwen3-coder",  # Use coding model
            capabilities=capabilities,
            session_id=session_id
        )

    def get_system_prompt(self) -> str:
        return """You are a Testing Agent specialized in creating comprehensive tests.

Your responsibilities:
1. Generate unit tests for given code
2. Create integration tests
3. Write test fixtures and mocks
4. Run tests and interpret results
5. Ensure high code coverage

You have access to these tools:
- read_file: Read code to test
- write_file: Write test files
- run_tests: Execute pytest tests

Follow testing best practices: arrange-act-assert, descriptive names, edge cases."""

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and run tests"""
        results = {
            "test_file": None,
            "test_results": None,
            "coverage": 0
        }

        # Implementation will call LLM to generate tests
        # Then use write_file and run_tests tools

        return results
```

**2.3 Agent Registry & Spawner**

**File: `agent/registry.py`**
```python
from typing import Dict, Type, Optional
from .specialized.base_specialized_agent import BaseSpecializedAgent
from .specialized.research_agent import ResearchAgent
from .specialized.testing_agent import TestingAgent
# Import other specialized agents...

class AgentRegistry:
    """Registry for all agent types"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._agent_types: Dict[str, Type[BaseSpecializedAgent]] = {}
        self._register_default_agents()
        self._initialized = True

    def _register_default_agents(self):
        """Register all default agent types"""
        self.register("research", ResearchAgent)
        self.register("testing", TestingAgent)
        # Register others...

    def register(self, agent_type: str, agent_class: Type[BaseSpecializedAgent]):
        """Register a new agent type"""
        self._agent_types[agent_type] = agent_class

    def get_agent_class(self, agent_type: str) -> Optional[Type[BaseSpecializedAgent]]:
        """Get agent class by type"""
        return self._agent_types.get(agent_type)

    def list_agent_types(self) -> list[str]:
        """List all registered agent types"""
        return list(self._agent_types.keys())

class AgentSpawner:
    """Factory for creating agent instances"""

    def __init__(self):
        self.registry = AgentRegistry()
        self._active_agents: Dict[str, BaseSpecializedAgent] = {}

    def spawn(self, agent_type: str, session_id: str) -> BaseSpecializedAgent:
        """Spawn a new agent instance"""
        agent_class = self.registry.get_agent_class(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type}")

        agent_id = f"{agent_type}_{session_id}"
        agent = agent_class(session_id=session_id)
        self._active_agents[agent_id] = agent

        return agent

    def get_agent(self, agent_id: str) -> Optional[BaseSpecializedAgent]:
        """Get an existing agent"""
        return self._active_agents.get(agent_id)

    def terminate(self, agent_id: str):
        """Terminate an agent"""
        if agent_id in self._active_agents:
            del self._active_agents[agent_id]

    def list_active(self) -> list[str]:
        """List active agent IDs"""
        return list(self._active_agents.keys())

# Global spawner instance
agent_spawner = AgentSpawner()
```

**2.4 API Endpoints for Agents**

Add to `routes.py`:

```python
@app.post("/api/agents/spawn")
async def spawn_agent(agent_type: str, session_id: str):
    """Spawn a new specialized agent"""
    from app.agent.registry import agent_spawner

    try:
        agent = agent_spawner.spawn(agent_type, session_id)
        return {
            "success": True,
            "agent_id": f"{agent_type}_{session_id}",
            "agent_type": agent.agent_type,
            "capabilities": agent.capabilities.__dict__
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/agents/types")
async def list_agent_types():
    """List available agent types"""
    from app.agent.registry import AgentRegistry

    registry = AgentRegistry()
    return {
        "agent_types": registry.list_agent_types()
    }

@app.get("/api/agents/active")
async def list_active_agents():
    """List active agent instances"""
    from app.agent.registry import agent_spawner

    return {
        "active_agents": agent_spawner.list_active()
    }
```

#### Deliverables (Week 2)
- ✅ Agent registry and spawner system
- ✅ 5 specialized agent types
- ✅ Dynamic agent creation API
- ✅ Agent lifecycle management

---

### Week 3: Enhanced Memory System

#### Objectives
- Implement knowledge graph for concept relationships
- Create learning database for pattern storage
- Enhance context manager

#### Tasks

**3.1 Knowledge Graph**

**File: `backend/app/memory/knowledge_graph.py`**
```python
from typing import List, Dict, Optional
import networkx as nx
import json
from dataclasses import dataclass

@dataclass
class Concept:
    """Represents a concept in the knowledge graph"""
    id: str
    type: str  # file, function, class, concept, pattern
    name: str
    properties: Dict

@dataclass
class Relationship:
    """Represents a relationship between concepts"""
    source_id: str
    target_id: str
    relationship_type: str  # imports, calls, inherits, uses, related_to
    properties: Dict

class KnowledgeGraph:
    """Graph-based knowledge representation"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.graph = nx.DiGraph()

    def add_concept(self, concept: Concept):
        """Add a concept to the graph"""
        self.graph.add_node(
            concept.id,
            type=concept.type,
            name=concept.name,
            **concept.properties
        )

    def add_relationship(self, rel: Relationship):
        """Add a relationship between concepts"""
        self.graph.add_edge(
            rel.source_id,
            rel.target_id,
            type=rel.relationship_type,
            **rel.properties
        )

    def get_related_concepts(
        self,
        concept_id: str,
        relationship_type: Optional[str] = None,
        depth: int = 1
    ) -> List[Concept]:
        """Get concepts related to given concept"""
        if concept_id not in self.graph:
            return []

        related = []

        # BFS traversal
        visited = set()
        queue = [(concept_id, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            # Get neighbors
            for neighbor in self.graph.neighbors(current_id):
                edge_data = self.graph.get_edge_data(current_id, neighbor)

                if relationship_type and edge_data.get("type") != relationship_type:
                    continue

                node_data = self.graph.nodes[neighbor]
                related.append(Concept(
                    id=neighbor,
                    type=node_data.get("type"),
                    name=node_data.get("name"),
                    properties={k: v for k, v in node_data.items() if k not in ["type", "name"]}
                ))

                if current_depth < depth:
                    queue.append((neighbor, current_depth + 1))

        return related

    def search_concepts(self, concept_type: str, properties: Dict) -> List[Concept]:
        """Search for concepts by type and properties"""
        results = []

        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get("type") != concept_type:
                continue

            # Check if properties match
            match = all(
                node_data.get(k) == v
                for k, v in properties.items()
            )

            if match:
                results.append(Concept(
                    id=node_id,
                    type=node_data.get("type"),
                    name=node_data.get("name"),
                    properties={k: v for k, v in node_data.items() if k not in ["type", "name"]}
                ))

        return results

    def export_to_dict(self) -> Dict:
        """Export graph to dictionary"""
        return {
            "nodes": [
                {"id": node_id, **data}
                for node_id, data in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **data}
                for u, v, data in self.graph.edges(data=True)
            ]
        }

    def import_from_dict(self, data: Dict):
        """Import graph from dictionary"""
        for node in data.get("nodes", []):
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)

        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.add_edge(source, target, **edge)
```

**3.2 Learning Database**

**File: `backend/app/memory/learning_db.py`**
```python
from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import List, Optional, Dict

Base = declarative_base()

class LearnedPattern(Base):
    """Stores successful code patterns"""
    __tablename__ = "learned_patterns"

    id = Column(String, primary_key=True)
    pattern_type = Column(String)  # loop, error_handling, api_call, etc.
    context = Column(JSON)  # When to use this pattern
    code_template = Column(Text)  # The pattern itself
    success_rate = Column(Float, default=0.0)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)

class ErrorLesson(Base):
    """Stores learned error solutions"""
    __tablename__ = "error_lessons"

    id = Column(String, primary_key=True)
    error_type = Column(String)  # ValueError, TypeError, etc.
    error_message = Column(Text)
    context = Column(JSON)  # Code context when error occurred
    solution = Column(Text)  # How it was fixed
    effectiveness = Column(Float, default=0.0)
    occurrences = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class LearningDB:
    """Service for storing and retrieving learned knowledge"""

    def __init__(self, db_session):
        self.session = db_session

    async def add_pattern(
        self,
        pattern_type: str,
        context: Dict,
        code_template: str
    ) -> LearnedPattern:
        """Store a successful pattern"""
        pattern = LearnedPattern(
            id=f"pattern_{datetime.utcnow().timestamp()}",
            pattern_type=pattern_type,
            context=context,
            code_template=code_template
        )
        self.session.add(pattern)
        await self.session.commit()
        return pattern

    async def find_similar_patterns(
        self,
        pattern_type: str,
        min_success_rate: float = 0.5
    ) -> List[LearnedPattern]:
        """Find patterns by type with minimum success rate"""
        return self.session.query(LearnedPattern).filter(
            LearnedPattern.pattern_type == pattern_type,
            LearnedPattern.success_rate >= min_success_rate
        ).order_by(LearnedPattern.usage_count.desc()).all()

    async def add_error_lesson(
        self,
        error_type: str,
        error_message: str,
        context: Dict,
        solution: str
    ) -> ErrorLesson:
        """Store an error and its solution"""
        lesson = ErrorLesson(
            id=f"error_{datetime.utcnow().timestamp()}",
            error_type=error_type,
            error_message=error_message,
            context=context,
            solution=solution
        )
        self.session.add(lesson)
        await self.session.commit()
        return lesson

    async def find_error_solutions(
        self,
        error_type: str,
        error_message: Optional[str] = None
    ) -> List[ErrorLesson]:
        """Find solutions for similar errors"""
        query = self.session.query(ErrorLesson).filter(
            ErrorLesson.error_type == error_type
        )

        if error_message:
            # Simple similarity - in production, use embedding similarity
            query = query.filter(ErrorLesson.error_message.contains(error_message[:50]))

        return query.order_by(ErrorLesson.effectiveness.desc()).limit(5).all()
```

**3.3 Enhanced Context Manager**

**File: `backend/app/memory/context_manager.py`**
```python
from typing import List, Dict, Any, Optional
from .knowledge_graph import KnowledgeGraph, Concept
from ..db.repository import ConversationRepository
from ..services.vector_db import VectorDBService

class ContextManager:
    """Enhanced context management with knowledge graph integration"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.knowledge_graph = KnowledgeGraph(session_id)
        self.vector_db = VectorDBService()
        self.recent_context = []
        self.max_recent = 10

    async def add_context(self, context_type: str, content: Any, metadata: Dict):
        """Add new context and update knowledge graph"""
        # Add to recent context
        self.recent_context.append({
            "type": context_type,
            "content": content,
            "metadata": metadata
        })

        if len(self.recent_context) > self.max_recent:
            self.recent_context.pop(0)

        # Update knowledge graph if it's a code artifact
        if context_type == "code":
            await self._update_graph_from_code(content, metadata)

    async def _update_graph_from_code(self, code: str, metadata: Dict):
        """Extract concepts from code and add to knowledge graph"""
        # Simple extraction - in production, use AST parsing
        filename = metadata.get("filename", "unknown")

        # Add file concept
        self.knowledge_graph.add_concept(Concept(
            id=f"file:{filename}",
            type="file",
            name=filename,
            properties={"language": metadata.get("language", "python")}
        ))

        # Extract functions (simplified)
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("def "):
                func_name = line.split("def ")[1].split("(")[0]
                func_id = f"function:{filename}:{func_name}"

                self.knowledge_graph.add_concept(Concept(
                    id=func_id,
                    type="function",
                    name=func_name,
                    properties={"line": i + 1, "file": filename}
                ))

                # Add relationship to file
                from .knowledge_graph import Relationship
                self.knowledge_graph.add_relationship(Relationship(
                    source_id=func_id,
                    target_id=f"file:{filename}",
                    relationship_type="defined_in",
                    properties={}
                ))

    async def get_relevant_context(self, task: str, max_items: int = 5) -> Dict[str, Any]:
        """Get relevant context for a task"""
        context = {
            "recent": self.recent_context[-max_items:],
            "similar_code": [],
            "related_concepts": []
        }

        # Search vector DB for similar code
        search_results = await self.vector_db.search_code(
            query=task,
            session_id=self.session_id,
            top_k=max_items
        )
        context["similar_code"] = [
            {"content": r.content, "metadata": r.metadata}
            for r in search_results
        ]

        # Get related concepts from knowledge graph
        # This is a simplified version - in production, extract entities from task
        # and find related concepts

        return context

    def export_graph(self) -> Dict:
        """Export knowledge graph"""
        return self.knowledge_graph.export_to_dict()

    def import_graph(self, data: Dict):
        """Import knowledge graph"""
        self.knowledge_graph.import_from_dict(data)
```

#### Deliverables (Week 3)
- ✅ Knowledge graph implementation
- ✅ Learning database schema
- ✅ Enhanced context manager
- ✅ Graph export/import capabilities

---

### Week 4: Integration & UI

#### Objectives
- Integrate all Phase 1 components
- Build frontend UI for tools and agents
- Add monitoring and logging
- Documentation and testing

#### Tasks

**4.1 Merge UI Improvements**

Merge improvements from `claude/fix-conversation-ui-theme-01Haho9joy38aV5T2WB9gy4i`:
- ErrorBoundary component
- Mock Mode for testing
- UI theme improvements

**4.2 Frontend Components for Tools**

**File: `frontend/src/components/ToolExecutionPanel.tsx`**
```typescript
interface ToolExecution {
  tool_name: string;
  params: any;
  result: {
    success: boolean;
    output: any;
    error?: string;
    execution_time: number;
  };
  timestamp: string;
}

export const ToolExecutionPanel: React.FC<{sessionId: string}> = ({sessionId}) => {
  const [executions, setExecutions] = useState<ToolExecution[]>([]);
  const [availableTools, setAvailableTools] = useState([]);

  useEffect(() => {
    // Fetch available tools
    apiClient.listTools().then(setAvailableTools);
  }, []);

  return (
    <div className="tool-execution-panel">
      <h3>Tool Executions</h3>
      <div className="tool-list">
        {availableTools.map(tool => (
          <ToolCard key={tool.name} tool={tool} />
        ))}
      </div>
      <div className="execution-log">
        {executions.map((exec, i) => (
          <ExecutionLogItem key={i} execution={exec} />
        ))}
      </div>
    </div>
  );
};
```

**4.3 Agent Visualization**

**File: `frontend/src/components/AgentNetwork.tsx`**
```typescript
interface AgentNode {
  agent_id: string;
  agent_type: string;
  status: 'active' | 'idle' | 'terminated';
  capabilities: any;
}

export const AgentNetwork: React.FC = () => {
  const [agents, setAgents] = useState<AgentNode[]>([]);

  useEffect(() => {
    // Poll active agents
    const interval = setInterval(() => {
      apiClient.listActiveAgents().then(data => setAgents(data.active_agents));
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="agent-network">
      <h3>Active Agents</h3>
      <div className="agent-grid">
        {agents.map(agent => (
          <AgentCard key={agent.agent_id} agent={agent} />
        ))}
      </div>
    </div>
  );
};
```

**4.4 Testing**

Create comprehensive tests:

```
backend/tests/
├── test_tools/
│   ├── test_file_tools.py
│   ├── test_code_tools.py
│   └── test_git_tools.py
├── test_agents/
│   ├── test_registry.py
│   ├── test_spawner.py
│   └── test_specialized_agents.py
└── test_memory/
    ├── test_knowledge_graph.py
    ├── test_learning_db.py
    └── test_context_manager.py
```

**4.5 Documentation**

Create documentation files:
- `docs/TOOLS.md` - Tool usage guide
- `docs/AGENTS.md` - Agent system documentation
- `docs/MEMORY.md` - Memory system architecture
- `docs/API.md` - Updated API reference

#### Deliverables (Week 4)
- ✅ Full system integration
- ✅ Frontend UI components
- ✅ Comprehensive test suite
- ✅ Complete documentation

---

## Success Metrics

### Phase 1 Completion Criteria

**Technical Milestones:**
- ✅ 7+ tools implemented and working
- ✅ 5+ specialized agent types
- ✅ Tool execution success rate > 90%
- ✅ Agent spawning < 500ms
- ✅ Knowledge graph with 100+ concepts
- ✅ All tests passing (>80% coverage)

**Integration Milestones:**
- ✅ Agents can use tools in workflows
- ✅ Tools integrated with existing workflow system
- ✅ Knowledge graph populated during sessions
- ✅ Frontend displays tool executions
- ✅ Agent network visualization working

**Quality Milestones:**
- ✅ Zero critical bugs
- ✅ API response time < 200ms (excluding tool execution)
- ✅ Documentation complete for all components
- ✅ Code review passed

---

## Risk Mitigation

### Technical Risks

**Risk 1: Tool Execution Safety**
- **Impact**: High - Could compromise system security
- **Mitigation**:
  - Strict parameter validation
  - Timeout mechanisms (30s default)
  - File size limits (10MB for reads, 1MB for writes)
  - Command whitelisting for shell tools
  - Future: Docker sandbox (Phase 2)

**Risk 2: Agent Complexity**
- **Impact**: Medium - Over-engineering could slow development
- **Mitigation**:
  - Start with simple agents
  - Incremental capability additions
  - Clear agent responsibilities
  - Reuse existing CodingAgent infrastructure

**Risk 3: Performance**
- **Impact**: Medium - Knowledge graph could slow down with scale
- **Mitigation**:
  - Lazy loading of graph nodes
  - Caching of frequently accessed concepts
  - Graph size limits (1000 nodes per session)
  - Periodic cleanup of old sessions

### Integration Risks

**Risk 1: Breaking Existing Workflows**
- **Impact**: High - Could disrupt current functionality
- **Mitigation**:
  - Maintain backward compatibility
  - Feature flags for new capabilities
  - Comprehensive integration tests
  - Gradual rollout

**Risk 2: UI Complexity**
- **Impact**: Low - Too many panels could confuse users
- **Mitigation**:
  - Progressive disclosure
  - Collapsible panels
  - Sensible defaults
  - User preferences

---

## Next Steps After Phase 1

### Phase 2 Preview: Deep Reasoning (Weeks 5-8)

**Key Features:**
- Multi-level reasoning engine (3 levels: analysis → reflection → verification)
- Self-criticism module
- Chain-of-thought prompting
- Uncertainty quantification

**Dependencies from Phase 1:**
- Agent registry (to register reasoning agent)
- Tool system (reasoning needs to verify outputs)
- Context manager (for reasoning history)

### Phase 3 Preview: Advanced Workflows (Weeks 9-12)

**Key Features:**
- Adaptive workflow engine
- Dynamic planning and replanning
- Quality gates and verification
- Parallel agent execution

**Dependencies from Phase 1:**
- Agent spawner (for dynamic workflow construction)
- Tool execution (for validation steps)
- Knowledge graph (for workflow optimization)

---

## Appendix

### A. File Structure After Phase 1

```
backend/app/
├── tools/
│   ├── __init__.py
│   ├── base.py
│   ├── executor.py
│   ├── registry.py
│   ├── file_tools.py
│   ├── code_tools.py
│   └── git_tools.py
├── agent/
│   ├── agent_manager.py (existing)
│   ├── workflow_manager.py (existing)
│   ├── registry.py (new)
│   └── specialized/
│       ├── __init__.py
│       ├── base_specialized_agent.py
│       ├── research_agent.py
│       ├── planning_agent.py
│       ├── coding_agent.py
│       ├── testing_agent.py
│       ├── review_agent.py
│       └── debug_agent.py
├── memory/
│   ├── __init__.py
│   ├── knowledge_graph.py
│   ├── learning_db.py
│   └── context_manager.py
└── api/
    └── routes.py (updated with new endpoints)

frontend/src/components/
├── ToolExecutionPanel.tsx
├── AgentNetwork.tsx
└── KnowledgeGraphView.tsx
```

### B. API Endpoints Summary

**Tools:**
- `POST /api/tools/execute` - Execute a tool
- `GET /api/tools/list` - List available tools
- `GET /api/tools/{name}/schema` - Get tool schema

**Agents:**
- `POST /api/agents/spawn` - Spawn specialized agent
- `GET /api/agents/types` - List agent types
- `GET /api/agents/active` - List active agents
- `DELETE /api/agents/{id}` - Terminate agent

**Memory:**
- `GET /api/memory/graph/{session_id}` - Export knowledge graph
- `POST /api/memory/graph/{session_id}` - Import knowledge graph
- `GET /api/memory/concepts/{session_id}` - Search concepts
- `POST /api/memory/patterns` - Store learned pattern
- `GET /api/memory/patterns/search` - Find similar patterns

### C. Technology Decisions

**Why NetworkX for Knowledge Graph?**
- Lightweight and Python-native
- Rich graph algorithms
- Easy serialization
- Future: Can migrate to Neo4j for scale

**Why Not Docker Sandbox in Phase 1?**
- Complexity - Focus on core functionality first
- Current mitigations sufficient for Phase 1
- Will be critical for Phase 2 when executing arbitrary code

**Why Specialized Agents vs Generic Agents?**
- Clear responsibilities
- Easier to optimize prompts
- Better user understanding
- Matches mental model of development workflow

### D. Dependencies Added

**Backend (requirements.txt):**
```
networkx==3.2.1        # Knowledge graph
pytest==7.4.3          # Testing framework
pytest-asyncio==0.21.1 # Async testing
```

**Frontend (package.json):**
```json
{
  "react-flow-renderer": "^10.3.17",  // Agent network visualization
  "d3": "^7.8.5"                      // Knowledge graph visualization
}
```

---

## Conclusion

Phase 1 establishes the **foundational infrastructure** for Next DeepAgent:

1. **Tool System**: Agents can now interact with the world (files, code, git)
2. **Agent Registry**: Dynamic creation of specialized agents on-demand
3. **Enhanced Memory**: Knowledge graphs and learning database for context

This foundation enables:
- **Phase 2**: Deep reasoning with tool verification
- **Phase 3**: Adaptive workflows with dynamic agent orchestration
- **Phase 4**: Continuous learning from tool usage patterns

**Phase 1 transforms our system from a 3-stage pipeline into a flexible, extensible multi-agent platform ready for advanced autonomous capabilities.**

---

**Document Version:** 1.0
**Status:** Ready for Implementation
**Estimated Completion:** 4 weeks
**Next Review:** End of Week 2
