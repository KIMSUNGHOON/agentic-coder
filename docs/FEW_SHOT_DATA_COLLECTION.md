# Few-Shot 예시 데이터 수집 전략

**문제**: Phase 1 구현에 수백 개의 예시가 필요하지만, 사용자가 직접 입력하기에는 한계가 있음

**해결책**: 자동화된 데이터 수집 및 생성 방법 활용

---

## 방법 1: LLM을 활용한 Synthetic 데이터 생성 (⭐ 추천)

### 장점
- ✅ **즉시 시작 가능** (기존 LLM 활용)
- ✅ **사용자 부담 없음** (자동 생성)
- ✅ **다양성 확보** (여러 패턴, 언어)
- ✅ **비용 효율적** (한 번만 생성)

### 구현 방법

```python
# backend/scripts/generate_few_shot_examples.py

import asyncio
import json
from typing import List, Dict
from pathlib import Path

from core.llm_client import LLMClient

class FewShotExampleGenerator:
    """LLM을 사용하여 intent classification 예시 자동 생성"""

    def __init__(self):
        self.llm = LLMClient()
        self.output_file = Path("data/few_shot_examples.json")

    async def generate_examples(
        self,
        intent_category: str,
        count: int = 50,
        languages: List[str] = ["korean", "english"]
    ) -> List[Dict]:
        """특정 intent에 대한 예시 생성

        Args:
            intent_category: "simple_conversation", "capability_question", etc.
            count: 생성할 예시 개수
            languages: 생성할 언어 목록

        Returns:
            List of {"input": "...", "intent": "...", "language": "..."}
        """

        prompt = self._build_generation_prompt(intent_category, count, languages)

        response = await self.llm.generate_async(
            prompt=prompt,
            temperature=0.8,  # 다양성을 위해 높은 temperature
            max_tokens=2000
        )

        # Parse LLM response
        examples = self._parse_llm_response(response)

        return examples

    def _build_generation_prompt(
        self,
        intent_category: str,
        count: int,
        languages: List[str]
    ) -> str:
        """예시 생성 프롬프트 구성"""

        # Intent별 가이드라인
        guidelines = {
            "simple_conversation": """
Greetings, thanks, acknowledgments that should be answered directly without creating workflows.
Examples:
- "안녕하세요"
- "Hello"
- "감사합니다"
- "Thank you"
            """,
            "capability_question": """
Questions asking WHETHER the system CAN do something, not asking it TO DO it.
Examples:
- "계획도 작성 가능합니까?" (Can you write plans?)
- "코드 리뷰 할 수 있어?" (Can you do code review?)
- "Are you able to debug?"
- "Do you support testing?"
            """,
            "simple_question": """
Questions seeking information or explanation, not asking for code generation.
Examples:
- "Python이 뭐야?" (What is Python?)
- "REST API 설명해줘" (Explain REST API)
- "What is Docker?"
- "Tell me about microservices"
            """,
            "coding_task": """
Actual requests to CREATE, MODIFY, or REVIEW code.
Examples:
- "REST API를 만들어줘" (Create a REST API)
- "이 코드 리뷰해줘" (Review this code)
- "Write a Flask server"
- "Fix this bug"
            """,
            "complex_task": """
Large-scale projects or planning requests.
Examples:
- "전체 웹 애플리케이션 구축해줘" (Build a full web app)
- "프로젝트 계획을 작성해줘" (Write a project plan)
- "Design a microservices architecture"
- "Create a complete e-commerce system"
            """
        }

        guideline = guidelines.get(intent_category, "")
        lang_str = ", ".join(languages)

        return f"""Generate {count} diverse examples of user inputs that should be classified as "{intent_category}".

**Guidelines:**
{guideline}

**Requirements:**
1. Generate examples in these languages: {lang_str}
2. Make them DIVERSE (different lengths, styles, formality levels)
3. Include edge cases and boundary examples
4. For each language, distribute examples evenly

**Output Format (JSON):**
[
  {{"input": "안녕하세요", "intent": "{intent_category}", "language": "korean"}},
  {{"input": "Hello", "intent": "{intent_category}", "language": "english"}},
  ...
]

Generate ONLY the JSON array, no additional text."""

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """LLM 응답에서 JSON 파싱"""
        try:
            # Extract JSON from response (may have markdown code blocks)
            json_start = response.find('[')
            json_end = response.rfind(']') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in response")

            json_str = response[json_start:json_end]
            examples = json.loads(json_str)

            return examples

        except Exception as e:
            print(f"Failed to parse LLM response: {e}")
            print(f"Response: {response[:500]}")
            return []

    async def generate_all_categories(self) -> Dict[str, List[Dict]]:
        """모든 intent category에 대한 예시 생성"""

        categories = [
            "simple_conversation",
            "capability_question",
            "simple_question",
            "coding_task",
            "complex_task"
        ]

        all_examples = {}

        for category in categories:
            print(f"Generating examples for: {category}...")
            examples = await self.generate_examples(
                intent_category=category,
                count=50,  # 각 카테고리당 50개
                languages=["korean", "english"]
            )
            all_examples[category] = examples
            print(f"  Generated {len(examples)} examples")

        # Save to file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(all_examples, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Saved all examples to: {self.output_file}")
        print(f"   Total examples: {sum(len(v) for v in all_examples.values())}")

        return all_examples


async def main():
    """Generate few-shot examples"""
    generator = FewShotExampleGenerator()

    # Generate examples for all categories
    examples = await generator.generate_all_categories()

    # Print summary
    print("\n📊 Summary:")
    for category, items in examples.items():
        print(f"   {category}: {len(items)} examples")
        # Show first example
        if items:
            print(f"      Example: {items[0]['input']}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 실행 방법

```bash
# 1. 예시 생성 (한 번만)
cd backend
python scripts/generate_few_shot_examples.py

