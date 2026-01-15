"""Coding Workflow for Agentic 2.0

Handles software development tasks:
- Bug fixes
- New feature implementation
- Code review
- Testing
- Refactoring

Uses LangGraph for orchestration with coding-specific logic.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from core.state import AgenticState, TaskStatus, update_task_status
from core.prompts import CodingPrompts
from .base_workflow import BaseWorkflow

logger = logging.getLogger(__name__)


class CodingWorkflow(BaseWorkflow):
    """Workflow for coding tasks

    Specialized for software development:
    - Code analysis and understanding
    - Implementation with safety checks
    - Testing and validation
    - Git operations (optional)

    Example:
        >>> workflow = CodingWorkflow(llm_client, safety, "/project")
        >>> result = await workflow.run_with_task(
        ...     "Fix authentication bug in login.py",
        ...     "task_123",
        ...     "coding"
        ... )
    """

    async def plan_node(self, state: AgenticState) -> AgenticState:
        """Plan coding task

        Analyzes the task and creates execution plan:
        1. Understand requirements
        2. Identify files to modify
        3. Determine approach
        4. Check for dependencies

        Args:
            state: Current workflow state

        Returns:
            Updated state with plan
        """
        logger.info(f"📋 Planning coding task: {state['task_description'][:100]}")

        try:
            # Use optimized prompt for GPT-OSS-120B
            messages = CodingPrompts.planning_prompt(
                task=state['task_description'],
                workspace=state.get('workspace', 'unknown'),
                context=state.get('context')
            )

            # Call LLM with lower temperature for planning
            response = await self.call_llm(messages, temperature=0.3)

            # Parse response
            try:
                # Extract JSON from response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                plan = json.loads(json_str)

                # Store plan in context
                state["context"]["plan"] = plan
                state["context"]["current_step"] = 0
                state["requires_sub_agents"] = plan.get("requires_sub_agents", False)

                logger.info(f"✅ Plan created: {plan.get('estimated_steps', 'unknown')} steps")

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse plan JSON: {e}")
                # Fallback: store raw response
                state["context"]["plan"] = {"raw": response}

            # Initialize iteration
            state["iteration"] = 0
            state["task_status"] = TaskStatus.IN_PROGRESS.value

            return state

        except Exception as e:
            logger.error(f"Planning error: {e}")
            state = add_error(state, f"Planning failed: {e}")
            return state

    async def execute_node(self, state: AgenticState) -> AgenticState:
        """Execute coding task

        Implements the planned changes:
        1. Read relevant files
        2. Analyze code
        3. Make modifications (with safety checks)
        4. Run tests (if applicable)
        5. Verify changes

        Args:
            state: Current workflow state

        Returns:
            Updated state with execution results
        """
        from core.state import increment_iteration

        logger.info(f"⚙️  Executing coding task (iteration {state['iteration']})")

        try:
            plan = state["context"].get("plan", {})
            current_step = state["context"].get("current_step", 0)
            previous_actions = state.get('tool_calls', [])

            # Use optimized prompt for GPT-OSS-120B
            messages = CodingPrompts.execution_prompt(
                task=state['task_description'],
                plan=plan,
                current_step=current_step,
                previous_actions=previous_actions
            )

            # Call LLM with low temperature for precise execution
            response = await self.call_llm(messages, temperature=0.2)

            # Parse action
            try:
                # Extract JSON
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                action = json.loads(json_str)

                # Execute action
                action_result = await self._execute_action(action, state)

                # Store result
                if "tool_calls" not in state:
                    state["tool_calls"] = []

                state["tool_calls"].append({
                    "action": action.get("action"),
                    "parameters": action,
                    "result": action_result,
                    "iteration": state["iteration"],
                })

                # Update context
                state["context"]["last_action"] = action
                state["context"]["last_result"] = action_result

                # Check if complete
                if action.get("action") == "COMPLETE":
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = action.get("summary", "Task completed")
                    state["should_continue"] = False

                    logger.info(f"✅ Task completed: {action.get('summary')}")

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse action JSON: {e}")
                logger.warning(f"Response: {response[:200]}")

            # Increment iteration
            state = increment_iteration(state)

            return state

        except Exception as e:
            logger.error(f"Execution error: {e}")
            from core.state import add_error
            state = add_error(state, f"Execution failed: {e}")
            state["should_continue"] = False
            return state

    async def _execute_action(self, action: Dict[str, Any], state: AgenticState) -> Dict[str, Any]:
        """Execute a single action

        Args:
            action: Action dictionary
            state: Current state

        Returns:
            Action result
        """
        action_type = action.get("action")

        try:
            if action_type == "READ_FILE":
                file_path = action.get("file_path")
                result = await self.fs_tools.read_file(file_path)
                return {"success": result.success, "content": result.output, "error": result.error}

            elif action_type == "SEARCH_CODE":
                pattern = action.get("pattern")
                file_pattern = action.get("file_pattern", "*.py")
                result = await self.search_tools.grep(pattern, file_pattern)
                return {"success": result.success, "matches": result.output, "error": result.error}

            elif action_type == "WRITE_FILE":
                file_path = action.get("file_path")
                content = action.get("content")
                result = await self.fs_tools.write_file(file_path, content)
                return {"success": result.success, "message": result.output, "error": result.error}

            elif action_type == "RUN_TESTS":
                test_path = action.get("test_path", "tests/")
                command = f"pytest {test_path} -v"
                result = await self.process_tools.execute_command(command, timeout=120)
                return {"success": result.success, "output": result.output, "error": result.error}

            elif action_type == "GIT_STATUS":
                result = await self.git_tools.status()
                return {"success": result.success, "status": result.output, "error": result.error}

            elif action_type == "COMPLETE":
                return {"success": True, "message": "Task marked complete"}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {"success": False, "error": str(e)}

    async def reflect_node(self, state: AgenticState) -> AgenticState:
        """Reflect on coding task progress with aggressive early completion"""
        logger.info(f"🤔 Reflecting (iteration {state['iteration']})")

        try:
            # Check if complete
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                logger.info("✅ Task already COMPLETED")
                state["should_continue"] = False
                return state

            # === AGGRESSIVE ITERATION LIMITS FOR CODING ===
            task_lower = state['task_description'].lower()

            # Coding task complexity indicators
            simple_indicators = ['create', 'make', 'write', 'add', 'simple', 'basic', 'calculator', 'function', 'class']
            is_simple_task = any(indicator in task_lower for indicator in simple_indicators)

            complex_indicators = ['refactor', 'optimize', 'architecture', 'framework', 'migration', 'restructure']
            is_complex_task = any(indicator in task_lower for indicator in complex_indicators)

            # STRICT iteration limits for coding
            if is_simple_task:
                hard_limit = 10  # 간단한 코딩: 최대 10회
            elif is_complex_task:
                hard_limit = 25  # 복잡한 코딩: 최대 25회
            else:
                hard_limit = 15  # 일반 코딩: 최대 15회

            # Check tool calls
            tool_calls = state.get("tool_calls", [])
            recent_tools = [call.get("action") for call in tool_calls[-5:]]

            logger.info(f"📊 Iteration {state['iteration']}/{hard_limit} | Tool calls: {len(tool_calls)}")

            # === FORCE COMPLETION CONDITIONS ===

            # 1. HARD LIMIT
            if state['iteration'] >= hard_limit:
                logger.warning(f"🛑 HARD LIMIT reached ({hard_limit})")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Coding task completed after {state['iteration']} iterations"
                state["should_continue"] = False
                return state

            # 2. LOOP DETECTION
            if len(recent_tools) >= 3 and len(set(recent_tools[-3:])) == 1:
                logger.warning(f"🔁 LOOP detected: {recent_tools[-1]} repeated")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Task stopped (loop detected)"
                state["should_continue"] = False
                return state

            # 3. NO PROGRESS
            if state['iteration'] >= 5 and len(tool_calls) == 0:
                logger.warning(f"⚠️  No tool activity after {state['iteration']} iterations")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = "Task completed with no tool executions"
                state["should_continue"] = False
                return state

            # 4. REPEATED FAILURES
            if len(tool_calls) >= 5:
                recent_5 = tool_calls[-5:]
                failed = sum(1 for call in recent_5 if not call.get("success", False))
                if failed >= 4:
                    logger.warning(f"❌ Multiple failures: {failed}/5")
                    state["task_status"] = TaskStatus.FAILED.value
                    state["task_error"] = f"{failed} out of 5 recent tool calls failed"
                    state["task_result"] = "Task failed due to repeated failures"
                    state["should_continue"] = False
                    return state

            # Continue to next iteration
            logger.info(f"🔄 Continue → iteration {state['iteration'] + 1}/{hard_limit}")
            state["should_continue"] = True
            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            from core.state import add_error
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
