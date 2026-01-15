"""Health Check for Agentic 2.0

System health monitoring:
- Component health checks
- System status
- Readiness checks
- Liveness checks
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Component health info"""
    name: str
    status: HealthStatus
    message: str
    last_check: datetime
    details: Dict[str, Any]


class HealthChecker:
    """System health checker

    Features:
    - Component health monitoring
    - Aggregated health status
    - Readiness/liveness checks
    - Health history

    Example:
        >>> checker = HealthChecker()
        >>> checker.register_check("llm", llm_health_check)
        >>> checker.register_check("database", db_health_check)
        >>> health = await checker.check_all()
    """

    def __init__(self):
        """Initialize health checker"""
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, ComponentHealth] = {}

    def register_check(
        self,
        name: str,
        check_func: Callable[[], bool]
    ):
        """Register a health check

        Args:
            name: Component name
            check_func: Function that returns True if healthy
        """
        self.checks[name] = check_func
        logger.info(f"Registered health check: {name}")

    async def check_component(self, name: str) -> ComponentHealth:
        """Check single component

        Args:
            name: Component name

        Returns:
            ComponentHealth object
        """
        if name not in self.checks:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="No health check registered",
                last_check=datetime.now(),
                details={}
            )

        check_func = self.checks[name]

        try:
            import asyncio

            # Execute health check
            if asyncio.iscoroutinefunction(check_func):
                is_healthy = await check_func()
            else:
                is_healthy = check_func()

            status = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY
            message = "OK" if is_healthy else "Health check failed"

            component_health = ComponentHealth(
                name=name,
                status=status,
                message=message,
                last_check=datetime.now(),
                details={"check_passed": is_healthy}
            )

        except Exception as e:
            logger.error(f"Health check failed for {name}: {e}")

            component_health = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
                last_check=datetime.now(),
                details={"error": str(e)}
            )

        # Store result
        self.last_results[name] = component_health

        return component_health

    async def check_all(self) -> Dict[str, Any]:
        """Check all components

        Returns:
            Dict with overall health status
        """
        import asyncio

        # Check all components
        tasks = [
            self.check_component(name)
            for name in self.checks.keys()
        ]

        if tasks:
            component_results = await asyncio.gather(*tasks)
        else:
            component_results = []

        # Aggregate status
        healthy_count = sum(
            1 for c in component_results
            if c.status == HealthStatus.HEALTHY
        )
        unhealthy_count = sum(
            1 for c in component_results
            if c.status == HealthStatus.UNHEALTHY
        )
        degraded_count = sum(
            1 for c in component_results
            if c.status == HealthStatus.DEGRADED
        )

        # Determine overall status
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        elif healthy_count > 0:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN

        return {
            "status": overall_status.value,
            "timestamp": datetime.now().isoformat(),
            "components": {
                c.name: {
                    "status": c.status.value,
                    "message": c.message,
                    "last_check": c.last_check.isoformat(),
                }
                for c in component_results
            },
            "summary": {
                "total": len(component_results),
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count,
            }
        }

    def is_ready(self) -> bool:
        """Readiness check (can accept requests)

        Returns:
            True if system is ready
        """
        # System is ready if no components are unhealthy
        if not self.last_results:
            return False  # No checks performed yet

        unhealthy = any(
            c.status == HealthStatus.UNHEALTHY
            for c in self.last_results.values()
        )

        return not unhealthy

    def is_alive(self) -> bool:
        """Liveness check (system is running)

        Returns:
            True if system is alive
        """
        # System is alive if we can execute checks
        # This is a simple check that the health checker is operational
        return True

    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary

        Returns:
            Dict with health summary
        """
        if not self.last_results:
            return {
                "status": "unknown",
                "message": "No health checks performed yet",
                "components": []
            }

        healthy_count = sum(
            1 for c in self.last_results.values()
            if c.status == HealthStatus.HEALTHY
        )
        total = len(self.last_results)

        if healthy_count == total:
            status = "healthy"
            message = "All components healthy"
        elif healthy_count == 0:
            status = "unhealthy"
            message = "All components unhealthy"
        else:
            status = "degraded"
            message = f"{healthy_count}/{total} components healthy"

        return {
            "status": status,
            "message": message,
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                }
                for c in self.last_results.values()
            ]
        }


# Pre-defined health check functions

def llm_health_check(llm_client) -> Callable[[], bool]:
    """Create LLM health check function

    Args:
        llm_client: LLM client instance

    Returns:
        Health check function
    """
    def check():
        # Check if endpoints are available
        if not hasattr(llm_client, 'endpoints'):
            return False

        # Check if at least one endpoint is healthy
        for endpoint in llm_client.endpoints:
            if endpoint.is_healthy:
                return True

        return False

    return check


def database_health_check(db_path: str) -> Callable[[], bool]:
    """Create database health check function

    Args:
        db_path: Database path

    Returns:
        Health check function
    """
    def check():
        import os
        # Simple check: database file exists
        return os.path.exists(db_path)

    return check


def disk_space_health_check(min_free_gb: float = 1.0) -> Callable[[], bool]:
    """Create disk space health check function

    Args:
        min_free_gb: Minimum free space in GB

    Returns:
        Health check function
    """
    def check():
        import shutil
        stat = shutil.disk_usage("/")
        free_gb = stat.free / (1024**3)
        return free_gb >= min_free_gb

    return check


def memory_health_check(max_usage_percent: float = 90.0) -> Callable[[], bool]:
    """Create memory health check function

    Args:
        max_usage_percent: Maximum memory usage percentage

    Returns:
        Health check function
    """
    def check():
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent <= max_usage_percent
        except ImportError:
            # psutil not available, assume healthy
            return True

    return check
