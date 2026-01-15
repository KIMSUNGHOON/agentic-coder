# Agentic 2.0 CLI Terminal UI 사용 가이드

## 📺 화면 구성

Agentic 2.0 CLI는 다음과 같은 구조로 구성되어 있습니다:

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: Agentic 2.0 - AI Coding Assistant                      │
│         Local GPT-OSS-120B | On-Premise Only                   │
├─────────────────────────┬───────────────────────────────────────┤
│                         │                                       │
│  Chat 영역              │  Logs 영역                            │
│  (대화 내용)            │  (시스템 로그)                        │
│                         │                                       │
│                         │───────────────────────────────────────│
│                         │                                       │
│                         │  Chain of Thought 영역                │
│                         │  (AI 사고 과정)                       │
│                         │                                       │
├─────────────────────────┴───────────────────────────────────────┤
│  Message Input                                                  │
│  (메시지 입력창)                                                │
├─────────────────────────────────────────────────────────────────┤
│  Progress 영역                                                  │
│  (작업 진행 상황)                                               │
├─────────────────────────────────────────────────────────────────┤
│ Status Bar: ● Ready | ♥ Healthy | No session | 🔒 Local Only  │
├─────────────────────────────────────────────────────────────────┤
│ Footer: ^C Quit | ^L Clear | ^H Toggle CoT | ^S Save           │
└─────────────────────────────────────────────────────────────────┘
```

## 🔍 Status Bar (하단 상태 표시줄) 설명

하단의 Status Bar는 시스템 상태를 실시간으로 표시합니다:

### 1. ● Ready / Processing / Error (현재 상태)

**의미**: 시스템의 현재 작업 상태를 나타냅니다.

| 표시 | 색상 | 의미 | 설명 |
|------|------|------|------|
| **● Ready** | 초록색 | 준비 완료 | 새로운 작업을 받을 준비가 되었습니다 |
| **● Processing** | 노란색 | 처리 중 | 현재 작업을 실행하고 있습니다 |
| **● Error** | 빨간색 | 오류 | 오류가 발생했습니다 |
| **● Initializing** | 흰색 | 초기화 중 | 시스템이 시작되고 있습니다 |

**예시**:
```
● Ready      → 메시지 입력 대기 중
● Processing → "파일 분석 중..." 작업 실행 중
● Error      → "LLM 서버 연결 실패" 등의 오류 발생
```

### 2. ♥ Healthy / Degraded / Unhealthy (시스템 건강 상태)

**의미**: LLM 서버와 시스템 구성 요소의 건강 상태를 나타냅니다.

| 표시 | 색상 | 의미 | 설명 |
|------|------|------|------|
| **♥ Healthy** | 초록색 | 정상 | 모든 시스템이 정상 작동 중 |
| **! Degraded** | 노란색 | 성능 저하 | 일부 기능이 느리거나 제한됨 |
| **✗ Unhealthy** | 빨간색 | 비정상 | 중요 구성 요소에 문제 발생 |
| **? Unknown** | 회색 | 알 수 없음 | 아직 상태 확인 전 |

**상태 판단 기준**:
- **Healthy**: LLM 서버 응답 정상, 모든 endpoint 사용 가능
- **Degraded**: Primary endpoint 실패, Secondary로 전환됨
- **Unhealthy**: 모든 LLM endpoint 실패, 작업 실행 불가
- **Unknown**: 시스템 시작 직후 또는 health check 전

**예시**:
```
♥ Healthy   → localhost:8001, localhost:8002 모두 정상
! Degraded  → localhost:8001 실패, localhost:8002만 사용 중
✗ Unhealthy → LLM 서버 모두 연결 실패
```

### 3. Session: xxxxxxxx / No session (세션 정보)

**의미**: 현재 대화 세션의 ID를 표시합니다.

| 표시 | 의미 | 설명 |
|------|------|------|
| **Session: a1b2c3d4** | 세션 활성 | 대화가 진행 중이며, 세션 ID는 a1b2c3d4... |
| **No session** | 세션 없음 | 아직 대화를 시작하지 않음 |

**세션이란?**:
- 하나의 대화 흐름을 추적하는 고유 식별자
- 대화 히스토리, 컨텍스트 등이 세션에 저장됨
- Ctrl+S로 세션을 로컬에 저장 가능

**세션 ID 형식**:
```
Session: a1b2c3d4  ← 전체 ID의 앞 8자리만 표시
(실제: a1b2c3d4-e5f6-7890-abcd-1234567890ab)
```

**예시**:
```
No session     → 프로그램 시작 직후
Session: fe52bd1 → 첫 메시지 전송 후 세션 생성됨
```

### 4. 🔒 Local Only (로컬 전용 모드)

**의미**: 모든 데이터가 로컬에만 저장되고, 외부 네트워크로 전송되지 않음을 보장합니다.

| 표시 | 색상 | 의미 |
|------|------|------|
| **🔒 Local Only** | 초록색 굵게 | 로컬 전용 모드 활성 |

**보안 보장**:
- ✅ 모든 데이터는 로컬 디스크에만 저장
- ✅ LLM 서버는 localhost (on-premise)만 사용
- ✅ 외부 API 호출 없음
- ✅ 인터넷 연결 불필요
- ✅ 데이터 유출 위험 없음

**저장 위치**:
```
./data/sessions/        # 세션 데이터
./logs/agentic.log      # 시스템 로그
./logs/prompts/         # 디버깅용 프롬프트 (save_prompts=true 시)
agentic.db              # SQLite 데이터베이스 (로컬)
```

**네트워크 접근 감지**:
- 외부 네트워크 접근이 감지되면 경고 표시:
  ```
  ⚠️  Security Warning: External network detected
  ```

## ⌨️ 키보드 단축키 (Footer 설명)

Footer에 표시되는 단축키들:

### 📋 ^P Palette (Ctrl+P: Command Palette)

**기능**: Textual의 Command Palette를 엽니다 (프레임워크 기본 기능).

**사용법**:
```
Ctrl+P를 누르면 Command Palette가 열립니다.
```

**Command Palette란?**:
- 사용 가능한 모든 명령어와 단축키를 검색하고 실행할 수 있는 메뉴
- 단축키를 외우지 않아도 기능을 쉽게 찾을 수 있습니다

**주요 기능**:
- 모든 키바인딩 검색
- 명령어 자동완성
- 빠른 기능 실행

**예시**:
```
Ctrl+P 입력 → Command Palette 열림
"clear" 입력 → "Clear Chat (^L)" 표시
Enter → 채팅 지우기 실행
```

**활용 시나리오**:
- 단축키를 잊어버렸을 때
- 사용 가능한 모든 기능 확인
- 키보드만으로 빠르게 작업

### 1. ^C Quit (Ctrl+C: 종료)

**기능**: 프로그램을 종료합니다.

**사용법**:
```
Ctrl+C를 누르면 프로그램이 즉시 종료됩니다.
```

**주의**:
- 진행 중인 작업이 있으면 중단됩니다
- 세션은 자동 저장되지 않으므로, 종료 전 Ctrl+S로 저장하세요

### 2. ^L Clear Chat (Ctrl+L: 채팅 지우기)

**기능**: 채팅 영역의 대화 내용을 지웁니다.

**사용법**:
```
Ctrl+L을 누르면 화면의 채팅 내용이 모두 지워집니다.
```

**주의**:
- 화면에서만 지워지며, 세션 데이터는 유지됩니다
- 시각적으로 깔끔하게 정리하고 싶을 때 사용
- Ctrl+S로 저장한 세션은 영향받지 않습니다

### 3. ^H Toggle CoT (Ctrl+H: Chain-of-Thought 토글)

**기능**: Chain-of-Thought (사고 과정) 패널을 표시/숨김 전환합니다.

**사용법**:
```
Ctrl+H를 누르면 우측 하단의 "Chain of Thought" 패널이 사라집니다.
다시 누르면 다시 나타납니다.
```

**Chain-of-Thought란?**:
- AI가 작업을 수행하면서 거치는 사고 과정을 실시간으로 표시
- 예시:
  ```
  Step 1: Analyzing task complexity...
  Step 2: Planning execution strategy...
  Step 3: Executing tools...
  Step 4: Reviewing results...
  ```

**언제 숨기나?**:
- 화면 공간이 부족할 때
- 최종 결과만 보고 싶을 때
- 디버깅이 필요 없을 때

### 4. ^S Save (Ctrl+S: 세션 저장)

**기능**: 현재 세션을 로컬에 저장합니다.

**사용법**:
```
Ctrl+S를 누르면 현재 대화 히스토리가 로컬에 저장됩니다.
```

**저장 내용**:
- 대화 히스토리 (사용자 입력 + AI 응답)
- 명령어 히스토리
- 세션 메타데이터

**저장 위치**:
```
./data/sessions/session_<timestamp>.json
```

**알림 메시지**:
```
✅ Session saved locally  → 성공
❌ Failed to save session: <error> → 실패
```

## 🎨 Progress Bar 설명

Progress 영역에는 현재 작업의 진행 상황이 실시간으로 표시됩니다:

```
Progress
┌─────────────────────────────────────────────────┐
│ 작업 실행 중 (Executing tools) [5/50] ████░░░░│
│ → 🔧 Executing action: READ_FILE                │
└─────────────────────────────────────────────────┘
```

**표시 정보**:
- **작업 설명**: 현재 무엇을 하고 있는지
- **진행률**: [현재 iteration / 최대 iteration]
- **진행 바**: 시각적 진행 상황
- **상세 액션**: 실행 중인 구체적 액션

## 💡 사용 예시

### 예시 1: 정상 작동 중

```
Status Bar: ● Ready | ♥ Healthy | Session: fe52bd1 | 🔒 Local Only

