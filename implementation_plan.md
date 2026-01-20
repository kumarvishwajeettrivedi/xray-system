# Documentation & Examples Refinement Plan

## Goal
Update `ARCHITECTURE.md` and `README.md` with comprehensive, real-world API specifications and examples. Implement "Scenario B: Listing Optimization" to ensure all three prompt scenarios are covered with working code and data.

## Proposed Changes

### 1. New Example: Listing Optimization (Scenario B)
Create `examples/listing_optimization.py` to simulate improving product listings.
- **Pipeline Name:** `listing_optimization`
- **Context:** `{"listing_id": "LST-...", "category": "..."}`
- **Steps:**
    - `analyze_content` (LLM)
    - `competitor_analysis` (Retrieval)
    - `generate_variations` (LLM)
    - `score_variations` (LLM Rank)

### 2. Documentation Updates
Update `README.md` and `ARCHITECTURE.md` to include:
- **Full API Specification:** Explicitly list all endpoints.
- **Real-world Examples:** Use actual data from the 3 scenarios (`competitor_selection`, `product_categorization`, `listing_optimization`).
- **Query Scenarios:** Show how to query distinct pipelines using `context` and `step_type` filters.

## Verification Plan

### Automated Verification
1.  **Run New Script:** Execute `python examples/listing_optimization.py` to populate DB.
2.  **API Check:** Verify `GET /api/runs?pipeline_name=listing_optimization` returns data.
3.  **Context Check:** Verify `GET /api/runs?context={"listing_id": "..."}` works.

### Manual Verification
- Review `README.md` and `ARCHITECTURE.md` for clarity and accuracy.
