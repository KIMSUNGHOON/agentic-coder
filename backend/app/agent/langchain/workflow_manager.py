"""Workflow-based coding agent using LangGraph with iterative review loop."""
import logging
import re
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator, Optional, TypedDict, Annotated, Literal
from operator import add
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from app.core.config import settings
from app.agent.base.interface import BaseWorkflow, BaseWorkflowManager

logger = logging.getLogger(__name__)


# State definition for LangGraph
class WorkflowState(TypedDict):
    """State maintained throughout the workflow."""
    user_request: str
    plan_text: str
    checklist: List[Dict[str, Any]]
    code_text: str
    artifacts: Annotated[List[Dict[str, Any]], add]
    review_result: Dict[str, Any]
    review_iteration: int  # Track review iterations
    max_iterations: int    # Maximum allowed iterations
    current_task_idx: int
    status: str
    error: Optional[str]


def parse_checklist(text: str) -> List[Dict[str, Any]]:
    """Parse text into checklist items."""
    items = []
    pattern = r'(?:^|\n)\s*(?:(\d+)[.\)]\s*|[-*]\s*)(.+?)(?=\n|$)'
    matches = re.findall(pattern, text)

    for i, (num, task) in enumerate(matches, 1):
        task = task.strip()
        if task:
            items.append({
                "id": int(num) if num else i,
                "task": task,
                "completed": False,
                "artifacts": []
            })

    return items


def parse_code_blocks(text: str) -> List[Dict[str, Any]]:
    """Extract code blocks from text."""
    artifacts = []
    pattern = r'```(\w+)?(?:\s+(\S+))?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)

    extensions = {
        "python": "py", "javascript": "js", "typescript": "ts",
        "java": "java", "go": "go", "rust": "rs", "cpp": "cpp",
        "c": "c", "html": "html", "css": "css", "json": "json",
        "yaml": "yaml", "sql": "sql", "bash": "sh", "shell": "sh"
    }

    for lang, filename, content in matches:
        lang = lang or "text"
        if not filename:
            ext = extensions.get(lang.lower(), "txt")
            filename = f"code.{ext}"
        artifacts.append({
            "type": "artifact",
            "language": lang,
            "filename": filename,
            "content": content.strip()
        })

    return artifacts


def parse_review(text: str) -> Dict[str, Any]:
    """Parse review text into structured format."""
    issues = []
    suggestions = []
    approved = False

    if re.search(r'(?:approved|lgtm|looks good|no issues)', text, re.IGNORECASE):
        approved = True

    issue_pattern = r'(?:^|\n)\s*[-*]?\s*(?:issue|bug|error|problem|warning)[:.]?\s*(.+?)(?=\n|$)'
    for match in re.finditer(issue_pattern, text, re.IGNORECASE):
        issues.append(match.group(1).strip())

    suggestion_pattern = r'(?:^|\n)\s*[-*]?\s*(?:suggest|recommend|consider|improvement)[:.]?\s*(.+?)(?=\n|$)'
    for match in re.finditer(suggestion_pattern, text, re.IGNORECASE):
        suggestions.append(match.group(1).strip())

    return {
        "issues": issues,
        "suggestions": suggestions,
        "approved": approved,
        "corrected_artifacts": parse_code_blocks(text)
    }


def should_fix_code(state: WorkflowState) -> Literal["fix_code", "end"]:
    """Decision function: should we fix the code or end?"""
    review_result = state.get("review_result", {})
    review_iteration = state.get("review_iteration", 0)
    max_iterations = state.get("max_iterations", settings.max_review_iterations)

    approved = review_result.get("approved", False)

    # End if approved OR max iterations reached
    if approved:
        logger.info("Code approved by review, ending workflow")
        return "end"
    elif review_iteration >= max_iterations:
        logger.info(f"Max iterations ({max_iterations}) reached, ending workflow")
        return "end"
    else:
        logger.info(f"Code not approved (iteration {review_iteration}/{max_iterations}), fixing code")
        return "fix_code"


