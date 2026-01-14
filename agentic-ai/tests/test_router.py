"""Unit tests for Intent Router

Tests multi-domain classification accuracy across various prompts.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.completion_usage import CompletionUsage

from core.router import IntentRouter, WorkflowDomain, IntentClassification, classify_intent
from core.llm_client import DualEndpointLLMClient, EndpointConfig


# Test prompts for each domain
CODING_PROMPTS = [
    "Fix the authentication bug in login.py",
    "Add unit tests for the user service",
    "Refactor the database connection module",
    "Debug why the API endpoint returns 500",
    "Implement a REST API for user management",
    "Review the code in pull request #123",
]

RESEARCH_PROMPTS = [
    "Research best practices for microservices architecture",
    "Compare React vs Vue for our next project",
    "Summarize this research paper on neural networks",
    "Find the latest trends in cloud computing",
    "What are the pros and cons of serverless?",
    "Explain how transformer models work",
]

DATA_PROMPTS = [
    "Analyze the sales data in this CSV file",
    "Create a dashboard for customer metrics",
    "Clean and normalize the user database",
    "Generate a visualization of monthly revenue",
    "Run SQL queries to find duplicate records",
    "Build an ETL pipeline for transaction data",
]

GENERAL_PROMPTS = [
    "Organize these files into folders",
    "Create a project plan for the new feature",
    "Help me prioritize my todo list",
    "Set up a meeting schedule",
    "Rename all files with the new naming convention",
    "Archive old logs from last year",
]


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing"""
    client = Mock(spec=DualEndpointLLMClient)
    client.model_name = "gpt-oss-120b"
    return client


def create_mock_response(domain: str, confidence: float = 0.9):
    """Create a mock ChatCompletion response"""
    json_content = f'''{{
        "domain": "{domain}",
        "confidence": {confidence},
        "reasoning": "Mock classification for testing",
        "requires_sub_agents": false,
        "estimated_complexity": "medium"
    }}'''

    return ChatCompletion(
        id="test_completion",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content=json_content
                )
            )
        ],
        created=1234567890,
        model="gpt-oss-120b",
        object="chat.completion",
        usage=CompletionUsage(
            completion_tokens=50,
            prompt_tokens=100,
            total_tokens=150
        )
    )


