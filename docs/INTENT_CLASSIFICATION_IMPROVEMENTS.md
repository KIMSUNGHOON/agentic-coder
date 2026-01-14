# Intent Classification 개선 계획 (Improvement Roadmap)

**작성일**: 2026-01-14
**현재 상태**: Rule-based + LLM Hybrid (81.5% 정확도)
**목표**: 95%+ 정확도, 다양한 사용자 입력 패턴 대응

---

## 현재 시스템 분석

### ✅ 잘 작동하는 부분
1. **Hybrid Architecture**: Rule-based (빠름) + LLM (정확함) 조합
2. **2-Step Classification**: Intent → Workflow 결정
3. **Pattern Detection**: 인사, capability question 패턴 감지
4. **Direct Response**: Workflow 없이 즉시 응답 (simple_conversation, simple_question)

### ⚠️ 개선 필요 영역
1. **Edge Cases**: 애매한 입력에 대한 처리 (confidence < 0.7)
2. **Context Awareness**: 이전 대화 맥락 미활용
3. **Learning**: 잘못된 분류에서 학습하지 못함
4. **Multilingual**: 한국어/영어 외 언어 미지원

---

## 개선 계획 (우선순위 순)

### Phase 1: Few-Shot Learning 강화 (우선순위: 🔴 HIGH)

**현재 문제:**
- LLM에 예시를 제공하지만 체계적이지 않음
- Boundary case 예시가 prompt에만 있고 동적으로 선택되지 않음

**목표:**
- 유사한 예시를 동적으로 선택하여 LLM에 제공
- Few-shot accuracy를 85% → 92%로 향상

**구현 방법:**

```python
# backend/core/supervisor.py

# 1. Few-shot 예시 데이터베이스 구축
FEW_SHOT_EXAMPLES = {
    "simple_conversation": [
        ("안녕", "안녕하세요! 무엇을 도와드릴까요?"),
        ("Hello", "Hi! How can I help you today?"),
        ("감사합니다", "천만에요! 또 도움이 필요하시면 언제든지 말씀해주세요."),
        ("Thank you", "You're welcome! Let me know if you need anything else."),
    ],
    "simple_question": [
        ("계획도 작성 가능합니까?", "네, 저는 프로젝트 계획, 아키텍처 설계, 구현 계획 등을 작성할 수 있습니다."),
        ("Can you write plans?", "Yes, I can create project plans, architecture designs, and implementation roadmaps."),
        ("Python이 뭐야?", "Python은 간결한 문법과 높은 가독성으로 유명한 고급 프로그래밍 언어입니다."),
        ("What is Python?", "Python is a high-level programming language known for its simple syntax and readability."),
    ],
    "capability_question": [
        ("코드 리뷰 할 수 있어?", "네, 저는 코드 리뷰를 수행할 수 있습니다. 코드를 공유해주시면 리뷰해드리겠습니다."),
        ("Are you able to debug?", "Yes, I can help debug code. Please share the code and error details."),
        ("테스트 작성 지원하나요?", "네, 단위 테스트, 통합 테스트 등 다양한 테스트 코드를 작성해드릴 수 있습니다."),
    ],
    "coding_task": [
        ("REST API를 만들어줘", "[workflow 생성]"),
        ("Create a Flask server", "[workflow 생성]"),
        ("이 코드를 리뷰해줘", "[workflow 생성]"),
    ],
    "mixed_intent": [
        ("안녕! Python으로 웹서버 만들어줘", "[workflow 생성] - 인사는 있지만 주 의도는 코드 생성"),
        ("Hi! Can you explain REST API?", "[direct response] - 인사 + 질문이지만 주 의도는 설명 요청"),
    ]
}

# 2. 유사도 기반 예시 선택 (Semantic Search)
def _select_relevant_examples(self, request: str, k: int = 3) -> List[Tuple[str, str]]:
    """
    현재 요청과 가장 유사한 k개의 예시를 선택

    Args:
        request: 사용자 요청
        k: 반환할 예시 개수

    Returns:
        List of (example_input, expected_output) tuples
    """
    # TODO: Implement semantic similarity using embeddings
    # For now, use simple keyword matching
    request_lower = request.lower()

    relevant_examples = []

    # Check which category is most relevant
    if self._is_greeting(request_lower):
        relevant_examples = FEW_SHOT_EXAMPLES["simple_conversation"][:k]
    elif self._is_capability_question(request_lower):
        relevant_examples = FEW_SHOT_EXAMPLES["capability_question"][:k]
    elif self._has_code_intent(request_lower):
        relevant_examples = FEW_SHOT_EXAMPLES["coding_task"][:k]
    else:
        relevant_examples = FEW_SHOT_EXAMPLES["simple_question"][:k]

    return relevant_examples

# 3. Few-shot prompt 구성
def _build_few_shot_prompt(self, request: str, examples: List[Tuple[str, str]]) -> str:
    """Few-shot 예시를 포함한 prompt 구성"""
    examples_text = "\n\n".join([
        f"User: {inp}\nIntent: {out}"
        for inp, out in examples
    ])

    return f"""Based on these examples:

{examples_text}

Now classify this request:
User: {request}
Intent: """
```