class LangGraphWorkflow(BaseWorkflow):
    """Multi-agent coding workflow using LangGraph with iterative review loop."""

    def __init__(self):
        """Initialize the LangGraph workflow."""
        # Initialize LLM clients
        self.reasoning_llm = ChatOpenAI(
            base_url=settings.vllm_reasoning_endpoint,
            model=settings.reasoning_model,
            temperature=0.7,
            max_tokens=2048,
            api_key="not-needed",
        )

        self.coding_llm = ChatOpenAI(
            base_url=settings.vllm_coding_endpoint,
            model=settings.coding_model,
            temperature=0.7,
            max_tokens=2048,
            api_key="not-needed",
        )

        # System prompts for each agent
        # DeepSeek R1 style for planning (reasoning model)
        self.planning_prompt = """Analyze request and create implementation checklist.

<think>
Break down the request into atomic, sequential steps.
Consider dependencies between tasks.
Order by implementation sequence.
</think>

<output_format>
1. [Task description]
2. [Task description]
3. [Task description]
</output_format>

Rules:
- One task per line
- Clear, actionable steps
- No explanations, only the numbered list"""

        # Qwen3 style for coding (coding model)
        self.coding_prompt = """Implement the specified task.

<response_format>
THOUGHTS: [brief analysis]

```language filename.ext
// complete code
```
</response_format>

<rules>
- Focus ONLY on current task
- One code block per file
- Include filename after language
- Write complete, runnable code
- Full file content for updates
- No explanations outside code blocks
</rules>"""

        # Qwen3 style for review (coding model)
        self.review_prompt = """Review code and provide structured feedback.

<response_format>
ANALYSIS: [brief review summary]

ISSUES:
- Issue: [problem description]

SUGGESTIONS:
- Suggest: [improvement]

STATUS: [APPROVED or NEEDS_REVISION]

If changes needed:
```language filename.ext
// corrected code
```
</response_format>

<criteria>
- Code correctness
- Best practices
- Security concerns
- Performance issues
</criteria>

Only list actual issues found. Be concise."""

        # Fix code prompt - used when review finds issues
        self.fix_code_prompt = """Fix the code based on review feedback.

<review_issues>
{issues}
</review_issues>

<review_suggestions>
{suggestions}
</review_suggestions>

<response_format>
FIXES_APPLIED: [list what you fixed]

```language filename.ext
// corrected complete code
```
</response_format>

<rules>
- Address ALL issues mentioned
- Apply relevant suggestions
- Provide complete fixed code
- Maintain original functionality
</rules>"""

        # Build the workflow graph
        self.graph = self._build_graph()

        logger.info("LangGraphWorkflow initialized with iterative review loop")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with conditional edges."""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("planning", self._planning_node)
        graph.add_node("coding", self._coding_node)
        graph.add_node("review", self._review_node)
        graph.add_node("fix_code", self._fix_code_node)

        # Add edges - with conditional loop
        graph.add_edge(START, "planning")
        graph.add_edge("planning", "coding")
        graph.add_edge("coding", "review")

        # Conditional edge after review: either fix_code or end
        graph.add_conditional_edges(
            "review",
            should_fix_code,
            {
                "fix_code": "fix_code",
                "end": END
            }
        )

        # After fixing, go back to review
        graph.add_edge("fix_code", "review")

        return graph.compile()

    async def _planning_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Planning agent node."""
        messages = [
            SystemMessage(content=self.planning_prompt),
            HumanMessage(content=state["user_request"])
        ]

        response = await self.reasoning_llm.ainvoke(messages)
        plan_text = response.content
        checklist = parse_checklist(plan_text)

        return {
            "plan_text": plan_text,
            "checklist": checklist,
            "status": "planning_complete"
        }

    async def _coding_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Coding agent node - implements all tasks."""
        all_artifacts = []
        code_text = ""
        checklist = state["checklist"]
        existing_code = ""

        for idx, task_item in enumerate(checklist):
            task_description = task_item["task"]

            # Build context message
            context_parts = [f"Original request: {state['user_request']}"]
            context_parts.append(f"\nFull plan:\n{state['plan_text']}")

            if existing_code:
                context_parts.append(f"\nCode implemented so far:\n{existing_code}")

            context_parts.append(f"\nCurrent task ({idx + 1}/{len(checklist)}): {task_description}")
            context_parts.append("\nPlease implement this specific task now.")

            messages = [
                SystemMessage(content=self.coding_prompt),
                HumanMessage(content="\n".join(context_parts))
            ]

            response = await self.coding_llm.ainvoke(messages)
            task_code = response.content
            code_text += task_code + "\n"

            # Extract artifacts from this task
            task_artifacts = parse_code_blocks(task_code)
            all_artifacts.extend(task_artifacts)

            # Update context with generated code
            for artifact in task_artifacts:
                existing_code += f"\n\n```{artifact['language']} {artifact['filename']}\n{artifact['content']}\n```"

            # Mark task as completed
            checklist[idx]["completed"] = True
            checklist[idx]["artifacts"] = [a["filename"] for a in task_artifacts]

        return {
            "code_text": code_text,
            "artifacts": all_artifacts,
            "checklist": checklist,
            "review_iteration": 0,  # Reset iteration on new code
            "status": "coding_complete"
        }

    async def _review_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Review agent node."""
        messages = [
            SystemMessage(content=self.review_prompt),
            HumanMessage(content=f"Please review this code:\n\n{state['code_text']}")
        ]

        response = await self.coding_llm.ainvoke(messages)
        review_result = parse_review(response.content)

        # Increment review iteration
        current_iteration = state.get("review_iteration", 0) + 1

        return {
            "review_result": review_result,
            "review_iteration": current_iteration,
            "status": "review_complete"
        }

    async def _fix_code_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Fix code based on review feedback."""
        review_result = state.get("review_result", {})
        issues = review_result.get("issues", [])
        suggestions = review_result.get("suggestions", [])

        # Build fix prompt with review feedback
        fix_prompt = self.fix_code_prompt.format(
            issues="\n".join(f"- {issue}" for issue in issues) if issues else "None",
            suggestions="\n".join(f"- {s}" for s in suggestions) if suggestions else "None"
        )

        messages = [
            SystemMessage(content=fix_prompt),
            HumanMessage(content=f"Original code to fix:\n\n{state['code_text']}")
        ]

        response = await self.coding_llm.ainvoke(messages)
        fixed_code = response.content

        # Extract new artifacts from fixed code
        fixed_artifacts = parse_code_blocks(fixed_code)

        return {
            "code_text": fixed_code,
            "artifacts": fixed_artifacts,
            "status": "fix_complete"
        }

    async def execute(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> str:
        """Execute the coding workflow."""
        logger.info(f"Executing LangGraph workflow for request: {user_request[:100]}...")

        initial_state = WorkflowState(
            user_request=user_request,
            plan_text="",
            checklist=[],
            code_text="",
            artifacts=[],
            review_result={},
            review_iteration=0,
            max_iterations=settings.max_review_iterations,
            current_task_idx=0,
            status="started",
            error=None
        )

        result = await self.graph.ainvoke(initial_state)
        return result.get("code_text", "")

    async def execute_stream(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the workflow with streaming updates and iterative review."""
        logger.info(f"Streaming LangGraph workflow for request: {user_request[:100]}...")
        workflow_id = str(uuid.uuid4())[:8]
        max_iterations = settings.max_review_iterations

        try:
            # Emit workflow creation event with loop structure
            yield {
                "agent": "Orchestrator",
                "type": "workflow_created",
                "status": "running",
                "message": f"LangGraph workflow initialized (max {max_iterations} review iterations)",
                "workflow_info": {
                    "workflow_id": workflow_id,
                    "workflow_type": "LangGraph Iterative Multi-Agent",
                    "nodes": ["PlanningAgent", "CodingAgent", "ReviewAgent", "FixCodeAgent"],
                    "edges": [
                        {"from": "START", "to": "PlanningAgent"},
                        {"from": "PlanningAgent", "to": "CodingAgent"},
                        {"from": "CodingAgent", "to": "ReviewAgent"},
                        {"from": "ReviewAgent", "to": "Decision"},
                        {"from": "Decision", "to": "FixCodeAgent", "condition": "not approved"},
                        {"from": "Decision", "to": "END", "condition": "approved"},
                        {"from": "FixCodeAgent", "to": "ReviewAgent"}
                    ],
                    "current_node": "PlanningAgent",
                    "max_iterations": max_iterations
                }
            }

            # Step 1: Planning
            planning_agent_id = f"planning-{uuid.uuid4().hex[:6]}"
            yield {
                "agent": "PlanningAgent",
                "type": "agent_spawn",
                "status": "running",
                "message": "Spawning PlanningAgent for task analysis",
                "agent_spawn": {
                    "agent_id": planning_agent_id,
                    "agent_type": "PlanningAgent",
                    "parent_agent": "Orchestrator",
                    "spawn_reason": "Analyze user request and create implementation checklist",
                    "timestamp": datetime.now().isoformat()
                }
            }

            yield {
                "agent": "PlanningAgent",
                "type": "thinking",
                "status": "running",
                "message": "Analyzing requirements..."
            }

            messages = [
                SystemMessage(content=self.planning_prompt),
                HumanMessage(content=user_request)
            ]

            start_time = time.time()
            plan_text = ""
            async for chunk in self.reasoning_llm.astream(messages):
                if chunk.content:
                    plan_text += chunk.content
            latency_ms = int((time.time() - start_time) * 1000)

            checklist = parse_checklist(plan_text)

            yield {
                "agent": "PlanningAgent",
                "type": "completed",
                "status": "completed",
                "items": checklist,
                "prompt_info": {
                    "system_prompt": self.planning_prompt,
                    "user_prompt": user_request,
                    "output": plan_text,
                    "model": settings.reasoning_model,
                    "latency_ms": latency_ms
                }
            }

            # Step 2: Coding
            coding_agent_id = f"coding-{uuid.uuid4().hex[:6]}"
            yield {
                "agent": "CodingAgent",
                "type": "agent_spawn",
                "status": "running",
                "message": "Spawning CodingAgent for implementation",
                "agent_spawn": {
                    "agent_id": coding_agent_id,
                    "agent_type": "CodingAgent",
                    "parent_agent": "Orchestrator",
                    "spawn_reason": f"Implement {len(checklist)} tasks from planning phase",
                    "timestamp": datetime.now().isoformat()
                }
            }

            all_artifacts = []
            code_text = ""
            existing_code = ""

            for idx, task_item in enumerate(checklist):
                task_num = idx + 1
                task_description = task_item["task"]

                yield {
                    "agent": "CodingAgent",
                    "type": "thinking",
                    "status": "running",
                    "message": f"Task {task_num}/{len(checklist)}: {task_description}",
                    "checklist": checklist
                }

                # Build context
                context_parts = [f"Original request: {user_request}"]
                context_parts.append(f"\nFull plan:\n{plan_text}")

                if existing_code:
                    context_parts.append(f"\nCode implemented so far:\n{existing_code}")

                context_parts.append(f"\nCurrent task ({task_num}/{len(checklist)}): {task_description}")
                context_parts.append("\nPlease implement this specific task now.")

                user_prompt_content = "\n".join(context_parts)
                messages = [
                    SystemMessage(content=self.coding_prompt),
                    HumanMessage(content=user_prompt_content)
                ]

                start_time = time.time()
                task_code = ""
                async for chunk in self.coding_llm.astream(messages):
                    if chunk.content:
                        task_code += chunk.content
                task_latency_ms = int((time.time() - start_time) * 1000)

                code_text += task_code + "\n"

                # Extract artifacts
                task_artifacts = parse_code_blocks(task_code)
                all_artifacts.extend(task_artifacts)

                for artifact in task_artifacts:
                    existing_code += f"\n\n```{artifact['language']} {artifact['filename']}\n{artifact['content']}\n```"

                    yield {
                        "agent": "CodingAgent",
                        "type": "artifact",
                        "status": "running",
                        "message": f"Task {task_num}: Created {artifact['filename']}",
                        "artifact": artifact,
                        "checklist": checklist
                    }

                # Mark task completed
                checklist[idx]["completed"] = True
                checklist[idx]["artifacts"] = [a["filename"] for a in task_artifacts]

                yield {
                    "agent": "CodingAgent",
                    "type": "task_completed",
                    "status": "running",
                    "message": f"Task {task_num}/{len(checklist)}: {task_description}",
                    "task_result": {
                        "task_num": task_num,
                        "task": task_description,
                        "artifacts": task_artifacts
                    },
                    "checklist": checklist,
                    "prompt_info": {
                        "system_prompt": self.coding_prompt,
                        "user_prompt": user_prompt_content,
                        "output": task_code,
                        "model": settings.coding_model,
                        "latency_ms": task_latency_ms
                    }
                }

            yield {
                "agent": "CodingAgent",
                "type": "completed",
                "status": "completed",
                "artifacts": all_artifacts,
                "checklist": checklist
            }

            # Step 3: Review Loop
            review_iteration = 0
            approved = False

            while not approved and review_iteration < max_iterations:
                review_iteration += 1

                # Spawn ReviewAgent
                review_agent_id = f"review-{uuid.uuid4().hex[:6]}"
                yield {
                    "agent": "ReviewAgent",
                    "type": "agent_spawn",
                    "status": "running",
                    "message": f"Spawning ReviewAgent (iteration {review_iteration}/{max_iterations})",
                    "agent_spawn": {
                        "agent_id": review_agent_id,
                        "agent_type": "ReviewAgent",
                        "parent_agent": "Orchestrator",
                        "spawn_reason": f"Review code - iteration {review_iteration} of {max_iterations}",
                        "timestamp": datetime.now().isoformat()
                    },
                    "iteration_info": {
                        "current": review_iteration,
                        "max": max_iterations
                    }
                }

                yield {
                    "agent": "ReviewAgent",
                    "type": "thinking",
                    "status": "running",
                    "message": f"Reviewing code (iteration {review_iteration}/{max_iterations})..."
                }

                review_user_prompt = f"Please review this code:\n\n{code_text}"
                messages = [
                    SystemMessage(content=self.review_prompt),
                    HumanMessage(content=review_user_prompt)
                ]

                start_time = time.time()
                review_text = ""
                async for chunk in self.coding_llm.astream(messages):
                    if chunk.content:
                        review_text += chunk.content
                review_latency_ms = int((time.time() - start_time) * 1000)

                review_result = parse_review(review_text)
                approved = review_result["approved"]

                yield {
                    "agent": "ReviewAgent",
                    "type": "completed",
                    "status": "completed",
                    "issues": review_result["issues"],
                    "suggestions": review_result["suggestions"],
                    "approved": approved,
                    "corrected_artifacts": review_result["corrected_artifacts"],
                    "prompt_info": {
                        "system_prompt": self.review_prompt,
                        "user_prompt": review_user_prompt,
                        "output": review_text,
                        "model": settings.coding_model,
                        "latency_ms": review_latency_ms
                    },
                    "iteration_info": {
                        "current": review_iteration,
                        "max": max_iterations
                    }
                }

                # Decision point
                yield {
                    "agent": "Orchestrator",
                    "type": "decision",
                    "status": "running",
                    "message": f"Review decision: {'APPROVED' if approved else 'NEEDS_REVISION'}",
                    "decision": {
                        "approved": approved,
                        "iteration": review_iteration,
                        "max_iterations": max_iterations,
                        "action": "end" if approved else ("fix_code" if review_iteration < max_iterations else "end_max_iterations")
                    }
                }

                # If not approved and we have iterations left, fix the code
                if not approved and review_iteration < max_iterations:
                    fix_agent_id = f"fix-{uuid.uuid4().hex[:6]}"
                    yield {
                        "agent": "FixCodeAgent",
                        "type": "agent_spawn",
                        "status": "running",
                        "message": f"Spawning FixCodeAgent to address {len(review_result['issues'])} issues",
                        "agent_spawn": {
                            "agent_id": fix_agent_id,
                            "agent_type": "FixCodeAgent",
                            "parent_agent": "Orchestrator",
                            "spawn_reason": f"Fix {len(review_result['issues'])} issues from review",
                            "timestamp": datetime.now().isoformat()
                        }
                    }

                    yield {
                        "agent": "FixCodeAgent",
                        "type": "thinking",
                        "status": "running",
                        "message": f"Fixing {len(review_result['issues'])} issues..."
                    }

                    # Build fix prompt
                    fix_prompt = self.fix_code_prompt.format(
                        issues="\n".join(f"- {issue}" for issue in review_result["issues"]) if review_result["issues"] else "None",
                        suggestions="\n".join(f"- {s}" for s in review_result["suggestions"]) if review_result["suggestions"] else "None"
                    )

                    fix_user_prompt = f"Original code to fix:\n\n{code_text}"
                    messages = [
                        SystemMessage(content=fix_prompt),
                        HumanMessage(content=fix_user_prompt)
                    ]

                    start_time = time.time()
                    fixed_code = ""
                    async for chunk in self.coding_llm.astream(messages):
                        if chunk.content:
                            fixed_code += chunk.content
                    fix_latency_ms = int((time.time() - start_time) * 1000)

                    # Update code and artifacts
                    code_text = fixed_code
                    fixed_artifacts = parse_code_blocks(fixed_code)
                    all_artifacts = fixed_artifacts  # Replace with fixed versions

                    for artifact in fixed_artifacts:
                        yield {
                            "agent": "FixCodeAgent",
                            "type": "artifact",
                            "status": "running",
                            "message": f"Fixed: {artifact['filename']}",
                            "artifact": artifact
                        }

                    yield {
                        "agent": "FixCodeAgent",
                        "type": "completed",
                        "status": "completed",
                        "artifacts": fixed_artifacts,
                        "prompt_info": {
                            "system_prompt": fix_prompt,
                            "user_prompt": fix_user_prompt,
                            "output": fixed_code,
                            "model": settings.coding_model,
                            "latency_ms": fix_latency_ms
                        },
                        "iteration_info": {
                            "current": review_iteration,
                            "max": max_iterations
                        }
                    }

            # Final summary
            yield {
                "agent": "Workflow",
                "type": "completed",
                "status": "finished",
                "summary": {
                    "tasks_completed": sum(1 for item in checklist if item["completed"]),
                    "total_tasks": len(checklist),
                    "artifacts_count": len(all_artifacts),
                    "review_approved": approved,
                    "review_iterations": review_iteration,
                    "max_iterations": max_iterations
                },
                "workflow_info": {
                    "workflow_id": workflow_id,
                    "workflow_type": "LangGraph Iterative Multi-Agent",
                    "nodes": ["PlanningAgent", "CodingAgent", "ReviewAgent", "FixCodeAgent"],
                    "edges": [
                        {"from": "START", "to": "PlanningAgent"},
                        {"from": "PlanningAgent", "to": "CodingAgent"},
                        {"from": "CodingAgent", "to": "ReviewAgent"},
                        {"from": "ReviewAgent", "to": "Decision"},
                        {"from": "Decision", "to": "FixCodeAgent", "condition": "not approved"},
                        {"from": "Decision", "to": "END", "condition": "approved"},
                        {"from": "FixCodeAgent", "to": "ReviewAgent"}
                    ],
                    "current_node": "END",
                    "final_status": "approved" if approved else "max_iterations_reached"
                }
            }

        except Exception as e:
            logger.error(f"Error in LangGraph workflow: {e}")
            yield {
                "agent": "Workflow",
                "type": "error",
                "status": "error",
                "message": str(e)
            }
            raise


class LangGraphWorkflowManager(BaseWorkflowManager):
    """Manager for LangGraph workflow sessions."""

    def __init__(self):
        """Initialize workflow manager."""
        self.workflows: Dict[str, LangGraphWorkflow] = {}
        logger.info("LangGraphWorkflowManager initialized")

    def get_or_create_workflow(self, session_id: str) -> LangGraphWorkflow:
        """Get existing workflow or create new one for session."""
        if session_id not in self.workflows:
            self.workflows[session_id] = LangGraphWorkflow()
            logger.info(f"Created new LangGraph workflow for session {session_id}")
        return self.workflows[session_id]

    def delete_workflow(self, session_id: str) -> None:
        """Delete workflow for session."""
        if session_id in self.workflows:
            del self.workflows[session_id]
            logger.info(f"Deleted workflow for session {session_id}")

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.workflows.keys())


# Global workflow manager instance
workflow_manager = LangGraphWorkflowManager()
