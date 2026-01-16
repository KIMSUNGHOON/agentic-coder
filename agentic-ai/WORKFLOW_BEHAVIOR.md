# Agentic 2.0 Workflow 동작 방식 설명

## 사용자 질문
> "Hello를 입력했을때 Executing Tools and operations가 동작 하는지 잘 모르겠습니다.
> workflow가 제대로 동작 하고 있는것입니까?"

**답변**: "Hello" 입력 시 **도구는 실행되지 않아야 합니다!** ✅

Agentic 2.0은 인사말을 감지하고 즉시 완료하도록 설계되었습니다.

---

## "Hello" 입력 시 전체 흐름

### 1단계: Intent Classification (의도 분류)

```
User Input: "Hello"
    ↓
IntentRouter.classify()
    ↓
[vLLM 서버 실행 중?]
    ├─ YES → LLM 기반 분류 실행
    │         - 프롬프트: "ALWAYS use GENERAL for greetings!"
    │         - 결과: GENERAL (confidence: 0.95)
    │         - 로그: "✅ Classification: general (confidence: 0.95)"
    │
    └─ NO → Rule-based fallback 분류
              - 인사말 키워드 체크: ['hello', 'hi', 'hey', '안녕', ...]
              - 결과: GENERAL (confidence: 0.95)
              - 로그: "👋 Detected greeting in fallback: 'Hello'"
```

**핵심**: vLLM 서버 실행 여부와 관계없이 항상 GENERAL workflow로 라우팅됩니다.

### 2단계: General Workflow 실행

```python
# agentic-ai/workflows/general_workflow.py
# Lines 56-63

async def plan_node(self, state: AgenticState):
    task_lower = state['task_description'].lower().strip()

    # 인사말 키워드 체크
    greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이']

    # 조건: 키워드 포함 AND 길이 < 20자
    if any(keyword in task_lower for keyword in greeting_keywords) and len(task_lower) < 20:
        logger.info("👋 Detected simple greeting, completing immediately")

        # 즉시 완료 설정
        state["task_status"] = TaskStatus.COMPLETED.value
        state["task_result"] = f"Hello! I'm Agentic 2.0. How can I help you today?"
        state["should_continue"] = False

        # plan_node에서 바로 리턴 → execute_node로 가지 않음!
        return state
```

**핵심**: `plan_node`에서 인사말을 감지하면 **즉시 완료**되고 `execute_node`로 가지 않습니다.

### 3단계: 결과 출력

```
[UI에 표시]
Hello! I'm Agentic 2.0. How can I help you today?

[Logs에 표시]
📋 Planning general task: Hello
👋 Detected simple greeting, completing immediately
✅ Task already COMPLETED
```

**도구 실행 없음!** "Executing Tools and operations" 메시지가 표시되지 않아야 합니다.

---

## Workflow 아키텍처

### LangGraph State Machine 구조

```
GeneralWorkflow StateGraph:

┌──────────────┐
│  User Input  │
│   "Hello"    │
└──────┬───────┘
       │
       v
┌──────────────┐
│  plan_node   │ ← 여기서 인사말 감지!
│              │
│ [Greeting?]  │
│  ├─ YES      │
│  │   ↓       │
│  │ Complete! │ ← 즉시 완료 (도구 실행 안 함)
│  │   ↓       │
│  │ RETURN    │
│  │           │
│  └─ NO       │
│      ↓       │
│   Create     │
│   plan       │
└──────┬───────┘
       │
       v
┌──────────────┐
│ execute_node │ ← 인사말은 여기까지 오지 않음!
│              │
│ [Execute     │
│  tools]      │
└──────┬───────┘
       │
       v
┌──────────────┐
│ reflect_node │
└──────────────┘
```

**핵심**: 인사말은 `plan_node`에서 즉시 완료되어 `execute_node`에 도달하지 않습니다.

---

## 실제 테스트 방법

### 테스트 1: vLLM 서버 실행 중

```bash
# 1. vLLM 서버 시작
cd /home/user/agentic-coder/agentic-ai
./start_vllm.sh

# 2. 30-60초 대기 (모델 로딩)
sleep 30

# 3. CLI 실행
python -m cli.app

# 4. "Hello" 입력
> Hello

# 5. 예상 출력
Hello! I'm Agentic 2.0. How can I help you today?

# 6. 로그 확인
tail -f logs/agentic.log | grep -E "(Classification|Detected|greeting)"
```

**예상 로그**:
```
✅ Classification: general (confidence: 0.95, complexity: low)
👋 Detected simple greeting, completing immediately
✅ Task already COMPLETED
```

**보면 안 되는 로그**:
```
❌ 🔧 Executing action: READ_FILE  (도구 실행 안 됨!)
❌ 🔧 Executing action: WRITE_FILE (도구 실행 안 됨!)
❌ ⚙️  Executing general task     (execute_node 실행 안 됨!)
```

### 테스트 2: vLLM 서버 없이 (Fallback 테스트)

```bash
# 1. vLLM 서버가 실행되지 않은 상태에서
./stop_vllm.sh  # 만약 실행 중이면 중지

# 2. CLI 실행
python -m cli.app

# 3. "Hello" 입력
> Hello

# 4. 예상 출력
🚨 LLM 서버에 연결할 수 없습니다!

하지만 fallback 분류가 작동하면:
Hello! I'm Agentic 2.0. How can I help you today?

# 5. 로그 확인
tail -f logs/agentic.log | grep -E "(Fallback|greeting|Classification)"
```

