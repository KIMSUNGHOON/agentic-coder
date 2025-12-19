"""Human-in-the-Loop (HITL) System

This module provides comprehensive HITL capabilities for the multi-agent workflow:
- 5 checkpoint types: approval, review, edit, choice, confirm
- WebSocket-based real-time communication
- Workflow pause/resume functionality
- Async event handling for user responses
"""

from .models import (
    HITLCheckpointType,
    HITLRequest,
    HITLResponse,
    HITLStatus,
)
from .manager import HITLManager, get_hitl_manager

__all__ = [
    "HITLCheckpointType",
    "HITLRequest",
    "HITLResponse",
    "HITLStatus",
    "HITLManager",
    "get_hitl_manager",
]
