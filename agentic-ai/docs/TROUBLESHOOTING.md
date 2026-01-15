# Agentic 2.0 Troubleshooting Guide

## Table of Contents

1. [Common Issues](#common-issues)
2. [LLM Client Issues](#llm-client-issues)
3. [Workflow Issues](#workflow-issues)
4. [Sub-Agent Issues](#sub-agent-issues)
5. [Persistence Issues](#persistence-issues)
6. [Performance Issues](#performance-issues)
7. [Error Handling](#error-handling)
8. [Debugging](#debugging)
9. [FAQ](#faq)

## Common Issues

### Installation Issues

#### Issue: Dependencies not installing

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement...
```

**Solution:**
```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install with verbose output
pip install -r requirements.txt -v

# Try installing dependencies one by one
pip install langgraph langchain-core anthropic openai
```

#### Issue: Python version mismatch

**Symptoms:**
```
SyntaxError: invalid syntax
```

**Solution:**
Agentic 2.0 requires Python 3.10+
```bash
python --version  # Check version
python3.10 -m venv venv  # Create venv with correct version
```

### Configuration Issues

#### Issue: Configuration file not found

**Symptoms:**
```
FileNotFoundError: config/config.yaml not found
```

**Solution:**
```python
# Specify full path
config = load_config("/absolute/path/to/config.yaml")

# Or set environment variable
export AGENTIC_CONFIG_PATH="/path/to/config.yaml"
```

#### Issue: Environment variables not substituted

**Symptoms:**
```
api_key: "${LLM_API_KEY}" instead of actual key
```

**Solution:**
```bash
# Make sure environment variables are set BEFORE running
export LLM_API_KEY="your-actual-key"
python script.py

# Check if variable is set
echo $LLM_API_KEY
```

## LLM Client Issues

### Issue: Connection refused

**Symptoms:**
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Diagnosis:**
```python
# Test endpoint manually
import requests
response = requests.get("http://localhost:8000/v1/health")
print(response.status_code)
```

**Solution:**
1. Check if LLM server is running:
   ```bash
   curl http://localhost:8000/v1/health
   ```

2. Verify URL in configuration:
   ```yaml
   llm:
     endpoints:
       - url: "http://localhost:8000/v1"  # Include /v1 if needed
   ```

3. Check firewall/network settings

### Issue: API key authentication failed

**Symptoms:**
```
401 Unauthorized: Invalid API key
```

**Solution:**
1. Verify API key is correct:
   ```bash
   echo $LLM_API_KEY
   ```

2. Check API key format in config:
   ```yaml
   endpoints:
     - api_key: "${LLM_API_KEY}"  # Environment variable
     # Not: "sk-..." directly (security risk)
   ```

3. Rotate API key if compromised

### Issue: Request timeout

**Symptoms:**
```
TimeoutError: Request timed out after 30 seconds
```

**Solution:**
```yaml
llm:
  endpoints:
    - timeout: 60  # Increase timeout
      max_retries: 3  # Enable retries
```

Or use error recovery:
```python
from production import ErrorRecovery

recovery = ErrorRecovery(max_retries=3, base_delay=2.0)
result = await recovery.retry_with_backoff(llm_call)
```

### Issue: Both endpoints failing

**Symptoms:**
```
All LLM endpoints unavailable
```

**Diagnosis:**
```python
llm_client = DualEndpointLLMClient(...)
health = llm_client.get_health_status()
print(health)  # Check which endpoints are failing
```

**Solution:**
1. Check endpoint health:
   ```bash
   curl http://localhost:8000/v1/health
   curl http://localhost:8001/v1/health
   ```

2. Enable health monitoring:
   ```python
   from production import HealthChecker

   checker = HealthChecker()
   checker.register_check("llm", lambda: llm_client.is_healthy())
   health = await checker.check_all()
   ```

3. Use graceful degradation:
   ```python
   from production import GracefulDegradation

   degradation = GracefulDegradation()
   if not llm_client.is_healthy():
       degradation.enter_degraded_mode("LLM unavailable")
   ```

## Workflow Issues

### Issue: Workflow timeout

**Symptoms:**
```
WorkflowTimeout: Workflow exceeded 300 seconds
```

**Solution:**
```yaml
workflows:
  default_timeout: 600  # Increase timeout to 10 minutes
```

Or for specific workflow:
```python
result = await workflow.execute(
    task_description="...",
    context={"timeout": 600}
)
```

### Issue: Workflow stuck in infinite loop

**Symptoms:**
- Workflow never completes
- Same steps repeating

**Diagnosis:**
```python
# Enable debug logging
logger.setLevel("DEBUG")

# Check workflow state
print(workflow.current_state)
print(workflow.execution_history)
```

**Solution:**
```yaml
workflows:
  max_iterations: 10  # Limit iterations
```

### Issue: Workflow phase failing

**Symptoms:**
```
Phase 'implementation' failed: ...
```

**Diagnosis:**
Check logs for specific error:
```bash
grep "phase.*implementation" logs/agent.jsonl | jq '.'
```

**Solution:**
1. Review phase-specific configuration
2. Check tool availability
3. Verify input/output formats

### Issue: Invalid workflow domain

**Symptoms:**
```
ValueError: Unknown workflow domain: xyz
```

**Solution:**
Valid domains are: `coding`, `research`, `data`, `general`

```python
# Let router auto-detect domain
result = await router.route_and_execute(
    task_description="Write Python code"  # Auto-routes to 'coding'
)

# Or specify explicitly
workflow = CodingWorkflow(...)
result = await workflow.execute(...)
```

## Sub-Agent Issues

### Issue: Task decomposition failing

**Symptoms:**
```
Failed to decompose task: ...
```

**Diagnosis:**
```python
from agents.task_decomposer import TaskDecomposer

decomposer = TaskDecomposer(llm_client=llm_client)
breakdown = await decomposer.decompose(task_description)

print(f"Complexity: {breakdown.complexity}")
print(f"Subtasks: {len(breakdown.subtasks)}")
```

**Solution:**
1. Simplify task description
2. Provide more context
3. Disable decomposition for simple tasks

### Issue: Too many sub-agents spawned

**Symptoms:**
```
ResourceError: Too many concurrent agents
```

**Solution:**
```python
manager = SubAgentManager(
    llm_client=llm_client,
    max_parallel=3  # Reduce parallelism
)
```

Or configure globally:
```yaml
performance:
  max_parallel_agents: 3
```

### Issue: Sub-agent execution timeout

**Symptoms:**
```
SubAgentTimeout: Agent 'code_reader' exceeded timeout
```

**Solution:**
```python
result = await manager.execute_with_agents(
    task_description="...",
    context={
        "agent_timeout": 120  # 2 minutes per agent
    }
)
```

### Issue: Agent result aggregation failed

**Symptoms:**
```
AggregationError: Could not combine results
```

**Diagnosis:**
Check result formats:
```python
for result in agent_results:
    print(f"Agent: {result.agent_type}")
    print(f"Result type: {type(result.result)}")
```

**Solution:**
Ensure agents return compatible formats or use custom aggregation strategy.

## Persistence Issues

### Issue: Database locked

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Solution:**
1. Use WAL mode for SQLite:
   ```python
   # In checkpointer initialization
   connection.execute("PRAGMA journal_mode=WAL")
   ```

2. Or switch to PostgreSQL:
   ```yaml
   persistence:
     checkpointing:
       backend: "postgres"
   ```

### Issue: Checkpoint not saved

**Symptoms:**
- No checkpoints in database
- Cannot resume workflow

**Diagnosis:**
```python
# Check if checkpointing is enabled
print(workflow.checkpointer is not None)

# List checkpoints
checkpoints = await checkpointer.list()
print(f"Found {len(checkpoints)} checkpoints")
```

**Solution:**
```yaml
persistence:
  checkpointing:
    enabled: true  # Ensure enabled
    checkpoint_interval: 5  # Save every 5 steps
```

### Issue: Session recovery failed

**Symptoms:**
```
RecoveryError: Could not restore session state
```

**Solution:**
1. Check session exists:
   ```python
   session = session_manager.get_session(session_id)
   if not session:
       print("Session not found")
   ```

2. Verify checkpoint validity:
   ```python
   # Load specific checkpoint
   state = await state_recovery.load_state(session_id, checkpoint_id)
   ```

3. Create new session if recovery fails

## Performance Issues

### Issue: Slow LLM responses

**Symptoms:**
- Response times > 5 seconds
- High latency

**Diagnosis:**
```python
from observability import MetricsCollector

metrics = MetricsCollector()
stats = metrics.get_stats(name="llm.call.duration")
print(f"Avg duration: {stats['mean']:.2f}s")
print(f"Max duration: {stats['max']:.2f}s")
```

**Solution:**
1. Enable response caching:
   ```yaml
   llm:
     caching:
       enabled: true
   ```

2. Reduce max_tokens:
   ```yaml
   llm:
     max_tokens: 2048  # Reduce from 4096
   ```

3. Use context filtering:
   ```python
   from production import ContextFilter

   filter = ContextFilter(max_tokens=2000)
   filtered_context = filter.filter_context(context)
   ```

### Issue: High memory usage

**Symptoms:**
```
MemoryError: Out of memory
```

**Solution:**
1. Reduce cache sizes:
   ```yaml
   performance:
     lru_cache_size: 100  # Reduce from 1000
     llm_cache_size: 50
   ```

2. Clear caches periodically:
   ```python
   from core.optimization import get_llm_cache

   cache = get_llm_cache()
   cache.clear()  # Clear cache
   ```

3. Limit concurrent operations:
   ```yaml
   performance:
     max_parallel_workflows: 2
     max_parallel_tools: 5
   ```

### Issue: Too many tool calls

**Symptoms:**
- Slow task execution
- Rate limit errors

**Solution:**
```yaml
safety:
  max_tool_calls_per_task: 30  # Reduce limit

  rate_limiting:
    max_requests_per_minute: 30
```

## Error Handling

### Issue: Errors not being caught

**Symptoms:**
- Unhandled exceptions crashing system
- No error recovery

**Solution:**
```python
from production import ErrorHandler, ErrorRecovery

handler = ErrorHandler()
recovery = ErrorRecovery()

try:
    result = await operation()
except Exception as e:
    # Handle error
    error_info = handler.handle_error(e)

    # Retry if recoverable
    if error_info.recoverable:
        result = await recovery.retry_with_backoff(operation)
    else:
        # Log and exit gracefully
        logger.error("Unrecoverable error", error=error_info)
        raise
```

### Issue: Retry exhausted

**Symptoms:**
```
RetryError: Max retries exceeded
```

**Solution:**
1. Increase retries:
   ```python
   recovery = ErrorRecovery(max_retries=5)
   ```

2. Use fallback:
   ```python
   result, used_fallback = await recovery.try_with_fallback(
       primary_function,
       fallback_function
   )
   ```

### Issue: Error categorization incorrect

**Symptoms:**
- TimeoutError categorized as NetworkError
- Wrong recovery strategy applied

**Solution:**
```python
# Override category
error_info = handler.handle_error(
    exception,
    category=ErrorCategory.TIMEOUT_ERROR
)
```

## Debugging

### Enable Debug Logging

```python
import logging

# Set log level
logging.basicConfig(level=logging.DEBUG)

# Or for specific components
logging.getLogger("core.llm_client").setLevel(logging.DEBUG)
logging.getLogger("workflows").setLevel(logging.DEBUG)
```

### Inspect Workflow State

```python
# Access workflow state
print(workflow.current_state)

# Check execution history
for step in workflow.execution_history:
    print(f"{step.timestamp}: {step.action} -> {step.result}")

# View checkpoints
checkpoints = await workflow.list_checkpoints()
for cp in checkpoints:
    print(f"Checkpoint {cp.checkpoint_id}: {cp.timestamp}")
```

### Monitor Metrics

```python
from observability import MetricsCollector

metrics = MetricsCollector(log_file="metrics.jsonl")

# Get summary
summary = metrics.get_summary()
print(f"Total metrics: {summary['total_metrics']}")
print(f"By type: {summary['by_type']}")

# Get specific stats
llm_stats = metrics.get_stats(name="llm.call.duration")
print(f"LLM calls: {llm_stats['count']}")
print(f"Avg duration: {llm_stats['mean']:.2f}s")
```

### Analyze Decisions

```python
from observability import DecisionTracker

tracker = DecisionTracker(log_file="decisions.jsonl")

# Get all decisions
decisions = tracker.get_decisions()

# Analyze by agent
for agent_name in set(d.agent_name for d in decisions):
    agent_decisions = tracker.get_decisions(agent_name=agent_name)
    print(f"{agent_name}: {len(agent_decisions)} decisions")

# Get stats
stats = tracker.get_stats()
print(f"Avg confidence: {stats['avg_confidence']:.2f}")
print(f"By outcome: {stats['by_outcome']}")
```

### Health Checks

```python
from production import HealthChecker

checker = HealthChecker()

# Register all components
checker.register_check("llm", lambda: llm_client.is_healthy())
checker.register_check("database", lambda: db.is_connected())

# Check all
health = await checker.check_all()
print(f"Overall: {health['status']}")

for component, status in health['components'].items():
    print(f"  {component}: {status['status']}")
```

## FAQ

### Q: How do I know which workflow to use?

**A:** Use the `WorkflowRouter` to automatically route tasks:
```python
router = WorkflowRouter(llm_client=llm_client)
result = await router.route_and_execute(task_description)
```

The router uses the LLM to classify tasks into domains:
- Code-related → CodingWorkflow
- Research/information → ResearchWorkflow
- Data analysis → DataWorkflow
- Other → GeneralWorkflow

### Q: Can I use multiple LLM providers?

**A:** Yes, configure multiple endpoints:
```yaml
llm:
  endpoints:
    - url: "http://openai:8000/v1"
      api_key: "${OPENAI_KEY}"
    - url: "http://anthropic:8000/v1"
      api_key: "${ANTHROPIC_KEY}"
```

### Q: How do I reduce costs?

**A:** Several strategies:
1. Enable caching
2. Reduce max_tokens
3. Use context filtering
4. Lower temperature for deterministic tasks
5. Limit tool calls

### Q: How do I handle long-running tasks?

**A:** Use persistence:
```yaml
persistence:
  checkpointing:
    enabled: true
    checkpoint_interval: 5
```

Then tasks can be resumed after interruption:
```python
result = await workflow.execute(
    task_description="...",
    session_id=session_id,  # Resume from checkpoint
    context=context
)
```

### Q: Can I customize workflows?

**A:** Yes, create custom workflow by extending `BaseWorkflow`:
```python
from workflows.base_workflow import BaseWorkflow

class MyCustomWorkflow(BaseWorkflow):
    def __init__(self, llm_client, config):
        super().__init__(llm_client, config)
        self.domain = "custom"

    async def execute(self, task_description, context=None):
        # Your custom logic
        pass
```

### Q: How do I secure API keys?

**A:** Best practices:
1. Never commit keys to git
2. Use environment variables
3. Use secret management (AWS Secrets Manager, Vault)
4. Rotate keys regularly
5. Use different keys for dev/prod

### Q: How do I monitor production systems?

**A:** Enable observability:
```yaml
observability:
  logging:
    enabled: true
  metrics:
    enabled: true
    export:
      enabled: true
      format: "prometheus"
```

Set up health check endpoints and alerting.

### Q: What if a tool is failing?

**A:** Diagnose with tool logger:
```python
from observability import ToolLogger

tool_logger = ToolLogger(log_file="tools.jsonl")

# Get failed calls
failed_calls = tool_logger.get_calls(
    tool_name="read_file",
    success_only=False
)

for call in failed_calls:
    if not call.success:
        print(f"Error: {call.error}")
```

Then fix the root cause (permissions, missing file, etc.)

## Getting Help

If you're still experiencing issues:

1. Check logs in `logs/` directory
2. Review configuration in `config/config.yaml`
3. Run tests: `python -m pytest tests/`
4. Open issue on GitHub with:
   - Error message
   - Configuration (redact secrets!)
   - Steps to reproduce
   - Logs (last 50 lines)

## Additional Resources

- [User Guide](USER_GUIDE.md)
- [API Reference](API_REFERENCE.md)
- [Configuration Guide](CONFIGURATION.md)
- [Examples](../examples/)
