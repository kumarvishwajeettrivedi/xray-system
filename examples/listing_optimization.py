"""
Example: Listing Optimization Pipeline with X-Ray Instrumentation

Scenario B from Assignment:
Given an existing product listing, generate an optimized version.

Steps:
1. Analyze current listing (LLM)
2. Extract high-performing patterns from competitors (Retrieval)
3. Generate improved content variations (LLM)
4. Score and select the best version (Score)
"""

import sys
import os
import random
import time
from typing import List, Dict, Any

# Add parent directory to path to import xray_sdk
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from xray_sdk import XRayTracer, Candidate

def analyze_listing(listing: Dict[str, str]) -> Dict[str, Any]:
    """Simulate analyzing listing quality"""
    time.sleep(random.uniform(0.1, 0.3))
    issues = []
    if len(listing['title']) < 50:
        issues.append("Title too short")
    if "features" not in listing['description'].lower():
        issues.append("Missing feature list")
    
    return {
        "score": random.randint(40, 80),
        "issues": issues,
        "sentiment": random.choice(["neutral", "positive", "salesy"])
    }

def find_competitor_patterns(category: str) -> List[str]:
    """Simulate retrieving patterns"""
    return [
        "Use power words in title",
        "Bullet points with emojis",
        "Mention warranty in first line"
    ]

def generate_variations(listing: Dict[str, str], patterns: List[str]) -> List[Dict[str, str]]:
    """Simulate generating variations"""
    variations = []
    for i in range(3):
        variations.append({
            "id": f"VAR-{i+1}",
            "title": f"New Title {i+1}: {listing['title']} (Optimized)",
            "description": f"Improved description with pattern: {patterns[i % len(patterns)]}",
            "tone": random.choice(["Professional", "Exciting", "Urgent"])
        })
    return variations

def score_variations(variations: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Simulate scoring variations"""
    scored = []
    for var in variations:
        score = random.uniform(0.7, 0.98)
        scored.append({
            "variation": var,
            "score": score,
            "reason": f"High engagement potential ({score:.2f})"
        })
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored

def optimize_listing(listing: Dict[str, str], api_url: str = "http://localhost:8000"):
    tracer = XRayTracer(
        pipeline_name="listing_optimization",
        pipeline_version="1.5.0",
        api_url=api_url,
        fail_silently=True
    )

    context = {"listing_id": listing['id'], "category": listing['category']}
    
    with tracer.start_run(context=context, tags=["ab_test_v2"]) as run:
        
        # Step 1: Analyze
        with run.step("analyze_current", "llm_analyze") as step:
            step.set_input({"title_len": len(listing['title'])})
            analysis = analyze_listing(listing)
            step.set_output(analysis)
            step.add_decision("analysis_complete", "Found quality issues", criteria={"issues": analysis['issues']})

        # Step 2: Competitor Patterns
        with run.step("competitor_patterns", "retrieval") as step:
            patterns = find_competitor_patterns(listing['category'])
            step.set_output({"patterns_found": len(patterns), "top_pattern": patterns[0]})

        # Step 3: Generate
        with run.step("generate_content", "llm_gen") as step:
            step.set_input({"pattern_count": len(patterns)})
            variations = generate_variations(listing, patterns)
            step.set_output({"generated_count": len(variations)})
            
            # Helper to create candidate objects
            cand_objs = [
                Candidate(id=v['id'], data={"title": v['title'], "tone": v['tone']}) 
                for v in variations
            ]
            step.set_output_candidates(cand_objs)

        # Step 4: Score & Select
        with run.step("select_best", "rank") as step:
            step.set_input_candidates(cand_objs)
            scored = score_variations(variations)
            winner = scored[0]
            
            # Record decisions
            for item in scored:
                step.add_decision(
                    action="scored",
                    reason=item['reason'],
                    criteria={"score": item['score'], "tone": item['variation']['tone']}
                )
            
            selected_cand = Candidate(id=winner['variation']['id'], data=winner['variation'], score=winner['score'])
            step.set_output_candidates([selected_cand])
            step.set_output({"selected_id": winner['variation']['id'], "final_score": winner['score']})

        run.set_final_output({
            "original": listing,
            "optimized": winner['variation']
        })
        print(f"Optimized {listing['id']} -> Winner: {winner['variation']['id']} (Score: {winner['score']:.2f})")

if __name__ == "__main__":
    listings = [
        {"id": "L-99887712", "title": "Blue Widget", "description": "A nice blue widget.", "category": "Home"},
        {"id": "L-44556677", "title": "Gaming Chair Red", "description": "Comfy chair.", "category": "Furniture"},
        {"id": "L-11223344", "title": "Coffee Maker", "description": "Brews coffee fast.", "category": "Kitchen"},
    ]
    
    print("Running Listing Optimization Pipeline...")
    for l in listings:
        optimize_listing(l)
