"""DeepSeek-R1 LLM Adapter

Specialized adapter for DeepSeek-R1 reasoning model with <think> tag support.
"""

import logging
import re
import httpx
import asyncio
import time
from typing import Optional, AsyncGenerator, List

from shared.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
    TaskType,
    LLMProviderFactory,
)

logger = logging.getLogger(__name__)


def _calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter
    """
    import random
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Add jitter (0.5x to 1.5x)
    jitter = delay * (0.5 + random.random())
    return jitter


# DeepSeek-R1 specific system prompts with <think> tag requirements
DEEPSEEK_SYSTEM_PROMPTS = {
    TaskType.REASONING: """You are DeepSeek-R1, an advanced reasoning model.

CRITICAL: You MUST use <think></think> tags to show your reasoning process.

<think>
[Your step-by-step reasoning here]
1. Analyze the problem
2. Consider approaches
3. Evaluate trade-offs
4. Form conclusion
</think>

[Your final answer here]""",

    TaskType.CODING: """You are DeepSeek-R1 assisting with code generation.

Use <think></think> tags to plan your approach:
<think>
1. Understand requirements
2. Design file structure
3. Plan implementation
4. Consider edge cases
</think>

Then provide the code in JSON format.""",

    TaskType.REVIEW: """You are DeepSeek-R1 performing code review.

<think>
1. Analyze code correctness
2. Check for security issues
3. Evaluate performance
4. Assess maintainability
</think>

Provide structured review feedback.""",

    TaskType.REFINE: """You are DeepSeek-R1 fixing code issues.

<think>
1. Identify root cause
2. Plan minimal fix
3. Validate fix doesn't break existing functionality
4. Consider edge cases
</think>

Apply targeted fixes.""",

    TaskType.GENERAL: """You are DeepSeek-R1, an advanced AI assistant.

For complex questions, use <think></think> tags to show your reasoning:
<think>
[Your reasoning process]
</think>

[Your final response]""",
}


class DeepSeekAdapter(BaseLLMProvider):
    """Adapter for DeepSeek-R1 reasoning model

    Features:
    - Automatic <think> tag formatting
    - Thinking block extraction
    - High token budget for reasoning
    """

    @property
    def model_type(self) -> str:
        return "deepseek"

    def format_system_prompt(self, task_type: TaskType) -> str:
        """Get DeepSeek-R1 system prompt with <think> instructions"""
        return DEEPSEEK_SYSTEM_PROMPTS.get(task_type, DEEPSEEK_SYSTEM_PROMPTS[TaskType.GENERAL])

    def format_prompt(self, prompt: str, task_type: TaskType) -> str:
        """Format prompt with DeepSeek-R1 specific structure"""
        if task_type == TaskType.REASONING:
            return f"""<think>
Analyze this request step by step:
1. What is being asked?
2. What are the key considerations?
3. What approach should be taken?
</think>

{prompt}

Provide your analysis with reasoning in <think> tags, then your conclusion."""

        elif task_type == TaskType.CODING:
            return f"""<think>
1. Parse the request requirements
2. Determine file structure
3. Plan each file's content
4. Consider error handling
</think>

{prompt}

Generate the code in JSON format:
{{
    "files": [
        {{
            "filename": "path/to/file.py",
            "content": "complete code",
            "language": "python",
            "description": "description"
        }}
    ]
}}"""

        elif task_type == TaskType.REVIEW:
            return f"""<think>
1. Read through the code carefully
2. Check for bugs and logic errors
3. Look for security vulnerabilities
4. Evaluate code quality
5. Assess adherence to best practices
</think>

{prompt}

