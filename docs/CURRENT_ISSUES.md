# Agentic Coder - 현재 이슈 및 개선 계획

**작성일**: 2026-01-13
**버전**: v1.0.0 (Remote Client Release)
**브랜치**: `claude/fix-hardcoded-config-QyiND`

---

## 1. 현재 상태

### ✅ 최근 완료된 작업
| 커밋 해시 | 설명 | 상태 |
|----------|------|------|
| `b9cdecd` | Remote client를 local CLI workflow와 동기화 | ✅ 완료 |
| `964a406` | Windows PowerShell 종료 처리 수정 | ✅ 완료 |
| `1ca1097` | Session API에서 dynamic_workflow 사용 방식 수정 | ✅ 완료 |
| `251ce97` | GitHub Actions에서 Linux 빌드 제거 (로컬 빌드) | ✅ 완료 |
| `f88ffde` | Code execution tools의 dict 출력 형식 처리 | ✅ 완료 |

### 📊 프로젝트 구성
```
✅ Local CLI: backend/cli/terminal_ui.py (Tool Use workflow)
✅ Remote Client: backend/cli/remote_client.py (Tool Use workflow via SSE)
✅ Session API: backend/app/api/routes/session_routes.py (SessionManager)
✅ Tool Registry: 27개 도구 등록 (file, code, git, web, search, sandbox)
✅ GitHub Actions: Windows/macOS 자동 빌드
✅ Documentation: SERVER_SETUP.md, REMOTE_CLIENT_BINARY.md
```

### 🔧 환경 정보
- **OS**: Ubuntu 22.04 LTS
- **Python**: 3.x (venv 사용)
- **LLM**: DeepSeek-R1 (vLLM endpoint)
- **Docker**: ❌ 미설치 (확인됨)
- **Git Status**: Clean (커밋할 변경사항 없음)

---

## 2. Issue Lists - Issue Detail

### Issue #1: Sandbox 기능 미작동 (Critical) 🔴

**현상:**
- 로컬 동작 시 sandbox 기능이 작동하지 않음
- `SandboxExecuteTool`은 등록되어 있으나 실행 불가능

**원인:**
```bash
$ docker ps
docker: command not found
```
- Docker가 설치되지 않음
- `SandboxExecuteTool`은 Docker 컨테이너 기반 (AIO Sandbox)
- Docker 없이는 격리된 코드 실행 환경 제공 불가능

**영향 범위:**
- Python/Node.js/Shell 격리 실행 불가
- 보안 위험: 시스템에 직접 코드 실행
- LLM이 `sandbox_execute` 도구 호출 시 실패

**관련 파일:**
- `backend/app/tools/sandbox_tools.py` (SandboxExecuteTool, SandboxManager)
- `backend/app/tools/registry.py` (line 127: SandboxExecuteTool 등록)
- `backend/core/supervisor.py` (line 1276: sandbox_execute 도구 설명)

**기술적 세부사항:**
```python
# SandboxExecuteTool 요구사항
- Docker image: ghcr.io/agent-infra/sandbox:latest
- API endpoint: http://localhost:8080
- Container management: docker run/stop/ps
- Health check: GET /v1/sandbox
```

---

### Issue #2: 불필요한 임시 파일 생성 (Medium) 🟡

**현상:**
- 사용자 보고: "계속 불필요한 코드들이 생성되는데. code_1.txt, code_2.txt, code_3.txt, code_4.txt 이런 류의 파일들이 생성 되는데"
- 현재 워크스페이스에는 없음 (과거 세션에서 생성된 것으로 추정)

**원인 (추정):**
1. **LLM의 잘못된 도구 사용 패턴**
   - `execute_python`에 직접 코드를 전달해야 하는데
   - `write_file`로 code_1.txt를 먼저 생성 후 실행하는 패턴

2. **프롬프트 가이드라인 부족**
   - TOOL_USE_SYSTEM_PROMPT에 임시 파일 생성 금지 명시 안 됨
   - 올바른 도구 사용 예시 부족

3. **검증 로직 부재**
   - `WriteFileTool`에서 임시 파일 패턴 차단 안 됨
   - 세션 종료 시 임시 파일 정리 로직 없음

