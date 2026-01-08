"""
Phase 4: Sandbox Tools Tests

AIO Sandbox 기반 코드 실행 도구 테스트
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import aiohttp

from app.tools.sandbox_tools import (
    SandboxConfig,
    SandboxManager,
    SandboxExecuteTool,
    SandboxFileManager,
    SandboxLanguage,
    execute_in_sandbox,
    get_sandbox_manager
)
from app.tools.base import ToolCategory, NetworkType, ToolResult


# ============================================
# SandboxConfig Tests
# ============================================

class TestSandboxConfig:
    """SandboxConfig 테스트"""

    def test_default_values(self):
        """기본값 테스트"""
        config = SandboxConfig()
        assert config.default_image == "ghcr.io/agent-infra/sandbox:latest"
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.default_timeout == 60
        assert config.max_timeout == 300

    def test_get_image_default(self):
        """기본 이미지 경로"""
        config = SandboxConfig()
        assert config.get_image() == "ghcr.io/agent-infra/sandbox:latest"

    def test_get_image_with_registry(self):
        """사내 레지스트리 이미지 경로"""
        config = SandboxConfig(registry="harbor.company.com")
        assert config.get_image() == "harbor.company.com/sandbox/aio:latest"

    def test_get_base_url(self):
        """API URL 생성"""
        config = SandboxConfig(host="192.168.1.100", port=9090)
        assert config.get_base_url() == "http://192.168.1.100:9090"

    def test_from_env(self):
        """환경변수에서 설정 로드"""
        with patch.dict('os.environ', {
            'SANDBOX_IMAGE': 'custom/image:v1',
            'SANDBOX_PORT': '9999',
            'SANDBOX_TIMEOUT': '120'
        }):
            config = SandboxConfig.from_env()
            assert config.default_image == "custom/image:v1"
            assert config.port == 9999
            assert config.default_timeout == 120


# ============================================
# SandboxManager Tests
# ============================================

class TestSandboxManager:
    """SandboxManager 테스트"""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """싱글톤 패턴 테스트"""
        await SandboxManager.reset_instance()

        manager1 = await SandboxManager.get_instance()
        manager2 = await SandboxManager.get_instance()

        assert manager1 is manager2
        await SandboxManager.reset_instance()

    @pytest.mark.asyncio
    async def test_is_running_false_when_not_started(self):
        """시작되지 않은 상태 확인"""
        config = SandboxConfig(port=18080)
        manager = SandboxManager(config)

        try:
            # Mock the session to simulate connection refused
            with patch.object(manager, '_get_session') as mock_session:
                mock_session.return_value.get = AsyncMock(
                    side_effect=aiohttp.ClientConnectorError(
                        connection_key=Mock(),
                        os_error=OSError("Connection refused")
                    )
                )
                result = await manager.is_running()
                assert result is False
        finally:
            await manager.cleanup()

    @pytest.mark.asyncio
    async def test_is_running_true_when_api_responds(self):
        """API 응답 시 실행 중"""
        config = SandboxConfig(port=18080)
        manager = SandboxManager(config)

        try:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            mock_session = AsyncMock()
            mock_session.get = Mock(return_value=mock_response)

            with patch.object(manager, '_get_session', return_value=mock_session):
                result = await manager.is_running()
                assert result is True
        finally:
            await manager.cleanup()

    @pytest.mark.asyncio
    async def test_start_when_already_running(self):
        """이미 실행 중일 때 start"""
        config = SandboxConfig(port=18080)
        manager = SandboxManager(config)

        try:
            with patch.object(manager, 'is_running', return_value=True):
                result = await manager.start()
                assert result is True
        finally:
            await manager.cleanup()

    @pytest.mark.asyncio
    async def test_start_docker_not_found(self):
        """Docker 미설치 시"""
        config = SandboxConfig(port=18080)
        manager = SandboxManager(config)

        try:
            async def mock_is_running():
                return False

            with patch.object(manager, 'is_running', side_effect=mock_is_running):
                with patch('app.tools.sandbox_tools.asyncio.create_subprocess_exec', side_effect=FileNotFoundError()):
                    result = await manager.start()
                    assert result is False
        finally:
            await manager.cleanup()


# ============================================
# SandboxExecuteTool Tests
# ============================================

class TestSandboxExecuteToolInit:
    """SandboxExecuteTool 초기화 테스트"""

    def test_init(self):
        """기본 초기화"""
        tool = SandboxExecuteTool()
        assert tool.name == "sandbox_execute"
        assert tool.category == ToolCategory.CODE
        assert tool.network_type == NetworkType.LOCAL
        assert tool.requires_network is False

    def test_description(self):
        """설명 확인"""
        tool = SandboxExecuteTool()
        assert "Docker" in tool.description
        assert "Python" in tool.description

    def test_parameters_schema(self):
        """파라미터 스키마"""
        tool = SandboxExecuteTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "code" in params["properties"]
        assert "language" in params["properties"]
        assert "timeout" in params["properties"]
        assert "code" in params["required"]


class TestSandboxExecuteToolValidation:
    """SandboxExecuteTool 파라미터 검증 테스트"""

    def test_validate_valid_python(self):
        """유효한 Python 코드"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="print('hello')", language="python") is True

    def test_validate_valid_nodejs(self):
        """유효한 Node.js 코드"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="console.log('hi')", language="nodejs") is True

    def test_validate_valid_shell(self):
        """유효한 Shell 명령어"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="ls -la", language="shell") is True

    def test_validate_empty_code(self):
        """빈 코드"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="", language="python") is False

    def test_validate_invalid_language(self):
        """지원하지 않는 언어"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="code", language="java") is False

    def test_validate_invalid_timeout(self):
        """유효하지 않은 타임아웃"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="code", timeout=0) is False
        assert tool.validate_params(code="code", timeout=500) is False

    def test_validate_valid_timeout(self):
        """유효한 타임아웃"""
        tool = SandboxExecuteTool()
        assert tool.validate_params(code="code", timeout=60) is True
        assert tool.validate_params(code="code", timeout=300) is True


class TestSandboxExecuteToolNetworkType:
    """SandboxExecuteTool 네트워크 타입 테스트"""

    def test_is_local(self):
        """LOCAL 타입"""
        tool = SandboxExecuteTool()
        assert tool.network_type == NetworkType.LOCAL

    def test_available_in_offline_mode(self):
        """오프라인 모드에서 사용 가능"""
        tool = SandboxExecuteTool()
        assert tool.is_available_in_mode("offline") is True

    def test_available_in_online_mode(self):
        """온라인 모드에서 사용 가능"""
        tool = SandboxExecuteTool()
        assert tool.is_available_in_mode("online") is True


class TestSandboxExecuteToolExecution:
    """SandboxExecuteTool 실행 테스트"""

    @pytest.fixture
    def tool(self):
        return SandboxExecuteTool()

    @pytest.mark.asyncio
    async def test_execute_sandbox_not_running(self, tool):
        """샌드박스 미실행 시"""
        mock_manager = AsyncMock()
        mock_manager.ensure_running = AsyncMock(return_value=False)

        with patch.object(tool, '_get_manager', return_value=mock_manager):
            result = await tool.execute(code="print('hello')")

            assert result.success is False
            assert "Failed to start sandbox" in result.error

    @pytest.mark.asyncio
    async def test_execute_python_success(self, tool):
        """Python 실행 성공"""
        mock_manager = AsyncMock()
        mock_manager.ensure_running = AsyncMock(return_value=True)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "output": "Hello, World!\n",
            "error": ""
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response)
        mock_manager._get_session = AsyncMock(return_value=mock_session)

        with patch.object(tool, '_get_manager', return_value=mock_manager):
            result = await tool.execute(
                code="print('Hello, World!')",
                language="python"
            )

            assert result.success is True
            assert result.output["stdout"] == "Hello, World!\n"
            assert result.output["language"] == "python"

    @pytest.mark.asyncio
    async def test_execute_python_error(self, tool):
        """Python 실행 오류"""
        mock_manager = AsyncMock()
        mock_manager.ensure_running = AsyncMock(return_value=True)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "output": "",
            "error": "NameError: name 'undefined_var' is not defined"
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response)
        mock_manager._get_session = AsyncMock(return_value=mock_session)

        with patch.object(tool, '_get_manager', return_value=mock_manager):
            result = await tool.execute(
                code="print(undefined_var)",
                language="python"
            )

            assert result.success is False
            assert "NameError" in result.output["stderr"]

    @pytest.mark.asyncio
    async def test_execute_shell_success(self, tool):
        """Shell 실행 성공"""
        mock_manager = AsyncMock()
        mock_manager.ensure_running = AsyncMock(return_value=True)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "output": "file1.txt\nfile2.txt\n",
                "error": "",
                "exitCode": 0
            }
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response)
        mock_manager._get_session = AsyncMock(return_value=mock_session)

        with patch.object(tool, '_get_manager', return_value=mock_manager):
            result = await tool.execute(
                code="ls",
                language="shell"
            )

            assert result.success is True
            assert "file1.txt" in result.output["stdout"]

    @pytest.mark.asyncio
    async def test_execute_invalid_params(self, tool):
        """잘못된 파라미터"""
        result = await tool.execute(code="", language="python")
        assert result.success is False
        assert "Invalid parameters" in result.error

    @pytest.mark.asyncio
    async def test_execute_unsupported_language(self, tool):
        """지원하지 않는 언어"""
        result = await tool.execute(code="code", language="java")
        assert result.success is False


# ============================================
# SandboxFileManager Tests
# ============================================

class TestSandboxFileManager:
    """SandboxFileManager 테스트"""

    @pytest.mark.asyncio
    async def test_read_file_success(self):
        """파일 읽기 성공"""
        file_manager = SandboxFileManager()

        mock_manager = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"content": "file content"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response)
        mock_manager._get_session = AsyncMock(return_value=mock_session)

        with patch.object(file_manager, '_get_manager', return_value=mock_manager):
            content = await file_manager.read_file("/tmp/test.txt")
            assert content == "file content"

    @pytest.mark.asyncio
    async def test_write_file_success(self):
        """파일 쓰기 성공"""
        file_manager = SandboxFileManager()

        mock_manager = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response)
        mock_manager._get_session = AsyncMock(return_value=mock_session)

        with patch.object(file_manager, '_get_manager', return_value=mock_manager):
            result = await file_manager.write_file("/tmp/test.txt", "content")
            assert result is True


# ============================================
# Registry Integration Tests
# ============================================

class TestSandboxToolRegistry:
    """레지스트리 통합 테스트"""

    def test_tool_registered(self):
        """도구 등록 확인"""
        from app.tools.registry import ToolRegistry
        ToolRegistry._instance = None  # Reset singleton

        registry = ToolRegistry()
        tool = registry.get_tool("sandbox_execute", check_availability=False)

        assert tool is not None
        assert tool.name == "sandbox_execute"
        assert tool.category == ToolCategory.CODE

    def test_tool_available_offline(self):
        """오프라인 모드에서 사용 가능"""
        from app.tools.registry import ToolRegistry
        ToolRegistry._instance = None

        with patch.dict('os.environ', {'NETWORK_MODE': 'offline'}):
            registry = ToolRegistry()
            tool = registry.get_tool("sandbox_execute")

            assert tool is not None  # LOCAL 타입이므로 사용 가능

    def test_tool_schema(self):
        """도구 스키마"""
        tool = SandboxExecuteTool()
        schema = tool.get_schema()

        assert schema["name"] == "sandbox_execute"
        assert schema["category"] == "code"
        assert "parameters" in schema


# ============================================
# Helper Function Tests
# ============================================

class TestHelperFunctions:
    """헬퍼 함수 테스트"""

    @pytest.mark.asyncio
    async def test_get_sandbox_manager(self):
        """get_sandbox_manager 함수"""
        await SandboxManager.reset_instance()
        manager = await get_sandbox_manager()
        assert isinstance(manager, SandboxManager)
        await SandboxManager.reset_instance()

    @pytest.mark.asyncio
    async def test_execute_in_sandbox(self):
        """execute_in_sandbox 함수"""
        with patch.object(SandboxExecuteTool, 'execute') as mock_execute:
            mock_execute.return_value = ToolResult(
                success=True,
                output={"stdout": "Hello\n", "exit_code": 0}
            )

            result = await execute_in_sandbox("print('Hello')")

            assert result.success is True
            mock_execute.assert_called_once()


# ============================================
# Edge Cases
# ============================================

class TestEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """타임아웃 처리"""
        tool = SandboxExecuteTool()

        mock_manager = AsyncMock()
        mock_manager.ensure_running = AsyncMock(return_value=True)
        mock_manager._get_session = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch.object(tool, '_get_manager', return_value=mock_manager):
            result = await tool.execute(
                code="import time; time.sleep(100)",
                language="python",
                timeout=1
            )

            assert result.success is False
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """API 오류 처리"""
        tool = SandboxExecuteTool()

        mock_manager = AsyncMock()
        mock_manager.ensure_running = AsyncMock(return_value=True)

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post = Mock(return_value=mock_response)
        mock_manager._get_session = AsyncMock(return_value=mock_session)

        with patch.object(tool, '_get_manager', return_value=mock_manager):
            result = await tool.execute(code="print('test')", language="python")

            assert result.success is False
            assert "API error" in result.output["stderr"]
