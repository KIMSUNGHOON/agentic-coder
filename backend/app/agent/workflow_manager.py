"""Workflow-based coding agent using Microsoft Agent Framework."""
import logging
from typing import List, Dict, Any, AsyncGenerator, Optional
from agent_framework import (
    WorkflowBuilder,
    ChatAgent,
    AgentRunContext,
    ChatMessage,
    BaseChatClient,
)
from app.services.vllm_client import vllm_router

logger = logging.getLogger(__name__)


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
    ) -> str:
        """Get a non-streaming response from vLLM.

        Args:
            messages: List of chat messages
            **kwargs: Additional arguments (temperature, max_tokens, etc.)

        Returns:
            Response content as string
        """
        # Convert ChatMessage to dict format for vLLM
        vllm_messages = [
            {"role": msg.role, "content": msg.text}
            for msg in messages
        ]

        response = await self.vllm_client.chat_completion(
            messages=vllm_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
            stream=False
        )

        return response.choices[0].message.content

    async def _inner_get_streaming_response(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Get a streaming response from vLLM.

        Args:
            messages: List of chat messages
            **kwargs: Additional arguments (temperature, max_tokens, etc.)

        Yields:
            Chunks of response content
        """
        # Convert ChatMessage to dict format for vLLM
        vllm_messages = [
            {"role": msg.role, "content": msg.text}
            for msg in messages
        ]

        async for chunk in self.vllm_client.stream_chat_completion(
            messages=vllm_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048)
        ):
            yield chunk


class CodingWorkflow:
    """Multi-agent coding workflow: Planning -> Coding -> Review."""

    def __init__(self):
        """Initialize the coding workflow."""
        # Create chat clients for each model
        self.reasoning_client = VLLMChatClient("reasoning")
        self.coding_client = VLLMChatClient("coding")

        # Create agents
        self.planning_agent = ChatAgent(
            name="PlanningAgent",
            description="Analyzes requirements and creates implementation plan",
            chat_client=self.reasoning_client,
            system_message="""You are a software architect and planning expert.
Your role is to:
1. Analyze the user's coding request carefully
2. Break down the problem into clear, actionable steps
3. Create a detailed implementation plan
4. Identify potential challenges and edge cases

Output your plan in a structured format with numbered steps."""
        )

        self.coding_agent = ChatAgent(
            name="CodingAgent",
            description="Implements code based on the plan",
            chat_client=self.coding_client,
            system_message="""You are an expert software engineer.
Your role is to:
1. Follow the implementation plan provided
2. Write clean, efficient, and well-documented code
3. Use best practices and design patterns
4. Include error handling and edge cases

Output the complete, runnable code with comments."""
        )

        self.review_agent = ChatAgent(
            name="ReviewAgent",
            description="Reviews and improves the generated code",
            chat_client=self.coding_client,
            system_message="""You are a senior code reviewer.
Your role is to:
1. Review the code for bugs, security issues, and performance problems
2. Check code quality, readability, and maintainability
3. Suggest improvements and optimizations
4. Verify that the code follows best practices

Output:
- List of issues found (if any)
- Improved code (if needed)
- Final approval or recommendations"""
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

        logger.info("CodingWorkflow initialized with 3 agents")

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
        initial_message = ChatMessage(role="user", content=user_request)

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

        Args:
            user_request: User's coding request
            context: Optional run context

        Yields:
            Dict with 'agent', 'status', 'content' keys
        """
        logger.info(f"Streaming workflow for request: {user_request[:100]}...")

        # Create initial message
        initial_message = ChatMessage(role="user", content=user_request)

        # For now, we'll execute each step and yield progress
        # TODO: Implement proper streaming when agent-framework supports it

        try:
            # Step 1: Planning
            yield {
                "agent": "PlanningAgent",
                "status": "running",
                "content": "🔍 Analyzing requirements and creating plan..."
            }

            plan_result = await self.planning_agent.run(initial_message)
            yield {
                "agent": "PlanningAgent",
                "status": "completed",
                "content": plan_result
            }

            # Step 2: Coding
            yield {
                "agent": "CodingAgent",
                "status": "running",
                "content": "💻 Generating code based on plan..."
            }

            # Pass plan to coding agent
            coding_message = ChatMessage(
                role="user",
                content=f"Based on this plan:\n\n{plan_result}\n\nPlease implement the code."
            )
            code_result = await self.coding_agent.run(coding_message)

            yield {
                "agent": "CodingAgent",
                "status": "completed",
                "content": code_result
            }

            # Step 3: Review
            yield {
                "agent": "ReviewAgent",
                "status": "running",
                "content": "🔎 Reviewing and improving code..."
            }

            # Pass code to review agent
            review_message = ChatMessage(
                role="user",
                content=f"Please review this code:\n\n{code_result}"
            )
            review_result = await self.review_agent.run(review_message)

            yield {
                "agent": "ReviewAgent",
                "status": "completed",
                "content": review_result
            }

            # Final result
            yield {
                "agent": "Workflow",
                "status": "finished",
                "content": f"✅ Workflow completed!\n\n**Final Code:**\n{code_result}\n\n**Review:**\n{review_result}"
            }

        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            yield {
                "agent": "Workflow",
                "status": "error",
                "content": f"❌ Error: {str(e)}"
            }
            raise


class WorkflowManager:
    """Manager for workflow-based coding sessions."""

    def __init__(self):
        """Initialize workflow manager."""
        self.workflows: Dict[str, CodingWorkflow] = {}
        logger.info("WorkflowManager initialized")

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

    def delete_workflow(self, session_id: str):
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