**예상 효과:**
- Accuracy: 81.5% → 92%
- Edge case 처리 개선
- 비용: 기존 LLM 호출과 동일 (예시만 추가)

**구현 난이도:** ⭐⭐ (Medium)

**일정:** 1-2일

---

### Phase 2: Confidence Score & Clarification (우선순위: 🟡 MEDIUM)

**현재 문제:**
- Confidence score를 반환하지만 활용하지 않음
- 애매한 입력에 대해 사용자에게 확인하지 않음

**목표:**
- 낮은 confidence 입력에 대해 사용자에게 명확화 요청
- False positive workflow 생성 방지

**구현 방법:**

```python
# backend/core/supervisor.py

def analyze_request(self, request: str, context: Optional[List] = None) -> dict:
    """Analyze request with confidence scoring"""
    analysis = self._perform_analysis(request, context)

    # CRITICAL: Check confidence score
    if analysis["confidence_score"] < 0.7:
        # Low confidence - ask for clarification
        return {
            **analysis,
            "requires_clarification": True,
            "clarification_options": self._generate_clarification_options(request, analysis)
        }

    return analysis

def _generate_clarification_options(self, request: str, analysis: dict) -> List[dict]:
    """Generate clarification options for ambiguous requests"""
    options = []

    # Option 1: Provide information
    options.append({
        "type": "simple_question",
        "label": "질문에 답변하기 (정보 제공)",
        "description": "요청하신 내용에 대한 설명을 드리겠습니다."
    })

    # Option 2: Generate code/plan
    options.append({
        "type": "coding_task",
        "label": "코드/계획 작성하기 (Workflow 실행)",
        "description": "실제 코드나 계획을 작성하여 제공해드리겠습니다."
    })

    return options
```

```python
# backend/app/agent/unified_agent_manager.py

async def process_unified_request(self, ...):
    """Process request with clarification support"""
    analysis = self.supervisor.analyze_request(user_message, context)

    # NEW: Handle clarification requests
    if analysis.get("requires_clarification"):
        if stream:
            async def stream_clarification():
                yield StreamUpdate(
                    agent="supervisor",
                    update_type="clarification_needed",
                    status="waiting",
                    message="이 요청을 어떻게 처리할까요?",
                    data={
                        "options": analysis["clarification_options"],
                        "original_intent": analysis["intent"],
                        "confidence": analysis["confidence_score"]
                    }
                )
            return stream_clarification()
```

**Frontend 변경:**

```typescript
// frontend/src/components/WorkflowInterface.tsx

// Handle clarification requests
if (update.update_type === 'clarification_needed') {
  // Show modal with options
  const selectedOption = await showClarificationModal(update.data.options);

  // Re-submit with clarified intent
  await submitWithClarification(userMessage, selectedOption);
}
```

**예상 효과:**
- False positive 30% 감소
- 사용자 경험 개선 (잘못된 workflow 생성 방지)
- Accuracy: 92% → 94%

**구현 난이도:** ⭐⭐⭐ (High - Frontend 변경 필요)

**일정:** 2-3일

---

### Phase 3: Feedback Loop & Learning (우선순위: 🟡 MEDIUM)

**현재 문제:**
- 잘못된 분류를 수정할 방법이 없음
- 사용자 피드백을 학습에 활용하지 못함

**목표:**
- 사용자가 잘못된 분류를 보고할 수 있는 기능
- 보고된 데이터를 학습 예시에 추가

**구현 방법:**