**영향 범위:**
- 워크스페이스 오염
- 사용자 혼란 (실제 프로젝트 파일 vs 임시 파일)
- 디스크 공간 낭비 (장기 실행 시)

**관련 파일:**
- `backend/core/supervisor.py` (line 1230-1330: TOOL_USE_SYSTEM_PROMPT)
- `backend/app/tools/file_tools.py` (WriteFileTool.validate_params)
- `backend/cli/session_manager.py` (세션 정리 로직 필요)

---

## 3. Issue 해결 계획

### Issue #1: Sandbox 기능 활성화

#### Option A: Docker 설치 및 구성 (권장) ⭐
**장점:**
- 완전한 격리 실행 환경
- 보안 강화
- 설계된 대로 동작

**단점:**
- Docker 설치 필요
- 리소스 사용 증가 (메모리 1GB, CPU 2코어)
- 설정 복잡도 증가

**구현 단계:**
```bash
# 1. Docker 설치 (Ubuntu 22.04)
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER  # 재로그인 필요

# 2. Sandbox 이미지 다운로드
docker pull ghcr.io/agent-infra/sandbox:latest

# 3. 서버 시작 시 자동 실행 설정
# start_server.sh에 Docker 체크 및 컨테이너 시작 로직 추가
```

#### Option B: Fallback 메커니즘 (빠른 해결) ⚡
**장점:**
- Docker 없어도 작동
- 기존 `ExecutePythonTool` 재사용
- 즉시 배포 가능

**단점:**
- 격리 실행 불가능 (보안 위험)
- 일부 기능 제한 (Node.js, TypeScript 미지원)

**구현 방법:**
```python
# supervisor.py: _execute_tool() 수정
async def _execute_tool(self, tool_name, arguments, context):
    # Sandbox 호출 시 Docker 확인
    if tool_name == "sandbox_execute":
        if not await self._check_docker_available():
            logger.warning("⚠️ Docker unavailable, falling back to execute_python")
            # Python만 fallback, 나머지는 에러 반환
            if arguments.get("language") == "python":
                tool_name = "execute_python"
                arguments = {"code": arguments["code"], "timeout": arguments.get("timeout", 30)}
            else:
                return {
                    "success": False,
                    "error": "Sandbox unavailable: Docker not installed. Only Python code can run without sandbox.",
                    "suggestion": "Install Docker or use execute_python for Python code"
                }
    # ... 기존 로직
```

#### Option C: 환경 검증 및 문서화 (병행) 📚
**구현:**
1. `start_server.sh/bat`에 Docker 체크 추가
2. 없으면 경고 출력
3. `docs/SANDBOX_SETUP.md` 작성
4. README에 Docker 요구사항 명시

---

### Issue #2: 임시 파일 생성 방지

#### 해결 전략: 3-Layer Defense

##### Layer 1: LLM 프롬프트 개선 (예방)
```python
# supervisor.py: TOOL_USE_SYSTEM_PROMPT 수정
TOOL_USE_SYSTEM_PROMPT = f"""
... (기존 내용) ...

## Important Guidelines for File Operations

❌ **DO NOT** create temporary files for code execution:
- NO: write_file(path="code_1.txt", ...) → execute_python(...)
- YES: execute_python(code="print('hello')", ...)

❌ **DO NOT** use numbered temporary files:
- NO: code_1.txt, code_2.txt, temp_script.py
- YES: Use execute_python() or shell_command() directly

✅ **ONLY use write_file()** for actual project files:
- Source code: main.py, utils.py, config.json
- Documentation: README.md, CHANGELOG.md
- Configuration: .env, pyproject.toml

Examples:
```python
# ❌ WRONG: Creating temporary file
write_file(path="code_1.txt", content="def foo(): pass")
execute_python(code=open("code_1.txt").read())

# ✅ CORRECT: Direct execution
execute_python(code="def foo(): pass\\nfoo()")
```
"""
```