**예상 로그**:
```
❌ LLM classification failed: Connection refused
🔄 Falling back to rule-based classification
👋 Detected greeting in fallback: 'Hello'
🔧 Fallback classification: general (confidence: 0.95)
👋 Detected simple greeting, completing immediately
```

---

## 코드 경로 정리

### 파일 1: `core/router.py`

**LLM 분류 프롬프트** (lines 95-102):
```python
4. GENERAL: Task management, greetings, and mixed workflows
   - Simple greetings and conversational responses (ALWAYS use GENERAL for greetings!)

Examples: "Hello", "Hi", "Hey", "How are you?", "Organize these files"

IMPORTANT: If the input is a simple greeting (hello, hi, hey, etc.),
ALWAYS classify as GENERAL with high confidence!
```

**Fallback 분류** (lines 261-273):
```python
# CRITICAL: Check for greetings FIRST!
greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이',
                     'good morning', 'good afternoon', 'good evening']
is_greeting = any(prompt_lower.startswith(kw) or prompt_lower == kw
                  for kw in greeting_keywords)

if is_greeting and len(user_prompt) < 30:
    logger.info(f"👋 Detected greeting in fallback: '{user_prompt}'")
    return IntentClassification(
        domain=WorkflowDomain.GENERAL,
        confidence=0.95,
        reasoning="Simple greeting detected (rule-based)"
    )
```

### 파일 2: `workflows/general_workflow.py`

**Plan Node 인사말 처리** (lines 56-63):
```python
greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이']
if any(keyword in task_lower for keyword in greeting_keywords) and len(task_lower) < 20:
    logger.info("👋 Detected simple greeting, completing immediately")
    state["task_status"] = TaskStatus.COMPLETED.value
    state["task_result"] = f"Hello! I'm Agentic 2.0. How can I help you today?"
    state["should_continue"] = False
    return state  # 즉시 리턴 → execute_node 실행 안 됨!
```

### 파일 3: `workflows/coding_workflow.py`

**방어 코드** (lines 64-74):
```python
# Coding workflow에 실수로 들어온 인사말 처리
greeting_keywords = ['hello', 'hi', 'hey', 'greetings', '안녕', '하이']
if any(keyword in task_lower for keyword in greeting_keywords) and len(task_lower) < 30:
    logger.info("👋 Detected greeting in coding workflow (misclassified?), handling gracefully")
    state["task_result"] = "Hello! I'm Agentic 2.0, your AI coding assistant..."
    state["should_continue"] = False
    return state
```

---

## 디버깅 가이드

### 증상: "Hello" 입력 후 도구가 실행되는 것 같음

**확인 단계**:

1. **로그 확인**:
```bash
tail -f logs/agentic.log | grep -E "(Hello|hello|greeting|Classification|Executing)"
```

2. **분류 결과 확인**:
```
✅ Classification: general (confidence: 0.95)  # 정상
❌ Classification: coding (confidence: 0.85)   # 비정상!
```

3. **Workflow 진입 확인**:
```
✅ 📋 Planning general task: Hello
✅ 👋 Detected simple greeting, completing immediately
✅ ✅ Task already COMPLETED

❌ 📋 Planning coding task: Hello  # 비정상!
❌ ⚙️  Executing general task      # 비정상! (execute_node 실행)
```

4. **도구 실행 확인**:
```
❌ 🔧 Executing action: READ_FILE   # 절대 나오면 안 됨!
❌ 🔧 Executing action: WRITE_FILE  # 절대 나오면 안 됨!
```

### 증상별 해결 방법

#### 증상 1: LLM 서버 연결 실패
```
ERROR: All 4 attempts failed on all endpoints
```

**해결**:
```bash
# vLLM 서버 시작
./start_vllm.sh

# 30초 대기
sleep 30

# 연결 확인
curl http://localhost:8001/v1/models
```

#### 증상 2: Coding workflow로 분류됨
```
❌ Classification: coding
```

**해결**:
- 코드에 방어 로직이 있으므로 큰 문제는 아님
- 하지만 IntentRouter 프롬프트를 확인해야 함
- `core/router.py`의 CLASSIFICATION_PROMPT 확인

#### 증상 3: execute_node가 실행됨
```
⚙️  Executing general task
```

**해결**:
- `workflows/general_workflow.py` line 56-63 확인
- 인사말 키워드 리스트에 사용자의 인사말이 있는지 확인
- 예: "Hello" → 'hello' (소문자로 변환되므로 일치)

---

## 요약

### ✅ 정상 동작 (Hello 입력 시)

1. **Intent Classification**: GENERAL (confidence: 0.95)
2. **Workflow**: GeneralWorkflow 실행
3. **plan_node**: 인사말 감지 → 즉시 완료
4. **execute_node**: 실행되지 않음 (도구 실행 없음!)
5. **결과**: "Hello! I'm Agentic 2.0. How can I help you today?"

### ❌ 비정상 동작 (보면 안 되는 것들)

1. ❌ "Executing Tools and operations" 메시지
2. ❌ execute_node 실행
3. ❌ READ_FILE, WRITE_FILE 같은 도구 호출
4. ❌ 여러 iteration 반복

---

## 관련 Commits

- **e003138**: 초기 greeting 처리 개선 (IntentRouter 프롬프트 + coding_workflow 방어 코드)
- **fa42cd8**: Fallback 분류에 명시적 greeting 감지 추가

---

**작성일**: 2026-01-16
**브랜치**: claude/fix-hardcoded-config-QyiND
**작성자**: Claude (Sonnet 4.5)
