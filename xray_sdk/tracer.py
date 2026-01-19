"""
X-Ray Tracer - Main SDK Interface

This module provides the developer-facing API for instrumenting pipelines using 
context managers. It handles state management, error capturing, and lifecycle 
events for pipeline runs and steps.
"""

import time
import uuid 
from typing import Any, Dict, List, Optional, Callable
from contextlib import contextmanager
from datetime import datetime

from .models import PipelineRun, StepTrace, Candidate, Decision
from .client import XRayClient


class XRayTracer:
    """
    Main entry point for X-Ray instrumentation.

    Usage:
        tracer = XRayTracer(api_url="http://localhost:8000", pipeline_name="my_pipeline")

        with tracer.start_run(context={"user_id": 123}) as run:
            # Step 1
            with run.step("keyword_generation", "llm_call") as step:
                keywords = generate_keywords(product)
                step.set_output({"keywords": keywords})
                step.add_decision("generated", f"Generated {len(keywords)} keywords", {"model": "gpt-4"})

            # Step 2
            with run.step("search", "api_call") as step:
                results = search_api(keywords)
                step.set_input({"query": keywords})
                step.set_candidates([Candidate(id=r.id, data=r.data) for r in results])
    """

    def __init__(
        self,
        pipeline_name: str,
        api_url: Optional[str] = None,
        pipeline_version: str = "1.0",
        enabled: bool = True,
        fail_silently: bool = True,
        auto_send: bool = True,
    ):
        """
        Initialize the tracer.

        Args:
            pipeline_name: Name of the pipeline being traced
            api_url: X-Ray API endpoint (if None, runs in local-only mode)
            pipeline_version: Version identifier for the pipeline
            enabled: If False, all tracing is a no-op (for production kill-switch)
            fail_silently: If True, X-Ray errors never propagate to user code
            auto_send: If True, automatically send data to API on run completion
        """
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.enabled = enabled
        self.fail_silently = fail_silently
        self.auto_send = auto_send

        self.client = XRayClient(api_url) if api_url else None
        self._current_run: Optional[RunContext] = None

    @contextmanager
    def start_run(
        self,
        context: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Start a new pipeline run.

        Args:
            context: Arbitrary metadata (user_id, product_id, environment, etc.)
            run_id: Optional custom run ID (otherwise generated)
            tags: Optional list of strings for categorization (e.g., ["team-a", "experiment-1"])

        Yields:
            RunContext: Context manager for adding steps
        """
        if not self.enabled:
            yield _NoOpRunContext()
            return

        run_id = run_id or str(uuid.uuid4())
        run = PipelineRun(
            run_id=run_id,
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
            context=context or {},
            tags=tags,
        )

        run_context = RunContext(run, self.client, self.fail_silently, self.auto_send)
        self._current_run = run_context

        try:
            yield run_context
        except Exception as e:
            # Capture the exception in the run
            run.complete(error=str(e))
            raise
        finally:
            # Complete the run
            if not run.end_time:
                run.complete()

            # Send to API if configured
            if self.auto_send and self.client:
                try:
                    run_context.send()
                except Exception as e:
                    if not self.fail_silently:
                        raise
                    # Silently fail - don't break user code

            self._current_run = None

    def get_current_run(self) -> Optional['RunContext']:
        """Get the current active run (if any)"""
        return self._current_run


class RunContext:
    """
    Context for a single pipeline run.
    Provides methods to add steps and manage the run lifecycle.
    """

    def __init__(
        self,
        run: PipelineRun,
        client: Optional[XRayClient],
        fail_silently: bool,
        auto_send: bool,
    ):
        self.run = run
        self.client = client
        self.fail_silently = fail_silently
        self.auto_send = auto_send

    @contextmanager
    def step(
        self,
        step_name: str,
        step_type: str,
        sample_rate: float = 1.0,
    ):
        """
        Trace a single step in the pipeline.

        Args:
            step_name: Unique name (e.g., "price_filter")
            step_type: Type of step (filter, rank, llm_call)
            sample_rate: 0.0 to 1.0. If <1.0, only subset of candidates are stored.
        """
        step = StepTrace(
            step_name=step_name,
            step_type=step_type,
            sample_rate=sample_rate,
        )

        step_context = StepContext(step, sample_rate)
        start_time = time.time()

        try:
            yield step_context
        except Exception as e:
            # Capture step-level errors automatically
            step_context.add_metadata("error", str(e))
            raise
        finally:
            step.duration_ms = (time.time() - start_time) * 1000
            self.run.add_step(step)

    # --- Helper Methods for Common Patterns ---

    @contextmanager
    def filter_step(self, name: str, sample_rate: float = 1.0):
        """Shortcut for a filtering step"""
        with self.step(name, "filter", sample_rate) as s:
            yield s

    @contextmanager
    def rank_step(self, name: str, sample_rate: float = 1.0):
        """Shortcut for a ranking step"""
        with self.step(name, "rank", sample_rate) as s:
            yield s

    @contextmanager
    def llm_step(self, name: str, sample_rate: float = 1.0):
        """Shortcut for an LLM call step"""
        with self.step(name, "llm_call", sample_rate) as s:
            yield s

    def set_final_output(self, output: Dict[str, Any]):
        self.run.final_output = output

    def send(self):
        """Manually send the run to the X-Ray API"""
        if self.client:
            try:
                # Use background sending to avoid blocking
                self.client.send_run_background(self.run)
            except Exception as e:
                if not self.fail_silently:
                    raise
                # Silently catch network errors so pipeline never breaks
                # In production, we would log this to a file or stderr

    def to_dict(self) -> Dict[str, Any]:
        return self.run.to_dict()


class StepContext:
    """
    Context for a single step.
    Handles sampling logic for high-cardinality data.
    """

    def __init__(self, step: StepTrace, sample_rate: float):
        self.step = step
        self.sample_rate = sample_rate
        
        # Deterministic sampling based on step ID to ensure consistency if re-run
        # But for this assignment, random float is sufficient
        import random
        self._should_sample = random.random() < sample_rate

    def set_input(self, inputs: Dict[str, Any]):
        self.step.inputs = inputs

    def set_output(self, outputs: Dict[str, Any]):
        self.step.outputs = outputs

    def set_input_candidates(self, candidates: List[Candidate]):
        """Set candidates, respecting sample rate"""
        if self._should_sample:
            self.step.input_candidates = candidates
        else:
            # FIX: If not sampling, store the count in metadata so we don't lose the "Size" context.
            # Even though we drop the list, knowing we dropped 5,000 items is crucial.
            self.step.metadata["input_count"] = len(candidates)

    def set_output_candidates(self, candidates: List[Candidate]):
        if self._should_sample:
            self.step.output_candidates = candidates

    def add_candidate_in(self, candidate: Candidate):
        if self._should_sample:
            self.step.input_candidates.append(candidate)

    def add_candidate_out(self, candidate: Candidate):
        if self._should_sample:
            self.step.output_candidates.append(candidate)

    def add_decision(
        self,
        action: str,
        reason: str,
        criteria: Optional[Dict[str, Any]] = None,
    ):
        """Always capture decisions, even if sampling candidates"""
        self.step.add_decision(action, reason, criteria)

    def add_metadata(self, key: str, value: Any):
        self.step.metadata[key] = value

    def get_summary(self) -> Dict[str, Any]:
        return self.step.summary()


class _NoOpRunContext:
    @contextmanager
    def step(self, *args, **kwargs):
        yield _NoOpStepContext()
    
    @contextmanager
    def filter_step(self, *args, **kwargs): yield _NoOpStepContext()
    @contextmanager
    def rank_step(self, *args, **kwargs): yield _NoOpStepContext()
    @contextmanager
    def llm_step(self, *args, **kwargs): yield _NoOpStepContext()

    def set_final_output(self, output): pass
    def send(self): pass
    def to_dict(self): return {}

class _NoOpStepContext:
    def set_input(self, inputs): pass
    def set_output(self, outputs): pass
    def set_input_candidates(self, candidates): pass
    def set_output_candidates(self, candidates): pass
    def add_candidate_in(self, candidate): pass
    def add_candidate_out(self, candidate): pass
    def add_decision(self, action, reason, criteria=None): pass
    def add_metadata(self, key, value): pass
    def get_summary(self): return {}
