"""Context Management Utilities

Phase 2 Context Improvement:
- Context compression for long conversations
- Key information extraction (files, errors, decisions)
- Agent-specific context filtering
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime


class ContextManager:
    """Manages conversation context with compression and filtering"""

    def __init__(self, max_recent_messages: int = 10):
        """Initialize context manager

        Args:
            max_recent_messages: Number of recent messages to keep in full
        """
        self.max_recent_messages = max_recent_messages

    def compress_conversation_history(
        self,
        history: List[Dict[str, str]],
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """Compress conversation history by summarizing old messages

        Args:
            history: Full conversation history
            max_tokens: Maximum tokens to target (rough estimate)

        Returns:
            Compressed conversation history
        """
        if len(history) <= self.max_recent_messages:
            return history

        # Keep recent messages in full
        recent = history[-self.max_recent_messages:]

        # Summarize older messages
        old_messages = history[:-self.max_recent_messages]
        summary = self._summarize_messages(old_messages)

        # Return summary + recent messages
        compressed = [
            {
                "role": "system",
                "content": f"이전 대화 요약:\n{summary}"
            }
        ] + recent

        return compressed

    def _summarize_messages(self, messages: List[Dict[str, str]]) -> str:
        """Summarize a list of messages

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        if not messages:
            return "이전 대화 없음"

        # Extract key information from old messages
        key_info = self.extract_key_info(messages)

        summary_parts = []

        # Add file information
        if key_info["files_mentioned"]:
            files_str = ", ".join(key_info["files_mentioned"][:10])
            summary_parts.append(f"작업한 파일: {files_str}")

        # Add error information
        if key_info["errors_encountered"]:
            errors_str = "; ".join(key_info["errors_encountered"][:5])
            summary_parts.append(f"발생한 에러: {errors_str}")

        # Add decisions made
        if key_info["decisions_made"]:
            decisions_str = "; ".join(key_info["decisions_made"][:5])
            summary_parts.append(f"주요 결정사항: {decisions_str}")

        # Add general summary
        summary_parts.append(
            f"총 {len(messages)}개의 이전 메시지 (사용자 {len([m for m in messages if m.get('role') == 'user'])}개, "
            f"AI {len([m for m in messages if m.get('role') == 'assistant'])}개)"
        )

        return "\n".join(summary_parts)

    def extract_key_info(self, history: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """Extract key information from conversation history

        Args:
            history: Conversation history

        Returns:
            Dictionary with extracted information:
            - files_mentioned: List of file paths mentioned
            - errors_encountered: List of error messages
            - decisions_made: List of key decisions
            - user_preferences: List of user preferences
        """
        files_mentioned = set()
        errors_encountered = []
        decisions_made = []
        user_preferences = []

        for msg in history:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # Extract file paths
            # Patterns: file.py, /path/to/file.js, C:\path\file.tsx
            file_patterns = [
                r'\b[\w/\\.-]+\.[a-zA-Z]{1,5}\b',  # file.ext
                r'`[\w/\\.-]+\.[a-zA-Z]{1,5}`',    # `file.ext`
            ]
            for pattern in file_patterns:
                matches = re.findall(pattern, content)
                files_mentioned.update(matches)

            # Extract error messages
            error_keywords = ["에러", "error", "실패", "failed", "exception", "오류"]
            if any(keyword in content.lower() for keyword in error_keywords):
                # Extract sentence containing error keyword
                sentences = content.split(".")
                for sentence in sentences:
                    if any(keyword in sentence.lower() for keyword in error_keywords):
                        errors_encountered.append(sentence.strip()[:200])
                        break

            # Extract decisions (user preferences)
            if role == "user":
                decision_keywords = [
                    "해주세요", "하십시오", "바랍니다", "원합니다",
                    "please", "want", "need", "should"
                ]
                if any(keyword in content.lower() for keyword in decision_keywords):
                    # Extract first meaningful sentence
                    sentences = content.split(".")
                    if sentences:
                        decisions_made.append(sentences[0].strip()[:200])

            # Extract user preferences
            if role == "user":
                preference_keywords = [
                    "선호", "prefer", "좋아", "like", "싫어", "dislike"
                ]
                if any(keyword in content.lower() for keyword in preference_keywords):
                    user_preferences.append(content[:200])

        return {
            "files_mentioned": sorted(list(files_mentioned))[:20],  # Top 20 files
            "errors_encountered": errors_encountered[:10],  # Top 10 errors
            "decisions_made": decisions_made[:10],  # Top 10 decisions
            "user_preferences": user_preferences[:5],  # Top 5 preferences
        }

    def get_agent_relevant_context(
        self,
        history: List[Dict[str, str]],
        agent_type: str
    ) -> List[Dict[str, str]]:
        """Filter conversation history for agent-specific context

        Args:
            history: Full conversation history
            agent_type: Type of agent (coder, reviewer, refiner, etc.)

        Returns:
            Filtered conversation history relevant to agent type
        """
        if agent_type == "coder":
            keywords = [
                "파일", "생성", "코드", "구현", "file", "create", "code",
                "implement", "function", "class", "module"
            ]
        elif agent_type == "reviewer":
            keywords = [
                "리뷰", "검토", "수정", "개선", "review", "check", "fix",
                "improve", "quality", "bug", "issue"
            ]
        elif agent_type == "refiner":
            keywords = [
                "개선", "최적화", "리팩토링", "refactor", "optimize",
                "improve", "clean", "enhance"
            ]
        elif agent_type == "security":
            keywords = [
                "보안", "security", "vulnerability", "취약점", "인증",
                "authentication", "권한", "authorization"
            ]
        elif agent_type == "testing":
            keywords = [
                "테스트", "test", "검증", "validation", "assert",
                "pytest", "unittest"
            ]
        else:
            # For unknown agents, return all history
            return history

        # Filter messages containing keywords
        filtered = []
        for msg in history:
            content = msg.get("content", "").lower()
            if any(keyword in content for keyword in keywords):
                filtered.append(msg)

        # Always include recent messages even if not matching keywords
        # to maintain conversation flow
        recent_messages = history[-5:]
        for msg in recent_messages:
            if msg not in filtered:
                filtered.append(msg)

        # Sort by original order
        filtered_sorted = sorted(
            filtered,
            key=lambda m: history.index(m) if m in history else 0
        )

        return filtered_sorted

    def create_enriched_context(
        self,
        history: List[Dict[str, str]],
        agent_type: Optional[str] = None,
        compress: bool = True
    ) -> Dict[str, Any]:
        """Create enriched context with compression and filtering

        Args:
            history: Full conversation history
            agent_type: Optional agent type for filtering
            compress: Whether to compress long conversations

        Returns:
            Enriched context dictionary
        """
        # Extract key information first
        key_info = self.extract_key_info(history)

        # Optionally filter by agent type
        if agent_type:
            filtered_history = self.get_agent_relevant_context(history, agent_type)
        else:
            filtered_history = history

        # Optionally compress
        if compress and len(filtered_history) > self.max_recent_messages:
            compressed_history = self.compress_conversation_history(filtered_history)
        else:
            compressed_history = filtered_history

        return {
            "conversation_history": compressed_history,
            "key_info": key_info,
            "total_messages": len(history),
            "filtered_messages": len(compressed_history),
            "agent_type": agent_type,
            "compression_enabled": compress,
        }

    def format_context_for_prompt(
        self,
        enriched_context: Dict[str, Any],
        include_key_info: bool = True
    ) -> str:
        """Format enriched context for inclusion in prompts

        Args:
            enriched_context: Enriched context from create_enriched_context()
            include_key_info: Whether to include extracted key information

        Returns:
            Formatted context string
        """
        parts = []

        # Add key information section
        if include_key_info and enriched_context.get("key_info"):
            key_info = enriched_context["key_info"]

            parts.append("## 주요 컨텍스트 정보\n")

            if key_info.get("files_mentioned"):
                files_str = ", ".join(key_info["files_mentioned"][:10])
                parts.append(f"**작업 파일**: {files_str}\n")

            if key_info.get("errors_encountered"):
                errors_str = "\n- ".join(key_info["errors_encountered"][:3])
                parts.append(f"**최근 에러**:\n- {errors_str}\n")

            if key_info.get("decisions_made"):
                decisions_str = "\n- ".join(key_info["decisions_made"][:3])
                parts.append(f"**주요 결정사항**:\n- {decisions_str}\n")

        # Add conversation history
        history = enriched_context.get("conversation_history", [])
        if history:
            parts.append(f"\n## 대화 히스토리 ({len(history)}개 메시지)\n")

            for i, msg in enumerate(history, 1):
                role = "사용자" if msg.get("role") == "user" else "AI"
                content = msg.get("content", "")[:1000]
                parts.append(f"**[{i}] {role}**: {content}\n")

        return "\n".join(parts)
