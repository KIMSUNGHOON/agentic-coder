# 원격 CLI 접속 설계

## 📋 요구사항

동일 네트워크 그룹의 다른 클라이언트에서 CLI를 사용하고 싶음

## 🎯 목표

- 로컬 CLI와 동일한 사용자 경험
- 최소한의 설정으로 원격 접속
- 보안 및 세션 격리
- 실시간 스트리밍 지원

## 🏗️ 아키텍처 옵션

### Option 1: HTTP/SSE 기반 원격 CLI (추천 ⭐)

```
┌─────────────┐         HTTP/SSE          ┌─────────────┐
│   Client    │ ──────────────────────► │   Backend   │
│  (Thin CLI) │                          │  (FastAPI)  │
│             │ ◄────────────────────── │             │
└─────────────┘    Streaming Response   └─────────────┘
                                              │
                                              ▼
                                        ┌─────────────┐
                                        │  vLLM x2    │
                                        └─────────────┘
```

**장점:**
- ✅ 기존 FastAPI backend 활용
- ✅ 방화벽 친화적 (HTTP만 필요)
- ✅ 브라우저 기반 웹 터미널 가능
- ✅ SSE로 실시간 스트리밍 지원
- ✅ 인증/권한 관리 용이

**구현:**
1. Backend에 `/api/v1/cli/session` endpoint 추가
2. SSE(Server-Sent Events)로 스트리밍 응답
3. 원격 클라이언트: 경량 Python CLI 또는 웹 UI
4. 세션 관리: JWT 토큰 기반

### Option 2: WebSocket 기반

```
┌─────────────┐       WebSocket          ┌─────────────┐
│   Client    │ ◄─────────────────────► │   Backend   │
│  (Web UI)   │      Bi-directional      │  (FastAPI)  │
└─────────────┘                          └─────────────┘
```

**장점:**
- ✅ 양방향 통신
- ✅ 실시간 interactive 지원
- ✅ 웹 브라우저 기반

**단점:**
- ❌ WebSocket 지원 필요 (일부 프록시 문제)
- ❌ 더 복잡한 구현

### Option 3: SSH 터널링 (가장 간단)

```
Client ──SSH──> Server ──> python -m cli
```

**장점:**
- ✅ 즉시 사용 가능
- ✅ 보안 내장

**단점:**
- ❌ SSH 서버 설정 필요
- ❌ 사용자 계정 관리 필요

## 🎨 추천 구현: HTTP/SSE 원격 CLI

### 1. Backend API 추가

```python
# backend/api/routes/cli.py

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

@router.post("/cli/session")
async def create_cli_session(
    request: CLIRequest,
    token: str = Depends(verify_token)
):
    """Create new CLI session"""
    session_id = create_session(token.user_id)
    return {"session_id": session_id, "workspace": get_workspace(session_id)}

@router.get("/cli/session/{session_id}/stream")
async def stream_cli_execution(
    session_id: str,
    prompt: str,
    token: str = Depends(verify_token)
):
    """Execute prompt with streaming response"""
    async def event_generator():
        async for update in execute_tool_use_workflow(prompt, session_id):
            yield {
                "event": update["type"],
                "data": json.dumps(update)
            }

    return EventSourceResponse(event_generator())
```

### 2. 경량 원격 CLI 클라이언트

```python
# remote_cli.py

import httpx
import asyncio
from rich.console import Console

class RemoteCLI:
    def __init__(self, server_url: str, token: str):
        self.server_url = server_url
        self.token = token
        self.console = Console()

    async def run(self):
        # Create session
        session = await self.create_session()

        # Interactive loop
        while True:
            prompt = self.console.input("[bold cyan]You:[/bold cyan] ")

            # Stream execution
            async for update in self.stream_execution(session["session_id"], prompt):
                self.display_update(update)

    async def stream_execution(self, session_id, prompt):
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET",
                f"{self.server_url}/api/v1/cli/session/{session_id}/stream",
                params={"prompt": prompt},
                headers={"Authorization": f"Bearer {self.token}"}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
```

### 3. 사용 방법

```bash
# 서버에서 backend 실행
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# 클라이언트에서 원격 CLI 실행
python remote_cli.py --server http://server-ip:8000 --token YOUR_TOKEN
```

## 🔐 보안 고려사항

### 1. 인증
```python
# JWT 토큰 기반 인증
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials):
    token = credentials.credentials
    payload = jwt.decode(token, SECRET_KEY)
    return User(**payload)
```

### 2. 세션 격리
- 각 사용자는 독립된 workspace
- Session ID 기반 파일 격리
- 사용자별 리소스 할당량

### 3. Rate Limiting
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/cli/session")
@limiter.limit("10/minute")  # 분당 10개 세션
async def create_cli_session():
    ...
```

## 📊 성능 최적화

### 1. Connection Pool
```python
# 재사용 가능한 연결 풀
httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100),
    timeout=30.0
)
```

### 2. Caching
```python
# Redis를 사용한 세션 캐싱
import redis.asyncio as redis

session_cache = redis.Redis(host='localhost', port=6379)
```

## 🚀 배포 시나리오

### 1. 개발 환경
```
Developer Laptop → http://dev-server:8000
```

### 2. 팀 환경
```
Team Member 1 →
Team Member 2 → http://shared-server:8000 → vLLM Cluster
Team Member 3 →
```

### 3. 프로덕션
```
Users → Nginx (Load Balancer) → FastAPI x3 → vLLM Cluster
```

## 📝 구현 우선순위

### Phase 1: HTTP API (1-2일)
- [ ] Backend API endpoints 추가
- [ ] SSE 스트리밍 구현
- [ ] 기본 인증 (토큰 기반)

### Phase 2: 원격 CLI 클라이언트 (1일)
- [ ] Python 경량 클라이언트
- [ ] Rich 기반 UI
- [ ] 설정 파일 지원

### Phase 3: 웹 UI (선택사항, 2-3일)
- [ ] React/Vue 웹 터미널
- [ ] xterm.js 통합
- [ ] 브라우저에서 직접 접속

## 🎯 다음 단계

1. **즉시 사용 가능**: SSH 터널링
   ```bash
   ssh user@server "cd /path/to/agentic-coder/backend && python -m cli"
   ```

2. **단기 구현**: HTTP/SSE API
   - Backend API 추가
   - 경량 Python 클라이언트

3. **장기 비전**: 웹 기반 터미널
   - 브라우저에서 직접 접속
   - 팀 협업 기능

## 💡 권장사항

**현재 단계에는 Option 3 (SSH 터널링) 추천**
- 즉시 사용 가능
- 추가 개발 불필요
- 안정성 검증됨

**다음 단계에는 Option 1 (HTTP/SSE) 구현**
- 확장 가능
- 팀 환경에 적합
- 웹 UI로 발전 가능
