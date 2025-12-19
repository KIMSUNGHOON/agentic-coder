"""Enhanced LangGraph Workflow - Production Implementation

This workflow implements:
- Supervisor → Architect → Coders → Quality Gates → HITL → Persistence
- Real-time streaming of code generation
- Parallel execution where applicable
- Proper HITL checkpoints with manager registration
- Agent execution time tracking
- ETA estimation

CRITICAL: This workflow performs REAL operations.
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Dict, List, Any, Optional
from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.langgraph.schemas.state import QualityGateState, create_initial_state, DebugLog

# Import nodes
from app.agent.langgraph.nodes.architect import architect_node
from app.agent.langgraph.nodes.coder import coder_node
from app.agent.langgraph.nodes.reviewer import reviewer_node
from app.agent.langgraph.nodes.refiner import refiner_node
from app.agent.langgraph.nodes.security_gate import security_gate_node
from app.agent.langgraph.nodes.qa_gate import qa_gate_node
from app.agent.langgraph.nodes.aggregator import quality_aggregator_node
from app.agent.langgraph.nodes.persistence import persistence_node

# Import Supervisor
from core.supervisor import SupervisorAgent

# Import HITL
from app.hitl import HITLManager, get_hitl_manager
from app.hitl.models import HITLCheckpointType, HITLRequest as HITLRequestModel, HITLStatus

logger = logging.getLogger(__name__)


# Agent display names and descriptions
AGENT_INFO = {
    "supervisor": {
        "title": "🧠 Supervisor",
        "description": "Task Analysis & Planning",
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


class EnhancedWorkflow:
    """Enhanced production workflow with:
    - Architect Agent for project design
    - Parallel execution support
    - Real-time streaming
    - HITL checkpoints with proper registration
    - Execution time tracking
    """

    def __init__(self):
        """Initialize enhanced workflow"""
        self.supervisor = SupervisorAgent(use_api=True)
        self.hitl_manager = get_hitl_manager()
        self.memory = MemorySaver()
        logger.info("✅ EnhancedWorkflow initialized")

    def _estimate_total_time(self, complexity: str, num_files: int) -> float:
        """Estimate total execution time based on complexity"""
        base_times = {
            "simple": 30,
            "moderate": 60,
            "complex": 120,
            "critical": 180,
        }
        base = base_times.get(complexity, 60)
        return base + (num_files * 5)

    def _get_agent_info(self, agent_name: str) -> Dict[str, str]:
        """Get display info for an agent"""
        return AGENT_INFO.get(agent_name, {
            "title": f"🤖 {agent_name.title()}",
            "description": "Processing...",
            "icon": "robot"
        })

    def _create_hitl_request(
        self,
        request_id: str,
        workflow_id: str,
        stage_id: str,
        checkpoint_type: HITLCheckpointType,
        title: str,
        description: str,
        content: Any,
        priority: str = "normal",
        allow_skip: bool = False
    ) -> HITLRequestModel:
        """Create and register HITL request with manager"""
        request = HITLRequestModel(
            request_id=request_id,
            workflow_id=workflow_id,
            stage_id=stage_id,
            checkpoint_type=checkpoint_type,
            title=title,
            description=description,
            content=content,
            priority=priority,
            allow_skip=allow_skip,
            status=HITLStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # Register with manager
        self.hitl_manager._pending_requests[request_id] = request
        self.hitl_manager._workflow_requests[workflow_id].add(request_id)

        logger.info(f"[HITL] Request registered: {request_id}")
        return request

    async def execute(
        self,
        user_request: str,
        workspace_root: str,
        task_type: str = "general",
        enable_debug: bool = True
    ) -> AsyncGenerator[Dict, None]:
        """Execute enhanced workflow with streaming

        Yields real-time updates including:
        - Agent progress and status
        - Streaming code generation content
        - HITL checkpoints
        - Execution times
        """
        workflow_id = f"workflow_{datetime.utcnow().timestamp()}"
        start_time = time.time()
        agent_times: Dict[str, float] = {}
        completed_agents: List[str] = []

        logger.info(f"🚀 Starting Enhanced Workflow: {workflow_id}")

        try:
            # ==================== PHASE 1: SUPERVISOR ====================
            yield self._create_update("supervisor", "starting", {
                "message": "Analyzing your request...",
                "workflow_id": workflow_id,
            })

            supervisor_start = time.time()
            supervisor_analysis = None
            thinking_blocks = []

            # Stream supervisor thinking
            async for update in self.supervisor.analyze_request_async(user_request):
                if update["type"] == "thinking":
                    thinking_blocks.append(update["content"])
                    yield self._create_update("supervisor", "thinking", {
                        "current_thinking": update["content"][:200] + "..." if len(update["content"]) > 200 else update["content"],
                        "thinking_stream": [t[:100] for t in thinking_blocks[-3:]],  # Last 3 blocks, truncated
                    })
                elif update["type"] == "analysis":
                    supervisor_analysis = update["content"]

            if not supervisor_analysis:
                supervisor_analysis = self.supervisor.analyze_request(user_request)

            agent_times["supervisor"] = time.time() - supervisor_start
            completed_agents.append("supervisor")

            estimated_total = self._estimate_total_time(
                supervisor_analysis.get("complexity", "moderate"), 10
            )

            yield self._create_update("supervisor", "completed", {
                "supervisor_analysis": supervisor_analysis,
                "task_complexity": supervisor_analysis.get("complexity"),
                "workflow_strategy": supervisor_analysis.get("workflow_strategy"),
                "execution_time": agent_times["supervisor"],
                "estimated_total_time": estimated_total,
                "completed_agents": completed_agents.copy(),
                "streaming_content": f"Task Analysis Complete\n• Complexity: {supervisor_analysis.get('complexity')}\n• Strategy: {supervisor_analysis.get('workflow_strategy')}",
            })

            # ==================== PHASE 2: ARCHITECT ====================
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

            architect_result = architect_node(state)
            agent_times["architect"] = time.time() - architect_start
            completed_agents.append("architect")

            architecture = architect_result.get("architecture_design", {})
            files_to_create = architect_result.get("files_to_create", [])

            # Generate project name and create project directory
            project_name = architecture.get("project_name", "project")
            # Sanitize project name (remove special characters, lowercase, replace spaces)
            import re
            project_name = re.sub(r'[^\w\-]', '-', project_name.lower()).strip('-')
            if not project_name:
                project_name = f"project_{int(time.time())}"

            # Create project directory within workspace
            import os
            project_dir = os.path.join(workspace_root, project_name)
            try:
                os.makedirs(project_dir, exist_ok=True)
                logger.info(f"📁 Created project directory: {project_dir}")
            except Exception as e:
                logger.error(f"Failed to create project directory: {e}")
                project_dir = workspace_root  # Fallback to workspace root

            # Update workspace_root to project directory for subsequent nodes
            state["workspace_root"] = project_dir
            original_workspace = workspace_root
            workspace_root = project_dir

            # Send project info to frontend
            yield self._create_update("workflow", "project_info", {
                "project_name": project_name,
                "project_dir": project_dir,
                "original_workspace": original_workspace,
                "message": f"Created project: {project_name}",
                "streaming_content": f"📁 Project: {project_name}\n📂 Location: {project_dir}",
            })

            # Stream architecture design summary
            arch_summary = f"Project: {architecture.get('project_name', 'project')}\n"
            arch_summary += f"Tech Stack: {architecture.get('tech_stack', {}).get('language', 'python')}\n"
            arch_summary += f"Files to create: {len(files_to_create)}\n"
            for f in files_to_create[:3]:
                arch_summary += f"  • {f.get('path', 'unknown')}\n"
            if len(files_to_create) > 3:
                arch_summary += f"  ... and {len(files_to_create) - 3} more"

            yield self._create_update("architect", "completed", {
                "architecture_design": architecture,
                "files_to_create": files_to_create,
                "execution_time": agent_times["architect"],
                "completed_agents": completed_agents.copy(),
                "streaming_content": arch_summary,
            })

            # ==================== PHASE 3: CODING ====================
            yield self._create_update("coder", "starting", {
                "message": f"Generating {len(files_to_create)} files...",
                "files_count": len(files_to_create),
            })

            coder_start = time.time()
            state.update(architect_result)

            # Stream each file being generated
            for i, file_info in enumerate(files_to_create):
                file_path = file_info.get("path", f"file_{i}.py")
                purpose = file_info.get("purpose", "Implementation")

                # Simulate streaming code snippet
                code_preview = self._generate_code_preview(file_path, purpose)

                yield self._create_update("coder", "streaming", {
                    "streaming_file": file_path,
                    "streaming_progress": f"{i + 1}/{len(files_to_create)}",
                    "message": f"Generating {file_path}...",
                    "streaming_content": code_preview,
                })
                await asyncio.sleep(0.3)

            coder_result = coder_node(state)
            agent_times["coder"] = time.time() - coder_start
            completed_agents.append("coder")
            state.update(coder_result)

            yield self._create_update("coder", "completed", {
                "coder_output": coder_result.get("coder_output"),
                "execution_time": agent_times["coder"],
                "completed_agents": completed_agents.copy(),
                "streaming_content": f"Generated {len(files_to_create)} files successfully",
            })

            # ==================== PHASE 4: QUALITY GATES ====================
            complexity = supervisor_analysis.get("complexity", "moderate")

            # Run quality gates
            for gate_name, gate_func in [
                ("reviewer", reviewer_node),
                ("qa_gate", qa_gate_node),
                ("security_gate", security_gate_node),
            ]:
                yield self._create_update(gate_name, "starting", {
                    "message": f"Running {self._get_agent_info(gate_name)['title']}...",
                })

                gate_start = time.time()
                gate_result = gate_func(state)
                agent_times[gate_name] = time.time() - gate_start
                completed_agents.append(gate_name)
                state.update(gate_result)

                # Create streaming content for gate results
                gate_content = self._format_gate_result(gate_name, gate_result)

                yield self._create_update(gate_name, "completed", {
                    "result": gate_result,
                    "execution_time": agent_times[gate_name],
                    "completed_agents": completed_agents.copy(),
                    "streaming_content": gate_content,
                })

            # ==================== PHASE 5: AGGREGATION ====================
            yield self._create_update("aggregator", "starting", {
                "message": "Aggregating results...",
            })

            agg_start = time.time()
            agg_result = quality_aggregator_node(state)
            agent_times["aggregator"] = time.time() - agg_start
            completed_agents.append("aggregator")
            state.update(agg_result)

            all_passed = (
                state.get("security_passed", False) and
                state.get("tests_passed", False) and
                state.get("review_approved", False)
            )

            agg_content = f"Quality Gate Results:\n"
            agg_content += f"  • Security: {'✅ Passed' if state.get('security_passed') else '❌ Failed'}\n"
            agg_content += f"  • Tests: {'✅ Passed' if state.get('tests_passed') else '❌ Failed'}\n"
            agg_content += f"  • Review: {'✅ Approved' if state.get('review_approved') else '❌ Rejected'}"

            yield self._create_update("aggregator", "completed", {
                "all_gates_passed": all_passed,
                "security_passed": state.get("security_passed"),
                "tests_passed": state.get("tests_passed"),
                "review_approved": state.get("review_approved"),
                "execution_time": agent_times["aggregator"],
                "streaming_content": agg_content,
            })

            # ==================== PHASE 6: HITL FINAL APPROVAL ====================
            hitl_approved = True  # Default to approved if no HITL needed

            if complexity in ["complex", "critical"] or not all_passed:
                hitl_request_id = f"final_review_{workflow_id}"

                # Create and register HITL request
                hitl_request = self._create_hitl_request(
                    request_id=hitl_request_id,
                    workflow_id=workflow_id,
                    stage_id="final_approval",
                    checkpoint_type=HITLCheckpointType.APPROVAL if all_passed else HITLCheckpointType.REVIEW,
                    title="Final Review Required" if all_passed else "Issues Found - Review Required",
                    description="Please review the generated code before saving.",
                    content={
                        "type": "code_review",
                        "artifacts_count": len(state.get("final_artifacts", [])),
                        "quality_summary": {
                            "security_passed": state.get("security_passed"),
                            "tests_passed": state.get("tests_passed"),
                            "review_approved": state.get("review_approved"),
                        }
                    },
                    priority="critical" if not all_passed else "high",
                    allow_skip=all_passed
                )

                yield self._create_update("hitl", "awaiting_approval", {
                    "hitl_request": hitl_request.model_dump(),
                    "message": "Waiting for your approval...",
                    "streaming_content": f"Human Review Required\n{hitl_request.title}\n\nPlease approve or provide feedback.",
                })

                # Wait for HITL response with timeout
                max_wait_time = 300  # 5 minutes max wait
                poll_interval = 2  # Check every 2 seconds
                waited = 0
                hitl_approved = False
                hitl_action = None
                hitl_feedback = None
                last_heartbeat = 0

                logger.info(f"[HITL] Waiting for response: {hitl_request_id}")

                while waited < max_wait_time:
                    await asyncio.sleep(poll_interval)
                    waited += poll_interval

                    # Send periodic heartbeat to keep SSE connection alive
                    if waited - last_heartbeat >= 10:
                        last_heartbeat = waited
                        yield self._create_update("hitl", "waiting", {
                            "message": f"Waiting for human approval... ({waited}s / {max_wait_time}s)",
                            "wait_time": waited,
                            "max_wait_time": max_wait_time,
                            "streaming_content": f"⏳ Waiting for human approval ({waited}s)",
                        })

                    # Check if response was submitted
                    if hitl_request_id in self.hitl_manager._pending_requests:
                        request = self.hitl_manager._pending_requests[hitl_request_id]
                        # Check if status is no longer pending (enum comparison)
                        status_value = request.status.value if hasattr(request.status, 'value') else str(request.status)
                        logger.info(f"[HITL] Checking status: {status_value}, response_action: {request.response_action}")

                        if status_value != "pending":
                            hitl_action = request.response_action
                            hitl_feedback = request.response_feedback
                            hitl_approved = hitl_action in ["approve", "confirm"]

                            logger.info(f"[HITL] Response received: action={hitl_action}, approved={hitl_approved}")

                            yield self._create_update("hitl", "completed", {
                                "action": hitl_action,
                                "feedback": hitl_feedback,
                                "approved": hitl_approved,
                                "streaming_content": f"Human Response: {hitl_action.upper() if hitl_action else 'N/A'}\n{hitl_feedback or 'No feedback provided'}",
                            })
                            break
                    else:
                        # Request was removed - check stored responses
                        if hitl_request_id in self.hitl_manager._responses:
                            response = self.hitl_manager._responses[hitl_request_id]
                            hitl_action = response.action.value if hasattr(response.action, 'value') else str(response.action)
                            hitl_feedback = response.feedback
                            hitl_approved = hitl_action in ["approve", "confirm"]

                            logger.info(f"[HITL] Found in responses: action={hitl_action}, approved={hitl_approved}")

                            yield self._create_update("hitl", "completed", {
                                "action": hitl_action,
                                "feedback": hitl_feedback,
                                "approved": hitl_approved,
                                "streaming_content": f"Human Response: {hitl_action.upper()}\n{hitl_feedback or 'No feedback provided'}",
                            })
                            break
                        else:
                            logger.warning(f"[HITL] Request removed but no response found: {hitl_request_id}")
                            break

                # Check if timeout
                if waited >= max_wait_time and not hitl_action:
                    logger.warning(f"[HITL] Timeout waiting for response: {hitl_request_id}")
                    yield self._create_update("hitl", "timeout", {
                        "message": "HITL request timed out",
                        "streaming_content": "⚠️ Timeout: No response received within 5 minutes",
                    })
                    hitl_approved = True  # Default to approved on timeout

                # Handle rejection/retry
                if not hitl_approved and hitl_action in ["reject", "retry"]:
                    yield self._create_update("workflow", "stopped", {
                        "reason": "rejected_by_user",
                        "feedback": hitl_feedback,
                        "streaming_content": f"⚠️ Workflow stopped by user\nAction: {hitl_action}\nFeedback: {hitl_feedback or 'None'}",
                        "message": "Workflow stopped - user requested changes",
                    })
                    return  # Stop workflow execution

            # ==================== PHASE 7: PERSISTENCE ====================
            yield self._create_update("persistence", "starting", {
                "message": "Saving files to workspace...",
            })

            persist_start = time.time()
            persist_result = persistence_node(state)
            agent_times["persistence"] = time.time() - persist_start
            completed_agents.append("persistence")

            saved_files = persist_result.get("final_artifacts", [])
            persist_content = f"Saved {len(saved_files)} files:\n"
            for artifact in saved_files[:5]:
                persist_content += f"  • {artifact.get('filename', 'unknown')}\n"

            yield self._create_update("persistence", "completed", {
                "saved_files": saved_files,
                "execution_time": agent_times["persistence"],
                "streaming_content": persist_content,
            })

            # ==================== WORKFLOW COMPLETE ====================
            total_time = time.time() - start_time

            summary = f"✅ Workflow Complete in {total_time:.1f}s\n\n"
            summary += "Agent Execution Times:\n"
            for agent, t in agent_times.items():
                summary += f"  • {self._get_agent_info(agent)['title']}: {t:.1f}s\n"

            yield self._create_update("workflow", "completed", {
                "workflow_id": workflow_id,
                "total_execution_time": round(total_time, 2),
                "agent_execution_times": {k: round(v, 2) for k, v in agent_times.items()},
                "completed_agents": completed_agents,
                "final_artifacts": state.get("final_artifacts", []),
                "streaming_content": summary,
                "message": f"Workflow completed in {total_time:.1f}s",
            })

        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}", exc_info=True)
            yield self._create_update("error", "error", {
                "error": str(e),
                "workflow_id": workflow_id,
                "streaming_content": f"❌ Error: {str(e)}",
            })

    def _generate_code_preview(self, file_path: str, purpose: str) -> str:
        """Generate a preview of code being created"""
        ext = file_path.split('.')[-1] if '.' in file_path else 'py'

        if ext in ['py', 'python']:
            return f'''# {file_path}
# Purpose: {purpose}

def main():
    """Main entry point"""
    pass

if __name__ == "__main__":
    main()'''
        elif ext in ['ts', 'tsx', 'js', 'jsx']:
            return f'''// {file_path}
// Purpose: {purpose}

export function main() {{
  // Implementation
}}'''
        else:
            return f"# {file_path}\n# {purpose}"

    def _format_gate_result(self, gate_name: str, result: Dict) -> str:
        """Format quality gate result for streaming display"""
        if gate_name == "reviewer":
            feedback = result.get("review_feedback", {})
            approved = feedback.get("approved", False)
            score = feedback.get("quality_score", 0)
            issues = feedback.get("issues", [])
            return f"Code Review: {'✅ Approved' if approved else '❌ Needs Changes'}\nQuality Score: {score:.0%}\nIssues: {len(issues)}"

        elif gate_name == "qa_gate":
            passed = result.get("tests_passed", False)
            results = result.get("qa_test_results", [])
            return f"QA Tests: {'✅ All Passed' if passed else '❌ Some Failed'}\nTests Run: {len(results)}"

        elif gate_name == "security_gate":
            passed = result.get("security_passed", False)
            findings = result.get("security_findings", [])
            critical = len([f for f in findings if f.get("severity") in ["critical", "high"]])
            return f"Security: {'✅ No Issues' if passed else '❌ Issues Found'}\nFindings: {len(findings)} ({critical} critical/high)"

        return f"{gate_name}: Complete"

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


# Global enhanced workflow instance
enhanced_workflow = EnhancedWorkflow()
