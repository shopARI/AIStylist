"""
Test runner for CrewAI migration tools
Runs all tests and provides summary.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_all_tests():
    """Run all test suites."""
    print("\n" + "=" * 80)
    print("CREWAI MIGRATION TEST SUITE")
    print("=" * 80)

    success_count = 0
    fail_count = 0

    # Test Neo4j tools
    print("\n" + "=" * 80)
    print("TESTING NEO4J TOOLS")
    print("=" * 80)
    try:
        from test_neo4j_tools import TestNeo4jConnection, TestSemanticExpansion, TestFulltextSearch

        test_suites = [
            ("Neo4j Connection", TestNeo4jConnection()),
            ("Semantic Expansion", TestSemanticExpansion()),
            ("Fulltext Search", TestFulltextSearch())
        ]

        for suite_name, suite in test_suites:
            print(f"\n{suite_name} Tests:")
            print("-" * 60)
            try:
                for method_name in dir(suite):
                    if method_name.startswith('test_'):
                        try:
                            method = getattr(suite, method_name)
                            print(f"\n  {method_name}...")
                            method()
                            print(f"   PASSED")
                            success_count += 1
                        except Exception as e:
                            print(f"   FAILED: {e}")
                            fail_count += 1
            except Exception as e:
                print(f"Suite failed: {e}")
                fail_count += 1

    except Exception as e:
        print(f"Failed to run Neo4j tests: {e}")
        fail_count += 1

    # Test Qdrant tools
    print("\n" + "=" * 80)
    print("TESTING QDRANT TOOLS")
    print("=" * 80)
    try:
        from test_qdrant_tools import TestQdrantConnection, TestEmbeddingGeneration, TestQdrantSearch

        test_suites = [
            ("Qdrant Connection", TestQdrantConnection()),
            ("Embedding Generation", TestEmbeddingGeneration()),
            ("Qdrant Search", TestQdrantSearch())
        ]

        for suite_name, suite in test_suites:
            print(f"\n{suite_name} Tests:")
            print("-" * 60)
            try:
                for method_name in dir(suite):
                    if method_name.startswith('test_'):
                        try:
                            method = getattr(suite, method_name)
                            print(f"\n  {method_name}...")
                            method()
                            print(f"   PASSED")
                            success_count += 1
                        except Exception as e:
                            print(f"   FAILED: {e}")
                            fail_count += 1
            except Exception as e:
                print(f"Suite failed: {e}")
                fail_count += 1

    except Exception as e:
        print(f"Failed to run Qdrant tests: {e}")
        fail_count += 1

    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = success_count + fail_count
    print(f"Total tests run: {total}")
    print(f"Passed: {success_count}")
    print(f"Failed: {fail_count}")

    if fail_count == 0:
        print("\n ALL TESTS PASSED!")
    else:
        print(f"\n {fail_count} TESTS FAILED")

    print("=" * 80)

    return fail_count == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
