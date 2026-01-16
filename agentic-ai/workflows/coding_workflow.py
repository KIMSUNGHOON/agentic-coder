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

from core.state import AgenticState, TaskStatus, update_task_status, add_error
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
            # Initialize context if needed
            if "context" not in state:
                state["context"] = {}

            # Use optimized prompt for GPT-OSS-120B
            messages = CodingPrompts.planning_prompt(
                task=state['task_description'],
                workspace=state.get('workspace', 'unknown'),
                context=state.get('context')
            )

            # Call LLM with lower temperature for planning
            response = await self.call_llm(messages, temperature=0.3)

            # Parse response with defensive checks
            try:
                # CRITICAL: Handle None or empty response
                if not response:
                    raise ValueError("LLM returned empty response")

                # Extract JSON from response - SAFE split handling
                json_str = None
                if "```json" in response:
                    parts = response.split("```json")
                    if len(parts) > 1:
                        json_str = parts[1].split("```")[0].strip()
                elif "```" in response:
                    parts = response.split("```")
                    if len(parts) > 1:
                        json_str = parts[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                # Check if we extracted valid JSON string
                if not json_str:
                    raise ValueError("Could not extract JSON from LLM response")

                plan = json.loads(json_str)

                # Store plan in context
                state["context"]["plan"] = plan
                state["context"]["current_step"] = 0
                state["requires_sub_agents"] = plan.get("requires_sub_agents", False)

                logger.info(f"✅ Plan created: {plan.get('estimated_steps', 'unknown')} steps")

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse plan JSON: {e}")
                logger.warning(f"Response preview: {response[:200] if response else 'None'}")
                # Fallback: store raw response
                state["context"]["plan"] = {"raw": response if response else ""}

            except ValueError as e:
                logger.error(f"Invalid LLM response: {e}")
                state["context"]["plan"] = {"error": str(e)}

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

            # CRITICAL: Handle None response
            if not response:
                logger.error("LLM returned None/empty response")
                state = add_error(state, "LLM returned empty response")
                state["should_continue"] = False
                return state

            # Store LLM response for debugging
            if "llm_responses" not in state["context"]:
                state["context"]["llm_responses"] = []
            state["context"]["llm_responses"].append({
                "iteration": state["iteration"],
                "node": "execute",
                "response": response[:500] if response else "None",  # Preview
                "full_response": response  # Full response for debugging
            })

            # Parse action with defensive checks
            try:
                # CRITICAL: Log raw response for debugging
                logger.info("=" * 60)
                logger.info("📥 RAW LLM RESPONSE:")
                logger.info(f"   Length: {len(response)} chars")
                logger.info(f"   First 500 chars: {repr(response[:500])}")
                logger.info(f"   Last 200 chars: {repr(response[-200:])}")
                logger.info("=" * 60)

                # Extract JSON - SAFE split handling
                json_str = None
                if "```json" in response:
                    parts = response.split("```json")
                    if len(parts) > 1:
                        json_str = parts[1].split("```")[0].strip()
                        logger.info("✅ Extracted JSON from ```json``` block")
                elif "```" in response:
                    parts = response.split("```")
                    if len(parts) > 1:
                        json_str = parts[1].split("```")[0].strip()
                        logger.info("✅ Extracted JSON from ``` block")
                else:
                    json_str = response.strip()
                    logger.info("✅ Using entire response as JSON")

                # Check if we extracted valid JSON string
                if not json_str:
                    raise ValueError("Could not extract JSON from LLM response")

                logger.info(f"📋 Extracted JSON string length: {len(json_str)}")
                logger.info(f"📋 JSON preview: {repr(json_str[:300])}")

                # CRITICAL: Validate JSON before parsing
                try:
                    action = json.loads(json_str)
                    logger.info(f"✅ JSON parsed successfully")
                    logger.info(f"   Action type: {action.get('action')}")
                    logger.info(f"   Has parameters: {'parameters' in action}")
                except json.JSONDecodeError as json_err:
                    logger.error(f"❌ JSON parsing failed at position {json_err.pos}")
                    logger.error(f"   Error: {json_err.msg}")
                    logger.error(f"   Line: {json_err.lineno}, Column: {json_err.colno}")
                    logger.error(f"   Context around error:")
                    start = max(0, json_err.pos - 50)
                    end = min(len(json_str), json_err.pos + 50)
                    logger.error(f"   ...{repr(json_str[start:end])}...")
                    raise  # Re-raise to be caught by outer handler

                # Execute action
                action_result = await self._execute_action(action, state)

                # Store result with success flag
                if "tool_calls" not in state:
                    state["tool_calls"] = []

                tool_call_info = {
                    "action": action.get("action"),
                    "action_details": action,  # Full action for debugging
                    "result": action_result,
                    "iteration": state["iteration"],
                    "success": action_result.get("success", False),
                }
                state["tool_calls"].append(tool_call_info)

                # Update context for UI display
                state["context"]["last_action"] = action
                state["context"]["last_result"] = action_result
                state["context"]["last_tool_execution"] = tool_call_info

                # Check if complete
                if action.get("action") == "COMPLETE":
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = action.get("summary", "Task completed")
                    state["should_continue"] = False

                    logger.info(f"✅ Task completed: {action.get('summary')}")

            except (json.JSONDecodeError, ValueError) as e:
                # ⚠️ JSON parsing failed or invalid response - store error and continue
                error_msg = f"LLM returned invalid JSON: {str(e)}"
                logger.error(error_msg)
                logger.error(f"Full LLM response:\n{response[:500] if response else 'None'}")

                # Store failed parsing attempt (add_error already imported at top)
                state = add_error(state, error_msg)

                # Add to tool_calls as failed attempt for tracking
                if "tool_calls" not in state:
                    state["tool_calls"] = []
                state["tool_calls"].append({
                    "action": "JSON_PARSE_ERROR",
                    "parameters": {"error": str(e), "response_preview": response[:200]},
                    "result": {"success": False, "error": error_msg},
                    "iteration": state["iteration"],
                    "success": False
                })

            # Increment iteration
            state = increment_iteration(state)

            return state

        except Exception as e:
            logger.error(f"Execution error: {e}")
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
        # CRITICAL: Handle None action
        if not action or not isinstance(action, dict):
            logger.error(f"Invalid action: {action}")
            return {"success": False, "error": f"Invalid action type: {type(action)}"}

        action_type = action.get("action")

        try:
            # Extract parameters from action (LLM returns {"action": "X", "parameters": {...}})
            # CRITICAL: Handle None parameters
            params = action.get("parameters", {})
            if params is None:
                params = {}

            if action_type == "READ_FILE":
                file_path = params.get("file_path")
                if not file_path:
                    return {"success": False, "error": "Missing file_path parameter"}
                result = await self.fs_tools.read_file(file_path)
                return {
                    "success": result.success,
                    "output": result.output,  # File content
                    "content": result.output,  # Alias for backward compatibility
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }

            elif action_type == "SEARCH_CODE":
                pattern = params.get("pattern")
                if not pattern:
                    return {"success": False, "error": "Missing pattern parameter"}
                file_pattern = params.get("file_pattern", "*.py")
                result = await self.search_tools.grep(pattern, file_pattern)
                return {
                    "success": result.success,
                    "matches": result.output,
                    "output": result.output,  # Alias
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }

            elif action_type == "WRITE_FILE":
                file_path = params.get("file_path")
                content = params.get("content")

                # CRITICAL: Detailed logging for debugging
                logger.info(f"📝 WRITE_FILE request:")
                logger.info(f"   file_path: {file_path}")
                logger.info(f"   content type: {type(content)}")
                logger.info(f"   content length: {len(content) if content is not None else 'None'}")
                logger.info(f"   content preview: {repr(content[:100]) if content else 'None'}")

                if not file_path:
                    logger.error("❌ WRITE_FILE failed: Missing file_path parameter")
                    return {"success": False, "error": "Missing file_path parameter"}
                if content is None:  # Allow empty string
                    logger.error("❌ WRITE_FILE failed: Missing content parameter (content is None)")
                    logger.error(f"   params received: {params}")
                    return {"success": False, "error": "Missing content parameter"}

                logger.info(f"📝 Writing file: {file_path} ({len(content)} chars)")
                result = await self.fs_tools.write_file(file_path, content)

                # Log result clearly
                if result.success:
                    abs_path = result.metadata.get('path', file_path) if result.metadata else file_path
                    logger.info(f"✅ File written successfully!")
                    logger.info(f"   Requested path: {file_path}")
                    logger.info(f"   Absolute path: {abs_path}")
                    logger.info(f"   Size: {result.metadata.get('bytes', 0)} bytes")
                    logger.info(f"   Lines: {result.metadata.get('lines', 0)}")
                    logger.info(f"   Metadata: {result.metadata}")
                else:
                    logger.error(f"❌ Failed to write file: {result.error}")
                    logger.error(f"   Requested path: {file_path}")

                # CRITICAL: Include metadata for UI display (absolute path, file size, etc.)
                return {
                    "success": result.success,
                    "message": result.output,
                    "output": result.output,  # Also provide as output
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }

            elif action_type == "LIST_DIRECTORY":
                # CRITICAL: This was missing - file browser didn't work!
                dir_path = params.get("path", ".")
                recursive = params.get("recursive", False)

                logger.info(f"📂 Listing directory: {dir_path} (recursive={recursive})")
                result = await self.fs_tools.list_directory(dir_path, recursive=recursive)

                if result.success:
                    logger.info(f"✅ Listed {len(result.output) if result.output else 0} entries")
                else:
                    logger.error(f"❌ Failed to list directory: {result.error}")

                return {
                    "success": result.success,
                    "output": result.output,  # List of entries
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }

            elif action_type == "RUN_TESTS":
                test_path = params.get("test_path", "tests/")
                command = f"pytest {test_path} -v"
                result = await self.process_tools.execute_command(command, timeout=120)
                return {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }

            elif action_type == "GIT_STATUS":
                result = await self.git_tools.status()
                return {
                    "success": result.success,
                    "status": result.output,
                    "output": result.output,  # Alias
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') else {}
                }

            elif action_type == "COMPLETE":
                summary = params.get("summary", "Task completed")
                logger.info(f"✅ Task marked COMPLETE: {summary}")
                return {"success": True, "message": summary}

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
                    # Collect detailed failure information
                    failed_tools = []
                    for call in recent_5:
                        if not call.get("success", False):
                            tool_name = call.get("action", "UNKNOWN")
                            error = call.get("result", {}).get("error", "No error message")
                            failed_tools.append(f"{tool_name}: {error}")

                    failure_details = "\n".join(failed_tools)
                    logger.warning(f"❌ Multiple failures: {failed}/5")
                    logger.warning(f"Failed tools:\n{failure_details}")

                    state["task_status"] = TaskStatus.FAILED.value
                    state["task_error"] = f"Task failed: {failed} out of 5 recent tool calls failed"
                    state["task_result"] = f"Task failed due to repeated failures:\n\n{failure_details}"
                    state["should_continue"] = False
                    return state

            # Continue to next iteration
            logger.info(f"🔄 Continue → iteration {state['iteration'] + 1}/{hard_limit}")
            state["should_continue"] = True
            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
