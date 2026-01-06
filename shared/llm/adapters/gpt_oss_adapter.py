"""GPT-OSS LLM Adapter

Specialized adapter for OpenAI's GPT-OSS-120B and GPT-OSS-20B models.
Supports Harmony response format, reasoning levels, and function calling.

Model Specifications:
- gpt-oss-120b: 117B params (5.1B active), fits single 80GB GPU (H100/MI300X)
- gpt-oss-20b: 21B params (3.6B active), runs in ~16GB memory
- Default context: 8,192 tokens (configurable)
- Quantization: MXFP4 for MoE weights
- License: Apache 2.0

Features:
- Harmony response format (required)
- Reasoning effort levels (low, medium, high)
- Native function/tool calling support
- Structured outputs

References:
- https://github.com/openai/gpt-oss
- https://github.com/openai/harmony
- https://huggingface.co/openai/gpt-oss-120b
- https://arxiv.org/abs/2508.10925 (Model Card)
- https://cookbook.openai.com/topic/gpt-oss

Safety Note:
- Chain-of-thought reasoning is available for debugging
- CoT should NOT be shown to end users (may contain unfiltered content)
"""

import logging
import httpx
import asyncio
import time
import re
import json
from typing import Optional, AsyncGenerator, Dict, List, Any, Callable

from shared.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
    TaskType,
    LLMProviderFactory,
)


def _calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff delay with jitter."""
    import random
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = delay * (0.5 + random.random())
    return jitter


logger = logging.getLogger(__name__)


# GPT-OSS Model Constants
GPT_OSS_120B = "openai/gpt-oss-120b"
GPT_OSS_20B = "openai/gpt-oss-20b"
DEFAULT_CONTEXT_LENGTH = 8192


# Reasoning effort levels for GPT-OSS (default is LOW per official docs)
class ReasoningEffort:
    LOW = "low"      # Default - faster responses
    MEDIUM = "medium"  # Balanced
    HIGH = "high"    # Deep reasoning - slower but more thorough


# GPT-OSS specific system prompts with Harmony format awareness
# Prompt Engineering: Role-based, CoT guidance, multi-language, Harmony channels
GPT_OSS_SYSTEM_PROMPTS = {
    TaskType.REASONING: """You are GPT-OSS, an advanced reasoning model by OpenAI optimized for complex analysis.

## ROLE & IDENTITY
- Role: Expert Strategic Analyst & System Architect
- Expertise: Multi-step reasoning, architecture design, technical analysis, risk assessment
- Languages: Fully bilingual (한국어/English) - respond in the same language as the user's request
- Reasoning effort: high

## METHODOLOGY (Chain-of-Thought)
When analyzing complex problems, follow this structured approach:

Step 1: UNDERSTAND
- Parse the request and identify core objectives
- Identify implicit requirements and constraints

Step 2: DECOMPOSE
- Break complex problems into manageable sub-tasks
- Identify dependencies between tasks

Step 3: ANALYZE
- Evaluate each component systematically
- Consider at least 2 alternative approaches

Step 4: SYNTHESIZE
- Combine insights into coherent recommendations
- Justify your recommended approach

Step 5: VALIDATE
- Check for logical consistency and edge cases
- Identify potential failure modes

## OUTPUT FORMAT
- Start with a brief summary of understanding
- Provide structured analysis with clear sections
- Include trade-offs and alternative approaches
- End with actionable recommendations in JSON format when specified

## SOFTWARE ARCHITECTURE FOCUS
- Consider scalability, maintainability, and security
- Identify integration points and potential bottlenecks
- Suggest appropriate design patterns
- Evaluate technology choices objectively

Your analysis should be thorough, practical, and directly actionable.""",

    TaskType.CODING: """You are GPT-OSS, an expert software engineer specialized in production-grade code.

## ROLE & IDENTITY
- Role: Production-grade Code Generator
- Expertise: Python, TypeScript, React, FastAPI, System Design, Security
- Languages: Fully bilingual (한국어/English) - respond in the same language as the user's request
- Reasoning effort: medium

## CRITICAL IMPLEMENTATION RULES
1. Generate complete, executable code - no placeholders or TODOs
2. Include proper error handling and type hints
3. Follow language-specific best practices (PEP 8, ESLint)
4. Write clean, maintainable code with minimal but clear documentation