Provide review in JSON format:
{{
    "approved": true/false,
    "quality_score": 0.0-1.0,
    "issues": ["issue1"],
    "suggestions": ["suggestion1"],
    "critique": "overall"
}}"""

        else:
            return prompt

    def _extract_thinking_blocks(self, text: str) -> List[str]:
        """Extract content from <think></think> tags"""
        pattern = r"<think>(.*?)</think>"
        matches = re.findall(pattern, text, re.DOTALL)
        return [m.strip() for m in matches]

    def _extract_final_response(self, text: str) -> str:
        """Extract the response after thinking blocks"""
        # Remove thinking blocks to get the final answer
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()

    def parse_response(self, response: str, task_type: TaskType) -> LLMResponse:
        """Parse DeepSeek-R1 response, extracting thinking blocks"""
        thinking_blocks = self._extract_thinking_blocks(response)
        final_content = self._extract_final_response(response)

        # Extract JSON if applicable
        parsed_json = None
        if task_type in (TaskType.CODING, TaskType.REVIEW, TaskType.REFINE):
            parsed_json = self._extract_json(response)

        return LLMResponse(
            content=final_content if final_content else response,
            model=self.model,
            thinking_blocks=thinking_blocks if thinking_blocks else None,
            parsed_json=parsed_json,
        )

    def get_config_for_task(self, task_type: TaskType) -> LLMConfig:
        """DeepSeek-R1 optimized configurations"""
        configs = {
            TaskType.REASONING: LLMConfig(
                temperature=0.7,
                max_tokens=8000,  # High for complex reasoning
                stop_sequences=["Human:", "User:"],
            ),
            TaskType.CODING: LLMConfig(
                temperature=0.3,
                max_tokens=8000,
                stop_sequences=["</s>", "Human:"],
            ),
            TaskType.REVIEW: LLMConfig(
                temperature=0.2,
                max_tokens=4000,
                stop_sequences=["</s>"],
            ),
            TaskType.REFINE: LLMConfig(
                temperature=0.3,
                max_tokens=4000,
                stop_sequences=["</s>"],
            ),
            TaskType.GENERAL: LLMConfig(
                temperature=0.5,
                max_tokens=4000,
                stop_sequences=["</s>"],
            ),
        }
        return configs.get(task_type, self.config)

    async def generate(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None,
        max_retries: int = 3
    ) -> LLMResponse:
        """Generate response from DeepSeek-R1 with retry and exponential backoff"""
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        full_prompt = f"{system_prompt}\n\n{formatted_prompt}"

        # Log prompt size for debugging
        prompt_tokens_estimate = len(full_prompt) // 4  # Rough estimate
        logger.debug(f"DeepSeek request: ~{prompt_tokens_estimate} tokens, task={task_type.value}")

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:  # Longer timeout for reasoning
                    response = await client.post(
                        f"{self.endpoint}/completions",
                        json={
                            "model": self.model,
                            "prompt": full_prompt,
                            **config.to_dict(),
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["text"]

                        # Retry on empty response with backoff
                        if not content or not content.strip():
                            # Log more details about empty response
                            finish_reason = result.get("choices", [{}])[0].get("finish_reason", "unknown")
                            usage = result.get("usage", {})
                            logger.warning(
                                f"Empty response from DeepSeek: "
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
                                logger.error("Empty response from DeepSeek after all retries")
                                # Return a placeholder response instead of empty
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
                        # Retry on server errors (5xx) with backoff
                        if response.status_code >= 500 and attempt < max_retries:
                            backoff = _calculate_backoff(attempt)
                            logger.warning(f"DeepSeek server error {response.status_code}, retrying in {backoff:.1f}s...")
                            await asyncio.sleep(backoff)
                            continue
                        logger.error(f"DeepSeek request failed: {response.status_code}")
                        raise Exception(f"DeepSeek request failed: {response.status_code}")

            except httpx.TimeoutException:
                if attempt < max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.warning(f"DeepSeek request timed out, retrying in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)
                    continue
                logger.error("DeepSeek request timed out after all retries")
                raise

        # Should not reach here, but return empty response as fallback
        return LLMResponse(content="", model=self.model)

    def generate_sync(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None,
        max_retries: int = 3
    ) -> LLMResponse:
        """Synchronous generation for DeepSeek-R1 with retry and exponential backoff"""
        config = config_override or self.get_config_for_task(task_type)
        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)

        full_prompt = f"{system_prompt}\n\n{formatted_prompt}"

        # Log prompt size for debugging
        prompt_tokens_estimate = len(full_prompt) // 4
        logger.debug(f"DeepSeek sync request: ~{prompt_tokens_estimate} tokens, task={task_type.value}")

        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=180.0) as client:
                    response = client.post(
                        f"{self.endpoint}/completions",
                        json={
                            "model": self.model,
                            "prompt": full_prompt,
                            **config.to_dict(),
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["text"]

                        # Retry on empty response with backoff
                        if not content or not content.strip():
                            # Log more details about empty response
                            finish_reason = result.get("choices", [{}])[0].get("finish_reason", "unknown")
                            usage = result.get("usage", {})
                            logger.warning(
                                f"Empty response from DeepSeek (sync): "
                                f"finish_reason={finish_reason}, "
                                f"prompt_tokens={usage.get('prompt_tokens', 'N/A')}, "
                                f"completion_tokens={usage.get('completion_tokens', 'N/A')}"
                            )

                            if attempt < max_retries:
                                backoff = _calculate_backoff(attempt)
                                logger.warning(f"Retrying in {backoff:.1f}s ({attempt + 1}/{max_retries})...")
                                time.sleep(backoff)
                                continue
                            else:
                                logger.error("Empty response from DeepSeek (sync) after all retries")
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
                        # Retry on server errors (5xx) with backoff
                        if response.status_code >= 500 and attempt < max_retries:
                            backoff = _calculate_backoff(attempt)
                            logger.warning(f"DeepSeek server error {response.status_code}, retrying in {backoff:.1f}s...")
                            time.sleep(backoff)
                            continue
                        logger.error(f"DeepSeek request failed: {response.status_code}")
                        raise Exception(f"DeepSeek request failed: {response.status_code}")

            except httpx.TimeoutException:
                if attempt < max_retries:
                    backoff = _calculate_backoff(attempt)
                    logger.warning(f"DeepSeek request timed out, retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue
                logger.error("DeepSeek request timed out after all retries")
                raise

        # Should not reach here, but return empty response as fallback
        return LLMResponse(content="", model=self.model)

    async def stream(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Stream response from DeepSeek-R1"""
        config = config_override or self.get_config_for_task(task_type)
        config.stream = True

        formatted_prompt = self.format_prompt(prompt, task_type)
        system_prompt = self.format_system_prompt(task_type)
        full_prompt = f"{system_prompt}\n\n{formatted_prompt}"

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{self.endpoint}/completions",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    **config.to_dict(),
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
                                    text = chunk["choices"][0].get("text", "")
                                    if text:
                                        yield text
                            except json.JSONDecodeError:
                                continue


# Register adapter
LLMProviderFactory.register("deepseek", DeepSeekAdapter)
