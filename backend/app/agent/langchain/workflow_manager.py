"""Workflow-based coding agent using LangGraph."""
import logging
import re
from typing import List, Dict, Any, AsyncGenerator, Optional, TypedDict, Annotated
from operator import add
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
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


class LangGraphWorkflow(BaseWorkflow):
    """Multi-agent coding workflow using LangGraph: Planning -> Coding -> Review."""

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
        self.planning_prompt = """You are a software architect and planning expert.

Your role is to analyze the user's coding request and create a checklist of tasks.

OUTPUT FORMAT (strictly follow this format):
1. [Task description]
2. [Task description]
3. [Task description]
...

Each task should be:
- Clear and actionable
- Focused on a single step
- Ordered by implementation sequence

Do NOT include explanations or prose. Only output the numbered checklist."""

        self.coding_prompt = """You are an expert software engineer.

Your role is to implement the SPECIFIC task given to you.

OUTPUT FORMAT (strictly follow this format):
Output a code block with filename:

```language filename.ext
// code here
```

Rules:
- Focus ONLY on the current task
- One code block per file
- Include the filename after the language
- Write complete, runnable code
- Do NOT include explanations outside code blocks"""

        self.review_prompt = """You are a senior code reviewer.

Your role is to review the code and provide structured feedback.

OUTPUT FORMAT:
## Issues
- Issue: [description of problem]

## Suggestions
- Suggest: [improvement recommendation]

## Status
[APPROVED or NEEDS_REVISION]

If code changes are needed, include the corrected code block."""

        # Build the workflow graph
        self.graph = self._build_graph()

        logger.info("LangGraphWorkflow initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        graph = StateGraph(WorkflowState)

        # Add nodes
        graph.add_node("planning", self._planning_node)
        graph.add_node("coding", self._coding_node)
        graph.add_node("review", self._review_node)

        # Add edges
        graph.add_edge(START, "planning")
        graph.add_edge("planning", "coding")
        graph.add_edge("coding", "review")
        graph.add_edge("review", END)

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

        return {
            "review_result": review_result,
            "status": "review_complete"
        }

    async def execute(
        self,
        user_request: str,
        context: Optional[Any] = None
    ) -> str:
        """Execute the coding workflow.

        Args:
            user_request: User's coding request
            context: Optional run context

        Returns:
            Final result from the workflow
        """
        logger.info(f"Executing LangGraph workflow for request: {user_request[:100]}...")

        initial_state = WorkflowState(
            user_request=user_request,
            plan_text="",
            checklist=[],
            code_text="",
            artifacts=[],
            review_result={},
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
        """Execute the workflow with streaming updates.

        Args:
            user_request: User's coding request
            context: Optional run context

        Yields:
            Updates with workflow progress
        """
        logger.info(f"Streaming LangGraph workflow for request: {user_request[:100]}...")

        try:
            # Step 1: Planning
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

            plan_text = ""
            async for chunk in self.reasoning_llm.astream(messages):
                if chunk.content:
                    plan_text += chunk.content

            checklist = parse_checklist(plan_text)

            yield {
                "agent": "PlanningAgent",
                "type": "completed",
                "status": "completed",
                "items": checklist
            }

            # Step 2: Coding
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

                messages = [
                    SystemMessage(content=self.coding_prompt),
                    HumanMessage(content="\n".join(context_parts))
                ]

                task_code = ""
                async for chunk in self.coding_llm.astream(messages):
                    if chunk.content:
                        task_code += chunk.content

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
                    "checklist": checklist
                }

            yield {
                "agent": "CodingAgent",
                "type": "completed",
                "status": "completed",
                "artifacts": all_artifacts,
                "checklist": checklist
            }

            # Step 3: Review
            yield {
                "agent": "ReviewAgent",
                "type": "thinking",
                "status": "running",
                "message": "Reviewing code..."
            }

            messages = [
                SystemMessage(content=self.review_prompt),
                HumanMessage(content=f"Please review this code:\n\n{code_text}")
            ]

            review_text = ""
            async for chunk in self.coding_llm.astream(messages):
                if chunk.content:
                    review_text += chunk.content

            review_result = parse_review(review_text)

            yield {
                "agent": "ReviewAgent",
                "type": "completed",
                "status": "completed",
                "issues": review_result["issues"],
                "suggestions": review_result["suggestions"],
                "approved": review_result["approved"],
                "corrected_artifacts": review_result["corrected_artifacts"]
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
                    "review_approved": review_result["approved"]
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
        """Get existing workflow or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            LangGraphWorkflow instance
        """
        if session_id not in self.workflows:
            self.workflows[session_id] = LangGraphWorkflow()
            logger.info(f"Created new LangGraph workflow for session {session_id}")
        return self.workflows[session_id]

    def delete_workflow(self, session_id: str) -> None:
        """Delete workflow for session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.workflows:
            del self.workflows[session_id]
            logger.info(f"Deleted workflow for session {session_id}")

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs.

        Returns:
            List of session IDs
        """
        return list(self.workflows.keys())


# Global workflow manager instance
workflow_manager = LangGraphWorkflowManager()
