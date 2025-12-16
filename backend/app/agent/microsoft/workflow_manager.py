"""Workflow-based coding agent using Microsoft Agent Framework."""
import logging
import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass, field
from agent_framework import (
    WorkflowBuilder,
    ChatAgent,
    AgentRunContext,
    ChatMessage,
    BaseChatClient,
    ChatResponseUpdate,
    TextContent,
)
from app.services.vllm_client import vllm_router
from app.agent.base.interface import BaseWorkflow, BaseWorkflowManager

logger = logging.getLogger(__name__)


class CodeBlockParser:
    """Parser for detecting and extracting code blocks from streaming text."""

    def __init__(self):
        self.buffer = ""
        self.in_code_block = False
        self.current_language = ""
        self.current_filename = ""

    def add_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """Add a chunk and return any complete code blocks.

        Returns:
            List of completed artifacts: [{"type": "artifact", "language": "...", "filename": "...", "content": "..."}]
        """
        self.buffer += chunk
        artifacts = []

        while True:
            if not self.in_code_block:
                # Look for opening ```
                match = re.search(r'```(\w+)?(?:\s+(\S+))?\n', self.buffer)
                if match:
                    self.in_code_block = True
                    self.current_language = match.group(1) or "text"
                    self.current_filename = match.group(2) or f"code.{self._get_extension(self.current_language)}"
                    self.buffer = self.buffer[match.end():]
                else:
                    break
            else:
                # Look for closing ```
                end_match = re.search(r'\n```(?:\s|$)', self.buffer)
                if end_match:
                    code_content = self.buffer[:end_match.start()]
                    artifacts.append({
                        "type": "artifact",
                        "language": self.current_language,
                        "filename": self.current_filename,
                        "content": code_content.strip()
                    })
                    self.buffer = self.buffer[end_match.end():]
                    self.in_code_block = False
                    self.current_language = ""
                    self.current_filename = ""
                else:
                    break

        return artifacts

    def _get_extension(self, language: str) -> str:
        """Get file extension for a language."""
        extensions = {
            "python": "py", "javascript": "js", "typescript": "ts",
            "java": "java", "go": "go", "rust": "rs", "cpp": "cpp",
            "c": "c", "html": "html", "css": "css", "json": "json",
            "yaml": "yaml", "sql": "sql", "bash": "sh", "shell": "sh"
        }
        return extensions.get(language.lower(), "txt")

    def get_remaining(self) -> str:
        """Get any remaining non-code text."""
        return self.buffer


def parse_checklist(text: str) -> List[Dict[str, Any]]:
    """Parse text into checklist items.

    Returns:
        List of checklist items: [{"id": 1, "task": "...", "completed": False}, ...]
    """
    items = []
    # Match numbered items like "1. Task" or "1) Task" or "- Task" or "* Task"
    pattern = r'(?:^|\n)\s*(?:(\d+)[.\)]\s*|[-*]\s*)(.+?)(?=\n|$)'
    matches = re.findall(pattern, text)

    for i, (num, task) in enumerate(matches, 1):
        task = task.strip()
        if task:
            items.append({
                "id": int(num) if num else i,
                "task": task,
                "completed": False
            })

    return items


def parse_review(text: str) -> Dict[str, Any]:
    """Parse review text into structured format.

    Returns:
        {"issues": [...], "suggestions": [...], "approved": bool}
    """
    issues = []
    suggestions = []
    approved = False

    # Check for approval indicators
    if re.search(r'(?:approved|lgtm|looks good|no issues)', text, re.IGNORECASE):
        approved = True

    # Extract issues (lines starting with issue indicators)
    issue_pattern = r'(?:^|\n)\s*[-*]?\s*(?:issue|bug|error|problem|warning)[:.]?\s*(.+?)(?=\n|$)'
    for match in re.finditer(issue_pattern, text, re.IGNORECASE):
        issues.append(match.group(1).strip())

    # Extract suggestions
    suggestion_pattern = r'(?:^|\n)\s*[-*]?\s*(?:suggest|recommend|consider|improvement)[:.]?\s*(.+?)(?=\n|$)'
    for match in re.finditer(suggestion_pattern, text, re.IGNORECASE):
        suggestions.append(match.group(1).strip())

    return {
        "issues": issues,
        "suggestions": suggestions,
        "approved": approved
    }


