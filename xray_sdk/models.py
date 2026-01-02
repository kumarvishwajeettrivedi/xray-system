"""
X-Ray SDK Data Models

These models define the structure of X-Ray traces. The design is intentionally
flexible to support diverse multi-step pipelines while maintaining queryability.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
import json
import time

 
class StepType(str, Enum):
    """Common step types - extensible via custom strings"""
    SEARCH = "search"
    FILTER = "filter"
    TRANSFORM = "transform"
    RANK = "rank"
    SELECT = "select"
    LLM_CALL = "llm_call"
    API_CALL = "api_call"
    CUSTOM = "custom"


@dataclass
class Candidate:
    """
    Represents a single item being processed (product, listing, category, etc.)

    Design principle: Store just enough to debug without bloating storage.
    Full details can be referenced via external_id if needed.
    """
    id: str  # Unique identifier for this candidate
    data: Dict[str, Any]  # Relevant attributes for debugging
    score: Optional[float] = None  # If applicable (ranking, relevance)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extensible metadata

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Decision:
    """
    Captures WHY something happened - the core of X-Ray's value.

    Examples:
    - Filter: "Eliminated because price $299 exceeds max $250"
    - Ranking: "Scored 0.85 based on title similarity + category match"
    - Selection: "Chose candidate X over Y because higher relevance score"
    """
    action: str  # What happened: "filtered_out", "ranked", "selected", etc.
    reason: str  # Human-readable explanation
    criteria: Dict[str, Any] = field(default_factory=dict)  # Structured criteria used

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StepTrace:
    """
    Captures a single step in a multi-step pipeline.

    Design principles:
    - Flexible schema: Different steps have different data needs
    - Performance-aware: Support sampling via sample_rate
    - Query-friendly: Normalized fields (step_type, step_name) enable cross-pipeline queries
    """
    step_name: str  # Unique name for this step type (e.g., "keyword_generation", "price_filter")
    step_type: str  # Normalized type (search, filter, rank, etc.)

    # Core trace data
    inputs: Dict[str, Any] = field(default_factory=dict)  # What went into this step
    outputs: Dict[str, Any] = field(default_factory=dict)  # What came out

    # Candidate tracking
    input_candidates: List[Candidate] = field(default_factory=list)
    output_candidates: List[Candidate] = field(default_factory=list)

    # Decision tracking - the "why"
    decisions: List[Decision] = field(default_factory=list)

    # Performance & metadata
    duration_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extensible for custom fields

    # Sampling control
    sample_rate: float = 1.0  # 1.0 = full capture, 0.1 = 10% sample

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    def add_decision(self, action: str, reason: str, criteria: Optional[Dict[str, Any]] = None):
        """Helper to add a decision"""
        self.decisions.append(Decision(
            action=action,
            reason=reason,
            criteria=criteria or {}
        ))

    def summary(self) -> Dict[str, Any]:
        """
        Returns a lightweight summary instead of full data.
        Useful for high-cardinality steps (e.g., 5000 candidates).
        """
        return {
            "step_name": self.step_name,
            "step_type": self.step_type,
            "input_count": len(self.input_candidates),
            "output_count": len(self.output_candidates),
            "reduction_rate": 1 - (len(self.output_candidates) / len(self.input_candidates)) if self.input_candidates else 0,
            "duration_ms": self.duration_ms,
            "decisions_count": len(self.decisions),
        }


@dataclass
class PipelineRun:
    """
    Represents a complete execution of a multi-step pipeline.

    Design principles:
    - Pipeline identity: pipeline_name + pipeline_version enable cross-run queries
    - Final result: Store the ultimate output for quick access
    - Extensible: context allows arbitrary metadata (user_id, product_id, etc.)
    """
    def __init__(
        self,
        run_id: str,
        pipeline_name: str,
        pipeline_version: str,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ):
        self.run_id = run_id
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.context = context or {}
        self.tags = tags or []
        
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.steps: List['StepTrace'] = []
        
        self.success = True
        self.error: Optional[str] = None
        self.final_output: Optional[Dict[str, Any]] = None

    def add_step(self, step: 'StepTrace'):
        step.run_id = self.run_id
        self.steps.append(step)

    def complete(self, success: bool = None, error: str = None):
        self.end_time = time.time()
        if success is not None:
            self.success = success
        if error:
            self.success = False
            self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "context": self.context,
            "tags": self.tags,
            "started_at": datetime.utcfromtimestamp(self.start_time).isoformat(),
            "completed_at": datetime.utcfromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "total_duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time else None,
            "steps": [s.to_dict() for s in self.steps],
            "success": self.success,
            "error": self.error,
            self.final_output = final_output
        if error:
            self.success = False
            self.error = error
