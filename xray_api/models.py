"""
Database models for X-Ray API

Design principles:
- Hybrid approach: Normalized fields for querying + JSON blob for flexibility
- Query-friendly: Key fields extracted for filtering and aggregation
- Scalable: Indexes on common query patterns
""" 

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Text, Index, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from .database import Base


class PipelineRunModel(Base):
    """
    Stores pipeline run metadata with normalized fields for querying.

    Queryability:
    - pipeline_name, pipeline_version: Group runs across time
    - success, total_duration_ms: Filter by outcome/performance
    - context (JSON): Query on custom dimensions (user_id, environment, etc.)
    - created_at: Time-series analysis
    """
    __tablename__ = "pipeline_runs"

    __tablename__ = "pipeline_runs"

    run_id = Column(String, primary_key=True, index=True)

    pipeline_name = Column(String, index=True, nullable=False)
    pipeline_version = Column(String, index=True, nullable=False)

    success = Column(Boolean, default=True, index=True)
    error = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    total_duration_ms = Column(Float, nullable=True)

    context = Column(JSON, nullable=True)  # user_id, product_id, environment, etc.
    tags = Column(JSON, nullable=True)
    final_output = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    steps = relationship("StepTraceModel", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_pipeline_name_created', 'pipeline_name', 'created_at'),
        Index('idx_pipeline_success', 'pipeline_name', 'success'),
    )


class StepTraceModel(Base):
    """
    Stores individual step traces with normalized fields for cross-pipeline queries.

    Queryability design:
    - step_name, step_type: Query steps across different pipelines
    - input_count, output_count: Find steps with high reduction rates
    - duration_ms: Identify performance bottlenecks
    - candidates & decisions (JSON): Full debugging data
    """
    __tablename__ = "step_traces"

    __tablename__ = "step_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("pipeline_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)

    step_name = Column(String, index=True, nullable=False)
    step_type = Column(String, index=True, nullable=False)

    duration_ms = Column(Float, nullable=True, index=True)
    timestamp = Column(DateTime, nullable=False)

    input_count = Column(Integer, default=0, index=True)
    output_count = Column(Integer, default=0, index=True)
    reduction_rate = Column(Float, default=0.0, index=True)

    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)
    input_candidates = Column(JSON, nullable=True)
    output_candidates = Column(JSON, nullable=True)
    decisions = Column(JSON, nullable=True)
    step_metadata = Column(JSON, nullable=True)

    sample_rate = Column(Float, default=1.0)

    run = relationship("PipelineRunModel", back_populates="steps")

    __table_args__ = (
        Index('idx_step_type_reduction', 'step_type', 'reduction_rate'),
        Index('idx_step_name_duration', 'step_name', 'duration_ms'),
        Index('idx_run_step_order', 'run_id', 'timestamp'),
    )