@dataclass
class Response:
    """Complete response wrapper matching agent framework expectations."""
    messages: List[ChatMessage] = field(default_factory=list)
    conversation_id: Optional[str] = None
    response_id: Optional[str] = None
    object: str = "response"
    created_at: Optional[datetime] = None
    status: str = "completed"
    model: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    usage_details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.response_id is None:
            self.response_id = f"resp_{uuid.uuid4().hex[:24]}"
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.usage is None:
            self.usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        if self.usage_details is None:
            self.usage_details = {}

    def __getattr__(self, name: str) -> Any:
        """Return None for any undefined attributes to prevent AttributeError."""
        return None

    @property
    def text(self) -> str:
        """Get text from first message."""
        return self.messages[0].text if self.messages else ""


class VLLMChatClient(BaseChatClient):
    """Custom chat client for vLLM that implements BaseChatClient interface."""

    def __init__(self, model_type: str):
        """Initialize vLLM chat client.

        Args:
            model_type: 'reasoning' or 'coding'
        """
        self.vllm_client = vllm_router.get_client(model_type)
        self.model_type = model_type

    async def _inner_get_response(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> Response:
        """Get a non-streaming response from vLLM.

        Args:
            messages: List of chat messages
            **kwargs: Additional arguments (temperature, max_tokens, etc.)

        Returns:
            Response object with messages and conversation_id
        """
        # Convert ChatMessage to dict format for vLLM
        # Role is an enum, so we need to get its string value
        vllm_messages = [
            {
                "role": msg.role if isinstance(msg.role, str) else msg.role.value,
                "content": msg.text
            }
            for msg in messages
        ]

        vllm_response = await self.vllm_client.chat_completion(
            messages=vllm_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
            stream=False
        )

        # Create response message
        response_message = ChatMessage(
            role="assistant",
            text=vllm_response.choices[0].message.content
        )

        # Extract usage information if available
        usage = None
        if hasattr(vllm_response, 'usage') and vllm_response.usage:
            usage = {
                "prompt_tokens": getattr(vllm_response.usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(vllm_response.usage, 'completion_tokens', 0),
                "total_tokens": getattr(vllm_response.usage, 'total_tokens', 0)
            }

        # Return Response object with all metadata
        return Response(
            messages=[response_message],
            conversation_id=kwargs.get("conversation_id"),
            model=self.model_type,
            usage=usage
        )

    async def _inner_get_streaming_response(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> AsyncGenerator[ChatResponseUpdate, None]:
        """Get a streaming response from vLLM.

        Args:
            messages: List of chat messages
            **kwargs: Additional arguments (temperature, max_tokens, etc.)

        Yields:
            ChatResponseUpdate instances with text content
        """
        # Convert ChatMessage to dict format for vLLM
        # Role is an enum, so we need to get its string value
        vllm_messages = [
            {
                "role": msg.role if isinstance(msg.role, str) else msg.role.value,
                "content": msg.text
            }
            for msg in messages
        ]

        async for chunk in self.vllm_client.stream_chat_completion(
            messages=vllm_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048)
        ):
            yield ChatResponseUpdate(
                contents=[TextContent(text=chunk)],
                role="assistant",
                author_name=self.model_type,
            )


class CodingWorkflow(BaseWorkflow):
    """Multi-agent coding workflow: Planning -> Coding -> Review."""

    def __init__(self):
        """Initialize the coding workflow."""
        # Create chat clients for each model
        self.reasoning_client = VLLMChatClient("reasoning")
        self.coding_client = VLLMChatClient("coding")

        # Create agents with structured output prompts
        self.planning_agent = ChatAgent(
            name="PlanningAgent",
            description="Analyzes requirements and creates implementation plan",
            chat_client=self.reasoning_client,
            system_message="""You are a software architect and planning expert.

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
        )

        self.coding_agent = ChatAgent(
            name="CodingAgent",
            description="Implements code based on the plan",
            chat_client=self.coding_client,
            system_message="""You are an expert software engineer.

Your role is to implement the SPECIFIC task given to you.

OUTPUT FORMAT (strictly follow this format):
Output a code block with filename:

```language filename.ext
// code here
```

Example:
```python main.py
def hello():
    print("Hello, World!")
```

Rules:
- Focus ONLY on the current task
- One code block per file
- Include the filename after the language
- Write complete, runnable code
- If updating existing code, include the full updated file
- Do NOT include explanations outside code blocks"""
        )

        self.review_agent = ChatAgent(
            name="ReviewAgent",
            description="Reviews and improves the generated code",
            chat_client=self.coding_client,
            system_message="""You are a senior code reviewer.

Your role is to review the code and provide structured feedback.

OUTPUT FORMAT (strictly follow this format):

## Issues
- Issue: [description of problem]
- Issue: [description of problem]

## Suggestions
- Suggest: [improvement recommendation]
- Suggest: [improvement recommendation]

## Status
[APPROVED or NEEDS_REVISION]

If code changes are needed, include the corrected code block:
```language filename.ext
// corrected code
```

Keep feedback concise. Only list actual issues found."""
        )

        # Build the sequential workflow
        self.workflow = (
            WorkflowBuilder()
            .add_agent(self.planning_agent)
            .add_agent(self.coding_agent)
            .add_agent(self.review_agent)
            .set_start_executor(self.planning_agent)
            .add_edge(self.planning_agent, self.coding_agent)
            .add_edge(self.coding_agent, self.review_agent)
            .build()
        )

        logger.info("CodingWorkflow (Microsoft) initialized with 3 agents")

    async def execute(
        self,
        user_request: str,
        context: Optional[AgentRunContext] = None
    ) -> str:
        """Execute the coding workflow.

        Args:
            user_request: User's coding request
            context: Optional run context

        Returns:
            Final result from the workflow
        """
        logger.info(f"Executing workflow for request: {user_request[:100]}...")

        # Create initial message
        initial_message = ChatMessage(role="user", text=user_request)

        # Run the workflow
        result = await self.workflow.run(
            input=initial_message,
            context=context
        )

        return result

    async def execute_stream(
        self,
        user_request: str,
        context: Optional[AgentRunContext] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute the workflow with streaming updates.

        Each agent yields updates to a single message box that gets updated in place.
        Frontend should replace (not append) content when receiving same agent updates.

        Args:
            user_request: User's coding request
            context: Optional run context

        Yields:
            Updates with consistent structure per agent:
            - type: "streaming" = content is being updated (replace previous)
            - type: "completed" = final result for this agent
        """
        logger.info(f"Streaming workflow for request: {user_request[:100]}...")

        initial_message = ChatMessage(role="user", text=user_request)

        def extract_text_from_update(update: ChatResponseUpdate) -> str:
            """Extract text content from ChatResponseUpdate."""
            text_parts = []
            for content in update.contents:
                if isinstance(content, TextContent) and content.text:
                    text_parts.append(content.text)
            return "".join(text_parts)

        try:
            # Step 1: Planning - show status, then result
            yield {
                "agent": "PlanningAgent",
                "type": "thinking",
                "status": "running",
                "message": "Analyzing requirements..."
            }

            plan_text = ""
            async for update in self.planning_agent.run_stream(initial_message):
                chunk_text = extract_text_from_update(update)
                if chunk_text:
                    plan_text += chunk_text

            # Parse and yield final checklist
            checklist_items = parse_checklist(plan_text)
            yield {
                "agent": "PlanningAgent",
                "type": "completed",
                "status": "completed",
                "items": checklist_items
            }

            # Step 2: Coding - iterate through each task
            all_artifacts = []
            code_text = ""

            # Track existing code for context
            existing_code_context = ""

            for task_idx, task_item in enumerate(checklist_items):
                task_num = task_idx + 1
                task_description = task_item["task"]

                # Show which task we're working on
                yield {
                    "agent": "CodingAgent",
                    "type": "thinking",
                    "status": "running",
                    "message": f"Task {task_num}/{len(checklist_items)}: {task_description}",
                    "checklist": checklist_items,
                    "completed_tasks": [
                        {
                            "task_num": i + 1,
                            "task": checklist_items[i]["task"],
                            "artifacts": checklist_items[i].get("artifacts", [])
                        }
                        for i in range(task_idx) if checklist_items[i]["completed"]
                    ]
                }

                # Build context message with existing code
                context_parts = [f"Original request: {user_request}"]
                context_parts.append(f"\nFull plan:\n{plan_text}")

                if existing_code_context:
                    context_parts.append(f"\nCode implemented so far:\n{existing_code_context}")

                context_parts.append(f"\nCurrent task ({task_num}/{len(checklist_items)}): {task_description}")
                context_parts.append("\nPlease implement this specific task now.")

                coding_message = ChatMessage(
                    role="user",
                    text="\n".join(context_parts)
                )

                # Execute this task
                task_code = ""
                code_parser = CodeBlockParser()
                task_artifacts = []  # Track artifacts for this specific task

                async for update in self.coding_agent.run_stream(coding_message):
                    chunk_text = extract_text_from_update(update)
                    if chunk_text:
                        task_code += chunk_text
                        code_text += chunk_text

                        # Check for completed code blocks
                        artifacts = code_parser.add_chunk(chunk_text)
                        for artifact in artifacts:
                            all_artifacts.append(artifact)
                            task_artifacts.append(artifact)
                            # Update existing code context
                            existing_code_context += f"\n\n```{artifact['language']} {artifact['filename']}\n{artifact['content']}\n```"

                            # Yield artifact immediately
                            yield {
                                "agent": "CodingAgent",
                                "type": "artifact",
                                "status": "running",
                                "message": f"Task {task_num}: Created {artifact['filename']}",
                                "artifact": artifact,
                                "checklist": checklist_items
                            }

                # Mark task as completed and store its artifacts
                checklist_items[task_idx]["completed"] = True
                checklist_items[task_idx]["artifacts"] = [a["filename"] for a in task_artifacts]

                # Build completed tasks list for display
                completed_tasks = [
                    {
                        "task_num": i + 1,
                        "task": checklist_items[i]["task"],
                        "artifacts": checklist_items[i].get("artifacts", [])
                    }
                    for i in range(task_idx + 1) if checklist_items[i]["completed"]
                ]

                # Yield task completion update with results
                yield {
                    "agent": "CodingAgent",
                    "type": "task_completed",
                    "status": "running",
                    "message": f"Task {task_num}/{len(checklist_items)}: {task_description}",
                    "task_result": {
                        "task_num": task_num,
                        "task": task_description,
                        "artifacts": task_artifacts
                    },
                    "checklist": checklist_items,
                    "completed_tasks": completed_tasks
                }

            # All tasks completed
            yield {
                "agent": "CodingAgent",
                "type": "completed",
                "status": "completed",
                "artifacts": all_artifacts,
                "checklist": checklist_items
            }

            # Step 3: Review - show status, then result
            review_message = ChatMessage(
                role="user",
                text=f"Please review this code:\n\n{code_text}"
            )

            yield {
                "agent": "ReviewAgent",
                "type": "thinking",
                "status": "running",
                "message": "Reviewing code..."
            }

            review_text = ""
            review_parser = CodeBlockParser()

            async for update in self.review_agent.run_stream(review_message):
                chunk_text = extract_text_from_update(update)
                if chunk_text:
                    review_text += chunk_text

            # Parse review and extract corrected artifacts
            review_result = parse_review(review_text)
            corrected_artifacts = []
            review_parser.buffer = review_text
            while True:
                artifacts = review_parser.add_chunk("")
                if not artifacts:
                    break
                corrected_artifacts.extend(artifacts)

            yield {
                "agent": "ReviewAgent",
                "type": "completed",
                "status": "completed",
                "issues": review_result["issues"],
                "suggestions": review_result["suggestions"],
                "approved": review_result["approved"],
                "corrected_artifacts": corrected_artifacts
            }

            # Final summary
            yield {
                "agent": "Workflow",
                "type": "completed",
                "status": "finished",
                "summary": {
                    "tasks_completed": sum(1 for item in checklist_items if item["completed"]),
                    "total_tasks": len(checklist_items),
                    "artifacts_count": len(all_artifacts),
                    "review_approved": review_result["approved"]
                }
            }

        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            yield {
                "agent": "Workflow",
                "type": "error",
                "status": "error",
                "message": str(e)
            }
            raise


class WorkflowManager(BaseWorkflowManager):
    """Manager for workflow-based coding sessions."""

    def __init__(self):
        """Initialize workflow manager."""
        self.workflows: Dict[str, CodingWorkflow] = {}
        logger.info("WorkflowManager (Microsoft) initialized")

    def get_or_create_workflow(self, session_id: str) -> CodingWorkflow:
        """Get existing workflow or create new one for session.

        Args:
            session_id: Session identifier

        Returns:
            CodingWorkflow instance
        """
        if session_id not in self.workflows:
            self.workflows[session_id] = CodingWorkflow()
            logger.info(f"Created new workflow for session {session_id}")
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
workflow_manager = WorkflowManager()
