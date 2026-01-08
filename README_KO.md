<div align="center">

# Agentic Coder

### 엔터프라이즈급 AI 코딩 어시스턴트

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

**Claude Code 스타일의 통합 워크플로우 아키텍처를 구현한 프로덕션 레디 AI 코딩 어시스턴트**

[주요 기능](#-주요-기능) • [빠른 시작](#-빠른-시작) • [문서](#-문서) • [로드맵](#-로드맵)

---

[English Documentation](README.md)

</div>

---

## 왜 Agentic Coder인가?

단순한 코드 생성 도구와 달리, Agentic Coder는 Claude Code, GitHub Copilot Workspace와 유사한 **완전한 코딩 워크플로우**를 제공합니다.

<table>
<tr>
<td width="50%" valign="top">

### 차별화된 강점

- **통합 워크플로우** - 지능형 요청 라우팅 (Q&A, 계획, 코드 생성, 리뷰, 디버그)
- **20개 에이전트 도구** - 파일, Git, 코드, 웹, 샌드박스 작업
- **네트워크 모드** - 폐쇄망 엔터프라이즈 환경을 위한 온/오프라인 모드
- **멀티 모델** - DeepSeek-R1, Qwen3-Coder, GPT-OSS 지원
- **한국어 NLP** - 네이티브 한국어 지원
- **CLI + Web UI** - 동일한 기능의 두 가지 인터페이스

</td>
<td width="50%" valign="top">

### 엔터프라이즈 레디

- **폐쇄망 지원** - 완전한 오프라인 동작
- **데이터 프라이버시** - 오프라인 모드에서 외부 API 호출 없음
- **샌드박스 실행** - Docker 격리로 안전한 코드 실행
- **세션 관리** - 영구 대화 기록
- **자체 호스팅** - 자체 인프라에서 실행
- **262개 테스트** - 프로덕션 품질 테스트 커버리지

</td>
</tr>
</table>

---

## 주요 기능

### 1. 통합 워크플로우 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│                           사용자 요청                                  │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Supervisor Agent (추론 LLM)                        │
│                                                                       │
│     요청 분석 → 응답 타입 결정 → 적절한 핸들러로 라우팅                   │
└──────────────────────────────────────────────────────────────────────┘
         │              │              │              │              │
         ▼              ▼              ▼              ▼              ▼
    ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐
    │빠른 Q&A│    │  계획  │    │코드생성│    │  리뷰  │    │ 디버그 │
    └────────┘    └────────┘    └────────┘    └────────┘    └────────┘
         │              │              │              │              │
         └──────────────┴──────────────┴──────────────┴──────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │     통합 응답 + Artifacts         │
                    └──────────────────────────────────┘
```

**차별화 포인트:**
- 단일 진입점이 모든 요청 유형 처리
- Supervisor가 추론 LLM(DeepSeek-R1)을 사용해 지능적 분석
- 요청 복잡도에 따른 자동 라우팅
- 모든 핸들러에서 일관된 응답 포맷

---

### 2. 에이전트 도구 (20개)

<table>
<tr>
<td width="33%" valign="top">

**파일 & Git**
| 도구 | 기능 |
|:-----|:-----|
| `read_file` | 파일 읽기 |
| `write_file` | 파일 쓰기/생성 |
| `search_files` | 패턴 검색 |
| `list_directory` | 디렉토리 목록 |
| `git_status` | 저장소 상태 |
| `git_diff` | 변경 사항 |
| `git_log` | 커밋 히스토리 |
| `git_branch` | 브랜치 관리 |
| `git_commit` | 커밋 생성 |

</td>
<td width="33%" valign="top">

**코드 작업**
| 도구 | 기능 |
|:-----|:-----|
| `execute_python` | Python 실행 |
| `run_tests` | 테스트 실행 |
| `lint_code` | 린팅 |
| `format_code` | 포맷팅 |
| `shell_command` | 셸 실행 |
| `generate_docstring` | Docstring 생성 |
| `sandbox_execute` | 격리 실행 |

</td>
<td width="33%" valign="top">

**웹 & 검색**
| 도구 | 기능 |
|:-----|:-----|
| `code_search` | 코드 검색 |
| `web_search` | 웹 검색 |
| `http_request` | REST API |
| `download_file` | 파일 다운로드 |

**네트워크 모드**
- `online` = 모든 도구
- `offline` = 외부 API 차단

</td>
</tr>
</table>

---

### 3. 네트워크 모드 (폐쇄망 지원)

엄격한 보안 요구사항이 있는 **엔터프라이즈 환경**에 최적화되어 있습니다.

| 모드 | 설명 | 차단되는 도구 |
|:-----|:-----|:-------------|
| `online` | 전체 기능 | 없음 |
| `offline` | 폐쇄망 모드 | `web_search`, `http_request` |

**보안 정책:**
- **차단**: 외부로 데이터를 전송하는 도구
- **허용**: 데이터를 수신만 하는 도구 (다운로드)
- **허용**: 모든 로컬 도구 (파일, Git, 코드)

```bash
# 오프라인 모드 활성화
NETWORK_MODE=offline
```

---

### 4. 샌드박스 실행 (Docker 격리)

신뢰할 수 없는 코드를 격리된 컨테이너에서 안전하게 실행합니다.

```python
sandbox = registry.get_tool("sandbox_execute")

# Python 실행
result = await sandbox.execute(
    code="import os; print(os.getcwd())",
    language="python",
    timeout=60
)

# 셸 실행
result = await sandbox.execute(
    code="ls -la && whoami",
    language="shell"
)
```

**지원 언어**: Python, Node.js, TypeScript, Shell

**오프라인 설정:**
```bash
docker pull ghcr.io/agent-infra/sandbox:latest
# 첫 다운로드 후 오프라인에서 동작
```

---

### 5. CLI 인터페이스

완전한 기능의 명령줄 인터페이스:

- **명령 히스토리** - 세션 간 영구 저장
- **자동 완성** - 명령어 및 파일 경로 탭 완성
- **슬래시 명령** - `/help`, `/status`, `/preview`, `/config`
- **스트리밍 출력** - 실시간 코드 생성 표시

```bash
# 대화형 모드 시작
python -m cli

# 원샷 모드
python -m cli "Python REST API 만들어줘"

# 옵션과 함께
python -m cli --workspace ./project --model qwen2.5-coder:32b
```

---

## 빠른 시작

### 사전 요구사항

| 요구사항 | 버전 |
|:---------|:-----|
| Python | 3.12+ |
| Node.js | 20+ |
| Docker | 최신 (샌드박스용) |
| GPU | NVIDIA 권장 (vLLM용) |

### 설치

```bash
# 1. 클론
git clone https://github.com/your-org/agentic-coder.git
cd agentic-coder

# 2. 환경 설정
cp .env.example .env

# 3. 백엔드
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. 프론트엔드
cd ../frontend
npm install

# 5. 샌드박스 (선택)
docker pull ghcr.io/agent-infra/sandbox:latest
```

### 서비스 시작

```bash
# 터미널 1: vLLM (추론)
vllm serve deepseek-ai/DeepSeek-R1 --port 8001

# 터미널 2: vLLM (코딩)
vllm serve Qwen/Qwen3-8B-Coder --port 8002

# 터미널 3: 백엔드
cd backend && uvicorn app.main:app --port 8000 --reload

# 터미널 4: 프론트엔드
cd frontend && npm run dev
```

**접속:** http://localhost:5173

### Mock 모드 (GPU 없이)

```bash
./RUN_MOCK.sh  # Linux/Mac
RUN_MOCK.bat   # Windows
```

---

## 환경 설정

```bash
# .env

# LLM 엔드포인트
VLLM_REASONING_ENDPOINT=http://localhost:8001/v1
VLLM_CODING_ENDPOINT=http://localhost:8002/v1
REASONING_MODEL=deepseek-ai/DeepSeek-R1
CODING_MODEL=Qwen/Qwen3-8B-Coder

# 네트워크 모드
NETWORK_MODE=online  # 또는 'offline'

# 샌드박스
SANDBOX_IMAGE=ghcr.io/agent-infra/sandbox:latest
SANDBOX_HOST=localhost
SANDBOX_PORT=8080
SANDBOX_TIMEOUT=60
```

---

## API 레퍼런스

### 통합 채팅

```http
POST /chat/unified
Content-Type: application/json

{
  "message": "테스트가 포함된 Python 계산기 만들어줘",
  "session_id": "session-123",
  "workspace": "/path/to/workspace"
}
```

### 스트리밍

```http
POST /chat/unified/stream
```

---

## 테스트

```bash
cd backend
pytest app/tools/tests/ -v

# 262 passed, 8 skipped
```

---

## 문서

| 문서 | 설명 |
|:-----|:-----|
| [에이전트 도구 가이드](docs/AGENT_TOOLS_PHASE2_README.md) | 20개 도구 전체 문서 |
| [아키텍처](docs/ARCHITECTURE.md) | 시스템 설계 |
| [CLI 가이드](docs/CLI_PHASE3_USER_GUIDE.md) | 명령줄 인터페이스 |
| [Mock 모드](docs/MOCK_MODE.md) | GPU 없이 테스트 |

---

## 로드맵

- [x] **Phase 1** - 핵심 도구 (14개)
- [x] **Phase 2** - 네트워크 모드 + 웹 도구
- [x] **Phase 2.5** - 코드 포맷팅 도구
- [x] **Phase 3** - 성능 최적화
- [x] **Phase 4** - 샌드박스 실행
- [ ] **Phase 5** - 승인 워크플로우가 포함된 계획 모드
- [ ] **Phase 6** - MCP (Model Context Protocol) 통합
- [ ] **Phase 7** - 멀티 에이전트 협업

---

## 지원 모델

| 모델 | 유형 | 강점 |
|:-----|:-----|:-----|
| DeepSeek-R1 | 추론 | 복잡한 분석, 계획 |
| Qwen3-Coder | 코딩 | 코드 생성, 완성 |
| GPT-OSS | 범용 | 균형 잡힌 성능 |

---

## 기여하기

1. 저장소 Fork
2. 기능 브랜치 생성 (`git checkout -b feature/amazing`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치 푸시 (`git push origin feature/amazing`)
5. Pull Request 생성

---

## 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

<div align="center">

**사용 기술**

[![Python](https://img.shields.io/badge/-Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/-React-61DAFB?style=flat-square&logo=react&logoColor=black)](https://reactjs.org)
[![vLLM](https://img.shields.io/badge/-vLLM-FF6F00?style=flat-square&logo=lightning&logoColor=white)](https://vllm.ai)
[![Docker](https://img.shields.io/badge/-Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)

---

**이 프로젝트가 도움이 되셨다면 ⭐를 눌러주세요!**

</div>