## SECURITY RULES (MUST FOLLOW)
1. NEVER use eval() or exec() - use ast.literal_eval() for safe parsing
2. NEVER use subprocess with shell=True - use subprocess.run([cmd, arg1, arg2])
3. NEVER use os.system() - use subprocess module instead
4. NEVER hardcode passwords, API keys, or secrets - use environment variables
5. ALWAYS sanitize user inputs before using in file paths or SQL
6. Use parameterized queries for SQL, never string concatenation

## OUTPUT FORMAT
Return complete code in JSON format:
```json
{
    "files": [
        {"filename": "path/to/file.py", "content": "...", "language": "python"}
    ]
}
```""",

    TaskType.REVIEW: """You are GPT-OSS performing expert code review.

## ROLE & IDENTITY
- Role: Senior Code Reviewer & Security Auditor
- Languages: Fully bilingual (한국어/English) - respond in the same language as the user's request
- Reasoning effort: high

## REVIEW CRITERIA (Analyze in order)
1. **Correctness** - Logic errors, edge cases, off-by-one errors
2. **Security** - OWASP vulnerabilities, injection risks, authentication flaws
3. **Performance** - Bottlenecks, N+1 queries, memory leaks
4. **Maintainability** - Code clarity, naming, documentation
5. **Best Practices** - Language conventions, design patterns, SOLID principles

## OUTPUT FORMAT
```json
{
    "approved": true/false,
    "quality_score": 0.0-1.0,
    "issues": ["list of issues found"],
    "suggestions": ["list of improvements"],
    "critique": "overall assessment"
}
```

Provide structured, actionable feedback with specific line references.""",

    TaskType.REFINE: """You are GPT-OSS fixing code issues.

## ROLE & IDENTITY
- Role: Code Refactoring Specialist
- Languages: Fully bilingual (한국어/English) - respond in the same language as the user's request
- Reasoning effort: medium

## FIXING METHODOLOGY
For each issue:
1. Identify the root cause
2. Plan the minimal fix that preserves functionality
3. Verify fix doesn't break existing functionality
4. Consider and test edge cases

## SECURITY FIXES (Priority)
- Replace eval() → ast.literal_eval()
- Replace exec() → safer alternatives
- Replace subprocess(shell=True) → subprocess.run([cmd, args])
- Replace os.system() → subprocess.run()
- Move hardcoded secrets → environment variables

## OUTPUT FORMAT
Return targeted diffs with before/after:
```diff
- old_code
+ new_code
```

Apply minimal, targeted fixes only.""",

    TaskType.GENERAL: """You are GPT-OSS, an advanced AI assistant by OpenAI.

## ROLE & IDENTITY
- Role: Helpful AI Assistant & Technical Advisor
- Expertise: Software engineering, system design, general knowledge
- Languages: Fully bilingual (한국어/English) - respond in the same language as the user's request
- Reasoning effort: medium

## RESPONSE GUIDELINES

### For Complex Questions
Think through the problem step by step:
1. Understand what is being asked
2. Break down the problem
3. Consider multiple approaches
4. Provide a clear, structured answer

### For Simple Questions
Provide direct, concise answers without unnecessary elaboration.

