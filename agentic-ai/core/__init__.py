"""Agentic 2.0 Core Module

Core infrastructure for the Agentic AI system:
- LLM client with dual endpoint failover
- Intent classification and routing
- Configuration management
- Tool safety and security controls
- LangGraph state machine definitions
- Persistence and memory management
"""

from core.llm_client import DualEndpointLLMClient, EndpointConfig, create_llm_client_from_config
from core.config_loader import Config, load_config
from core.router import IntentRouter, WorkflowDomain, IntentClassification, classify_intent
from core.tool_safety import (
    ToolSafetyManager,
    SafetyViolation,
    ViolationType,
    create_safety_manager_from_config,
)
from core.state import (
    AgenticState,
    Message,
    ToolCall,
    SubAgentInfo,
    TaskStatus,
    create_initial_state,
    update_task_status,
    add_error,
    increment_iteration,
    validate_state,
)
from core.optimization import (
    LRUCache,
    LLMResponseCache,
    StateOptimizer,
    PerformanceMonitor,
    get_llm_cache,
    get_state_optimizer,
    get_performance_monitor,
)

__all__ = [
    # LLM Client
    "DualEndpointLLMClient",
    "EndpointConfig",
    "create_llm_client_from_config",
    # Config
    "Config",
    "load_config",
    # Router
    "IntentRouter",
    "WorkflowDomain",
    "IntentClassification",
    "classify_intent",
    # Safety
    "ToolSafetyManager",
    "SafetyViolation",
    "ViolationType",
    "create_safety_manager_from_config",
    # State
    "AgenticState",
    "Message",
    "ToolCall",
    "SubAgentInfo",
    "TaskStatus",
    "create_initial_state",
    "update_task_status",
    "add_error",
    "increment_iteration",
    "validate_state",
    # Optimization
    "LRUCache",
    "LLMResponseCache",
    "StateOptimizer",
    "PerformanceMonitor",
    "get_llm_cache",
    "get_state_optimizer",
    "get_performance_monitor",
]
