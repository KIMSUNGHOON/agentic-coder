"""
Phase 4: Sandbox Execution Tools

AIO Sandbox 기반의 격리된 코드 실행 환경을 제공합니다.

Features:
- Docker 컨테이너 기반 격리 실행
- Python, Node.js, Shell 지원
- 오프라인 환경 지원 (사전 빌드 이미지 사용)
- 리소스 제한 및 타임아웃

AIO Sandbox Docker Image:
- Official: ghcr.io/agent-infra/sandbox:latest
- Custom Registry: {registry}/sandbox/aio:latest
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Callable

import aiohttp

from .base import BaseTool, ToolResult, ToolCategory, NetworkType


logger = logging.getLogger(__name__)


class SandboxLanguage(Enum):
    """지원하는 프로그래밍 언어"""
    PYTHON = "python"
    NODEJS = "nodejs"
    TYPESCRIPT = "typescript"
    SHELL = "shell"


@dataclass
class SandboxConfig:
    """
    AIO Sandbox 설정

    환경변수로 오버라이드 가능:
    - SANDBOX_IMAGE: Docker 이미지
    - SANDBOX_REGISTRY: 사내 레지스트리 (오프라인용)
    - SANDBOX_PORT: API 포트
    - SANDBOX_TIMEOUT: 기본 타임아웃
    """

    # Docker 이미지 설정
    default_image: str = "ghcr.io/agent-infra/sandbox:latest"
    registry: Optional[str] = None  # 사내 레지스트리 (예: harbor.company.com)

    # API 설정
    host: str = "localhost"
    port: int = 8080

    # 실행 설정
    default_timeout: int = 60  # 초
    max_timeout: int = 300  # 최대 5분

    # 컨테이너 설정
    container_name: str = "testcodeagent-sandbox"
    auto_start: bool = True  # 컨테이너 자동 시작
    auto_stop: bool = False  # 세션 종료 시 자동 중지

    # 리소스 제한 (Docker run 옵션)
    memory_limit: str = "1g"
    cpu_limit: float = 2.0

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        """환경변수에서 설정 로드"""
        return cls(
            default_image=os.getenv("SANDBOX_IMAGE", cls.default_image),
            registry=os.getenv("SANDBOX_REGISTRY"),
            host=os.getenv("SANDBOX_HOST", "localhost"),
            port=int(os.getenv("SANDBOX_PORT", "8080")),
            default_timeout=int(os.getenv("SANDBOX_TIMEOUT", "60")),
            memory_limit=os.getenv("SANDBOX_MEMORY", "1g"),
            cpu_limit=float(os.getenv("SANDBOX_CPU", "2.0")),
        )

    def get_image(self) -> str:
        """전체 이미지 경로 반환"""
        if self.registry:
            # ghcr.io/agent-infra/sandbox -> {registry}/sandbox/aio
            return f"{self.registry}/sandbox/aio:latest"
        return self.default_image

    def get_base_url(self) -> str:
        """API 기본 URL"""
        return f"http://{self.host}:{self.port}"


class SandboxManager:
    """
    AIO Sandbox Docker 컨테이너 관리자

    컨테이너 라이프사이클:
    - start(): 컨테이너 시작
    - stop(): 컨테이너 중지
    - is_running(): 실행 상태 확인
    - ensure_running(): 실행 중이 아니면 시작
    """

    _instance: Optional["SandboxManager"] = None

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig.from_env()
        self._container_id: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_instance(cls, config: Optional[SandboxConfig] = None) -> "SandboxManager":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    async def reset_instance(cls):
        """인스턴스 리셋 (테스트용)"""
        if cls._instance is not None:
            await cls._instance.cleanup()
            cls._instance = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 반환"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.default_timeout)
            )
        return self._session

    async def cleanup(self):
        """리소스 정리"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def is_running(self) -> bool:
        """샌드박스가 실행 중인지 확인"""
        try:
            session = await self._get_session()
            url = f"{self.config.get_base_url()}/v1/sandbox"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def wait_for_ready(self, timeout: int = 30) -> bool:
        """샌드박스가 준비될 때까지 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.is_running():
                return True
            await asyncio.sleep(1)
        return False

    async def start(self) -> bool:
        """
        Docker 컨테이너 시작

        Returns:
            bool: 시작 성공 여부
        """
        # 이미 실행 중인지 확인
        if await self.is_running():
            logger.info("✅ Sandbox already running")
            return True

        image = self.config.get_image()
        container_name = self.config.container_name

        try:
            # 기존 컨테이너 제거
            remove_cmd = ["docker", "rm", "-f", container_name]
            proc = await asyncio.create_subprocess_exec(
                *remove_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()

            # 새 컨테이너 시작
            docker_cmd = [
                "docker", "run",
                "-d",  # 백그라운드 실행
                "--name", container_name,
                "--security-opt", "seccomp=unconfined",
                "-p", f"{self.config.port}:8080",
                f"--memory={self.config.memory_limit}",
                f"--cpus={self.config.cpu_limit}",
                image
            ]

            logger.info(f"🚀 Starting sandbox container: {image}")
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode('utf-8').strip()
                logger.error(f"❌ Failed to start sandbox: {error_msg}")
                return False

            self._container_id = stdout.decode('utf-8').strip()[:12]
            logger.info(f"📦 Container started: {self._container_id}")

            # 준비될 때까지 대기
            if await self.wait_for_ready(timeout=30):
                logger.info("✅ Sandbox ready")
                return True
            else:
                logger.error("❌ Sandbox failed to become ready")
                return False

        except FileNotFoundError:
            logger.error("❌ Docker not found. Please install Docker.")
            return False
        except Exception as e:
            logger.error(f"❌ Error starting sandbox: {e}")
            return False

    async def stop(self) -> bool:
        """Docker 컨테이너 중지"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stop", self.config.container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()

            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", self.config.container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()

            logger.info("🛑 Sandbox stopped")
            return True
        except Exception as e:
            logger.error(f"❌ Error stopping sandbox: {e}")
            return False

    async def ensure_running(self) -> bool:
        """실행 중이 아니면 시작"""
        if await self.is_running():
            return True
        return await self.start()

    async def get_info(self) -> Optional[Dict[str, Any]]:
        """샌드박스 정보 조회"""
        try:
            session = await self._get_session()
            url = f"{self.config.get_base_url()}/v1/sandbox"
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f"Error getting sandbox info: {e}")
        return None


