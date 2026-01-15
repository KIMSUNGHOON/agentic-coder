"""Research Workflow for Agentic 2.0

Handles information gathering and analysis tasks:
- Web research
- Documentation review
- Competitive analysis
- Information synthesis
- Summarization

Uses LangGraph for orchestration with research-specific logic.
"""

import logging
import json
from typing import Dict, Any

from core.state import AgenticState, TaskStatus, increment_iteration, add_error
from .base_workflow import BaseWorkflow

logger = logging.getLogger(__name__)


class ResearchWorkflow(BaseWorkflow):
    """Workflow for research tasks

    Specialized for information gathering:
    - Search and collect information
    - Analyze and synthesize
    - Summarize findings
    - Generate reports

    Example:
        >>> workflow = ResearchWorkflow(llm_client, safety)
        >>> result = await workflow.run_with_task(
        ...     "Research best practices for API design",
        ...     "task_456",
        ...     "research"
        ... )
    """

    async def plan_node(self, state: AgenticState) -> AgenticState:
        """Plan research task"""
        logger.info(f"📋 Planning research task: {state['task_description'][:100]}")

        try:
            planning_prompt = f"""You are a research analyst planning an information gathering task.

Task: {state['task_description']}

Create a research plan. Consider:
1. What information do we need?
2. Where should we look? (files, code, documentation)
3. What's the search strategy?
4. How will we synthesize findings?

Respond in JSON format:
{{
    "research_questions": ["question1", "question2"],
    "search_locations": ["location1", "location2"],
    "estimated_steps": 3,
    "synthesis_approach": "approach description"
}}
"""

            messages = [
                {"role": "system", "content": "You are a research analyst."},
                {"role": "user", "content": planning_prompt}
            ]

            response = await self.call_llm(messages, temperature=0.3)

            # Parse and store plan
            try:
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()

                plan = json.loads(json_str)
                state["context"]["plan"] = plan
                state["context"]["findings"] = []

                logger.info(f"✅ Research plan created: {len(plan.get('research_questions', []))} questions")

            except json.JSONDecodeError:
                state["context"]["plan"] = {"raw": response}

            state["iteration"] = 0
            state["task_status"] = TaskStatus.IN_PROGRESS.value

            return state

        except Exception as e:
            logger.error(f"Planning error: {e}")
            state = add_error(state, f"Planning failed: {e}")
            return state

    async def execute_node(self, state: AgenticState) -> AgenticState:
        """Execute research task"""
        logger.info(f"⚙️  Executing research (iteration {state['iteration']})")

        try:
            execution_prompt = f"""You are conducting research step by step.

Task: {state['task_description']}
Plan: {json.dumps(state['context'].get('plan', {}), indent=2)}
Iteration: {state['iteration']}
Findings so far: {json.dumps(state['context'].get('findings', []), indent=2)}

Choose ONE action:

1. SEARCH_FILES: Search for files matching pattern
   Example: {{"action": "SEARCH_FILES", "pattern": "*.md"}}

2. SEARCH_CONTENT: Search file contents
   Example: {{"action": "SEARCH_CONTENT", "pattern": "API design", "file_pattern": "*.md"}}

3. READ_FILE: Read a specific file
   Example: {{"action": "READ_FILE", "file_path": "docs/api_guide.md"}}

4. ANALYZE: Analyze collected information
   Example: {{"action": "ANALYZE", "focus": "What are the key recommendations?"}}

5. COMPLETE: Research is complete
   Example: {{"action": "COMPLETE", "summary": "Research findings..."}}

Respond with ONLY JSON.
"""

            messages = [
                {"role": "system", "content": "You are a research analyst. Respond with only JSON."},
                {"role": "user", "content": execution_prompt}
            ]

            response = await self.call_llm(messages, temperature=0.2)

            # Parse and execute action
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

                # Store findings
                if action.get("action") not in ["COMPLETE", "ANALYZE"]:
                    if action_result.get("success"):
                        state["context"]["findings"].append({
                            "action": action.get("action"),
                            "data": action_result.get("content") or action_result.get("matches"),
                        })

                # Check completion
                if action.get("action") == "COMPLETE":
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = action.get("summary", "Research completed")
                    state["should_continue"] = False

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse action: {e}")

            state = increment_iteration(state)
            return state

        except Exception as e:
            logger.error(f"Execution error: {e}")
            state = add_error(state, f"Execution failed: {e}")
            state["should_continue"] = False
            return state

    async def _execute_action(self, action: Dict[str, Any], state: AgenticState) -> Dict[str, Any]:
        """Execute research action"""
        action_type = action.get("action")

        try:
            if action_type == "SEARCH_FILES":
                pattern = action.get("pattern", "*.md")
                result = await self.fs_tools.search_files(pattern)
                return {"success": result.success, "files": result.output, "error": result.error}

            elif action_type == "SEARCH_CONTENT":
                pattern = action.get("pattern")
                file_pattern = action.get("file_pattern", "*")
                result = await self.search_tools.grep(pattern, file_pattern)
                return {"success": result.success, "matches": result.output, "error": result.error}

            elif action_type == "READ_FILE":
                file_path = action.get("file_path")
                result = await self.fs_tools.read_file(file_path)
                return {"success": result.success, "content": result.output, "error": result.error}

            elif action_type == "ANALYZE":
                # LLM-based analysis of findings
                return {"success": True, "message": "Analysis requested"}

            elif action_type == "COMPLETE":
                return {"success": True, "message": "Research complete"}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def reflect_node(self, state: AgenticState) -> AgenticState:
        """Reflect on research progress with aggressive early completion"""
        logger.info(f"🤔 Reflecting (iteration {state['iteration']})")

        try:
            # Check completion
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                logger.info("✅ Task already COMPLETED")
                state["should_continue"] = False
                return state

            # === AGGRESSIVE ITERATION LIMITS FOR RESEARCH ===
            task_lower = state['task_description'].lower()

            # Research complexity indicators
            simple_indicators = ['find', 'search', 'what', 'where', 'list', 'show']
            is_simple_task = any(indicator in task_lower for indicator in simple_indicators)

            complex_indicators = ['analyze', 'compare', 'evaluate', 'comprehensive', 'detailed']
            is_complex_task = any(indicator in task_lower for indicator in complex_indicators)

            # STRICT iteration limits for research
            if is_simple_task:
                hard_limit = 8   # 간단한 검색: 최대 8회
            elif is_complex_task:
                hard_limit = 20  # 복잡한 분석: 최대 20회
            else:
                hard_limit = 12  # 일반 조사: 최대 12회

            tool_calls = state.get("tool_calls", [])
            findings_count = len(state["context"].get("findings", []))

            logger.info(f"📊 Iteration {state['iteration']}/{hard_limit} | Findings: {findings_count}")

            # === FORCE COMPLETION CONDITIONS ===

            # 1. HARD LIMIT
            if state['iteration'] >= hard_limit:
                logger.warning(f"🛑 HARD LIMIT reached ({hard_limit})")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Research completed after {state['iteration']} iterations. Findings: {findings_count}"
                state["should_continue"] = False
                return state

            # 2. SUFFICIENT FINDINGS
            if findings_count >= 5:
                logger.info(f"✅ Sufficient findings: {findings_count}")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = f"Research completed with {findings_count} findings"
                state["should_continue"] = False
                return state

            # 3. NO PROGRESS
            if state['iteration'] >= 5 and findings_count == 0:
                logger.warning(f"⚠️  No findings after {state['iteration']} iterations")
                state["task_status"] = TaskStatus.COMPLETED.value
                state["task_result"] = "Research completed with no findings"
                state["should_continue"] = False
                return state

            # Continue
            logger.info(f"🔄 Continue → iteration {state['iteration'] + 1}/{hard_limit}")
            state["should_continue"] = True
            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
