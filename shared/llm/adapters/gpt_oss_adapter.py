"""GPT-OSS LLM Adapter

Specialized adapter for OpenAI's GPT-OSS-120B and GPT-OSS-20B models.
Supports Harmony response format and reasoning levels.

References:
- https://github.com/openai/gpt-oss
- https://github.com/openai/harmony
- https://huggingface.co/openai/gpt-oss-120b
"""

import logging
import httpx
import asyncio
import time
import re
from typing import Optional, AsyncGenerator, Dict, List, Any

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


# Reasoning effort levels for GPT-OSS
class ReasoningEffort:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# GPT-OSS specific system prompts with Harmony format awareness
GPT_OSS_SYSTEM_PROMPTS = {
    TaskType.REASONING: """You are GPT-OSS, an advanced reasoning model by OpenAI.

Reasoning effort: high

For complex analysis tasks:
1. Break down the problem systematically
2. Consider multiple perspectives
3. Evaluate trade-offs
4. Provide well-structured conclusions

Your analysis should be thorough and actionable.""",

    TaskType.CODING: """You are GPT-OSS, an expert software engineer.

Reasoning effort: medium

ROLE: Production-grade Code Generator
EXPERTISE: Python, TypeScript, React, FastAPI, System Design, Security

CRITICAL RULES:
1. Generate complete, executable code
2. Include proper error handling and type hints
3. Follow language-specific best practices (PEP 8, ESLint)
4. Write clean, maintainable code with documentation

SECURITY RULES (MUST FOLLOW):
1. NEVER use eval() or exec() - use ast.literal_eval() for safe parsing
2. NEVER use subprocess with shell=True - use subprocess.run([cmd, arg1, arg2])
3. NEVER use os.system() - use subprocess module instead
4. NEVER hardcode passwords, API keys, or secrets - use environment variables
5. ALWAYS sanitize user inputs before using in file paths or SQL
6. Use parameterized queries for SQL, never string concatenation

OUTPUT: Return code in the specified JSON format.""",

    TaskType.REVIEW: """You are GPT-OSS performing expert code review.

Reasoning effort: high

Analyze the code for:
1. Correctness - Logic errors, edge cases
2. Security - OWASP vulnerabilities, injection risks
3. Performance - Bottlenecks, optimization opportunities
4. Maintainability - Code clarity, documentation
5. Best Practices - Language conventions, design patterns

Provide structured, actionable feedback.""",

    TaskType.REFINE: """You are GPT-OSS fixing code issues.

Reasoning effort: medium

For each issue:
1. Identify the root cause
2. Plan the minimal fix
3. Ensure fix doesn't break existing functionality
4. Consider edge cases

SECURITY FIXES:
- Replace eval() with ast.literal_eval()
- Replace exec() with safer alternatives
- Replace subprocess(shell=True) with subprocess([cmd, args])
- Replace os.system() with subprocess.run()
- Move hardcoded secrets to environment variables

Apply targeted, minimal fixes.""",

    TaskType.GENERAL: """You are GPT-OSS, an advanced AI assistant by OpenAI.

Reasoning effort: medium

Provide helpful, accurate, and well-reasoned responses.
For complex questions, think through the problem step by step.""",
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
    - analysis channel: Chain-of-thought reasoning
    - commentary channel: Tool calls
    - final channel: User-facing response

    When using vLLM, the Harmony format is handled automatically.
    """

    def __init__(
        self,
        endpoint: str,
        model: str = "openai/gpt-oss-120b",
        config: Optional[LLMConfig] = None,
        reasoning_effort: str = ReasoningEffort.MEDIUM,
    ):
        """Initialize GPT-OSS adapter

        Args:
            endpoint: vLLM server endpoint (e.g., http://localhost:8000/v1)
            model: Model name (gpt-oss-120b or gpt-oss-20b)
            config: Default LLM configuration
            reasoning_effort: Default reasoning level (low, medium, high)
        """
        super().__init__(endpoint, model, config or GPT_OSS_TASK_CONFIGS[TaskType.GENERAL])
        self.reasoning_effort = reasoning_effort
        logger.info(f"GPT-OSS Adapter initialized: {model} @ {endpoint}")
        logger.info(f"Default reasoning effort: {reasoning_effort}")

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

    async def generate(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None,
        max_retries: int = 3,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResponse:
        """Generate response from GPT-OSS with retry and backoff

        Args:
            prompt: User prompt
            task_type: Type of task for prompt/config selection
            config_override: Override default config
            max_retries: Number of retries on failure
            reasoning_effort: Override default reasoning effort
        """
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        # Adjust reasoning effort in system prompt if specified
        if reasoning_effort:
            system_prompt = re.sub(
                r'Reasoning effort: \w+',
                f'Reasoning effort: {reasoning_effort}',
                system_prompt
            )

        prompt_tokens_estimate = len(f"{system_prompt}\n\n{formatted_prompt}") // 4
        logger.debug(f"GPT-OSS request: ~{prompt_tokens_estimate} tokens, task={task_type.value}")

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": formatted_prompt}
                    ]

                    response = await client.post(
                        f"{self.endpoint}/chat/completions",
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": config.temperature,
                            "max_tokens": config.max_tokens,
                            "top_p": config.top_p,
                            "stop": config.stop_sequences if config.stop_sequences else None,
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0].get("message", {}).get("content", "")

                        if not content or not content.strip():
                            finish_reason = result.get("choices", [{}])[0].get("finish_reason", "unknown")
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
    ) -> LLMResponse:
        """Synchronous generation for GPT-OSS"""
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        if reasoning_effort:
            system_prompt = re.sub(
                r'Reasoning effort: \w+',
                f'Reasoning effort: {reasoning_effort}',
                system_prompt
            )

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=180.0) as client:
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": formatted_prompt}
                    ]

                    response = client.post(
                        f"{self.endpoint}/chat/completions",
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": config.temperature,
                            "max_tokens": config.max_tokens,
                            "top_p": config.top_p,
                            "stop": config.stop_sequences if config.stop_sequences else None,
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0].get("message", {}).get("content", "")

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
