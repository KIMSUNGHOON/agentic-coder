"""Backend Bridge for CLI

Integrates CLI with backend workflows, LLM, and orchestrator.
Provides progress streaming and Chain-of-Thought parsing.
"""

import asyncio
import logging
import re
from typing import Optional, AsyncIterator, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from core.config_loader import load_config
from core.llm_client import DualEndpointLLMClient, EndpointConfig
from core.tool_safety import ToolSafetyManager
from workflows.orchestrator import WorkflowOrchestrator, WorkflowResult
from core.router import WorkflowDomain

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Progress update from workflow execution"""
    type: str  # "status", "progress", "cot", "log", "result"
    message: str
    data: Optional[Dict[str, Any]] = None


@dataclass
class CoTBlock:
    """Parsed Chain-of-Thought block"""
    content: str
    step: int
    timestamp: float


class BackendBridge:
    """Bridge between CLI and backend systems

    Features:
    - Configuration loading
    - LLM client initialization
    - Orchestrator management
    - Progress streaming
    - Chain-of-Thought parsing

    Example:
        >>> bridge = BackendBridge()
        >>> await bridge.initialize()
        >>> async for update in bridge.execute_task("Fix auth bug"):
        ...     print(update.message)
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize backend bridge

        Args:
            config_path: Path to configuration file (auto-detected if not provided)
        """
        if config_path is None:
            # Auto-detect config path
            from pathlib import Path

            # Try multiple paths
            possible_paths = [
                Path("config/config.yaml"),  # From project root
                Path("agentic-ai/config/config.yaml"),  # From parent dir
                Path(__file__).parent.parent / "config" / "config.yaml",  # Relative to this file
            ]

            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
            else:
                # Default to first path
                config_path = "config/config.yaml"

        self.config_path = config_path
        self.config = None
        self.llm_client: Optional[DualEndpointLLMClient] = None
        self.safety: Optional[ToolSafetyManager] = None
        self.orchestrator: Optional[WorkflowOrchestrator] = None

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize backend components

        Raises:
            Exception: If initialization fails
        """
        if self._initialized:
            return

        try:
            logger.info("🚀 Initializing backend bridge")

            # Load configuration
            logger.info(f"📋 Loading config from {self.config_path}")
            self.config = load_config(self.config_path)

            # Initialize LLM client
            endpoints = [
                EndpointConfig(
                    url=ep["url"],
                    name=ep["name"],
                    timeout=ep.get("timeout", 120)
                )
                for ep in self.config.llm.endpoints
            ]

            self.llm_client = DualEndpointLLMClient(
                endpoints=endpoints,
                model_name=self.config.llm.model_name,
                health_check_interval=self.config.llm.health_check["interval_seconds"],
                max_retries=self.config.llm.retry["max_attempts"],
                backoff_base=self.config.llm.retry["backoff_base"],
            )

            logger.info(f"✅ LLM client initialized ({len(endpoints)} endpoints)")

            # Initialize safety manager
            # Note: Config uses dataclasses, so we need to extract values properly
            safety_config = self.config.tools.safety
            self.safety = ToolSafetyManager(
                enabled=safety_config.enabled,
                command_allowlist=list(safety_config.command_allowlist) if safety_config.command_allowlist else [],
                command_denylist=list(safety_config.command_denylist) if safety_config.command_denylist else [],
                protected_files=list(safety_config.protected_files) if safety_config.protected_files else [],
                protected_patterns=list(safety_config.protected_patterns) if safety_config.protected_patterns else [],
            )

            logger.info("✅ Tool safety manager initialized")

            # Initialize orchestrator
            # Get recursion_limit from config, default to 100 if not present
            recursion_limit = getattr(self.config.workflows, 'recursion_limit', 100)

            self.orchestrator = WorkflowOrchestrator(
                llm_client=self.llm_client,
                safety_manager=self.safety,
                workspace=self.config.workspace.default_path,
                max_iterations=self.config.workflows.max_iterations,
                recursion_limit=recursion_limit,
            )

            logger.info(f"✅ Workflow orchestrator initialized (recursion_limit: {recursion_limit})")

            self._initialized = True
            logger.info("🎉 Backend bridge ready")

        except Exception as e:
            logger.error(f"❌ Failed to initialize backend: {e}")
            raise

    async def execute_task(
        self,
        task_description: str,
        workspace: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> AsyncIterator[ProgressUpdate]:
        """Execute task with progress streaming

        Args:
            task_description: Task description
            workspace: Optional workspace override
            domain: Optional domain override (coding, research, data, general)

        Yields:
            ProgressUpdate objects with execution status
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Yield initial status
            yield ProgressUpdate(
                type="status",
                message="Starting task execution...",
                data={"status": "initializing"}
            )

            # Parse domain if provided
            domain_override = None
            if domain:
                try:
                    domain_override = WorkflowDomain(domain.lower())
                except ValueError:
                    yield ProgressUpdate(
                        type="log",
                        message=f"Invalid domain '{domain}', using auto-classification",
                        data={"level": "warning"}
                    )

            # Yield classification status
            yield ProgressUpdate(
                type="status",
                message="Classifying intent...",
                data={"status": "classifying"}
            )

            # Execute task
            # Note: For now, we execute directly. In the future, we can add
            # streaming support to the orchestrator to yield intermediate updates.
            result = await self.orchestrator.execute_task(
                task_description=task_description,
                workspace=workspace,
                domain_override=domain_override,
            )

            # Parse result and extract CoT if present
            cot_blocks = self._extract_cot_blocks(result)

            # Yield CoT blocks if found
            for cot in cot_blocks:
                yield ProgressUpdate(
                    type="cot",
                    message=cot.content,
                    data={"step": cot.step, "timestamp": cot.timestamp}
                )

            # Yield final result
            if result.success:
                yield ProgressUpdate(
                    type="result",
                    message="Task completed successfully",
                    data={
                        "success": True,
                        "output": result.output,
                        "iterations": result.iterations,
                        "metadata": result.metadata,
                    }
                )
            else:
                yield ProgressUpdate(
                    type="result",
                    message=f"Task failed: {result.error}",
                    data={
                        "success": False,
                        "error": result.error,
                        "iterations": result.iterations,
                        "metadata": result.metadata,
                    }
                )

        except Exception as e:
            logger.error(f"❌ Task execution failed: {e}", exc_info=True)
            yield ProgressUpdate(
                type="result",
                message=f"Task failed: {str(e)}",
                data={"success": False, "error": str(e)}
            )

    def _extract_cot_blocks(self, result: WorkflowResult) -> list[CoTBlock]:
        """Extract Chain-of-Thought blocks from result

        GPT-OSS-120B uses <think>...</think> tags for reasoning.

        Args:
            result: Workflow result

        Returns:
            List of parsed CoT blocks
        """
        blocks = []

        if not result.output:
            return blocks

        output_str = str(result.output)

        # Find all <think>...</think> blocks
        pattern = r'<think>(.*?)</think>'
        matches = re.finditer(pattern, output_str, re.DOTALL | re.IGNORECASE)

        import time

        for i, match in enumerate(matches, 1):
            content = match.group(1).strip()
            blocks.append(CoTBlock(
                content=content,
                step=i,
                timestamp=time.time()
            ))

        return blocks

    async def get_health_status(self) -> Dict[str, Any]:
        """Get system health status

        Returns:
            Dictionary with health information
        """
        if not self._initialized:
            return {
                "status": "not_initialized",
                "endpoints": [],
                "orchestrator": None,
            }

        # Get LLM health
        llm_health = self.llm_client.get_health_stats()

        # Get orchestrator stats
        orchestrator_stats = self.orchestrator.get_stats()

        # Determine overall status
        healthy_endpoints = llm_health["healthy_endpoints"]
        total_endpoints = llm_health["total_endpoints"]

        if healthy_endpoints == 0:
            status = "unhealthy"
        elif healthy_endpoints < total_endpoints:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "llm": llm_health,
            "orchestrator": orchestrator_stats,
            "config": {
                "mode": self.config.mode,
                "model": self.config.llm.model_name,
                "workspace": self.config.workspace.default_path,
            }
        }

    async def close(self):
        """Clean up resources"""
        if self.orchestrator:
            await self.orchestrator.close()

        if self.llm_client:
            await self.llm_client.close()

        self._initialized = False
        logger.info("🔌 Backend bridge closed")


# Global bridge instance (singleton)
_bridge_instance: Optional[BackendBridge] = None


def get_bridge() -> BackendBridge:
    """Get global backend bridge instance (singleton)

    Returns:
        BackendBridge instance
    """
    global _bridge_instance

    if _bridge_instance is None:
        _bridge_instance = BackendBridge()

    return _bridge_instance
