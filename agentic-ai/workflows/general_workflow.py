"""General Workflow for Agentic 2.0

Handles general tasks and mixed workflows:
- File operations and organization
- Task management
- System administration
- Mixed domain tasks
- Fallback for unclear tasks

Uses LangGraph for orchestration with general-purpose logic.
"""

import logging
import json
from typing import Dict, Any

from core.state import AgenticState, TaskStatus, increment_iteration, add_error
from .base_workflow import BaseWorkflow

logger = logging.getLogger(__name__)


class GeneralWorkflow(BaseWorkflow):
    """Workflow for general tasks

    Handles diverse tasks:
    - File organization
    - System operations
    - Task management
    - Multi-domain tasks

    Example:
        >>> workflow = GeneralWorkflow(llm_client, safety, "/workspace")
        >>> result = await workflow.run_with_task(
        ...     "Organize project files into folders",
        ...     "task_abc",
        ...     "general"
        ... )
    """

    async def plan_node(self, state: AgenticState) -> AgenticState:
        """Plan general task"""
        logger.info(f"📋 Planning general task: {state['task_description'][:100]}")

        try:
            # Initialize context if needed
            if "context" not in state:
                state["context"] = {}

            # Always initialize completed_steps at the start
            if "completed_steps" not in state["context"]:
                state["context"]["completed_steps"] = []

            task_lower = state['task_description'].lower().strip()

            # Handle simple greetings and conversational inputs
            greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이']
            if any(keyword in task_lower for keyword in greeting_keywords) and len(task_lower) < 20:
                logger.info("👋 Detected simple greeting, completing immediately")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Hello! I'm Agentic 2.0. How can I help you today?"
                state["should_continue"] = False
                return state

            planning_prompt = f"""You are planning a general task.

Task: {state['task_description']}
Workspace: {state.get('workspace', 'unknown')}

Analyze this task and create a plan. Consider:
1. What type of task is this?
2. What operations are needed?
3. What's the sequence of actions?
4. Are there any dependencies?

Respond in JSON format:
{{
    "task_type": "file_organization|system_admin|task_management|mixed|conversational",
    "steps": ["step1", "step2", "step3"],
    "estimated_steps": 3,
    "tools_needed": ["filesystem", "process", "git"]
}}
"""

            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": planning_prompt}
            ]

            response = await self.call_llm(messages, temperature=0.3)

            # Parse plan
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                plan = json.loads(json_str)
                state["context"]["plan"] = plan
                # completed_steps already initialized at start of method

                logger.info(f"✅ Plan created: {plan.get('task_type', 'unknown')} task")

                # If plan indicates conversational task, complete immediately
                if plan.get('task_type') == 'conversational':
                    logger.info("💬 Conversational task detected, completing")
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = "I'm ready to assist you. Please let me know what specific task you'd like help with."
                    state["should_continue"] = False
                    return state

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM plan response: {e}")
                # If we can't parse the plan, treat as conversational and complete
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = "I'm ready to help. Please provide more specific details about what you'd like me to do."
                state["should_continue"] = False
                return state

            state["iteration"] = 0
            state["task_status"] = TaskStatus.IN_PROGRESS.value

            return state

        except Exception as e:
            logger.error(f"Planning error: {e}")
            # If planning fails (e.g., LLM server not available), fail gracefully
            state["task_status"] = TaskStatus.FAILED.value
            state["task_error"] = f"Planning failed: {e}. Is the LLM server running?"
            state["should_continue"] = False
            state = add_error(state, f"Planning failed: {e}")
            return state

    async def execute_node(self, state: AgenticState) -> AgenticState:
        """Execute general task"""
        logger.info(f"⚙️  Executing general task (iteration {state['iteration']})")

        try:
            execution_prompt = f"""You are executing a general task step by step.

Task: {state['task_description']}
Plan: {json.dumps(state['context'].get('plan', {}), indent=2)}
Iteration: {state['iteration']}
Completed steps: {state['context'].get('completed_steps', [])}

Choose ONE action from available tools:

FILESYSTEM:
1. LIST_DIRECTORY: List directory contents
   Example: {{"action": "LIST_DIRECTORY", "path": "."}}

2. SEARCH_FILES: Find files by pattern
   Example: {{"action": "SEARCH_FILES", "pattern": "*.md"}}

3. READ_FILE: Read a file
   Example: {{"action": "READ_FILE", "file_path": "README.md"}}

4. WRITE_FILE: Write to a file
   Example: {{"action": "WRITE_FILE", "file_path": "output.txt", "content": "..."}}

PROCESS:
5. RUN_COMMAND: Execute shell command
   Example: {{"action": "RUN_COMMAND", "command": "ls -la"}}

GIT:
6. GIT_STATUS: Check git status
   Example: {{"action": "GIT_STATUS"}}

COMPLETION:
7. COMPLETE: Task is complete
   Example: {{"action": "COMPLETE", "summary": "Task summary..."}}

Respond with ONLY JSON.
"""

            messages = [
                {"role": "system", "content": "You are a helpful assistant. Respond with only JSON."},
                {"role": "user", "content": execution_prompt}
            ]

            response = await self.call_llm(messages, temperature=0.2)

            # Parse and execute
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                action = json.loads(json_str)
                action_result = await self._execute_action(action, state)

                # Store result
                if "tool_calls" not in state:
                    state["tool_calls"] = []

                state["tool_calls"].append({
                    "action": action.get("action"),
                    "result": action_result,
                    "iteration": state["iteration"],
                })

                # Track completed steps (safe access)
                if action_result.get("success"):
                    if "completed_steps" not in state["context"]:
                        state["context"]["completed_steps"] = []
                    state["context"]["completed_steps"].append(action.get("action"))

                # Check completion
                if action.get("action") == "COMPLETE":
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = action.get("summary", "Task completed")
                    state["should_continue"] = False

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse action: {e}")
                # If JSON parsing fails multiple times, give up
                if state["iteration"] >= 2:
                    logger.error("Multiple JSON parse failures, completing task")
                    state["task_status"] = TaskStatus.FAILED.value
                    state["task_error"] = "Unable to parse LLM response as JSON"
                    state["should_continue"] = False
                    return state

            state = increment_iteration(state)
            return state

        except Exception as e:
            logger.error(f"Execution error: {e}")
            # If execution fails (e.g., LLM call fails), mark as failed
            state["task_status"] = TaskStatus.FAILED.value
            state["task_error"] = f"Execution failed: {e}"
            state = add_error(state, f"Execution failed: {e}")
            state["should_continue"] = False
            return state

    async def _execute_action(self, action: Dict[str, Any], state: AgenticState) -> Dict[str, Any]:
        """Execute general action"""
        action_type = action.get("action")

        try:
            if action_type == "LIST_DIRECTORY":
                path = action.get("path", ".")
                result = await self.fs_tools.list_directory(path)
                return {"success": result.success, "entries": result.output, "error": result.error}

            elif action_type == "SEARCH_FILES":
                pattern = action.get("pattern", "*")
                result = await self.fs_tools.search_files(pattern)
                return {"success": result.success, "files": result.output, "error": result.error}

            elif action_type == "READ_FILE":
                file_path = action.get("file_path")
                result = await self.fs_tools.read_file(file_path)
                return {"success": result.success, "content": result.output, "error": result.error}

            elif action_type == "WRITE_FILE":
                file_path = action.get("file_path")
                content = action.get("content")
                result = await self.fs_tools.write_file(file_path, content)
                return {"success": result.success, "message": result.output, "error": result.error}

            elif action_type == "RUN_COMMAND":
                command = action.get("command")
                result = await self.process_tools.execute_command(command)
                return {"success": result.success, "output": result.output, "error": result.error}

            elif action_type == "GIT_STATUS":
                result = await self.git_tools.status()
                return {"success": result.success, "status": result.output, "error": result.error}

            elif action_type == "COMPLETE":
                return {"success": True, "message": "Task complete"}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def reflect_node(self, state: AgenticState) -> AgenticState:
        """Reflect on general task progress"""
        logger.info(f"🤔 Reflecting on general task (iteration {state['iteration']})")

        try:
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                state["should_continue"] = False
                return state

            if state["iteration"] >= state["max_iterations"]:
                state["should_continue"] = False
                state["task_status"] = TaskStatus.FAILED.value
                state["task_error"] = "Max iterations reached"
                return state

            # Check progress
            completed_steps = state["context"].get("completed_steps", [])
            if len(completed_steps) > 0:
                logger.info(f"✅ Progress: {len(completed_steps)} steps completed")

            state["should_continue"] = True
            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
