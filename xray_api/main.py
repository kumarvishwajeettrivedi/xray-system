"""
X-Ray API - FastAPI Application

Provides endpoints for:
1. Ingesting pipeline run data
2. Querying runs and steps
3. Analyzing cross-pipeline patterns
""" 

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, String
from typing import Optional, List
from datetime import datetime
import json

from .database import get_db, init_db
from .models import PipelineRunModel, StepTraceModel
from .schemas import (
    PipelineRunCreate,
    PipelineRunResponse,
    PipelineRunSummary,
    RunListResponse,
    StepQueryParams,
    StepListResponse,
    StepTraceSchema,
)


def to_naive_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert timezone-aware datetime to naive datetime for PostgreSQL."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        # Convert to UTC and remove timezone info
        return dt.replace(tzinfo=None)
    return dt

app = FastAPI(
    title="X-Ray API",
    description="API for debugging multi-step, non-deterministic pipelines",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "X-Ray API"}


@app.post("/api/runs", response_model=dict, status_code=201)
async def create_run(
    run_data: PipelineRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest a new pipeline run.

    This is the primary endpoint that the SDK uses to send trace data.
    """
    # Create the run with timezone-naive datetimes
    run = PipelineRunModel(
        run_id=run_data.run_id,
        pipeline_name=run_data.pipeline_name,
        pipeline_version=run_data.pipeline_version,
        success=run_data.success,
        error=run_data.error,
        started_at=to_naive_datetime(run_data.started_at),
        completed_at=to_naive_datetime(run_data.completed_at),
        total_duration_ms=run_data.total_duration_ms,
        context=run_data.context,
        tags=run_data.tags,
        final_output=run_data.final_output,
    )

    # Create steps
    for step_data in run_data.steps:
        # Calculate counts and reduction rate
        input_count = len(step_data.input_candidates)
        output_count = len(step_data.output_candidates)
        reduction_rate = (input_count - output_count) / input_count if input_count > 0 else 0.0

        step = StepTraceModel(
            run_id=run_data.run_id,
            step_name=step_data.step_name,
            step_type=step_data.step_type,
            duration_ms=step_data.duration_ms,
            timestamp=to_naive_datetime(step_data.timestamp),
            input_count=input_count,
            output_count=output_count,
            reduction_rate=reduction_rate,
            inputs=step_data.inputs,
            outputs=step_data.outputs,
            input_candidates=[c.dict() for c in step_data.input_candidates],
            output_candidates=[c.dict() for c in step_data.output_candidates],
            decisions=[d.dict() for d in step_data.decisions],
            step_metadata=step_data.metadata,
            sample_rate=step_data.sample_rate,
        )
        run.steps.append(step)

    db.add(run)
    await db.commit()

    return {"status": "created", "run_id": run_data.run_id}


@app.get("/api/runs/{run_id}", response_model=PipelineRunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific pipeline run by ID with all step details.

    This is the primary debugging endpoint - returns full trace data.
    """
    result = await db.execute(
        select(PipelineRunModel).where(PipelineRunModel.run_id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Fetch steps
    steps_result = await db.execute(
        select(StepTraceModel)
        .where(StepTraceModel.run_id == run_id)
        .order_by(StepTraceModel.timestamp)
    )
    steps = steps_result.scalars().all()

    # Convert to response format
    steps_data = []
    for step in steps:
        steps_data.append(StepTraceSchema(
            step_name=step.step_name,
            step_type=step.step_type,
            inputs=step.inputs or {},
            outputs=step.outputs or {},
            input_candidates=[c for c in (step.input_candidates or [])],
            output_candidates=[c for c in (step.output_candidates or [])],
            decisions=[d for d in (step.decisions or [])],
            duration_ms=step.duration_ms,
            timestamp=step.timestamp,
            metadata=step.step_metadata or {},
            sample_rate=step.sample_rate,
        ))

    return PipelineRunResponse(
        run_id=run.run_id,
        pipeline_name=run.pipeline_name,
        pipeline_version=run.pipeline_version,
        success=run.success,
        error=run.error,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_ms=run.total_duration_ms,
        context=run.context or {},
        final_output=run.final_output,
        created_at=run.created_at,
        steps=steps_data,
    )


@app.get("/api/runs", response_model=RunListResponse)
async def list_runs(
    pipeline_name: Optional[str] = None,
    pipeline_version: Optional[str] = None,
    success: Optional[bool] = None,
    tags: Optional[str] = Query(None, description="Filter by tag"),
    context: Optional[str] = Query(None, description="Filter by context JSON (e.g. {'user_id': '123'})"),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Query pipeline runs with filters.

    Supports filtering by:
    - pipeline_name: Specific pipeline
    - pipeline_version: Specific version
    - success: Filter by outcome
    - context: Filter by context fields (exact match on JSON subset)
    """
    # Build query
    query = select(PipelineRunModel)
    conditions = []

    if pipeline_name:
        conditions.append(PipelineRunModel.pipeline_name == pipeline_name)
    if pipeline_version:
        conditions.append(PipelineRunModel.pipeline_version == pipeline_version)
    if success is not None:
        conditions.append(PipelineRunModel.success == success)
    
    # Filter by tag if provided
    if tags:
        conditions.append(func.cast(PipelineRunModel.tags, String).like(f'%"{tags}"%'))

    # Filter by context if provided
    if context:
        try:
            context_dict = json.loads(context)
            # Use JSON containment operator (@>)
            # Note: We cast to JSONB to ensure we use the GIN index and proper operator
            # even though the model defines it as generic JSON
            from sqlalchemy.dialects.postgresql import JSONB
            conditions.append(func.cast(PipelineRunModel.context, JSONB).contains(context_dict))
        except json.JSONDecodeError:
            # If invalid JSON, ignore or we could raise HTTPException
            # For now we'll ignore to matching existing leniency, or raise 400?
            # Better to raise 400 so user knows why it didn't filter
            raise HTTPException(status_code=400, detail="Invalid JSON format for context parameter")

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(PipelineRunModel)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.order_by(PipelineRunModel.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    # Get step counts
    items = []
    for run in runs:
        step_count_result = await db.execute(
            select(func.count()).where(StepTraceModel.run_id == run.run_id)
        )
        step_count = step_count_result.scalar()

        items.append(PipelineRunSummary(
            run_id=run.run_id,
            pipeline_name=run.pipeline_name,
            pipeline_version=run.pipeline_version,
            success=run.success,
            total_duration_ms=run.total_duration_ms,
            started_at=run.started_at,
            completed_at=run.completed_at,
            step_count=step_count,
            context=run.context or {},
            tags=run.tags or [],
        ))

    return RunListResponse(total=total, items=items)


@app.get("/api/steps", response_model=StepListResponse)
async def query_steps(
    step_name: Optional[str] = None,
    step_type: Optional[str] = None,
    min_reduction_rate: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    max_reduction_rate: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    min_duration_ms: Optional[float] = None,
    max_duration_ms: Optional[float] = None,
    pipeline_name: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Query steps across ALL pipeline runs.

    This is the key queryability feature - find patterns across different pipelines.

    Examples:
    - Find all filter steps that eliminated >90% of candidates
    - Find slow LLM calls across all pipelines
    - Identify bottlenecks by step type
    """
    # Build query
    query = select(StepTraceModel)
    conditions = []

    if step_name:
        conditions.append(StepTraceModel.step_name == step_name)
    if step_type:
        conditions.append(StepTraceModel.step_type == step_type)
    if min_reduction_rate is not None:
        conditions.append(StepTraceModel.reduction_rate >= min_reduction_rate)
    if max_reduction_rate is not None:
        conditions.append(StepTraceModel.reduction_rate <= max_reduction_rate)
    if min_duration_ms is not None:
        conditions.append(StepTraceModel.duration_ms >= min_duration_ms)
    if max_duration_ms is not None:
        conditions.append(StepTraceModel.duration_ms <= max_duration_ms)

    # Filter by pipeline if specified
    if pipeline_name:
        query = query.join(PipelineRunModel)
        conditions.append(PipelineRunModel.pipeline_name == pipeline_name)

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(StepTraceModel)
    if pipeline_name:
        count_query = count_query.join(PipelineRunModel)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.order_by(StepTraceModel.timestamp.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    steps = result.scalars().all()

    # Convert to response
    items = []
    for step in steps:
        items.append(StepTraceSchema(
            step_name=step.step_name,
            step_type=step.step_type,
            inputs=step.inputs or {},
            outputs=step.outputs or {},
            input_candidates=[c for c in (step.input_candidates or [])],
            output_candidates=[c for c in (step.output_candidates or [])],
            decisions=[d for d in (step.decisions or [])],
            duration_ms=step.duration_ms,
            timestamp=step.timestamp,
            metadata=step.step_metadata or {},
            sample_rate=step.sample_rate,
        ))

    return StepListResponse(total=total, items=items)


@app.get("/api/analytics/step-performance")
async def step_performance_analytics(
    pipeline_name: Optional[str] = None,
    step_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated performance metrics for steps.

    Returns statistics like:
    - Average reduction rate by step type
    - Average duration by step type
    - Count of steps by type
    """
    # Build base query
    query = select(
        StepTraceModel.step_type,
        StepTraceModel.step_name,
        func.count(StepTraceModel.id).label('count'),
        func.avg(StepTraceModel.reduction_rate).label('avg_reduction_rate'),
        func.avg(StepTraceModel.duration_ms).label('avg_duration_ms'),
        func.max(StepTraceModel.reduction_rate).label('max_reduction_rate'),
        func.min(StepTraceModel.reduction_rate).label('min_reduction_rate'),
    )

    if pipeline_name:
        query = query.join(PipelineRunModel).where(PipelineRunModel.pipeline_name == pipeline_name)

    if step_type:
        query = query.where(StepTraceModel.step_type == step_type)

    query = query.group_by(StepTraceModel.step_type, StepTraceModel.step_name)

    result = await db.execute(query)
    rows = result.all()

    analytics = []
    for row in rows:
        analytics.append({
            "step_type": row.step_type,
            "step_name": row.step_name,
            "count": row.count,
            "avg_reduction_rate": round(row.avg_reduction_rate, 3) if row.avg_reduction_rate else 0,
            "avg_duration_ms": round(row.avg_duration_ms, 2) if row.avg_duration_ms else 0,
            "max_reduction_rate": round(row.max_reduction_rate, 3) if row.max_reduction_rate else 0,
            "min_reduction_rate": round(row.min_reduction_rate, 3) if row.min_reduction_rate else 0,
        })

    return {"analytics": analytics}
