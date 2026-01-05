"""Unit tests for Quality Gate Workflow

Tests the LangGraph orchestration system including:
- State management
- Node execution
- Security scanning
- Path validation
- Context persistence
"""

import pytest
import tempfile
import json
from pathlib import Path
from app.agent.langgraph.schemas.state import create_initial_state, QualityGateState
from app.agent.langgraph.nodes.supervisor import supervisor_node
from app.agent.langgraph.nodes.security_gate import SecurityScanner
from app.agent.langgraph.nodes.aggregator import quality_aggregator_node
from app.agent.langgraph.tools.file_validator import FileValidator
from app.agent.langgraph.tools.context_manager import ContextManager


class TestStateManagement:
    """Test QualityGateState creation and management"""

    def test_create_initial_state(self):
        """Test initial state creation"""
        state = create_initial_state(
            user_request="Implement user authentication",
            workspace_root="/tmp/test",
            task_type="implementation"
        )

        assert state["user_request"] == "Implement user authentication"
        assert state["workspace_root"] == "/tmp/test"
        assert state["task_type"] == "implementation"
        assert state["iteration"] == 0
        assert state["workflow_status"] == "running"
        assert state["security_findings"] == []
        assert state["error_log"] == []

    def test_state_has_required_fields(self):
        """Test that state contains all required fields"""
        state = create_initial_state("test", "/tmp")

        required_fields = [
            "user_request",
            "workspace_root",
            "task_type",
            "current_node",
            "iteration",
            "max_iterations",
            "workflow_status",
            "started_at"
        ]

        for field in required_fields:
            assert field in state, f"Missing required field: {field}"


class TestSupervisorNode:
    """Test supervisor node task analysis"""

    def test_detects_implementation_task(self):
        """Test detection of implementation tasks"""
        state = create_initial_state(
            "Implement user login feature",
            "/tmp"
        )

        updates = supervisor_node(state)

        assert updates["task_type"] == "implementation"
        # Simple task -> linear -> sequential execution
        assert updates["execution_mode"] == "sequential"
        assert updates["max_iterations"] == 3

    def test_detects_review_task(self):
        """Test detection of review tasks"""
        state = create_initial_state(
            "Review the authentication code",
            "/tmp"
        )

        updates = supervisor_node(state)

        assert updates["task_type"] == "review"
        # Contains "auth" keyword -> CRITICAL -> parallel execution
        assert updates["execution_mode"] == "parallel"

    def test_detects_testing_task(self):
        """Test detection of testing tasks"""
        state = create_initial_state(
            "Add unit tests for the API",
            "/tmp"
        )

        updates = supervisor_node(state)

        assert updates["task_type"] == "testing"

    def test_detects_security_task(self):
        """Test detection of security audit tasks"""
        state = create_initial_state(
            "Run security scan for vulnerabilities",
            "/tmp"
        )

        updates = supervisor_node(state)

        assert updates["task_type"] == "security_audit"


class TestSecurityScanner:
    """Test security vulnerability scanner"""

    def test_detects_sql_injection(self):
        """Test SQL injection detection"""
        code = '''
def get_user(username):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
'''
        findings = SecurityScanner.scan_code(code, "test.py")

        sql_findings = [f for f in findings if f["category"] == "sql_injection"]
        assert len(sql_findings) > 0
        assert sql_findings[0]["severity"] == "critical"

    def test_detects_command_injection(self):
        """Test command injection detection"""
        code = '''
import subprocess
subprocess.call(user_input, shell=True)
'''
        findings = SecurityScanner.scan_code(code, "test.py")

        cmd_findings = [f for f in findings if f["category"] == "command_injection"]
        assert len(cmd_findings) > 0
        assert cmd_findings[0]["severity"] == "critical"

    def test_detects_path_traversal(self):
        """Test path traversal detection"""
        code = '''
file_path = "../../../etc/passwd"
with open(file_path, 'r') as f:
    data = f.read()
'''
        findings = SecurityScanner.scan_code(code, "test.py")

        path_findings = [f for f in findings if f["category"] == "path_traversal"]
        assert len(path_findings) > 0

    def test_detects_hardcoded_secrets(self):
        """Test hardcoded secret detection"""
        code = '''
api_key = "sk-1234567890abcdef"
password = "supersecret123"
'''
        findings = SecurityScanner.scan_code(code, "test.py")

        secret_findings = [f for f in findings if f["category"] == "hardcoded_secrets"]
        assert len(secret_findings) >= 2

    def test_safe_code_has_no_findings(self):
        """Test that safe code produces no findings"""
        code = '''
def get_user(user_id: int):
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
'''
        findings = SecurityScanner.scan_code(code, "test.py")

        assert len(findings) == 0