```python
# backend/core/feedback_store.py (NEW)

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

class IntentFeedbackStore:
    """Store user feedback on intent classifications"""

    def __init__(self, feedback_file: str = "data/intent_feedback.jsonl"):
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)

    def add_feedback(
        self,
        user_input: str,
        predicted_intent: str,
        correct_intent: str,
        confidence_score: float,
        user_comment: str = ""
    ):
        """Record user correction"""
        feedback = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_input": user_input,
            "predicted_intent": predicted_intent,
            "correct_intent": correct_intent,
            "confidence_score": confidence_score,
            "user_comment": user_comment
        }

        # Append to JSONL file
        with open(self.feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback, ensure_ascii=False) + "\n")

    def get_corrections(self, limit: int = 100) -> List[Dict]:
        """Get recent corrections for training"""
        corrections = []

        if not self.feedback_file.exists():
            return corrections

        with open(self.feedback_file, "r", encoding="utf-8") as f:
            for line in f:
                corrections.append(json.loads(line))

        return corrections[-limit:]

    def update_few_shot_examples(self):
        """Update FEW_SHOT_EXAMPLES with corrections"""
        corrections = self.get_corrections()

        # Add high-confidence corrections to examples
        for correction in corrections:
            if correction["confidence_score"] < 0.6:  # Was very wrong
                # Add to few-shot examples
                intent = correction["correct_intent"]
                example = (correction["user_input"], intent)

                # Append to appropriate category
                # (Implementation depends on FEW_SHOT_EXAMPLES structure)
                pass
```

```python
# backend/app/api/main_routes.py (ADD endpoint)

@router.post("/feedback/intent")
async def submit_intent_feedback(
    user_input: str,
    predicted_intent: str,
    correct_intent: str,
    confidence_score: float,
    user_comment: str = ""
):
    """Submit feedback on incorrect intent classification"""
    feedback_store = IntentFeedbackStore()
    feedback_store.add_feedback(
        user_input=user_input,
        predicted_intent=predicted_intent,
        correct_intent=correct_intent,
        confidence_score=confidence_score,
        user_comment=user_comment
    )

    # Optionally: Update few-shot examples immediately
    # feedback_store.update_few_shot_examples()

    return {"success": True, "message": "Feedback recorded"}
```

**Frontend:**

```typescript
// Add "Report Wrong Classification" button in UI
<button onClick={() => reportWrongIntent(message, predictedIntent)}>
  🚩 잘못된 분류 신고
</button>
```

**예상 효과:**
- 지속적인 개선 (시간이 지날수록 정확도 상승)
- 사용자 참여도 증가
- Domain-specific 패턴 학습

**구현 난이도:** ⭐⭐ (Medium)

**일정:** 2일

---

### Phase 4: Context-Aware Classification (우선순위: 🟢 LOW)

**현재 문제:**
- 이전 대화 맥락을 intent classification에 활용하지 않음
- "그럼 작성해줘" 같은 context-dependent 입력 처리 불가

**목표:**
- 대화 히스토리를 활용한 맥락 기반 분류
- Context-dependent 표현 이해

**구현 방법:**

```python
# backend/core/supervisor.py

def analyze_request_with_context(
    self,
    request: str,
    conversation_history: List[Dict[str, str]]
) -> dict:
    """Analyze request considering conversation context"""

    # Extract context clues from history
    context_summary = self._summarize_context(conversation_history)

    # Example context patterns:
    # User: "계획도 작성 가능합니까?"
    # Bot: "네, 가능합니다."
    # User: "그럼 작성해줘" ← Context: referring to "계획 작성"

    # Build context-aware prompt
    if conversation_history:
        last_user_msg = conversation_history[-2]["content"] if len(conversation_history) >= 2 else ""
        last_bot_msg = conversation_history[-1]["content"] if conversation_history else ""

        # Detect context-dependent phrases
        context_dependent = self._is_context_dependent(request)

        if context_dependent:
            # Resolve reference from context
            resolved_request = self._resolve_context(request, last_user_msg, last_bot_msg)
            return self.analyze_request(resolved_request)

    return self.analyze_request(request)

def _is_context_dependent(self, request: str) -> bool:
    """Check if request depends on previous context"""
    context_markers = [
        "그럼", "그러면", "그렇다면",  # Korean: "then", "in that case"
        "그거", "그것", "이거", "저거",  # Korean: "that", "this"
        "then", "in that case", "that one", "it"
    ]
    return any(marker in request.lower() for marker in context_markers)

def _resolve_context(
    self,
    request: str,
    prev_user: str,
    prev_bot: str
) -> str:
    """Resolve context-dependent request"""
    # Example:
    # prev_user: "계획도 작성 가능합니까?"
    # prev_bot: "네, 가능합니다."
    # request: "그럼 작성해줘"
    # → resolved: "계획을 작성해줘"

    # Simple heuristic: combine previous user request with current action
    if "그럼" in request and "가능" in prev_user:
        # Extract topic from previous question
        topic = self._extract_topic(prev_user)  # → "계획"
        action = self._extract_action(request)   # → "작성"

        return f"{topic}을 {action}"

    return request
```

