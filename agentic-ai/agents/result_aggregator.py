"""Result Aggregator for Agentic 2.0

Combines results from multiple sub-agents:
- Result merging strategies
- Conflict resolution
- Summary generation
- Context combination
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from core.llm_client import DualEndpointLLMClient
from .parallel_executor import ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class AggregationStrategy(str, Enum):
    """Strategy for aggregating results"""
    CONCATENATE = "concatenate"  # Simple concatenation
    SUMMARIZE = "summarize"  # LLM-based summarization
    MERGE_JSON = "merge_json"  # Merge JSON objects
    LIST = "list"  # Keep as list of results


@dataclass
class AggregatedResult:
    """Aggregated result from multiple sub-agents"""
    original_task: str
    success: bool
    strategy: AggregationStrategy
    combined_result: Any
    individual_results: List[ExecutionResult]
    total_duration_seconds: float
    success_count: int
    failure_count: int
    summary: str
    errors: List[str]
    metadata: Dict[str, Any]


class ResultAggregator:
    """Aggregates results from multiple sub-agents

    Features:
    - Multiple aggregation strategies
    - LLM-based summarization
    - Error collection
    - Statistics tracking

    Example:
        >>> aggregator = ResultAggregator(llm_client)
        >>> aggregated = await aggregator.aggregate(
        ...     results=execution_results,
        ...     original_task="Analyze codebase",
        ...     strategy=AggregationStrategy.SUMMARIZE
        ... )
        >>> print(aggregated.combined_result)
    """

    def __init__(self, llm_client: Optional[DualEndpointLLMClient] = None):
        """Initialize result aggregator

        Args:
            llm_client: Optional LLM client for summarization
        """
        self.llm_client = llm_client

    async def aggregate(
        self,
        results: List[ExecutionResult],
        original_task: str,
        strategy: AggregationStrategy = AggregationStrategy.CONCATENATE
    ) -> AggregatedResult:
        """Aggregate results from multiple executions

        Args:
            results: List of execution results
            original_task: Original task description
            strategy: Aggregation strategy

        Returns:
            AggregatedResult with combined result
        """
        logger.info(f"📊 Aggregating {len(results)} results using {strategy}")

        # Separate successful and failed results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        success_count = len(successful)
        failure_count = len(failed)

        # Calculate total duration (max if parallel, sum if sequential)
        # Assume parallel if results have overlapping times
        total_duration = self._calculate_total_duration(results)

        # Collect errors
        errors = [r.error for r in failed if r.error]

        # Aggregate based on strategy
        if strategy == AggregationStrategy.CONCATENATE:
            combined_result = await self._concatenate_results(successful)
        elif strategy == AggregationStrategy.SUMMARIZE:
            combined_result = await self._summarize_results(successful, original_task)
        elif strategy == AggregationStrategy.MERGE_JSON:
            combined_result = await self._merge_json_results(successful)
        elif strategy == AggregationStrategy.LIST:
            combined_result = [r.result for r in successful]
        else:
            combined_result = await self._concatenate_results(successful)

        # Generate summary
        summary = await self._generate_summary(
            original_task=original_task,
            success_count=success_count,
            failure_count=failure_count,
            combined_result=combined_result
        )

        # Overall success
        overall_success = failure_count == 0 and success_count > 0

        aggregated = AggregatedResult(
            original_task=original_task,
            success=overall_success,
            strategy=strategy,
            combined_result=combined_result,
            individual_results=results,
            total_duration_seconds=total_duration,
            success_count=success_count,
            failure_count=failure_count,
            summary=summary,
            errors=errors,
            metadata={
                "aggregated_at": datetime.now().isoformat(),
                "result_count": len(results),
                "strategy": strategy.value
            }
        )

        logger.info(f"✅ Aggregation complete: {success_count} succeeded, {failure_count} failed")

        return aggregated

    async def _concatenate_results(self, results: List[ExecutionResult]) -> str:
        """Concatenate results with separators"""
        if not results:
            return ""

        parts = []
        for result in results:
            if result.result:
                parts.append(f"=== {result.subtask_id} ===\n{result.result}\n")

        return "\n".join(parts)

    async def _summarize_results(
        self,
        results: List[ExecutionResult],
        original_task: str
    ) -> str:
        """Summarize results using LLM"""
        if not self.llm_client:
            logger.warning("No LLM client available for summarization, falling back to concatenation")
            return await self._concatenate_results(results)

        if not results:
            return "No successful results to summarize"

        # Combine results
        combined = await self._concatenate_results(results)

        # Ask LLM to summarize
        summary_prompt = f"""Summarize the results from multiple sub-tasks.

