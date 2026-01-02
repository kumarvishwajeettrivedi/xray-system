"""
Example: Competitor Selection Pipeline with X-Ray Instrumentation

This demonstrates how to instrument a multi-step, non-deterministic pipeline
to enable deep debugging when results are unexpected.

Scenario:
Given a seller's product, find the most relevant competitor product to benchmark against.

Steps:
1. Generate search keywords (LLM - non-deterministic)
2. Search for candidate products (API call - large result set)
3. Apply filters (price, rating, category)
4. Rank by relevance (LLM - non-deterministic)
5. Select best match
"""

import sys
import os
import random
from typing import List, Dict, Any

# Add parent directory to path to import xray_sdk
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from xray_sdk import XRayTracer, Candidate


# Mock functions simulating real pipeline components
def generate_keywords_llm(product: Dict[str, Any]) -> List[str]:
    """Simulate LLM generating search keywords"""
    # In reality, this would call GPT-4 or similar
    base_keywords = product['title'].lower().split()
    keywords = base_keywords + [product['category']]
    return keywords[:5]  # Simulated output


def search_products(keywords: List[str]) -> List[Dict[str, Any]]:
    """Simulate product search API"""
    # In reality, this would query a product database
    # Simulating finding 50 candidate products
    candidates = []
    
    # Generate 200 candidates for better load testing
    categories = ["Electronics", "Office", "Home", "Accessories"]
    base_titles = [
        "Pro Laptop Stand", "Ergonomic Riser", "Aluminum Desk Mount", 
        "Phone Holder", "Tablet Stand", "Monitor Arm", "Keyboard Tray"
    ]
    
    for i in range(200):
        # Randomize attributes
        price = random.uniform(20.0, 150.0)
        title_base = random.choice(base_titles)
        suffix = random.choice(['Pro', 'Max', 'Lite', 'v2', '2025 Edition'])
        
        candidates.append({
            'id': f'PROD-{i}',
            'title': f"{title_base} {suffix} - {i}",
            'price': round(price, 2),
            'rating': round(random.uniform(2.5, 5.0), 1),
            'review_count': random.randint(10, 5000),
            'category': random.choice(categories),
        })
    return candidates


def apply_price_filter(
    candidates: List[Dict[str, Any]],
    min_price: float,
    max_price: float
) -> tuple[List[Dict[str, Any]], List[tuple[Dict[str, Any], str]]]:
    """Filter by price range, returning kept items and rejected items with reasons"""
    kept = []
    rejected = []

    for candidate in candidates:
        if candidate['price'] < min_price:
            rejected.append((candidate, f"Price ${candidate['price']} below minimum ${min_price}"))
        elif candidate['price'] > max_price:
            rejected.append((candidate, f"Price ${candidate['price']} above maximum ${max_price}"))
        else:
            kept.append(candidate)

    return kept, rejected


def apply_rating_filter(
    candidates: List[Dict[str, Any]],
    min_rating: float
) -> tuple[List[Dict[str, Any]], List[tuple[Dict[str, Any], str]]]:
    """Filter by minimum rating"""
    kept = []
    rejected = []

    for candidate in candidates:
        if candidate['rating'] < min_rating:
            rejected.append((candidate, f"Rating {candidate['rating']} below minimum {min_rating}"))
        else:
            kept.append(candidate)

    return kept, rejected


def rank_by_relevance_llm(
    candidates: List[Dict[str, Any]],
    original_product: Dict[str, Any]
) -> List[tuple[Dict[str, Any], float, str]]:
    """Simulate LLM ranking candidates by relevance"""
    # In reality, this would use an LLM to assess relevance
    # Simulating by assigning random scores
    ranked = []
    for candidate in candidates:
        score = random.uniform(0.3, 0.95)
        reasoning = f"Similarity score {score:.2f} based on title match and category"
        ranked.append((candidate, score, reasoning))

    # Sort by score descending
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def select_best_competitor(ranked_candidates: List[tuple[Dict[str, Any], float, str]]) -> Dict[str, Any]:
    """Select the top-ranked competitor"""
    if not ranked_candidates:
        return None
    return ranked_candidates[0][0]


