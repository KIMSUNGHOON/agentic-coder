"""HITL Manager

Core manager for Human-in-the-Loop functionality.
Handles workflow pause/resume and user response coordination.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

from .models import (
    HITLRequest,
    HITLResponse,
    HITLStatus,
    HITLAction,
    HITLEvent,
    HITLCheckpointType,
)

logger = logging.getLogger(__name__)


class HITLManager:
    """Manager for Human-in-the-Loop interactions

    This manager:
    1. Tracks pending HITL requests
    2. Coordinates with WebSocket for real-time UI updates
    3. Handles workflow pause/resume
    4. Manages request timeouts
    """

    def __init__(self):
        # Pending requests by request_id
        self._pending_requests: Dict[str, HITLRequest] = {}

        # Requests grouped by workflow_id
        self._workflow_requests: Dict[str, Set[str]] = defaultdict(set)

        # Events for async waiting
        self._response_events: Dict[str, asyncio.Event] = {}

        # Stored responses
        self._responses: Dict[str, HITLResponse] = {}

        # WebSocket broadcast callback (set by API layer)
        self._broadcast_callback: Optional[Callable] = None

        # Timeout tasks
        self._timeout_tasks: Dict[str, asyncio.Task] = {}

        logger.info("HITLManager initialized")

    def set_broadcast_callback(self, callback: Callable):
        """Set the WebSocket broadcast callback

        Args:
            callback: Async function to broadcast events to clients
        """
        self._broadcast_callback = callback
        logger.info("WebSocket broadcast callback set")

    async def request_human_input(
        self,
        request: HITLRequest,
        timeout_seconds: Optional[int] = None
    ) -> HITLResponse:
        """Request human input and wait for response

        This method:
        1. Registers the request
        2. Broadcasts to WebSocket
        3. Waits for user response (with optional timeout)
        4. Returns the response

        Args:
            request: The HITL request
            timeout_seconds: Optional timeout (overrides request.timeout_seconds)

        Returns:
            HITLResponse from user

        Raises:
            asyncio.TimeoutError: If request times out
        """
        request_id = request.request_id
        workflow_id = request.workflow_id

        logger.info(
            f"[HITL] Request created: {request_id} "
            f"(type={request.checkpoint_type.value}, workflow={workflow_id})"
        )

        # Register request
        self._pending_requests[request_id] = request
        self._workflow_requests[workflow_id].add(request_id)

        # Create event for async waiting
        self._response_events[request_id] = asyncio.Event()

        # Broadcast to WebSocket
        await self._broadcast_hitl_event(
            HITLEvent(
                event_type="hitl.request",
                workflow_id=workflow_id,
                request_id=request_id,
                data=request.model_dump()
            )
        )

        # Set up timeout if specified
        timeout = timeout_seconds or request.timeout_seconds
        if timeout:
            self._timeout_tasks[request_id] = asyncio.create_task(
                self._handle_timeout(request_id, timeout)
            )

        try:
            # Wait for response
            if timeout:
                await asyncio.wait_for(
                    self._response_events[request_id].wait(),
                    timeout=timeout
                )
            else:
                await self._response_events[request_id].wait()

            # Get and return response
            response = self._responses.get(request_id)
            if not response:
                raise ValueError(f"No response found for request {request_id}")

            logger.info(
                f"[HITL] Response received: {request_id} "
                f"(action={response.action.value})"
            )

            return response

        except asyncio.TimeoutError:
            logger.warning(f"[HITL] Request timed out: {request_id}")
            await self._handle_request_timeout(request_id)
            raise

        finally:
            # Cleanup
            self._cleanup_request(request_id)

    async def submit_response(self, response: HITLResponse) -> bool:
        """Submit user's response to a pending request

        Args:
            response: The user's response

        Returns:
            True if response was accepted, False otherwise
        """
        request_id = response.request_id

        if request_id not in self._pending_requests:
            logger.warning(f"[HITL] Response for unknown request: {request_id}")
            return False

        request = self._pending_requests[request_id]

        # Validate response action for checkpoint type
        if not self._validate_response(request, response):
            logger.warning(
                f"[HITL] Invalid response action {response.action} "
                f"for checkpoint type {request.checkpoint_type}"
            )
            return False

        # Update request status
        request.status = self._action_to_status(response.action)

        # Store response details on request for workflow to read
        request.response_action = response.action.value if hasattr(response.action, 'value') else response.action
        request.response_feedback = response.feedback

        # Store response
        self._responses[request_id] = response

        # Cancel timeout if exists
        if request_id in self._timeout_tasks:
            self._timeout_tasks[request_id].cancel()
            del self._timeout_tasks[request_id]

        # Signal waiting coroutine
        if request_id in self._response_events:
            self._response_events[request_id].set()

        # Broadcast response event
        await self._broadcast_hitl_event(
            HITLEvent(
                event_type="hitl.response",
                workflow_id=request.workflow_id,
                request_id=request_id,
                data=response.model_dump()
            )
        )

        logger.info(
            f"[HITL] Response submitted: {request_id} "
            f"(action={response.action.value})"
        )

        return True

    def get_pending_requests(self, workflow_id: Optional[str] = None) -> list[HITLRequest]:
        """Get all pending HITL requests

        Args:
            workflow_id: Optional filter by workflow ID

        Returns:
            List of pending requests
        """
        if workflow_id:
            request_ids = self._workflow_requests.get(workflow_id, set())
            return [
                self._pending_requests[rid]
                for rid in request_ids
                if rid in self._pending_requests
            ]
        return list(self._pending_requests.values())

    def get_request(self, request_id: str) -> Optional[HITLRequest]:
        """Get a specific HITL request

        Args:
            request_id: The request ID

        Returns:
            The request or None if not found
        """
        return self._pending_requests.get(request_id)

    async def cancel_request(self, request_id: str, reason: str = "Cancelled by user") -> bool:
        """Cancel a pending HITL request

        Args:
            request_id: The request to cancel
            reason: Cancellation reason

        Returns:
            True if cancelled, False if not found
        """
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        request.status = HITLStatus.CANCELLED

        # Create cancel response
        response = HITLResponse(
            request_id=request_id,
            action=HITLAction.CANCEL,
            feedback=reason
        )
        self._responses[request_id] = response

        # Signal waiting coroutine
        if request_id in self._response_events:
            self._response_events[request_id].set()

        # Broadcast cancellation
        await self._broadcast_hitl_event(
            HITLEvent(
                event_type="hitl.cancelled",
                workflow_id=request.workflow_id,
                request_id=request_id,
                data={"reason": reason}
            )
        )

        logger.info(f"[HITL] Request cancelled: {request_id} ({reason})")
        return True

    async def cancel_workflow_requests(self, workflow_id: str, reason: str = "Workflow cancelled"):
        """Cancel all pending requests for a workflow

        Args:
            workflow_id: The workflow ID
            reason: Cancellation reason
        """
        request_ids = list(self._workflow_requests.get(workflow_id, set()))
        for request_id in request_ids:
            await self.cancel_request(request_id, reason)

    # ==================== Private Methods ====================

    def _validate_response(self, request: HITLRequest, response: HITLResponse) -> bool:
        """Validate that response action is valid for checkpoint type"""
        valid_actions = {
            HITLCheckpointType.APPROVAL: {HITLAction.APPROVE, HITLAction.REJECT, HITLAction.CANCEL},
            HITLCheckpointType.REVIEW: {HITLAction.APPROVE, HITLAction.REJECT, HITLAction.RETRY, HITLAction.CANCEL},
            HITLCheckpointType.EDIT: {HITLAction.APPROVE, HITLAction.EDIT, HITLAction.REJECT, HITLAction.CANCEL},
            HITLCheckpointType.CHOICE: {HITLAction.SELECT, HITLAction.CANCEL},
            HITLCheckpointType.CONFIRM: {HITLAction.CONFIRM, HITLAction.CANCEL},
        }

        allowed = valid_actions.get(request.checkpoint_type, set())
        return response.action in allowed

    def _action_to_status(self, action: HITLAction) -> HITLStatus:
        """Convert action to status"""
        mapping = {
            HITLAction.APPROVE: HITLStatus.APPROVED,
            HITLAction.CONFIRM: HITLStatus.APPROVED,
            HITLAction.REJECT: HITLStatus.REJECTED,
            HITLAction.EDIT: HITLStatus.MODIFIED,
            HITLAction.RETRY: HITLStatus.PENDING,  # Will be retried
            HITLAction.SELECT: HITLStatus.SELECTED,
            HITLAction.CANCEL: HITLStatus.CANCELLED,
        }
        return mapping.get(action, HITLStatus.PENDING)

    async def _broadcast_hitl_event(self, event: HITLEvent):
        """Broadcast HITL event via WebSocket"""
        if self._broadcast_callback:
            try:
                await self._broadcast_callback(event)
            except Exception as e:
                logger.error(f"[HITL] Failed to broadcast event: {e}")
        else:
            logger.debug("[HITL] No broadcast callback set, event not sent")

    async def _handle_timeout(self, request_id: str, timeout_seconds: int):
        """Handle request timeout"""
        await asyncio.sleep(timeout_seconds)
        await self._handle_request_timeout(request_id)

    async def _handle_request_timeout(self, request_id: str):
        """Handle a request that has timed out"""
        if request_id not in self._pending_requests:
            return

        request = self._pending_requests[request_id]
        request.status = HITLStatus.TIMEOUT

        # Broadcast timeout event
        await self._broadcast_hitl_event(
            HITLEvent(
                event_type="hitl.timeout",
                workflow_id=request.workflow_id,
                request_id=request_id,
                data={"message": "Request timed out waiting for user input"}
            )
        )

    def _cleanup_request(self, request_id: str):
        """Clean up a completed/cancelled request"""
        if request_id in self._pending_requests:
            request = self._pending_requests[request_id]
            workflow_id = request.workflow_id

            # Remove from workflow tracking
            if workflow_id in self._workflow_requests:
                self._workflow_requests[workflow_id].discard(request_id)
                if not self._workflow_requests[workflow_id]:
                    del self._workflow_requests[workflow_id]

            # Remove request
            del self._pending_requests[request_id]

        # Remove event
        if request_id in self._response_events:
            del self._response_events[request_id]

        # Cancel timeout task if exists
        if request_id in self._timeout_tasks:
            self._timeout_tasks[request_id].cancel()
            del self._timeout_tasks[request_id]


# Global singleton instance
_hitl_manager: Optional[HITLManager] = None


def get_hitl_manager() -> HITLManager:
    """Get the global HITL manager instance"""
    global _hitl_manager
    if _hitl_manager is None:
        _hitl_manager = HITLManager()
    return _hitl_manager
