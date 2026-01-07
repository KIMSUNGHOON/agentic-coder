"""Dynamic LangGraph Workflow - Supervisor-Led Dynamic Agent Spawning

This workflow implements TRULY DYNAMIC agent spawning based on Supervisor analysis:
- Supervisor analyzes request and determines required_agents
- StateGraph is constructed dynamically with ONLY required agents
- No static pipeline - each request gets a custom workflow

Key difference from static enhanced_workflow:
- enhanced_workflow: Always runs ALL agents (Supervisor→Architect→Coder→All Quality Gates→HITL)
- dynamic_workflow: Only spawns agents that Supervisor determines are needed

Example:
- Simple Q&A: Supervisor only (no other agents)
- Simple code: Supervisor→Architect→Coder→Review (no security/QA gates)
- Critical code: Full pipeline with all gates and human approval

CRITICAL: This workflow performs REAL file operations.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Dict, List, Any, Optional, Callable
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.langgraph.schemas.state import QualityGateState, create_initial_state

# Import nodes - but only use them dynamically
from app.agent.langgraph.nodes.architect import architect_node
from app.agent.langgraph.nodes.coder import coder_node
from app.agent.langgraph.nodes.reviewer import reviewer_node
from app.agent.langgraph.nodes.refiner import refiner_node
from app.agent.langgraph.nodes.security_gate import security_gate_node
from app.agent.langgraph.nodes.qa_gate import qa_gate_node
from app.agent.langgraph.nodes.aggregator import quality_aggregator_node
from app.agent.langgraph.nodes.persistence import persistence_node

# Import Supervisor
from core.supervisor import SupervisorAgent, ResponseType, AgentCapability, TaskComplexity

# Import HITL
from app.hitl import get_hitl_manager
from app.hitl.models import HITLCheckpointType, HITLRequest as HITLRequestModel, HITLStatus

logger = logging.getLogger(__name__)


# Agent display names and descriptions
AGENT_INFO = {
    "supervisor": {
        "title": "🧠 Supervisor",
        "description": "Task Analysis & Routing",
        "icon": "brain"
    },
    "architect": {
        "title": "🏗️ Architect",
        "description": "Project Structure Design",
        "icon": "building"
    },
    "coder": {
        "title": "💻 Coder",
        "description": "Code Implementation",
        "icon": "code"
    },
    "reviewer": {
        "title": "👀 Reviewer",
        "description": "Code Quality Review",
        "icon": "eye"
    },
    "qa_gate": {
        "title": "🧪 QA Tester",
        "description": "Test Generation & Execution",
        "icon": "flask"
    },
    "security_gate": {
        "title": "🔒 Security",
        "description": "Security Analysis",
        "icon": "shield"
    },
    "refiner": {
        "title": "🔧 Refiner",
        "description": "Code Refinement",
        "icon": "wrench"
    },
    "aggregator": {
        "title": "📊 Aggregator",
        "description": "Results Aggregation",
        "icon": "chart"
    },
    "hitl": {
        "title": "👤 Human Review",
        "description": "Awaiting Your Approval",
        "icon": "user"
    },
    "persistence": {
        "title": "💾 Persistence",
        "description": "Saving Files",
        "icon": "save"
    }
}

# Map capability names to actual node functions
CAPABILITY_TO_NODE = {
    AgentCapability.IMPLEMENTATION: ("coder", coder_node),
    AgentCapability.REVIEW: ("reviewer", reviewer_node),
    AgentCapability.SECURITY: ("security_gate", security_gate_node),
    AgentCapability.TESTING: ("qa_gate", qa_gate_node),
    AgentCapability.REFINEMENT: ("refiner", refiner_node),
}


class DynamicStateGraphBuilder:
    """Builds LangGraph StateGraph dynamically based on required agents

    This builder creates workflow graphs that ONLY include the agents
    specified by the Supervisor's analysis.
    """

    def __init__(self):
        self.memory = MemorySaver()
        logger.info("🏗️ DynamicStateGraphBuilder initialized")

    def build_graph(
        self,
        required_agents: List[str],
        workflow_strategy: str,
        complexity: str,
        requires_approval: bool = False
    ) -> StateGraph:
        """Build a StateGraph with only the required agents

        Args:
            required_agents: List of capability strings from Supervisor
            workflow_strategy: Strategy (linear, parallel_gates, adaptive_loop, staged_approval)
            complexity: Task complexity level
            requires_approval: Whether human approval is required

        Returns:
            Compiled StateGraph ready for execution
        """
        logger.info(f"🎯 Building dynamic StateGraph")
        logger.info(f"   Strategy: {workflow_strategy}")
        logger.info(f"   Required Agents: {required_agents}")
        logger.info(f"   Complexity: {complexity}")
        logger.info(f"   Human Approval: {requires_approval}")

        workflow = StateGraph(QualityGateState)

        # Core nodes that are always included for code generation
        nodes_to_add = set()

        # Determine which nodes to add based on required_agents
        if AgentCapability.IMPLEMENTATION in required_agents:
            nodes_to_add.add("coder")

        if AgentCapability.REVIEW in required_agents:
            nodes_to_add.add("reviewer")

        if AgentCapability.SECURITY in required_agents:
            nodes_to_add.add("security_gate")

        if AgentCapability.TESTING in required_agents:
            nodes_to_add.add("qa_gate")

        if AgentCapability.REFINEMENT in required_agents:
            nodes_to_add.add("refiner")

        # If we have any quality gates, we need aggregator
        has_quality_gates = bool(nodes_to_add & {"reviewer", "security_gate", "qa_gate"})
        if has_quality_gates:
            nodes_to_add.add("aggregator")

        # Always add persistence if we're generating code
        if "coder" in nodes_to_add:
            nodes_to_add.add("persistence")

        logger.info(f"   Final nodes: {nodes_to_add}")

        # Build graph based on strategy
        if workflow_strategy == "linear":
            return self._build_linear_graph(workflow, nodes_to_add, requires_approval)
        elif workflow_strategy == "parallel_gates":
            return self._build_parallel_gates_graph(workflow, nodes_to_add, requires_approval)
        elif workflow_strategy == "adaptive_loop":
            return self._build_adaptive_loop_graph(workflow, nodes_to_add, requires_approval)
        elif workflow_strategy == "staged_approval":
            return self._build_staged_approval_graph(workflow, nodes_to_add, requires_approval)
        else:
            # Default to parallel_gates
            return self._build_parallel_gates_graph(workflow, nodes_to_add, requires_approval)

    def _build_linear_graph(
        self,
        workflow: StateGraph,
        nodes: set,
        requires_approval: bool
    ) -> StateGraph:
        """Build simple linear workflow

        Flow: Coder → [Reviewer] → Persistence → END
        """
        logger.info("📏 Building LINEAR workflow")

        if "coder" in nodes:
            workflow.add_node("coder", coder_node)

        if "reviewer" in nodes:
            workflow.add_node("reviewer", reviewer_node)

        if "persistence" in nodes:
            workflow.add_node("persistence", persistence_node)

        # Set edges
        if "coder" in nodes:
            workflow.set_entry_point("coder")

            if "reviewer" in nodes:
                workflow.add_edge("coder", "reviewer")
                if "persistence" in nodes:
                    workflow.add_edge("reviewer", "persistence")
                    workflow.add_edge("persistence", END)
                else:
                    workflow.add_edge("reviewer", END)
            elif "persistence" in nodes:
                workflow.add_edge("coder", "persistence")
                workflow.add_edge("persistence", END)
            else:
                workflow.add_edge("coder", END)

        return workflow.compile(checkpointer=self.memory)

    def _build_parallel_gates_graph(
        self,
        workflow: StateGraph,
        nodes: set,
        requires_approval: bool
    ) -> StateGraph:
        """Build parallel quality gates workflow

        Flow: Coder → [Security || QA || Review] → Aggregator → [Refiner → loop] or END
        """
        logger.info("🔀 Building PARALLEL GATES workflow")

        # Add only the required nodes
        if "coder" in nodes:
            workflow.add_node("coder", coder_node)

        gates = []
        if "security_gate" in nodes:
            workflow.add_node("security_gate", security_gate_node)
            gates.append("security_gate")

        if "qa_gate" in nodes:
            workflow.add_node("qa_gate", qa_gate_node)
            gates.append("qa_gate")

        if "reviewer" in nodes:
            workflow.add_node("reviewer", reviewer_node)
            gates.append("reviewer")

        if "aggregator" in nodes:
            workflow.add_node("aggregator", quality_aggregator_node)

        if "refiner" in nodes:
            workflow.add_node("refiner", refiner_node)

        if "persistence" in nodes:
            workflow.add_node("persistence", persistence_node)

        # Set entry point
        if "coder" in nodes:
            workflow.set_entry_point("coder")

            # Connect coder to all gates in parallel
            for gate in gates:
                workflow.add_edge("coder", gate)

            # Connect all gates to aggregator
            if gates and "aggregator" in nodes:
                for gate in gates:
                    workflow.add_edge(gate, "aggregator")

                # Aggregator decides: END or refine
                if "refiner" in nodes:
                    workflow.add_conditional_edges(
                        "aggregator",
                        self._should_refine,
                        {
                            "approve": "persistence" if "persistence" in nodes else END,
                            "refine": "refiner",
                            "max_iterations": "persistence" if "persistence" in nodes else END,
                        }
                    )
                    workflow.add_edge("refiner", "coder")
                else:
                    workflow.add_edge("aggregator", "persistence" if "persistence" in nodes else END)
            elif not gates:
                # No gates, go directly to persistence
                workflow.add_edge("coder", "persistence" if "persistence" in nodes else END)

            if "persistence" in nodes:
                workflow.add_edge("persistence", END)

        return workflow.compile(checkpointer=self.memory)

    def _build_adaptive_loop_graph(
        self,
        workflow: StateGraph,
        nodes: set,
        requires_approval: bool
    ) -> StateGraph:
        """Build adaptive refinement loop workflow

        Flow: Coder → Review → [RCA → Refiner → loop] OR [Done]
        """
        logger.info("🔄 Building ADAPTIVE LOOP workflow")

        # Add nodes
        if "coder" in nodes:
            workflow.add_node("coder", coder_node)

        if "reviewer" in nodes:
            workflow.add_node("reviewer", reviewer_node)

        if "security_gate" in nodes:
            workflow.add_node("security_gate", security_gate_node)

        if "qa_gate" in nodes:
            workflow.add_node("qa_gate", qa_gate_node)

        if "aggregator" in nodes:
            workflow.add_node("aggregator", quality_aggregator_node)

        if "refiner" in nodes:
            workflow.add_node("refiner", refiner_node)

        if "persistence" in nodes:
            workflow.add_node("persistence", persistence_node)

        # Set entry point
        if "coder" in nodes:
            workflow.set_entry_point("coder")

            # Connect based on what's available
            if "security_gate" in nodes:
                workflow.add_edge("coder", "security_gate")
                if "reviewer" in nodes:
                    workflow.add_edge("security_gate", "reviewer")
                elif "aggregator" in nodes:
                    workflow.add_edge("security_gate", "aggregator")
            elif "reviewer" in nodes:
                workflow.add_edge("coder", "reviewer")

            if "reviewer" in nodes:
                if "qa_gate" in nodes:
                    workflow.add_edge("reviewer", "qa_gate")
                    workflow.add_edge("qa_gate", "aggregator" if "aggregator" in nodes else END)
                elif "aggregator" in nodes:
                    workflow.add_edge("reviewer", "aggregator")

            if "aggregator" in nodes:
                if "refiner" in nodes:
                    workflow.add_conditional_edges(
                        "aggregator",
                        self._should_refine,
                        {
                            "approve": "persistence" if "persistence" in nodes else END,
                            "refine": "refiner",
                            "max_iterations": "persistence" if "persistence" in nodes else END,
                        }
                    )
                    workflow.add_edge("refiner", "coder")
                else:
                    workflow.add_edge("aggregator", "persistence" if "persistence" in nodes else END)

            if "persistence" in nodes:
                workflow.add_edge("persistence", END)

        return workflow.compile(checkpointer=self.memory)

    def _build_staged_approval_graph(
        self,
        workflow: StateGraph,
        nodes: set,
        requires_approval: bool
    ) -> StateGraph:
        """Build workflow with staged human approval

        Flow: All gates → Human Approval → Persistence → Done
        """
        logger.info("👤 Building STAGED APPROVAL workflow")

        # For staged approval, we use the parallel gates structure
        # but the HITL is handled externally in the execute method
        return self._build_parallel_gates_graph(workflow, nodes, requires_approval)

    def _should_refine(self, state: QualityGateState) -> str:
        """Decide if refinement is needed"""
        review_approved = state.get("review_approved", False)
        refinement_iteration = state.get("refinement_iteration", 0)
        max_iterations = state.get("max_iterations", 5)

        if refinement_iteration >= max_iterations:
            logger.warning(f"⚠️ Max iterations ({max_iterations}) reached")
            return "max_iterations"

        if review_approved:
            logger.info("✅ All gates passed - approving")
            return "approve"

        logger.info(f"🔄 Refinement needed (iteration {refinement_iteration}/{max_iterations})")
        return "refine"


class DynamicWorkflow:
    """Dynamic Workflow with Supervisor-Led Agent Spawning

    This workflow:
    1. Uses Supervisor to analyze the request
    2. Builds StateGraph dynamically based on required_agents
    3. Only spawns agents that are actually needed
    4. Streams results with progress tracking
    """

    def __init__(self):
        """Initialize dynamic workflow"""
        self.supervisor = SupervisorAgent(use_api=True)
        self.hitl_manager = get_hitl_manager()
        self.graph_builder = DynamicStateGraphBuilder()
        logger.info("✅ DynamicWorkflow initialized")

    def _get_agent_info(self, agent_name: str) -> Dict[str, str]:
        """Get display info for an agent"""
        return AGENT_INFO.get(agent_name, {
            "title": f"🤖 {agent_name.title()}",
            "description": "Processing...",
            "icon": "robot"
        })

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think></think> tags from text

        For models that don't use think tags (GPT-OSS, Qwen),
        we strip any accidental <think> content from output.

        Args:
            text: Text that may contain think tags

        Returns:
            Clean text without think tags
        """
        import re
        if not text:
            return ""

        # Remove <think>...</think> blocks entirely
        clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Clean up any extra whitespace
        clean = re.sub(r'\n\s*\n\s*\n', '\n\n', clean)
        return clean.strip()

    def _create_update(
        self,
        node: str,
        status: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create standardized update for frontend"""
        agent_info = self._get_agent_info(node)

        return {
            "node": node,
            "status": status,
            "agent_title": agent_info["title"],
            "agent_description": agent_info["description"],
            "agent_icon": agent_info["icon"],
            "updates": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def execute(
        self,
        user_request: str,
        workspace_root: str,
        task_type: str = "general",
        enable_debug: bool = True,
        system_prompt: str = "",
        conversation_history: List[Dict[str, str]] = None
    ) -> AsyncGenerator[Dict, None]:
        """Execute dynamic workflow with streaming

        This method:
        1. Supervisor analyzes the request
        2. Based on required_agents, builds a custom StateGraph
        3. Executes only the necessary agents
        4. Streams updates to frontend

        Args:
            user_request: User's coding request
            workspace_root: Base directory for file operations
            task_type: Type of task (optional, Supervisor will determine)
            enable_debug: Enable debug logging
            system_prompt: Optional custom system prompt
            conversation_history: Previous conversation for context continuity
        """
        conversation_history = conversation_history or []
        workflow_id = f"dynamic_{datetime.utcnow().timestamp()}"
        start_time = time.time()
        agent_times: Dict[str, float] = {}
        completed_agents: List[str] = []

        logger.info(f"🚀 Starting Dynamic Workflow: {workflow_id}")
        logger.info(f"   Request: {user_request[:100]}...")

        try:
            # ==================== PHASE 1: SUPERVISOR ANALYSIS ====================
            yield self._create_update("supervisor", "starting", {
                "message": "Analyzing your request...",
                "workflow_id": workflow_id,
            })

            supervisor_start = time.time()
            supervisor_analysis = None
            thinking_blocks = []

            # Build context from conversation history
            context = None
            if conversation_history:
                context = {
                    "conversation_history": conversation_history,
                    "turn_count": len(conversation_history),
                    "system_prompt": system_prompt if system_prompt else None,
                }
                logger.info(f"📝 Conversation context: {len(conversation_history)} previous messages")

            # Build enhanced request with conversation context
            enhanced_request = user_request
            if conversation_history:
                # Add recent conversation context to the request for continuity
                recent_context = conversation_history[-6:]  # Last 3 exchanges (user + assistant)
                context_summary = "\n".join([
                    f"{'사용자' if msg['role'] == 'user' else 'AI'}: {msg['content'][:200]}..."
                    if len(msg['content']) > 200 else f"{'사용자' if msg['role'] == 'user' else 'AI'}: {msg['content']}"
                    for msg in recent_context
                ])
                enhanced_request = f"""이전 대화 내용:
{context_summary}

현재 요청:
{user_request}"""

            # Stream supervisor thinking
            async for update in self.supervisor.analyze_request_async(enhanced_request, context):
                if update["type"] == "thinking":
                    thinking_blocks.append(update["content"])
                    yield self._create_update("supervisor", "thinking", {
                        "current_thinking": update["content"][:200] + "..." if len(update["content"]) > 200 else update["content"],
                    })
                elif update["type"] == "analysis":
                    supervisor_analysis = update["content"]

            if not supervisor_analysis:
                supervisor_analysis = self.supervisor.analyze_request(enhanced_request, context)

            agent_times["supervisor"] = time.time() - supervisor_start
            completed_agents.append("supervisor")

            # Extract key analysis results
            response_type = supervisor_analysis.get("response_type", ResponseType.CODE_GENERATION)
            complexity = supervisor_analysis.get("complexity", TaskComplexity.MODERATE)
            required_agents = supervisor_analysis.get("required_agents", [AgentCapability.IMPLEMENTATION])
            workflow_strategy = supervisor_analysis.get("workflow_strategy", "parallel_gates")
            requires_approval = supervisor_analysis.get("requires_human_approval", False)

            # Log dynamic routing decision
            logger.info(f"📊 Supervisor Analysis Complete:")
            logger.info(f"   Response Type: {response_type}")
            logger.info(f"   Complexity: {complexity}")
            logger.info(f"   Required Agents: {required_agents}")
            logger.info(f"   Strategy: {workflow_strategy}")
            logger.info(f"   Human Approval: {requires_approval}")

            yield self._create_update("supervisor", "completed", {
                "supervisor_analysis": supervisor_analysis,
                "response_type": response_type,
                "task_complexity": complexity,
                "required_agents": required_agents,
                "workflow_strategy": workflow_strategy,
                "execution_time": agent_times["supervisor"],
                "streaming_content": f"분석 완료\n• 응답 유형: {response_type}\n• 복잡도: {complexity}\n• 필요 에이전트: {len(required_agents)}개\n• 전략: {workflow_strategy}",
            })

            # ==================== ROUTING: Quick Q&A vs Full Pipeline ====================
            if response_type == ResponseType.QUICK_QA:
                # Quick Q&A - Supervisor responds directly, no other agents
                logger.info("🎯 Quick Q&A mode - Supervisor responds directly")

                reasoning = supervisor_analysis.get("reasoning", "")
                # Clean any <think> tags from reasoning (shouldn't be there for GPT-OSS)
                reasoning = self._strip_think_tags(reasoning)

                yield self._create_update("workflow", "completed", {
                    "workflow_id": workflow_id,
                    "workflow_type": "quick_qa",
                    "total_execution_time": time.time() - start_time,
                    "streaming_content": f"## Quick Q&A 응답\n\n{reasoning}\n\n*Quick Q&A 모드로 응답했습니다.*",
                    "message": "Quick Q&A completed",
                    "is_final": True,
                })
                return

            elif response_type == ResponseType.PLANNING:
                # Planning mode - detailed analysis without code generation
                logger.info("🎯 Planning mode - Supervisor provides detailed plan")

                reasoning = supervisor_analysis.get("reasoning", "")
                # Clean any <think> tags from reasoning (shouldn't be there for GPT-OSS)
                reasoning = self._strip_think_tags(reasoning)

                # Save plan as markdown file
                plan_filename = None
                plan_filepath = None
                try:
                    import os
                    from datetime import datetime as dt
                    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
                    plan_filename = f"plan_{timestamp}.md"
                    plan_filepath = os.path.join(workspace_root, plan_filename)

                    # Create workspace if it doesn't exist
                    os.makedirs(workspace_root, exist_ok=True)

                    # Format the plan as markdown
                    plan_content = f"""# 개발 계획서
생성일: {dt.now().strftime("%Y-%m-%d %H:%M:%S")}

## 요청 내용
{user_request}

## 분석 결과

{reasoning}

---
*이 파일은 AI 코드 에이전트에 의해 자동 생성되었습니다.*
"""
                    with open(plan_filepath, 'w', encoding='utf-8') as f:
                        f.write(plan_content)

                    logger.info(f"📄 Saved plan to: {plan_filepath}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to save plan file: {e}")
                    plan_filename = None
                    plan_filepath = None

                yield self._create_update("workflow", "completed", {
                    "workflow_id": workflow_id,
                    "workflow_type": "planning",
                    "total_execution_time": time.time() - start_time,
                    "streaming_content": f"## 계획/설계 분석\n\n{reasoning}\n\n" + (f"📄 계획서가 저장되었습니다: `{plan_filename}`\n\n" if plan_filename else "") + "*계획 모드로 응답했습니다. 코드 생성이 필요하면 명시적으로 요청해주세요.*",
                    "message": "Planning completed",
                    "is_final": True,
                    "plan_file": plan_filename,
                    "plan_filepath": plan_filepath,
                })
                return

            # ==================== PHASE 2: ARCHITECT (for code generation) ====================
            # Only run architect if we're doing code generation
            if response_type in [ResponseType.CODE_GENERATION, ResponseType.DEBUGGING, ResponseType.CODE_REVIEW]:
                yield self._create_update("architect", "starting", {
                    "message": "Designing project architecture...",
                })

                architect_start = time.time()
                state = create_initial_state(
                    user_request=user_request,
                    workspace_root=workspace_root,
                    task_type=supervisor_analysis.get("task_type", "implementation"),
                    enable_debug=enable_debug
                )
                state["supervisor_analysis"] = supervisor_analysis
                state["max_iterations"] = supervisor_analysis.get("max_iterations", 5)

                architect_result = architect_node(state)
                agent_times["architect"] = time.time() - architect_start
                completed_agents.append("architect")
                state.update(architect_result)

                architecture = architect_result.get("architecture_design", {})
                files_to_create = architect_result.get("files_to_create", [])

                # Generate project directory
                import re
                import os
                project_name = self._generate_project_name(user_request, supervisor_analysis, architecture)
                project_name = re.sub(r'[^\w\-]', '-', project_name.lower()).strip('-')
                project_name = re.sub(r'-+', '-', project_name)
                if not project_name or len(project_name) < 2:
                    project_name = f"project_{int(time.time())}"

                project_dir = os.path.join(workspace_root, project_name)
                suffix = 1
                while os.path.exists(project_dir):
                    project_name = f"{project_name}_{suffix}"
                    project_dir = os.path.join(workspace_root, project_name)
                    suffix += 1
                    if suffix > 100:
                        project_name = f"project_{int(time.time())}"
                        project_dir = os.path.join(workspace_root, project_name)
                        break

                os.makedirs(project_dir, exist_ok=True)
                logger.info(f"📁 Created project directory: {project_dir}")

                state["workspace_root"] = project_dir

                yield self._create_update("workflow", "project_info", {
                    "project_name": project_name,
                    "project_dir": project_dir,
                    "streaming_content": f"📁 Project: {project_name}\n📂 Location: {project_dir}",
                })

                yield self._create_update("architect", "completed", {
                    "architecture_design": architecture,
                    "files_to_create": files_to_create,
                    "execution_time": agent_times["architect"],
                    "streaming_content": f"프로젝트 설계 완료\n• 파일 수: {len(files_to_create)}개",
                })

                # ==================== PHASE 3: DYNAMIC GRAPH EXECUTION ====================
                # Build StateGraph with ONLY required agents
                logger.info(f"🏗️ Building dynamic StateGraph with agents: {required_agents}")

                yield self._create_update("workflow", "building_graph", {
                    "message": f"Building dynamic workflow with {len(required_agents)} agents...",
                    "required_agents": required_agents,
                    "workflow_strategy": workflow_strategy,
                })

                # Execute agents based on requirements
                # We'll do this manually instead of using compiled graph for better streaming control

                # CODER
                if AgentCapability.IMPLEMENTATION in required_agents:
                    yield self._create_update("coder", "starting", {
                        "message": f"Generating {len(files_to_create)} files...",
                    })

                    coder_start = time.time()
                    yield self._create_update("coder", "streaming", {
                        "message": "Generating code...",
                        "streaming_content": f"$ generating code...\n> workspace: {project_dir}\n> files: {len(files_to_create)} planned",
                    })

                    coder_result = coder_node(state)
                    agent_times["coder"] = time.time() - coder_start
                    completed_agents.append("coder")
                    state.update(coder_result)

                    artifacts = coder_result.get("coder_output", {}).get("artifacts", [])

                    yield self._create_update("coder", "completed", {
                        "coder_output": coder_result.get("coder_output"),
                        "artifacts": artifacts,
                        "execution_time": agent_times["coder"],
                        "streaming_content": f"✅ Generated {len(artifacts)} files",
                    })

                # QUALITY GATES (only if required)
                gates_to_run = []
                if AgentCapability.REVIEW in required_agents:
                    gates_to_run.append(("reviewer", reviewer_node))
                if AgentCapability.SECURITY in required_agents:
                    gates_to_run.append(("security_gate", security_gate_node))
                if AgentCapability.TESTING in required_agents:
                    gates_to_run.append(("qa_gate", qa_gate_node))

                if gates_to_run:
                    logger.info(f"🔍 Running {len(gates_to_run)} quality gates")

                    # Run gates in parallel
                    for gate_name, _ in gates_to_run:
                        yield self._create_update(gate_name, "starting", {
                            "message": f"Running {self._get_agent_info(gate_name)['title']}...",
                        })

                    async def run_gate(gate_name: str, gate_func) -> tuple:
                        gate_start = time.time()
                        result = await asyncio.to_thread(gate_func, state)
                        return gate_name, result, time.time() - gate_start

                    gate_tasks = [run_gate(name, func) for name, func in gates_to_run]
                    gate_results = await asyncio.gather(*gate_tasks)

                    for gate_name, gate_result, gate_time in gate_results:
                        agent_times[gate_name] = gate_time
                        completed_agents.append(gate_name)
                        state.update(gate_result)

                        yield self._create_update(gate_name, "completed", {
                            "result": gate_result,
                            "execution_time": gate_time,
                            "streaming_content": f"✅ {gate_name} 완료",
                        })

                    # AGGREGATION (if we have gates)
                    yield self._create_update("aggregator", "starting", {
                        "message": "Aggregating results...",
                    })

                    agg_start = time.time()
                    agg_result = quality_aggregator_node(state)
                    agent_times["aggregator"] = time.time() - agg_start
                    completed_agents.append("aggregator")
                    state.update(agg_result)

                    all_passed = (
                        state.get("security_passed", True) and
                        state.get("qa_passed", True) and
                        state.get("review_approved", True)
                    )

                    yield self._create_update("aggregator", "completed", {
                        "all_gates_passed": all_passed,
                        "execution_time": agent_times["aggregator"],
                        "streaming_content": f"품질 검사 결과: {'✅ 통과' if all_passed else '⚠️ 이슈 발견'}",
                    })

                    # REFINEMENT LOOP (if needed and enabled)
                    if AgentCapability.REFINEMENT in required_agents and not all_passed:
                        max_iterations = supervisor_analysis.get("max_iterations", 5)
                        iteration = 0

                        while not all_passed and iteration < max_iterations:
                            iteration += 1
                            logger.info(f"🔄 Refinement iteration {iteration}/{max_iterations}")

                            yield self._create_update("refiner", "starting", {
                                "message": f"Refining code (iteration {iteration}/{max_iterations})...",
                            })

                            state["refinement_iteration"] = iteration
                            refiner_start = time.time()
                            refiner_result = refiner_node(state)
                            agent_times["refiner"] = agent_times.get("refiner", 0) + (time.time() - refiner_start)
                            state.update(refiner_result)

                            yield self._create_update("refiner", "completed", {
                                "iteration": iteration,
                                "execution_time": time.time() - refiner_start,
                            })

                            # Re-run quality gates
                            for gate_name, gate_func in gates_to_run:
                                gate_result = gate_func(state)
                                state.update(gate_result)

                            agg_result = quality_aggregator_node(state)
                            state.update(agg_result)

                            all_passed = (
                                state.get("security_passed", True) and
                                state.get("qa_passed", True) and
                                state.get("review_approved", True)
                            )

                            if all_passed:
                                break

                        if "refiner" not in completed_agents:
                            completed_agents.append("refiner")

                # PERSISTENCE
                yield self._create_update("persistence", "starting", {
                    "message": "Saving files...",
                })

                # Collect all artifacts
                # FIXED: Remove duplicates by normalized path before setting final_artifacts
                import os
                coder_output = state.get("coder_output", {})
                all_artifacts_raw = coder_output.get("artifacts", [])
                workspace_root = state.get("workspace_root", "")

                # Deduplicate artifacts by normalized absolute path
                seen_paths = set()
                all_artifacts = []
                for artifact in all_artifacts_raw:
                    artifact_filename = artifact.get("filename", "")
                    artifact_file_path = artifact.get("file_path", "")

                    # Normalize path
                    if artifact_file_path and os.path.isabs(artifact_file_path):
                        normalized_path = os.path.normpath(artifact_file_path)
                    elif artifact_filename:
                        normalized_path = os.path.normpath(os.path.join(workspace_root, artifact_filename))
                    else:
                        logger.warning(f"⚠️  Skipping artifact without valid path in final_artifacts")
                        continue

                    # Add only if not seen before
                    if normalized_path not in seen_paths:
                        all_artifacts.append(artifact)
                        seen_paths.add(normalized_path)
                    else:
                        logger.warning(f"⚠️  Removed duplicate from final_artifacts: {artifact_filename}")

                logger.info(f"📁 Final artifacts: {len(all_artifacts_raw)} raw → {len(all_artifacts)} unique")

                state["final_artifacts"] = all_artifacts
                state["workflow_status"] = "completed"

                persist_start = time.time()
                persist_result = persistence_node(state)
                agent_times["persistence"] = time.time() - persist_start
                completed_agents.append("persistence")

                yield self._create_update("persistence", "completed", {
                    "saved_files": all_artifacts,
                    "project_name": project_name,
                    "project_dir": project_dir,
                    "execution_time": agent_times["persistence"],
                    "streaming_content": f"💾 {len(all_artifacts)}개 파일 저장 완료\n📂 {project_dir}",
                })

                # ==================== WORKFLOW COMPLETE ====================
                total_time = time.time() - start_time

                # Build summary with dynamic agent info
                summary = f"✅ Dynamic Workflow Complete in {total_time:.1f}s\n\n"
                summary += f"📊 Workflow Type: {workflow_strategy}\n"
                summary += f"🎯 Agents Spawned: {len(completed_agents)}\n\n"
                summary += "Agent Execution Times:\n"
                for agent in completed_agents:
                    if agent in agent_times:
                        summary += f"  • {self._get_agent_info(agent)['title']}: {agent_times[agent]:.1f}s\n"

                yield self._create_update("workflow", "completed", {
                    "workflow_id": workflow_id,
                    "workflow_type": "dynamic",
                    "total_execution_time": round(total_time, 2),
                    "agent_execution_times": {k: round(v, 2) for k, v in agent_times.items()},
                    "completed_agents": completed_agents,
                    "required_agents": required_agents,
                    "final_artifacts": all_artifacts,
                    "project_name": project_name,
                    "project_dir": project_dir,
                    "streaming_content": summary,
                    "message": f"Workflow completed in {total_time:.1f}s",
                    "is_final": True,
                })

        except Exception as e:
            logger.error(f"❌ Dynamic workflow failed: {e}", exc_info=True)
            yield self._create_update("error", "error", {
                "error": str(e),
                "workflow_id": workflow_id,
                "streaming_content": f"❌ Error: {str(e)}",
            })

    def _generate_project_name(
        self,
        user_request: str,
        supervisor_analysis: Dict,
        architecture: Dict
    ) -> str:
        """Generate a meaningful project name"""
        import re

        request_lower = user_request.lower()

        # Korean keywords mapping
        korean_keywords = {
            "계산기": "calculator",
            "할일": "todo",
            "메모": "memo",
            "게시판": "board",
            "채팅": "chat",
            "블로그": "blog",
        }

        for kor, eng in korean_keywords.items():
            if kor in request_lower:
                return eng

        # English keywords
        english_patterns = [
            (r'\b(calculator)\b', 'calculator'),
            (r'\b(todo)\b', 'todo-app'),
            (r'\b(chat)\b', 'chat-app'),
            (r'\b(blog)\b', 'blog'),
        ]

        for pattern, name in english_patterns:
            if re.search(pattern, request_lower):
                return name

        # Use architecture name if available
        arch_name = architecture.get("project_name", "")
        if arch_name and arch_name.lower() not in {"project", "app", "code"}:
            return arch_name

        # Fallback
        return f"project-{int(time.time()) % 10000}"


# Global dynamic workflow instance
dynamic_workflow = DynamicWorkflow()