# Main pipeline with X-Ray instrumentation
def find_competitor_product(product: Dict[str, Any], api_url: str = "http://localhost:8000") -> Dict[str, Any]:
    """
    Find the best competitor product with full X-Ray tracing.

    This shows how a developer would instrument an existing pipeline.
    """
    # Initialize X-Ray tracer
    tracer = XRayTracer(
        pipeline_name="competitor_selection",
        api_url=api_url,
        pipeline_version="1.0",
        enabled=True,
        fail_silently=True,  # Never break production code
        auto_send=True,  # Automatically send to API
    )

    val_tags = ["team_search", "experiment_A"] if product['id'].endswith("0") else ["team_search"]
    # Start a traced run
    with tracer.start_run(context={"product_id": product['id'], "user_id": "user_123"}, tags=val_tags) as run:

        # Step 1: Generate keywords using LLM
        with run.step("keyword_generation", "llm_call") as step:
            keywords = generate_keywords_llm(product)

            step.set_input({"product_title": product['title'], "category": product['category']})
            step.set_output({"keywords": keywords})
            step.add_decision(
                action="generated",
                reason=f"Generated {len(keywords)} keywords from product title and category",
                criteria={"model": "gpt-4", "temperature": 0.7}
            )

        # Step 2: Search for candidate products
        with run.step("product_search", "api_call") as step:
            candidates = search_products(keywords)

            step.set_input({"keywords": keywords})
            step.set_output({"candidate_count": len(candidates)})

            # Convert to Candidate objects
            candidate_objs = [
                Candidate(
                    id=c['id'],
                    data={
                        'title': c['title'],
                        'price': c['price'],
                        'rating': c['rating'],
                        'category': c['category'],
                    }
                )
                for c in candidates
            ]
            step.set_output_candidates(candidate_objs)

            step.add_decision(
                action="searched",
                reason=f"Found {len(candidates)} candidates from search API",
                criteria={"search_keywords": keywords}
            )

        # Step 3: Apply price filter
        with run.step("price_filter", "filter") as step:
            target_price = product['price']
            min_price = target_price * 0.7  # 30% lower
            max_price = target_price * 1.3  # 30% higher

            kept, rejected = apply_price_filter(candidates, min_price, max_price)

            step.set_input({
                "candidate_count": len(candidates),
                "min_price": min_price,
                "max_price": max_price,
            })
            step.set_output({"kept_count": len(kept), "rejected_count": len(rejected)})

            # Track input/output candidates
            step.set_input_candidates([Candidate(id=c['id'], data={'price': c['price']}) for c in candidates])
            step.set_output_candidates([Candidate(id=c['id'], data={'price': c['price']}) for c in kept])

            # Record decisions for rejected items (showing why each was filtered)
            for candidate, reason in rejected[:10]:  # Sample first 10 for performance
                step.add_decision(
                    action="filtered_out",
                    reason=reason,
                    criteria={"candidate_id": candidate['id'], "price": candidate['price']}
                )

            step.add_decision(
                action="filter_applied",
                reason=f"Kept {len(kept)}/{len(candidates)} candidates within price range ${min_price:.2f}-${max_price:.2f}",
                criteria={"min_price": min_price, "max_price": max_price}
            )

            # Update for next step
            candidates = kept

        # Step 4: Apply rating filter
        with run.step("rating_filter", "filter") as step:
            min_rating = 4.0
            kept, rejected = apply_rating_filter(candidates, min_rating)

            step.set_input({
                "candidate_count": len(candidates),
                "min_rating": min_rating,
            })
            step.set_output({"kept_count": len(kept), "rejected_count": len(rejected)})

            step.set_input_candidates([Candidate(id=c['id'], data={'rating': c['rating']}) for c in candidates])
            step.set_output_candidates([Candidate(id=c['id'], data={'rating': c['rating']}) for c in kept])

            # Record sample rejections
            for candidate, reason in rejected[:10]:
                step.add_decision(
                    action="filtered_out",
                    reason=reason,
                    criteria={"candidate_id": candidate['id'], "rating": candidate['rating']}
                )

            step.add_decision(
                action="filter_applied",
                reason=f"Kept {len(kept)}/{len(candidates)} candidates with rating >= {min_rating}",
                criteria={"min_rating": min_rating}
            )

            candidates = kept

        # Step 5: Rank by relevance using LLM
        with run.step("relevance_ranking", "rank") as step:
            if not candidates:
                step.set_output({"ranked_count": 0})
                step.add_decision(
                    action="no_candidates",
                    reason="No candidates remaining after filters",
                    criteria={}
                )
                ranked = []
            else:
                ranked = rank_by_relevance_llm(candidates, product)

                step.set_input({"candidate_count": len(candidates)})
                step.set_output({"ranked_count": len(ranked)})

                # Track ranked candidates with scores
                ranked_candidate_objs = [
                    Candidate(
                        id=c['id'],
                        data={'title': c['title'], 'category': c['category']},
                        score=score
                    )
                    for c, score, _ in ranked
                ]
                step.set_output_candidates(ranked_candidate_objs)

                # Record ranking decisions for top candidates
                for i, (candidate, score, reasoning) in enumerate(ranked[:5]):
                    step.add_decision(
                        action="ranked",
                        reason=reasoning,
                        criteria={
                            "rank": i + 1,
                            "candidate_id": candidate['id'],
                            "score": score,
                        }
                    )

                step.add_decision(
                    action="ranking_complete",
                    reason=f"Ranked {len(ranked)} candidates by relevance using LLM",
                    criteria={"model": "gpt-4", "top_score": ranked[0][1] if ranked else 0}
                )

        # Step 6: Select best competitor
        with run.step("final_selection", "select") as step:
            if not ranked:
                selected = None
                step.set_output({"selected": None})
                step.add_decision(
                    action="no_selection",
                    reason="No candidates available for selection",
                    criteria={}
                )
            else:
                selected = select_best_competitor(ranked)
                score = ranked[0][1]

                step.set_input({"candidate_count": len(ranked)})
                step.set_output({
                    "selected_id": selected['id'],
                    "selected_title": selected['title'],
                    "final_score": score,
                })

                step.set_output_candidates([
                    Candidate(
                        id=selected['id'],
                        data=selected,
                        score=score
                    )
                ])

                step.add_decision(
                    action="selected",
                    reason=f"Selected {selected['id']} with score {score:.2f} as best competitor",
                    criteria={
                        "candidate_id": selected['id'],
                        "score": score,
                        "title": selected['title'],
                    }
                )

        # Set final output
        run.set_final_output({
            "competitor_product": selected,
            "original_product": product,
        })

        return selected


if __name__ == "__main__":
    # Example product
    print("🚀 Starting large batch test (300 products)...")
    
    products = [
        {"id": f"TEST-{i}", "title": f"Laptop Stand Model {i}", "category": "Office", "price": 45 + (i % 50)} 
        for i in range(300)
    ]

    import time
    start_time = time.time()
    
    for i, product in enumerate(products):
        if (i+1) % 10 == 0:
            print(f"[{i+1}/300] Processing...")
        find_competitor_product(product, api_url="http://localhost:8000")

        
    total_time = time.time() - start_time
    print(f"\n✅ Batch complete!")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average latency per run: {(total_time / 300) * 1000:.2f}ms")