**예상 효과:**
- Multi-turn conversation 정확도 향상
- 자연스러운 대화 흐름 지원
- Accuracy: 94% → 95%+

**구현 난이도:** ⭐⭐⭐⭐ (Very High - NLP 복잡)

**일정:** 3-5일

---

### Phase 5: Advanced Techniques (우선순위: 🔵 FUTURE)

**연구 방향:**

1. **Embedding-based Similarity Search**
   - 사용자 입력을 벡터화하여 유사한 예시 검색
   - Tools: OpenAI Embeddings, Sentence-BERT
   - 예상 효과: Few-shot 예시 선택 정확도 향상

2. **Fine-tuned Intent Classifier**
   - BERT/RoBERTa 기반 intent classifier 학습
   - 수집된 feedback 데이터로 fine-tuning
   - 예상 효과: 98%+ accuracy, 낮은 레이턴시

3. **Multi-language Support**
   - 일본어, 중국어, 스페인어 지원
   - 언어별 few-shot 예시 구축
   - 예상 효과: Global 사용자 지원

4. **Confidence Calibration**
   - Confidence score를 실제 정확도와 일치시키기
   - Temperature scaling, Platt scaling
   - 예상 효과: 더 신뢰할 수 있는 confidence score

---

## 구현 우선순위 및 일정

| Phase | 우선순위 | 예상 기간 | 예상 효과 |
|-------|---------|-----------|-----------|
| **Phase 1: Few-Shot Learning** | 🔴 HIGH | 1-2일 | 81.5% → 92% |
| **Phase 2: Confidence & Clarification** | 🟡 MEDIUM | 2-3일 | 92% → 94% |
| **Phase 3: Feedback Loop** | 🟡 MEDIUM | 2일 | 지속적 개선 |
| **Phase 4: Context-Aware** | 🟢 LOW | 3-5일 | 94% → 95%+ |
| **Phase 5: Advanced Techniques** | 🔵 FUTURE | 1-2주 | 95%+ → 98%+ |

**Total Timeline**: 1-2주 (Phase 1-3 완료 시 production-ready)

---

## 성공 지표 (KPIs)

### 정량적 지표
- **Intent Classification Accuracy**: 81.5% → 95%+
- **False Positive Rate** (불필요한 workflow): 18.5% → 5% 이하
- **Clarification Rate**: 애매한 입력 중 사용자 확인 요청 비율 20%+
- **User Correction Rate**: 사용자가 분류 수정한 비율 < 3%

### 정성적 지표
- 사용자 만족도 (인사에 workflow 생성 안함)
- Edge case 처리 능력 (capability question 등)
- Multi-turn conversation 자연스러움

---

## 참고 자료

### Academic Papers
- [Intent Detection in the Age of LLMs (2024)](https://arxiv.org/html/2410.01627v1)
- [IntentGPT: Few-shot Intent Discovery (2024)](https://arxiv.org/html/2411.10670v1)
- [Intent Classification for Bank Chatbots through LLM Fine-Tuning (2024)](https://arxiv.org/html/2410.04925v1)

### Industry Best Practices
- [Hybrid LLM + Intent Classification Approach](https://medium.com/data-science-collective/intent-driven-natural-language-interface-a-hybrid-llm-intent-classification-approach-e1d96ad6f35d)
- [Benchmarking Hybrid LLM Classification Systems](https://www.voiceflow.com/pathways/benchmarking-hybrid-llm-classification-systems)
- [Intent Classification in 2026: What it is & How it Works](https://research.aimultiple.com/intent-classification/)

### Implementation Guides
- [LLM-Powered Chatbots: Practical Guide](https://ranjankumar.in/llm-powered-chatbots-a-practical-guide-to-user-input-classification-and-intent-handling/)
- [Intent Classification: 2025 Techniques for NLP Models](https://labelyourdata.com/articles/machine-learning/intent-classification)

---

## 다음 단계

1. **Phase 1 구현 시작** (Few-Shot Learning)
   - `FEW_SHOT_EXAMPLES` 데이터베이스 구축
   - `_select_relevant_examples()` 구현
   - `_build_few_shot_prompt()` 구현

2. **테스트 케이스 확장**
   - Capability questions 추가
   - Context-dependent 입력 추가
   - Edge cases 추가

3. **Monitoring Dashboard 구축**
   - Intent classification 정확도 추적
   - False positive/negative 추적
   - Confidence score 분포

4. **Documentation 업데이트**
   - API 문서에 clarification flow 추가
   - Frontend 가이드 업데이트

---

**작성자**: Claude (Autonomous Analysis)
**Last Updated**: 2026-01-14
**Status**: 📝 Planning Phase