Original Task: {original_task}

Results from {len(results)} sub-tasks:
{combined}

Provide a concise summary that:
1. Highlights key findings
2. Notes any patterns or insights
3. Identifies any issues or gaps
4. Gives an overall assessment

Keep the summary under 500 words.
"""

        try:
            messages = [
                {"role": "system", "content": "You are an expert at synthesizing information."},
                {"role": "user", "content": summary_prompt}
            ]

            response = await self.llm_client.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=1000
            )

            summary = response.choices[0].message.content
            return summary

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return await self._concatenate_results(results)

    async def _merge_json_results(self, results: List[ExecutionResult]) -> Dict[str, Any]:
        """Merge JSON results into single object"""
        merged = {}

        for result in results:
            if not result.result:
                continue

            # Try to parse as JSON
            try:
                if isinstance(result.result, str):
                    data = json.loads(result.result)
                elif isinstance(result.result, dict):
                    data = result.result
                else:
                    # Store as-is
                    merged[result.subtask_id] = result.result
                    continue

                # Merge dict
                merged[result.subtask_id] = data

            except json.JSONDecodeError:
                # Not JSON, store as string
                merged[result.subtask_id] = result.result

        return merged

    async def _generate_summary(
        self,
        original_task: str,
        success_count: int,
        failure_count: int,
        combined_result: Any
    ) -> str:
        """Generate summary of aggregation"""
        total = success_count + failure_count

        summary_parts = [
            f"Task: {original_task}",
            f"Results: {success_count}/{total} successful"
        ]

        if failure_count > 0:
            summary_parts.append(f"Failures: {failure_count}")

        # Add result preview
        if combined_result:
            if isinstance(combined_result, str):
                preview = combined_result[:200]
                if len(combined_result) > 200:
                    preview += "..."
                summary_parts.append(f"Result preview: {preview}")
            elif isinstance(combined_result, dict):
                summary_parts.append(f"Result keys: {', '.join(combined_result.keys())}")
            elif isinstance(combined_result, list):
                summary_parts.append(f"Result count: {len(combined_result)}")

        return " | ".join(summary_parts)

    def _calculate_total_duration(self, results: List[ExecutionResult]) -> float:
        """Calculate total duration

        If tasks overlap (parallel), use max duration
        If tasks are sequential, use sum of durations
        """
        if not results:
            return 0.0

        # Check if tasks have overlapping execution times
        results_with_times = [r for r in results if r.started_at and r.completed_at]

        if not results_with_times:
            # No timing info, sum durations
            return sum(r.duration_seconds for r in results)

        # Sort by start time
        sorted_results = sorted(results_with_times, key=lambda r: r.started_at)

        # Check for overlaps
        has_overlap = False
        for i in range(len(sorted_results) - 1):
            current_end = sorted_results[i].completed_at
            next_start = sorted_results[i + 1].started_at

            if current_end > next_start:
                has_overlap = True
                break

        if has_overlap:
            # Parallel execution - use span from first start to last end
            first_start = min(r.started_at for r in results_with_times)
            last_end = max(r.completed_at for r in results_with_times)
            return (last_end - first_start).total_seconds()
        else:
            # Sequential execution - sum durations
            return sum(r.duration_seconds for r in results)

    def format_report(self, aggregated: AggregatedResult) -> str:
        """Format aggregated result as readable report"""
        lines = [
            "=" * 80,
            "AGGREGATED RESULTS REPORT",
            "=" * 80,
            "",
            f"Original Task: {aggregated.original_task}",
            f"Success: {aggregated.success}",
            f"Strategy: {aggregated.strategy.value}",
            "",
            f"Results: {aggregated.success_count}/{aggregated.success_count + aggregated.failure_count} successful",
            f"Total Duration: {aggregated.total_duration_seconds:.1f}s",
            "",
            "Summary:",
            aggregated.summary,
            ""
        ]

        if aggregated.errors:
            lines.append("Errors:")
            for i, error in enumerate(aggregated.errors, 1):
                lines.append(f"  {i}. {error}")
            lines.append("")

        lines.append("Combined Result:")
        if isinstance(aggregated.combined_result, str):
            lines.append(aggregated.combined_result)
        else:
            lines.append(json.dumps(aggregated.combined_result, indent=2))

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)


# Add missing import
from dataclasses import dataclass
