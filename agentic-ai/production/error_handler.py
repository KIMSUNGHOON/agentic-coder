"""Error Handling for Agentic 2.0

Production error handling:
- Graceful degradation
- Error recovery
- User-friendly messages
"""

import logging
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"  # Minor issues, can continue
    MEDIUM = "medium"  # Recoverable errors
    HIGH = "high"  # Critical errors, may need intervention
    CRITICAL = "critical"  # System failure


class ErrorCategory(str, Enum):
    """Error categories"""
    LLM_ERROR = "llm_error"  # LLM API errors
    TOOL_ERROR = "tool_error"  # Tool execution errors
    WORKFLOW_ERROR = "workflow_error"  # Workflow errors
    NETWORK_ERROR = "network_error"  # Network/connectivity errors
    VALIDATION_ERROR = "validation_error"  # Input validation errors
    TIMEOUT_ERROR = "timeout_error"  # Timeout errors
    RESOURCE_ERROR = "resource_error"  # Resource exhaustion
    UNKNOWN_ERROR = "unknown_error"  # Unknown errors


class DegradationStrategy(str, Enum):
    """Degradation strategies"""
    REDUCE_FEATURES = "reduce_features"  # Reduce available features
    USE_CACHE = "use_cache"  # Use cached responses
    SIMPLIFY_OPERATIONS = "simplify_operations"  # Simplify operations
    PARTIAL_RESULTS = "partial_results"  # Return partial results