##### Layer 2: WriteFileTool 검증 강화 (차단)
```python
# file_tools.py: WriteFileTool.validate_params() 수정
import re
from pathlib import Path

def validate_params(self, path: str, content: str, **kwargs) -> bool:
    # Base validation
    if not path or not isinstance(path, str):
        return False
    if not isinstance(content, str):
        return False

    # Prevent temporary file patterns
    filename = Path(path).name
    temp_patterns = [
        r'^code_\d+\.txt$',       # code_1.txt, code_2.txt
        r'^temp_.*\.(py|js|txt)$', # temp_script.py
        r'^tmp_.*$',               # tmp_anything
        r'^test_\d+\.txt$',        # test_1.txt
    ]

    for pattern in temp_patterns:
        if re.match(pattern, filename):
            logger.warning(
                f"⚠️ Refused to create temporary file: {filename}\n"
                f"   Use execute_python() or shell_command() instead.\n"
                f"   Temporary files pollute the workspace."
            )
            return False

    return True
```

##### Layer 3: 세션 정리 자동화 (청소)
```python
# session_manager.py: 세션 종료 시 정리
import glob

async def cleanup_temporary_files(self):
    """Remove temporary files from workspace at session end"""
    temp_patterns = [
        "code_*.txt",
        "temp_*.py",
        "temp_*.js",
        "tmp_*",
        "test_*.txt"
    ]

    removed_count = 0
    for pattern in temp_patterns:
        for file_path in self.workspace.glob(pattern):
            try:
                file_path.unlink()
                logger.info(f"🗑️  Cleaned up temporary file: {file_path.name}")
                removed_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove {file_path}: {e}")

    if removed_count > 0:
        logger.info(f"✅ Cleaned up {removed_count} temporary files")

    return removed_count

# SessionManager.__del__() 또는 explicit close() 메서드에서 호출
async def close(self):
    """Close session and cleanup"""
    await self.cleanup_temporary_files()
    if self.auto_save:
        self.save_session()
```

---

## 4. 실행 순서 및 우선 순위 설정

### Phase 1: 즉시 실행 (오늘) 🔥
**목표**: Docker 없이도 정상 작동 + 임시 파일 방지

| 순서 | 작업 | 예상 시간 | 담당 |
|------|------|----------|------|
| 1 | ✅ 현재 이슈 문서화 (`CURRENT_ISSUES.md`) | 30분 | ✅ 완료 |
| 2 | LLM 프롬프트 개선 (임시 파일 금지 명시) | 15분 | 대기 |
| 3 | WriteFileTool 검증 강화 (임시 파일 패턴 차단) | 30분 | 대기 |
| 4 | Sandbox fallback 메커니즘 추가 | 45분 | 대기 |
| 5 | 테스트 및 커밋 | 30분 | 대기 |

**완료 조건:**
- [x] CURRENT_ISSUES.md 작성
- [ ] LLM이 임시 파일 생성하지 않음
- [ ] Docker 없어도 Python 코드 실행 가능
- [ ] Sandbox 호출 시 명확한 에러 메시지

---

### Phase 2: 단기 개선 (이번 주) 📅
**목표**: Docker 설치 + 문서화 + 자동 정리

| 순서 | 작업 | 예상 시간 | 담당 |
|------|------|----------|------|
| 1 | Docker 설치 및 Sandbox 활성화 | 1시간 | 대기 |
| 2 | `docs/SANDBOX_SETUP.md` 작성 | 30분 | 대기 |
| 3 | `start_server.sh/bat`에 Docker 체크 추가 | 30분 | 대기 |
| 4 | SessionManager에 cleanup 메서드 추가 | 30분 | 대기 |
| 5 | README에 Docker 요구사항 명시 | 15분 | 대기 |
| 6 | Health check에 Docker 상태 추가 | 30분 | 대기 |

**완료 조건:**
- [ ] Sandbox 정상 작동 (Python/Node.js/Shell)
- [ ] 문서화 완료 (설치 가이드)
- [ ] 서버 시작 시 환경 검증
- [ ] 세션 종료 시 임시 파일 자동 제거

---

### Phase 3: 중기 개선 (선택 사항) 💡
**목표**: 사용자 경험 개선 + 모니터링

| 작업 | 설명 | 우선순위 |
|------|------|----------|
| Sandbox 상태 모니터링 | `/health`에 Docker/Sandbox 상태 표시 | 중 |
| CLI 시작 시 환경 검증 | Docker 없으면 경고 출력 | 중 |
| Workspace 사용량 추적 | 세션별 디스크 사용량 모니터링 | 낮음 |
| 자동 정리 스케줄러 | 오래된 세션 자동 제거 | 낮음 |
| Tool 사용 통계 | 어떤 도구가 많이 사용되는지 분석 | 낮음 |

