# Context Improvement Plan
## 대화 컨텍스트 유지 개선 계획

**작성일**: 2026-01-07
**목적**: 동일 세션 내 이전 대화 내역에 대한 문맥 이해 개선

---

## 🔴 현재 문제점

### 1. 극심한 컨텍스트 제한
```python
# backend/app/agent/langgraph/dynamic_workflow.py:542-547
recent_context = conversation_history[-6:]  # 최근 6개 메시지만!
context_summary = "\n".join([
    f"{'사용자' if msg['role'] == 'user' else 'AI'}: {msg['content'][:200]}..."  # 200자만!
])
```

**문제점**:
- ❌ 최근 3번의 대화(6개 메시지)만 사용
- ❌ 각 메시지를 200자로 truncate
- ❌ 긴 대화에서 초기 컨텍스트 완전 손실
- ❌ 코드 생성/검토 내용 등 중요 정보 손실

### 2. Supervisor만 컨텍스트 접근
```python
# Supervisor에게만 enhanced_request로 전달
enhanced_request = f"""이전 대화 내용:
{context_summary}

현재 요청:
{user_request}"""
```

**문제점**:
- ❌ Coder, Reviewer, Refiner 등 다른 에이전트는 컨텍스트 없음
- ❌ 에이전트 간 컨텍스트 공유 불가
- ❌ 이전에 생성한 파일에 대한 수정 요청 시 문맥 손실

### 3. 단순 텍스트 Concatenation
**문제점**:
- ❌ 구조화된 컨텍스트가 아닌 단순 텍스트
- ❌ 중요도/시간순 구분 없음
- ❌ 파일명, 에러 메시지 등 중요 정보 추출 안됨

---

## ✅ 개선 방안

### Phase 1: 긴급 개선 (1-2시간) - **즉시 적용**

#### 1.1 컨텍스트 윈도우 확대
```python
# BEFORE: 6개 메시지
recent_context = conversation_history[-6:]

# AFTER: 20개 메시지 (최근 10번 대화)
recent_context = conversation_history[-20:]
```

#### 1.2 Truncate 한도 증가
```python
# BEFORE: 200자로 제한
msg['content'][:200]

# AFTER: 1000자로 확대
msg['content'][:1000]
```

#### 1.3 State에 Full Context 추가
```python
initial_state = {
    "user_request": user_request,
    "workspace_root": workspace_root,
    "conversation_history": conversation_history,  # ← 전체 히스토리 추가
    "conversation_summary": context_summary,      # ← 요약본도 유지
    ...
}
```

#### 1.4 모든 에이전트에서 컨텍스트 접근
- Coder: 이전에 생성한 파일 참조
- Reviewer: 이전 리뷰 이력 참조
- Refiner: 이전 개선 요청사항 참조

#### 1.5 GPT-OSS용 Harmony Format 적용
**OpenAI Harmony Format**: https://github.com/openai/harmony

**적용 사항**:
```python
# System Prompt 구조화
system_prompt = {
    "role": "system",
    "content": [
        {"type": "text", "text": "You are a coding assistant..."},
        {"type": "context", "context": conversation_history}  # Structured context
    ]
}

# User Prompt with Context
user_prompt = {
    "role": "user",
    "content": [
        {"type": "context", "context": recent_context},
        {"type": "text", "text": user_request}
    ]
}
```

**Harmony Format 핵심 원칙**:
1. 구조화된 메시지 형식 사용
2. Context를 별도 타입으로 분리
3. System/User 역할 명확히 구분
4. 메타데이터 활용 (timestamp, priority 등)

**예상 효과**:
- ✅ GPT-OSS 모델의 컨텍스트 이해력 향상
- ✅ 응답 품질 개선
- ✅ Hallucination 감소

---

### Phase 2: 구조 개선 (1일)

#### 2.1 컨텍스트 압축 시스템
```python
def compress_conversation_history(history: List[Dict], max_tokens: int = 4000):
    """오래된 대화는 요약, 최근 대화는 전체 보관"""
    if len(history) <= 10:
        return history

    # 최근 10개는 전체 보관
    recent = history[-10:]

    # 오래된 대화는 요약
    old_messages = history[:-10]
    summary = summarize_messages(old_messages)

    return [{"role": "system", "content": f"이전 대화 요약: {summary}"}] + recent
```

#### 2.2 중요 정보 추출
```python
def extract_key_info(history: List[Dict]) -> Dict:
    """파일명, 에러 메시지, 주요 결정사항 추출"""
    return {
        "files_mentioned": extract_filenames(history),
        "errors_encountered": extract_errors(history),
        "decisions_made": extract_decisions(history),
        "user_preferences": extract_preferences(history)
    }
```

