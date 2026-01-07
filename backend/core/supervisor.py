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

# Add project root to path for shared module access
PROJECT_ROOT = Path(__file__).parent.parent.parent  # backend/core -> backend -> project_root
sys.path.insert(0, str(PROJECT_ROOT))

# Add backend to path for app module access
BACKEND_ROOT = Path(__file__).parent.parent  # backend/core -> backend
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.vllm_client import vllm_router
from app.core.config import settings

# Import model-specific prompts
from shared.prompts.deepseek_r1 import (
    DEEPSEEK_R1_SYSTEM_PROMPT,
    DEEPSEEK_R1_CONFIG,
)
from shared.prompts.gpt_oss import (
    GPT_OSS_SYSTEM_PROMPT,
    GPT_OSS_SUPERVISOR_PROMPT,
    GPT_OSS_PLANNING_PROMPT,
    GPT_OSS_QA_PROMPT,
    GPT_OSS_CONFIG,
)

logger = logging.getLogger(__name__)


class TaskComplexity:
    """Task complexity levels"""
    SIMPLE = "simple"  # Single agent, no loops
    MODERATE = "moderate"  # Multiple agents, basic loop
    COMPLEX = "complex"  # All gates, refinement loops
    CRITICAL = "critical"  # All gates, security, human approval