---

## 5. 개선 계획

### 5.1 Sandbox 기능 개선

#### 현재 구조
```
┌─────────────────┐
│  Supervisor     │
│  (Tool Use)     │
└────────┬────────┘
         │
         ├─ execute_python ──> 시스템에 직접 실행 (위험)
         │
         └─ sandbox_execute ──> Docker (안전, 현재 미작동)
                               ├─ Python (Jupyter API)
                               ├─ Node.js (Shell API)
                               ├─ TypeScript (ts-node)
                               └─ Shell (bash)
```

#### 개선된 구조
```
┌─────────────────┐
│  Supervisor     │
│  (Tool Use)     │
└────────┬────────┘
         │
         ├─ execute_python ──> Fallback (Docker 없을 때)
         │                     └─ 경고: "격리 실행 아님"
         │
         └─ sandbox_execute ──>
              ├─ Docker 체크
              │  ├─ ✅ Available → Sandbox 실행
              │  └─ ❌ Unavailable →
              │       ├─ Python → execute_python (경고)
              │       └─ Others → Error (명확한 메시지)
              │
              └─ Health monitoring
                 ├─ Container status
                 ├─ API availability
                 └─ Resource usage
```

#### 구현 세부사항

**1. Docker 가용성 체크 함수**
```python
# supervisor.py 또는 sandbox_tools.py
async def check_docker_available() -> Dict[str, Any]:
    """Check Docker availability and status"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return {
                "available": True,
                "status": "running",
                "message": "Docker is available"
            }
        else:
            return {
                "available": False,
                "status": "error",
                "message": stderr.decode().strip()
            }
    except FileNotFoundError:
        return {
            "available": False,
            "status": "not_installed",
            "message": "Docker is not installed"
        }
    except Exception as e:
        return {
            "available": False,
            "status": "unknown",
            "message": str(e)
        }
```

**2. Health Check 개선**
```python
# app/main.py: /health endpoint 수정
@app.get("/health")
async def health_check():
    health = {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "llm": await check_llm_connection(),
            "vector_db": await check_vector_db(),
            "docker": await check_docker_available(),  # NEW
            "sandbox": await check_sandbox_ready()      # NEW
        }
    }

    # Docker 없으면 degraded 상태
    if not health["components"]["docker"]["available"]:
        health["status"] = "degraded"
        health["warnings"] = [
            "Docker is not available. Sandbox execution will use fallback mode."
        ]

    return health

async def check_sandbox_ready() -> Dict[str, Any]:
    """Check if Sandbox container is ready"""
    try:
        from app.tools.sandbox_tools import SandboxManager
        manager = await SandboxManager.get_instance()
        is_ready = await manager.is_running()

        if is_ready:
            info = await manager.get_info()
            return {
                "status": "ready",
                "container": manager._container_id,
                "info": info
            }
        else:
            return {
                "status": "not_running",
                "message": "Sandbox container is not running"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
```

