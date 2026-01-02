"""
Example: Querying X-Ray Traces

This demonstrates how to query the X-Ray API to analyze pipeline runs.

Prerequisites:
1. X-Ray API must be running (python run_api.py)
2. At least one pipeline run must exist (python examples/competitor_selection.py)
"""

import sys
import os
from pprint import pprint

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from xray_sdk import XRayClient


def main():
    # Initialize client
    client = XRayClient(api_url="http://localhost:8000")

    print("=" * 70)
    print("X-Ray Query Examples")
    print("=" * 70)

    # Example 1: List recent runs
    print("\n1. Recent competitor_selection runs:")
    print("-" * 70)
    try:
        results = client.query_runs(
            pipeline_name="competitor_selection",
            limit=5
        )

        if results.get('items'):
            for run in results['items']:
                status = "✓" if run['success'] else "✗"
                print(f"{status} Run {run['run_id'][:8]}... | "
                      f"Duration: {run.get('total_duration_ms', 0):.0f}ms | "
                      f"Steps: {run['step_count']}")
        else:
            print("No runs found. Run 'python examples/competitor_selection.py' first.")
    except Exception as e:
        print(f"Error: {e}")
        print("\nIs the API running? Start it with: python run_api.py")
        return

    # Example 2: Get detailed trace for first run
    if results.get('items'):
        print("\n2. Detailed trace for the first run:")
        print("-" * 70)
        run_id = results['items'][0]['run_id']

        try:
            run_detail = client.get_run(run_id)

            print(f"Pipeline: {run_detail['pipeline_name']}")
            print(f"Started: {run_detail['started_at']}")
            print(f"Success: {run_detail['success']}")
            print(f"\nSteps ({len(run_detail['steps'])}):")

            for i, step in enumerate(run_detail['steps'], 1):
                print(f"\n  {i}. {step['step_name']} ({step['step_type']})")
                print(f"     Duration: {step.get('duration_ms', 0):.0f}ms")

                # Show candidate flow
                input_count = len(step.get('input_candidates', []))
                output_count = len(step.get('output_candidates', []))
                if input_count > 0 or output_count > 0:
                    reduction = ((input_count - output_count) / input_count * 100) if input_count > 0 else 0
                    print(f"     Candidates: {input_count} → {output_count} ({reduction:.0f}% reduction)")

                # Show key decisions
                decisions = step.get('decisions', [])
                if decisions:
                    print(f"     Decisions: {len(decisions)} recorded")
                    # Show first decision as example
                    if len(decisions) > 0:
                        first_decision = decisions[0]
                        print(f"       └─ {first_decision['action']}: {first_decision['reason']}")

            # Show final output
            if run_detail.get('final_output'):
                print("\n  Final Output:")
                competitor = run_detail['final_output'].get('competitor_product')
                if competitor:
                    print(f"    Selected: {competitor.get('title', 'N/A')}")
                    print(f"    Price: ${competitor.get('price', 0)}")
                    print(f"    Category: {competitor.get('category', 'N/A')}")

        except Exception as e:
            print(f"Error fetching run details: {e}")

    # Example 3: Find aggressive filter steps across all runs
    print("\n3. Filter steps that eliminated >80% of candidates:")
    print("-" * 70)

    try:
        # This is a cross-pipeline query - works across different pipeline types
        import httpx
        response = httpx.get(
            "http://localhost:8000/api/steps",
            params={
                "step_type": "filter",
                "min_reduction_rate": 0.8,
                "limit": 10
            },
            timeout=5.0
        )

        if response.status_code == 200:
            data = response.json()
            if data.get('items'):
                for step in data['items']:
                    reduction_pct = step['reduction_rate'] * 100
                    print(f"  • {step['step_name']}: "
                          f"{step['input_count']} → {step['output_count']} "
                          f"({reduction_pct:.0f}% eliminated)")
            else:
                print("  No filter steps found with >80% reduction rate.")
        else:
            print(f"  Error: HTTP {response.status_code}")

    except Exception as e:
        print(f"  Error: {e}")

    # Example 4: Step performance analytics
    print("\n4. Performance analytics for competitor_selection:")
    print("-" * 70)

    try:
        import httpx
        response = httpx.get(
            "http://localhost:8000/api/analytics/step-performance",
            params={"pipeline_name": "competitor_selection"},
            timeout=5.0
        )

        if response.status_code == 200:
            data = response.json()
            analytics = data.get('analytics', [])

            if analytics:
                print(f"\n{'Step Name':<25} {'Type':<12} {'Avg Duration':<15} {'Avg Reduction':<15}")
                print("-" * 70)

                for item in analytics:
                    print(f"{item['step_name']:<25} "
                          f"{item['step_type']:<12} "
                          f"{item['avg_duration_ms']:>10.0f}ms     "
                          f"{item['avg_reduction_rate']*100:>10.1f}%")
            else:
                print("  No analytics available yet.")

    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 70)
    print("Query examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
