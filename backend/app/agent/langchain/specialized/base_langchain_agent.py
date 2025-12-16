"""Base class for LangChain specialized agents with tool usage via LangGraph."""
import logging
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from abc import ABC, abstractmethod
from dataclasses import dataclass
from operator import add

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.agent.langchain.tool_adapter import get_langchain_tools, LangChainToolAdapter

logger = logging.getLogger(__name__)


@dataclass
class LangChainAgentCapabilities:
    """Defines what a LangChain agent can do."""
    can_use_tools: bool = True
    allowed_tools: Optional[List[str]] = None  # None = all tools allowed
    can_spawn_agents: bool = False
    max_iterations: int = 5
    model_type: str = "coding"  # "reasoning" or "coding"


class AgentState(TypedDict):
    """State maintained throughout agent execution."""
    messages: Annotated[List, add]
    task: str
    context: Dict[str, Any]
    iteration: int
    result: Optional[Dict[str, Any]]


class BaseLangChainAgent(ABC):
    """
    Base class for LangChain specialized agents with tool usage.

    Uses LangGraph for ReAct-style tool usage with automatic iteration control.
    """

    def __init__(
        self,
        agent_type: str,
        capabilities: LangChainAgentCapabilities,
        session_id: str
    ):
        """Initialize LangChain specialized agent.

        Args:
            agent_type: Type identifier (research, testing, etc.)
            capabilities: Agent capabilities configuration
            session_id: Session identifier
        """
        self.agent_type = agent_type
        self.capabilities = capabilities
        self.session_id = session_id
        self.history: List[Dict] = []

        # Initialize LLM based on model type
        if capabilities.model_type == "reasoning":
            self.llm = ChatOpenAI(
                base_url=settings.vllm_reasoning_endpoint,
                model=settings.reasoning_model,
                temperature=0.7,
                max_tokens=2048,
                api_key="not-needed",
            )
        else:
            self.llm = ChatOpenAI(
                base_url=settings.vllm_coding_endpoint,
                model=settings.coding_model,
                temperature=0.7,
                max_tokens=2048,
                api_key="not-needed",
            )

        # Initialize tools
        self.tools: List[LangChainToolAdapter] = []
        if capabilities.can_use_tools:
            self.tools = get_langchain_tools(
                session_id=session_id,
                tool_names=capabilities.allowed_tools
            )
            # Bind tools to LLM
            if self.tools:
                self.llm_with_tools = self.llm.bind_tools(self.tools)
            else:
                self.llm_with_tools = self.llm
        else:
            self.llm_with_tools = self.llm

        # Build the agent graph
        self.graph = self._build_graph()

        logger.info(
            f"Initialized LangChain {agent_type} agent for session {session_id} "
            f"with {len(self.tools)} tools"
        )

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph agent graph."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("agent", self._agent_node)
        if self.tools:
            graph.add_node("tools", ToolNode(self.tools))

        # Add edges
        graph.add_edge(START, "agent")

        if self.tools:
            # Conditional edge: if tool calls, go to tools; else end
            graph.add_conditional_edges(
                "agent",
                self._should_continue,
                {
                    "tools": "tools",
                    "end": END
                }
            )
            graph.add_edge("tools", "agent")
        else:
            graph.add_edge("agent", END)

        return graph.compile()

    def _should_continue(self, state: AgentState) -> str:
        """Determine if we should continue to tools or end."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None

        # Check iteration limit
        if state["iteration"] >= self.capabilities.max_iterations:
            logger.info(f"Max iterations ({self.capabilities.max_iterations}) reached")
            return "end"

        # Check if last message has tool calls
        if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        return "end"

    async def _agent_node(self, state: AgentState) -> Dict[str, Any]:
        """Agent reasoning node."""
        messages = state["messages"]

        # Add system prompt if first iteration
        if state["iteration"] == 0:
            system_msg = SystemMessage(content=self.get_system_prompt())
            messages = [system_msg] + messages

        # Call LLM
        response = await self.llm_with_tools.ainvoke(messages)

        return {
            "messages": [response],
            "iteration": state["iteration"] + 1
        }

    async def process(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a task and return results.

        Args:
            task: Task description
            context: Additional context (files, data, etc.)

        Returns:
            Processing results
        """
        context = context or {}

        # Build initial message
        task_message = f"Task: {task}"
        if context:
            task_message += f"\n\nContext:\n{self._format_context(context)}"

        initial_state = AgentState(
            messages=[HumanMessage(content=task_message)],
            task=task,
            context=context,
            iteration=0,
            result=None
        )

        # Run the graph
        try:
            final_state = await self.graph.ainvoke(initial_state)

            # Extract result from final message
            messages = final_state["messages"]
            final_message = messages[-1] if messages else None

            result = {
                "task": task,
                "success": True,
                "iterations": final_state["iteration"],
                "response": final_message.content if final_message else "",
                "tool_calls": self._extract_tool_calls(messages),
            }

            # Update history
            self.add_to_history("user", task)
            self.add_to_history("assistant", result["response"])

            return result

        except Exception as e:
            logger.error(f"Error processing task: {e}")
            return {
                "task": task,
                "success": False,
                "error": str(e),
                "iterations": 0,
                "response": "",
                "tool_calls": []
            }

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary as string."""
        lines = []
        for key, value in context.items():
            if isinstance(value, (dict, list)):
                import json
                value = json.dumps(value, indent=2, ensure_ascii=False)
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _extract_tool_calls(self, messages: List) -> List[Dict]:
        """Extract tool calls from message history."""
        tool_calls = []
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {}),
                    })
        return tool_calls

    def add_to_history(self, role: str, content: str):
        """Add a message to agent's history."""
        self.history.append({
            "role": role,
            "content": content
        })

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Get recent history."""
        return self.history[-limit:]

    def clear_history(self):
        """Clear agent history."""
        self.history = []
        logger.debug(f"Cleared history for {self.agent_type} agent")

    def to_dict(self) -> Dict:
        """Serialize agent to dictionary."""
        return {
            "agent_type": self.agent_type,
            "framework": "langchain",
            "session_id": self.session_id,
            "capabilities": {
                "can_use_tools": self.capabilities.can_use_tools,
                "allowed_tools": self.capabilities.allowed_tools,
                "can_spawn_agents": self.capabilities.can_spawn_agents,
                "max_iterations": self.capabilities.max_iterations,
                "model_type": self.capabilities.model_type,
            },
            "tools": [t.name for t in self.tools],
            "history_length": len(self.history)
        }
