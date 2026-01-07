"""Code Generation Handler - 코드 생성 워크플로우 처리.

이 핸들러는 전체 코드 생성 워크플로우를 실행합니다:
Architect → Coder → Review → (Refine) → Artifacts
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator

from app.core.config import settings
from app.agent.handlers.base import BaseHandler, HandlerResult, StreamUpdate
from app.agent import get_workflow_manager

logger = logging.getLogger(__name__)


class CodeGenerationHandler(BaseHandler):
    """코드 생성 워크플로우 핸들러

    전체 코드 생성 파이프라인을 실행하고 결과를 수집합니다.
    """

    def __init__(self):
        """CodeGenerationHandler 초기화"""
        super().__init__()
        self.workflow_manager = get_workflow_manager()
        self.logger.info("CodeGenerationHandler initialized")

    async def execute(
        self,
        user_message: str,
        analysis: Dict[str, Any],
        context: Any
    ) -> HandlerResult:
        """코드 생성 실행 (비스트리밍)

        Args:
            user_message: 사용자 요청
            analysis: Supervisor 분석 결과
            context: 대화 컨텍스트

        Returns:
            HandlerResult: 처리 결과 (생성된 코드 + 아티팩트)
        """
        try:
            # 워크스페이스 확인
            workspace = None
            if context and hasattr(context, 'workspace'):
                workspace = context.workspace

            # 워크플로우 컨텍스트 구성
            workflow_context = {
                "workspace": workspace,
                "analysis": analysis,
                "session_id": context.session_id if context else "default"
            }

            # 워크플로우 가져오기
            workflow = await self._get_workflow(context)

            # 스트리밍 결과 수집
            artifacts = []
            updates = []
            agents_used = set()

            # 대화 컨텍스트를 포함한 enriched user message 생성
            enriched_message = self._build_enriched_message(user_message, context)

            self.logger.info(f"Starting code generation: {user_message[:50]}...")

            async for update in workflow.execute_stream(enriched_message, workflow_context):
                updates.append(update)

                # 에이전트 추적
                if update.get("agent"):
                    agents_used.add(update["agent"])

                # 아티팩트 수집
                if update.get("artifacts"):
                    artifacts.extend(update["artifacts"])
                elif update.get("type") == "artifact" and update.get("content"):
                    # 단일 아티팩트 형식
                    artifacts.append({
                        "filename": update.get("filename", "code.py"),
                        "language": update.get("language", "python"),
                        "content": update.get("content"),
                        "saved_path": update.get("saved_path")
                    })

            # 사용자 응답 생성
            user_response = self._format_code_response(artifacts, updates)

            # 메타데이터
            metadata = {
                "agents_used": list(agents_used),
                "update_count": len(updates),
                "artifact_count": len(artifacts),
                "timestamp": datetime.now().isoformat()
            }

            self.logger.info(f"Code generation completed: {len(artifacts)} artifacts")

            return HandlerResult(
                content=user_response,
                artifacts=artifacts,
                metadata=metadata,
                success=True
            )

        except Exception as e:
            self.logger.error(f"Code generation error: {e}")
            return HandlerResult(
                content="",
                success=False,
                error=str(e)
            )

    async def execute_stream(
        self,
        user_message: str,
        analysis: Dict[str, Any],
        context: Any
    ) -> AsyncGenerator[StreamUpdate, None]:
        """코드 생성 스트리밍

        Args:
            user_message: 사용자 요청
            analysis: Supervisor 분석 결과
            context: 대화 컨텍스트

        Yields:
            StreamUpdate: 스트리밍 업데이트
        """
        yield StreamUpdate(
            agent="CodeGenerationHandler",
            update_type="progress",
            status="running",
            message="코드 생성 워크플로우를 시작합니다..."
        )

        try:
            workspace = None
            if context and hasattr(context, 'workspace'):
                workspace = context.workspace

            workflow_context = {
                "workspace": workspace,
                "analysis": analysis,
                "session_id": context.session_id if context else "default"
            }

            workflow = await self._get_workflow(context)
            artifacts = []

            # 대화 컨텍스트를 포함한 enriched user message 생성
            enriched_message = self._build_enriched_message(user_message, context)

            async for update in workflow.execute_stream(enriched_message, workflow_context):
                # 워크플로우 업데이트를 StreamUpdate로 변환
                agent = update.get("agent", "Workflow")
                update_type = update.get("type", "progress")
                status = update.get("status", "running")
                message = update.get("message", "")

                # streaming_content 추출 (워크플로우에서 전달된 실시간 출력)
                streaming_content = (
                    update.get("streaming_content") or
                    update.get("content") or
                    update.get("partial_output") or
                    ""
                )

                # 아티팩트 수집 - 복수형 artifacts 배열
                if update.get("artifacts"):
                    artifacts.extend(update["artifacts"])
                # 단수형 artifact 객체 (workflow_manager에서 개별 파일 생성 시)
                elif update_type == "artifact":
                    artifact_data = update.get("artifact", {})
                    if artifact_data and artifact_data.get("filename"):
                        artifact_obj = {
                            "filename": artifact_data.get("filename", "code.py"),
                            "language": artifact_data.get("language", "python"),
                            "content": artifact_data.get("content", ""),
                            "saved_path": artifact_data.get("saved_path"),
                            "action": "created"
                        }
                        artifacts.append(artifact_obj)
                        self.logger.info(f"Captured artifact: {artifact_obj['filename']}")

                yield StreamUpdate(
                    agent=agent,
                    update_type=update_type,
                    status=status,
                    message=message,
                    streaming_content=streaming_content if streaming_content else None,
                    data=update
                )

            # 완료 업데이트
            user_response = self._format_code_response(artifacts, [])

            yield StreamUpdate(
                agent="CodeGenerationHandler",
                update_type="completed",
                status="completed",
                message="코드 생성이 완료되었습니다.",
                data={
                    "artifacts": artifacts,
                    "full_content": user_response
                }
            )

        except Exception as e:
            self.logger.error(f"Code generation stream error: {e}")
            yield StreamUpdate(
                agent="CodeGenerationHandler",
                update_type="error",
                status="error",
                message=str(e)
            )

    async def _get_workflow(self, context: Any):
        """워크플로우 인스턴스 가져오기

        Args:
            context: 대화 컨텍스트

        Returns:
            워크플로우 인스턴스
        """
        session_id = context.session_id if context and hasattr(context, 'session_id') else "default"
        workspace = context.workspace if context and hasattr(context, 'workspace') else None

        return await self.workflow_manager.get_workflow(
            session_id=session_id,
            workspace=workspace
        )

    def _format_code_response(
        self,
        artifacts: List[Dict[str, Any]],
        updates: List[Dict[str, Any]]
    ) -> str:
        """코드 생성 결과를 사용자 친화적 응답으로 변환

        Args:
            artifacts: 생성된 아티팩트 목록
            updates: 워크플로우 업데이트 목록

        Returns:
            str: 포맷된 응답
        """
        if not artifacts:
            # 아티팩트가 없는 경우
            error_msg = self._extract_error_from_updates(updates)
            if error_msg:
                return f"코드 생성 중 문제가 발생했습니다:\n\n{error_msg}\n\n요청을 더 구체적으로 설명해주세요."
            return "코드 생성을 완료하지 못했습니다. 요청을 더 구체적으로 설명해주세요."

        # 파일 목록 생성
        files_summary = "\n".join([
            f"- `{a.get('filename', 'unknown')}` ({a.get('language', 'unknown')})"
            for a in artifacts
        ])

        # 코드 내용 포맷
        code_blocks = []
        for artifact in artifacts[:3]:  # 처음 3개 파일만 표시
            filename = artifact.get('filename', 'code')
            language = artifact.get('language', 'text')
            content = artifact.get('content') or ''  # None 처리

            # 너무 긴 코드는 잘라서 표시
            if content and len(content) > 2000:
                content = content[:2000] + "\n\n... (truncated)"

            code_blocks.append(f"### {filename}\n\n```{language}\n{content}\n```")

        if len(artifacts) > 3:
            code_blocks.append(f"\n*... 그 외 {len(artifacts) - 3}개 파일*")

        code_content = "\n\n".join(code_blocks)

        return f"""## 코드 생성 완료