# 출력 예시:
# Generating examples for: simple_conversation...
#   Generated 50 examples
# Generating examples for: capability_question...
#   Generated 50 examples
# ...
# ✅ Saved all examples to: data/few_shot_examples.json
#    Total examples: 250

# 2. Supervisor에서 로드
# backend/core/supervisor.py에서 자동 로드
```

### 생성 품질 검증

```python
# backend/scripts/validate_examples.py

import json
from pathlib import Path
from core.supervisor import SupervisorAgent

def validate_generated_examples():
    """생성된 예시의 품질 검증"""

    # Load generated examples
    examples_file = Path("data/few_shot_examples.json")
    with open(examples_file, 'r', encoding='utf-8') as f:
        all_examples = json.load(f)

    supervisor = SupervisorAgent()

    total = 0
    correct = 0

    for expected_intent, examples in all_examples.items():
        for example in examples:
            user_input = example['input']

            # Classify with supervisor
            analysis = supervisor.analyze_request(user_input)
            predicted_intent = analysis.get('intent')

            total += 1
            if predicted_intent == expected_intent:
                correct += 1
            else:
                print(f"❌ MISMATCH:")
                print(f"   Input: {user_input}")
                print(f"   Expected: {expected_intent}")
                print(f"   Predicted: {predicted_intent}")

    accuracy = correct / total * 100
    print(f"\n✅ Validation Result: {correct}/{total} ({accuracy:.1f}%)")

    return accuracy

if __name__ == "__main__":
    validate_generated_examples()
```

---

## 방법 2: 현재 시스템 로그 분석 (점진적 수집)

### 장점
- ✅ **실제 사용자 입력** (realistic data)
- ✅ **자동 수집** (사용자 행동 기반)
- ✅ **무료** (이미 있는 데이터)

### 구현 방법

```python
# backend/scripts/collect_from_logs.py

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

from app.db import get_db
from app.db.repository import ConversationRepository

