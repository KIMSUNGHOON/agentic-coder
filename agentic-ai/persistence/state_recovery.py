"""State Recovery Module for Agentic 2.0

Checkpoint-based state recovery:
- Load state from checkpoint
- Resume interrupted workflows
- State validation
- Recovery statistics
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
from core.state import AgenticState

logger = logging.getLogger(__name__)


class StateRecovery:
    """Manages state recovery from checkpoints

    Features:
    - Load state from checkpointer
    - Resume workflows from last checkpoint
    - List available checkpoints
    - State validation

    Example:
        >>> recovery = StateRecovery(checkpointer)
        >>> state = await recovery.load_state(thread_id="thread_abc123")
        >>> if state:
        ...     # Resume workflow with recovered state
        ...     result = await workflow.ainvoke(state, config={"thread_id": thread_id})
    """

    def __init__(self, checkpointer: BaseCheckpointSaver):
        """Initialize state recovery

        Args:
            checkpointer: LangGraph checkpointer instance
        """
        self.checkpointer = checkpointer
        self.recovery_count = 0

        logger.info("🔄 StateRecovery initialized")

    async def load_state(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[AgenticState]:
        """Load state from checkpoint

        Args:
            thread_id: Thread ID to load
            checkpoint_id: Optional specific checkpoint ID (defaults to latest)

        Returns:
            AgenticState or None if not found
        """
        try:
            # Get checkpoint
            if checkpoint_id:
                # Load specific checkpoint
                checkpoint = await self.checkpointer.aget(
                    {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
                )
            else:
                # Load latest checkpoint
                checkpoint = await self.checkpointer.aget(
                    {"configurable": {"thread_id": thread_id}}
                )

            if not checkpoint:
                logger.warning(f"No checkpoint found for thread: {thread_id}")
                return None

            # Extract state from checkpoint
            state = checkpoint.get("channel_values", {})

            if not state:
                logger.warning(f"Empty state in checkpoint: {thread_id}")
                return None

            self.recovery_count += 1
            logger.info(f"🔄 State loaded: thread {thread_id[:16]}")

            return state

        except Exception as e:
            logger.error(f"❌ Failed to load state: {e}")
            return None

    async def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List checkpoints for a thread

        Args:
            thread_id: Thread ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata
        """
        try:
            checkpoints = []

            # Get checkpoint history
            async for checkpoint_tuple in self.checkpointer.alist(
                {"configurable": {"thread_id": thread_id}},
                limit=limit
            ):
                checkpoint_metadata = {
                    "checkpoint_id": checkpoint_tuple.config.get("configurable", {}).get("checkpoint_id"),
                    "thread_id": thread_id,
                    "parent_checkpoint_id": checkpoint_tuple.parent_config.get("configurable", {}).get("checkpoint_id") if checkpoint_tuple.parent_config else None,
                }
                checkpoints.append(checkpoint_metadata)

            logger.info(f"📋 Found {len(checkpoints)} checkpoints for thread {thread_id[:16]}")
            return checkpoints

        except Exception as e:
            logger.error(f"❌ Failed to list checkpoints: {e}")
            return []

    async def has_checkpoint(self, thread_id: str) -> bool:
        """Check if thread has any checkpoints

        Args:
            thread_id: Thread ID

        Returns:
            True if checkpoints exist
        """
        try:
            checkpoint = await self.checkpointer.aget(
                {"configurable": {"thread_id": thread_id}}
            )
            return checkpoint is not None

        except Exception as e:
            logger.error(f"❌ Error checking checkpoint: {e}")
            return False

    def validate_state(self, state: AgenticState) -> bool:
        """Validate recovered state structure

        Args:
            state: State to validate

        Returns:
            True if valid
        """
        required_keys = [
            "task_id",
            "task_description",
            "task_type",
            "task_status",
            "workspace",
        ]

        for key in required_keys:
            if key not in state:
                logger.warning(f"Missing required key in state: {key}")
                return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics

        Returns:
            Dict with statistics
        """
        return {
            "recovery_count": self.recovery_count,
            "checkpointer_type": type(self.checkpointer).__name__,
        }


# Utility functions

async def can_resume(
    checkpointer: BaseCheckpointSaver,
    thread_id: str
) -> bool:
    """Check if a thread can be resumed

    Args:
        checkpointer: LangGraph checkpointer
        thread_id: Thread ID to check

    Returns:
        True if thread has checkpoints and can be resumed
    """
    recovery = StateRecovery(checkpointer)
    return await recovery.has_checkpoint(thread_id)


async def resume_workflow(
    workflow: Any,
    checkpointer: BaseCheckpointSaver,
    thread_id: str,
    input_data: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Resume a workflow from checkpoint

    Args:
        workflow: Compiled LangGraph workflow
        checkpointer: Checkpointer instance
        thread_id: Thread ID to resume
        input_data: Optional additional input data

    Returns:
        Workflow result or None if failed
    """
    try:
        # Check if checkpoint exists
        recovery = StateRecovery(checkpointer)
        has_checkpoint = await recovery.has_checkpoint(thread_id)

        if not has_checkpoint:
            logger.warning(f"Cannot resume: no checkpoint for thread {thread_id}")
            return None

        # Resume workflow with thread_id in config
        config = {"configurable": {"thread_id": thread_id}}

        if input_data:
            # Merge with existing state
            result = await workflow.ainvoke(input_data, config=config)
        else:
            # Resume from checkpoint without new input
            result = await workflow.ainvoke(None, config=config)

        logger.info(f"✅ Workflow resumed: thread {thread_id[:16]}")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to resume workflow: {e}")
        return None