class TestIntentRouter:
    """Test suite for IntentRouter"""

    @pytest.mark.asyncio
    async def test_coding_classification(self, mock_llm_client):
        """Test classification of coding prompts"""
        mock_llm_client.chat_completion = AsyncMock(
            return_value=create_mock_response("coding", 0.95)
        )

        router = IntentRouter(mock_llm_client)
        result = await router.classify("Fix the authentication bug")

        assert result.domain == WorkflowDomain.CODING
        assert result.confidence >= 0.7
        assert isinstance(result.reasoning, str)

    @pytest.mark.asyncio
    async def test_research_classification(self, mock_llm_client):
        """Test classification of research prompts"""
        mock_llm_client.chat_completion = AsyncMock(
            return_value=create_mock_response("research", 0.92)
        )

        router = IntentRouter(mock_llm_client)
        result = await router.classify("Research best practices for API design")

        assert result.domain == WorkflowDomain.RESEARCH
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_data_classification(self, mock_llm_client):
        """Test classification of data prompts"""
        mock_llm_client.chat_completion = AsyncMock(
            return_value=create_mock_response("data", 0.88)
        )

        router = IntentRouter(mock_llm_client)
        result = await router.classify("Analyze this CSV file")

        assert result.domain == WorkflowDomain.DATA
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_general_classification(self, mock_llm_client):
        """Test classification of general prompts"""
        mock_llm_client.chat_completion = AsyncMock(
            return_value=create_mock_response("general", 0.85)
        )

        router = IntentRouter(mock_llm_client)
        result = await router.classify("Organize these files")

        assert result.domain == WorkflowDomain.GENERAL
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_low_confidence_warning(self, mock_llm_client):
        """Test handling of low confidence classifications"""
        mock_llm_client.chat_completion = AsyncMock(
            return_value=create_mock_response("coding", 0.55)
        )

        router = IntentRouter(mock_llm_client, confidence_threshold=0.7)
        result = await router.classify("Maybe fix something?")

        # Should still return result but with low confidence
        assert result.confidence < 0.7
        assert result.domain == WorkflowDomain.CODING

    @pytest.mark.asyncio
    async def test_fallback_classification(self, mock_llm_client):
        """Test fallback to rule-based classification on LLM failure"""
        mock_llm_client.chat_completion = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        router = IntentRouter(mock_llm_client, enable_fallback=True)
        result = await router.classify("Fix the bug in authentication code")

        # Fallback should classify based on keywords
        assert result.domain in [WorkflowDomain.CODING, WorkflowDomain.GENERAL]
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_fallback_disabled_raises_exception(self, mock_llm_client):
        """Test that disabling fallback raises exception on LLM failure"""
        mock_llm_client.chat_completion = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        router = IntentRouter(mock_llm_client, enable_fallback=False)

        with pytest.raises(Exception, match="LLM service unavailable"):
            await router.classify("Fix the bug")

    @pytest.mark.asyncio
    async def test_markdown_json_parsing(self, mock_llm_client):
        """Test parsing JSON wrapped in markdown code blocks"""
        markdown_response = ChatCompletion(
            id="test_completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content='''```json
{
    "domain": "coding",
    "confidence": 0.95,
    "reasoning": "This is a coding task",
    "requires_sub_agents": false,
    "estimated_complexity": "medium"
}
```'''
                    )
                )
            ],
            created=1234567890,
            model="gpt-oss-120b",
            object="chat.completion",
            usage=CompletionUsage(
                completion_tokens=50,
                prompt_tokens=100,
                total_tokens=150
            )
        )

        mock_llm_client.chat_completion = AsyncMock(return_value=markdown_response)
        router = IntentRouter(mock_llm_client)
        result = await router.classify("Fix the bug")

        assert result.domain == WorkflowDomain.CODING
        assert result.confidence == 0.95

    def test_fallback_coding_keywords(self, mock_llm_client):
        """Test fallback classification with coding keywords"""
        router = IntentRouter(mock_llm_client, enable_fallback=True)

        result = router._fallback_classify("Fix the bug in the function and add tests")

        assert result.domain == WorkflowDomain.CODING
        assert result.confidence > 0.5

    def test_fallback_research_keywords(self, mock_llm_client):
        """Test fallback classification with research keywords"""
        router = IntentRouter(mock_llm_client, enable_fallback=True)

        result = router._fallback_classify("Research and compare best practices")

        assert result.domain == WorkflowDomain.RESEARCH
        assert result.confidence > 0.5

    def test_fallback_data_keywords(self, mock_llm_client):
        """Test fallback classification with data keywords"""
        router = IntentRouter(mock_llm_client, enable_fallback=True)

        result = router._fallback_classify("Analyze the CSV dataset and create visualization")

        assert result.domain == WorkflowDomain.DATA
        assert result.confidence > 0.5

    def test_fallback_no_keywords(self, mock_llm_client):
        """Test fallback classification with no matching keywords"""
        router = IntentRouter(mock_llm_client, enable_fallback=True)

        result = router._fallback_classify("Hello world")

        assert result.domain == WorkflowDomain.GENERAL
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, mock_llm_client):
        """Test that router tracks classification statistics"""
        mock_llm_client.chat_completion = AsyncMock(
            side_effect=[
                create_mock_response("coding", 0.9),
                create_mock_response("coding", 0.85),
                create_mock_response("research", 0.92),
            ]
        )

        router = IntentRouter(mock_llm_client)

        await router.classify("Fix bug 1")
        await router.classify("Fix bug 2")
        await router.classify("Research something")

        stats = router.get_stats()

        assert stats["total_classifications"] == 3
        assert stats["domain_distribution"]["coding"] == 2
        assert stats["domain_distribution"]["research"] == 1
        assert stats["confidence_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_convenience_function(self, mock_llm_client):
        """Test convenience classify_intent function"""
        mock_llm_client.chat_completion = AsyncMock(
            return_value=create_mock_response("coding", 0.9)
        )

        result = await classify_intent("Fix the bug", mock_llm_client)

        assert result.domain == WorkflowDomain.CODING
        assert result.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_sub_agent_detection(self, mock_llm_client):
        """Test detection of tasks requiring sub-agents"""
        complex_response = ChatCompletion(
            id="test_completion",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content='''{"domain": "coding", "confidence": 0.9, "reasoning": "Complex task", "requires_sub_agents": true, "estimated_complexity": "high"}'''
                    )
                )
            ],
            created=1234567890,
            model="gpt-oss-120b",
            object="chat.completion",
            usage=CompletionUsage(completion_tokens=50, prompt_tokens=100, total_tokens=150)
        )

        mock_llm_client.chat_completion = AsyncMock(return_value=complex_response)
        router = IntentRouter(mock_llm_client)
        result = await router.classify("Refactor the entire authentication system")

        assert result.requires_sub_agents == True
        assert result.estimated_complexity == "high"


# Integration test markers
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_llm_classification():
    """Integration test with real LLM (requires running vLLM server)

    Skip this test if LLM endpoints are not available.
    Run with: pytest tests/test_router.py -m integration
    """
    pytest.skip("Integration test - requires running LLM server")

    # Uncomment below to test with real LLM
    # endpoints = [
    #     EndpointConfig(url="http://localhost:8001/v1", name="primary", timeout=120)
    # ]
    # llm_client = DualEndpointLLMClient(endpoints=endpoints, model_name="gpt-oss-120b")
    # router = IntentRouter(llm_client)
    #
    # # Test various prompts
    # for prompt in CODING_PROMPTS[:2]:
    #     result = await router.classify(prompt)
    #     print(f"Prompt: {prompt}")
    #     print(f"Domain: {result.domain}, Confidence: {result.confidence}")
    #     assert result.domain == WorkflowDomain.CODING
    #
    # await llm_client.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
