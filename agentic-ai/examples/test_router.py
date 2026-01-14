"""Example script to test Intent Router

This script demonstrates:
1. Loading configuration
2. Creating LLM client with dual endpoints
3. Classifying various prompts
4. Viewing router statistics

Usage:
    python examples/test_router.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_loader import load_config
from core.llm_client import create_llm_client_from_config
from core.router import IntentRouter, WorkflowDomain


# Test prompts for each domain
TEST_PROMPTS = [
    # Coding
    "Fix the authentication bug in login.py",
    "Add unit tests for the user service module",
    "Refactor the database connection code for better performance",

    # Research
    "Research best practices for microservices architecture in 2026",
    "Compare React vs Vue for our next frontend project",
    "Summarize the latest trends in AI model optimization",

    # Data
    "Analyze the sales data in the quarterly_report.csv file",
    "Create a visualization dashboard for customer metrics",
    "Clean and normalize the user database entries",

    # General
    "Organize these project files into a proper directory structure",
    "Create a project plan for the new feature launch",
    "Help me prioritize my todo list for this week",
]


async def main():
    """Main test function"""
    print("=" * 80)
    print("Intent Router Test")
    print("=" * 80)
    print()

    # Load configuration
    print("📋 Loading configuration...")
    try:
        config = load_config("config/config.yaml")
        print(f"✅ Configuration loaded (mode: {config.mode})")
    except FileNotFoundError:
        print("❌ Config file not found. Using default configuration.")
        # Create minimal config for testing
        config_dict = {
            "llm": {
                "model_name": "gpt-oss-120b",
                "endpoints": [
                    {"url": "http://localhost:8001/v1", "name": "primary", "timeout": 120}
                ],
                "health_check": {"interval_seconds": 30},
                "retry": {"max_attempts": 4, "backoff_base": 2}
            }
        }
        from core.llm_client import create_llm_client_from_config
        llm_client = create_llm_client_from_config(config_dict)
    else:
        # Create LLM client from config
        print("🚀 Initializing LLM client...")
        llm_client = create_llm_client_from_config(config.to_dict())
        print(f"✅ LLM client initialized ({len(config.llm.endpoints)} endpoints)")

    # Create intent router
    print("🎯 Initializing Intent Router...")
    router = IntentRouter(llm_client, confidence_threshold=0.7)
    print("✅ Intent Router ready")
    print()

    # Test classification
    print("=" * 80)
    print("Testing Classification")
    print("=" * 80)
    print()

    results = []

    for i, prompt in enumerate(TEST_PROMPTS, 1):
        print(f"[{i}/{len(TEST_PROMPTS)}] Prompt: {prompt[:70]}...")

        try:
            result = await router.classify(prompt)

            # Print result
            print(f"    Domain: {result.domain.value}")
            print(f"    Confidence: {result.confidence:.2%}")
            print(f"    Complexity: {result.estimated_complexity}")
            print(f"    Sub-agents: {'Yes' if result.requires_sub_agents else 'No'}")
            print(f"    Reasoning: {result.reasoning[:100]}...")
            print()

            results.append(result)

        except Exception as e:
            print(f"    ❌ Error: {e}")
            print()

    # Show statistics
    print("=" * 80)
    print("Router Statistics")
    print("=" * 80)
    print()

    stats = router.get_stats()
    print(f"Total Classifications: {stats['total_classifications']}")
    print(f"Confidence Threshold: {stats['confidence_threshold']}")
    print(f"Fallback Enabled: {stats['fallback_enabled']}")
    print()

    print("Domain Distribution:")
    for domain, count in stats['domain_distribution'].items():
        percentage = (count / stats['total_classifications'] * 100) if stats['total_classifications'] > 0 else 0
        print(f"  {domain:12s}: {count:2d} ({percentage:5.1f}%)")
    print()

    # Summary by expected domain
    print("=" * 80)
    print("Classification Summary")
    print("=" * 80)
    print()

    expected_domains = [
        WorkflowDomain.CODING, WorkflowDomain.CODING, WorkflowDomain.CODING,
        WorkflowDomain.RESEARCH, WorkflowDomain.RESEARCH, WorkflowDomain.RESEARCH,
        WorkflowDomain.DATA, WorkflowDomain.DATA, WorkflowDomain.DATA,
        WorkflowDomain.GENERAL, WorkflowDomain.GENERAL, WorkflowDomain.GENERAL,
    ]

    correct = 0
    for i, (prompt, result, expected) in enumerate(zip(TEST_PROMPTS, results, expected_domains)):
        is_correct = result.domain == expected
        if is_correct:
            correct += 1

        status = "✅" if is_correct else "❌"
        print(f"{status} {prompt[:60]:60s} | {expected.value:10s} → {result.domain.value:10s}")

    accuracy = (correct / len(results) * 100) if results else 0
    print()
    print(f"Accuracy: {correct}/{len(results)} ({accuracy:.1f}%)")
    print()

    # Close connections
    print("🔌 Closing connections...")
    await llm_client.close()
    print("✅ Done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
