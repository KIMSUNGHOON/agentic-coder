"""Base Handler - 응답 타입별 핸들러의 베이스 클래스.

모든 핸들러는 이 클래스를 상속받아 구현합니다.
"""
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


@dataclass
class HandlerResult:
    """핸들러 실행 결과

    Attributes:
        content: 사용자에게 표시할 응답 텍스트
        artifacts: 생성된 아티팩트 (파일) 목록
        plan_file: 저장된 계획 파일 경로 (있는 경우)
        metadata: 추가 메타데이터 (토큰 사용량, 레이턴시 등)
        success: 성공 여부
        error: 에러 메시지 (실패 시)
    """
    content: str
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    plan_file: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


@dataclass
class StreamUpdate:
    """스트리밍 업데이트

    Attributes:
        agent: 업데이트를 생성한 에이전트 이름
        update_type: 업데이트 유형 (thinking, artifact, progress, completed, error)
        status: 상태 (running, completed, error)
        message: 상태 메시지
        data: 추가 데이터
        timestamp: 타임스탬프
    """
    agent: str
    update_type: str
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = {
            "agent": self.agent,
            "type": self.update_type,
            "status": self.status,
            "message": self.message
        }
        if self.data:
            result["data"] = self.data
        if self.timestamp:
            result["timestamp"] = self.timestamp
        return result


class BaseHandler(ABC):
    """응답 타입별 핸들러 베이스 클래스

    모든 핸들러는 이 클래스를 상속받아 execute 메서드를 구현해야 합니다.
    """

    def __init__(self):
        """핸들러 초기화"""
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def execute(
        self,
        user_message: str,
        analysis: Dict[str, Any],
        context: Any  # ConversationContext
    ) -> HandlerResult:
        """핸들러 실행 (비스트리밍)

        Args:
            user_message: 사용자 메시지
            analysis: Supervisor 분석 결과
            context: 대화 컨텍스트

        Returns:
            HandlerResult: 핸들러 실행 결과
        """
        pass

    async def execute_stream(
        self,
        user_message: str,
        analysis: Dict[str, Any],
        context: Any  # ConversationContext
    ) -> AsyncGenerator[StreamUpdate, None]:
        """핸들러 실행 (스트리밍)

        기본 구현은 execute()를 호출하고 완료 업데이트를 반환합니다.
        스트리밍이 필요한 핸들러는 이 메서드를 오버라이드해야 합니다.

        Args:
            user_message: 사용자 메시지
            analysis: Supervisor 분석 결과
            context: 대화 컨텍스트

        Yields:
            StreamUpdate: 스트리밍 업데이트
        """
        # 시작 업데이트
        yield StreamUpdate(
            agent=self.__class__.__name__,
            update_type="progress",
            status="running",
            message="처리 중..."
        )

        # 실행
        result = await self.execute(user_message, analysis, context)

        # 완료 업데이트
        yield StreamUpdate(
            agent=self.__class__.__name__,
            update_type="completed",
            status="completed" if result.success else "error",
            message=result.content[:200] if result.success else result.error,
            data={
                "artifacts": result.artifacts,
                "plan_file": result.plan_file
            }
        )

    def _strip_think_tags(self, text: str) -> str:
        """<think> 태그 제거

        Args:
            text: 원본 텍스트

        Returns:
            str: think 태그가 제거된 텍스트
        """
        if not text:
            return ""

        # <think>...</think> 블록 제거
        clean = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 연속된 줄바꿈 정리
        clean = re.sub(r'\n\s*\n\s*\n', '\n\n', clean)
        return clean.strip()

    def _extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """마크다운 코드 블록 추출

        Args:
            text: 원본 텍스트

        Returns:
            List[Dict[str, str]]: 코드 블록 목록 (language, code)
        """
        pattern = r'```(\w*)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)

        blocks = []
        for language, code in matches:
            blocks.append({
                "language": language or "text",
                "code": code.strip()
            })

        return blocks

    def _format_artifacts_for_display(self, artifacts: List[Dict[str, Any]]) -> str:
        """아티팩트 목록을 표시용 문자열로 변환

        Args:
            artifacts: 아티팩트 목록

        Returns:
            str: 포맷된 문자열
        """
        if not artifacts:
            return ""

        lines = ["### 생성된 파일"]
        for artifact in artifacts:
            filename = artifact.get("filename", "unknown")
            language = artifact.get("language", "text")
            lines.append(f"- `{filename}` ({language})")

        return "\n".join(lines)
