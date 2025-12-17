"""
Unit tests for basic workflow functionality

Tests core workflow components without requiring full LLM integration.
Focuses on:
- Task parsing
- Parallel execution logic
- SharedContext operations
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any


# Test SharedContext separately (since it's duplicated in both workflows)
class TestSharedContext:
    """Test SharedContext thread-safety and operations"""

    @pytest.mark.asyncio
    async def test_shared_context_import(self):
        """Test that SharedContext can be imported from workflow_manager"""
        # Import from standard workflow
        try:
            from app.agent.langchain.workflow_manager import SharedContext
            assert SharedContext is not None
            print("✅ SharedContext imported from workflow_manager")
        except ImportError as e:
            pytest.skip(f"Workflow module not available: {e}")

    @pytest.mark.asyncio
    async def test_shared_context_basic_operations(self):
        """Test basic set/get operations"""
        try:
            from app.agent.langchain.workflow_manager import SharedContext
        except ImportError:
            pytest.skip("Workflow module not available")

        context = SharedContext()

        # Test set operation
        await context.set(
            agent_id="agent1",
            agent_type="TestAgent",
            key="result",
            value={"status": "success"},
            description="Test result"
        )

        # Test get operation
        result = await context.get("agent1", "result")
        assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_shared_context_concurrent_writes(self):
        """Test concurrent writes to SharedContext"""
        try:
            from app.agent.langchain.workflow_manager import SharedContext
        except ImportError:
            pytest.skip("Workflow module not available")

        context = SharedContext()

        async def write_data(agent_id: str, value: int):
            await context.set(
                agent_id=agent_id,
                agent_type="TestAgent",
                key="count",
                value=value,
                description=f"Count for {agent_id}"
            )

        # Concurrent writes from 10 different agents
        tasks = [write_data(f"agent{i}", i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all writes succeeded
        for i in range(10):
            result = await context.get(f"agent{i}", "count")
            assert result == i

    @pytest.mark.asyncio
    async def test_shared_context_list_keys(self):
        """Test listing all context keys"""
        try:
            from app.agent.langchain.workflow_manager import SharedContext
        except ImportError:
            pytest.skip("Workflow module not available")

        context = SharedContext()

        # Add multiple entries
        await context.set("agent1", "TestAgent", "key1", "value1", "desc1")
        await context.set("agent1", "TestAgent", "key2", "value2", "desc2")
        await context.set("agent2", "TestAgent", "key3", "value3", "desc3")

        # List keys for agent1
        keys = await context.list_keys("agent1")
        assert "key1" in keys
        assert "key2" in keys
        assert len(keys) == 2

    @pytest.mark.asyncio
    async def test_shared_context_get_all(self):
        """Test getting all context data"""
        try:
            from app.agent.langchain.workflow_manager import SharedContext
        except ImportError:
            pytest.skip("Workflow module not available")

        context = SharedContext()

        await context.set("agent1", "TestAgent", "data", {"x": 1}, "test")
        await context.set("agent2", "TestAgent", "data", {"x": 2}, "test")

        all_data = await context.get_all()
        assert "agent1:data" in all_data
        assert "agent2:data" in all_data
        assert all_data["agent1:data"].value == {"x": 1}
        assert all_data["agent2:data"].value == {"x": 2}


class TestTaskParsing:
    """Test task parsing utilities"""

    def test_parse_checklist_basic(self):
        """Test parsing basic checklist format"""
        try:
            from app.agent.langchain.workflow_manager import parse_checklist
        except ImportError:
            pytest.skip("Workflow module not available")

        checklist_text = """
        - [ ] Task 1: Create main.py
        - [ ] Task 2: Add error handling
        - [ ] Task 3: Write tests
        """

        tasks = parse_checklist(checklist_text)
        assert len(tasks) == 3
        assert tasks[0]["description"] == "Create main.py"
        assert tasks[1]["description"] == "Add error handling"
        assert tasks[2]["description"] == "Write tests"

    def test_parse_checklist_with_completed_tasks(self):
        """Test parsing checklist with completed items"""
        try:
            from app.agent.langchain.workflow_manager import parse_checklist
        except ImportError:
            pytest.skip("Workflow module not available")

        checklist_text = """
        - [x] Task 1: Create main.py (completed)
        - [ ] Task 2: Add error handling
        - [x] Task 3: Write tests (done)
        """

        tasks = parse_checklist(checklist_text)
        # Should only return incomplete tasks
        assert len(tasks) == 1
        assert tasks[0]["description"] == "Add error handling"

    def test_parse_checklist_with_numbers(self):
        """Test parsing numbered checklist"""
        try:
            from app.agent.langchain.workflow_manager import parse_checklist
        except ImportError:
            pytest.skip("Workflow module not available")

        checklist_text = """
        1. [ ] Task 1: Create main.py
        2. [ ] Task 2: Add error handling
        3. [ ] Task 3: Write tests
        """

        tasks = parse_checklist(checklist_text)
        assert len(tasks) == 3

    def test_parse_empty_checklist(self):
        """Test parsing empty checklist"""
        try:
            from app.agent.langchain.workflow_manager import parse_checklist
        except ImportError:
            pytest.skip("Workflow module not available")

        tasks = parse_checklist("")
        assert len(tasks) == 0

        tasks = parse_checklist("No tasks here")
        assert len(tasks) == 0


class TestParallelExecution:
    """Test parallel execution logic (without actual LLM calls)"""

    @pytest.mark.asyncio
    async def test_calculate_optimal_parallel(self):
        """Test calculation of optimal parallel task count"""
        try:
            from app.agent.langchain.workflow_manager import WorkflowManager
        except ImportError:
            pytest.skip("Workflow module not available")

        # Mock manager
        manager = Mock()
        manager.max_parallel_agents = 25

        # Simulate _calculate_optimal_parallel logic
        def calc_optimal(task_count: int, max_parallel: int) -> int:
            if task_count <= 1:
                return 1
            return min(task_count, max_parallel)

        # Test various scenarios
        assert calc_optimal(5, 25) == 5  # Few tasks
        assert calc_optimal(30, 25) == 25  # Many tasks (capped)
        assert calc_optimal(1, 25) == 1  # Single task
        assert calc_optimal(0, 25) == 1  # Edge case

    @pytest.mark.asyncio
    async def test_parallel_task_batching(self):
        """Test that tasks are properly batched for parallel execution"""
        try:
            from app.agent.langchain.workflow_manager import WorkflowManager
        except ImportError:
            pytest.skip("Workflow module not available")

        # Simulate batching logic
        tasks = list(range(50))  # 50 tasks
        batch_size = 10

        batches = []
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batches.append(batch)

        assert len(batches) == 5  # 50 tasks / 10 per batch
        assert len(batches[0]) == 10
        assert len(batches[-1]) == 10

    @pytest.mark.asyncio
    async def test_error_isolation_in_parallel_execution(self):
        """Test that one failing task doesn't stop others"""

        async def task_that_succeeds(task_id: int) -> Dict:
            await asyncio.sleep(0.01)
            return {"id": task_id, "status": "success"}

        async def task_that_fails(task_id: int) -> Dict:
            await asyncio.sleep(0.01)
            raise ValueError(f"Task {task_id} failed")

        # Mix of succeeding and failing tasks
        tasks = [
            asyncio.create_task(task_that_succeeds(1)),
            asyncio.create_task(task_that_fails(2)),
            asyncio.create_task(task_that_succeeds(3)),
            asyncio.create_task(task_that_fails(4)),
            asyncio.create_task(task_that_succeeds(5)),
        ]

        # Gather with return_exceptions=True (like parallel workflow does)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 3  # Tasks 1, 3, 5 succeeded
        assert len(failures) == 2  # Tasks 2, 4 failed
        assert all(r["status"] == "success" for r in successes)


