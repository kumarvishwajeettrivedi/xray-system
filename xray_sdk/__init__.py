"""
X-Ray SDK - Debugging tool for multi-step, non-deterministic pipelines

Public API:
    - XRayTracer: Main entry point for instrumentation
    - Candidate: Model for tracking items through the pipeline
    - StepType: Common step types (extensible)
"""

from .tracer import XRayTracer
from .models import Candidate, StepType, Decision
from .client import XRayClient

__version__ = "0.1.0"

__all__ = [
    "XRayTracer",
    "Candidate",
    "StepType",
    "Decision",
    "XRayClient",
]
