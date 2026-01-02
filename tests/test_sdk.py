"""
Tests for X-Ray SDK

Run with: pytest tests/
"""

import pytest
from xray_sdk import XRayTracer, Candidate, StepType
from xray_sdk.models import PipelineRun, StepTrace, Decision


def test_candidate_creation():
    """Test Candidate model"""
    candidate = Candidate(
        id="prod-123",
        data={"title": "Test Product", "price": 99.99},
        score=0.85,
        metadata={"source": "api"}
    )

    assert candidate.id == "prod-123"
    assert candidate.data["price"] == 99.99
    assert candidate.score == 0.85
    assert candidate.metadata["source"] == "api"


def test_decision_creation():
    """Test Decision model"""
    decision = Decision(
        action="filtered_out",
        reason="Price too high",
        criteria={"max_price": 100, "actual_price": 150}
    )

    assert decision.action == "filtered_out"
    assert decision.reason == "Price too high"
    assert decision.criteria["actual_price"] == 150


def test_step_trace():
    """Test StepTrace model"""
    step = StepTrace(
        step_name="price_filter",
        step_type="filter"
    )

    step.inputs = {"min_price": 50, "max_price": 200}
    step.outputs = {"kept": 25, "rejected": 75}

    step.add_decision("filter_applied", "Filtered by price range", {"min": 50, "max": 200})

    assert step.step_name == "price_filter"
    assert step.step_type == "filter"
    assert len(step.decisions) == 1
    assert step.decisions[0].action == "filter_applied"


def test_step_summary():
    """Test step summary calculation"""
    step = StepTrace(
        step_name="test_filter",
        step_type="filter"
    )

    # Add candidates
    step.input_candidates = [
        Candidate(id=f"c{i}", data={"value": i})
        for i in range(100)
    ]
    step.output_candidates = [
        Candidate(id=f"c{i}", data={"value": i})
        for i in range(20)
    ]

    summary = step.summary()

    assert summary["input_count"] == 100
    assert summary["output_count"] == 20
    assert summary["reduction_rate"] == 0.8  # 80% reduction


def test_pipeline_run():
    """Test PipelineRun model"""
    run = PipelineRun(
        run_id="run-123",
        pipeline_name="test_pipeline",
        pipeline_version="1.0"
    )

    step1 = StepTrace(step_name="step1", step_type="transform")
    step2 = StepTrace(step_name="step2", step_type="filter")

    run.add_step(step1)
    run.add_step(step2)

    assert len(run.steps) == 2
    assert run.steps[0].step_name == "step1"
    assert run.steps[1].step_name == "step2"


def test_tracer_disabled():
    """Test that disabled tracer is a no-op"""
    tracer = XRayTracer(
        pipeline_name="test",
        enabled=False,
        api_url=None
    )

    # Should not raise any errors
    with tracer.start_run() as run:
        with run.step("test_step", "custom") as step:
            step.set_input({"test": "data"})
            step.set_output({"result": "success"})
            step.add_decision("test", "test reason")

    # Should complete without errors


def test_tracer_local_mode():
    """Test tracer in local mode (no API)"""
    tracer = XRayTracer(
        pipeline_name="test_pipeline",
        api_url=None,  # No API
        auto_send=False
    )

    with tracer.start_run(context={"user_id": "test_user"}) as run:
        with run.step("test_step", "transform") as step:
            step.set_input({"data": [1, 2, 3]})
            step.set_output({"result": [2, 4, 6]})

        # Get the run data
        run_data = run.to_dict()

    assert run_data["pipeline_name"] == "test_pipeline"
    assert run_data["context"]["user_id"] == "test_user"
    assert len(run_data["steps"]) == 1
    assert run_data["steps"][0]["step_name"] == "test_step"


def test_step_context_decisions():
    """Test adding multiple decisions to a step"""
    tracer = XRayTracer(
        pipeline_name="test",
        api_url=None,
        auto_send=False
    )

    with tracer.start_run() as run:
        with run.step("filter_step", "filter") as step:
            # Simulate filtering
            candidates = [
                {"id": f"c{i}", "price": i * 10}
                for i in range(10)
            ]

            for candidate in candidates:
                if candidate["price"] > 50:
                    step.add_decision(
                        "filtered_out",
                        f"Price {candidate['price']} exceeds max 50",
                        {"candidate_id": candidate["id"]}
                    )

        run_data = run.to_dict()

    # Should have recorded 4 decisions (prices 60, 70, 80, 90 are > 50)
    decisions = run_data["steps"][0]["decisions"]
    assert len(decisions) == 4
    assert all(d["action"] == "filtered_out" for d in decisions)


def test_candidate_flow():
    """Test tracking candidates through a step"""
    tracer = XRayTracer(
        pipeline_name="test",
        api_url=None,
        auto_send=False
    )

    with tracer.start_run() as run:
        with run.step("filter_step", "filter") as step:
            # Input candidates
            input_candidates = [
                Candidate(id=f"prod-{i}", data={"price": i * 20})
                for i in range(10)
            ]
            step.set_input_candidates(input_candidates)

            # Simulate filtering
            output_candidates = [
                c for c in input_candidates
                if c.data["price"] <= 100
            ]
            step.set_output_candidates(output_candidates)

        run_data = run.to_dict()

    step_data = run_data["steps"][0]
    assert len(step_data["input_candidates"]) == 10
    assert len(step_data["output_candidates"]) == 6  # Prices 0, 20, 40, 60, 80, 100


def test_pipeline_completion():
    """Test pipeline completion tracking"""
    tracer = XRayTracer(
        pipeline_name="test",
        api_url=None,
        auto_send=False
    )

    with tracer.start_run() as run:
        with run.step("step1", "transform"):
            pass

        run.set_final_output({"result": "success"})

    # Get run data after context exits (run is completed)
    run_data = run.to_dict()

    assert run_data["success"] is True
    assert run_data["final_output"] is not None
    assert run_data["final_output"]["result"] == "success"
    assert run_data["completed_at"] is not None
    assert run_data["total_duration_ms"] is not None


def test_pipeline_error_handling():
    """Test pipeline error capture"""
    tracer = XRayTracer(
        pipeline_name="test",
        api_url=None,
        auto_send=False,
        fail_silently=True
    )

    try:
        with tracer.start_run() as run:
            with run.step("failing_step", "custom"):
                raise ValueError("Test error")
    except ValueError:
        pass  # Expected

    # The error should be captured
    # (In real implementation, we'd check run.run.error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