class TestFileValidator:
    """Test file path validation and sandboxing"""

    def test_validates_safe_relative_path(self):
        """Test validation of safe relative paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = FileValidator(tmpdir)

            is_valid, error, resolved = validator.validate_path("src/main.py")

            assert is_valid is True
            assert error == ""
            assert str(resolved).startswith(tmpdir)

    def test_rejects_path_traversal(self):
        """Test rejection of path traversal attempts"""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = FileValidator(tmpdir)

            is_valid, error, _ = validator.validate_path("../../../etc/passwd")

            assert is_valid is False
            assert "escape" in error.lower() or "dangerous" in error.lower()

    def test_rejects_forbidden_system_paths(self):
        """Test rejection of forbidden system paths"""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = FileValidator(tmpdir)

            is_valid, error, _ = validator.validate_path("/etc/passwd")

            assert is_valid is False
            assert "forbidden" in error.lower() or "escape" in error.lower()

    def test_validates_absolute_path_within_workspace(self):
        """Test validation of absolute paths within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            validator = FileValidator(tmpdir)
            safe_path = Path(tmpdir) / "subdir" / "file.txt"

            is_valid, error, resolved = validator.validate_path(str(safe_path))

            assert is_valid is True
            assert resolved == safe_path


class TestContextManager:
    """Test context persistence manager"""

    def test_creates_new_context(self):
        """Test creating new context file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context_mgr = ContextManager(tmpdir)

            context = {
                "project_name": "TestProject",
                "version": "1.0.0"
            }

            success = context_mgr.save_context(context, merge=False)

            assert success is True
            assert (Path(tmpdir) / ".ai_context.json").exists()

    def test_loads_existing_context(self):
        """Test loading existing context"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context_mgr = ContextManager(tmpdir)

            # Save context
            original = {"project_name": "TestProject", "version": "1.0.0"}
            context_mgr.save_context(original, merge=False)

            # Load context
            loaded = context_mgr.load_context()

            assert loaded is not None
            assert loaded["project_name"] == "TestProject"
            assert loaded["version"] == "1.0.0"
            assert "last_updated" in loaded

    def test_merges_context(self):
        """Test context merging"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context_mgr = ContextManager(tmpdir)

            # Save initial context
            context_mgr.save_context({"key1": "value1"}, merge=False)

            # Merge new data
            context_mgr.save_context({"key2": "value2"}, merge=True)

            # Load and verify
            loaded = context_mgr.load_context()

            assert loaded["key1"] == "value1"
            assert loaded["key2"] == "value2"

    def test_adds_workflow_execution(self):
        """Test adding workflow execution records"""
        with tempfile.TemporaryDirectory() as tmpdir:
            context_mgr = ContextManager(tmpdir)

            success = context_mgr.add_workflow_execution(
                workflow_type="implementation",
                status="completed",
                duration_ms=1500.0,
                artifacts=["main.py", "test.py"],
                notes="Implemented user login"
            )

            assert success is True

            loaded = context_mgr.load_context()
            assert "workflow_history" in loaded
            assert len(loaded["workflow_history"]) == 1
            assert loaded["workflow_history"][0]["workflow_type"] == "implementation"


class TestQualityAggregator:
    """Test quality aggregator node"""

    def test_passes_when_all_gates_pass(self):
        """Test that aggregator passes when all gates pass"""
        state = create_initial_state("test", "/tmp")
        state["security_passed"] = True
        state["tests_passed"] = True
        state["review_approved"] = True

        updates = quality_aggregator_node(state)

        assert updates["workflow_status"] == "completed"

    def test_triggers_self_healing_on_failure(self):
        """Test that aggregator triggers self-healing on failure"""
        state = create_initial_state("test", "/tmp")
        state["security_passed"] = False
        state["tests_passed"] = True
        state["review_approved"] = True
        state["iteration"] = 0
        state["max_iterations"] = 3

        updates = quality_aggregator_node(state)

        assert updates["workflow_status"] == "self_healing"

    def test_fails_on_max_iterations(self):
        """Test that aggregator fails after max iterations"""
        state = create_initial_state("test", "/tmp")
        state["security_passed"] = False
        state["iteration"] = 3
        state["max_iterations"] = 3

        updates = quality_aggregator_node(state)

        assert updates["workflow_status"] == "failed"


class TestCoderNode:
    """Test coder node functionality"""

    def test_coder_returns_token_usage(self):
        """Test that coder node returns token_usage in result"""
        from app.agent.langgraph.nodes.coder import coder_node
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            state = create_initial_state(
                user_request="Create a simple calculator",
                workspace_root=tmpdir,
                task_type="implementation"
            )
            state["enable_debug"] = True

            result = coder_node(state)

            # Check that result has token_usage key
            assert "token_usage" in result, "coder_node should return token_usage"

            # Check token_usage structure
            token_usage = result["token_usage"]
            assert "prompt_tokens" in token_usage
            assert "completion_tokens" in token_usage
            assert "total_tokens" in token_usage

            # Values should be integers >= 0
            assert isinstance(token_usage["prompt_tokens"], int)
            assert isinstance(token_usage["completion_tokens"], int)
            assert isinstance(token_usage["total_tokens"], int)
            assert token_usage["prompt_tokens"] >= 0
            assert token_usage["completion_tokens"] >= 0
            assert token_usage["total_tokens"] >= 0

    def test_coder_output_includes_token_usage(self):
        """Test that coder_output also contains token_usage"""
        from app.agent.langgraph.nodes.coder import coder_node
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            state = create_initial_state(
                user_request="Create a basic web app",
                workspace_root=tmpdir,
                task_type="implementation"
            )
            state["enable_debug"] = True

            result = coder_node(state)

            # Check coder_output structure
            assert "coder_output" in result
            coder_output = result["coder_output"]
            assert "token_usage" in coder_output, "coder_output should include token_usage"

    def test_fallback_generator_returns_tuple(self):
        """Test that fallback code generator works correctly"""
        from app.agent.langgraph.nodes.coder import _fallback_code_generator

        files = _fallback_code_generator("Create a calculator", "implementation")

        assert isinstance(files, list)
        assert len(files) > 0
        assert "filename" in files[0]
        assert "content" in files[0]

    def test_generate_code_with_vllm_returns_tuple(self):
        """Test _generate_code_with_vllm returns (files, token_usage) tuple"""
        from app.agent.langgraph.nodes.coder import _generate_code_with_vllm
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Will use fallback since vLLM endpoint is not configured
            result = _generate_code_with_vllm(
                user_request="Create a test app",
                task_type="implementation",
                workspace_root=tmpdir
            )

            # Should return a tuple
            assert isinstance(result, tuple), "_generate_code_with_vllm should return a tuple"
            assert len(result) == 2, "Tuple should have 2 elements (files, token_usage)"

            files, token_usage = result
            assert isinstance(files, list)
            assert isinstance(token_usage, dict)
            assert "prompt_tokens" in token_usage
            assert "completion_tokens" in token_usage
            assert "total_tokens" in token_usage

    def test_coder_artifact_has_action_field(self):
        """Test that artifacts include action field (created/modified)"""
        from app.agent.langgraph.nodes.coder import coder_node
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            state = create_initial_state(
                user_request="Create a simple hello world app",
                workspace_root=tmpdir,
                task_type="implementation"
            )
            state["enable_debug"] = True

            result = coder_node(state)

            # Check that artifacts have action field
            artifacts = result.get("artifacts", [])
            if artifacts:
                for artifact in artifacts:
                    assert "action" in artifact, "Artifact should have action field"
                    assert artifact["action"] in ["created", "modified"], \
                        f"Action should be 'created' or 'modified', got {artifact['action']}"
                    assert "relative_path" in artifact, "Artifact should have relative_path"
                    assert "project_root" in artifact, "Artifact should have project_root"

    def test_coder_detects_modified_files(self):
        """Test that coder correctly identifies modified vs created files"""
        from app.agent.langgraph.nodes.coder import coder_node
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an existing file first
            existing_file = os.path.join(tmpdir, "main.py")
            with open(existing_file, "w") as f:
                f.write("# Old content")

            state = create_initial_state(
                user_request="Update the main.py file",
                workspace_root=tmpdir,
                task_type="implementation"
            )
            state["enable_debug"] = True

            result = coder_node(state)

            # Find main.py artifact if it exists
            artifacts = result.get("artifacts", [])
            main_artifact = next((a for a in artifacts if "main.py" in a.get("filename", "")), None)

            if main_artifact:
                # Since main.py existed, it should be marked as modified
                assert main_artifact.get("action") == "modified", \
                    "Existing file should be marked as 'modified'"
