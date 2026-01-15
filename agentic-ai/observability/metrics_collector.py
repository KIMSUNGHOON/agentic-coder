"""Metrics Collector for Agentic 2.0

Performance metrics collection:
- Custom metrics
- Counters and gauges
- Histograms
- Export and reporting
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from enum import Enum


class MetricType(str, Enum):
    """Metric types"""
    COUNTER = "counter"  # Incrementing value
    GAUGE = "gauge"  # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution of values
    TIMER = "timer"  # Duration measurements


@dataclass
class Metric:
    """Metric record"""

    metric_id: str
    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["metric_type"] = self.metric_type.value
        return d


class MetricsCollector:
    """Collects and tracks performance metrics

    Features:
    - Multiple metric types (counter, gauge, histogram, timer)
    - Tagged metrics for filtering
    - Aggregation and statistics
    - Export to JSONL

    Example:
        >>> collector = MetricsCollector(log_file="logs/metrics.jsonl")
        >>> collector.increment("workflow.executions", tags={"domain": "coding"})
        >>> collector.gauge("active.agents", 3)
        >>> collector.timer("llm.call.duration", 1.5, tags={"model": "gpt-oss-120b"})
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        auto_save: bool = True
    ):
        """Initialize metrics collector

        Args:
            log_file: Path to JSONL log file for metrics
            auto_save: Auto-save metrics to file (default: True)
        """
        self.log_file = log_file
        self.auto_save = auto_save
        self.metrics: List[Metric] = []
        self._metric_counter = 0
        self._counters: Dict[str, float] = {}

        # Create log file if specified
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        unit: Optional[str] = None
    ) -> Metric:
        """Record a metric

        Args:
            name: Metric name
            metric_type: Type of metric
            value: Metric value
            tags: Optional tags for filtering
            unit: Optional unit (seconds, bytes, etc.)

        Returns:
            Metric object
        """
        self._metric_counter += 1
        metric_id = f"metric_{self._metric_counter:06d}"

        metric = Metric(
            metric_id=metric_id,
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {},
            unit=unit,
        )

        self.metrics.append(metric)

        # Auto-save to file
        if self.auto_save and self.log_file:
            self._save_metric(metric)

        return metric

    def counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record counter metric (cumulative)

        Args:
            name: Counter name
            value: Value to add (default: 1.0)
            tags: Optional tags
        """
        # Update internal counter
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

        # Record metric
        self.record(name, MetricType.COUNTER, value, tags)

    def increment(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ):
        """Increment counter by 1

        Args:
            name: Counter name
            tags: Optional tags
        """
        self.counter(name, 1.0, tags)

    def gauge(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        unit: Optional[str] = None
    ):
        """Record gauge metric (point-in-time value)

        Args:
            name: Gauge name
            value: Current value
            tags: Optional tags
            unit: Optional unit
        """
        self.record(name, MetricType.GAUGE, value, tags, unit)

    def histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        unit: Optional[str] = None
    ):
        """Record histogram metric (distribution)

        Args:
            name: Histogram name
            value: Value to record
            tags: Optional tags
            unit: Optional unit
        """
        self.record(name, MetricType.HISTOGRAM, value, tags, unit)

    def timer(
        self,
        name: str,
        duration: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record timer metric (duration)

        Args:
            name: Timer name
            duration: Duration in seconds
            tags: Optional tags
        """
        self.record(name, MetricType.TIMER, duration, tags, unit="seconds")

    def get_counter_value(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None
    ) -> float:
        """Get current counter value

        Args:
            name: Counter name
            tags: Optional tags

        Returns:
            Current counter value
        """
        key = self._make_key(name, tags)
        return self._counters.get(key, 0.0)

    def get_metrics(
        self,
        name: Optional[str] = None,
        metric_type: Optional[MetricType] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None
    ) -> List[Metric]:
        """Get metrics with optional filtering

        Args:
            name: Filter by name
            metric_type: Filter by type
            tags: Filter by tags
            limit: Limit number of results

        Returns:
            List of Metric objects
        """
        filtered = self.metrics

        if name:
            filtered = [m for m in filtered if m.name == name]

        if metric_type:
            filtered = [m for m in filtered if m.metric_type == metric_type]

        if tags:
            filtered = [
                m for m in filtered
                if all(m.tags.get(k) == v for k, v in tags.items())
            ]

        if limit:
            filtered = filtered[-limit:]

        return filtered

    def get_stats(
        self,
        name: Optional[str] = None,
        metric_type: Optional[MetricType] = None
    ) -> Dict[str, Any]:
        """Get metric statistics

        Args:
            name: Filter by name
            metric_type: Filter by type

        Returns:
            Dict with statistics
        """
        filtered = self.get_metrics(name=name, metric_type=metric_type)

        if not filtered:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "sum": None,
            }

        values = [m.value for m in filtered]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "sum": sum(values),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get overall metrics summary

        Returns:
            Dict with summary statistics
        """
        if not self.metrics:
            return {
                "total_metrics": 0,
                "by_type": {},
                "by_name": {},
            }

        # Count by type
        by_type: Dict[str, int] = {}
        for metric in self.metrics:
            type_str = metric.metric_type.value
            by_type[type_str] = by_type.get(type_str, 0) + 1

        # Count by name
        by_name: Dict[str, int] = {}
        for metric in self.metrics:
            by_name[metric.name] = by_name.get(metric.name, 0) + 1

        return {
            "total_metrics": len(self.metrics),
            "by_type": by_type,
            "by_name": by_name,
            "counters": dict(self._counters),
        }

    def _make_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Make key for counter storage"""
        if not tags:
            return name

        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def _save_metric(self, metric: Metric):
        """Save single metric to file"""
        if not self.log_file:
            return

        with open(self.log_file, "a") as f:
            f.write(json.dumps(metric.to_dict()) + "\n")

    def export_all(self, output_file: str):
        """Export all metrics to file

        Args:
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            for metric in self.metrics:
                f.write(json.dumps(metric.to_dict()) + "\n")

    def clear(self):
        """Clear all metrics"""
        self.metrics.clear()
        self._metric_counter = 0
        self._counters.clear()