다음 파일들이 생성되었습니다:
{files_summary}

{code_content}

---
추가 수정이나 테스트가 필요하면 말씀해주세요."""

    def _extract_error_from_updates(self, updates: List[Dict[str, Any]]) -> Optional[str]:
        """업데이트에서 에러 메시지 추출

        Args:
            updates: 워크플로우 업데이트 목록

        Returns:
            Optional[str]: 에러 메시지 또는 None
        """
        for update in reversed(updates):
            if update.get("status") == "error" or update.get("type") == "error":
                return update.get("message") or update.get("error")
        return None

    def _build_enriched_message(self, user_message: str, context: Any) -> str:
        """대화 컨텍스트를 포함한 확장 메시지 생성

        사용자의 현재 메시지만으로는 무엇을 구현해야 할지 알 수 없을 때,
        이전 대화 컨텍스트를 포함하여 전체 맥락을 전달합니다.

        Args:
            user_message: 현재 사용자 메시지
            context: 대화 컨텍스트

        Returns:
            str: 컨텍스트가 포함된 확장 메시지
        """
        if not context or not hasattr(context, 'messages'):
            return user_message

        # 이전 대화 내용 추출
        messages = context.messages if hasattr(context, 'messages') else []
        if not messages:
            return user_message

        # 이전 plan 또는 구현 계획 추출
        previous_plan = None
        for msg in reversed(messages):
            content = msg.get("content", "")
            # 이전 응답에서 계획/plan 관련 내용 찾기
            if msg.get("role") == "assistant":
                # Plan 파일 경로가 언급된 경우
                if "plan" in content.lower() and ("##" in content or "1." in content):
                    # 계획 내용이 포함된 응답 발견
                    previous_plan = content
                    break

        # 최근 대화 히스토리 구성 (최대 10개 메시지)
        recent_messages = messages[-10:] if len(messages) > 10 else messages

        # 대화 요약 생성
        conversation_history = []
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 긴 메시지는 요약
            if len(content) > 500:
                content = content[:500] + "..."
            conversation_history.append(f"[{role}]: {content}")

        history_text = "\n".join(conversation_history)

        # 확장 메시지 구성
        enriched_parts = [f"## Previous Conversation Context\n{history_text}"]

        # 이전 plan이 있으면 명시적으로 포함
        if previous_plan:
            self.logger.info("Found previous plan in conversation history, including it")
            enriched_parts.append(f"\n## Previous Implementation Plan\n{previous_plan[:2000]}")

        enriched_parts.append(f"\n## Current User Request\n{user_message}")
        enriched_parts.append("""
## Instructions
IMPORTANT: If a previous implementation plan exists above, USE IT DIRECTLY.
Do NOT create a new plan - implement the code based on the existing plan.
Focus on the specific requirements from the previous conversation and plan.""")

        enriched = "\n".join(enriched_parts)
        self.logger.info(f"Built enriched message with {len(recent_messages)} context messages, plan included: {previous_plan is not None}")
        return enriched