**3. 서버 시작 스크립트 개선**
```bash
# start_server.sh에 추가
echo "🔍 Checking environment..."

# Docker 체크
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        echo "✅ Docker is available"

        # Sandbox 이미지 체크
        if docker images | grep -q "agent-infra/sandbox"; then
            echo "✅ Sandbox image found"
        else
            echo "⚠️  Sandbox image not found"
            echo "   Run: docker pull ghcr.io/agent-infra/sandbox:latest"
        fi
    else
        echo "⚠️  Docker is installed but not running"
        echo "   Run: sudo systemctl start docker"
    fi
else
    echo "⚠️  Docker is not installed"
    echo "   Sandbox features will be unavailable"
    echo "   Install: sudo apt-get install docker.io"
    echo ""
    echo "   The server will start in fallback mode."
    echo "   Python code will run directly (not isolated)."
    echo ""
    read -p "   Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

---

### 5.2 임시 파일 생성 방지 개선

#### 예방 메커니즘 (Prevention)

**1. LLM Few-shot Examples 추가**
```python
# supervisor.py: TOOL_USE_SYSTEM_PROMPT에 예시 추가
"""
## Correct Tool Usage Examples

### Example 1: Execute Python code ✅
User: "Calculate factorial of 5"

CORRECT:
{
  "tool": "execute_python",
  "arguments": {
    "code": "def factorial(n):\\n    if n <= 1: return 1\\n    return n * factorial(n-1)\\nprint(factorial(5))"
  }
}

WRONG ❌:
{
  "tool": "write_file",
  "arguments": {"path": "code_1.txt", "content": "def factorial..."}
}
{
  "tool": "execute_python",
  "arguments": {"code": "exec(open('code_1.txt').read())"}
}

### Example 2: Create actual project file ✅
User: "Create a utility module"

CORRECT:
{
  "tool": "write_file",
  "arguments": {
    "path": "utils/helpers.py",
    "content": "def format_output(data):\\n    ..."
  }
}

### Example 3: Multi-step code execution ✅
User: "Test the database connection"

CORRECT:
{
  "tool": "execute_python",
  "arguments": {
    "code": "import sqlite3\\nconn = sqlite3.connect('test.db')\\nprint('Connected')"
  }
}
"""
```

**2. Tool Schema에 경고 추가**
```python
# file_tools.py: WriteFileTool.__init__()
self.description = """
Write content to a file. Creates directories if needed.

⚠️ IMPORTANT: Use this ONLY for actual project files.
DO NOT create temporary files like code_1.txt, temp_script.py.
For code execution, use execute_python() or shell_command() directly.

Good use cases:
- Source code: main.py, utils.py, models.py
- Configuration: config.json, .env
- Documentation: README.md, docs/guide.md

Bad use cases ❌:
- code_1.txt, code_2.txt (use execute_python instead)
- temp_script.py (use execute_python instead)
- tmp_test.js (use sandbox_execute instead)
"""
```

#### 감지 메커니즘 (Detection)

**1. Real-time Monitoring**
```python
# supervisor.py: _execute_tool() 수정
async def _execute_tool(self, tool_name, arguments, context):
    # Monitor write_file calls
    if tool_name == "write_file":
        path = arguments.get("path", "")
        if self._is_suspicious_temp_file(path):
            logger.warning(
                f"🚨 SUSPICIOUS FILE CREATION DETECTED: {path}\n"
                f"   This looks like a temporary file.\n"
                f"   Consider using execute_python() or sandbox_execute() instead."
            )
            # Option 1: Block (strict)
            # return {"success": False, "error": "Temporary file creation blocked"}

            # Option 2: Warn but allow (lenient)
            # Continue with execution but log for analysis

    # ... 기존 로직

def _is_suspicious_temp_file(self, path: str) -> bool:
    """Check if path looks like a temporary file"""
    filename = Path(path).name
    suspicious_patterns = [
        r'^code_\d+\.txt$',
        r'^temp_.*\.(py|js|txt)$',
        r'^tmp_',
        r'^test_\d+\.',
    ]
    return any(re.match(p, filename) for p in suspicious_patterns)
