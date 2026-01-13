"""Debug specific failing test cases"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.supervisor import SupervisorAgent


def debug_case(input_text: str):
    """Debug a specific case"""
    print(f"\n{'='*80}")
    print(f"Input: {input_text}")
    print(f"{'='*80}")

    supervisor = SupervisorAgent()
    analysis = supervisor.analyze_request(input_text)

    print(f"Intent: {analysis.get('intent')}")
    print(f"Requires Workflow: {analysis.get('requires_workflow')}")
    print(f"Response Type: {analysis.get('response_type')}")
    print(f"Direct Response: {analysis.get('direct_response', 'N/A')[:100]}")
    print(f"API Used: {analysis.get('api_used')}")

    # Debug internal methods
    request_lower = input_text.lower().strip()
    print(f"\nDebug Info:")
    print(f"  _is_quick_qa_request: {supervisor._is_quick_qa_request(request_lower)}")
    print(f"  _has_code_intent: {supervisor._has_code_intent(request_lower)}")
    print(f"  _determine_response_type: {supervisor._determine_response_type(input_text)}")


if __name__ == "__main__":
    # Test failing cases
    debug_case("Thank you")
    debug_case("Explain what REST API is")
    debug_case("Tell me about microservices architecture")