class LogBasedExampleCollector:
    """실제 사용 로그에서 예시 수집"""

    def __init__(self):
        self.db = next(get_db())
        self.repo = ConversationRepository(self.db)

    def collect_examples(
        self,
        days: int = 30,
        min_confidence: float = 0.8
    ) -> Dict[str, List[Dict]]:
        """최근 N일간의 로그에서 예시 수집

        Args:
            days: 수집 기간
            min_confidence: 최소 confidence (높을수록 정확한 예시)

        Returns:
            Dict of {intent: [examples]}
        """

        # Get recent conversations
        since = datetime.now() - timedelta(days=days)
        conversations = self.repo.list_conversations(limit=1000)

        examples_by_intent = {}

        for conv in conversations:
            if conv.created_at < since:
                continue

            # Get messages with metadata
            messages = self.repo.get_messages(conv.session_id)

            for msg in messages:
                if msg.role != 'user':
                    continue

                # Check if we have intent classification metadata
                meta = msg.meta_info or {}
                intent = meta.get('intent')
                confidence = meta.get('confidence_score', 0)

                if not intent or confidence < min_confidence:
                    continue

                # Add to examples
                if intent not in examples_by_intent:
                    examples_by_intent[intent] = []

                examples_by_intent[intent].append({
                    'input': msg.content,
                    'intent': intent,
                    'confidence': confidence,
                    'timestamp': msg.created_at.isoformat()
                })

        # Remove duplicates and sort by confidence
        for intent in examples_by_intent:
            # Deduplicate
            seen = set()
            unique = []
            for ex in examples_by_intent[intent]:
                if ex['input'] not in seen:
                    seen.add(ex['input'])
                    unique.append(ex)

            # Sort by confidence
            unique.sort(key=lambda x: x['confidence'], reverse=True)

            # Keep top 100
            examples_by_intent[intent] = unique[:100]

        return examples_by_intent

    def save_examples(self, examples: Dict, output_file: str = "data/log_based_examples.json"):
        """Save collected examples"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(examples, f, ensure_ascii=False, indent=2)

        print(f"✅ Saved {sum(len(v) for v in examples.values())} examples to {output_path}")

def main():
    collector = LogBasedExampleCollector()

    # Collect from last 30 days
    examples = collector.collect_examples(days=30, min_confidence=0.8)

    # Print summary
    print("📊 Collected Examples:")
    for intent, items in examples.items():
        print(f"   {intent}: {len(items)} examples")

    # Save
    collector.save_examples(examples)

if __name__ == "__main__":
    main()
```

---

## 방법 3: 공개 데이터셋 활용 + 번역

### 데이터셋 소스
1. **ATIS (Airline Travel Information System)** - Intent classification benchmark
2. **SNIPS** - Intent detection dataset (7 intents)
3. **Banking77** - Banking domain intents
4. **HWU64** - 64 intents across 21 domains

### 구현 방법

```python
# backend/scripts/import_public_datasets.py

import requests
import json
from typing import List, Dict

class PublicDatasetImporter:
    """공개 데이터셋 가져오기"""

    # Intent mapping (public dataset → our intents)
    INTENT_MAPPING = {
        # SNIPS intents
        "GetWeather": "simple_question",
        "BookRestaurant": "coding_task",
        "PlayMusic": "coding_task",
        "AddToPlaylist": "coding_task",
        "RateBook": "simple_question",
        "SearchScreeningEvent": "simple_question",
        "SearchCreativeWork": "simple_question",

        # Banking77 examples
        "balance": "simple_question",
        "transfer": "coding_task",
        "card_issues": "simple_question",
        # ... (map all 77 intents)
    }

    def download_snips_dataset(self) -> List[Dict]:
        """Download SNIPS dataset"""
        # SNIPS is available on GitHub
        url = "https://github.com/snipsco/nlu-benchmark/raw/master/2017-06-custom-intent-engines/..."

        # ... (download and parse)
        pass

    def translate_to_korean(self, text: str) -> str:
        """영어 예시를 한국어로 번역"""
        # Use translation API or LLM
        # For now, use LLM
        prompt = f"Translate this to natural Korean:\n{text}\n\nKorean:"
        # ... call LLM
        pass
```

---

## 방법 4: 점진적 수집 (Incremental Collection)

### 자동 예시 수집 시스템

```python
# backend/core/example_collector.py

from typing import Dict
from datetime import datetime
import json
from pathlib import Path

class IncrementalExampleCollector:
    """사용자 사용 중 자동으로 예시 수집"""

    def __init__(self, output_file: str = "data/incremental_examples.jsonl"):
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

    def record_classification(
        self,
        user_input: str,
        predicted_intent: str,
        confidence: float,
        was_correct: bool = None  # User feedback으로 확인
    ):
        """분류 결과 기록"""

        # Only record high-confidence classifications
        if confidence < 0.85:
            return

        record = {
            'timestamp': datetime.utcnow().isoformat(),
            'input': user_input,
            'intent': predicted_intent,
            'confidence': confidence,
            'verified': was_correct
        }

        # Append to JSONL file
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def get_collected_examples(self, min_count: int = 100) -> Dict:
        """수집된 예시를 few-shot format으로 변환"""

        if not self.output_file.exists():
            return {}

        examples_by_intent = {}

        with open(self.output_file, 'r', encoding='utf-8') as f:
            for line in f:
                record = json.loads(line)

                # Skip unverified low-confidence
                if record.get('verified') is False:
                    continue

                intent = record['intent']
                if intent not in examples_by_intent:
                    examples_by_intent[intent] = []

                examples_by_intent[intent].append({
                    'input': record['input'],
                    'intent': intent,
                    'confidence': record['confidence']
                })

        # Filter: only return if we have enough examples
        filtered = {}
        for intent, examples in examples_by_intent.items():
            if len(examples) >= min_count:
                # Sort by confidence and take top N
                examples.sort(key=lambda x: x['confidence'], reverse=True)
                filtered[intent] = examples[:200]

        return filtered
```

### Supervisor에 통합

```python
# backend/core/supervisor.py

from core.example_collector import IncrementalExampleCollector

class SupervisorAgent:
    def __init__(self):
        # ...
        self.example_collector = IncrementalExampleCollector()

    def analyze_request(self, request: str, context: Optional[List] = None) -> dict:
        """Analyze with example collection"""

        analysis = self._perform_analysis(request, context)

        # Record this classification
        self.example_collector.record_classification(
            user_input=request,
            predicted_intent=analysis['intent'],
            confidence=analysis['confidence_score']
        )

        return analysis
```

---

## 권장 전략: Hybrid Approach

**Phase 1 (Day 1):** LLM으로 초기 예시 생성 (250개)
```bash
python scripts/generate_few_shot_examples.py
```

**Phase 2 (Day 2-7):** 실제 사용하면서 점진적 수집
- 자동으로 high-confidence 분류 기록
- 사용자 피드백 수집

**Phase 3 (Week 2+):** 로그 분석으로 보강
```bash
python scripts/collect_from_logs.py
```

**Phase 4 (Long-term):** 공개 데이터셋으로 다양성 추가
- 특정 도메인이 부족할 때
- 특정 언어가 부족할 때

---

## 데이터 품질 관리

### 자동 검증

```python
def validate_example_quality(examples: List[Dict]) -> float:
    """예시 품질 자동 검증"""
    supervisor = SupervisorAgent()

    correct = 0
    total = len(examples)

    for ex in examples:
        predicted = supervisor.analyze_request(ex['input'])
        if predicted['intent'] == ex['intent']:
            correct += 1

    return correct / total
```

### 주기적 리뷰

```python
# 매주 실행
python scripts/review_examples.py

# Output:
# 📊 Example Quality Report:
#    simple_conversation: 95% accuracy (50 examples)
#    capability_question: 88% accuracy (45 examples)
#    ⚠️ coding_task: 72% accuracy (need review!)
```

---

## 요약

| 방법 | 즉시 시작 | 품질 | 비용 | 추천 |
|------|----------|------|------|------|
| 🤖 **LLM 생성** | ✅ | 중-고 | 낮음 | ⭐⭐⭐⭐⭐ |
| 📊 **로그 분석** | ⚠️ (데이터 필요) | 최고 | 무료 | ⭐⭐⭐⭐ |
| 🌐 **공개 데이터셋** | ✅ | 중 | 무료 | ⭐⭐⭐ |
| 📈 **점진적 수집** | ⚠️ (시간 필요) | 최고 | 무료 | ⭐⭐⭐⭐⭐ |

**최적 전략**: LLM 생성으로 시작 → 점진적 수집으로 개선

이 방법으로 사용자 부담 없이 고품질 예시를 확보할 수 있습니다!
