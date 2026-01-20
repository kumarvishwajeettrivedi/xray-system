"""
Example: Product Categorization Pipeline with X-Ray Instrumentation

Scenario C from Assignment:
Given a new product, assign it to the correct category in a taxonomy of 10,000+ categories.

Steps:
1. Extract attributes (LLM)
2. Match against taxonomy (Vector Search / Rule implementation mock)
3. Score confidence
4. Select best-fit category
"""

import sys
import os
import random
import time
from typing import List, Dict, Any

# Add parent directory to path to import xray_sdk
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from xray_sdk import XRayTracer, Candidate

# Mock Taxonomy
TAXONOMY = [
    "Electronics > Phones > Accessories > Chargers",
    "Electronics > Computers > Components > Storage",
    "Office > Supplies > Desk Accessories",
    "Home > Kitchen > Small Appliances",
    "Automotive > Interior > Accessories",
    "Fashion > Men > Accessories > Belts",
]

def extract_attributes_llm(product: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate extracting structured attributes from unstructured text"""
    # Mock latency
    time.sleep(random.uniform(0.05, 0.2))
    
    return {
        "material": "plastic" if "plastic" in product['description'] else "metal",
        "power_type": "wireless" if "wireless" in product['title'].lower() else "corded",
        "weight": "0.5kg",
        "extracted_keywords": product['title'].lower().split()[:3]
    }

def match_categories(attributes: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Simulate finding candidate categories"""
    # Simply return random subset of taxonomy as "candidates"
    candidates = []
    num_candidates = random.randint(3, 6)
    selected_paths = random.sample(TAXONOMY, num_candidates)
    
    for i, path in enumerate(selected_paths):
        candidates.append({
            "id": f"CAT-{random.randint(1000, 9999)}",
            "path": path,
            "rule_match": random.choice(["keyword_match", "vector_similarity"]),
            "base_score": random.uniform(0.4, 0.8)
        })
    return candidates

def score_candidates_llm(product: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Simulate LLM scoring confidence for each category"""
    scored = []
    for cand in candidates:
        # Simulate logic: if "wireless" is in product and "Chargers" in path, high score
        score = cand['base_score']
        reason = "Low relevance"
        
        if "wireless" in product['title'].lower() and "Chargers" in cand['path']:
            score = random.uniform(0.9, 0.99)
            reason = "Perfect match for wireless charger"
        elif "Office" in cand['path'] and "Stand" in product['title']:
            score = random.uniform(0.8, 0.95)
            reason = "Good fit for office equipment"
        else:
            score = random.uniform(0.1, 0.6)
            reason = "Weak semantic overlap"
            
        cand_copy = cand.copy()
        cand_copy['final_score'] = score
        cand_copy['reasoning'] = reason
        scored.append(cand_copy)
    
    # Sort by score
    scored.sort(key=lambda x: x['final_score'], reverse=True)
    return scored

def categorize_product(product: Dict[str, Any], api_url: str = "http://localhost:8000"):
    tracer = XRayTracer(
        pipeline_name="product_categorization",
        pipeline_version="2.1.0",
        api_url=api_url,
        fail_silently=True
    )

    with tracer.start_run(context={"sku": product['sku'], "source": "vendor_import"}, tags=["batch_import", "auto_cat"]) as run:
        
        # Step 1: Attribute Extraction
        with run.step("extract_attributes", "llm_extract") as step:
            step.set_input({"title": product['title'], "desc_len": len(product['description'])})
            attrs = extract_attributes_llm(product)
            step.set_output(attrs)
            step.add_decision("extraction", "Extracted 3 key attributes", criteria={"model": "gpt-3.5-turbo"})

        # Step 2: Candidate Matching
        with run.step("category_retrieval", "retrieval") as step:
            candidates = match_categories(attrs)
            step.set_input({"keywords": attrs['extracted_keywords']})
            step.set_output({"candidate_count": len(candidates)})
            
            cand_objs = [Candidate(id=c['id'], data={"path": c['path']}) for c in candidates]
            step.set_output_candidates(cand_objs)

        # Step 3: Scoring & Selection
        with run.step("confidence_scoring", "llm_score") as step:
            step.set_input_candidates(cand_objs)
            
            scored = score_candidates_llm(product, candidates)
            winner = scored[0]
            
            # Record decisions
            for cand in scored:
                step.add_decision(
                    action="scored", 
                    reason=cand['reasoning'], 
                    criteria={"score": cand['final_score'], "category": cand['path']}
                )
                
            selected_cand = Candidate(id=winner['id'], data=winner, score=winner['final_score'])
            step.set_output_candidates([selected_cand])
            step.set_output({"selected_category": winner['path'], "confidence": winner['final_score']})

        run.set_final_output({"category": winner['path']})
        print(f"Categorized '{product['title']}' -> {winner['path']}")

if __name__ == "__main__":
    products = [
        {"sku": "8402451-DK", "title": "UltraFast Wireless Charger", "description": "Fast charging pad for phones."},
        {"sku": "99381-OFF", "title": "Aluminum Laptop Stand", "description": "Ergonomic riser for desk."},
        {"sku": "1122-PL", "title": "Generic Plastic Cup", "description": "Drinking vessel."},
        {"sku": "LOGI-M305", "title": "Wireless Mouse", "description": "2.4Ghz optical mouse."},
    ]
    
    print("Running Product Categorization Pipeline...")
    for p in products:
        categorize_product(p)