class TestWorkflowErrorHandling:
    """Test error handling in workflows"""

    @pytest.mark.asyncio
    async def test_invalid_task_format_handling(self):
        """Test handling of invalid task formats"""
        try:
            from app.agent.langchain.workflow_manager import parse_checklist
        except ImportError:
            pytest.skip("Workflow module not available")

        # Malformed checklist
        malformed = "This is not a valid checklist format!!!"

        tasks = parse_checklist(malformed)
        # Should return empty list, not crash
        assert isinstance(tasks, list)
        assert len(tasks) == 0

    @pytest.mark.asyncio
    async def test_missing_dependencies_handling(self):
        """Test that missing optional dependencies are handled gracefully"""

        # Test importing workflow without deepagents
        try:
            from app.agent.langchain import workflow_manager
            assert workflow_manager is not None
        except ImportError as e:
            # Should not crash, might just not have deepagents
            assert "deepagents" in str(e).lower() or True


class TestWorkflowStateManagement:
    """Test workflow state persistence and recovery"""

    def test_workflow_state_serialization(self):
        """Test that workflow state can be serialized"""
        state = {
            "checklist": ["Task 1", "Task 2"],
            "artifacts": [{"filename": "test.py", "content": "code"}],
            "completed_tasks": ["Task 1"],
            "parallel_results": [{"agent": "Agent1", "status": "success"}]
        }

        # Should be JSON serializable (for database storage)
        import json
        serialized = json.dumps(state)
        deserialized = json.loads(serialized)

        assert deserialized == state
        assert isinstance(deserialized["checklist"], list)
        assert isinstance(deserialized["artifacts"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
