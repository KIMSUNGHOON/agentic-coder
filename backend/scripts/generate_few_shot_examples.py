#!/usr/bin/env python3
"""LLM을 활용한 Few-Shot 예시 자동 생성

사용자가 직접 예시를 입력할 필요 없이, LLM이 다양한 intent 예시를 자동 생성합니다.

Usage:
    python scripts/generate_few_shot_examples.py

Output:
    data/few_shot_examples.json
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_client import LLMClient


class FewShotExampleGenerator:
    """LLM을 사용하여 intent classification 예시 자동 생성"""

    def __init__(self):
        self.llm = LLMClient()
        self.output_file = Path(__file__).parent.parent / "data" / "few_shot_examples.json"

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

        try:
            # Use synchronous API for simplicity
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.8,  # 다양성을 위해 높은 temperature
                max_tokens=2000
            )

            # Parse LLM response
            examples = self._parse_llm_response(response)

            return examples

        except Exception as e:
            print(f"❌ Error generating examples for {intent_category}: {e}")
            return []

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
Greetings, thanks, acknowledgments, casual conversation that should be answered directly without creating workflows.

Good Examples:
- "안녕하세요" → simple greeting
- "Hello" → simple greeting
- "감사합니다" → thank you
- "Thank you" → thank you
- "오늘 기분 어때?" → casual conversation
- "How are you?" → casual conversation
- "알겠습니다" → acknowledgment
- "Okay, got it" → acknowledgment

Include variations in:
- Formality (formal vs casual)
- Length (1 word to 10 words)
- Context (greeting, thanks, farewell, acknowledgment)
            """,

            "capability_question": """
Questions asking WHETHER the system CAN do something, not asking it TO DO it.
These are questions ABOUT capabilities, not requests for action.

Good Examples:
- "계획도 작성 가능합니까?" → asking if capable
- "Can you write plans?" → asking if capable
- "코드 리뷰 할 수 있어?" → asking if capable
- "Are you able to debug?" → asking if capable
- "Python 지원하나요?" → asking if supported
- "Do you support Python?" → asking if supported

Key Markers:
- Korean: "가능합니까", "할 수 있어", "지원하나", "되나요"
- English: "can you", "are you able", "do you support", "is it possible"

Include variations in:
- Formality ("가능합니까" vs "가능해")
- Topic (planning, coding, reviewing, testing, debugging)
            """,

            "simple_question": """
Questions seeking information or explanation, not asking for code generation or workflow.
Information-seeking questions that should be answered directly.

Good Examples:
- "Python이 뭐야?" → what is X
- "What is Python?" → what is X
- "REST API 설명해줘" → explain concept
- "Explain REST API" → explain concept
- "Docker와 VM의 차이점은?" → compare concepts
- "What's the difference between Docker and VM?" → compare concepts
- "왜 TypeScript를 써?" → why question
- "Why use TypeScript?" → why question

Include variations in:
- Topic (languages, frameworks, concepts, tools)
- Question type (what, why, how, difference, comparison)
- Depth (simple to complex topics)
            """,

            "coding_task": """
Actual requests to CREATE, MODIFY, or REVIEW code.
These require workflow creation and code generation.

Good Examples:
- "REST API를 만들어줘" → create code
- "Create a REST API" → create code
- "이 코드 리뷰해줘" → review code
- "Review this code" → review code
- "Flask 서버 만들어줘" → create server
- "Write a Flask server" → create server
- "버그를 고쳐줘" → fix bug
- "Fix this bug" → fix bug

Key Action Verbs:
- Korean: "만들어줘", "작성해줘", "구현해줘", "리뷰해줘", "고쳐줘"
- English: "create", "make", "write", "implement", "review", "fix"

Include variations in:
- Task type (create, review, debug, refactor, test)
- Technology (Python, JavaScript, Go, React, Flask, etc.)
- Complexity (single function to full module)
            """,

            "complex_task": """
Large-scale projects, full system design, or multi-step planning requests.
These require comprehensive planning and multiple agents.

Good Examples:
- "전체 웹 애플리케이션 구축해줘" → full application
- "Build a complete web application" → full application
- "E-commerce 시스템 만들어줘" → complete system
- "Create an e-commerce system" → complete system
- "프로젝트 계획을 작성해줘" → project planning
- "Write a project plan" → project planning
- "마이크로서비스 아키텍처 설계해줘" → architecture design
- "Design a microservices architecture" → architecture design

Key Characteristics:
- Multiple components/modules
- System-level scope
- Planning/design focus
- Enterprise-level complexity

Include variations in:
- Scale (small system to enterprise)
- Domain (web, mobile, backend, DevOps)
- Focus (architecture, planning, implementation)
            """
        }

        guideline = guidelines.get(intent_category, "")
        lang_str = ", ".join(languages)

        return f"""You are a data generator for intent classification training.

Generate {count} diverse examples of user inputs that should be classified as "{intent_category}".

**Guidelines:**
{guideline}

**Requirements:**
1. Generate examples in these languages: {lang_str}
2. Make them DIVERSE:
   - Different lengths (short to long)
   - Different styles (formal to casual)
   - Different topics (if applicable)
   - Edge cases and boundary examples
3. For each language, distribute examples evenly (~{count//len(languages)} per language)
4. Each example must be realistic - something a real user would type
5. NO duplicates or near-duplicates

**Output Format (JSON ONLY, no markdown):**
[
  {{"input": "안녕하세요", "intent": "{intent_category}", "language": "korean"}},
  {{"input": "Hello", "intent": "{intent_category}", "language": "english"}},
  ...
]

Generate EXACTLY {count} examples. Output ONLY the JSON array, no explanation or markdown."""

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """LLM 응답에서 JSON 파싱"""
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith('```'):
                # Remove ```json and ``` markers
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response

            # Extract JSON array
            json_start = response.find('[')
            json_end = response.rfind(']') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON array found in response")

            json_str = response[json_start:json_end]
            examples = json.loads(json_str)

            # Validate structure
            for ex in examples:
                if 'input' not in ex or 'intent' not in ex:
                    raise ValueError(f"Invalid example structure: {ex}")

            return examples

        except Exception as e:
            print(f"❌ Failed to parse LLM response: {e}")
            print(f"Response preview: {response[:500]}")
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
            print(f"\n🤖 Generating examples for: {category}...")
            examples = await self.generate_examples(
                intent_category=category,
                count=50,  # 각 카테고리당 50개
                languages=["korean", "english"]
            )

            if examples:
                all_examples[category] = examples
                print(f"   ✅ Generated {len(examples)} examples")

                # Show first 3 examples
                for i, ex in enumerate(examples[:3]):
                    print(f"      {i+1}. [{ex['language']}] {ex['input']}")
            else:
                print(f"   ⚠️ No examples generated (check LLM response)")

        # Save to file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(all_examples, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Saved all examples to: {self.output_file}")
        print(f"   Total examples: {sum(len(v) for v in all_examples.values())}")

        return all_examples


async def main():
    """Generate few-shot examples"""
    print("=" * 80)
    print("Few-Shot Example Generator")
    print("=" * 80)

    generator = FewShotExampleGenerator()

    # Generate examples for all categories
    examples = await generator.generate_all_categories()

    # Print final summary
    print("\n" + "=" * 80)
    print("📊 Generation Summary:")
    print("=" * 80)

    total = 0
    for category, items in examples.items():
        count = len(items)
        total += count

        # Count by language
        lang_counts = {}
        for item in items:
            lang = item.get('language', 'unknown')
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        lang_str = ", ".join([f"{k}: {v}" for k, v in lang_counts.items()])

        print(f"   {category:25} {count:3} examples  ({lang_str})")

    print(f"\n   {'TOTAL':25} {total:3} examples")

    print("\n✨ Next steps:")
    print("   1. Review generated examples:")
    print(f"      cat {generator.output_file}")
    print("   2. Validate quality:")
    print("      python scripts/validate_examples.py")
    print("   3. Use in Supervisor:")
    print("      # Automatically loaded from data/few_shot_examples.json")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
