# X-Ray SDK: Pipeline Decision Debugging

**A debugging system for multi-step, non-deterministic algorithmic pipelines.**

X-Ray provides visibility into complex systems (like RAG, Search, or Recommendation pipelines) by capturing decision context at each step. Unlike traditional tracing that shows "what happened," X-Ray reveals "**why this output**" by tracking inputs, candidates, filtering logic, and reasoning.

This implementation demonstrates the core SDK and API for debugging pipelines like competitor selection, listing optimization, and product categorization.

---

## Quick Start

### Tools
- Python 3.9+
- PostgreSQL 12+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/kumarvishwajeettrivedi/xray-system.git
   cd xray-system
   ```

2. **Set up Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Database**
   - Create a Postgres database named `xray_db`.
   - Copy `.env.example` to `.env` and update credentials.
   - Run the setup script:
     ```bash
     psql -U postgres -d xray_db -f postgres_setup.sql
     ```

4. **Start the API**
   ```bash
   python run_api.py
   # API running at http://localhost:8000
   ```

5. **Install SDK (Editable Mode)**
   ```bash
   pip install -e .
   ```

---

## Example

### 1. Run the Demo Pipeline
We have provided a robust example simulating a "Competitor Selection" pipeline.

```bash
python examples/competitor_selection.py
```
*This script runs a batch of 300 products to demonstrate performance and latency tracking.*

### 2. API Reference (Postman-ready)
You can test these endpoints directly using Postman or curl.

#### **Health Check**
- `GET /`

#### **Runs**
- **List Runs**: `GET /api/runs`
  - Filters: `pipeline_name`, `success`, `tags`, `context`
  
  **Real World Examples:**
  
  *1. Competitor Selection (Scenario A):* Find runs for a specific user ID.
  ```bash
  GET /api/runs?pipeline_name=competitor_selection&context={"user_id": "usr_8f92a1b3c4d5"}
  ```

  *2. Listing Optimization (Scenario B):* Find runs for a specific listing ID.
  ```bash
  GET /api/runs?pipeline_name=listing_optimization&context={"listing_id": "L-99887712"}
  ```

  *3. Product Categorization (Scenario C):* Find runs where a specific SKU was processed.
  ```bash
  GET /api/runs?pipeline_name=product_categorization&context={"sku": "8402451-DK"}
  ```

  *4. Failed Runs:* Find only failed runs to debug issues.
  ```bash
  GET /api/runs?success=false
  ```

### 3. Examples & Scenarios
We provide scripts simulating real-world complex pipelines:

#### **Scenario A: Competitor Selection**
finds the best competitor product.
```bash
python examples/competitor_selection.py
```

#### **Scenario B: Listing Optimization**
Optimizes product titles and descriptions using competitor patterns.
```bash
python examples/listing_optimization.py
```

#### **Scenario C: Product Categorization**
Assigns new products to a taxonomy using LLM + Vector Search logic.
```bash
python examples/product_categorization.py
```

### 4. View Traces (Frontend)
Launch the included Streamlit dashboard to explore runs. It checks **interactive Gantt charts** to visualize step latency and parallelism.

```bash
streamlit run frontend/streamlit_app.py
```
*Visit http://localhost:8501*

### 3. API Reference (Postman-ready)
See [API Reference](#2-api-reference-postman-ready) above or [ARCHITECTURE.md](./ARCHITECTURE.md) for full details.

### 4. View Traces (Frontend)

```python
from xray_sdk import XRayTracer

tracer = XRayTracer("my_pipeline")

with tracer.start_run() as run:
    with run.step("filtering", "filter") as step:
        step.set_input({"candidates": 5000})
        # ... logic ...
        step.add_decision("filtered_out", "Price too high", {"threshold": 100})
```

---

## Architecture Overview

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full technical deep dive.

### Core Components
- **X-Ray SDK**: Lightweight Python context managers for capturing data. Default `fail_silently=True` for production safety.
- **X-Ray API**: Async FastAPI service handling high-throughput ingestion.
- **PostgreSQL**: Hybrid Relational + JSONB data model. Allows structured queries ("show all failed runs") and flexible analysis ("show reasoning for step X").

### Key Design Decisions
- **Hybrid Data Model**: Normalized `runs` table for speed; JSONB for flexible step context.
- **Async Ingestion**: The SDK uses a background worker thread to send traces, ensuring **zero latency impact** on the main application execution.
- **Sampling Strategy**: `summary()` mode and `sample_rate` logic designed for high-cardinality steps (5000+ items).
- **Graceful Degradation**: If the API is down, the SDK ensures your pipeline continues running.

---

## Current Limitations

### Implementation Scope
- **Mock Data**: The demo uses synthetic data and simulated LLM latencies.
- **Single Instance**: Designed for a single-server deployment (simplified for this assignment).

## Future Roadmap

### Production Enhancements
1. **Persistent Queueing**: Upgrade from in-memory queue to Redis/Celery for durability across restarts.
2. **Blob Storage**: Move large candidate lists to S3/GCS, keeping Postgres lean for metadata.
3. **Advanced Sampling**: implement dynamic "tail sampling" to keep only interesting traces (failures/anomalies).
4. **Auto-Instrumentation**: Decorators for popular libraries (LangChain, LlamaIndex).

---
