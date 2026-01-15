# Agentic 2.0 User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Workflow Execution](#workflow-execution)
5. [Sub-Agent System](#sub-agent-system)
6. [Observability](#observability)
7. [Production Features](#production-features)
8. [Best Practices](#best-practices)

## Introduction

Agentic 2.0 is a production-ready agentic AI system featuring:

- **LLM Integration**: Dual-endpoint LLM client with automatic failover
- **Workflow Orchestration**: 4 specialized workflows (Coding, Research, Data Analysis, General)
- **Sub-Agent Spawning**: 12 specialized agent types for complex task decomposition
- **Optimization**: LRU caching, LLM response caching, state optimization
- **Persistence**: Session and checkpoint management with SQLite/PostgreSQL
- **Observability**: Structured logging, decision tracking, metrics collection
- **Production Ready**: Performance optimization, error handling, health monitoring

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd agentic-ai

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

```python
from config.settings import load_config
from core.llm_client import DualEndpointLLMClient
from workflows.router import WorkflowRouter

# Load configuration
config = load_config("config/config.yaml")

# Initialize LLM client
llm_client = DualEndpointLLMClient(
    endpoints=config.llm.endpoints,
    model_name=config.llm.model_name,
    mode=config.llm.mode  # "active-active" or "primary-secondary"
)

# Create workflow router
router = WorkflowRouter(llm_client=llm_client, config=config)

# Execute task
result = await router.route_and_execute(
    task_description="Write a Python function to calculate factorial",
    context={"workspace": "./workspace"}
)

print(f"Result: {result['output']}")
```

## Configuration

### LLM Configuration

Configure LLM endpoints in `config/config.yaml`:

```yaml
llm:
  model_name: "gpt-oss-120b"
  temperature: 0.7
  max_tokens: 4096
  mode: "active-active"  # or "primary-secondary"

  endpoints:
    - url: "http://localhost:8000/v1"
      api_key: "your-api-key"
      name: "endpoint1"
      timeout: 30

    - url: "http://localhost:8001/v1"
      api_key: "your-api-key"
      name: "endpoint2"
      timeout: 30
```

### Safety Configuration

```yaml
safety:
  max_tool_calls_per_task: 50
  allowed_domains:
    - "example.com"
    - "api.example.com"

  blocked_tools:
    - "execute_shell"

  dangerous_patterns:
    - "rm -rf"
    - "format C:"
```

## Workflow Execution

### Coding Workflow

The coding workflow handles code-related tasks with phases: planning, implementation, testing, and review.

```python
from workflows.coding_workflow import CodingWorkflow

workflow = CodingWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Create a REST API endpoint for user authentication",
    context={
        "workspace": "./project",
        "language": "python",
        "framework": "fastapi"
    }
)
```

### Research Workflow

The research workflow gathers, analyzes, and synthesizes information.

```python
from workflows.research_workflow import ResearchWorkflow

workflow = ResearchWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Research best practices for microservices architecture",
    context={
        "depth": "comprehensive",
        "sources": ["academic", "industry"]
    }
)
```

### Data Analysis Workflow

The data analysis workflow loads, analyzes, and visualizes data.

```python
from workflows.data_workflow import DataWorkflow

workflow = DataWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Analyze sales data and identify trends",
    context={
        "data_path": "./data/sales.csv",
        "output_dir": "./reports"
    }
)
```

### General Workflow

The general workflow handles miscellaneous tasks with flexible execution.

```python
from workflows.general_workflow import GeneralWorkflow

workflow = GeneralWorkflow(llm_client=llm_client, config=config)

result = await workflow.execute(
    task_description="Organize project files and create documentation",
    context={
        "workspace": "./project"
    }
)
```

## Sub-Agent System

### Task Decomposition

The sub-agent system automatically decomposes complex tasks:

```python
from agents.sub_agent_manager import SubAgentManager

manager = SubAgentManager(
    llm_client=llm_client,
    config=config,
    max_parallel=5
)

result = await manager.execute_with_agents(
    task_description="Build a complete web application",
    context={"workspace": "./webapp"}
)
```

### Agent Types

**Code Agents:**
- `CODE_READER`: Read and analyze code
- `CODE_WRITER`: Write new code
- `CODE_TESTER`: Test code and validate

**Research Agents:**
- `DOCUMENT_SEARCHER`: Search documentation
- `INFORMATION_GATHERER`: Gather information
- `REPORT_WRITER`: Write reports

**Data Agents:**
- `DATA_LOADER`: Load data from files
- `DATA_ANALYZER`: Analyze data
- `DATA_VISUALIZER`: Create visualizations

**General Agents:**
- `FILE_ORGANIZER`: Organize files
- `TASK_EXECUTOR`: Execute generic tasks
- `COMMAND_RUNNER`: Run commands

### Execution Strategies

- **Parallel**: Independent subtasks executed concurrently
- **Sequential**: Dependent subtasks executed in order
- **Mixed**: Combination of parallel and sequential execution

## Observability

### Structured Logging

```python
from observability import get_logger

logger = get_logger(log_file="logs/agent.jsonl")

# Basic logging
logger.info("Task started", task_id="task_123")

# Workflow logging
logger.log_workflow("coding", "started", task_id="task_123")
logger.log_workflow("coding", "completed", task_id="task_123", duration=45.5)

# Agent logging
logger.log_agent("planner", "workflow", "started", iteration=1)
```

### Decision Tracking

```python
from observability import DecisionTracker

tracker = DecisionTracker(log_file="logs/decisions.jsonl")

decision = tracker.record_decision(
    agent_name="planner",
    agent_type="workflow",
    decision_type="plan",
    decision="Execute 3 sequential steps",
    reasoning="Task complexity requires structured approach",
    confidence=0.85,
    alternatives=["Parallel execution", "Single step"]
)

# Update outcome later
tracker.update_outcome(decision.decision_id, "success")
```

### Metrics Collection

```python
from observability import MetricsCollector

metrics = MetricsCollector(log_file="logs/metrics.jsonl")

# Counter
metrics.increment("workflow.executions", tags={"domain": "coding"})

# Gauge
metrics.gauge("active.agents", 3, unit="count")

# Timer
metrics.timer("llm.call.duration", 1.5, tags={"model": "gpt-oss-120b"})

# Histogram
metrics.histogram("response.time", 0.25, unit="seconds")
```

## Production Features

### Endpoint Selection

```python
from production import EndpointSelector, EndpointConfig

endpoints = [
    EndpointConfig(
        name="primary",
        url="http://localhost:8000",
        api_key="key1"
    ),
    EndpointConfig(
        name="secondary",
        url="http://localhost:8001",
        api_key="key2"
    )
]

selector = EndpointSelector(endpoints=endpoints)

# Record health metrics
selector.record_success("http://localhost:8000", response_time_ms=100)
selector.record_failure("http://localhost:8001")

# Select best endpoint
best_endpoint = selector.select_best_endpoint()
```

### Error Handling

```python
from production import ErrorHandler, ErrorRecovery

handler = ErrorHandler()
recovery = ErrorRecovery(max_retries=3)

try:
    result = await risky_operation()
except Exception as e:
    # Handle error
    error_info = handler.handle_error(e)
    print(f"Error: {error_info.user_message}")

    # Retry with exponential backoff
    result = await recovery.retry_with_backoff(
        risky_operation,
        max_retries=3
    )
```

### Graceful Degradation

```python
from production import GracefulDegradation, DegradationStrategy

degradation = GracefulDegradation()

# Enter degraded mode
if system_overloaded():
    degradation.enter_degraded_mode(
        reason="High load",
        strategy=DegradationStrategy.REDUCE_FEATURES
    )

# Check mode
if degradation.is_degraded():
    # Use simplified operations
    result = await simple_operation()
else:
    # Use full features
    result = await complex_operation()

# Exit degraded mode
degradation.exit_degraded_mode()
```

### Health Monitoring

```python
from production import HealthChecker

checker = HealthChecker()

# Register health checks
def llm_check():
    return llm_client.is_available()

def database_check():
    return database.is_connected()

checker.register_check("llm", llm_check)
checker.register_check("database", database_check)

# Check health
health = await checker.check_all()
print(f"Status: {health['status']}")
print(f"Healthy: {health['summary']['healthy']}/{health['summary']['total']}")

# Readiness/Liveness checks
ready = checker.is_ready()  # Can accept requests
alive = checker.is_alive()  # System is running
```

## Best Practices

### 1. Configuration Management

- Store sensitive data in environment variables
- Use different configs for dev/staging/prod
- Validate configuration on startup

### 2. Error Handling

- Use `ErrorRecovery.retry_with_backoff()` for transient errors
- Implement health checks for all critical components
- Enable graceful degradation for non-critical features

### 3. Observability

- Enable structured logging for all agents
- Track decisions with reasoning and alternatives
- Collect metrics for performance monitoring
- Review logs and metrics regularly

### 4. Performance

- Use LRU cache for frequently accessed data
- Enable LLM response caching for deterministic calls
- Limit parallel execution to avoid resource exhaustion
- Monitor response times and adjust accordingly

### 5. Safety

- Configure allowed domains for web access
- Set max tool calls per task
- Block dangerous tools and patterns
- Validate all tool parameters

### 6. Testing

- Test workflows with sample tasks
- Validate sub-agent decomposition
- Verify error handling and recovery
- Check health monitoring and degradation

### 7. Deployment

- Use health check endpoints for readiness/liveness probes
- Monitor endpoint health and response times
- Set up alerting for critical errors
- Implement circuit breakers for external services

## Example: Complete Application

```python
import asyncio
from config.settings import load_config
from core.llm_client import DualEndpointLLMClient
from workflows.router import WorkflowRouter
from observability import get_logger, DecisionTracker, MetricsCollector
from production import (
    EndpointSelector, ErrorHandler, ErrorRecovery,
    GracefulDegradation, HealthChecker
)

async def main():
    # Load configuration
    config = load_config("config/config.yaml")

    # Initialize observability
    logger = get_logger(log_file="logs/agent.jsonl")
    decisions = DecisionTracker(log_file="logs/decisions.jsonl")
    metrics = MetricsCollector(log_file="logs/metrics.jsonl")

    # Initialize production components
    endpoint_selector = EndpointSelector(endpoints=config.llm.endpoints)
    error_handler = ErrorHandler()
    error_recovery = ErrorRecovery()
    degradation = GracefulDegradation()
    health_checker = HealthChecker()

    # Initialize LLM client
    llm_client = DualEndpointLLMClient(
        endpoints=config.llm.endpoints,
        model_name=config.llm.model_name
    )

    # Register health checks
    health_checker.register_check("llm", lambda: llm_client.is_healthy())

    # Create router
    router = WorkflowRouter(llm_client=llm_client, config=config)

    # Check system health
    health = await health_checker.check_all()
    logger.info("System health check", status=health['status'])

    if not health_checker.is_ready():
        logger.error("System not ready")
        return

    # Execute task with error handling
    try:
        logger.log_workflow("coding", "started", task_id="task_001")
        metrics.increment("workflow.started", tags={"domain": "coding"})

        result = await error_recovery.retry_with_backoff(
            lambda: router.route_and_execute(
                task_description="Create a factorial function",
                context={"workspace": "./workspace"}
            ),
            max_retries=3
        )

        logger.log_workflow("coding", "completed", task_id="task_001")
        metrics.increment("workflow.completed", tags={"domain": "coding"})

        print(f"Result: {result['output']}")

    except Exception as e:
        error_info = error_handler.handle_error(e)
        logger.error("Task failed", error=error_info.message)
        metrics.increment("workflow.failed", tags={"domain": "coding"})

    # Get statistics
    health_summary = health_checker.get_health_summary()
    metrics_summary = metrics.get_summary()

    logger.info("Execution complete",
                health=health_summary,
                metrics=metrics_summary)

if __name__ == "__main__":
    asyncio.run(main())
```

## Support

For issues, questions, or contributions:
- GitHub Issues: <repository-url>/issues
- Documentation: <repository-url>/docs
- Examples: `examples/` directory
