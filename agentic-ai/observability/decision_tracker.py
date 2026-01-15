"""Decision Tracker for Agentic 2.0

Tracks agent decisions:
- Decision recording
- Decision history
- Reasoning capture
- Statistics
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class Decision:
    """Agent decision record"""

    decision_id: str
    agent_name: str
    agent_type: str
    timestamp: datetime
    decision_type: str  # plan, execute, reflect, route, etc.
    decision: str  # The actual decision made
    reasoning: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None  # success, failure, pending

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class DecisionTracker:
    """Tracks agent decisions for observability

    Features:
    - Record all agent decisions
    - Capture reasoning
    - Track alternatives considered
    - Decision history per agent
    - Export to JSONL

    Example:
        >>> tracker = DecisionTracker(log_file="logs/decisions.jsonl")
        >>> tracker.record_decision(
        ...     agent_name="planner",
        ...     agent_type="workflow",
        ...     decision_type="plan",
        ...     decision="Execute 3 sequential steps",
        ...     reasoning="Task complexity requires structured approach",
        ...     confidence=0.85
        ... )
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        auto_save: bool = True
    ):
        """Initialize decision tracker

        Args:
            log_file: Path to JSONL log file for decisions
            auto_save: Auto-save decisions to file (default: True)
        """
        self.log_file = log_file
        self.auto_save = auto_save
        self.decisions: List[Decision] = []
        self._decision_counter = 0

        # Create log file if specified
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_decision(
        self,
        agent_name: str,
        agent_type: str,
        decision_type: str,
        decision: str,
        reasoning: Optional[str] = None,
        alternatives: Optional[List[str]] = None,
        confidence: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        """Record an agent decision

        Args:
            agent_name: Name of the agent
            agent_type: Type of agent
            decision_type: Type of decision (plan, execute, reflect, etc.)
            decision: The decision made
            reasoning: Reasoning behind the decision
            alternatives: Alternative options considered
            confidence: Confidence score (0.0-1.0)
            context: Additional context

        Returns:
            Decision object
        """
        self._decision_counter += 1
        decision_id = f"decision_{self._decision_counter:06d}"

        decision_obj = Decision(
            decision_id=decision_id,
            agent_name=agent_name,
            agent_type=agent_type,
            timestamp=datetime.now(),
            decision_type=decision_type,
            decision=decision,
            reasoning=reasoning,
            alternatives=alternatives or [],
            confidence=confidence,
            context=context or {},
        )

        self.decisions.append(decision_obj)

        # Auto-save to file
        if self.auto_save and self.log_file:
            self._save_decision(decision_obj)

        return decision_obj

    def update_outcome(
        self,
        decision_id: str,
        outcome: str
    ):
        """Update decision outcome

        Args:
            decision_id: Decision ID
            outcome: Outcome (success, failure, etc.)
        """
        for decision in self.decisions:
            if decision.decision_id == decision_id:
                decision.outcome = outcome

                # Re-save if auto-save enabled
                if self.auto_save and self.log_file:
                    self._save_decision(decision)

                break

    def get_decisions(
        self,
        agent_name: Optional[str] = None,
        decision_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Decision]:
        """Get decisions with optional filtering

        Args:
            agent_name: Filter by agent name
            decision_type: Filter by decision type
            limit: Limit number of results

        Returns:
            List of Decision objects
        """
        filtered = self.decisions

        if agent_name:
            filtered = [d for d in filtered if d.agent_name == agent_name]

        if decision_type:
            filtered = [d for d in filtered if d.decision_type == decision_type]

        if limit:
            filtered = filtered[-limit:]

        return filtered

    def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics

        Returns:
            Dict with statistics
        """
        if not self.decisions:
            return {
                "total_decisions": 0,
                "by_type": {},
                "by_agent": {},
                "avg_confidence": None,
            }

        # Count by type
        by_type: Dict[str, int] = {}
        for decision in self.decisions:
            by_type[decision.decision_type] = by_type.get(decision.decision_type, 0) + 1

        # Count by agent
        by_agent: Dict[str, int] = {}
        for decision in self.decisions:
            by_agent[decision.agent_name] = by_agent.get(decision.agent_name, 0) + 1

        # Average confidence
        confidences = [d.confidence for d in self.decisions if d.confidence is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None

        return {
            "total_decisions": len(self.decisions),
            "by_type": by_type,
            "by_agent": by_agent,
            "avg_confidence": avg_confidence,
        }

    def _save_decision(self, decision: Decision):
        """Save single decision to file"""
        if not self.log_file:
            return

        with open(self.log_file, "a") as f:
            f.write(json.dumps(decision.to_dict()) + "\n")

    def export_all(self, output_file: str):
        """Export all decisions to file

        Args:
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w") as f:
            for decision in self.decisions:
                f.write(json.dumps(decision.to_dict()) + "\n")

    def clear(self):
        """Clear all decisions"""
        self.decisions.clear()
        self._decision_counter = 0
