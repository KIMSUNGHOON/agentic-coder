"""Tests for Phase 2 Context Manager

Tests context compression, key info extraction, and agent-specific filtering.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

try:
    import pytest
except ImportError:
    pytest = None

from app.utils.context_manager import ContextManager


def test_compress_conversation_history():
    """Test conversation history compression"""
    mgr = ContextManager(max_recent_messages=5)

    # Create 15 messages (should compress 10, keep 5)
    history = [
        {"role": "user", "content": f"Message {i}"}
        for i in range(15)
    ]

    compressed = mgr.compress_conversation_history(history, max_tokens=4000)

    # Should have summary + 5 recent messages
    assert len(compressed) == 6  # 1 summary + 5 recent
    assert compressed[0]["role"] == "system"
    assert "이전 대화 요약" in compressed[0]["content"]


def test_extract_key_info():
    """Test key information extraction"""
    mgr = ContextManager()

    history = [
        {"role": "user", "content": "Please create test.py and main.js files"},
        {"role": "assistant", "content": "Created test.py with 100 lines"},
        {"role": "user", "content": "I got an error: FileNotFoundError at line 42"},
        {"role": "assistant", "content": "Let me fix that error in test.py"},
        {"role": "user", "content": "I prefer using TypeScript instead of JavaScript"},
    ]

    key_info = mgr.extract_key_info(history)

    # Check files mentioned
    assert "test.py" in key_info["files_mentioned"]
    assert "main.js" in key_info["files_mentioned"]

    # Check errors encountered
    assert len(key_info["errors_encountered"]) > 0
    assert any("error" in err.lower() for err in key_info["errors_encountered"])

    # Check user preferences
    assert len(key_info["user_preferences"]) > 0
    assert any("prefer" in pref.lower() for pref in key_info["user_preferences"])


def test_agent_specific_filtering():
    """Test agent-specific context filtering"""
    mgr = ContextManager()

    history = [
        {"role": "user", "content": "Create a Python file with authentication"},
        {"role": "assistant", "content": "I'll implement the auth module"},
        {"role": "user", "content": "Please review the code for security issues"},
        {"role": "assistant", "content": "Found 3 security vulnerabilities"},
        {"role": "user", "content": "Run the tests to verify"},
        {"role": "assistant", "content": "All tests passed"},
    ]

    # Coder should get coding-related messages
    coder_context = mgr.get_agent_relevant_context(history, "coder")
    assert any("file" in msg["content"].lower() or "implement" in msg["content"].lower()
               for msg in coder_context)

    # Reviewer should get review-related messages
    reviewer_context = mgr.get_agent_relevant_context(history, "reviewer")
    assert any("review" in msg["content"].lower() for msg in reviewer_context)

    # Security should get security-related messages
    security_context = mgr.get_agent_relevant_context(history, "security")
    assert any("security" in msg["content"].lower() or "auth" in msg["content"].lower()
               for msg in security_context)


def test_create_enriched_context():
    """Test enriched context creation"""
    mgr = ContextManager(max_recent_messages=3)

    history = [
        {"role": "user", "content": f"Message {i} about test.py"}
        for i in range(10)
    ]

    enriched = mgr.create_enriched_context(
        history=history,
        agent_type="coder",
        compress=True
    )

    assert "conversation_history" in enriched
    assert "key_info" in enriched
    assert enriched["total_messages"] == 10
    assert enriched["agent_type"] == "coder"
    assert enriched["compression_enabled"] is True


def test_format_context_for_prompt():
    """Test context formatting for prompts"""
    mgr = ContextManager()

    history = [
        {"role": "user", "content": "Create test.py"},
        {"role": "assistant", "content": "Created test.py successfully"},
    ]

    enriched = mgr.create_enriched_context(history, agent_type="coder", compress=False)
    formatted = mgr.format_context_for_prompt(enriched, include_key_info=True)

    assert "## 주요 컨텍스트 정보" in formatted
    assert "## 대화 히스토리" in formatted
    assert "test.py" in formatted


if __name__ == "__main__":
    # Run simple tests
    print("Testing Context Manager...")

    print("\n1. Testing compression...")
    test_compress_conversation_history()
    print("✓ Compression works")

    print("\n2. Testing key info extraction...")
    test_extract_key_info()
    print("✓ Key info extraction works")

    print("\n3. Testing agent filtering...")
    test_agent_specific_filtering()
    print("✓ Agent filtering works")

    print("\n4. Testing enriched context...")
    test_create_enriched_context()
    print("✓ Enriched context works")

    print("\n5. Testing prompt formatting...")
    test_format_context_for_prompt()
    print("✓ Prompt formatting works")

    print("\n✅ All tests passed!")