class SandboxExecuteTool(BaseTool):
    """
    AIO Sandbox를 사용한 코드 실행 도구

    Features:
    - Python 코드 실행 (Jupyter API)
    - Node.js/TypeScript 실행 (Shell API)
    - Shell 명령어 실행
    - 파일 입출력 지원

    Network Type: LOCAL (Docker 컨테이너는 로컬 실행)

    Example:
        ```python
        tool = SandboxExecuteTool()

        # Python 실행
        result = await tool.execute(
            code="print('Hello, World!')",
            language="python"
        )

        # Node.js 실행
        result = await tool.execute(
            code="console.log('Hello');",
            language="nodejs"
        )

        # Shell 명령어
        result = await tool.execute(
            code="ls -la",
            language="shell"
        )
        ```
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        super().__init__(
            name="sandbox_execute",
            category=ToolCategory.CODE
        )
        self.description = (
            "Execute code in an isolated Docker sandbox environment. "
            "Supports Python, Node.js, TypeScript, and Shell. "
            "Code runs in a secure container with resource limits."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Code to execute"
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "nodejs", "typescript", "shell"],
                    "default": "python",
                    "description": "Programming language"
                },
                "timeout": {
                    "type": "integer",
                    "default": 60,
                    "maximum": 300,
                    "description": "Execution timeout in seconds"
                },
                "working_dir": {
                    "type": "string",
                    "default": "/home/user",
                    "description": "Working directory inside container"
                }
            },
            "required": ["code"]
        }

        # Network type: LOCAL (로컬 Docker 실행)
        self.network_type = NetworkType.LOCAL
        self.requires_network = False

        self.config = config or SandboxConfig.from_env()
        self._manager: Optional[SandboxManager] = None

    async def _get_manager(self) -> SandboxManager:
        """SandboxManager 인스턴스 반환"""
        if self._manager is None:
            self._manager = await SandboxManager.get_instance(self.config)
        return self._manager

    def validate_params(self, **kwargs) -> bool:
        """파라미터 검증"""
        code = kwargs.get("code", "")
        if not code or not isinstance(code, str):
            return False

        language = kwargs.get("language", "python")
        if language not in ["python", "nodejs", "typescript", "shell"]:
            return False

        timeout = kwargs.get("timeout", 60)
        if not isinstance(timeout, int) or timeout < 1 or timeout > 300:
            return False

        return True

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 60,
        working_dir: str = "/home/user",
        **kwargs
    ) -> ToolResult:
        """
        코드 실행

        Args:
            code: 실행할 코드
            language: 언어 (python, nodejs, typescript, shell)
            timeout: 타임아웃 (초)
            working_dir: 작업 디렉토리

        Returns:
            ToolResult with stdout, stderr, exit_code
        """
        start_time = time.time()

        # 파라미터 검증
        if not self.validate_params(code=code, language=language, timeout=timeout):
            return ToolResult(
                success=False,
                output=None,
                error="Invalid parameters"
            )

        try:
            # 샌드박스 시작 확인
            manager = await self._get_manager()

            if not await manager.ensure_running():
                return ToolResult(
                    success=False,
                    output=None,
                    error="Failed to start sandbox container. Is Docker running?"
                )

            # 언어별 실행
            if language == "python":
                result = await self._execute_python(code, timeout)
            elif language in ["nodejs", "typescript"]:
                result = await self._execute_nodejs(code, language, timeout, working_dir)
            elif language == "shell":
                result = await self._execute_shell(code, timeout, working_dir)
            else:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Unsupported language: {language}"
                )

            execution_time = time.time() - start_time
            result["execution_time_seconds"] = round(execution_time, 3)
            result["language"] = language

            success = result.get("exit_code", 1) == 0

            return ToolResult(
                success=success,
                output=result,
                error=result.get("stderr") if not success else None,
                execution_time=execution_time
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                output=None,
                error=f"Execution timeout: exceeded {timeout} seconds"
            )
        except Exception as e:
            logger.error(f"❌ Sandbox execution error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"Sandbox execution failed: {str(e)}"
            )

    async def _execute_python(self, code: str, timeout: int) -> Dict[str, Any]:
        """Python 코드 실행 (Jupyter API 사용)"""
        manager = await self._get_manager()
        session = await manager._get_session()

        url = f"{self.config.get_base_url()}/v1/jupyter/execute"
        payload = {"code": code}

        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "stdout": data.get("output", ""),
                        "stderr": data.get("error", ""),
                        "exit_code": 0 if not data.get("error") else 1,
                        "raw_response": data
                    }
                else:
                    error_text = await resp.text()
                    return {
                        "stdout": "",
                        "stderr": f"API error: {resp.status} - {error_text}",
                        "exit_code": 1
                    }
        except asyncio.TimeoutError:
            return {
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "exit_code": -1
            }

    async def _execute_nodejs(
        self,
        code: str,
        language: str,
        timeout: int,
        working_dir: str
    ) -> Dict[str, Any]:
        """Node.js/TypeScript 실행 (Shell API로 파일 생성 후 실행)"""
        manager = await self._get_manager()
        session = await manager._get_session()

        # 파일 확장자 결정
        ext = "ts" if language == "typescript" else "js"
        filename = f"/tmp/code_{int(time.time())}.{ext}"

        # 코드 파일 작성
        write_url = f"{self.config.get_base_url()}/v1/file/write"
        await session.post(write_url, json={"file": filename, "content": code})

        # 실행 명령어
        if language == "typescript":
            command = f"cd {working_dir} && ts-node {filename}"
        else:
            command = f"cd {working_dir} && node {filename}"

        return await self._execute_shell(command, timeout, working_dir)

    async def _execute_shell(
        self,
        command: str,
        timeout: int,
        working_dir: str
    ) -> Dict[str, Any]:
        """Shell 명령어 실행"""
        manager = await self._get_manager()
        session = await manager._get_session()

        url = f"{self.config.get_base_url()}/v1/shell/exec"
        payload = {
            "command": command,
            "timeout": timeout * 1000  # ms 단위
        }

        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout + 5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # AIO Sandbox API 응답 구조에 맞게 파싱
                    output = data.get("data", {}).get("output", "") if isinstance(data.get("data"), dict) else data.get("output", "")
                    error = data.get("data", {}).get("error", "") if isinstance(data.get("data"), dict) else data.get("error", "")
                    exit_code = data.get("data", {}).get("exitCode", 0) if isinstance(data.get("data"), dict) else data.get("exitCode", 0)

                    return {
                        "stdout": output,
                        "stderr": error,
                        "exit_code": exit_code,
                        "command": command,
                        "raw_response": data
                    }
                else:
                    error_text = await resp.text()
                    return {
                        "stdout": "",
                        "stderr": f"API error: {resp.status} - {error_text}",
                        "exit_code": 1,
                        "command": command
                    }
        except asyncio.TimeoutError:
            return {
                "stdout": "",
                "stderr": f"Timeout after {timeout}s",
                "exit_code": -1,
                "command": command
            }


class SandboxFileManager:
    """
    샌드박스 파일 관리 유틸리티

    샌드박스 내부의 파일을 읽고 쓰는 기능을 제공합니다.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig.from_env()
        self._manager: Optional[SandboxManager] = None

    async def _get_manager(self) -> SandboxManager:
        if self._manager is None:
            self._manager = await SandboxManager.get_instance(self.config)
        return self._manager

    async def read_file(self, path: str) -> Optional[str]:
        """샌드박스 내 파일 읽기"""
        manager = await self._get_manager()
        session = await manager._get_session()

        url = f"{self.config.get_base_url()}/v1/file/read"
        try:
            async with session.post(url, json={"file": path}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("content", data.get("data", {}).get("content"))
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
        return None

    async def write_file(self, path: str, content: str) -> bool:
        """샌드박스 내 파일 쓰기"""
        manager = await self._get_manager()
        session = await manager._get_session()

        url = f"{self.config.get_base_url()}/v1/file/write"
        try:
            async with session.post(url, json={"file": path, "content": content}) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
        return False


# 모듈 레벨 헬퍼 함수

async def get_sandbox_manager(config: Optional[SandboxConfig] = None) -> SandboxManager:
    """SandboxManager 싱글톤 인스턴스 반환"""
    return await SandboxManager.get_instance(config)


async def execute_in_sandbox(
    code: str,
    language: str = "python",
    timeout: int = 60
) -> ToolResult:
    """
    간편한 코드 실행 함수

    Example:
        result = await execute_in_sandbox("print('Hello')", language="python")
        print(result.output["stdout"])
    """
    tool = SandboxExecuteTool()
    return await tool.execute(code=code, language=language, timeout=timeout)