class ResponseType:
    """Response type - determines workflow routing"""
    QUICK_QA = "quick_qa"  # Simple Q&A - supervisor responds directly
    PLANNING = "planning"  # Planning/design - supervisor with detailed analysis
    CODE_GENERATION = "code_generation"  # Full pipeline - all agents
    CODE_REVIEW = "code_review"  # Review existing code
    DEBUGGING = "debugging"  # Debug/fix issues


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

    This agent uses LLM reasoning to:
    1. Understand user intent
    2. Assess task complexity
    3. Determine required agents
    4. Build dynamic workflow DAG
    5. Monitor execution and adjust as needed

    Supports multiple LLM backends:
    - DeepSeek-R1: Uses <think></think> tags for reasoning
    - GPT-OSS: Uses Harmony format without <think> tags
    - Qwen: Standard prompting
    """

    def __init__(self, use_api: bool = True):
        """Initialize Supervisor Agent

        Args:
            use_api: Whether to use LLM API (True) or rule-based fallback (False)
        """
        # Detect model type from settings
        self.model_type = settings.get_reasoning_model_type
        logger.info(f"🔍 Detected reasoning model type: {self.model_type}")

        # Select appropriate prompts based on model type
        if self.model_type == "gpt-oss":
            self.system_prompt = GPT_OSS_SYSTEM_PROMPT
            self.analysis_prompt = GPT_OSS_SUPERVISOR_PROMPT
            self.planning_prompt = GPT_OSS_PLANNING_PROMPT
            self.qa_prompt = GPT_OSS_QA_PROMPT
            self.config = GPT_OSS_CONFIG
            self.uses_think_tags = False
        elif self.model_type == "deepseek":
            self.system_prompt = DEEPSEEK_R1_SYSTEM_PROMPT
            self.analysis_prompt = SUPERVISOR_ANALYSIS_PROMPT
            self.planning_prompt = None  # Use default
            self.qa_prompt = None
            self.config = DEEPSEEK_R1_CONFIG
            self.uses_think_tags = True
        else:
            # Generic/Qwen - use GPT-OSS style (no think tags)
            self.system_prompt = GPT_OSS_SYSTEM_PROMPT
            self.analysis_prompt = GPT_OSS_SUPERVISOR_PROMPT
            self.planning_prompt = GPT_OSS_PLANNING_PROMPT
            self.qa_prompt = GPT_OSS_QA_PROMPT
            self.config = GPT_OSS_CONFIG
            self.uses_think_tags = False

        self.use_api = use_api
        self._thinking_pattern = re.compile(r'<think>(.*?)</think>', re.DOTALL)
        self._json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
        logger.info(f"✅ Supervisor Agent initialized (API mode: {use_api}, model: {self.model_type})")

    def _strip_think_tags(self, text: str) -> str:
        """Remove <think></think> tags from text

        For models that don't use think tags (GPT-OSS, Qwen),
        we strip any accidental <think> content from output.

        Args:
            text: Text that may contain think tags

        Returns:
            Clean text without think tags
        """
        if not text:
            return ""

        # Remove <think>...</think> blocks entirely
        clean = self._thinking_pattern.sub('', text)
        # Clean up any extra whitespace
        clean = re.sub(r'\n\s*\n\s*\n', '\n\n', clean)
        return clean.strip()

    def _format_context_harmony(self, context: Dict) -> str:
        """Format context in Harmony-style structured format

        OpenAI Harmony format emphasizes structured, hierarchical context presentation
        for better LLM comprehension, especially for GPT-OSS models.

        Args:
            context: Context dictionary with conversation_history, system_prompt, etc.

        Returns:
            Formatted context string in Harmony format
        """
        if not context:
            return "No previous context available."

        formatted_parts = []

        # Add system context if available
        if context.get("system_prompt"):
            formatted_parts.append(f"### System Context\n{context['system_prompt']}\n")

        # Format conversation history (EXPANDED from 6 to 20 messages)
        if context.get("conversation_history"):
            history = context["conversation_history"]
            formatted_parts.append(f"### Conversation History ({len(history)} messages)\n")

            # Take recent messages (already expanded in dynamic_workflow.py)
            for i, msg in enumerate(history, 1):
                role = "USER" if msg.get("role") == "user" else "ASSISTANT"
                content = msg.get("content", "")

                # Truncate if too long (already expanded to 1000 chars)
                if len(content) > 1000:
                    content = content[:1000] + "..."

                formatted_parts.append(f"**[{i}] {role}**: {content}\n")

        # Add turn count
        if context.get("turn_count"):
            formatted_parts.append(f"\n**Total Turns**: {context['turn_count']}\n")

        return "\n".join(formatted_parts) if formatted_parts else "No previous context available."

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
                # Get reasoning client
                client = vllm_router.get_client("reasoning")

                # Build prompt using model-appropriate template with Harmony format
                # Format conversation history in structured way
                context_formatted = self._format_context_harmony(context) if context else "No previous context available."

                prompt = self.analysis_prompt.format(
                    user_request=user_request,
                    context=context_formatted
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
                    temperature=self.config.get("temperature", 0.7),
                    max_tokens=self.config.get("max_tokens", 8000)
                ):
                    full_response += chunk

                    # Only process <think> tags if model uses them (DeepSeek)
                    if self.uses_think_tags:
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

                logger.info(f"✅ API Analysis Complete (model: {self.model_type})")

            except Exception as e:
                logger.warning(f"⚠️ LLM API call failed: {e}, falling back to rule-based")
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

        # Strip <think> tags from response if model doesn't use them
        clean_response = response
        if not self.uses_think_tags:
            clean_response = self._strip_think_tags(response)

        # Extract JSON from response
        json_match = self._json_pattern.search(clean_response)

        if json_match:
            try:
                parsed = json.loads(json_match.group(1))

                # Clean reasoning - strip think tags if present
                reasoning = "\n".join(thinking_blocks) if thinking_blocks else ""
                if not self.uses_think_tags:
                    reasoning = self._strip_think_tags(reasoning)
                    # For GPT-OSS, use analysis_summary as reasoning if available
                    if parsed.get("analysis_summary"):
                        reasoning = parsed["analysis_summary"]

                return {
                    "user_request": user_request,
                    "timestamp": datetime.utcnow().isoformat(),
                    "response_type": parsed.get("response_type", self._determine_response_type(user_request)),
                    "complexity": parsed.get("complexity", TaskComplexity.MODERATE),
                    "task_type": parsed.get("task_type", "general"),
                    "required_agents": parsed.get("required_agents", [AgentCapability.IMPLEMENTATION]),
                    "workflow_strategy": parsed.get("workflow_strategy", "parallel_gates"),
                    "max_iterations": parsed.get("max_iterations", 5),
                    "requires_human_approval": parsed.get("requires_human_approval", False),
                    "reasoning": reasoning,
                    "thinking_blocks": thinking_blocks if self.uses_think_tags else [],
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
        response_type = self._determine_response_type(request)
        return {
            "user_request": request,
            "timestamp": datetime.utcnow().isoformat(),
            "response_type": response_type,  # NEW: determines workflow routing
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

    def _determine_response_type(self, request: str) -> str:
        """Determine how to respond to this request

        This is the KEY routing decision - determines if we need:
        - quick_qa: Simple answer, no code generation
        - planning: Detailed plan/design, no code yet
        - code_generation: Full pipeline with all agents
        - code_review: Review existing code
        - debugging: Fix/debug issues

        Args:
            request: User request

        Returns:
            Response type string
        """
        request_lower = request.lower()

        # 1. Q&A patterns - simple questions that don't need code
        qa_patterns = [
            # Korean
            "뭐야", "뭔가요", "무엇", "알려줘", "설명해", "어떻게 동작",
            "왜", "차이점", "비교", "장단점", "추천", "조언",
            # English
            "what is", "what are", "how does", "why", "explain",
            "difference between", "compare", "pros and cons",
            "recommend", "advice", "tell me about",
        ]
        if any(p in request_lower for p in qa_patterns) and not self._has_code_intent(request_lower):
            return ResponseType.QUICK_QA

        # 2. Planning/Design patterns - detailed analysis, no code yet
        planning_patterns = [
            # Korean
            "계획", "설계", "아키텍처", "구조", "방법론", "전략",
            "어떻게 만들", "어떻게 구현", "방향",
            # English
            "plan", "design", "architecture", "structure", "strategy",
            "how should i", "how would you", "approach", "methodology",
        ]
        if any(p in request_lower for p in planning_patterns):
            return ResponseType.PLANNING

        # 3. Code Review patterns
        review_patterns = [
            # Korean
            "리뷰", "검토", "분석해", "확인해", "문제 있", "개선",
            # English
            "review", "check", "analyze", "look at", "improve", "refactor",
        ]
        # Fixed: Proper operator precedence with parentheses
        if any(p in request_lower for p in review_patterns) and ("코드" in request_lower or "code" in request_lower):
            return ResponseType.CODE_REVIEW

        # 4. Debugging patterns
        debug_patterns = [
            # Korean
            "오류", "에러", "버그", "수정", "안돼", "안됨", "왜 안",
            "문제", "고쳐", "디버그",
            # English
            "error", "bug", "fix", "doesn't work", "not working", "debug",
            "issue", "problem", "broken",
        ]
        if any(p in request_lower for p in debug_patterns):
            return ResponseType.DEBUGGING

        # 5. Code Generation - explicit code creation requests
        code_patterns = [
            # Korean - verb stems to match various conjugations
            # 만들다: 만들어, 만들고, 만드는, 만들 -> use "만들" or "만드"
            "만들", "만드",  # covers 만들어, 만들고, 만드는, etc.
            "구현",  # covers 구현해, 구현하고, 구현할
            "작성",  # covers 작성해, 작성하고, 작성할
            "개발",  # covers 개발해, 개발하고, 개발할
            "생성",  # covers 생성해, 생성하고, 생성할
            "추가",  # covers 추가해, 추가하고, 추가할
            "코드",
            # Intent patterns
            "싶습니다", "싶어요", "싶어", "원합니다", "원해요", "원해",
            "해줘", "해주세요", "해 줘", "해 주세요",
            # English
            "create", "implement", "write", "develop", "code",
            "generate", "build", "make",
        ]
        if any(p in request_lower for p in code_patterns):
            return ResponseType.CODE_GENERATION

        # Default: If unclear, use planning to clarify
        return ResponseType.PLANNING

    def _has_code_intent(self, request_lower: str) -> bool:
        """Check if request has intent to generate code

        Uses verb stems to match various Korean conjugations.
        """
        code_intent_words = [
            # Korean - verb stems
            "만들", "만드", "구현", "작성", "개발", "코드",
            "생성", "추가",
            # Intent patterns
            "싶습니다", "싶어요", "싶어", "원합니다", "원해요", "원해",
            "해줘", "해주세요",
            # English
            "create", "implement", "write", "develop", "generate code",
            "build", "make a", "code for",
        ]
        return any(w in request_lower for w in code_intent_words)

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

        Model-aware: Uses <think> tags only for DeepSeek-R1
        """
        complexity = self._assess_complexity(request)
        task_type = self._determine_task_type(request)
        agents = self._determine_required_agents(request)

        # Build reasoning content
        analysis_content = f"""1. Request Analysis:
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
   - Enable refinement loops if needed"""

        # Format based on model type
        if self.uses_think_tags:
            # DeepSeek-R1: Use <think> tags
            reasoning = f"""<think>
{analysis_content}
</think>

Strategy: {self._build_workflow_strategy(request)} approach with {len(agents)} agents."""
        else:
            # GPT-OSS/Qwen: Structured format without <think> tags
            reasoning = f"""## Analysis

{analysis_content}

**Strategy:** {self._build_workflow_strategy(request)} approach with {len(agents)} agents."""

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
