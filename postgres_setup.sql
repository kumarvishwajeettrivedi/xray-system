CREATE DATABASE xray_db;


\c xray_db;

CREATE TABLE pipeline_runs (
    run_id VARCHAR(255) PRIMARY KEY,
    pipeline_name VARCHAR(255) NOT NULL,
    pipeline_version VARCHAR(255) NOT NULL,
    success BOOLEAN DEFAULT TRUE,
    error TEXT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    total_duration_ms FLOAT,
    context JSONB,
    tags JSONB,
    final_output JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE step_traces (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    step_name VARCHAR(255) NOT NULL,
    step_type VARCHAR(255) NOT NULL,
    duration_ms FLOAT,
    timestamp TIMESTAMP NOT NULL,
    input_count INTEGER DEFAULT 0,
    output_count INTEGER DEFAULT 0,
    reduction_rate FLOAT DEFAULT 0.0,
    inputs JSONB,
    outputs JSONB,
    input_candidates JSONB,
    output_candidates JSONB,
    decisions JSONB,
    step_metadata JSONB,
    sample_rate FLOAT DEFAULT 1.0
);

CREATE INDEX idx_pipeline_runs_name ON pipeline_runs(pipeline_name);
CREATE INDEX idx_pipeline_runs_version ON pipeline_runs(pipeline_version);
CREATE INDEX idx_pipeline_runs_success ON pipeline_runs(success);
CREATE INDEX idx_pipeline_runs_created ON pipeline_runs(created_at);
CREATE INDEX idx_pipeline_runs_name_created ON pipeline_runs(pipeline_name, created_at);
CREATE INDEX idx_pipeline_runs_name_success ON pipeline_runs(pipeline_name, success);

CREATE INDEX idx_step_traces_run_id ON step_traces(run_id);
CREATE INDEX idx_step_traces_step_name ON step_traces(step_name);
CREATE INDEX idx_step_traces_step_type ON step_traces(step_type);
CREATE INDEX idx_step_traces_duration ON step_traces(duration_ms);
CREATE INDEX idx_step_traces_input_count ON step_traces(input_count);
CREATE INDEX idx_step_traces_output_count ON step_traces(output_count);
CREATE INDEX idx_step_traces_reduction_rate ON step_traces(reduction_rate);
CREATE INDEX idx_step_traces_type_reduction ON step_traces(step_type, reduction_rate);
CREATE INDEX idx_step_traces_name_duration ON step_traces(step_name, duration_ms);
CREATE INDEX idx_step_traces_run_timestamp ON step_traces(run_id, timestamp);

CREATE INDEX idx_pipeline_runs_context ON pipeline_runs USING GIN (context);
CREATE INDEX idx_step_traces_decisions ON step_traces USING GIN (decisions);
CREATE INDEX idx_step_traces_metadata ON step_traces USING GIN (step_metadata);
