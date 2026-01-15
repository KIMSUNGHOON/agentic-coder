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
            logger.error(f"❌ Planning error: {e}")

            # Provide clear error message based on error type
            error_msg = str(e)
            if "Connection" in error_msg or "refused" in error_msg or "timeout" in error_msg.lower():
                user_msg = (
                    "🚨 LLM 서버에 연결할 수 없습니다!\n\n"
                    "해결 방법:\n"
                    "1. vLLM 서버가 실행 중인지 확인하세요\n"
                    "2. config.yaml에서 LLM endpoint 설정을 확인하세요\n"
                    "3. 서버 포트가 열려있는지 확인하세요\n\n"
                    f"기술 상세: {error_msg}"
                )
            else:
                user_msg = f"Planning 실패: {error_msg}"

            state["task_status"] = TaskStatus.FAILED.value
            state["task_error"] = user_msg
            state["task_result"] = user_msg  # Also set result so it shows in UI
            state["should_continue"] = False
            state = add_error(state, user_msg)
            return state

    async def execute_node(self, state: AgenticState) -> AgenticState:
        """Execute general task"""
        logger.info(f"⚙️  Executing general task (iteration {state['iteration']})")

        try:
            # Calculate progress
            completed_steps = state['context'].get('completed_steps', [])
            plan = state['context'].get('plan', {})
            estimated_steps = plan.get('estimated_steps', len(plan.get('steps', [])))

            execution_prompt = f"""You are executing a general task step by step.

Task: {state['task_description']}
Plan: {json.dumps(plan, indent=2)}
Iteration: {state['iteration']}/{state['max_iterations']}
Progress: {len(completed_steps)}/{estimated_steps} steps completed
Completed steps: {completed_steps}

IMPORTANT: If you have completed ALL required steps for the task, you MUST use the COMPLETE action.

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

COMPLETION (ALWAYS USE THIS WHEN DONE):
7. COMPLETE: Task is complete - **MANDATORY** when you finish
   Example: {{"action": "COMPLETE", "summary": "Successfully created calculator.py with basic operations"}}

🚨 CRITICAL DECISION RULES:
1. For file creation tasks: After WRITE_FILE → Use COMPLETE immediately
2. For simple tasks: 2-3 tool calls is enough → Use COMPLETE
3. For questions: After gathering info → Use COMPLETE
4. If you wrote code successfully → Use COMPLETE
5. DON'T keep using tools unnecessarily → Use COMPLETE when done

✅ GOOD Example (Simple task):
User: "Create calculator.py"
Iteration 1: LIST_DIRECTORY (check files)
Iteration 2: WRITE_FILE (create calculator.py)
Iteration 3: COMPLETE ← STOP HERE!

❌ BAD Example:
Iteration 3: READ_FILE (why? already done!)
Iteration 4: WRITE_FILE again (unnecessary!)
Iteration 5-50: Keep repeating tools (WRONG!)

**Respond with ONLY JSON. Use COMPLETE action if task is finished.**
"""

            messages = [
                {"role": "system", "content": "You are a helpful assistant. Respond with only JSON."},
                {"role": "user", "content": execution_prompt}
            ]

            response = await self.call_llm(messages, temperature=0.2)
            logger.debug(f"LLM response: {response[:200]}...")

            # Store LLM response in state for UI display
            if "llm_responses" not in state["context"]:
                state["context"]["llm_responses"] = []
            state["context"]["llm_responses"].append({
                "iteration": state["iteration"],
                "node": "execute",
                "response": response[:500],  # First 500 chars for preview
                "full_response": response
            })

            # Parse and execute
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                action = json.loads(json_str)
                action_name = action.get("action", "UNKNOWN")

                # Store action decision in state for UI display
                state["context"]["last_action"] = {
                    "action": action_name,
                    "iteration": state["iteration"],
                    "details": action
                }

                # Log what action we're executing
                logger.info(f"🔧 Executing action: {action_name}")
                if action_name == "COMPLETE":
                    logger.info(f"✅ Task completion requested: {action.get('summary', 'N/A')[:100]}")
                else:
                    logger.debug(f"   Action details: {json.dumps(action, indent=2)[:200]}")

                action_result = await self._execute_action(action, state)

                # Log action result
                if action_result.get("success"):
                    logger.info(f"✅ Action {action_name} succeeded")
                else:
                    logger.warning(f"⚠️  Action {action_name} failed: {action_result.get('error', 'Unknown error')}")

                # Store result with detailed info for UI display
                if "tool_calls" not in state:
                    state["tool_calls"] = []

                tool_call_info = {
                    "action": action.get("action"),
                    "action_details": action,  # Include parameters
                    "result": action_result,
                    "iteration": state["iteration"],
                    "success": action_result.get("success", False),
                }
                state["tool_calls"].append(tool_call_info)

                # Store last tool execution for UI streaming
                state["context"]["last_tool_execution"] = tool_call_info

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
            logger.error(f"❌ Execution error: {e}")

            # Provide clear error message
            error_msg = str(e)
            if "Connection" in error_msg or "refused" in error_msg or "timeout" in error_msg.lower():
                user_msg = (
                    "🚨 LLM 서버 연결 실패!\n\n"
                    "작업 실행 중 LLM 서버와의 연결이 끊어졌습니다.\n"
                    "vLLM 서버 상태를 확인하세요.\n\n"
                    f"기술 상세: {error_msg}"
                )
            else:
                user_msg = f"작업 실행 실패: {error_msg}"

            state["task_status"] = TaskStatus.FAILED.value
            state["task_error"] = user_msg
            state["task_result"] = user_msg
            state = add_error(state, user_msg)
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
            # Check if already completed
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                logger.info("✅ Task is COMPLETED, stopping workflow")
                state["should_continue"] = False
                return state

            # Check if max iterations reached
            if state["iteration"] >= state["max_iterations"]:
                logger.warning(f"⚠️  Max iterations ({state['max_iterations']}) reached!")
                state["should_continue"] = False

                # Check if we made progress despite hitting max iterations
                completed_steps = state["context"].get("completed_steps", [])
                if len(completed_steps) > 0:
                    # We made progress! Report as partial success
                    logger.warning(f"⚠️  Made progress: {len(completed_steps)} steps completed")
                    state["task_status"] = TaskStatus.COMPLETED.value  # Changed from FAILED
                    state["task_result"] = (
                        f"Task partially completed ({len(completed_steps)} steps). "
                        f"You may need to continue or adjust the task. "
                        f"Completed: {', '.join(completed_steps[:5])}"
                    )
                else:
                    # No progress at all
                    logger.warning(f"⚠️  No progress made in {state['max_iterations']} iterations")
                    state["task_status"] = TaskStatus.FAILED.value
                    state["task_error"] = (
                        f"Max iterations ({state['max_iterations']}) reached without completing the task. "
                        f"This may indicate: (1) Task is too complex, (2) LLM not available, "
                        f"or (3) Task needs to be broken down into smaller steps."
                    )
                return state

            # Check progress and provide detailed feedback
            completed_steps = state["context"].get("completed_steps", [])
            plan = state["context"].get("plan", {})
            total_steps = plan.get("estimated_steps", len(plan.get("steps", [])))
            task_type = plan.get("task_type", "unknown")

            # === Early completion checks ===

            # 1. Check if all steps are done
            if len(completed_steps) > 0:
                logger.info(f"✅ Progress: {len(completed_steps)}/{total_steps} steps completed")
                logger.debug(f"   Completed steps: {completed_steps}")

                # Auto-complete if all steps are done
                if total_steps > 0 and len(completed_steps) >= total_steps:
                    logger.info(f"🎯 All {total_steps} steps completed! Auto-completing task")
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = f"Task completed successfully. Completed steps: {', '.join(completed_steps)}"
                    state["should_continue"] = False
                    return state

                # Warn if approaching max iterations without completion
                remaining = state['max_iterations'] - state['iteration']
                if remaining <= 5 and len(completed_steps) < total_steps:
                    logger.warning(f"⚠️  Only {remaining} iterations left! Progress: {len(completed_steps)}/{total_steps}")

            # 2. Conversational/simple tasks: Complete after 1-3 iterations
            if task_type == "conversational" and state['iteration'] >= 1:
                logger.info(f"💬 Conversational task completed after {state['iteration']} iteration(s)")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = "Conversational task completed"
                state["should_continue"] = False
                return state

            # 3. If no progress after 5 iterations, likely stuck or task is too vague
            if len(completed_steps) == 0 and state['iteration'] >= 5:
                logger.warning(f"⚠️  No progress after {state['iteration']} iterations. Completing with partial results")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = (
                    f"Task completed with limited progress after {state['iteration']} iterations. "
                    "This may indicate the task needs to be more specific or broken down into smaller parts."
                )
                state["should_continue"] = False
                return state

            # 4. Check for repeated failures
            recent_tool_calls = state.get("tool_calls", [])[-5:]  # Last 5 calls
            if len(recent_tool_calls) >= 5:
                failed_count = sum(1 for call in recent_tool_calls if not call.get("result", {}).get("success"))
                if failed_count >= 4:  # 4 out of 5 failed
                    logger.warning(f"⚠️  Multiple tool failures detected. Stopping to avoid infinite loop")
                    state["task_status"] = TaskStatus.FAILED.value
                    state["task_error"] = "Task stopped due to repeated tool failures"
                    state["should_continue"] = False
                    return state

            # 5. Detect repeated actions (stuck in loop)
            if len(recent_tool_calls) >= 3:
                actions = [call.get("action") for call in recent_tool_calls[-3:]]
                if len(set(actions)) == 1:  # Same action 3 times in a row
                    logger.warning(f"⚠️  Repeated action detected ({actions[0]}). May be stuck in loop")
                    # Don't stop yet, but warn

            # === Smart iteration-based completion ===

            # Determine task complexity from description
            task_lower = state['task_description'].lower()

            # Simple task indicators
            simple_indicators = ['create', 'make', 'write', 'add', 'simple', 'basic', 'hello', 'calculator']
            is_simple_task = any(indicator in task_lower for indicator in simple_indicators)

            # Complex task indicators
            complex_indicators = ['refactor', 'optimize', 'migrate', 'architecture', 'system', 'framework']
            is_complex_task = any(indicator in task_lower for indicator in complex_indicators)

            # Set iteration limits based on task type
            if is_simple_task:
                soft_limit = 5
                hard_limit = 10
            elif is_complex_task:
                soft_limit = 15
                hard_limit = 25
            else:
                soft_limit = 10
                hard_limit = 20

            # Check tool calls for actual progress
            tool_calls = state.get("tool_calls", [])
            recent_tools = [call.get("action") for call in tool_calls[-5:]]

            # Force completion conditions:
            # 1. Exceeded hard limit
            if state['iteration'] >= hard_limit:
                logger.warning(f"⚠️  Hard limit reached ({hard_limit} iterations)")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = (
                    f"Task completed after {state['iteration']} iterations. "
                    f"Executed {len(tool_calls)} tool calls. "
                    f"Consider breaking down into smaller tasks if incomplete."
                )
                state["should_continue"] = False
                return state

            # 2. Past soft limit with no recent tool activity
            if state['iteration'] >= soft_limit:
                if len(recent_tools) < 2:
                    logger.info(f"✅ Soft limit reached with minimal activity - completing task")
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = f"Task completed after {state['iteration']} iterations with {len(tool_calls)} actions"
                    state["should_continue"] = False
                    return state
                else:
                    logger.warning(f"⚠️  Soft limit exceeded ({soft_limit}), but still active. Will stop at hard limit ({hard_limit})")

            # 3. Stuck in loop (same tool 4+ times in a row)
            if len(recent_tools) >= 4 and len(set(recent_tools[-4:])) == 1:
                logger.warning(f"⚠️  Stuck in loop with repeated {recent_tools[-1]} calls")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Task stopped: Detected loop pattern after {state['iteration']} iterations"
                state["should_continue"] = False
                return state

            # Continue: Still within limits
            logger.info(f"🔄 Continuing iteration {state['iteration']}/{hard_limit} (soft limit: {soft_limit})")
            state["should_continue"] = True
            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
