"""Production Module for Agentic 2.0

Production-ready features:
- Performance optimization
- Error handling
- Health checks
- Deployment support
"""

from .performance import (
    EndpointSelector,
    EndpointConfig,
    EndpointHealth,
    ContextFilter,
    ParallelToolExecutor,
)
from .error_handler import (
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    ErrorInfo,
    ErrorRecovery,
    GracefulDegradation,
    DegradationStrategy,
)
from .health_check import (
    HealthChecker,
    HealthStatus,
    ComponentHealth,
    llm_health_check,
    database_health_check,
    disk_space_health_check,
    memory_health_check,
)

__all__ = [
    # Performance
    "EndpointSelector",
    "EndpointConfig",
    "EndpointHealth",
    "ContextFilter",
    "ParallelToolExecutor",
    # Error handling
    "ErrorHandler",
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorInfo",
    "ErrorRecovery",
    "GracefulDegradation",
    "DegradationStrategy",
    # Health
    "HealthChecker",
    "HealthStatus",
    "ComponentHealth",
    "llm_health_check",
    "database_health_check",
    "disk_space_health_check",
    "memory_health_check",
]
