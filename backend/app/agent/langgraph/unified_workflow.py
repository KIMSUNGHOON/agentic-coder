"""Unified LangGraph Workflow - Production Implementation with Supervisor

This is the EXECUTABLE workflow that integrates:
- Supervisor-Led Dynamic Workflow (DeepSeek-R1 reasoning)
- Dynamic DAG construction based on task complexity
- Real LLM-powered code generation and review
- Quality gates and refinement cycles
- Human approval
- Debug logging

CRITICAL: This workflow performs REAL operations, not simulations.
"""

import logging
from typing import AsyncGenerator, Dict, Literal
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.langgraph.schemas.state import QualityGateState, create_initial_state, DebugLog
from app.agent.langgraph.tools.context_manager import ContextManager
from app.agent.langgraph.tools.filesystem_tools import FILESYSTEM_TOOLS

# Import Supervisor-Led Dynamic Workflow components
from core.supervisor import SupervisorAgent
from core.workflow import DynamicWorkflowBuilder, create_workflow_from_supervisor_analysis
from core.agent_registry import get_registry

logger = logging.getLogger(__name__)


class UnifiedLangGraphWorkflow:
    """Unified production workflow with REAL execution

    This class implements the complete workflow including:
    - Supervisor-led task analysis (DeepSeek-R1)
    - Dynamic workflow construction based on task complexity
    - Real LLM-powered code generation and review
    - Quality gates and refinement cycles
    - Human approval
    - Debug logging
    """

    def __init__(self):
        """Initialize unified workflow"""
        self.supervisor = SupervisorAgent()
        self.workflow_builder = DynamicWorkflowBuilder()
        self.agent_registry = get_registry()
        self.tools = FILESYSTEM_TOOLS
        self.graph = None  # Will be built dynamically per request
        logger.info("✅ UnifiedLangGraphWorkflow initialized with Supervisor")


    async def execute(
        self,
        user_request: str,
        workspace_root: str,
        task_type: str = "general",
        enable_debug: bool = True,
        system_prompt: str = ""
    ) -> AsyncGenerator[Dict, None]:
        """Execute Supervisor-led dynamic workflow with REAL operations

        CRITICAL: This method performs ACTUAL file operations.

        Flow:
        1. Supervisor analyzes request (DeepSeek-R1 reasoning with streaming)
        2. Dynamic workflow graph is constructed
        3. Workflow executes with real LLM calls
        4. Results are streamed back to frontend

        Args:
            user_request: User's request
            workspace_root: Workspace root directory
            task_type: Type of task (optional, Supervisor will determine)
            enable_debug: Enable debug logging
            system_prompt: Optional custom system prompt (for future use)
            enable_debug: Whether to enable debug logging

        Yields:
            State updates from each node, including Supervisor analysis and thinking stream
        """
        logger.info(f"🚀 Starting Supervisor-Led Workflow Execution")
        logger.info(f"   Request: {user_request[:100]}")
        logger.info(f"   Workspace: {workspace_root}")

        try:
            # STEP 1: Supervisor analyzes request using DeepSeek-R1 with streaming
            logger.info("🧠 Step 1/3: Supervisor Analysis (DeepSeek-R1 with streaming)")

            supervisor_analysis = None
            thinking_blocks = []

            # Stream supervisor analysis with <think> blocks
            async for update in self.supervisor.analyze_request_async(user_request):
                if update["type"] == "thinking":
                    thinking_blocks.append(update["content"])

                    # Yield thinking update for real-time UI
                    yield {
                        "node": "supervisor",
                        "updates": {
                            "current_thinking": update["content"],
                            "thinking_stream": thinking_blocks.copy(),
                            "thinking_complete": update.get("is_complete", False),
                        },
                        "status": "thinking",
                        "timestamp": datetime.utcnow().isoformat()
                    }

                elif update["type"] == "analysis":
                    supervisor_analysis = update["content"]

            # Fallback to sync if async failed
            if not supervisor_analysis:
                supervisor_analysis = self.supervisor.analyze_request(user_request)

            # Yield complete Supervisor analysis to frontend
            yield {
                "node": "supervisor",
                "updates": {
                    "supervisor_analysis": supervisor_analysis,
                    "current_thinking": supervisor_analysis.get("reasoning", ""),
                    "thinking_stream": thinking_blocks,
                    "task_complexity": supervisor_analysis.get("complexity", "moderate"),
                    "workflow_strategy": supervisor_analysis.get("workflow_strategy", "parallel_gates"),
                    "required_agents": supervisor_analysis.get("required_agents", []),
                    "api_used": supervisor_analysis.get("api_used", False),
                },
                "status": "running",
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"✅ Supervisor Analysis Complete:")
            logger.info(f"   Complexity: {supervisor_analysis['complexity']}")
            logger.info(f"   Task Type: {supervisor_analysis['task_type']}")
            logger.info(f"   Strategy: {supervisor_analysis['workflow_strategy']}")
            logger.info(f"   Required Agents: {supervisor_analysis['required_agents']}")

            # STEP 2: Build dynamic workflow graph
            logger.info("🏗️  Step 2/3: Building Dynamic Workflow")
            workflow_graph = create_workflow_from_supervisor_analysis(supervisor_analysis)

            # Yield workflow graph info to frontend
            yield {
                "node": "workflow_builder",
                "updates": {
                    "workflow_graph": {
                        "strategy": supervisor_analysis["workflow_strategy"],
                        "nodes": supervisor_analysis["required_agents"],
                        "max_iterations": supervisor_analysis["max_iterations"]
                    }
                },
                "status": "running",
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"✅ Dynamic Workflow Built")
            logger.info(f"   Strategy: {supervisor_analysis['workflow_strategy']}")
            logger.info(f"   Nodes: {len(supervisor_analysis['required_agents'])}")

            # STEP 3: Execute the dynamically built workflow
            logger.info("⚙️  Step 3/3: Executing Workflow")

            # Create initial state
            initial_state = create_initial_state(
                user_request=user_request,
                workspace_root=workspace_root,
                task_type=supervisor_analysis["task_type"],  # type: ignore
                enable_debug=enable_debug
            )

            # Add supervisor analysis to state
            initial_state["supervisor_analysis"] = supervisor_analysis
            initial_state["max_iterations"] = supervisor_analysis["max_iterations"]
            initial_state["thinking_stream"] = thinking_blocks
            initial_state["task_complexity"] = supervisor_analysis.get("complexity", "moderate")
            initial_state["workflow_strategy"] = supervisor_analysis.get("workflow_strategy", "parallel_gates")
            initial_state["required_agents"] = supervisor_analysis.get("required_agents", [])

            # Execute graph with streaming
            config = {
                "configurable": {"thread_id": f"unified_{datetime.utcnow().timestamp()}"},
                "recursion_limit": supervisor_analysis["max_iterations"] * 10  # Dynamic limit
            }

            async for event in workflow_graph.astream(initial_state, config):
                for node_name, node_output in event.items():
                    logger.info(f"📍 Node '{node_name}' completed")

                    # Yield update with debug logs
                    yield {
                        "node": node_name,
                        "updates": node_output,
                        "status": "running",
                        "timestamp": datetime.utcnow().isoformat()
                    }

            # Get final state
            final_state = await workflow_graph.aget_state(config)

            yield {
                "node": "END",
                "updates": final_state.values,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info("✅ Supervisor-Led Workflow Execution Completed")

        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}", exc_info=True)
            yield {
                "node": "ERROR",
                "updates": {"error": str(e), "traceback": str(e)},
                "status": "error",
                "timestamp": datetime.utcnow().isoformat()
            }


# Global unified workflow instance
unified_workflow = UnifiedLangGraphWorkflow()
