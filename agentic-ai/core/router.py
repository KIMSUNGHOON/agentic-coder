"""Multi-Domain Intent Router for Agentic 2.0

Routes user prompts to appropriate workflows:
- Coding: Software development, debugging, code review
- Research: Information gathering, analysis, summarization
- Data: Data processing, analysis, visualization
- General: Task management, utilities, mixed workflows

Uses LLM-based classification with confidence scoring.
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .llm_client import DualEndpointLLMClient

logger = logging.getLogger(__name__)


class WorkflowDomain(str, Enum):
    """Workflow domain types"""
    CODING = "coding"
    RESEARCH = "research"
    DATA = "data"
    GENERAL = "general"


@dataclass
class IntentClassification:
    """Result of intent classification"""
    domain: WorkflowDomain
    confidence: float
    reasoning: str
    requires_sub_agents: bool = False
    estimated_complexity: str = "medium"  # low, medium, high

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization

        Returns:
            Dictionary representation
        """
        return {
            "domain": self.domain.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "requires_sub_agents": self.requires_sub_agents,
            "estimated_complexity": self.estimated_complexity,
        }


class IntentRouter:
    """Multi-domain intent classifier and router

    Features:
    - 4-way classification (coding, research, data, general)
    - Confidence scoring
    - Complexity estimation
    - Sub-agent requirement detection

    Example:
        >>> router = IntentRouter(llm_client)
        >>> result = await router.classify("Fix the authentication bug")
        >>> print(result.domain)  # WorkflowDomain.CODING
        >>> print(result.confidence)  # 0.95
    """

    # Classification prompt template
    CLASSIFICATION_PROMPT = """You are an intent classifier for an agentic AI system.

Analyze the user's request and classify it into ONE of these domains:

1. CODING: Software development tasks
   - Writing/modifying code, debugging, testing
   - Code review, refactoring, optimization
   - Build systems, CI/CD, deployment
   Examples: "Fix the authentication bug", "Add unit tests", "Refactor this module"

2. RESEARCH: Information gathering and analysis
   - Web research, documentation review
   - Competitive analysis, market research
   - Summarization, synthesis of information
   Examples: "Research best practices for API design", "Summarize this paper", "Compare React vs Vue"

3. DATA: Data processing and analysis
   - Data cleaning, transformation, ETL
   - Statistical analysis, visualization
   - Database queries, data modeling
   Examples: "Analyze this CSV file", "Create a dashboard", "Clean the customer data"

4. GENERAL: Task management, greetings, and mixed workflows
   - Simple greetings and conversational responses (ALWAYS use GENERAL for greetings!)
   - File operations, system tasks
   - Multi-domain tasks that don't fit other categories
   - Administrative tasks, scheduling
   Examples: "Hello", "Hi", "Hey", "How are you?", "Organize these files", "Create a project plan"

IMPORTANT: If the input is a simple greeting (hello, hi, hey, etc.), ALWAYS classify as GENERAL with high confidence!

User Request: {user_prompt}

Respond in JSON format:
{{
    "domain": "coding|research|data|general",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this domain was chosen",
    "requires_sub_agents": true|false,
    "estimated_complexity": "low|medium|high"
}}

Domain:"""

    def __init__(
        self,
        llm_client: DualEndpointLLMClient,
        confidence_threshold: float = 0.7,
        enable_fallback: bool = True,
    ):
        """Initialize IntentRouter

        Args:
            llm_client: DualEndpointLLMClient for classification
            confidence_threshold: Minimum confidence for classification (default: 0.7)
            enable_fallback: Enable rule-based fallback if LLM fails (default: True)
        """
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold
        self.enable_fallback = enable_fallback

        # Statistics
        self.total_classifications = 0
        self.domain_counts = {domain: 0 for domain in WorkflowDomain}

        logger.info(f"🎯 IntentRouter initialized (confidence threshold: {confidence_threshold})")

    async def classify(self, user_prompt: str) -> IntentClassification:
        """Classify user prompt into workflow domain

        Args:
            user_prompt: User's input text

        Returns:
            IntentClassification with domain, confidence, and metadata

        Raises:
            Exception: If classification fails and fallback is disabled
        """
        logger.info(f"📋 Classifying intent: {user_prompt[:100]}...")

        try:
            # Try LLM-based classification first
            result = await self._llm_classify(user_prompt)

            # Update statistics
            self.total_classifications += 1
            self.domain_counts[result.domain] += 1

            logger.info(
                f"✅ Classification: {result.domain.value} "
                f"(confidence: {result.confidence:.2f}, "
                f"complexity: {result.estimated_complexity})"
            )

            return result

        except Exception as e:
            logger.error(f"❌ LLM classification failed: {e}")

            if self.enable_fallback:
                logger.info("🔄 Falling back to rule-based classification")
                result = self._fallback_classify(user_prompt)
                self.total_classifications += 1
                self.domain_counts[result.domain] += 1
                return result
            else:
                raise

    async def _llm_classify(self, user_prompt: str) -> IntentClassification:
        """Use LLM for intent classification

        Args:
            user_prompt: User's input text

        Returns:
            IntentClassification from LLM response
        """
        # Prepare classification prompt
        prompt = self.CLASSIFICATION_PROMPT.format(user_prompt=user_prompt)

        messages = [
            {"role": "system", "content": "You are a precise intent classifier. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]

        # Call LLM
        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=0.0,  # Deterministic classification
            max_tokens=500,
        )

        # Parse response
        content = response.choices[0].message.content.strip()

        # Extract JSON if it's wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            import re
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                raise ValueError(f"Could not parse JSON from response: {content}")

        # Validate and create result
        domain = WorkflowDomain(data["domain"])
        confidence = float(data["confidence"])
        reasoning = data["reasoning"]
        requires_sub_agents = data.get("requires_sub_agents", False)
        estimated_complexity = data.get("estimated_complexity", "medium")

        # Check confidence threshold
        if confidence < self.confidence_threshold:
            logger.warning(
                f"⚠️  Low confidence classification: {confidence:.2f} < {self.confidence_threshold}"
            )

        return IntentClassification(
            domain=domain,
            confidence=confidence,
            reasoning=reasoning,
            requires_sub_agents=requires_sub_agents,
            estimated_complexity=estimated_complexity,
        )

    def _fallback_classify(self, user_prompt: str) -> IntentClassification:
        """Rule-based fallback classification

        Uses keyword matching when LLM classification fails.

        Args:
            user_prompt: User's input text

        Returns:
            IntentClassification based on rules
        """
        prompt_lower = user_prompt.lower().strip()

        # CRITICAL: Check for greetings FIRST!
        greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이', 'good morning', 'good afternoon', 'good evening']
        is_greeting = any(prompt_lower.startswith(kw) or prompt_lower == kw for kw in greeting_keywords)

        if is_greeting and len(user_prompt) < 30:
            logger.info(f"👋 Detected greeting in fallback: '{user_prompt}'")
            return IntentClassification(
                domain=WorkflowDomain.GENERAL,
                confidence=0.95,
                reasoning="Simple greeting detected (rule-based)",
                requires_sub_agents=False,
                estimated_complexity="low",
            )

        # Coding keywords
        coding_keywords = [
            "code", "function", "class", "debug", "bug", "fix", "test",
            "refactor", "implement", "api", "module", "library", "framework",
            "error", "exception", "compile", "build", "deploy", "git", "commit"
        ]

        # Research keywords
        research_keywords = [
            "research", "find", "search", "analyze", "compare", "summarize",
            "explain", "what is", "how does", "best practices", "documentation",
            "paper", "article", "study", "investigate", "explore"
        ]

        # Data keywords
        data_keywords = [
            "data", "dataset", "csv", "excel", "sql", "database", "query",
            "analyze", "visualization", "chart", "graph", "statistics",
            "clean", "transform", "etl", "pandas", "numpy"
        ]

        # Count keyword matches
        coding_score = sum(1 for kw in coding_keywords if kw in prompt_lower)
        research_score = sum(1 for kw in research_keywords if kw in prompt_lower)
        data_score = sum(1 for kw in data_keywords if kw in prompt_lower)

        # Determine domain
        scores = {
            WorkflowDomain.CODING: coding_score,
            WorkflowDomain.RESEARCH: research_score,
            WorkflowDomain.DATA: data_score,
        }

        max_score = max(scores.values())

        if max_score == 0:
            # No keyword matches, default to GENERAL
            domain = WorkflowDomain.GENERAL
            confidence = 0.5
            reasoning = "No strong indicators, defaulting to general workflow"
        else:
            # Get domain with highest score
            domain = max(scores, key=scores.get)
            confidence = min(0.6 + (max_score * 0.05), 0.85)  # Cap at 0.85 for rule-based
            reasoning = f"Rule-based classification ({max_score} keyword matches)"

        logger.info(f"🔧 Fallback classification: {domain.value} (confidence: {confidence:.2f})")

        return IntentClassification(
            domain=domain,
            confidence=confidence,
            reasoning=reasoning,
            requires_sub_agents=False,
            estimated_complexity="medium",
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics

        Returns:
            Dictionary with classification statistics
        """
        return {
            "total_classifications": self.total_classifications,
            "domain_distribution": {
                domain.value: count
                for domain, count in self.domain_counts.items()
            },
            "confidence_threshold": self.confidence_threshold,
            "fallback_enabled": self.enable_fallback,
        }


# Convenience function
async def classify_intent(
    user_prompt: str,
    llm_client: DualEndpointLLMClient,
    confidence_threshold: float = 0.7,
) -> IntentClassification:
    """Convenience function for one-off intent classification

    Args:
        user_prompt: User's input text
        llm_client: DualEndpointLLMClient instance
        confidence_threshold: Minimum confidence (default: 0.7)

    Returns:
        IntentClassification result

    Example:
        >>> llm_client = DualEndpointLLMClient(endpoints)
        >>> result = await classify_intent("Debug the login issue", llm_client)
        >>> print(result.domain)  # WorkflowDomain.CODING
    """
    router = IntentRouter(llm_client, confidence_threshold)
    return await router.classify(user_prompt)
