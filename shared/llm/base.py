"""LLM Provider Interface - Abstract Base for Model Adapters

This module defines the abstract interface for LLM providers,
enabling seamless switching between different models (DeepSeek, Qwen, GPT, etc.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, AsyncGenerator, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks that can be performed by LLM"""
    REASONING = "reasoning"
    CODING = "coding"
    REVIEW = "review"
    REFINE = "refine"
    GENERAL = "general"


@dataclass
class LLMConfig:
    """Configuration for LLM requests"""
    temperature: float = 0.3
    max_tokens: int = 4096
    top_p: float = 0.95
    stop_sequences: List[str] = field(default_factory=lambda: ["</s>"])
    stream: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "stop": self.stop_sequences,
            "stream": self.stream,
        }


@dataclass
class LLMResponse:
    """Standardized response from LLM"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict] = None

    # Parsed structured data (if applicable)
    parsed_json: Optional[Dict] = None
    thinking_blocks: Optional[List[str]] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers

    All model-specific adapters should inherit from this class
    and implement the abstract methods.
    """

    def __init__(self, endpoint: str, model: str, config: Optional[LLMConfig] = None):
        self.endpoint = endpoint
        self.model = model
        self.config = config or LLMConfig()
        self._client = None

    @property
    @abstractmethod
    def model_type(self) -> str:
        """Return the model type identifier (e.g., 'deepseek', 'qwen', 'gpt')"""
        pass

    @abstractmethod
    def format_prompt(self, prompt: str, task_type: TaskType) -> str:
        """Format prompt according to model's requirements

        Args:
            prompt: The raw prompt text
            task_type: Type of task being performed

        Returns:
            Formatted prompt string
        """
        pass

    @abstractmethod
    def format_system_prompt(self, task_type: TaskType) -> str:
        """Get the appropriate system prompt for the task type

        Args:
            task_type: Type of task being performed

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def parse_response(self, response: str, task_type: TaskType) -> LLMResponse:
        """Parse the raw LLM response into a standardized format

        Args:
            response: Raw response text from LLM
            task_type: Type of task that was performed

        Returns:
            Standardized LLMResponse object
        """
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None
    ) -> LLMResponse:
        """Generate a response from the LLM

        Args:
            prompt: The prompt to send to the LLM
            task_type: Type of task being performed
            config_override: Optional config to override defaults

        Returns:
            LLMResponse object
        """
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        task_type: TaskType = TaskType.GENERAL,
        config_override: Optional[LLMConfig] = None
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM

        Args:
            prompt: The prompt to send to the LLM
            task_type: Type of task being performed
            config_override: Optional config to override defaults

        Yields:
            Response chunks as strings
        """
        pass

    def get_config_for_task(self, task_type: TaskType) -> LLMConfig:
        """Get optimal configuration for a specific task type

        Args:
            task_type: Type of task

        Returns:
            LLMConfig optimized for the task
        """
        # Default configurations by task type
        task_configs = {
            TaskType.REASONING: LLMConfig(temperature=0.7, max_tokens=8000),
            TaskType.CODING: LLMConfig(temperature=0.2, max_tokens=4096),
            TaskType.REVIEW: LLMConfig(temperature=0.1, max_tokens=2048),
            TaskType.REFINE: LLMConfig(temperature=0.3, max_tokens=4096),
            TaskType.GENERAL: self.config,
        }
        return task_configs.get(task_type, self.config)

    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON from response text

        Handles DeepSeek-R1 format with <think>...</think> tags.

        Args:
            text: Response text that may contain JSON

        Returns:
            Parsed JSON dict or None
        """
        import json
        import re

        if not text or not text.strip():
            logger.warning("Empty response text - cannot extract JSON")
            return None

        try:
            # Step 1: Remove <think>...</think> tags (DeepSeek-R1 reasoning)
            # Handle both closed and unclosed tags
            cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            # Handle unclosed <think> tag (remove everything after it)
            if '<think>' in cleaned_text:
                cleaned_text = cleaned_text.split('<think>')[0]

            # Step 2: Also remove any other common wrapper tags
            cleaned_text = re.sub(r'<reasoning>.*?</reasoning>', '', cleaned_text, flags=re.DOTALL)
            cleaned_text = re.sub(r'<output>|</output>', '', cleaned_text)

            # Step 3: Try direct JSON parse first (if response is pure JSON)
            cleaned_text = cleaned_text.strip()
            if cleaned_text.startswith('{') and cleaned_text.endswith('}'):
                try:
                    return json.loads(cleaned_text)
                except json.JSONDecodeError:
                    pass

            # Step 4: Find JSON object in text
            json_start = cleaned_text.find("{")
            json_end = cleaned_text.rfind("}") + 1

            if json_start != -1 and json_end > json_start:
                json_str = cleaned_text[json_start:json_end]

                # Try to parse as-is first
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.debug(f"Initial JSON parse failed: {e}")

                    # Try to fix common JSON issues
                    fixed_json = json_str

                    # Fix 1: Handle newlines in strings (convert to \n)
                    # This is tricky - only fix if inside quotes
                    fixed_json = re.sub(r'(?<=": ")([^"]*)\n([^"]*?)(?=")', r'\1\\n\2', fixed_json)

                    # Fix 2: Remove trailing commas before } or ]
                    fixed_json = re.sub(r',\s*([}\]])', r'\1', fixed_json)

                    # Fix 3: Replace Python True/False/None with JSON equivalents
                    fixed_json = re.sub(r'\bTrue\b', 'true', fixed_json)
                    fixed_json = re.sub(r'\bFalse\b', 'false', fixed_json)
                    fixed_json = re.sub(r'\bNone\b', 'null', fixed_json)

                    try:
                        return json.loads(fixed_json)
                    except json.JSONDecodeError as e2:
                        logger.debug(f"Fixed JSON parse also failed: {e2}")

            # Step 5: Fallback - try to extract JSON from code blocks
            code_block_patterns = [
                r'```json\s*\n?(.*?)\n?```',  # ```json ... ```
                r'```\s*\n?(\{.*?\})\n?```',   # ``` {...} ```
            ]
            for pattern in code_block_patterns:
                code_block_match = re.search(pattern, text, re.DOTALL)
                if code_block_match:
                    try:
                        return json.loads(code_block_match.group(1).strip())
                    except json.JSONDecodeError:
                        continue

            # Step 6: Try to find JSON array
            if '[' in cleaned_text:
                array_start = cleaned_text.find("[")
                array_end = cleaned_text.rfind("]") + 1
                if array_start != -1 and array_end > array_start:
                    try:
                        result = json.loads(cleaned_text[array_start:array_end])
                        # Wrap array in dict for consistency
                        return {"items": result} if isinstance(result, list) else result
                    except json.JSONDecodeError:
                        pass

            logger.warning("Failed to parse JSON from response")
            logger.debug(f"Response text (first 500 chars): {text[:500]}")
        except Exception as e:
            logger.warning(f"Error extracting JSON: {e}")

        return None


class LLMProviderFactory:
    """Factory for creating LLM provider instances"""

    _providers: Dict[str, type] = {}

    @classmethod
    def register(cls, model_type: str, provider_class: type):
        """Register a provider class for a model type"""
        cls._providers[model_type] = provider_class

    @classmethod
    def create(
        cls,
        model_type: str,
        endpoint: str,
        model: str,
        config: Optional[LLMConfig] = None
    ) -> BaseLLMProvider:
        """Create a provider instance for the given model type

        Args:
            model_type: Type of model (deepseek, qwen, gpt, generic)
            endpoint: API endpoint URL
            model: Model name/identifier
            config: Optional configuration

        Returns:
            LLM provider instance

        Raises:
            ValueError: If model_type is not registered
        """
        if model_type not in cls._providers:
            # Fallback to generic if specific adapter not found
            if "generic" in cls._providers:
                logger.warning(f"No adapter for '{model_type}', using generic")
                model_type = "generic"
            else:
                raise ValueError(f"Unknown model type: {model_type}")

        return cls._providers[model_type](endpoint, model, config)

    @classmethod
    def get_available_types(cls) -> List[str]:
        """Get list of registered model types"""
        return list(cls._providers.keys())
