"""Data Workflow for Agentic 2.0

Handles data processing and analysis tasks:
- Data cleaning and transformation
- Statistical analysis
- Data visualization
- ETL operations
- Database queries

Uses LangGraph for orchestration with data-specific logic.
"""

import logging
import json
from typing import Dict, Any

from core.state import AgenticState, TaskStatus, increment_iteration, add_error
from .base_workflow import BaseWorkflow

logger = logging.getLogger(__name__)


class DataWorkflow(BaseWorkflow):
    """Workflow for data tasks

    Specialized for data processing:
    - Load and inspect data
    - Clean and transform
    - Analyze and visualize
    - Generate insights

    Example:
        >>> workflow = DataWorkflow(llm_client, safety, "/data")
        >>> result = await workflow.run_with_task(
        ...     "Analyze sales data in Q4_sales.csv",
        ...     "task_789",
        ...     "data"
        ... )
    """

    async def plan_node(self, state: AgenticState) -> AgenticState:
        """Plan data task"""
        logger.info(f"📋 Planning data task: {state['task_description'][:100]}")

        try:
            planning_prompt = f"""You are a data analyst planning a data processing task.

Task: {state['task_description']}
Workspace: {state.get('workspace', 'unknown')}

Create a data analysis plan. Consider:
1. What data needs to be processed?
2. What operations are required? (load, clean, transform, analyze)
3. What insights should we extract?
4. What outputs are needed?

Respond in JSON format:
{{
    "data_sources": ["file1.csv", "file2.csv"],
    "operations": ["load", "clean", "analyze"],
    "estimated_steps": 4,
    "expected_insights": ["insight1", "insight2"]
}}
"""

            messages = [
                {"role": "system", "content": "You are a data analyst."},
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
                state["context"]["data_loaded"] = False

                logger.info(f"✅ Data plan created: {len(plan.get('operations', []))} operations")

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
        """Execute data task"""
        logger.info(f"⚙️  Executing data task (iteration {state['iteration']})")

        try:
            execution_prompt = f"""You are processing data step by step.

Task: {state['task_description']}
Plan: {json.dumps(state['context'].get('plan', {}), indent=2)}
Iteration: {state['iteration']}
Data loaded: {state['context'].get('data_loaded', False)}

Choose ONE action:

1. SEARCH_FILES: Find data files
   Example: {{"action": "SEARCH_FILES", "pattern": "*.csv"}}

2. READ_FILE: Read data file
   Example: {{"action": "READ_FILE", "file_path": "data/sales.csv"}}

3. RUN_PYTHON: Execute Python code for analysis
   Example: {{"action": "RUN_PYTHON", "code": "import pandas as pd; df = pd.read_csv('data.csv'); print(df.describe())"}}

4. WRITE_FILE: Save results
   Example: {{"action": "WRITE_FILE", "file_path": "results/analysis.txt", "content": "..."}}

5. COMPLETE: Analysis is complete
   Example: {{"action": "COMPLETE", "summary": "Analysis results..."}}

Respond with ONLY JSON.
"""

            messages = [
                {"role": "system", "content": "You are a data analyst. Respond with only JSON."},
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

                # Update context
                if action.get("action") == "READ_FILE" and action_result.get("success"):
                    state["context"]["data_loaded"] = True

                # Check completion
                if action.get("action") == "COMPLETE":
                    state["task_status"] = TaskStatus.COMPLETED.value
                    state["task_result"] = action.get("summary", "Data task completed")
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
        """Execute data action"""
        action_type = action.get("action")

        try:
            if action_type == "SEARCH_FILES":
                pattern = action.get("pattern", "*.csv")
                result = await self.fs_tools.search_files(pattern)
                return {"success": result.success, "files": result.output, "error": result.error}

            elif action_type == "READ_FILE":
                file_path = action.get("file_path")
                result = await self.fs_tools.read_file(file_path, max_size_mb=50)  # Larger for data
                return {"success": result.success, "content": result.output, "error": result.error}

            elif action_type == "RUN_PYTHON":
                code = action.get("code")
                result = await self.process_tools.execute_python(code, timeout=120)
                return {"success": result.success, "output": result.output, "error": result.error}

            elif action_type == "WRITE_FILE":
                file_path = action.get("file_path")
                content = action.get("content")
                result = await self.fs_tools.write_file(file_path, content)
                return {"success": result.success, "message": result.output, "error": result.error}

            elif action_type == "COMPLETE":
                return {"success": True, "message": "Data task complete"}

            else:
                return {"success": False, "error": f"Unknown action: {action_type}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def reflect_node(self, state: AgenticState) -> AgenticState:
        """Reflect on data task progress"""
        logger.info(f"🤔 Reflecting on data task (iteration {state['iteration']})")

        try:
            if state.get("task_status") == TaskStatus.COMPLETED.value:
                state["should_continue"] = False
                return state

            if state["iteration"] >= state["max_iterations"]:
                state["should_continue"] = False
                state["task_status"] = TaskStatus.FAILED.value
                state["task_error"] = "Max iterations reached"
                return state

            state["should_continue"] = True
            return state

        except Exception as e:
            logger.error(f"Reflection error: {e}")
            state = add_error(state, f"Reflection failed: {e}")
            state["should_continue"] = False
            return state
