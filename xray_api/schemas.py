"""
Pydantic schemas for X-Ray API

These define the request/response shapes for the API.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
 

# Candidate schemas
class CandidateSchema(BaseModel):
    id: str
    data: Dict[str, Any]
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Decision schemas
class DecisionSchema(BaseModel):
    action: str
    reason: str
    criteria: Dict[str, Any] = Field(default_factory=dict)


# Step schemas
class StepTraceSchema(BaseModel):
    step_name: str
    step_type: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    input_candidates: List[CandidateSchema] = Field(default_factory=list)
    output_candidates: List[CandidateSchema] = Field(default_factory=list)
    decisions: List[DecisionSchema] = Field(default_factory=list)
    duration_ms: Optional[float] = None
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sample_rate: float = 1.0

    class Config:
        from_attributes = True


# Pipeline Run schemas
class PipelineRunCreate(BaseModel):
    """Schema for creating a new pipeline run"""
    run_id: str
    pipeline_name: str
    pipeline_version: str
    steps: List[StepTraceSchema] = Field(default_factory=list)
    final_output: Optional[Dict[str, Any]] = None
    success: bool = True
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class PipelineRunResponse(BaseModel):
    """Schema for pipeline run response"""
    run_id: str
    pipeline_name: str
    pipeline_version: str
    success: bool
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    context: Dict[str, Any]
    tags: List[str] = Field(default_factory=list)
    final_output: Optional[Dict[str, Any]] = None
    created_at: datetime
    steps: List[StepTraceSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PipelineRunSummary(BaseModel):
    """Lightweight summary for list endpoints"""
    run_id: str
    pipeline_name: str
    pipeline_version: str
    success: bool
    total_duration_ms: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    step_count: int
    context: Dict[str, Any]
    tags: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


# Query schemas
class RunQueryParams(BaseModel):
    """Parameters for querying runs"""
    pipeline_name: Optional[str] = None
    pipeline_version: Optional[str] = None
    success: Optional[bool] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


class StepQueryParams(BaseModel):
    """Parameters for querying steps across runs"""
    step_name: Optional[str] = None
    step_type: Optional[str] = None
    min_reduction_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_reduction_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)


# Response wrappers
class RunListResponse(BaseModel):
    total: int
    items: List[PipelineRunSummary]


class StepListResponse(BaseModel):
    total: int
    items: List[StepTraceSchema]