@dataclass
class ErrorInfo:
    """Error information"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    user_message: str
    timestamp: datetime
    details: Dict[str, Any]
    recoverable: bool
    recovery_suggestion: Optional[str] = None


class ErrorHandler:
    """Handle errors with graceful degradation

    Features:
    - Error categorization
    - Severity assessment
    - User-friendly messages
    - Error logging and tracking

    Example:
        >>> handler = ErrorHandler()
        >>> error_info = handler.handle_error(
        ...     exception=e,
        ...     context={"task": "coding"}
        ... )
        >>> print(error_info.user_message)
    """

    def __init__(self):
        """Initialize error handler"""
        self.error_count = 0
        self.errors: List[ErrorInfo] = []

    def handle_error(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        category: Optional[ErrorCategory] = None
    ) -> ErrorInfo:
        """Handle an error

        Args:
            exception: The exception
            context: Additional context
            category: Error category (auto-detected if None)

        Returns:
            ErrorInfo object
        """
        self.error_count += 1
        error_id = f"error_{self.error_count:06d}"

        # Detect category if not provided
        if category is None:
            category = self._detect_category(exception)

        # Determine severity
        severity = self._assess_severity(exception, category)

        # Check if recoverable
        recoverable = self._is_recoverable(exception, category)

        # Generate messages
        technical_message = str(exception)
        user_message = self._generate_user_message(exception, category)
        recovery_suggestion = self._get_recovery_suggestion(category) if recoverable else None

        # Create error info
        error_info = ErrorInfo(
            error_id=error_id,
            category=category,
            severity=severity,
            message=technical_message,
            user_message=user_message,
            timestamp=datetime.now(),
            details=context or {},
            recoverable=recoverable,
            recovery_suggestion=recovery_suggestion
        )

        # Log error
        self._log_error(error_info)

        # Store for tracking
        self.errors.append(error_info)

        return error_info

    def _detect_category(self, exception: Exception) -> ErrorCategory:
        """Detect error category from exception"""
        exception_type = type(exception).__name__

        # LLM errors
        if any(keyword in exception_type.lower() for keyword in ["openai", "llm", "api"]):
            return ErrorCategory.LLM_ERROR

        # Timeout errors (check before network errors)
        if "timeout" in exception_type.lower():
            return ErrorCategory.TIMEOUT_ERROR

        # Network errors
        if any(keyword in exception_type.lower() for keyword in ["connection", "network"]):
            return ErrorCategory.NETWORK_ERROR

        # Validation errors
        if any(keyword in exception_type.lower() for keyword in ["validation", "value", "type"]):
            return ErrorCategory.VALIDATION_ERROR

        return ErrorCategory.UNKNOWN_ERROR

    def _assess_severity(
        self,
        exception: Exception,
        category: ErrorCategory
    ) -> ErrorSeverity:
        """Assess error severity"""
        # Critical categories
        if category in [ErrorCategory.LLM_ERROR, ErrorCategory.WORKFLOW_ERROR]:
            return ErrorSeverity.HIGH

        # Medium severity
        if category in [ErrorCategory.TOOL_ERROR, ErrorCategory.NETWORK_ERROR]:
            return ErrorSeverity.MEDIUM

        # Low severity
        if category in [ErrorCategory.VALIDATION_ERROR]:
            return ErrorSeverity.LOW

        return ErrorSeverity.MEDIUM

    def _is_recoverable(
        self,
        exception: Exception,
        category: ErrorCategory
    ) -> bool:
        """Check if error is recoverable"""
        # Network and timeout errors are usually recoverable
        if category in [ErrorCategory.NETWORK_ERROR, ErrorCategory.TIMEOUT_ERROR]:
            return True

        # Tool errors may be recoverable
        if category == ErrorCategory.TOOL_ERROR:
            return True

        # LLM errors may be recoverable with retry
        if category == ErrorCategory.LLM_ERROR:
            return True

        return False

    def _generate_user_message(
        self,
        exception: Exception,
        category: ErrorCategory
    ) -> str:
        """Generate user-friendly error message"""
        messages = {
            ErrorCategory.LLM_ERROR: "AI model encountered an issue. Retrying with backup endpoint...",
            ErrorCategory.TOOL_ERROR: "Tool execution failed. Attempting alternative approach...",
            ErrorCategory.WORKFLOW_ERROR: "Workflow encountered an error. Please check your input.",
            ErrorCategory.NETWORK_ERROR: "Network connection issue. Retrying...",
            ErrorCategory.VALIDATION_ERROR: "Input validation failed. Please check your parameters.",
            ErrorCategory.TIMEOUT_ERROR: "Operation timed out. Retrying with extended timeout...",
            ErrorCategory.RESOURCE_ERROR: "System resources exhausted. Please try again later.",
            ErrorCategory.UNKNOWN_ERROR: "An unexpected error occurred. Our team has been notified.",
        }

        return messages.get(category, "An error occurred. Please try again.")

    def _get_recovery_suggestion(self, category: ErrorCategory) -> str:
        """Get recovery suggestion"""
        suggestions = {
            ErrorCategory.LLM_ERROR: "Retry with backup endpoint or reduce complexity",
            ErrorCategory.TOOL_ERROR: "Try alternative tool or simplify parameters",
            ErrorCategory.NETWORK_ERROR: "Check network connection and retry",
            ErrorCategory.TIMEOUT_ERROR: "Increase timeout or simplify task",
        }

        return suggestions.get(category, "Retry the operation")

    def _log_error(self, error_info: ErrorInfo):
        """Log error with appropriate level"""
        log_message = (
            f"[{error_info.error_id}] {error_info.category.value}: "
            f"{error_info.message}"
        )

        if error_info.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        if not self.errors:
            return {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "recoverable_count": 0,
            }

        by_category = {}
        for error in self.errors:
            cat = error.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        by_severity = {}
        for error in self.errors:
            sev = error.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

        recoverable_count = sum(1 for e in self.errors if e.recoverable)

        return {
            "total_errors": len(self.errors),
            "by_category": by_category,
            "by_severity": by_severity,
            "recoverable_count": recoverable_count,
        }


class ErrorRecovery:
    """Automatic error recovery strategies

    Features:
    - Retry with backoff
    - Fallback execution
    - Alternative approaches
    - State recovery

    Example:
        >>> recovery = ErrorRecovery()
        >>> result = await recovery.retry_with_backoff(
        ...     func=api_call,
        ...     max_retries=3
        ... )
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0
    ):
        """Initialize error recovery

        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: Optional[int] = None,
        **kwargs
    ) -> Any:
        """Retry function with exponential backoff

        Args:
            func: Function to retry
            *args: Function arguments
            max_retries: Max retries (overrides default)
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        import asyncio

        max_retries = max_retries or self.max_retries
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay
                    )

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed")

        raise last_exception

    async def try_with_fallback(
        self,
        primary_func: Callable,
        fallback_func: Callable,
        *args,
        **kwargs
    ) -> tuple[Any, bool]:
        """Try primary function, fallback if fails

        Args:
            primary_func: Primary function to try
            fallback_func: Fallback function
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            (result, used_fallback)
        """
        import asyncio

        try:
            if asyncio.iscoroutinefunction(primary_func):
                result = await primary_func(*args, **kwargs)
            else:
                result = primary_func(*args, **kwargs)

            return result, False

        except Exception as e:
            logger.warning(f"Primary function failed: {e}. Using fallback...")

            try:
                if asyncio.iscoroutinefunction(fallback_func):
                    result = await fallback_func(*args, **kwargs)
                else:
                    result = fallback_func(*args, **kwargs)

                return result, True

            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise


