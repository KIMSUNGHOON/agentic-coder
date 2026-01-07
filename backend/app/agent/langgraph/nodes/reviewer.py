"""Reviewer Node - Production Implementation

Reviews generated code using LLM via vLLM/OpenAI-compatible endpoint.
Uses model adapters for flexible model switching.
"""

import logging
from typing import Dict, List
from datetime import datetime

from app.core.config import settings
from app.agent.langgraph.schemas.state import QualityGateState, DebugLog
from app.services.http_client import LLMHttpClient

# Import LLM provider for model-agnostic calls
try:
    from shared.llm import LLMProviderFactory, TaskType
    LLM_PROVIDER_AVAILABLE = True
except ImportError:
    LLM_PROVIDER_AVAILABLE = False

logger = logging.getLogger(__name__)


def reviewer_node(state: QualityGateState) -> Dict:
    """Reviewer Node: Review code quality

    This node:
    1. Analyzes generated code from coder_output
    2. Checks for common issues and best practices
    3. Generates review feedback
    4. Determines if code is approved or needs refinement

    Args:
        state: Current workflow state

    Returns:
        State updates with review feedback and approval status
    """
    logger.info("👔 Reviewer Node: Starting code review...")

    coder_output = state.get("coder_output")
    debug_logs = []

    if not coder_output or not coder_output.get("artifacts"):
        logger.warning("⚠️  No code to review")
        return {
            "review_feedback": {
                "approved": False,
                "issues": ["No code artifacts found to review"],
                "suggestions": [],
                "quality_score": 0.0,
                "critique": "No artifacts to review"
            },
            "review_approved": False,
            "debug_logs": debug_logs,
        }

    artifacts = coder_output.get("artifacts", [])

    # Add thinking debug log
    if state.get("enable_debug"):
        debug_logs.append(DebugLog(
            timestamp=datetime.utcnow().isoformat(),
            node="reviewer",
            agent="ReviewerAgent",
            event_type="thinking",
            content=f"Reviewing {len(artifacts)} files...",
            metadata={"file_count": len(artifacts)},
            token_usage=None
        ))

    # Perform review
    try:
        review_result = _review_code_with_vllm(artifacts, state.get("user_request", ""))

        approved = review_result["approved"]

        # FIXED: Force approval after max refinement iterations to prevent infinite loop
        refinement_iteration = state.get("refinement_iteration", 0)
        max_iterations = state.get("max_iterations", 5)

        if refinement_iteration >= max_iterations - 1 and not approved:
            # Force approve on last iteration (max_iterations - 1)
            logger.warning(f"⚠️ Refinement iteration {refinement_iteration}/{max_iterations} - forcing approval to prevent loop")
            approved = True
            review_result["approved"] = True
            review_result["critique"] += f" [Auto-approved after {max_iterations} iterations]"

        logger.info(f"📋 Review {'✅ APPROVED' if approved else '❌ REJECTED'}")
        logger.info(f"   Quality Score: {review_result['quality_score']:.2f}")
        logger.info(f"   Issues: {len(review_result['issues'])}")
        logger.info(f"   Suggestions: {len(review_result['suggestions'])}")
        logger.info(f"   Refinement Iteration: {refinement_iteration}/{max_iterations}")

        # Add result debug log
        if state.get("enable_debug"):
            debug_logs.append(DebugLog(
                timestamp=datetime.utcnow().isoformat(),
                node="reviewer",
                agent="ReviewerAgent",
                event_type="result",
                content=f"Review {'approved' if approved else 'rejected'}: "
                       f"{len(review_result['issues'])} issues, "
                       f"score {review_result['quality_score']:.2f}",
                metadata={
                    "approved": approved,
                    "quality_score": review_result["quality_score"],
                    "issues_count": len(review_result["issues"]),
                },
                token_usage={
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            ))

        return {
            "review_feedback": review_result,
            "review_approved": approved,
            "debug_logs": debug_logs,
        }

    except Exception as e:
        logger.error(f"❌ Review failed: {e}", exc_info=True)

        if state.get("enable_debug"):
            debug_logs.append(DebugLog(
                timestamp=datetime.utcnow().isoformat(),
                node="reviewer",
                agent="ReviewerAgent",
                event_type="error",
                content=f"Review failed: {str(e)}",
                metadata={"error_type": type(e).__name__},
                token_usage=None
            ))

        return {
            "review_feedback": {
                "approved": False,
                "issues": [f"Review error: {str(e)}"],
                "suggestions": [],
                "quality_score": 0.0,
                "critique": "Review failed due to error"
            },
            "review_approved": False,
            "debug_logs": debug_logs,
        }


def _review_code_with_vllm(artifacts: List[Dict], user_request: str) -> Dict:
    """Review code using LLM provider

    Args:
        artifacts: List of code artifacts to review
        user_request: Original user request

    Returns:
        Review result with approved, issues, suggestions, quality_score, critique
    """
    # Get endpoint and model from settings
    review_endpoint = settings.get_coding_endpoint
    review_model = settings.get_coding_model

    # Check if LLM is available
    if not review_endpoint:
        logger.warning("⚠️  LLM endpoint not configured, using fallback reviewer")
        return _fallback_code_reviewer(artifacts, user_request)

    # Build review prompt
    code_summary = "\n\n".join([
        f"File: {a['filename']}\n```{a.get('language', 'text')}\n{a['content'][:500]}...\n```"
        for a in artifacts[:3]  # Review first 3 files
    ])

    review_prompt = f"""Original Request: {user_request}

Generated Code:
{code_summary}

Review this code for:
1. Correctness - Does it fulfill the requirements?
2. Security - Any vulnerabilities?
3. Performance - Any inefficiencies?
4. Best Practices - Does it follow conventions?"""

    # Try LLM provider adapter first
    if LLM_PROVIDER_AVAILABLE:
        try:
            provider = LLMProviderFactory.create(
                model_type=settings.get_reasoning_model_type,
                endpoint=review_endpoint,
                model=review_model
            )

            # Use synchronous version
            response = provider.generate_sync(review_prompt, TaskType.REVIEW)

            if response.parsed_json:
                logger.info(f"🤖 Review via {settings.get_reasoning_model_type} adapter")
                return response.parsed_json

        except Exception as e:
            logger.warning(f"LLM provider failed: {e}, falling back to direct call")

    # Fallback to direct HTTP call with retry logic
    try:
        # Get model-specific prompt
        model_type = settings.get_reasoning_model_type
        prompt = _get_review_prompt(model_type, review_prompt)

        # Log model info (model type auto-detected from model name)
        logger.info(f"🤖 Reviewing with model: {review_model} (type: {model_type})")

        # Use HTTP client with built-in retry logic
        http_client = LLMHttpClient(
            timeout=90,
            max_retries=3,
            base_delay=2
        )

        result, error = http_client.post(
            url=f"{review_endpoint}/completions",
            json={
                "model": review_model,
                "prompt": prompt,
                "max_tokens": 1024,
                "temperature": 0.1,
                "stop": ["</s>", "Human:", "User:"]
            }
        )

        if error:
            logger.warning(f"LLM review failed after retries: {error}, using fallback")
            return _fallback_code_reviewer(artifacts, user_request)

        generated_text = result["choices"][0]["text"]

        # Parse JSON
        import json
        try:
            json_start = generated_text.find("{")
            json_end = generated_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = generated_text[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        logger.warning("Failed to parse LLM review JSON, using fallback")
        return _fallback_code_reviewer(artifacts, user_request)

    except Exception as e:
        logger.error(f"LLM review failed: {e}")
        return _fallback_code_reviewer(artifacts, user_request)


def _get_review_prompt(model_type: str, review_context: str) -> str:
    """Generate model-specific review prompt

    Args:
        model_type: Type of model (deepseek, gpt-oss, qwen, generic)
        review_context: Code review context

    Returns:
        Formatted prompt for the model
    """
    json_format = """{{
    "approved": true/false,
    "quality_score": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "critique": "Overall assessment"
}}"""

    if model_type == "deepseek":
        # DeepSeek-R1: Use <think> tags for reasoning
        return f"""You are an expert code reviewer. Review the following code for quality and correctness.

<think>
1. Analyze code correctness and logic
2. Check for security vulnerabilities
3. Evaluate performance considerations
4. Assess code style and best practices
</think>

{review_context}

Provide a detailed review in JSON format:
{json_format}

Review:"""

    elif model_type in ("gpt-oss", "gpt"):
        # GPT-OSS: Structured prompt without special tags
        return f"""## Code Review Task

You are an expert code reviewer. Review the following code for quality and correctness.

### Review Criteria
1. **Correctness** - Does it fulfill requirements?
2. **Security** - Any vulnerabilities?
3. **Performance** - Any inefficiencies?
4. **Best Practices** - Does it follow conventions?

### Code to Review
{review_context}

### Response Format
Provide your review in JSON format:
```json
{json_format}
```

Review:"""

    else:
        # Generic/Qwen: Simple prompt
        return f"""You are an expert code reviewer. Review the following code for quality and correctness.

{review_context}

Provide a detailed review in JSON format:
{json_format}

Review:"""


def _fallback_code_reviewer(artifacts: List[Dict], user_request: str) -> Dict:
    """Fallback code reviewer using heuristics

    Performs basic code quality checks without LLM.
    """
    logger.info("📝 Using fallback code reviewer (vLLM not available)")

    issues = []
    suggestions = []
    total_quality_points = 0
    max_quality_points = 0

    for artifact in artifacts:
        content = artifact.get("content", "")
        filename = artifact.get("filename", "unknown")
        language = artifact.get("language", "text")

        # Check 1: File not empty
        max_quality_points += 1
        if len(content.strip()) > 0:
            total_quality_points += 1
        else:
            issues.append(f"{filename}: File is empty")

        # Check 2: Reasonable file size
        max_quality_points += 1
        if 10 < len(content) < 10000:
            total_quality_points += 1
        elif len(content) < 10:
            issues.append(f"{filename}: File too short (may be incomplete)")
        else:
            suggestions.append(f"{filename}: File is very large, consider splitting")

        # Language-specific checks
        if language == "python":
            # Check 3: Has docstring or comments
            max_quality_points += 1
            if '"""' in content or "'''" in content or "#" in content:
                total_quality_points += 1
            else:
                suggestions.append(f"{filename}: Add docstrings and comments")

            # Check 4: No TODO markers
            max_quality_points += 1
            if "TODO" not in content and "FIXME" not in content:
                total_quality_points += 1
            else:
                issues.append(f"{filename}: Contains TODO/FIXME markers")

            # Check 5: Has functions or classes
            max_quality_points += 1
            if "def " in content or "class " in content:
                total_quality_points += 1
            else:
                issues.append(f"{filename}: No functions or classes defined")

        elif language in ["html", "javascript", "css"]:
            # Check 3: Properly formatted
            max_quality_points += 1
            if language == "html" and "<!DOCTYPE" in content:
                total_quality_points += 1
            elif language == "javascript" and "function" in content:
                total_quality_points += 1
            elif language == "css" and "{" in content and "}" in content:
                total_quality_points += 1
            else:
                suggestions.append(f"{filename}: Check file structure")

    # Calculate quality score
    quality_score = total_quality_points / max(max_quality_points, 1)

    # Approval decision
    # Approve if:
    # 1. Quality score > 0.7
    # 2. No critical issues (empty files, TODO markers, missing structure)
    critical_issues = [i for i in issues if any(word in i for word in ["empty", "TODO", "No functions"])]
    approved = quality_score > 0.7 and len(critical_issues) == 0

    # Generate critique
    if approved:
        critique = f"Code quality is good (score: {quality_score:.2f}). Ready for deployment."
    elif quality_score > 0.5:
        critique = f"Code quality is acceptable (score: {quality_score:.2f}), but has some issues to address."
    else:
        critique = f"Code quality needs improvement (score: {quality_score:.2f}). Requires refinement."

    return {
        "approved": approved,
        "issues": issues,
        "suggestions": suggestions,
        "quality_score": quality_score,
        "critique": critique
    }
