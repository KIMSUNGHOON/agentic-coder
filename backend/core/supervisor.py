"""Supervisor Agent - The Strategist

This is the orchestrator that analyzes user requests and dynamically
constructs workflows based on task complexity and requirements.

Uses DeepSeek-R1 for reasoning and planning via vLLM API.
"""

import asyncio
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

# Import vLLM client for DeepSeek-R1
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.vllm_client import vllm_router

# Import DeepSeek-R1 prompts
from shared.prompts.deepseek_r1 import (
    DEEPSEEK_R1_SYSTEM_PROMPT,
    DEEPSEEK_R1_CONFIG,
)

logger = logging.getLogger(__name__)


class TaskComplexity:
    """Task complexity levels"""
    SIMPLE = "simple"  # Single agent, no loops
    MODERATE = "moderate"  # Multiple agents, basic loop
    COMPLEX = "complex"  # All gates, refinement loops
    CRITICAL = "critical"  # All gates, security, human approval


class AgentCapability:
    """Agent capabilities"""
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    SECURITY = "security"
    TESTING = "testing"
    REFINEMENT = "refinement"
    RCA = "root_cause_analysis"


@dataclass
class ThinkingBlock:
    """Parsed thinking block from DeepSeek-R1"""
    content: str
    step_number: int = 0
    is_complete: bool = False


@dataclass
class SupervisorAnalysis:
    """Result of supervisor analysis"""
    user_request: str
    timestamp: str
    complexity: str
    task_type: str
    required_agents: List[str]
    workflow_strategy: str
    max_iterations: int
    requires_human_approval: bool
    reasoning: str
    thinking_blocks: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    api_used: bool = False  # True if DeepSeek-R1 API was used


# Supervisor Analysis Prompt for DeepSeek-R1
SUPERVISOR_ANALYSIS_PROMPT = """Analyze the following user request and determine the optimal workflow strategy.

USER REQUEST:
{user_request}

CONTEXT (if available):
{context}

ANALYSIS REQUIREMENTS:
1. Assess task complexity (simple, moderate, complex, critical)
2. Determine primary task type (implementation, review, testing, security_audit, general)
3. Identify required agent capabilities
4. Select optimal workflow strategy
5. Estimate maximum iterations needed
6. Determine if human approval is required

AVAILABLE STRATEGIES:
- linear: Simple sequential execution (for simple tasks)
- parallel_gates: Parallel quality gates (for moderate tasks)
- adaptive_loop: Dynamic refinement with RCA (for complex tasks)
- staged_approval: Includes human approval gates (for critical tasks)

AVAILABLE AGENT CAPABILITIES:
- planning: High-level task planning
- implementation: Code generation
- review: Code review
- security: Security analysis
- testing: Test generation and execution
- refinement: Code improvement
- root_cause_analysis: Deep problem analysis

Provide your analysis in the following JSON format AFTER your thinking:

```json
{{
    "complexity": "simple|moderate|complex|critical",
    "task_type": "implementation|review|testing|security_audit|general",
    "required_agents": ["agent1", "agent2"],
    "workflow_strategy": "linear|parallel_gates|adaptive_loop|staged_approval",
    "max_iterations": 5,
    "requires_human_approval": false,
    "confidence_score": 0.85
}}
```
"""


