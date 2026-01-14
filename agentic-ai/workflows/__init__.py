"""Workflows Module for Agentic 2.0

LangGraph-based workflow orchestration:
- Base workflow orchestrator
- Domain-specific workflows (coding, research, data, general)
- State machine execution
- Sub-agent coordination
"""

from .orchestrator import WorkflowOrchestrator
from .base_workflow import BaseWorkflow, WorkflowResult
from .coding_workflow import CodingWorkflow
from .research_workflow import ResearchWorkflow
from .data_workflow import DataWorkflow
from .general_workflow import GeneralWorkflow

__all__ = [
    "WorkflowOrchestrator",
    "BaseWorkflow",
    "WorkflowResult",
    "CodingWorkflow",
    "ResearchWorkflow",
    "DataWorkflow",
    "GeneralWorkflow",
]