```

**2. Session Analytics**
```python
# session_manager.py: 세션 통계 추가
class SessionManager:
    def __init__(self, ...):
        # ...
        self.stats = {
            "files_created": [],
            "suspicious_files": [],
            "tools_used": {}
        }

    def record_tool_use(self, tool_name, arguments, result):
        """Record tool usage for analytics"""
        # Count tool usage
        self.stats["tools_used"][tool_name] = \
            self.stats["tools_used"].get(tool_name, 0) + 1

        # Track file creation
        if tool_name == "write_file" and result.get("success"):
            path = arguments.get("path")
            self.stats["files_created"].append(path)

            # Flag suspicious files
            if self._is_suspicious_temp_file(path):
                self.stats["suspicious_files"].append({
                    "path": path,
                    "timestamp": datetime.now().isoformat()
                })

    def get_session_report(self) -> Dict:
        """Generate session summary report"""
        return {
            "session_id": self.session_id,
            "duration": ...,
            "total_interactions": len(self.conversation_history),
            "files_created": len(self.stats["files_created"]),
            "suspicious_files": len(self.stats["suspicious_files"]),
            "top_tools": sorted(
                self.stats["tools_used"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
```

#### 정리 메커니즘 (Cleanup)

**1. Automatic Cleanup on Session End**
```python
# session_manager.py
async def close(self):
    """Close session with cleanup"""
    # 1. Cleanup temporary files
    removed = await self.cleanup_temporary_files()

    # 2. Generate report
    report = self.get_session_report()
    if removed > 0:
        report["cleanup"] = {
            "removed_files": removed,
            "message": f"Cleaned up {removed} temporary files"
        }

    # 3. Save session
    if self.auto_save:
        self.save_session()

    # 4. Log summary
    logger.info(f"📊 Session {self.session_id} closed:")
    logger.info(f"   - Interactions: {report['total_interactions']}")
    logger.info(f"   - Files created: {report['files_created']}")
    logger.info(f"   - Cleaned up: {removed} files")

    return report
```

**2. Manual Cleanup Command**
```python
# CLI에서 /cleanup 명령어 추가
async def handle_cleanup_command(self):
    """Handle /cleanup command"""
    self.console.print("[yellow]🧹 Cleaning up temporary files...[/yellow]")

    patterns = ["code_*.txt", "temp_*.py", "tmp_*"]
    removed = []

    for pattern in patterns:
        for file_path in self.session_mgr.workspace.glob(pattern):
            try:
                file_path.unlink()
                removed.append(file_path.name)
            except Exception as e:
                logger.error(f"Failed to remove {file_path}: {e}")

    if removed:
        self.console.print(f"[green]✓ Removed {len(removed)} files:[/green]")
        for filename in removed:
            self.console.print(f"  - {filename}")
    else:
        self.console.print("[green]✓ No temporary files found[/green]")
```

---

### 5.3 문서화 개선

#### 추가할 문서

**1. `docs/SANDBOX_SETUP.md`**
```markdown
# Sandbox Setup Guide

## Requirements
- Docker 19.03+
- 2GB RAM available
- 10GB disk space

## Installation
[Step-by-step guide]

## Configuration
[Environment variables]

## Troubleshooting
[Common issues]
```

**2. `docs/TROUBLESHOOTING.md`**
```markdown
# Troubleshooting Guide

## Sandbox Issues
- Docker not found
- Container won't start
- Permission denied

## File Issues
- Temporary files accumulating
- Workspace permission errors

## Network Issues
- Remote client connection failed
- vLLM endpoint unreachable
```

**3. README 업데이트**
- Docker 요구사항 명시
- 설치 가이드 링크
- FAQ 섹션 추가

---

## 6. 성공 기준 (Definition of Done)

### Phase 1 완료 조건
- [ ] Docker 없어도 서버가 정상 시작됨
- [ ] Python 코드가 fallback으로 실행됨
- [ ] LLM이 임시 파일을 생성하지 않음
- [ ] Suspicious file 생성 시 경고 로그 출력
- [ ] 모든 테스트 통과

### Phase 2 완료 조건
- [ ] Docker 설치 및 Sandbox 정상 작동
- [ ] 문서화 완료 (SANDBOX_SETUP.md, TROUBLESHOOTING.md)
- [ ] Health check에 Docker 상태 표시
- [ ] 서버 시작 시 환경 검증 수행
- [ ] 세션 종료 시 임시 파일 자동 제거

### Phase 3 완료 조건
- [ ] Sandbox 모니터링 대시보드
- [ ] Workspace 사용량 추적
- [ ] Tool 사용 통계 수집
- [ ] 자동 정리 스케줄러 작동

---

## 7. 참고 자료

### 관련 파일
- `backend/app/tools/sandbox_tools.py` - Sandbox 구현
- `backend/app/tools/file_tools.py` - 파일 도구
- `backend/core/supervisor.py` - Tool Use 워크플로
- `backend/cli/session_manager.py` - 세션 관리
- `backend/app/main.py` - Health check

### 외부 문서
- Docker 설치: https://docs.docker.com/engine/install/
- AIO Sandbox: https://github.com/agent-infra/sandbox
- PyInstaller: https://pyinstaller.org/

---

**다음 단계**: Phase 1 구현 시작 (LLM 프롬프트 개선)