class GracefulDegradation:
    """Graceful degradation strategies

    Features:
    - Reduced functionality mode
    - Cached responses
    - Simplified operations
    - Partial results

    Example:
        >>> degradation = GracefulDegradation()
        >>> result = degradation.degrade_if_needed(
        ...     normal_func=complex_operation,
        ...     degraded_func=simple_operation,
        ...     health_check=lambda: system_healthy()
        ... )
    """

    def __init__(self):
        """Initialize graceful degradation"""
        self.degraded_mode = False
        self.degradation_reason: Optional[str] = None
        self.degradation_strategy: Optional[DegradationStrategy] = None

    def enter_degraded_mode(
        self,
        reason: str,
        strategy: DegradationStrategy = DegradationStrategy.REDUCE_FEATURES
    ):
        """Enter degraded mode

        Args:
            reason: Reason for degradation
            strategy: Degradation strategy to apply
        """
        self.degraded_mode = True
        self.degradation_reason = reason
        self.degradation_strategy = strategy
        logger.warning(f"Entering degraded mode: {reason} (strategy: {strategy})")

    def exit_degraded_mode(self):
        """Exit degraded mode"""
        logger.info("Exiting degraded mode")
        self.degraded_mode = False
        self.degradation_reason = None
        self.degradation_strategy = None

    def is_degraded(self) -> bool:
        """Check if in degraded mode

        Returns:
            True if in degraded mode
        """
        return self.degraded_mode

    def get_current_strategy(self) -> Optional[DegradationStrategy]:
        """Get current degradation strategy

        Returns:
            Current strategy or None if not degraded
        """
        return self.degradation_strategy

    async def degrade_if_needed(
        self,
        normal_func: Callable,
        degraded_func: Callable,
        health_check: Callable[[], bool],
        *args,
        **kwargs
    ) -> tuple[Any, bool]:
        """Execute with degradation if needed

        Args:
            normal_func: Normal function
            degraded_func: Degraded version
            health_check: Function to check if degradation needed
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            (result, was_degraded)
        """
        import asyncio

        # Check if we need to degrade
        is_healthy = health_check()

        if not is_healthy or self.degraded_mode:
            logger.info("Using degraded functionality")

            if asyncio.iscoroutinefunction(degraded_func):
                result = await degraded_func(*args, **kwargs)
            else:
                result = degraded_func(*args, **kwargs)

            return result, True

        # Try normal operation
        try:
            if asyncio.iscoroutinefunction(normal_func):
                result = await normal_func(*args, **kwargs)
            else:
                result = normal_func(*args, **kwargs)

            return result, False

        except Exception as e:
            logger.error(f"Normal operation failed: {e}. Degrading...")

            if asyncio.iscoroutinefunction(degraded_func):
                result = await degraded_func(*args, **kwargs)
            else:
                result = degraded_func(*args, **kwargs)

            return result, True
