"""Chain-of-Thought Viewer Component

Displays GPT-OSS-120B reasoning process.
"""

from textual.widgets import RichLog
from rich.text import Text
from rich.panel import Panel
from datetime import datetime


class CoTViewer(RichLog):
    """Chain-of-Thought display

    Shows <think> blocks from GPT-OSS-120B:
    - Step-by-step reasoning
    - Decision points
    - Alternative considerations
    - Confidence levels
    """

    def __init__(self, **kwargs):
        super().__init__(
            highlight=True,
            markup=True,
            wrap=True,
            max_lines=500,
            **kwargs
        )
        self.can_focus = False
        self.reasoning_count = 0

    def add_thinking(self, content: str, step: int = None) -> None:
        """Add a thinking block

        Args:
            content: Thinking content
            step: Step number (optional)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        text = Text()
        text.append(f"[{timestamp}] ", style="dim")

        if step is not None:
            text.append(f"Step {step}", style="bold magenta")
        else:
            text.append("Thinking", style="bold magenta")

        text.append("\n", style="dim")
        text.append(content, style="italic white")

        self.write(Panel(
            text,
            border_style="magenta dim",
            padding=(0, 1),
            title="🤔 CoT"
        ))

        self.reasoning_count += 1

    def add_decision(
        self,
        decision: str,
        reasoning: str,
        confidence: float = None
    ) -> None:
        """Add a decision point

        Args:
            decision: Decision made
            reasoning: Reasoning behind decision
            confidence: Confidence level (0.0-1.0)
        """
        text = Text()
        text.append("Decision: ", style="bold cyan")
        text.append(decision, style="white")
        text.append("\n\n", style="dim")

        text.append("Reasoning: ", style="bold cyan")
        text.append(reasoning, style="white")

        if confidence is not None:
            text.append("\n\n", style="dim")
            text.append("Confidence: ", style="bold cyan")

            conf_pct = int(confidence * 100)
            if confidence >= 0.8:
                style = "green"
            elif confidence >= 0.6:
                style = "yellow"
            else:
                style = "red"

            text.append(f"{conf_pct}%", style=f"bold {style}")

        self.write(Panel(
            text,
            border_style="cyan",
            padding=(0, 1),
            title="💡 Decision"
        ))

    def add_alternatives(self, alternatives: list[str]) -> None:
        """Add alternative options considered

        Args:
            alternatives: List of alternative options
        """
        text = Text()
        text.append("Alternatives Considered:\n", style="bold yellow")

        for i, alt in enumerate(alternatives, 1):
            text.append(f"\n{i}. ", style="dim")
            text.append(alt, style="white")

        self.write(Panel(
            text,
            border_style="yellow dim",
            padding=(0, 1),
            title="⚖️  Alternatives"
        ))

    def add_reasoning_summary(
        self,
        total_steps: int,
        duration: float
    ) -> None:
        """Add reasoning summary

        Args:
            total_steps: Total reasoning steps
            duration: Total duration in seconds
        """
        text = Text()
        text.append("Reasoning Complete\n\n", style="bold green")
        text.append(f"Steps: {total_steps}\n", style="white")
        text.append(f"Duration: {duration:.2f}s", style="white")

        self.write(Panel(
            text,
            border_style="green",
            padding=(0, 1),
            title="✅ Summary"
        ))