class SupervisorAgent:
    """The Strategist - Analyzes requests and orchestrates workflows

    This agent uses DeepSeek-R1 reasoning to:
    1. Understand user intent
    2. Assess task complexity
    3. Determine required agents
    4. Build dynamic workflow DAG
    5. Monitor execution and adjust as needed
    """

    def __init__(self, use_api: bool = True):
        """Initialize Supervisor Agent

        Args:
            use_api: Whether to use DeepSeek-R1 API (True) or rule-based fallback (False)
        """
        self.system_prompt = DEEPSEEK_R1_SYSTEM_PROMPT
        self.use_api = use_api
        self._thinking_pattern = re.compile(r'<think>(.*?)</think>', re.DOTALL)
        self._json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
        logger.info(f"✅ Supervisor Agent initialized (API mode: {use_api})")

    async def analyze_request_async(
        self,
        user_request: str,
        context: Optional[Dict] = None
    ) -> AsyncGenerator[Dict, None]:
        """Analyze user request asynchronously with streaming

        Uses DeepSeek-R1 reasoning with streaming <think> blocks.

        Args:
            user_request: User's input
            context: Optional context from previous interactions

        Yields:
            Analysis updates including thinking blocks
        """
        logger.info("🎯 Supervisor: Analyzing user request (async)...")
        logger.info(f"   Request: {user_request[:100]}...")

        thinking_buffer = []

        if self.use_api:
            try:
                # Get reasoning client for DeepSeek-R1
                client = vllm_router.get_client("reasoning")

                # Build prompt
                prompt = SUPERVISOR_ANALYSIS_PROMPT.format(
                    user_request=user_request,
                    context=str(context) if context else "None"
                )

                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ]

                # Stream response
                full_response = ""
                current_thinking = ""
                in_thinking_block = False

                async for chunk in client.stream_chat_completion(
                    messages=messages,
                    temperature=DEEPSEEK_R1_CONFIG["temperature"],
                    max_tokens=DEEPSEEK_R1_CONFIG["max_tokens"]
                ):
                    full_response += chunk

                    # Detect thinking blocks
                    if "<think>" in chunk:
                        in_thinking_block = True
                        current_thinking = ""

                    if in_thinking_block:
                        current_thinking += chunk

                        # Yield partial thinking for streaming UI
                        yield {
                            "type": "thinking",
                            "content": current_thinking,
                            "is_complete": False
                        }

                    if "</think>" in chunk:
                        in_thinking_block = False
                        thinking_buffer.append(current_thinking)

                        # Yield complete thinking block
                        yield {
                            "type": "thinking",
                            "content": current_thinking,
                            "is_complete": True
                        }

                # Parse final analysis
                analysis = self._parse_llm_response(full_response, user_request, thinking_buffer)
                analysis["api_used"] = True

                yield {
                    "type": "analysis",
                    "content": analysis
                }

                logger.info(f"✅ API Analysis Complete (DeepSeek-R1)")

            except Exception as e:
                logger.warning(f"⚠️ DeepSeek-R1 API call failed: {e}, falling back to rule-based")
                # Fallback to rule-based
                analysis = self._rule_based_analysis(user_request)
                yield {
                    "type": "analysis",
                    "content": analysis
                }
        else:
            # Use rule-based analysis
            analysis = self._rule_based_analysis(user_request)
            yield {
                "type": "analysis",
                "content": analysis
            }

    def analyze_request(
        self,
        user_request: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """Analyze user request synchronously (for backward compatibility)

        Uses rule-based analysis by default for sync calls.

        Args:
            user_request: User's input
            context: Optional context from previous interactions

        Returns:
            Analysis results with workflow plan
        """
        logger.info("🎯 Supervisor: Analyzing user request (sync)...")
        logger.info(f"   Request: {user_request[:100]}...")

        analysis = self._rule_based_analysis(user_request)

        logger.info(f"✅ Analysis Complete:")
        logger.info(f"   Complexity: {analysis['complexity']}")
        logger.info(f"   Task Type: {analysis['task_type']}")
        logger.info(f"   Required Agents: {len(analysis['required_agents'])}")
        logger.info(f"   Strategy: {analysis['workflow_strategy']}")

        return analysis

    def _parse_llm_response(
        self,
        response: str,
        user_request: str,
        thinking_blocks: List[str]
    ) -> Dict:
        """Parse LLM response to extract analysis

        Args:
            response: Full LLM response
            user_request: Original user request
            thinking_blocks: Collected thinking blocks

        Returns:
            Parsed analysis dict
        """
        import json

        # Extract JSON from response
        json_match = self._json_pattern.search(response)

        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                return {
                    "user_request": user_request,
                    "timestamp": datetime.utcnow().isoformat(),
                    "complexity": parsed.get("complexity", TaskComplexity.MODERATE),
                    "task_type": parsed.get("task_type", "general"),
                    "required_agents": parsed.get("required_agents", [AgentCapability.IMPLEMENTATION]),
                    "workflow_strategy": parsed.get("workflow_strategy", "parallel_gates"),
                    "max_iterations": parsed.get("max_iterations", 5),
                    "requires_human_approval": parsed.get("requires_human_approval", False),
                    "reasoning": "\n".join(thinking_blocks),
                    "thinking_blocks": thinking_blocks,
                    "confidence_score": parsed.get("confidence_score", 0.8),
                    "api_used": True
                }
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from LLM response")

        # Fallback to rule-based if parsing fails
        return self._rule_based_analysis(user_request, thinking_blocks)

    def _rule_based_analysis(
        self,
        request: str,
        thinking_blocks: Optional[List[str]] = None
    ) -> Dict:
        """Rule-based analysis fallback

        Args:
            request: User request
            thinking_blocks: Optional thinking blocks from failed API call

        Returns:
            Analysis dict
        """
        return {
            "user_request": request,
            "timestamp": datetime.utcnow().isoformat(),
            "complexity": self._assess_complexity(request),
            "task_type": self._determine_task_type(request),
            "required_agents": self._determine_required_agents(request),
            "workflow_strategy": self._build_workflow_strategy(request),
            "max_iterations": self._determine_max_iterations(request),
            "requires_human_approval": self._requires_human_approval(request),
            "reasoning": self._generate_reasoning(request),
            "thinking_blocks": thinking_blocks or [],
            "confidence_score": 0.7,  # Lower confidence for rule-based
            "api_used": False
        }

    def _assess_complexity(self, request: str) -> str:
        """Assess task complexity

        SIMPLE: Single file, clear requirements
        MODERATE: Multiple files, some ambiguity
        COMPLEX: Architecture changes, multiple components
        CRITICAL: Security-sensitive, production code
        """
        request_lower = request.lower()

        # Critical indicators
        if any(word in request_lower for word in [
            "production", "deploy", "critical", "security", "auth", "payment"
        ]):
            return TaskComplexity.CRITICAL

        # Complex indicators
        if any(word in request_lower for word in [
            "refactor", "architecture", "system", "integrate", "migrate"
        ]):
            return TaskComplexity.COMPLEX

        # Moderate indicators
        if any(word in request_lower for word in [
            "multiple", "several", "add and", "implement feature"
        ]):
            return TaskComplexity.MODERATE

        # Simple by default
        return TaskComplexity.SIMPLE

    def _determine_task_type(self, request: str) -> str:
        """Determine primary task type"""
        request_lower = request.lower()

        # Check in priority order
        if any(word in request_lower for word in ["test", "testing", "unit test"]):
            return "testing"
        elif any(word in request_lower for word in ["security", "vulnerability", "owasp"]):
            return "security_audit"
        elif any(word in request_lower for word in ["review", "check", "analyze"]):
            return "review"
        elif any(word in request_lower for word in ["implement", "create", "add", "build"]):
            return "implementation"
        else:
            return "general"

    def _determine_required_agents(self, request: str) -> List[str]:
        """Determine which agents are needed

        Returns list of agent capabilities required
        """
        request_lower = request.lower()
        required = []

        # Always need planning for complex tasks
        complexity = self._assess_complexity(request)
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.CRITICAL]:
            required.append(AgentCapability.PLANNING)

        # Implementation agent
        if any(word in request_lower for word in [
            "implement", "create", "add", "build", "write"
        ]):
            required.append(AgentCapability.IMPLEMENTATION)

        # Review agent (almost always needed)
        if complexity != TaskComplexity.SIMPLE:
            required.append(AgentCapability.REVIEW)

        # Security agent for critical tasks
        if complexity == TaskComplexity.CRITICAL or "security" in request_lower:
            required.append(AgentCapability.SECURITY)

        # Testing agent
        if "test" in request_lower or complexity == TaskComplexity.CRITICAL:
            required.append(AgentCapability.TESTING)

        # Refinement for moderate+ complexity
        if complexity in [TaskComplexity.MODERATE, TaskComplexity.COMPLEX, TaskComplexity.CRITICAL]:
            required.append(AgentCapability.REFINEMENT)

        # RCA for complex+ tasks
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.CRITICAL]:
            required.append(AgentCapability.RCA)

        return required or [AgentCapability.IMPLEMENTATION]  # At least one agent

    def _build_workflow_strategy(self, request: str) -> str:
        """Build workflow execution strategy

        Returns strategy name:
        - linear: Simple sequential execution
        - parallel_gates: Parallel quality gates
        - adaptive_loop: Dynamic refinement with RCA
        - staged_approval: Includes human approval gates
        """
        complexity = self._assess_complexity(request)

        if complexity == TaskComplexity.CRITICAL:
            return "staged_approval"
        elif complexity == TaskComplexity.COMPLEX:
            return "adaptive_loop"
        elif complexity == TaskComplexity.MODERATE:
            return "parallel_gates"
        else:
            return "linear"

    def _determine_max_iterations(self, request: str) -> int:
        """Determine maximum refinement iterations"""
        complexity = self._assess_complexity(request)

        iterations_map = {
            TaskComplexity.SIMPLE: 3,
            TaskComplexity.MODERATE: 5,
            TaskComplexity.COMPLEX: 7,
            TaskComplexity.CRITICAL: 10,
        }

        return iterations_map.get(complexity, 5)

    def _requires_human_approval(self, request: str) -> bool:
        """Check if human approval is required"""
        complexity = self._assess_complexity(request)
        request_lower = request.lower()

        # Always require approval for critical tasks
        if complexity == TaskComplexity.CRITICAL:
            return True

        # Require approval for sensitive operations
        if any(word in request_lower for word in [
            "delete", "drop", "truncate", "production", "deploy"
        ]):
            return True

        return False

    def _generate_reasoning(self, request: str) -> str:
        """Generate reasoning explanation

        In production, this would use DeepSeek-R1 <think> blocks
        """
        complexity = self._assess_complexity(request)
        task_type = self._determine_task_type(request)
        agents = self._determine_required_agents(request)

        reasoning = f"""<think>
1. Request Analysis:
   - Input: "{request[:100]}..."
   - Detected complexity: {complexity}
   - Primary task type: {task_type}

2. Required Capabilities:
   {chr(10).join(f"   - {agent}" for agent in agents)}

3. Workflow Strategy:
   - Complexity level requires {self._build_workflow_strategy(request)} strategy
   - Max iterations: {self._determine_max_iterations(request)}
   - Human approval: {self._requires_human_approval(request)}

4. Execution Plan:
   - Start with planning/analysis
   - Route to appropriate implementation agents
   - Apply quality gates based on complexity
   - Enable refinement loops if needed
</think>

Strategy: {self._build_workflow_strategy(request)} approach with {len(agents)} agents.
"""
        return reasoning

    async def adjust_workflow(
        self,
        current_state: Dict,
        failure_reason: str
    ) -> Dict:
        """Dynamically adjust workflow based on execution feedback

        Uses DeepSeek-R1 RCA to analyze failures and adjust strategy.

        Args:
            current_state: Current workflow state
            failure_reason: Reason for the adjustment

        Returns:
            Adjusted workflow parameters
        """
        logger.info(f"🔄 Supervisor: Adjusting workflow due to: {failure_reason}")

        # Use RCA to determine adjustment
        rca_result = await self._perform_rca(current_state, failure_reason)

        return {
            "adjusted": True,
            "reason": failure_reason,
            "rca_analysis": rca_result,
            "new_max_iterations": current_state.get("max_iterations", 5) + 2,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _perform_rca(
        self,
        state: Dict,
        failure_reason: str
    ) -> str:
        """Perform Root Cause Analysis using DeepSeek-R1

        Args:
            state: Current workflow state
            failure_reason: Failure description

        Returns:
            RCA analysis text
        """
        if not self.use_api:
            return f"Rule-based RCA: {failure_reason}"

        try:
            client = vllm_router.get_client("reasoning")

            from shared.prompts.deepseek_r1 import DEEPSEEK_R1_RCA_PROMPT

            prompt = DEEPSEEK_R1_RCA_PROMPT.format(
                error_description=failure_reason,
                current_state=str(state.get("workflow_status", "unknown")),
                expected_behavior="Successful completion",
                logs=str(state.get("error_log", []))[-1000:]
            )

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = await client.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"RCA API call failed: {e}")
            return f"RCA unavailable: {failure_reason}"


# Global supervisor instance (with API mode enabled by default)
supervisor = SupervisorAgent(use_api=True)
