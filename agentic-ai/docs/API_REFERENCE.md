# Agentic 2.0 API Reference

## Table of Contents

1. [Core](#core)
2. [Workflows](#workflows)
3. [Agents](#agents)
4. [Observability](#observability)
5. [Production](#production)
6. [Persistence](#persistence)
7. [Tools](#tools)

## Core

### LLM Client

#### `DualEndpointLLMClient`

Dual-endpoint LLM client with automatic failover.

**Constructor:**
```python
DualEndpointLLMClient(
    endpoints: List[EndpointConfig],
    model_name: str,
    mode: str = "active-active"  # or "primary-secondary"
)
```

**Methods:**

```python
async def chat_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
    **kwargs
) -> Dict[str, Any]
```
Send chat completion request with automatic failover.

```python
def is_healthy() -> bool
```
Check if at least one endpoint is healthy.

```python
def get_health_status() -> Dict[str, Any]
```
Get health status of all endpoints.

**Example:**
```python
llm_client = DualEndpointLLMClient(
    endpoints=[
        {"url": "http://localhost:8000", "api_key": "key1"},
        {"url": "http://localhost:8001", "api_key": "key2"}
    ],
    model_name="gpt-oss-120b",
    mode="active-active"
)

response = await llm_client.chat_completion(
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7
)
```

---

### Router

#### `WorkflowRouter`

Routes tasks to appropriate workflows.

**Constructor:**
```python
WorkflowRouter(
    llm_client: DualEndpointLLMClient,
    config: Config
)
```

**Methods:**

```python
async def route_and_execute(
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```
Route task to appropriate workflow and execute.

Returns:
- `domain`: Workflow domain (coding, research, data, general)
- `output`: Execution result
- `success`: Boolean success status
- `error`: Error message if failed

**Example:**
```python
router = WorkflowRouter(llm_client=llm_client, config=config)

result = await router.route_and_execute(
    task_description="Write a Python function",
    context={"workspace": "./workspace"}
)
```

---

## Workflows

### Base Workflow

#### `BaseWorkflow`

Abstract base class for all workflows.

**Methods:**

```python
async def execute(
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```
Execute workflow. Returns dict with:
- `output`: Result
- `steps`: List of executed steps
- `metrics`: Performance metrics

```python
async def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    use_cache: bool = True
) -> str
```
Call LLM with optional caching.

---

### Coding Workflow

#### `CodingWorkflow`

Handles code-related tasks.

**Phases:**
1. Planning
2. Implementation
3. Testing
4. Review

**Example:**
```python
workflow = CodingWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Create REST API",
    context={"workspace": "./project", "language": "python"}
)
```

---

### Research Workflow

#### `ResearchWorkflow`

Handles research and information gathering.

**Phases:**
1. Query formulation
2. Information gathering
3. Analysis
4. Synthesis

**Example:**
```python
workflow = ResearchWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Research microservices best practices",
    context={"depth": "comprehensive"}
)
```

---

### Data Workflow

#### `DataWorkflow`

Handles data analysis tasks.

**Phases:**
1. Data loading
2. Analysis
3. Visualization
4. Reporting

**Example:**
```python
workflow = DataWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Analyze sales data",
    context={"data_path": "./data.csv"}
)
```

---

### General Workflow

#### `GeneralWorkflow`

Handles general-purpose tasks.

**Phases:**
1. Understanding
2. Planning
3. Execution

**Example:**
```python
workflow = GeneralWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Organize project files",
    context={"workspace": "./project"}
)
```

---

## Agents

### Sub-Agent Manager

#### `SubAgentManager`

Manages sub-agent spawning and execution.

**Constructor:**
```python
SubAgentManager(
    llm_client: DualEndpointLLMClient,
    config: Config,
    max_parallel: int = 5
)
```

**Methods:**

```python
async def execute_with_agents(
    task_description: str,
    context: Optional[Dict[str, Any]] = None,
    parent_agent: Optional[str] = None
) -> Dict[str, Any]
```
Decompose task and execute with sub-agents.

Returns:
- `success`: Boolean
- `result`: Aggregated result
- `subtasks`: List of subtask results
- `execution_time`: Total duration

**Example:**
```python
manager = SubAgentManager(
    llm_client=llm_client,
    config=config,
    max_parallel=5
)

result = await manager.execute_with_agents(
    task_description="Build web application",
    context={"workspace": "./webapp"}
)
```

---

### Task Decomposer

#### `TaskDecomposer`

Decomposes complex tasks into subtasks.

**Methods:**

```python
async def decompose(
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> TaskBreakdown
```

Returns `TaskBreakdown` with:
- `requires_decomposition`: Boolean
- `complexity`: SIMPLE, MODERATE, or COMPLEX
- `subtasks`: List of Subtask objects
- `execution_strategy`: PARALLEL or SEQUENTIAL

---

## Observability

### Structured Logger

#### `StructuredLogger`

JSONL structured logging.

**Constructor:**
```python
StructuredLogger(
    log_file: Optional[str] = None,
    console_output: bool = True
)
```

**Methods:**

```python
def info(message: str, **context)
def warning(message: str, **context)
def error(message: str, **context)
def debug(message: str, **context)

def log_workflow(
    domain: str,
    status: str,
    **context
)

def log_agent(
    agent_name: str,
    agent_type: str,
    status: str,
    **context
)

def log_task(
    task_id: str,
    status: str,
    **context
)
```

**Example:**
```python
logger = StructuredLogger(log_file="logs/agent.jsonl")
logger.info("Task started", task_id="task_123")
logger.log_workflow("coding", "completed", duration=45.5)
```

---

### Decision Tracker

#### `DecisionTracker`

Tracks agent decisions with reasoning.

**Methods:**

```python
def record_decision(
    agent_name: str,
    agent_type: str,
    decision_type: str,
    decision: str,
    reasoning: str,
    alternatives: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    context: Optional[Dict] = None
) -> Decision
```

```python
def update_outcome(
    decision_id: str,
    outcome: str
)
```

```python
def get_decisions(
    agent_name: Optional[str] = None,
    decision_type: Optional[str] = None
) -> List[Decision]
```

```python
def get_stats() -> Dict[str, Any]
```

**Example:**
```python
tracker = DecisionTracker(log_file="logs/decisions.jsonl")

decision = tracker.record_decision(
    agent_name="planner",
    agent_type="workflow",
    decision_type="plan",
    decision="Use 3-step approach",
    reasoning="Task complexity",
    confidence=0.85
)

tracker.update_outcome(decision.decision_id, "success")
```

---

### Metrics Collector

#### `MetricsCollector`

Collects performance metrics.

**Methods:**

```python
def counter(name: str, value: float = 1.0, tags: Optional[Dict] = None)
def increment(name: str, tags: Optional[Dict] = None)
def gauge(name: str, value: float, tags: Optional[Dict] = None, unit: Optional[str] = None)
def histogram(name: str, value: float, tags: Optional[Dict] = None, unit: Optional[str] = None)
def timer(name: str, duration: float, tags: Optional[Dict] = None)
```

```python
def get_counter_value(name: str, tags: Optional[Dict] = None) -> float
def get_metrics(...) -> List[Metric]
def get_stats(...) -> Dict[str, Any]
def get_summary() -> Dict[str, Any]
```

**Example:**
```python
metrics = MetricsCollector(log_file="logs/metrics.jsonl")

metrics.increment("workflow.executions", tags={"domain": "coding"})
metrics.gauge("active.agents", 3, unit="count")
metrics.timer("llm.duration", 1.5, tags={"model": "gpt-oss-120b"})
```

---

## Production

### Endpoint Selector

#### `EndpointSelector`

Intelligent endpoint selection with health tracking.

**Constructor:**
```python
EndpointSelector(
    endpoints: List[EndpointConfig],
    health_check_interval: int = 30,
    max_consecutive_failures: int = 3
)
```

**Methods:**

```python
def select_best_endpoint() -> Optional[Dict[str, Any]]
```

```python
def record_success(url: str, response_time_ms: float)
def record_failure(url: str)
```

```python
def get_endpoint_stats(url: str) -> Dict[str, Any]
def get_health_status() -> Dict[str, Any]
```

**Example:**
```python
selector = EndpointSelector(endpoints=[...])

selector.record_success("http://localhost:8000", response_time_ms=100)
best = selector.select_best_endpoint()
stats = selector.get_endpoint_stats(best['url'])
```

---

### Context Filter

#### `ContextFilter`

Filters and optimizes context for LLM calls.

**Constructor:**
```python
ContextFilter(
    max_tokens: int = 4000,
    max_message_length: int = 2000,
    max_tool_calls: int = 10,
    max_list_items: int = 10,
    max_context_size: int = 10000
)
```

**Methods:**

```python
def filter_context(
    context: Dict[str, Any],
    priority_keys: Optional[List[str]] = None
) -> Dict[str, Any]
```

**Example:**
```python
filter = ContextFilter(max_message_length=500)

filtered = filter.filter_context(
    context={"large_data": "..." * 1000},
    priority_keys=["task_id", "workspace"]
)
```

---

### Error Handler

#### `ErrorHandler`

Comprehensive error handling with categorization.

**Methods:**

```python
def handle_error(
    exception: Exception,
    context: Optional[Dict] = None,
    category: Optional[ErrorCategory] = None
) -> ErrorInfo
```

Returns `ErrorInfo` with:
- `error_id`: Unique ID
- `category`: Error category
- `severity`: Error severity
- `message`: Technical message
- `user_message`: User-friendly message
- `recoverable`: Boolean
- `context`: Error context

**Example:**
```python
handler = ErrorHandler()

try:
    risky_operation()
except Exception as e:
    error_info = handler.handle_error(e)
    print(error_info.user_message)
```

---

### Error Recovery

#### `ErrorRecovery`

Retry mechanisms with exponential backoff.

**Constructor:**
```python
ErrorRecovery(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
)
```

**Methods:**

```python
async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: Optional[int] = None,
    **kwargs
) -> Any
```

```python
async def try_with_fallback(
    primary_func: Callable,
    fallback_func: Callable,
    *args,
    **kwargs
) -> Tuple[Any, bool]
```

**Example:**
```python
recovery = ErrorRecovery(max_retries=3)

result = await recovery.retry_with_backoff(
    risky_function,
    arg1="value"
)

result, used_fallback = await recovery.try_with_fallback(
    primary_function,
    fallback_function
)
```

---

### Graceful Degradation

#### `GracefulDegradation`

Graceful degradation for system health.

**Methods:**

```python
def enter_degraded_mode(
    reason: str,
    strategy: DegradationStrategy = DegradationStrategy.REDUCE_FEATURES
)
```

```python
def exit_degraded_mode()
```

```python
def is_degraded() -> bool
def get_current_strategy() -> Optional[DegradationStrategy]
```

**Example:**
```python
degradation = GracefulDegradation()

if system_overloaded():
    degradation.enter_degraded_mode(
        reason="High load",
        strategy=DegradationStrategy.REDUCE_FEATURES
    )

if degradation.is_degraded():
    # Use simplified operations
    pass
```

---

### Health Checker

#### `HealthChecker`

Component health monitoring.

**Methods:**

```python
def register_check(name: str, check_func: Callable[[], bool])
```

```python
async def check_component(name: str) -> ComponentHealth
async def check_all() -> Dict[str, Any]
```

```python
def is_ready() -> bool  # Can accept requests
def is_alive() -> bool  # System is running
```

```python
def get_health_summary() -> Dict[str, Any]
```

**Example:**
```python
checker = HealthChecker()

checker.register_check("llm", lambda: llm_client.is_healthy())
checker.register_check("database", lambda: db.is_connected())

health = await checker.check_all()
ready = checker.is_ready()
```

---

## Persistence

### Session Manager

#### `SessionManager`

Manages sessions for persistence.

**Methods:**

```python
def create_session(
    task_description: str,
    task_type: str,
    workspace: str,
    metadata: Optional[Dict] = None
) -> Session
```

```python
def get_session(session_id: str) -> Optional[Session]
def list_sessions() -> List[Session]
def close_session(session_id: str)
```

**Example:**
```python
manager = SessionManager()

session = manager.create_session(
    task_description="Build app",
    task_type="coding",
    workspace="./workspace"
)

thread_id = session.thread_id  # For LangGraph checkpointing
```

---

### Checkpointer Manager

#### `CheckpointerManager`

Manages LangGraph checkpointers.

**Methods:**

```python
async def get_checkpointer(
    backend: str = "sqlite",  # or "postgres"
    **kwargs
) -> Union[AsyncSqliteSaver, AsyncPostgresSaver]
```

**Example:**
```python
manager = CheckpointerManager(db_path="checkpoints.db")

checkpointer = await manager.get_checkpointer(backend="sqlite")

# Use with LangGraph
workflow = StateGraph(...)
workflow = workflow.compile(checkpointer=checkpointer)
```

---

## Tools

### Tool Safety Manager

#### `ToolSafetyManager`

Validates and secures tool calls.

**Methods:**

```python
def validate_tool_call(
    tool_name: str,
    parameters: Dict[str, Any],
    context: Optional[Dict] = None
) -> Tuple[bool, Optional[str]]
```

```python
def is_tool_allowed(tool_name: str) -> bool
def check_dangerous_pattern(text: str) -> bool
```

**Example:**
```python
safety = ToolSafetyManager(config=config)

is_valid, error = safety.validate_tool_call(
    tool_name="read_file",
    parameters={"file_path": "/etc/passwd"}
)

if not is_valid:
    print(f"Blocked: {error}")
```

---

## Enums

### `WorkflowDomain`
- `CODING`
- `RESEARCH`
- `DATA_ANALYSIS`
- `GENERAL`

### `ErrorCategory`
- `LLM_ERROR`
- `TOOL_ERROR`
- `WORKFLOW_ERROR`
- `NETWORK_ERROR`
- `VALIDATION_ERROR`
- `TIMEOUT_ERROR`
- `RESOURCE_ERROR`
- `UNKNOWN_ERROR`

### `ErrorSeverity`
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

### `DegradationStrategy`
- `REDUCE_FEATURES`
- `USE_CACHE`
- `SIMPLIFY_OPERATIONS`
- `PARTIAL_RESULTS`

### `HealthStatus`
- `HEALTHY`
- `DEGRADED`
- `UNHEALTHY`
- `UNKNOWN`

### `TaskComplexity`
- `SIMPLE`
- `MODERATE`
- `COMPLEX`

### `ExecutionStrategy`
- `PARALLEL`
- `SEQUENTIAL`
- `MIXED`

### `SubAgentType`
Code agents:
- `CODE_READER`
- `CODE_WRITER`
- `CODE_TESTER`

Research agents:
- `DOCUMENT_SEARCHER`
- `INFORMATION_GATHERER`
- `REPORT_WRITER`

Data agents:
- `DATA_LOADER`
- `DATA_ANALYZER`
- `DATA_VISUALIZER`

General agents:
- `FILE_ORGANIZER`
- `TASK_EXECUTOR`
- `COMMAND_RUNNER`
