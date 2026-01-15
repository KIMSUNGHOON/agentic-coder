"""Parallel Executor for Agentic 2.0

Executes multiple sub-agents concurrently:
- Parallel task execution
- Resource management
- Error handling
- Progress tracking
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .sub_agent import SubAgent
from .task_decomposer import SubTask

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """Result of sub-agent execution"""
    subtask_id: str
    agent_name: str
    status: ExecutionStatus
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    iterations: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ParallelExecutor:
    """Executes multiple sub-agents in parallel

    Features:
    - Concurrent execution with asyncio
    - Configurable parallelism limit
    - Error isolation (one failure doesn't stop others)
    - Progress tracking
    - Timeout management

    Example:
        >>> executor = ParallelExecutor(max_parallel=3)
        >>> results = await executor.execute_batch([
        ...     (agent1, subtask1),
        ...     (agent2, subtask2),
        ...     (agent3, subtask3)
        ... ])
        >>> for result in results:
        ...     if result.success:
        ...         print(f"✅ {result.subtask_id}: {result.result}")
    """

    def __init__(
        self,
        max_parallel: int = 5,
        default_timeout: int = 300
    ):
        """Initialize parallel executor

        Args:
            max_parallel: Maximum concurrent executions (default: 5)
            default_timeout: Default timeout per task in seconds (default: 300)
        """
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.active_count = 0
        self.completed_count = 0
        self.failed_count = 0

        logger.info(f"🚀 ParallelExecutor initialized (max_parallel={max_parallel})")

    async def execute_batch(
        self,
        agent_tasks: List[tuple[SubAgent, SubTask]],
        parent_context: Optional[Dict[str, Any]] = None
    ) -> List[ExecutionResult]:
        """Execute a batch of sub-agents in parallel

        Args:
            agent_tasks: List of (SubAgent, SubTask) tuples
            parent_context: Optional context to pass to all agents

        Returns:
            List of ExecutionResult objects
        """
        if not agent_tasks:
            return []

        logger.info(f"🚀 Executing batch of {len(agent_tasks)} tasks (max_parallel={self.max_parallel})")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_parallel)

        # Create tasks
        tasks = [
            self._execute_with_semaphore(agent, subtask, semaphore, parent_context)
            for agent, subtask in agent_tasks
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        execution_results = []
        for i, result in enumerate(results):
            agent, subtask = agent_tasks[i]

            if isinstance(result, Exception):
                # Task raised an exception
                logger.error(f"❌ Task {subtask.id} failed with exception: {result}")
                execution_results.append(ExecutionResult(
                    subtask_id=subtask.id,
                    agent_name=agent.config.name,
                    status=ExecutionStatus.FAILED,
                    success=False,
                    error=str(result)
                ))
                self.failed_count += 1
            else:
                # Task completed (may have succeeded or failed)
                execution_results.append(result)
                if result.success:
                    self.completed_count += 1
                else:
                    self.failed_count += 1

        success_count = sum(1 for r in execution_results if r.success)
        logger.info(f"✅ Batch complete: {success_count}/{len(agent_tasks)} succeeded")

        return execution_results

    async def _execute_with_semaphore(
        self,
        agent: SubAgent,
        subtask: SubTask,
        semaphore: asyncio.Semaphore,
        parent_context: Optional[Dict[str, Any]]
    ) -> ExecutionResult:
        """Execute single task with semaphore control"""

        async with semaphore:
            self.active_count += 1
            started_at = datetime.now()

            try:
                logger.info(f"▶️  Starting {subtask.id} with {agent.config.name}")

                # Merge parent context with subtask context
                context = {**(parent_context or {}), **subtask.context}

                # Execute task
                task_result = await agent.execute_task(
                    task_description=subtask.description,
                    task_id=subtask.id,
                    parent_context=context
                )

                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()

                # Create execution result
                if task_result["success"]:
                    status = ExecutionStatus.COMPLETED
                    logger.info(f"✅ {subtask.id} completed in {duration:.1f}s")
                else:
                    status = ExecutionStatus.FAILED
                    logger.error(f"❌ {subtask.id} failed: {task_result.get('error', 'Unknown error')}")

                return ExecutionResult(
                    subtask_id=subtask.id,
                    agent_name=agent.config.name,
                    status=status,
                    success=task_result["success"],
                    result=task_result.get("result"),
                    error=task_result.get("error"),
                    duration_seconds=duration,
                    iterations=task_result.get("iterations", 0),
                    started_at=started_at,
                    completed_at=completed_at
                )

            except Exception as e:
                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()

                logger.error(f"❌ {subtask.id} exception: {e}")

                return ExecutionResult(
                    subtask_id=subtask.id,
                    agent_name=agent.config.name,
                    status=ExecutionStatus.FAILED,
                    success=False,
                    error=str(e),
                    duration_seconds=duration,
                    started_at=started_at,
                    completed_at=completed_at
                )

            finally:
                self.active_count -= 1

    async def execute_sequential(
        self,
        agent_tasks: List[tuple[SubAgent, SubTask]],
        parent_context: Optional[Dict[str, Any]] = None
    ) -> List[ExecutionResult]:
        """Execute tasks sequentially (one at a time)

        Args:
            agent_tasks: List of (SubAgent, SubTask) tuples
            parent_context: Optional context to pass to all agents

        Returns:
            List of ExecutionResult objects
        """
        logger.info(f"🔄 Executing {len(agent_tasks)} tasks sequentially")

        results = []

        for agent, subtask in agent_tasks:
            started_at = datetime.now()

            try:
                logger.info(f"▶️  Starting {subtask.id} with {agent.config.name}")

                # Merge context
                context = {**(parent_context or {}), **subtask.context}

                # Execute task
                task_result = await agent.execute_task(
                    task_description=subtask.description,
                    task_id=subtask.id,
                    parent_context=context
                )

                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()

                # Create execution result
                if task_result["success"]:
                    status = ExecutionStatus.COMPLETED
                    logger.info(f"✅ {subtask.id} completed in {duration:.1f}s")
                    self.completed_count += 1
                else:
                    status = ExecutionStatus.FAILED
                    logger.error(f"❌ {subtask.id} failed: {task_result.get('error', 'Unknown error')}")
                    self.failed_count += 1

                result = ExecutionResult(
                    subtask_id=subtask.id,
                    agent_name=agent.config.name,
                    status=status,
                    success=task_result["success"],
                    result=task_result.get("result"),
                    error=task_result.get("error"),
                    duration_seconds=duration,
                    iterations=task_result.get("iterations", 0),
                    started_at=started_at,
                    completed_at=completed_at
                )

                results.append(result)

            except Exception as e:
                completed_at = datetime.now()
                duration = (completed_at - started_at).total_seconds()

                logger.error(f"❌ {subtask.id} exception: {e}")
                self.failed_count += 1

                result = ExecutionResult(
                    subtask_id=subtask.id,
                    agent_name=agent.config.name,
                    status=ExecutionStatus.FAILED,
                    success=False,
                    error=str(e),
                    duration_seconds=duration,
                    started_at=started_at,
                    completed_at=completed_at
                )

                results.append(result)

        success_count = sum(1 for r in results if r.success)
        logger.info(f"✅ Sequential execution complete: {success_count}/{len(agent_tasks)} succeeded")

        return results

    async def execute_with_dependencies(
        self,
        agent_tasks: List[tuple[SubAgent, SubTask]],
        execution_batches: List[List[str]],
        parent_context: Optional[Dict[str, Any]] = None
    ) -> List[ExecutionResult]:
        """Execute tasks respecting dependencies

        Args:
            agent_tasks: List of (SubAgent, SubTask) tuples
            execution_batches: Batches of task IDs (from TaskDecomposer.get_execution_order)
            parent_context: Optional context to pass to all agents

        Returns:
            List of ExecutionResult objects
        """
        logger.info(f"🔄 Executing {len(agent_tasks)} tasks in {len(execution_batches)} batches")

        # Create lookup for agent_tasks by subtask ID
        task_map = {subtask.id: (agent, subtask) for agent, subtask in agent_tasks}

        all_results = []
        accumulated_context = parent_context.copy() if parent_context else {}

        for batch_num, batch_ids in enumerate(execution_batches):
            logger.info(f"📦 Batch {batch_num + 1}/{len(execution_batches)}: {len(batch_ids)} tasks")

            # Get agents and subtasks for this batch
            batch_tasks = [task_map[task_id] for task_id in batch_ids if task_id in task_map]

            # Execute batch in parallel
            batch_results = await self.execute_batch(batch_tasks, accumulated_context)

            # Update accumulated context with results
            for result in batch_results:
                if result.success and result.result:
                    accumulated_context[result.subtask_id] = result.result

            all_results.extend(batch_results)

        success_count = sum(1 for r in all_results if r.success)
        logger.info(f"✅ Dependency-aware execution complete: {success_count}/{len(agent_tasks)} succeeded")

        return all_results

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            "max_parallel": self.max_parallel,
            "active_count": self.active_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "total_executed": self.completed_count + self.failed_count
        }

    def reset_stats(self):
        """Reset execution statistics"""
        self.completed_count = 0
        self.failed_count = 0