#### 2.3 에이전트별 컨텍스트 필터링
```python
def get_agent_relevant_context(history: List[Dict], agent_type: str) -> List[Dict]:
    """에이전트 타입에 맞는 컨텍스트만 추출"""
    if agent_type == "coder":
        # 코드 생성 관련 대화만
        return filter_by_keywords(history, ["파일", "생성", "코드", "구현"])
    elif agent_type == "reviewer":
        # 리뷰/검토 관련 대화만
        return filter_by_keywords(history, ["리뷰", "검토", "수정", "개선"])
```

---

### Phase 3: 고도화 (1주)

#### 3.1 RAG 기반 컨텍스트 검색
```python
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings

def get_relevant_history(query: str, history: List[Dict], top_k: int = 10):
    """의미적으로 관련된 과거 대화 검색"""
    # 대화 히스토리를 벡터 DB에 저장
    vectorstore = Chroma.from_texts(
        texts=[msg['content'] for msg in history],
        metadatas=history,
        embedding=OpenAIEmbeddings()
    )

    # 현재 요청과 유사한 대화 검색
    relevant = vectorstore.similarity_search(query, k=top_k)
    return relevant
```

#### 3.2 세션 메모리 시스템
```python
class SessionMemory:
    """세션별 장기 메모리"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.files_worked_on: List[str] = []
        self.previous_errors: List[Dict] = []
        self.user_preferences: Dict = {}
        self.project_context: Dict = {}

    def update_from_conversation(self, message: Dict):
        """대화에서 중요 정보 추출하여 메모리 업데이트"""
        if "파일" in message['content']:
            self.files_worked_on.extend(extract_filenames(message))
        if "에러" in message['content']:
            self.previous_errors.append(extract_error_info(message))
```

#### 3.3 벡터 DB 통합
- ChromaDB 또는 Pinecone 사용
- 대화 히스토리 임베딩 저장
- 시간 가중치 적용 (최근 대화 우선)
- 의미적 유사도 기반 검색

---

## 📊 예상 효과

### Phase 1 적용 후
- ✅ 컨텍스트 윈도우: 3번 대화 → 10번 대화
- ✅ 정보 보존: 200자 → 1000자 (5배 증가)
- ✅ 모든 에이전트가 컨텍스트 접근 가능
- ✅ GPT-OSS 응답 품질 향상 (Harmony format)

### Phase 2 적용 후
- ✅ 장기 대화에서도 초기 컨텍스트 보존
- ✅ 중요 정보 자동 추출 및 보관
- ✅ 에이전트별 최적화된 컨텍스트

### Phase 3 적용 후
- ✅ 의미적 컨텍스트 검색
- ✅ 세션 간 지식 공유
- ✅ 프로젝트 컨텍스트 자동 관리

---

## 🚀 실행 계획

### ✅ Phase 1 - 긴급 개선 (즉시 시작)
- [ ] 1. `dynamic_workflow.py` 수정
  - [ ] 컨텍스트 윈도우: 6 → 20
  - [ ] Truncate 한도: 200 → 1000
  - [ ] State에 conversation_history 추가
- [ ] 2. `coder.py` 수정
  - [ ] State에서 conversation_history 접근
  - [ ] 이전 파일 생성 이력 참조
- [ ] 3. `reviewer.py` 수정
  - [ ] 이전 리뷰 이력 참조
- [ ] 4. GPT-OSS Harmony Format 적용
  - [ ] System prompt 구조화
  - [ ] Context 타입 분리
  - [ ] 메타데이터 추가

### 🔜 Phase 2 - 구조 개선 (이후)
- [ ] 컨텍스트 압축 로직 구현
- [ ] 중요 정보 추출 시스템
- [ ] 에이전트별 필터링

### 🔜 Phase 3 - 고도화 (장기)
- [ ] RAG 시스템 구축
- [ ] 세션 메모리 구현
- [ ] 벡터 DB 통합

---

## 📝 참고 자료

- OpenAI Harmony Format: https://github.com/openai/harmony
- LangChain Memory: https://python.langchain.com/docs/modules/memory/
- ChromaDB: https://www.trychroma.com/
- Context Window Management Best Practices

---

## 📌 변경 이력

| 날짜 | Phase | 내용 | 상태 |
|------|-------|------|------|
| 2026-01-07 | Phase 1 | 긴급 개선 시작 | 🔄 진행중 |
