# Agentic 2.0 Configuration Guide

## Table of Contents

1. [Overview](#overview)
2. [Configuration File](#configuration-file)
3. [LLM Configuration](#llm-configuration)
4. [Safety Configuration](#safety-configuration)
5. [Workflow Configuration](#workflow-configuration)
6. [Persistence Configuration](#persistence-configuration)
7. [Observability Configuration](#observability-configuration)
8. [Production Configuration](#production-configuration)
9. [Environment Variables](#environment-variables)
10. [Advanced Configuration](#advanced-configuration)

## Overview

Agentic 2.0 uses YAML configuration files for system settings. The default configuration file is `config/config.yaml`.

## Configuration File

### Structure

```yaml
llm:
  # LLM client settings

safety:
  # Safety and security settings

workflows:
  # Workflow-specific settings

persistence:
  # Persistence and checkpoint settings

observability:
  # Logging and monitoring settings

production:
  # Production features settings
```

### Loading Configuration

```python
from config.settings import load_config

# Load default configuration
config = load_config()

# Load custom configuration
config = load_config("path/to/custom_config.yaml")
```

## LLM Configuration

### Basic Settings

```yaml
llm:
  model_name: "gpt-oss-120b"
  temperature: 0.7
  max_tokens: 4096
  top_p: 0.9
  frequency_penalty: 0.0
  presence_penalty: 0.0
```

**Parameters:**
- `model_name`: Model identifier
- `temperature`: Randomness (0.0-1.0)
- `max_tokens`: Maximum response tokens
- `top_p`: Nucleus sampling threshold
- `frequency_penalty`: Reduce repetition (-2.0 to 2.0)
- `presence_penalty`: Encourage topic diversity (-2.0 to 2.0)

### Endpoint Configuration

#### Active-Active Mode

Equal traffic distribution across endpoints:

```yaml
llm:
  mode: "active-active"

  endpoints:
    - url: "http://localhost:8000/v1"
      api_key: "${LLM_API_KEY_1}"
      name: "endpoint1"
      timeout: 30
      max_retries: 3

    - url: "http://localhost:8001/v1"
      api_key: "${LLM_API_KEY_2}"
      name: "endpoint2"
      timeout: 30
      max_retries: 3
```

#### Primary-Secondary Mode

Primary endpoint with fallback:

```yaml
llm:
  mode: "primary-secondary"

  endpoints:
    - url: "http://primary:8000/v1"
      api_key: "${PRIMARY_API_KEY}"
      name: "primary"
      timeout: 30
      priority: 1  # Primary

    - url: "http://secondary:8000/v1"
      api_key: "${SECONDARY_API_KEY}"
      name: "secondary"
      timeout: 30
      priority: 2  # Fallback
```

### Health Check Configuration

```yaml
llm:
  health_check:
    enabled: true
    interval_seconds: 30
    timeout_seconds: 10
    failure_threshold: 3
    success_threshold: 2
```

### Caching Configuration

```yaml
llm:
  caching:
    enabled: true
    max_size: 1000
    ttl_seconds: 300
    cache_deterministic_only: true  # Only cache when temp < 0.5
```

## Safety Configuration

### Tool Safety

```yaml
safety:
  enabled: true

  # Max tool calls per task
  max_tool_calls_per_task: 50

  # Allowed tools (if empty, all tools allowed)
  allowed_tools:
    - "read_file"
    - "write_file"
    - "search_web"

  # Blocked tools
  blocked_tools:
    - "execute_shell"
    - "delete_system_file"

  # Allowed domains for web access
  allowed_domains:
    - "github.com"
    - "stackoverflow.com"
    - "python.org"

  # Dangerous patterns (regex)
  dangerous_patterns:
    - "rm -rf /"
    - "format C:"
    - "DROP TABLE"
    - "DELETE FROM .* WHERE 1=1"

  # File access restrictions
  allowed_file_paths:
    - "./workspace/**"
    - "./data/**"

  blocked_file_paths:
    - "/etc/**"
    - "/sys/**"
    - "~/.ssh/**"
```

### Rate Limiting

```yaml
safety:
  rate_limiting:
    enabled: true
    max_requests_per_minute: 60
    max_requests_per_hour: 1000
    max_concurrent_requests: 10
```

## Workflow Configuration

### Global Workflow Settings

```yaml
workflows:
  # Default timeout for all workflows (seconds)
  default_timeout: 300

  # Max iterations per workflow
  max_iterations: 10

  # Enable/disable checkpointing
  enable_checkpointing: true
```

### Coding Workflow

```yaml
workflows:
  coding:
    enabled: true

    # Workflow phases
    phases:
      - planning
      - implementation
      - testing
      - review

    # Testing configuration
    testing:
      enabled: true
      frameworks:
        - pytest
        - unittest
      coverage_threshold: 80

    # Code review configuration
    review:
      enabled: true
      checks:
        - syntax
        - style
        - security
        - performance
```

### Research Workflow

```yaml
workflows:
  research:
    enabled: true

    # Research phases
    phases:
      - query_formulation
      - information_gathering
      - analysis
      - synthesis

    # Sources configuration
    sources:
      web_search: true
      documentation: true
      academic: false

    # Depth settings
    max_sources: 10
    max_depth: 3
```

### Data Workflow

```yaml
workflows:
  data:
    enabled: true

    # Data phases
    phases:
      - data_loading
      - analysis
      - visualization
      - reporting

    # Supported formats
    supported_formats:
      - csv
      - json
      - parquet
      - excel

    # Visualization settings
    visualization:
      enabled: true
      default_backend: "matplotlib"
      output_format: "png"
```

## Persistence Configuration

### Session Management

```yaml
persistence:
  sessions:
    enabled: true
    storage_path: "./data/sessions"
    max_active_sessions: 100
    session_timeout_minutes: 60
```

### Checkpointing

```yaml
persistence:
  checkpointing:
    enabled: true
    backend: "sqlite"  # or "postgres"

    # SQLite configuration
    sqlite:
      db_path: "./data/checkpoints.db"
      connection_pool_size: 5

    # PostgreSQL configuration (if backend: "postgres")
    postgres:
      host: "localhost"
      port: 5432
      database: "agentic_checkpoints"
      user: "${POSTGRES_USER}"
      password: "${POSTGRES_PASSWORD}"
      connection_pool_size: 10

    # Checkpoint settings
    checkpoint_interval: 5  # Save every N steps
    max_checkpoints_per_session: 100
    cleanup_old_checkpoints: true
    checkpoint_retention_days: 7
```

### State Recovery

```yaml
persistence:
  state_recovery:
    enabled: true
    auto_resume: true  # Automatically resume from last checkpoint
    recovery_on_error: true  # Resume after errors
```

## Observability Configuration

### Structured Logging

```yaml
observability:
  logging:
    enabled: true
    format: "jsonl"  # or "json", "text"

    # Log files
    log_dir: "./logs"
    log_file: "agent.jsonl"

    # Log levels
    console_level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    file_level: "DEBUG"

    # Log rotation
    rotation:
      enabled: true
      max_bytes: 10485760  # 10MB
      backup_count: 5

    # Component-specific logging
    components:
      llm_client: "DEBUG"
      workflows: "INFO"
      agents: "DEBUG"
      tools: "INFO"
```

### Decision Tracking

```yaml
observability:
  decision_tracking:
    enabled: true
    log_file: "decisions.jsonl"
    track_alternatives: true
    track_confidence: true
    track_reasoning: true
```

### Metrics Collection

```yaml
observability:
  metrics:
    enabled: true
    log_file: "metrics.jsonl"

    # Metrics to collect
    collect:
      - workflow_executions
      - llm_calls
      - tool_calls
      - errors
      - response_times

    # Aggregation
    aggregation_interval_seconds: 60

    # Export
    export:
      enabled: false
      format: "prometheus"  # or "statsd", "datadog"
      endpoint: "http://localhost:9090"
```

## Production Configuration

### Endpoint Selection

```yaml
production:
  endpoint_selection:
    enabled: true

    # Health check settings
    health_check_interval: 30
    max_consecutive_failures: 3

    # Selection algorithm
    algorithm: "weighted"  # "round-robin", "weighted", "least-response-time"

    # Response time weights
    response_time_weight: 0.7
    success_rate_weight: 0.3
```

### Context Filtering

```yaml
production:
  context_filtering:
    enabled: true

    # Size limits
    max_tokens: 4000
    max_message_length: 2000
    max_tool_calls: 10
    max_list_items: 10
    max_context_size: 10000

    # Priority keys (always preserved)
    priority_keys:
      - "task_id"
      - "workspace"
      - "current_step"
```

### Error Handling

```yaml
production:
  error_handling:
    enabled: true

    # Retry configuration
    retry:
      enabled: true
      max_retries: 3
      base_delay: 1.0
      max_delay: 60.0
      exponential_backoff: true

    # Error categorization
    categorization:
      enabled: true
      user_friendly_messages: true

    # Error history
    track_errors: true
    max_error_history: 1000
```

### Graceful Degradation

```yaml
production:
  graceful_degradation:
    enabled: true

    # Degradation triggers
    triggers:
      high_error_rate: 0.5  # 50% error rate
      high_response_time: 5000  # 5 seconds
      low_health_score: 0.5

    # Degradation strategies
    strategies:
      - reduce_features
      - use_cache
      - simplify_operations
      - partial_results

    # Recovery
    auto_recovery: true
    recovery_threshold: 0.8  # 80% health
```

### Health Monitoring

```yaml
production:
  health_monitoring:
    enabled: true

    # Health check interval
    check_interval_seconds: 30

    # Components to monitor
    components:
      - llm_client
      - database
      - disk_space
      - memory

    # Thresholds
    thresholds:
      disk_space_gb: 1.0
      memory_usage_percent: 90.0

    # Health check endpoints
    http_endpoints:
      liveness: "/health/live"
      readiness: "/health/ready"
      detailed: "/health/status"
```

## Environment Variables

### Required Variables

```bash
# LLM API Keys
export LLM_API_KEY_1="your-api-key-1"
export LLM_API_KEY_2="your-api-key-2"

# Database (if using PostgreSQL)
export POSTGRES_USER="agentic_user"
export POSTGRES_PASSWORD="your-password"
```

### Optional Variables

```bash
# Override configuration file
export AGENTIC_CONFIG_PATH="/path/to/custom_config.yaml"

# Override log directory
export AGENTIC_LOG_DIR="/var/log/agentic"

# Override data directory
export AGENTIC_DATA_DIR="/var/data/agentic"

# Enable debug mode
export AGENTIC_DEBUG="true"

# Set log level
export AGENTIC_LOG_LEVEL="DEBUG"
```

### Loading Environment Variables

```python
import os
from config.settings import load_config

# Load configuration with environment variables
config = load_config()

# Environment variables are automatically substituted in config file:
# api_key: "${LLM_API_KEY_1}" -> api_key: "actual-key-value"
```

## Advanced Configuration

### Custom Workflow Configuration

```yaml
workflows:
  custom_workflow:
    enabled: true
    class: "workflows.custom.MyCustomWorkflow"

    # Custom parameters
    parameters:
      custom_param1: "value1"
      custom_param2: 123
```

### Performance Tuning

```yaml
performance:
  # Parallel execution
  max_parallel_workflows: 5
  max_parallel_tools: 10
  max_parallel_agents: 5

  # Caching
  lru_cache_size: 1000
  llm_cache_size: 500
  state_cache_size: 100

  # Memory management
  max_memory_mb: 2048
  garbage_collection: "auto"

  # Timeouts
  default_timeout: 300
  llm_timeout: 60
  tool_timeout: 30
```

### Development Settings

```yaml
development:
  # Debug mode
  debug: true

  # Verbose logging
  verbose: true

  # Disable safety checks (DANGER!)
  disable_safety: false

  # Mock LLM responses
  mock_llm: false
  mock_llm_responses_file: "./tests/fixtures/mock_responses.yaml"

  # Test mode
  test_mode: false
```

### Production Settings

```yaml
production:
  # Optimize for production
  optimize: true

  # Enable all production features
  enable_all_features: true

  # Strict mode (fail fast on errors)
  strict_mode: false

  # Monitoring
  monitoring:
    enabled: true
    metrics_port: 9090
    health_port: 8080
```

## Configuration Validation

### Validate Configuration

```python
from config.settings import load_config, validate_config

config = load_config("config/config.yaml")

# Validate configuration
is_valid, errors = validate_config(config)

if not is_valid:
    for error in errors:
        print(f"Configuration error: {error}")
    exit(1)
```

### Configuration Schema

The configuration schema is defined in `config/schema.py` and includes:
- Type validation
- Range checks
- Required fields
- Default values
- Deprecation warnings

## Configuration Examples

### Minimal Configuration

```yaml
llm:
  model_name: "gpt-oss-120b"
  endpoints:
    - url: "http://localhost:8000/v1"
      api_key: "${LLM_API_KEY}"

safety:
  max_tool_calls_per_task: 50
```

### Production Configuration

```yaml
llm:
  model_name: "gpt-oss-120b"
  temperature: 0.7
  max_tokens: 4096
  mode: "active-active"

  endpoints:
    - url: "http://llm-1:8000/v1"
      api_key: "${LLM_API_KEY_1}"
      name: "llm-1"
      timeout: 30
      max_retries: 3

    - url: "http://llm-2:8000/v1"
      api_key: "${LLM_API_KEY_2}"
      name: "llm-2"
      timeout: 30
      max_retries: 3

  caching:
    enabled: true
    max_size: 1000
    ttl_seconds: 300

safety:
  enabled: true
  max_tool_calls_per_task: 100
  rate_limiting:
    enabled: true
    max_requests_per_minute: 60

persistence:
  checkpointing:
    enabled: true
    backend: "postgres"
    postgres:
      host: "postgres:5432"
      database: "agentic"
      user: "${POSTGRES_USER}"
      password: "${POSTGRES_PASSWORD}"

observability:
  logging:
    enabled: true
    console_level: "INFO"
    file_level: "DEBUG"

  metrics:
    enabled: true
    export:
      enabled: true
      format: "prometheus"

production:
  endpoint_selection:
    enabled: true

  error_handling:
    enabled: true
    retry:
      max_retries: 3

  graceful_degradation:
    enabled: true

  health_monitoring:
    enabled: true
```

## Configuration Best Practices

1. **Security**
   - Never commit API keys or passwords
   - Use environment variables for secrets
   - Rotate API keys regularly

2. **Performance**
   - Tune cache sizes for your workload
   - Adjust max parallel settings based on resources
   - Monitor and optimize timeouts

3. **Reliability**
   - Enable checkpointing for long-running tasks
   - Configure appropriate retry settings
   - Enable health monitoring

4. **Observability**
   - Enable structured logging
   - Collect metrics for monitoring
   - Track decisions for debugging

5. **Safety**
   - Configure tool restrictions
   - Set rate limits
   - Block dangerous patterns
