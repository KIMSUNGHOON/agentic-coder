"""Task Decomposer for Agentic 2.0

Analyzes complex tasks and breaks them into subtasks:
- Complexity analysis
- Task breakdown strategy
- Dependency detection
- Sub-agent type selection
"""

import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from core.llm_client import DualEndpointLLMClient
from .sub_agent import SubAgentType

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels"""
    SIMPLE = "simple"  # Single operation, no decomposition needed
    MODERATE = "moderate"  # 2-3 steps, limited decomposition
    COMPLEX = "complex"  # 4+ steps, requires decomposition
    VERY_COMPLEX = "very_complex"  # Many steps, parallel execution beneficial


@dataclass
class SubTask:
    """Individual subtask for execution"""
    id: str
    description: str
    agent_type: SubAgentType
    priority: int = 0  # Higher = execute first
    dependencies: List[str] = field(default_factory=list)  # IDs of tasks that must complete first
    estimated_iterations: int = 3
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskBreakdown:
    """Result of task decomposition"""
    original_task: str
    complexity: TaskComplexity
    requires_decomposition: bool
    subtasks: List[SubTask]
    execution_strategy: str  # "sequential" or "parallel"
    estimated_duration_seconds: int
    reasoning: str


class TaskDecomposer:
    """Decomposes complex tasks into subtasks for sub-agents

    Features:
    - LLM-based complexity analysis
    - Intelligent task breakdown
    - Dependency detection
    - Agent type recommendation

    Example:
        >>> decomposer = TaskDecomposer(llm_client)
        >>> breakdown = await decomposer.decompose(
        ...     "Analyze all Python files and generate a report"
        ... )
        >>> print(f"Complexity: {breakdown.complexity}")
        >>> for subtask in breakdown.subtasks:
        ...     print(f"- {subtask.description} ({subtask.agent_type})")
    """

    def __init__(self, llm_client: DualEndpointLLMClient):
        """Initialize task decomposer

        Args:
            llm_client: LLM client for analysis
        """
        self.llm_client = llm_client

    async def decompose(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskBreakdown:
        """Decompose task into subtasks

        Args:
            task_description: Task to decompose
            context: Optional context information

        Returns:
            TaskBreakdown with subtasks and strategy
        """
        logger.info(f"📋 Decomposing task: {task_description[:100]}")

        try:
            # Analyze task complexity
            analysis = await self._analyze_complexity(task_description, context)

            # Check if decomposition needed
            if analysis["complexity"] == TaskComplexity.SIMPLE:
                logger.info("✅ Simple task, no decomposition needed")
                return TaskBreakdown(
                    original_task=task_description,
                    complexity=TaskComplexity.SIMPLE,
                    requires_decomposition=False,
                    subtasks=[],
                    execution_strategy="direct",
                    estimated_duration_seconds=30,
                    reasoning="Task is simple enough for direct execution"
                )

            # Break down into subtasks
            subtasks = await self._break_down_task(
                task_description,
                analysis["complexity"],
                context
            )

            # Determine execution strategy
            strategy = self._determine_strategy(subtasks)

            # Estimate duration
            duration = self._estimate_duration(subtasks, strategy)

            breakdown = TaskBreakdown(
                original_task=task_description,
                complexity=analysis["complexity"],
                requires_decomposition=True,
                subtasks=subtasks,
                execution_strategy=strategy,
                estimated_duration_seconds=duration,
                reasoning=analysis.get("reasoning", "Task requires decomposition")
            )

            logger.info(f"✅ Task decomposed: {len(subtasks)} subtasks, {strategy} execution")

            return breakdown

        except Exception as e:
            logger.error(f"❌ Task decomposition error: {e}")
            # Fallback: treat as simple task
            return TaskBreakdown(
                original_task=task_description,
                complexity=TaskComplexity.SIMPLE,
                requires_decomposition=False,
                subtasks=[],
                execution_strategy="direct",
                estimated_duration_seconds=60,
                reasoning=f"Decomposition failed: {e}, defaulting to direct execution"
            )

    async def _analyze_complexity(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze task complexity using LLM"""

        analysis_prompt = f"""Analyze the complexity of this task.

Task: {task_description}
Context: {json.dumps(context or {}, indent=2)}

Determine:
1. Complexity level: simple, moderate, complex, or very_complex
2. Reasoning for the assessment
3. Key subtasks if complex

Respond in JSON format:
{{
    "complexity": "simple|moderate|complex|very_complex",
    "reasoning": "Why this complexity level?",
    "requires_parallel_execution": true/false,
    "key_operations": ["operation1", "operation2", ...]
}}
"""

        messages = [
            {"role": "system", "content": "You are a task analysis expert. Respond with only JSON."},
            {"role": "user", "content": analysis_prompt}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )

        # Parse response
        try:
            content = response.choices[0].message.content

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            analysis = json.loads(json_str)

            # Convert string to enum
            analysis["complexity"] = TaskComplexity(analysis["complexity"])

            return analysis

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse complexity analysis: {e}")
            return {
                "complexity": TaskComplexity.MODERATE,
                "reasoning": "Default assessment due to parse error",
                "requires_parallel_execution": False,
                "key_operations": []
            }

    async def _break_down_task(
        self,
        task_description: str,
        complexity: TaskComplexity,
        context: Optional[Dict[str, Any]]
    ) -> List[SubTask]:
        """Break task into subtasks using LLM"""

        breakdown_prompt = f"""Break down this task into concrete subtasks.

Task: {task_description}
Complexity: {complexity}
Context: {json.dumps(context or {}, indent=2)}

For each subtask, specify:
1. ID (unique identifier)
2. Description (what needs to be done)
3. Agent type (from: {', '.join([t.value for t in SubAgentType])})
4. Priority (higher number = higher priority, 0-10)
5. Dependencies (IDs of subtasks that must complete first)
6. Estimated iterations (1-10)

Respond in JSON format:
{{
    "subtasks": [
        {{
            "id": "subtask_1",
            "description": "Specific task description",
            "agent_type": "code_reader",
            "priority": 5,
            "dependencies": [],
            "estimated_iterations": 3
        }},
        ...
    ]
}}
"""

        messages = [
            {"role": "system", "content": "You are a task breakdown expert. Respond with only JSON."},
            {"role": "user", "content": breakdown_prompt}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=2000
        )

        # Parse response
        try:
            content = response.choices[0].message.content

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            data = json.loads(json_str)

            subtasks = []
            for st in data.get("subtasks", []):
                # Convert agent_type string to enum
                try:
                    agent_type = SubAgentType(st["agent_type"])
                except ValueError:
                    logger.warning(f"Unknown agent type: {st['agent_type']}, using TASK_EXECUTOR")
                    agent_type = SubAgentType.TASK_EXECUTOR

                subtask = SubTask(
                    id=st["id"],
                    description=st["description"],
                    agent_type=agent_type,
                    priority=st.get("priority", 0),
                    dependencies=st.get("dependencies", []),
                    estimated_iterations=st.get("estimated_iterations", 3)
                )
                subtasks.append(subtask)

            return subtasks

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse task breakdown: {e}")
            # Fallback: create single subtask
            return [
                SubTask(
                    id="fallback_1",
                    description=task_description,
                    agent_type=SubAgentType.TASK_EXECUTOR,
                    priority=0,
                    dependencies=[],
                    estimated_iterations=5
                )
            ]

    def _determine_strategy(self, subtasks: List[SubTask]) -> str:
        """Determine execution strategy based on dependencies

        Returns:
            "sequential" or "parallel"
        """
        if not subtasks:
            return "direct"

        # Check if any task has dependencies
        has_dependencies = any(task.dependencies for task in subtasks)

        if has_dependencies:
            # Some tasks depend on others, use sequential
            return "sequential"
        else:
            # No dependencies, can execute in parallel
            return "parallel"

    def _estimate_duration(self, subtasks: List[SubTask], strategy: str) -> int:
        """Estimate total duration in seconds

        Args:
            subtasks: List of subtasks
            strategy: Execution strategy

        Returns:
            Estimated duration in seconds
        """
        if not subtasks:
            return 30

        # Each iteration takes ~10 seconds on average
        seconds_per_iteration = 10

        if strategy == "parallel":
            # Duration is max of all subtask durations
            max_duration = max(
                task.estimated_iterations * seconds_per_iteration
                for task in subtasks
            )
            return max_duration
        else:
            # Duration is sum of all subtask durations
            total_duration = sum(
                task.estimated_iterations * seconds_per_iteration
                for task in subtasks
            )
            return total_duration

    def analyze_dependencies(self, subtasks: List[SubTask]) -> Dict[str, List[str]]:
        """Analyze dependency graph

        Returns:
            Dict mapping task ID to list of task IDs it depends on
        """
        dependency_graph = {}

        for task in subtasks:
            dependency_graph[task.id] = task.dependencies

        return dependency_graph

    def get_execution_order(self, subtasks: List[SubTask]) -> List[List[str]]:
        """Get execution order respecting dependencies

        Returns:
            List of execution batches (can run in parallel within batch)
        """
        # Build dependency graph
        remaining = {task.id: set(task.dependencies) for task in subtasks}
        completed = set()
        batches = []

        while remaining:
            # Find tasks with no remaining dependencies
            batch = [
                task_id for task_id, deps in remaining.items()
                if not deps
            ]

            if not batch:
                # Circular dependency or error
                logger.warning("Circular dependency detected, breaking...")
                batch = list(remaining.keys())

            batches.append(batch)

            # Remove completed tasks
            for task_id in batch:
                completed.add(task_id)
                del remaining[task_id]

            # Update remaining dependencies
            for task_id in remaining:
                remaining[task_id] -= completed

        return batches
