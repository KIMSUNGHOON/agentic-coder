"""Workflow Orchestrator for Agentic 2.0

Main orchestrator that:
1. Classifies user intent using IntentRouter
2. Selects appropriate workflow (coding, research, data, general)
3. Executes workflow using LangGraph
4. Returns results

This is the main entry point for task execution.
"""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from core.llm_client import DualEndpointLLMClient
from core.router import IntentRouter, WorkflowDomain, IntentClassification
from core.tool_safety import ToolSafetyManager
from core.state import create_initial_state, AgenticState
from .base_workflow import BaseWorkflow, WorkflowResult

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Main workflow orchestrator

    Coordinates the entire agentic system:
    - Intent classification
    - Workflow selection
    - Execution management
    - Result aggregation

    Example:
        >>> orchestrator = WorkflowOrchestrator(llm_client, safety, workspace)
        >>> result = await orchestrator.execute_task("Fix the authentication bug")
        >>> print(result.success, result.output)
    """

    def __init__(
        self,
        llm_client: DualEndpointLLMClient,
        safety_manager: ToolSafetyManager,
        workspace: Optional[str] = None,
        max_iterations: int = 10,
        recursion_limit: int = 100,
        sub_agent_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize WorkflowOrchestrator

        Args:
            llm_client: LLM client for AI operations
            safety_manager: Safety manager for tool validation
            workspace: Default working directory (optional)
            max_iterations: Default max iterations per workflow (default: 10)
            recursion_limit: LangGraph recursion limit (default: 100)
            sub_agent_config: Sub-agent configuration (Phase 5, optional)
        """
        self.llm_client = llm_client
        self.safety = safety_manager
        self.workspace = workspace
        self.max_iterations = max_iterations
        self.recursion_limit = recursion_limit
        self.sub_agent_config = sub_agent_config or {"enabled": False}

        # Initialize intent router
        self.router = IntentRouter(llm_client, confidence_threshold=0.7)

        # Note: Workflows are NOT cached anymore (for session workspace isolation)
        # Each task creates a new workflow instance with the correct workspace

        # Statistics
        self.total_tasks = 0
        self.tasks_by_domain = {domain: 0 for domain in WorkflowDomain}

        logger.info(
            f"🎯 WorkflowOrchestrator initialized "
            f"(workspace: {workspace or 'none'}, max_iterations: {max_iterations}, "
            f"recursion_limit: {recursion_limit}, sub_agents: {self.sub_agent_config.get('enabled', False)})"
        )

    def _get_workflow(self, domain: WorkflowDomain, workspace: Optional[str] = None) -> BaseWorkflow:
        """Get workflow for domain

        Args:
            domain: Workflow domain
            workspace: Workspace path (uses self.workspace if not provided)

        Returns:
            Workflow instance (creates new instance each time for workspace isolation)

        Raises:
            ValueError: If domain is not supported

        Note:
            Workflows are NOT cached to ensure each task gets correct workspace.
            This is critical for session isolation where each session has its own workspace.
        """
        # Use provided workspace or default
        effective_workspace = workspace or self.workspace

        # Create new workflow instance (NO CACHING for workspace isolation!)
        try:
            if domain == WorkflowDomain.CODING:
                from .coding_workflow import CodingWorkflow
                workflow = CodingWorkflow(self.llm_client, self.safety, effective_workspace)

            elif domain == WorkflowDomain.RESEARCH:
                from .research_workflow import ResearchWorkflow
                workflow = ResearchWorkflow(self.llm_client, self.safety, effective_workspace)

            elif domain == WorkflowDomain.DATA:
                from .data_workflow import DataWorkflow
                workflow = DataWorkflow(self.llm_client, self.safety, effective_workspace)

            elif domain == WorkflowDomain.GENERAL:
                from .general_workflow import GeneralWorkflow
                workflow = GeneralWorkflow(self.llm_client, self.safety, effective_workspace)

            else:
                raise ValueError(f"Unsupported domain: {domain}")

            logger.info(f"✅ Created workflow: {domain.value} (workspace: {effective_workspace})")
            return workflow

        except ImportError as e:
            logger.error(f"Failed to import workflow for {domain}: {e}")
            raise ValueError(f"Workflow not implemented: {domain.value}")

    async def classify_and_route(
        self,
        task_description: str
    ) -> tuple[WorkflowDomain, IntentClassification]:
        """Classify task and determine workflow

        Args:
            task_description: User's task description

        Returns:
            Tuple of (domain, classification_result)
        """
        logger.info(f"🎯 Classifying task: {task_description[:100]}")

        # Classify intent
        classification = await self.router.classify(task_description)

        logger.info(
            f"✅ Classification: {classification.domain.value} "
            f"(confidence: {classification.confidence:.2%})"
        )

        return classification.domain, classification

    async def execute_task(
        self,
        task_description: str,
        task_id: Optional[str] = None,
        workspace: Optional[str] = None,
        max_iterations: Optional[int] = None,
        domain_override: Optional[WorkflowDomain] = None,
    ) -> WorkflowResult:
        """Execute task with automatic workflow selection

        Main entry point for task execution.

        Args:
            task_description: User's task description
            task_id: Optional task ID (auto-generated if not provided)
            workspace: Optional workspace override
            max_iterations: Optional max iterations override
            domain_override: Optional domain override (skip classification)

        Returns:
            WorkflowResult with execution results
        """
        # Generate task ID if not provided
        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        # Use defaults if not overridden
        workspace = workspace or self.workspace
        max_iterations = max_iterations or self.max_iterations

        try:
            logger.info(f"🚀 Executing task: {task_id}")
            logger.info(f"📝 Description: {task_description}")

            start_time = datetime.now()

            # Classify and route (unless domain override)
            if domain_override:
                domain = domain_override
                classification = None
                logger.info(f"⚡ Using domain override: {domain.value}")
            else:
                domain, classification = await self.classify_and_route(task_description)

            # Update statistics
            self.total_tasks += 1
            self.tasks_by_domain[domain] += 1

            # Get workflow with correct workspace
            workflow = self._get_workflow(domain, workspace=workspace)

            # Create initial state
            state = create_initial_state(
                task_description=task_description,
                task_id=task_id,
                workflow_domain=domain,
                workspace=workspace,
                max_iterations=max_iterations,
                recursion_limit=self.recursion_limit,
            )

            # Add classification metadata
            if classification:
                state["context"]["classification"] = {
                    "domain": classification.domain.value,
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning,
                    "requires_sub_agents": classification.requires_sub_agents,
                    "estimated_complexity": classification.estimated_complexity,
                }

            # Add sub-agent configuration (Phase 5)
            state["context"]["sub_agent_config"] = self.sub_agent_config

            # Run workflow
            logger.info(f"🔄 Running {domain.value} workflow")
            result = await workflow.run(state)

            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()

            # Add metadata
            if result.metadata is None:
                result.metadata = {}

            result.metadata.update({
                "task_id": task_id,
                "domain": domain.value,
                "classification": classification.to_dict() if classification else None,
                "total_duration_seconds": total_duration,
                "workspace": workspace,
            })

            logger.info(
                f"✅ Task completed: {task_id} "
                f"({result.iterations} iterations, {total_duration:.2f}s)"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Task failed: {task_id} - {e}")

            return WorkflowResult(
                success=False,
                output=None,
                error=str(e),
                iterations=0,
                metadata={
                    "task_id": task_id,
                    "error_type": type(e).__name__,
                }
            )

    async def execute_task_stream(
        self,
        task_description: str,
        task_id: Optional[str] = None,
        workspace: Optional[str] = None,
        max_iterations: Optional[int] = None,
        domain_override: Optional[WorkflowDomain] = None,
    ):
        """Execute task with streaming support (yields intermediate events)

        This enables real-time feedback during task execution:
        - Classification events
        - Workflow node transitions
        - LLM streaming chunks
        - Tool execution events
        - Final results

        Args:
            task_description: User's task description
            task_id: Optional task ID (auto-generated if not provided)
            workspace: Optional workspace override
            max_iterations: Optional max iterations override
            domain_override: Optional domain override (skip classification)

        Yields:
            Dict with event type and data:
            - type: "classification", "workflow_start", "node_executed", "workflow_complete", etc.
            - data: Event-specific data

        Example:
            >>> async for event in orchestrator.execute_task_stream("Fix auth bug"):
            ...     if event["type"] == "node_executed":
            ...         print(f"Node: {event['data']['node']}")
        """
        # Generate task ID if not provided
        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        # Use defaults if not overridden
        workspace = workspace or self.workspace
        max_iterations = max_iterations or self.max_iterations

        try:
            logger.info(f"🚀 Executing task (STREAMING): {task_id}")
            logger.info(f"📝 Description: {task_description}")

            start_time = datetime.now()

            # Classify and route (unless domain override)
            if domain_override:
                domain = domain_override
                classification = None
                logger.info(f"⚡ Using domain override: {domain.value}")

                # Yield domain event
                yield {
                    "type": "classification",
                    "data": {
                        "domain": domain.value,
                        "override": True
                    }
                }
            else:
                # Yield classification start
                yield {
                    "type": "classification_start",
                    "data": {"task": task_description}
                }

                domain, classification = await self.classify_and_route(task_description)

                # Yield classification result
                yield {
                    "type": "classification",
                    "data": {
                        "domain": domain.value,
                        "confidence": classification.confidence,
                        "reasoning": classification.reasoning[:200] if classification.reasoning else None,
                        "override": False
                    }
                }

            # Update statistics
            self.total_tasks += 1
            self.tasks_by_domain[domain] += 1

            # Get workflow with correct workspace
            workflow = self._get_workflow(domain, workspace=workspace)

            # Create initial state
            state = create_initial_state(
                task_description=task_description,
                task_id=task_id,
                workflow_domain=domain,
                workspace=workspace,
                max_iterations=max_iterations,
                recursion_limit=self.recursion_limit,
            )

            # Add classification metadata
            if classification:
                state["context"]["classification"] = {
                    "domain": classification.domain.value,
                    "confidence": classification.confidence,
                    "reasoning": classification.reasoning,
                    "requires_sub_agents": classification.requires_sub_agents,
                    "estimated_complexity": classification.estimated_complexity,
                }

            # Add sub-agent configuration (Phase 5)
            state["context"]["sub_agent_config"] = self.sub_agent_config

            # Run workflow with streaming
            logger.info(f"🔄 Running {domain.value} workflow (STREAMING)")

            async for event in workflow.run_stream(state):
                # Propagate workflow events
                yield event

            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()

            # Yield task complete event
            yield {
                "type": "task_complete",
                "data": {
                    "task_id": task_id,
                    "domain": domain.value,
                    "total_duration": total_duration
                }
            }

        except Exception as e:
            logger.error(f"❌ Task failed (STREAMING): {task_id} - {e}", exc_info=True)
            yield {
                "type": "task_error",
                "data": {
                    "task_id": task_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }

    async def execute_with_domain(
        self,
        task_description: str,
        domain: WorkflowDomain,
        task_id: Optional[str] = None,
        workspace: Optional[str] = None,
        max_iterations: Optional[int] = None,
    ) -> WorkflowResult:
        """Execute task with specific domain (skip classification)

        Useful when domain is already known.

        Args:
            task_description: Task description
            domain: Specific workflow domain
            task_id: Optional task ID
            workspace: Optional workspace
            max_iterations: Optional max iterations

        Returns:
            WorkflowResult
        """
        return await self.execute_task(
            task_description=task_description,
            task_id=task_id,
            workspace=workspace,
            max_iterations=max_iterations,
            domain_override=domain,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics

        Returns:
            Dictionary with statistics
        """
        return {
            "total_tasks": self.total_tasks,
            "tasks_by_domain": {
                domain.value: count
                for domain, count in self.tasks_by_domain.items()
            },
            "router_stats": self.router.get_stats(),
            # Note: Workflows are not cached anymore (for workspace isolation)
        }

    async def close(self):
        """Clean up resources"""
        logger.info("🔌 Closing orchestrator")

        # Close LLM client
        await self.llm_client.close()

        # Clear workflow cache
        self._workflows.clear()

        logger.info("✅ Orchestrator closed")
