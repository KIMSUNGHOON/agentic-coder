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

            # Parse plan with defensive checks
            try:
                # CRITICAL: Handle None or empty response
                if not response:
                    raise ValueError("LLM returned empty response")

                # Extract JSON - SAFE split handling
                json_str = None
                if "```json" in response:
                    parts = response.split("```json")
                    if len(parts) > 1:
                        json_str = parts[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                # Check if we extracted valid JSON string
                if not json_str:
                    raise ValueError("Could not extract JSON from LLM response")

                plan = json.loads(json_str)
                state["context"]["plan"] = plan
                # completed_steps already initialized at start of method

                logger.info(f"✅ Plan created: {plan.get('task_type', 'unknown')} task")

                # If plan indicates conversational task, generate appropriate response
                if plan.get('task_type') == 'conversational':
                    logger.info("💬 Conversational task detected, generating LLM response")

                    # Use LLM to generate contextual conversational response
                    conversation_prompt = f"""The user said: "{state['task_description']}"

This is a conversational input (not a task requiring tools). Generate a friendly, helpful response.

Guidelines:
- If it's a greeting: Respond warmly and briefly introduce yourself as Agentic 2.0
- If it's a question: Answer concisely
- If it's unclear: Ask for clarification politely
- Keep response natural and under 3 sentences

Response:"""

                    conv_messages = [
                        {"role": "system", "content": "You are Agentic 2.0, a helpful AI assistant specialized in software development."},
                        {"role": "user", "content": conversation_prompt}
                    ]

                    try:
                        response = await self.call_llm(conv_messages, temperature=0.7, max_tokens=200)
                        state["task_result"] = response.strip()
                        logger.info(f"✅ Generated conversational response: {response[:100]}...")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to generate conversational response: {e}")
                        # Fallback response only if LLM fails
                        state["task_result"] = "Hello! I'm Agentic 2.0, your AI assistant. How can I help you today?"

                    state["task_status"] = TaskStatus.COMPLETED.value
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

            # CRITICAL: Handle None response
            if not response:
                logger.error("LLM returned None/empty response")
                state = add_error(state, "LLM returned empty response")
                state["should_continue"] = False
                return state

            logger.debug(f"LLM response: {response[:200]}...")

            # Store LLM response in state for UI display
            if "llm_responses" not in state["context"]:
                state["context"]["llm_responses"] = []
            state["context"]["llm_responses"].append({
                "iteration": state["iteration"],
                "node": "execute",
                "response": response[:500] if response else "None",  # First 500 chars for preview
                "full_response": response
            })

            # Parse and execute with defensive checks
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

            except (json.JSONDecodeError, ValueError) as e:
                # ⚠️ JSON parsing failed or invalid response - store error and track
                error_msg = f"LLM returned invalid JSON: {str(e)}"
                logger.error(error_msg)
                logger.error(f"Full LLM response:\n{response[:500] if response else 'None'}")

                # Add to tool_calls as failed attempt
                if "tool_calls" not in state:
                    state["tool_calls"] = []
                state["tool_calls"].append({
                    "action": "JSON_PARSE_ERROR",
                    "parameters": {"error": str(e), "response_preview": response[:200]},
                    "result": {"success": False, "error": error_msg},
                    "iteration": state["iteration"],
                    "success": False
                })

                # Store error in state (add_error already imported at top)
                state = add_error(state, error_msg)

                # If JSON parsing fails multiple times, give up
                parse_errors = sum(1 for call in state["tool_calls"] if call.get("action") == "JSON_PARSE_ERROR")
                if parse_errors >= 3:
                    logger.error(f"Multiple JSON parse failures ({parse_errors}), completing task")
                    state["task_status"] = TaskStatus.FAILED.value
                    state["task_error"] = "Unable to parse LLM response as JSON after multiple attempts"
                    state["task_result"] = f"Failed: LLM returned invalid JSON {parse_errors} times"
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

            if action_type == "LIST_DIRECTORY":
                path = params.get("path", ".")
                result = await self.fs_tools.list_directory(path)
                return {
                    "success": result.success,
                    "output": result.output,  # CRITICAL: Use "output" not "entries" for consistency!
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') and result.metadata else {}
                }

            elif action_type == "SEARCH_FILES":
                pattern = params.get("pattern", "*")
                result = await self.fs_tools.search_files(pattern)
                return {
                    "success": result.success,
                    "output": result.output,  # List of file paths
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') and result.metadata else {}
                }

            elif action_type == "READ_FILE":
                file_path = params.get("file_path")
                if not file_path:
                    return {"success": False, "error": "Missing file_path parameter"}
                result = await self.fs_tools.read_file(file_path)
                return {
                    "success": result.success,
                    "content": result.output,  # File content as string
                    "output": result.output,  # Also provide as output for consistency
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') and result.metadata else {}
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
                if content is None:
                    logger.error("❌ WRITE_FILE failed: Missing content parameter (content is None)")
                    logger.error(f"   params received: {params}")
                    return {"success": False, "error": "Missing content parameter"}

                logger.info(f"📝 Writing file: {file_path} ({len(content)} chars)")
                result = await self.fs_tools.write_file(file_path, content)

                if result.success:
                    abs_path = result.metadata.get('path', file_path) if result.metadata else file_path
                    logger.info(f"✅ File written successfully!")
                    logger.info(f"   Requested path: {file_path}")
                    logger.info(f"   Absolute path: {abs_path}")
                    logger.info(f"   Size: {result.metadata.get('bytes', 0)} bytes")
                    logger.info(f"   Lines: {result.metadata.get('lines', 0)}")
                else:
                    logger.error(f"❌ Failed to write file: {result.error}")
                    logger.error(f"   Requested path: {file_path}")

                return {
                    "success": result.success,
                    "message": result.output,
                    "output": result.output,  # Also provide as output
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') and result.metadata else {}
                }

            elif action_type == "RUN_COMMAND":
                command = params.get("command")
                if not command:
                    return {"success": False, "error": "Missing command parameter"}
                result = await self.process_tools.execute_command(command)
                return {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') and result.metadata else {}
                }

            elif action_type == "GIT_STATUS":
                result = await self.git_tools.status()
                return {
                    "success": result.success,
                    "output": result.output,  # Git status output
                    "status": result.output,  # Also provide as "status" for backward compatibility
                    "error": result.error,
                    "metadata": result.metadata if hasattr(result, 'metadata') and result.metadata else {}
                }

            elif action_type == "COMPLETE":
                summary = params.get("summary", "Task complete")
                logger.info(f"✅ Task marked COMPLETE: {summary}")
                return {"success": True, "message": summary}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            logger.error(f"❌ Action execution error: {e}")
            return {"success": False, "error": str(e)}

    async def reflect_node(self, state: AgenticState) -> AgenticState:
        """Reflect on general task progress with aggressive early completion"""
        logger.info(f"🤔 Reflecting (iteration {state['iteration']})")

        try:
            # Check if already completed
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                logger.info("✅ Task already COMPLETED")
                state["should_continue"] = False
                return state

            # === AGGRESSIVE ITERATION LIMITS ===
            # Determine task complexity from description
            task_lower = state['task_description'].lower()

            # Simple task indicators
            simple_indicators = ['create', 'make', 'write', 'add', 'simple', 'basic', 'hello', 'calculator', 'file']
            is_simple_task = any(indicator in task_lower for indicator in simple_indicators)

            # Complex task indicators
            complex_indicators = ['refactor', 'optimize', 'migrate', 'architecture', 'system', 'framework', 'restructure']
            is_complex_task = any(indicator in task_lower for indicator in complex_indicators)

            # Set STRICT iteration limits
            if is_simple_task:
                hard_limit = 8   # 간단한 작업: 최대 8회
            elif is_complex_task:
                hard_limit = 20  # 복잡한 작업: 최대 20회
            else:
                hard_limit = 12  # 일반 작업: 최대 12회

            # Check tool calls
            tool_calls = state.get("tool_calls", [])
            recent_tools = [call.get("action") for call in tool_calls[-5:]]

            logger.info(f"📊 Iteration {state['iteration']}/{hard_limit} | Tool calls: {len(tool_calls)} | Recent: {recent_tools[-3:] if recent_tools else []}")

            # === FORCE COMPLETION CONDITIONS ===

            # 1. HARD LIMIT - 절대 넘지 않음
            if state['iteration'] >= hard_limit:
                logger.warning(f"🛑 HARD LIMIT reached ({hard_limit})")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Task completed after {state['iteration']} iterations (limit: {hard_limit}). Executed {len(tool_calls)} tool calls."
                state["should_continue"] = False
                return state

            # 2. STUCK IN LOOP - 같은 도구 3번 반복
            if len(recent_tools) >= 3 and len(set(recent_tools[-3:])) == 1:
                logger.warning(f"🔁 LOOP detected: {recent_tools[-1]} repeated 3 times")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Task stopped after {state['iteration']} iterations (loop detected)"
                state["should_continue"] = False
                return state

            # 3. NO PROGRESS - iteration 5+ with no tools
            if state['iteration'] >= 5 and len(tool_calls) == 0:
                logger.warning(f"⚠️  No tool activity after {state['iteration']} iterations")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Task completed with no tool executions after {state['iteration']} iterations"
                state["should_continue"] = False
                return state

            # 4. REPEATED FAILURES - 최근 5개 중 4개 실패
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
                    state["task_result"] = f"Task failed after {state['iteration']} iterations due to repeated failures:\n\n{failure_details}"
                    state["should_continue"] = False
                    return state

            # 5. SOFT CHECK - 간단한 작업은 5회 후 도구 활동 체크
            if is_simple_task and state['iteration'] >= 5:
                if len(recent_tools) < 2:
                    logger.info(f"✅ Simple task with minimal recent activity - completing")
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = f"Task completed after {state['iteration']} iterations"
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