→ 모든 시스템 정상, 세션 활성, 로컬 전용 모드
```

### 예시 2: LLM 서버 문제

```
Status Bar: ● Error | ✗ Unhealthy | No session | 🔒 Local Only

→ LLM 서버 연결 실패, 작업 실행 불가
→ 해결: localhost:8001, localhost:8002 서버 상태 확인
```

### 예시 3: 작업 처리 중

```
Status Bar: ● Processing | ♥ Healthy | Session: a1b2c3d | 🔒 Local Only

Progress:
작업 실행 중 (Executing tools) [12/50] ███████░░░░░░░
→ 🔧 Executing action: LIST_DIRECTORY

→ 현재 12번째 iteration 실행 중
```

### 예시 4: Secondary endpoint 사용 중

```
Status Bar: ● Ready | ! Degraded | Session: 3e37b9c | 🔒 Local Only

→ Primary endpoint (8001) 실패
→ Secondary endpoint (8002)로 전환되어 작동 중
→ 성능 저하 가능
```

## 🔧 트러블슈팅

### Q1: "✗ Unhealthy" 표시가 계속 나타남

**원인**: LLM 서버가 실행되지 않았거나 연결 실패

**해결**:
```bash
# 1. LLM 서버 상태 확인
curl http://localhost:8001/health
curl http://localhost:8002/health

