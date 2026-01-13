"""
Test Intent Classification - Production Level Validation

This test suite validates that the Supervisor correctly classifies user intents
and only creates workflows when appropriate.

Test Categories:
1. Simple Conversations (should NOT create workflows)
2. Simple Questions (should NOT create workflows)
3. Coding Tasks (should create workflows)
4. Complex Tasks (should create workflows)
5. Edge Cases (mixed intents, unclear requests)

Expected Production-Level Behavior:
- Greetings get direct responses, not Development Plans
- Questions get explanations, not workflows
- Coding requests trigger appropriate workflows
- Intent detection accuracy > 95%
"""

import asyncio
import json
from typing import Dict, List
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.supervisor import SupervisorAgent


class IntentClassificationTester:
    """Test suite for intent classification validation"""

    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0

    def test_cases(self) -> List[Dict]:
        """Define comprehensive test cases"""
        return [
            # ============================================
            # Category 1: Simple Conversations (NO Workflow)
            # ============================================
            {
                "name": "Korean Greeting - 안녕",
                "input": "안녕",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "Korean Greeting - 안녕하세요",
                "input": "안녕하세요",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "English Greeting - Hello",
                "input": "Hello",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "English Greeting - Hi",
                "input": "Hi",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "Korean Thanks",
                "input": "감사합니다",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "English Thanks",
                "input": "Thank you",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "Casual Chat - How are you",
                "input": "How are you?",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },
            {
                "name": "Korean Acknowledgment",
                "input": "네, 알겠어요",
                "expected_intent": "simple_conversation",
                "expected_workflow": False,
                "category": "simple_conversation"
            },

            # ============================================
            # Category 2: Simple Questions (NO Workflow)
            # ============================================
            {
                "name": "What is Python",
                "input": "What is Python?",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "simple_question"
            },
            {
                "name": "Korean Question - 파이썬이 뭐야",
                "input": "파이썬이 뭐야?",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "simple_question"
            },
            {
                "name": "Explain REST API",
                "input": "Explain what REST API is",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "simple_question"
            },
            {
                "name": "Korean Explanation Request",
                "input": "Docker가 뭔지 설명해줘",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "simple_question"
            },
            {
                "name": "Conceptual Question",
                "input": "Tell me about microservices architecture",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "simple_question"
            },
            {
                "name": "What can you do",
                "input": "What can you help me with?",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "simple_question"
            },

            # ============================================
            # Category 3: Coding Tasks (WITH Workflow)
            # ============================================
            {
                "name": "Create Flask Server",
                "input": "Create a Flask server with REST API endpoints",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },
            {
                "name": "Korean - REST API 만들기",
                "input": "REST API를 만들어줘",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },
            {
                "name": "Implement Authentication",
                "input": "Implement JWT authentication for the API",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },
            {
                "name": "Fix Bug",
                "input": "Fix the bug in the user registration endpoint",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },
            {
                "name": "Write Tests",
                "input": "Write unit tests for the authentication module",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },
            {
                "name": "Korean - 코드 리뷰",
                "input": "이 코드를 리뷰해줘",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },
            {
                "name": "Refactor Code",
                "input": "Refactor this function to use async/await",
                "expected_intent": "coding_task",
                "expected_workflow": True,
                "category": "coding_task"
            },

            # ============================================
            # Category 4: Complex Tasks (WITH Workflow)
            # ============================================
            {
                "name": "Design System Architecture",
                "input": "Design a microservices architecture for an e-commerce platform with payment integration",
                "expected_intent": "complex_task",
                "expected_workflow": True,
                "category": "complex_task"
            },
            {
                "name": "Build Full Application",
                "input": "Build a complete web application with React frontend and FastAPI backend",
                "expected_intent": "complex_task",
                "expected_workflow": True,
                "category": "complex_task"
            },
            {
                "name": "Korean - 전체 시스템 구축",
                "input": "사용자 인증, 결제, 알림 기능이 있는 전체 시스템을 구축해줘",
                "expected_intent": "complex_task",
                "expected_workflow": True,
                "category": "complex_task"
            },

            # ============================================
            # Category 5: Edge Cases
            # ============================================
            {
                "name": "Mixed Intent - Greeting + Request",
                "input": "안녕! Python으로 웹서버 만들어줘",
                "expected_intent": "coding_task",  # Should prioritize coding intent
                "expected_workflow": True,
                "category": "edge_case"
            },
            {
                "name": "Unclear Intent",
                "input": "I need help with something",
                "expected_intent": "simple_conversation",  # Too vague, should ask for clarification
                "expected_workflow": False,
                "category": "edge_case"
            },
            {
                "name": "Question About Code (Not Creation)",
                "input": "How does this authentication work?",
                "expected_intent": "simple_question",
                "expected_workflow": False,
                "category": "edge_case"
            }
        ]

    async def run_test(self, test_case: Dict) -> Dict:
        """Run a single test case"""
        print(f"\n{'='*80}")
        print(f"TEST: {test_case['name']}")
        print(f"{'='*80}")
        print(f"Input: {test_case['input']}")
        print(f"Expected Intent: {test_case['expected_intent']}")
        print(f"Expected Workflow: {test_case['expected_workflow']}")
        print(f"Category: {test_case['category']}")
        print(f"-"*80)

        try:
            # Analyze request
            analysis = self.supervisor.analyze_request(test_case['input'])

            # Extract results
            actual_intent = analysis.get('intent', 'unknown')
            actual_workflow = analysis.get('requires_workflow', True)
            direct_response = analysis.get('direct_response', '')

            # Check if test passed
            intent_match = actual_intent == test_case['expected_intent']
            workflow_match = actual_workflow == test_case['expected_workflow']
            passed = intent_match and workflow_match

            # Print results
            print(f"✅ ACTUAL Intent: {actual_intent}" if intent_match else f"❌ ACTUAL Intent: {actual_intent}")
            print(f"✅ ACTUAL Workflow: {actual_workflow}" if workflow_match else f"❌ ACTUAL Workflow: {actual_workflow}")

            if direct_response:
                print(f"\n📝 Direct Response:")
                print(f"   {direct_response[:200]}...")

            if passed:
                print(f"\n✅ TEST PASSED")
                self.passed_tests += 1
            else:
                print(f"\n❌ TEST FAILED")
                self.failed_tests += 1
                if not intent_match:
                    print(f"   Expected intent: {test_case['expected_intent']}, got: {actual_intent}")
                if not workflow_match:
                    print(f"   Expected workflow: {test_case['expected_workflow']}, got: {actual_workflow}")

            return {
                'test_name': test_case['name'],
                'input': test_case['input'],
                'category': test_case['category'],
                'expected_intent': test_case['expected_intent'],
                'actual_intent': actual_intent,
                'expected_workflow': test_case['expected_workflow'],
                'actual_workflow': actual_workflow,
                'passed': passed,
                'direct_response': direct_response[:100] if direct_response else None,
                'full_analysis': analysis
            }

        except Exception as e:
            print(f"\n❌ TEST ERROR: {str(e)}")
            self.failed_tests += 1
            return {
                'test_name': test_case['name'],
                'input': test_case['input'],
                'category': test_case['category'],
                'passed': False,
                'error': str(e)
            }

    async def run_all_tests(self):
        """Run all test cases"""
        print("\n" + "="*80)
        print("INTENT CLASSIFICATION - PRODUCTION LEVEL TEST SUITE")
        print("="*80)

        test_cases = self.test_cases()
        self.total_tests = len(test_cases)

        for test_case in test_cases:
            result = await self.run_test(test_case)
            self.test_results.append(result)

        # Print summary
        self.print_summary()

        # Save results
        self.save_results()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        print(f"\n📊 Overall Results:")
        print(f"   Total Tests: {self.total_tests}")
        print(f"   Passed: {self.passed_tests}")
        print(f"   Failed: {self.failed_tests}")

        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        print(f"   Success Rate: {success_rate:.1f}%")

        # Category breakdown
        print(f"\n📈 Results by Category:")
        categories = {}
        for result in self.test_results:
            category = result.get('category', 'unknown')
            if category not in categories:
                categories[category] = {'total': 0, 'passed': 0}
            categories[category]['total'] += 1
            if result.get('passed', False):
                categories[category]['passed'] += 1

        for category, stats in categories.items():
            cat_success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            print(f"   {category}: {stats['passed']}/{stats['total']} ({cat_success_rate:.1f}%)")

        # Production readiness assessment
        print(f"\n🎯 Production Readiness Assessment:")
        if success_rate >= 95:
            print(f"   ✅ PRODUCTION READY - Intent classification meets production standards (≥95%)")
        elif success_rate >= 85:
            print(f"   ⚠️  NEEDS IMPROVEMENT - Close to production quality (85-95%)")
        else:
            print(f"   ❌ NOT READY - Significant improvements needed (<85%)")

        # Failed tests detail
        if self.failed_tests > 0:
            print(f"\n❌ Failed Tests Detail:")
            for result in self.test_results:
                if not result.get('passed', False):
                    print(f"   - {result['test_name']}")
                    print(f"     Input: {result['input']}")
                    if 'error' in result:
                        print(f"     Error: {result['error']}")
                    else:
                        print(f"     Expected: intent={result.get('expected_intent')}, workflow={result.get('expected_workflow')}")
                        print(f"     Actual: intent={result.get('actual_intent')}, workflow={result.get('actual_workflow')}")

    def save_results(self):
        """Save test results to file"""
        output_file = Path(__file__).parent / "intent_classification_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total_tests': self.total_tests,
                    'passed': self.passed_tests,
                    'failed': self.failed_tests,
                    'success_rate': (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
                },
                'results': self.test_results
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Results saved to: {output_file}")


async def main():
    """Main test runner"""
    tester = IntentClassificationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
