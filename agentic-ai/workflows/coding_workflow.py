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
            # Build planning prompt
            planning_prompt = f"""You are a senior software engineer planning a coding task.

Task: {state['task_description']}
Workspace: {state.get('workspace', 'unknown')}

Analyze this task and create a structured plan. Consider:
1. What needs to be done?
2. Which files might need to be modified?
3. What's the best approach?
4. Are there any dependencies or risks?
5. Should we create sub-tasks?

Respond in JSON format:
{{
    "understanding": "Brief task understanding",
    "approach": "Implementation approach",
    "files_to_check": ["list", "of", "files"],
    "estimated_steps": 3,
    "requires_sub_agents": false,
    "risks": ["potential", "risks"]
}}
"""

            messages = [
                {"role": "system", "content": "You are a senior software engineer."},
                {"role": "user", "content": planning_prompt}
            ]

            # Call LLM
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

            # Build execution prompt
            execution_prompt = f"""You are executing a coding task step by step.

Task: {state['task_description']}
Plan: {json.dumps(plan, indent=2)}
Current Step: {current_step + 1}
Iteration: {state['iteration']}

Previous actions: {json.dumps(state.get('tool_calls', [])[-5:], indent=2) if state.get('tool_calls') else 'None'}

What should you do next? Choose ONE action:

1. READ_FILE: Read a file to understand code
   Example: {{"action": "READ_FILE", "file_path": "src/auth/login.py"}}

2. SEARCH_CODE: Search for specific code patterns
   Example: {{"action": "SEARCH_CODE", "pattern": "def authenticate", "file_pattern": "*.py"}}

3. WRITE_FILE: Write or modify a file (be careful!)
   Example: {{"action": "WRITE_FILE", "file_path": "src/auth/login.py", "content": "..."}}

4. RUN_TESTS: Run tests to verify changes
   Example: {{"action": "RUN_TESTS", "test_path": "tests/test_auth.py"}}

5. GIT_STATUS: Check git status
   Example: {{"action": "GIT_STATUS"}}

6. COMPLETE: Task is complete
   Example: {{"action": "COMPLETE", "summary": "Successfully fixed bug"}}

Respond with ONLY the JSON action, no explanation.
"""

            messages = [
                {"role": "system", "content": "You are a senior software engineer. Respond with only JSON."},
                {"role": "user", "content": execution_prompt}
            ]

            # Call LLM
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
        """Reflect on coding task progress

        Reviews execution and decides next steps:
        1. Was the action successful?
        2. Is the task complete?
        3. Do we need more iterations?
        4. Any errors to address?

        Args:
            state: Current workflow state

        Returns:
            Updated state with reflection
        """
        logger.info(f"🤔 Reflecting on iteration {state['iteration']}")

        try:
            last_action = state["context"].get("last_action", {})
            last_result = state["context"].get("last_result", {})

            # Check if complete
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                state["should_continue"] = False
                logger.info("✅ Task is complete")
                return state

            # Check max iterations
            if state["iteration"] >= state["max_iterations"]:
                state["should_continue"] = False
                state["task_status"] = TaskStatus.FAILED.value
                state["task_error"] = f"Max iterations reached ({state['max_iterations']})"
                logger.warning(f"⚠️  Max iterations reached")
                return state

            # Check last result
            if not last_result.get("success"):
                logger.warning(f"⚠️  Last action failed: {last_result.get('error')}")
                # Continue to retry (up to max iterations)

            # Continue iteration
            state["should_continue"] = True

            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            from core.state import add_error
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
