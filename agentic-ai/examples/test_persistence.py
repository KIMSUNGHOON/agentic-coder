"""Test Persistence System

Demonstrates:
1. CheckpointerManager - SQLite/PostgreSQL checkpointer
2. SessionManager - Session and thread management
3. StateRecovery - Load state from checkpoints
4. Workflow integration with checkpointing
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence import (
    CheckpointerManager,
    create_sqlite_checkpointer,
    SessionManager,
    Session,
    StateRecovery,
)
from core.state import create_initial_state
from core.config_loader import load_config


def test_session_manager():
    """Test SessionManager"""
    print("=" * 60)
    print("Testing SessionManager")
    print("=" * 60)

    manager = SessionManager()

    # Create sessions
    print("\n1. Creating sessions...")
    session1 = manager.create_session(
        task_description="Build a web application",
        task_type="coding",
        workspace="/workspace/project1"
    )
    print(f"   Session 1: {session1.session_id[:16]}")
    print(f"   Thread ID: {session1.thread_id[:16]}")

    session2 = manager.create_session(
        task_description="Research machine learning papers",
        task_type="research",
        workspace="/workspace/research",
        metadata={"topic": "transformers"}
    )
    print(f"   Session 2: {session2.session_id[:16]}")
    print("   ✅ Session creation works")

    # Get session
    print("\n2. Getting session...")
    retrieved = manager.get_session(session1.session_id)
    assert retrieved is not None
    assert retrieved.session_id == session1.session_id
    print("   ✅ Session retrieval works")

    # Record checkpoints
    print("\n3. Recording checkpoints...")
    manager.record_checkpoint(session1.session_id)
    manager.record_checkpoint(session1.session_id)
    retrieved = manager.get_session(session1.session_id)
    assert retrieved.checkpoint_count == 2
    print(f"   Checkpoints: {retrieved.checkpoint_count}")
    print("   ✅ Checkpoint recording works")

    # Complete session
    print("\n4. Completing session...")
    manager.complete_session(session1.session_id)
    retrieved = manager.get_session(session1.session_id)
    assert retrieved.status == "completed"
    assert session1.session_id not in manager.active_sessions
    print("   ✅ Session completion works")

    # List sessions
    print("\n5. Listing sessions...")
    active = manager.list_active_sessions()
    all_sessions = manager.list_all_sessions()
    print(f"   Active: {len(active)}")
    print(f"   Total: {len(all_sessions)}")
    assert len(active) == 1  # Only session2
    assert len(all_sessions) == 2
    print("   ✅ Session listing works")

    # Statistics
    print("\n6. Getting statistics...")
    stats = manager.get_stats()
    print(f"   Total: {stats['total_sessions']}")
    print(f"   Active: {stats['active_sessions']}")
    print(f"   Completed: {stats['completed_sessions']}")
    print("   ✅ Statistics works")

    print()


async def test_checkpointer():
    """Test CheckpointerManager"""
    print("=" * 60)
    print("Testing CheckpointerManager")
    print("=" * 60)

    # Create temp directory for test
    test_db = "/tmp/test_checkpoints.db"

    print("\n1. Creating SQLite checkpointer...")
    manager = CheckpointerManager(db_path=test_db, db_type="sqlite")
    checkpointer = await manager.get_checkpointer()
    assert checkpointer is not None
    print("   ✅ SQLite checkpointer created")

    # Get stats
    print("\n2. Getting checkpointer stats...")
    stats = manager.get_stats()
    print(f"   Type: {stats['db_type']}")
    print(f"   Path: {stats['db_path']}")
    print(f"   Initialized: {stats['initialized']}")
    print("   ✅ Stats works")

    # Close
    print("\n3. Closing checkpointer...")
    await manager.close()
    print("   ✅ Close works")

    # Convenience function
    print("\n4. Testing convenience function...")
    checkpointer2 = await create_sqlite_checkpointer("/tmp/test_checkpoints2.db")
    assert checkpointer2 is not None
    print("   ✅ Convenience function works")

    print()


async def test_state_recovery():
    """Test StateRecovery"""
    print("=" * 60)
    print("Testing StateRecovery")
    print("=" * 60)

    # Create checkpointer
    test_db = "/tmp/test_recovery.db"
    checkpointer = await create_sqlite_checkpointer(test_db)

    print("\n1. Creating StateRecovery...")
    recovery = StateRecovery(checkpointer)
    print("   ✅ StateRecovery created")

    # Test with non-existent thread
    print("\n2. Testing with non-existent thread...")
    state = await recovery.load_state("nonexistent_thread")
    assert state is None
    print("   ✅ Returns None for non-existent thread")

    # Check checkpoint existence
    print("\n3. Checking checkpoint existence...")
    exists = await recovery.has_checkpoint("nonexistent_thread")
    assert not exists
    print("   ✅ Checkpoint existence check works")

    # Test state validation
    print("\n4. Testing state validation...")
    valid_state = create_initial_state(
        task_id="task_1",
        task_description="Test task",
        workflow_domain=WorkflowDomain.CODING,
        workspace="/workspace"
    )
    is_valid = recovery.validate_state(valid_state)
    assert is_valid
    print("   ✅ State validation works")

    # Get stats
    print("\n5. Getting recovery stats...")
    stats = recovery.get_stats()
    print(f"   Recovery count: {stats['recovery_count']}")
    print(f"   Checkpointer type: {stats['checkpointer_type']}")
    print("   ✅ Stats works")

    print()


async def test_integration():
    """Test integration with workflow"""
    print("=" * 60)
    print("Testing Persistence Integration")
    print("=" * 60)

    print("\n1. Setting up persistence...")

    # Create session manager
    session_mgr = SessionManager()

    # Create checkpointer
    checkpointer_mgr = CheckpointerManager(db_path="/tmp/test_integration.db")
    checkpointer = await checkpointer_mgr.get_checkpointer()

    # Create recovery
    recovery = StateRecovery(checkpointer)

    print("   ✅ Persistence components initialized")

    print("\n2. Creating session...")
    session = session_mgr.create_session(
        task_description="Test workflow with checkpointing",
        task_type="coding",
        workspace="/workspace/test"
    )
    print(f"   Session: {session.session_id[:16]}")
    print(f"   Thread: {session.thread_id[:16]}")
    print("   ✅ Session created")

    print("\n3. Simulating workflow execution...")
    # In real usage, you would:
    # 1. Create workflow with checkpointer
    #    workflow = graph.compile(checkpointer=checkpointer)
    # 2. Execute with thread_id in config
    #    config = {"configurable": {"thread_id": session.thread_id}}
    #    result = await workflow.ainvoke(state, config=config)
    # 3. Record checkpoint
    #    session_mgr.record_checkpoint(session.session_id)

    session_mgr.record_checkpoint(session.session_id)
    print("   ✅ Checkpoint recorded")

    print("\n4. Completing session...")
    session_mgr.complete_session(session.session_id)
    print("   ✅ Session completed")

    print("\n5. Getting final statistics...")
    session_stats = session_mgr.get_stats()
    recovery_stats = recovery.get_stats()

    print(f"   Sessions: {session_stats}")
    print(f"   Recovery: {recovery_stats}")
    print("   ✅ Integration test complete")

    print()


async def main():
    """Run all tests"""
    print()
    print("=" * 60)
    print("Persistence System Tests")
    print("=" * 60)
    print()

    try:
        # Run tests
        test_session_manager()
        await test_checkpointer()
        await test_state_recovery()
        await test_integration()

        print("=" * 60)
        print("✅ All persistence tests passed!")
        print("=" * 60)
        print()

        print("Usage Example:")
        print("-" * 60)
        print("""
from persistence import CheckpointerManager, SessionManager, StateRecovery

# 1. Initialize persistence
session_mgr = SessionManager()
checkpointer_mgr = CheckpointerManager(db_path="./data/checkpoints.db")
checkpointer = await checkpointer_mgr.get_checkpointer()

# 2. Create session
session = session_mgr.create_session(
    task_description="Build web app",
    task_type="coding",
    workspace="/workspace"
)

# 3. Create workflow with checkpointer
workflow = graph.compile(checkpointer=checkpointer)

# 4. Execute with thread_id
config = {"configurable": {"thread_id": session.thread_id}}
result = await workflow.ainvoke(initial_state, config=config)

# 5. Record checkpoint
session_mgr.record_checkpoint(session.session_id)

# 6. Resume from checkpoint
recovery = StateRecovery(checkpointer)
state = await recovery.load_state(session.thread_id)
result = await workflow.ainvoke(state, config=config)

# 7. Complete session
session_mgr.complete_session(session.session_id)
        """)
        print("-" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