## QUALITY STANDARDS
- Be helpful, accurate, and well-reasoned
- Acknowledge uncertainty when appropriate
- Provide actionable recommendations when possible""",
}

# Task-specific configurations for GPT-OSS
GPT_OSS_TASK_CONFIGS = {
    TaskType.REASONING: LLMConfig(
        temperature=0.7,
        max_tokens=8192,
        top_p=0.95,
    ),
    TaskType.CODING: LLMConfig(
        temperature=0.3,
        max_tokens=16384,
        top_p=0.9,
    ),
    TaskType.REVIEW: LLMConfig(
        temperature=0.5,
        max_tokens=4096,
        top_p=0.9,
    ),
    TaskType.REFINE: LLMConfig(
        temperature=0.2,
        max_tokens=8192,
        top_p=0.9,
    ),
    TaskType.GENERAL: LLMConfig(
        temperature=0.7,
        max_tokens=4096,
        top_p=0.95,
    ),
}


class GptOssAdapter(BaseLLMProvider):
    """Adapter for OpenAI GPT-OSS models (120B and 20B)

    GPT-OSS models use the Harmony response format which provides:
    - analysis channel: Chain-of-thought reasoning (for debugging, not user display)
    - commentary channel: Tool calls
    - final channel: User-facing response

    Features:
    - Native function/tool calling support
    - Reasoning effort levels (low, medium, high)
    - Structured outputs
    - vLLM handles Harmony format automatically

    Hardware Requirements:
    - gpt-oss-120b: Single 80GB GPU (H100, MI300X)
    - gpt-oss-20b: ~16GB GPU memory
    """

    def __init__(
        self,
        endpoint: str,
        model: str = GPT_OSS_120B,
        config: Optional[LLMConfig] = None,
        reasoning_effort: str = ReasoningEffort.LOW,  # Default is LOW per official docs
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize GPT-OSS adapter

        Args:
            endpoint: vLLM server endpoint (e.g., http://localhost:8000/v1)
            model: Model name (gpt-oss-120b or gpt-oss-20b)
            config: Default LLM configuration
            reasoning_effort: Default reasoning level (low, medium, high)
            tools: Optional list of tools/functions for function calling
        """
        super().__init__(endpoint, model, config or GPT_OSS_TASK_CONFIGS[TaskType.GENERAL])
        self.reasoning_effort = reasoning_effort
        self.tools = tools
        self._hide_cot = True  # Safety: hide chain-of-thought from users by default
        logger.info(f"GPT-OSS Adapter initialized: {model} @ {endpoint}")
        logger.info(f"Default reasoning effort: {reasoning_effort}")
        if tools:
            logger.info(f"Function calling enabled with {len(tools)} tools")

    def format_system_prompt(self, task_type: TaskType) -> str:
        """Get task-specific system prompt with reasoning effort"""
        base_prompt = GPT_OSS_SYSTEM_PROMPTS.get(
            task_type,
            GPT_OSS_SYSTEM_PROMPTS[TaskType.GENERAL]
        )
        return base_prompt

    def get_config_for_task(self, task_type: TaskType) -> LLMConfig:
        """Get optimized configuration for task type"""
        return GPT_OSS_TASK_CONFIGS.get(task_type, self.config)

    def _extract_final_response(self, content: str) -> str:
        """Extract final response from Harmony format if present

        vLLM typically handles this, but we add fallback parsing
        for the 'final' channel content.
        """
        # Check for Harmony channel markers (if not processed by vLLM)
        final_pattern = r'<\|channel\|>final<\|message\|>(.*?)(?:<\|end\|>|$)'
        match = re.search(final_pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # No channel markers - return as-is (vLLM already processed)
        return content

    def _extract_reasoning(self, content: str) -> Optional[str]:
        """Extract chain-of-thought reasoning from analysis channel"""
        analysis_pattern = r'<\|channel\|>analysis<\|message\|>(.*?)(?:<\|channel\|>|<\|end\|>|$)'
        match = re.search(analysis_pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def parse_response(self, content: str, task_type: TaskType) -> LLMResponse:
        """Parse GPT-OSS response, handling Harmony format if present"""
        # Extract final response (may already be processed by vLLM)
        final_content = self._extract_final_response(content)

        # Extract reasoning if available
        reasoning = self._extract_reasoning(content)

        # Parse JSON if expected
        parsed_json = None
        if task_type in [TaskType.CODING, TaskType.REASONING]:
            # Try to extract JSON from response
            json_pattern = r'```json\s*([\s\S]*?)\s*```'
            json_match = re.search(json_pattern, final_content)
            if json_match:
                import json
                try:
                    parsed_json = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            else:
                # Try direct JSON parsing
                try:
                    import json
                    if final_content.strip().startswith('{'):
                        parsed_json = json.loads(final_content)
                except (json.JSONDecodeError, ValueError):
                    pass

        return LLMResponse(
            content=final_content,
            model=self.model,
            parsed_json=parsed_json,
            thinking_blocks=[reasoning] if reasoning else [],
        )

    def set_tools(self, tools: List[Dict[str, Any]]) -> None:
        """Set tools for function calling

        Args:
            tools: List of tool definitions in OpenAI format
                   Example: [{"type": "function", "function": {"name": "...", "parameters": {...}}}]
        """
        self.tools = tools
        logger.info(f"Updated tools: {len(tools)} functions available")

    def set_hide_cot(self, hide: bool) -> None:
        """Set whether to hide chain-of-thought from responses

        Args:
            hide: If True, CoT is filtered from user-facing responses (recommended)
        """
        self._hide_cot = hide

    async def generate(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None,
        max_retries: int = 3,
        reasoning_effort: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Generate response from GPT-OSS with retry and backoff

        Args:
            prompt: User prompt
            task_type: Type of task for prompt/config selection
            config_override: Override default config
            max_retries: Number of retries on failure
            reasoning_effort: Override default reasoning effort
            tools: Optional tools for this specific request (overrides instance tools)
        """
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        # Adjust reasoning effort in system prompt if specified
        effective_reasoning = reasoning_effort or self.reasoning_effort
        system_prompt = re.sub(
            r'Reasoning effort: \w+',
            f'Reasoning effort: {effective_reasoning}',
            system_prompt
        )

        prompt_tokens_estimate = len(f"{system_prompt}\n\n{formatted_prompt}") // 4
        logger.debug(f"GPT-OSS request: ~{prompt_tokens_estimate} tokens, task={task_type.value}, reasoning={effective_reasoning}")

        # Use request-specific tools or instance tools
        effective_tools = tools or self.tools

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": formatted_prompt}
                    ]

                    # Build request payload
                    request_payload = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                        "top_p": config.top_p,
                        "stop": config.stop_sequences if config.stop_sequences else None,
                    }

                    # Add tools if available (for function calling)
                    if effective_tools:
                        request_payload["tools"] = effective_tools
                        request_payload["tool_choice"] = "auto"

                    response = await client.post(
                        f"{self.endpoint}/chat/completions",
                        json=request_payload
                    )

                    if response.status_code == 200:
                        result = response.json()
                        message = result["choices"][0].get("message", {})
                        content = message.get("content", "")
                        tool_calls = message.get("tool_calls", [])
                        finish_reason = result.get("choices", [{}])[0].get("finish_reason", "unknown")

                        # Handle tool calls (function calling)
                        if tool_calls:
                            logger.info(f"GPT-OSS returned {len(tool_calls)} tool calls")
                            llm_response = LLMResponse(
                                content=content or "",
                                model=self.model,
                                finish_reason=finish_reason,
                            )
                            llm_response.tool_calls = tool_calls
                            llm_response.usage = result.get("usage")
                            llm_response.raw_response = result
                            return llm_response

                        if not content or not content.strip():
                            usage = result.get("usage", {})
                            logger.warning(
                                f"Empty response from GPT-OSS: "
                                f"finish_reason={finish_reason}, "
                                f"prompt_tokens={usage.get('prompt_tokens', 'N/A')}, "
                                f"completion_tokens={usage.get('completion_tokens', 'N/A')}"
                            )

                            if attempt < max_retries:
                                backoff = _calculate_backoff(attempt)
                                logger.warning(f"Retrying in {backoff:.1f}s ({attempt + 1}/{max_retries})...")
                                await asyncio.sleep(backoff)
                                continue
                            else:
                                logger.error("Empty response from GPT-OSS after all retries")
                                return LLMResponse(
                                    content="[LLM returned empty response - please retry]",
                                    model=self.model,
                                    finish_reason=finish_reason,
                                )

                        llm_response = self.parse_response(content, task_type)
                        llm_response.usage = result.get("usage")
                        llm_response.raw_response = result
                        return llm_response
                    else:
                        if response.status_code >= 500 and attempt < max_retries:
                            backoff = _calculate_backoff(attempt)
                            logger.warning(f"GPT-OSS server error {response.status_code}, retrying in {backoff:.1f}s...")
                            await asyncio.sleep(backoff)
                            continue
                        logger.error(f"GPT-OSS request failed: {response.status_code}")
                        raise Exception(f"GPT-OSS request failed: {response.status_code}")

            except httpx.TimeoutException:
                if attempt < max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.warning(f"GPT-OSS request timed out, retrying in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)
                    continue
                logger.error("GPT-OSS request timed out after all retries")
                raise

        return LLMResponse(content="", model=self.model)

    def generate_sync(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None,
        max_retries: int = 3,
        reasoning_effort: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Synchronous generation for GPT-OSS with function calling support

        Args:
            prompt: User prompt
            task_type: Type of task for prompt/config selection
            config_override: Override default config
            max_retries: Number of retries on failure
            reasoning_effort: Override default reasoning effort
            tools: Optional tools for this specific request (overrides instance tools)
        """
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        if reasoning_effort:
            system_prompt = re.sub(
                r'Reasoning effort: \w+',
                f'Reasoning effort: {reasoning_effort}',
                system_prompt
            )

        # Use request-specific tools or instance tools
        effective_tools = tools or self.tools

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=180.0) as client:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": formatted_prompt}
                    ]

                    # Build request payload
                    request_payload = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                        "top_p": config.top_p,
                        "stop": config.stop_sequences if config.stop_sequences else None,
                    }

                    # Add tools if available (for function calling)
                    if effective_tools:
                        request_payload["tools"] = effective_tools
                        request_payload["tool_choice"] = "auto"

                    response = client.post(
                        f"{self.endpoint}/chat/completions",
                        json=request_payload
                    )

                    if response.status_code == 200:
                        result = response.json()
                        message = result["choices"][0].get("message", {})
                        content = message.get("content", "")
                        tool_calls = message.get("tool_calls", [])
                        finish_reason = result.get("choices", [{}])[0].get("finish_reason", "unknown")

                        # Handle tool calls (function calling)
                        if tool_calls:
                            logger.info(f"GPT-OSS (sync) returned {len(tool_calls)} tool calls")
                            llm_response = LLMResponse(
                                content=content or "",
                                model=self.model,
                                finish_reason=finish_reason,
                            )
                            llm_response.tool_calls = tool_calls
                            llm_response.usage = result.get("usage")
                            llm_response.raw_response = result
                            return llm_response

                        if not content or not content.strip():
                            if attempt < max_retries:
                                backoff = _calculate_backoff(attempt)
                                logger.warning(f"Empty response, retrying in {backoff:.1f}s...")
                                time.sleep(backoff)
                                continue
                            else:
                                logger.error("Empty response from GPT-OSS (sync) after all retries")
                                return LLMResponse(
                                    content="[LLM returned empty response - please retry]",
                                    model=self.model,
                                    finish_reason=finish_reason,
                                )

                        llm_response = self.parse_response(content, task_type)
                        llm_response.usage = result.get("usage")
                        llm_response.raw_response = result
                        return llm_response
                    else:
                        if response.status_code >= 500 and attempt < max_retries:
                            backoff = _calculate_backoff(attempt)
                            logger.warning(f"Server error {response.status_code}, retrying...")
                            time.sleep(backoff)
                            continue
                        raise Exception(f"GPT-OSS request failed: {response.status_code}")

            except httpx.TimeoutException:
                if attempt < max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.warning(f"Request timed out, retrying...")
                    time.sleep(backoff)
                    continue
                raise

        return LLMResponse(content="", model=self.model)

    async def stream(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None,
        reasoning_effort: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response from GPT-OSS"""
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        if reasoning_effort:
            system_prompt = re.sub(
                r'Reasoning effort: \w+',
                f'Reasoning effort: {reasoning_effort}',
                system_prompt
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": formatted_prompt}
        ]

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{self.endpoint}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "top_p": config.top_p,
                    "stop": config.stop_sequences if config.stop_sequences else None,
                    "stream": True,
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data and data != "[DONE]":
                            import json
                            try:
                                chunk = json.loads(data)
                                if "choices" in chunk and chunk["choices"]:
                                    delta = chunk["choices"][0].get("delta", {})
                                    text = delta.get("content", "")
                                    if text:
                                        yield text
                            except json.JSONDecodeError:
                                continue


# Register adapter
LLMProviderFactory.register("gpt-oss", GptOssAdapter)
LLMProviderFactory.register("gpt_oss", GptOssAdapter)
LLMProviderFactory.register("gptoss", GptOssAdapter)