# 2. vLLM 서버 실행 확인
ps aux | grep vllm

# 3. 포트 확인
netstat -tuln | grep 8001
netstat -tuln | grep 8002
```

### Q2: "! Degraded" 표시가 나타남

**원인**: Primary endpoint 실패, Secondary로 전환됨

**영향**: 일부 성능 저하, 하지만 작업은 계속 가능

**해결**:
```bash
# Primary endpoint 재시작
# config.yaml의 endpoints 확인
```

### Q3: "No session" 상태가 계속됨

**원인**: 첫 메시지를 아직 전송하지 않음

**해결**: 메시지를 입력하고 Enter를 누르면 세션이 자동 생성됩니다.

### Q4: Progress가 멈춘 것 같음

**확인 사항**:
1. Status Bar가 "● Processing" 상태인지
2. Logs 영역에서 실제 로그가 계속 업데이트되는지
3. Iteration 숫자가 증가하는지

**원인 가능성**:
- LLM 서버 응답 느림 (정상, 대기 필요)
- Max iterations 도달 (50/50 표시되면 정상 종료)
- Recursion limit 도달 (Bug Fix #8에서 해결됨)

### Q5: "⚠️ Security Warning: External network detected" 경고

**원인**: 외부 네트워크 접근 감지

**확인**:
```yaml
# config.yaml 확인
tools:
  network:
    enabled: false  # 반드시 false여야 함
```

**보안**: 이 경고가 나타나면 즉시 확인 필요!

## 📚 추가 정보

### Logs 영역

실시간으로 시스템 로그가 표시됩니다:

```
INFO  | 🚀 Starting workflow (max 50 iterations)
INFO  | 계획 수립 중 (Planning task execution strategy) [1/50]
INFO  | 🔧 Executing action: READ_FILE
INFO  | ✅ Action READ_FILE succeeded
DEBUG | Node: execute | Iteration: 5/50 | Continue: True
```

**로그 레벨**:
- **DEBUG**: 상세한 디버깅 정보 (config.yaml에서 level: DEBUG 설정 시)
- **INFO**: 일반 정보 (작업 진행 상황)
- **WARNING**: 경고 (성능 저하, iteration 임박 등)
- **ERROR**: 오류 (작업 실패, 서버 연결 실패 등)

### Chain of Thought 영역

AI의 사고 과정을 단계별로 표시:

```
Step 1: Analyzing task complexity (0.6)
Step 2: Planning execution with 5 steps
Step 3: Executing file operations
Step 4: Reviewing results - 3/5 completed
Step 5: Deciding to continue iteration
```

**활용**:
- AI가 왜 그런 결정을 내렸는지 이해
- 디버깅 시 문제 지점 파악
- 복잡한 작업의 진행 과정 추적

## 🎯 요약

| 요소 | 의미 | 색상 | 중요도 |
|------|------|------|--------|
| **● Ready** | 작업 준비 완료 | 초록 | ⭐⭐⭐ |
| **● Processing** | 작업 실행 중 | 노랑 | ⭐⭐⭐ |
| **● Error** | 오류 발생 | 빨강 | ⭐⭐⭐ |
| **♥ Healthy** | 시스템 정상 | 초록 | ⭐⭐⭐⭐⭐ |
| **! Degraded** | 성능 저하 | 노랑 | ⭐⭐⭐⭐ |
| **✗ Unhealthy** | 시스템 비정상 | 빨강 | ⭐⭐⭐⭐⭐ |
| **Session: xxx** | 세션 활성 | 청록 | ⭐⭐ |
| **No session** | 세션 없음 | 회색 | ⭐ |
| **🔒 Local Only** | 로컬 전용 | 초록 | ⭐⭐⭐⭐⭐ |
| **^C Quit** | 프로그램 종료 | - | ⭐⭐⭐ |
| **^L Clear** | 화면 정리 | - | ⭐ |
| **^H Toggle** | CoT 표시/숨김 | - | ⭐⭐ |
| **^S Save** | 세션 저장 | - | ⭐⭐⭐ |

---

**문서 버전**: 1.0.0
**작성일**: 2026-01-15
**관련**: Agentic 2.0 CLI Application (Bug Fix #8 포함)
