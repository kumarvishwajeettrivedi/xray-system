"""
X-Ray Trace Viewer - Streamlit Frontend

A simple UI for querying and visualizing X-Ray traces.

Run with:
    streamlit run frontend/streamlit_app.py
"""

import os
import streamlit as st
import httpx
import pandas as pd
from datetime import datetime
import json

# Configuration
# API URL - Can be configured via environment variable
API_URL = os.getenv("XRAY_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="X-Ray Trace Viewer",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 X-Ray Trace Viewer")
st.markdown("**Debug multi-step pipelines by understanding WHY decisions were made**")

# Sidebar
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Recent Runs", "Run Details", "Step Analysis", "Analytics"]
)


def api_get(endpoint: str, params: dict = None):
    """Make GET request to API with caching"""
    try:
        response = httpx.get(f"{API_URL}{endpoint}", params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


# Page 1: Recent Runs
if page == "Recent Runs":
    st.header("Recent Pipeline Runs")

    col1, col2, col3 = st.columns(3)

    with col1:
        pipeline_name = st.text_input("Pipeline Name", value="")
    with col2:
        success_filter = st.selectbox("Status", ["All", "Success", "Failed"])
    with col3:
        limit = st.number_input("Limit", min_value=1, max_value=100, value=20)

    if st.button("Query Runs", type="primary"):
        params = {"limit": limit}
        if pipeline_name:
            params["pipeline_name"] = pipeline_name
        if success_filter != "All":
            params["success"] = success_filter == "Success"

        data = api_get("/api/runs", params)

        if data:
            
            # Store in session state so it persists when switching pages
            st.session_state['recent_runs'] = data['items']
            st.session_state['run_ids'] = [r['run_id'] for r in data['items']]

    # Display results from session state if available
    if 'recent_runs' in st.session_state and st.session_state['recent_runs']:
        runs = []
        for run in st.session_state['recent_runs']:
            runs.append({
                "Run ID": run['run_id'],
                "Pipeline": run['pipeline_name'],
                "Version": run['pipeline_version'],
                "Status": "✅ Success" if run['success'] else "❌ Failed",
                "Duration (ms)": f"{run.get('total_duration_ms', 0):.0f}",
                "Steps": run['step_count'],
                "Started": run['started_at'][:19],
            })

        count = len(runs)
        st.success(f"Found {count} runs")
        
        df = pd.DataFrame(runs)
        st.dataframe(df, use_container_width=True, height=400)
                
    elif 'recent_runs' in st.session_state:
        st.info("No runs found. Run a pipeline first.")


# Page 2: Run Details
elif page == "Run Details":
    st.header("Pipeline Run Details")

    run_id = st.text_input("Enter Run ID", value="")

    # Or select from recent runs
    if 'run_ids' in st.session_state:
        selected_run = st.selectbox("Or select from recent", [""] + st.session_state['run_ids'])
        if selected_run:
            run_id = selected_run

    if run_id and st.button("Fetch Details", type="primary"):
        data = api_get(f"/api/runs/{run_id}")

        if data:
            # Run metadata
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"**Pipeline:** {data['pipeline_name']}")
            with col2:
                status = "✅ Success" if data['success'] else "❌ Failed"
                st.markdown(f"**Status:** {status}")
            with col3:
                st.markdown(f"**Duration:** {data.get('total_duration_ms', 0):.0f} ms")
            with col4:
                st.markdown(f"**Steps:** {len(data['steps'])}")

            st.divider()

            # Timeline Visualization (Gantt Chart)
            st.subheader("Execution Timeline")
            
            if data['steps']:
                import plotly.express as px
                
                # Prepare data for Gantt
                timeline_data = []
                run_start = datetime.fromisoformat(data['started_at'])
                
                for step in data['steps']:
                    step_start = datetime.fromisoformat(step['timestamp'])
                    duration_s = step.get('duration_ms', 0) / 1000.0
                    step_end = step_start.replace(microsecond=int(step_start.microsecond + duration_s * 1000000))
                    
                    timeline_data.append(dict(
                        Step=step['step_name'],
                        Start=step_start,
                        Finish=step_end,
                        Type=step['step_type'],
                        Duration=f"{step.get('duration_ms', 0):.0f} ms"
                    ))
                
                if timeline_data:
                    fig = px.timeline(
                        timeline_data, 
                        x_start="Start", 
                        x_end="Finish", 
                        y="Step", 
                        color="Type",
                        hover_data=["Duration"],
                        title="Step Execution Timeline"
                    )
                    fig.update_yaxes(autorange="reversed") # Top to bottom
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # Final output
            st.subheader("Final Output")
            if data.get('final_output'):
                st.json(data['final_output'])
            else:
                st.info("No final output recorded")

            st.divider()

            # Steps
            st.subheader("Pipeline Steps")

            for i, step in enumerate(data['steps'], 1):
                with st.expander(f"**{i}. {step['step_name']}** ({step['step_type']}) - {step.get('duration_ms', 0):.0f}ms"):
                    # Metrics
                    col1, col2, col3 = st.columns(3)

                    input_count = len(step.get('input_candidates', []))
                    output_count = len(step.get('output_candidates', []))
                    reduction = ((input_count - output_count) / input_count * 100) if input_count > 0 else 0

                    with col1:
                        st.metric("Input Candidates", input_count)
                    with col2:
                        st.metric("Output Candidates", output_count)
                    with col3:
                        st.metric("Reduction", f"{reduction:.0f}%")

                    # Inputs/Outputs
                    col1, col2 = st.columns(2)
                    with col1:
                        if step.get('inputs'):
                            st.write("**Inputs:**")
                            st.json(step['inputs'])
                    with col2:
                        if step.get('outputs'):
                            st.write("**Outputs:**")
                            st.json(step['outputs'])

                    # Decisions - THE KEY PART
                    if step.get('decisions'):
                        st.write("**Decisions (Why?):**")
                        for j, decision in enumerate(step['decisions'][:10], 1):  # Show first 10
                            st.markdown(f"{j}. **{decision['action']}**: {decision['reason']}")
                            if decision.get('criteria'):
                                st.caption(f"Criteria: {json.dumps(decision['criteria'], indent=2)}")

                    # Candidates
                    if input_count > 0 or output_count > 0:
                        st.write("**Candidates:**")
                        tab1, tab2 = st.tabs(["Input", "Output"])

                        with tab1:
                            if step.get('input_candidates'):
                                candidates_df = pd.DataFrame([
                                    {
                                        "ID": c['id'],
                                        "Score": c.get('score', 'N/A'),
                                        **c.get('data', {})
                                    }
                                    for c in step['input_candidates'][:20]  # Show first 20
                                ])
                                st.dataframe(candidates_df, use_container_width=True)

                        with tab2:
                            if step.get('output_candidates'):
                                candidates_df = pd.DataFrame([
                                    {
                                        "ID": c['id'],
                                        "Score": c.get('score', 'N/A'),
                                        **c.get('data', {})
                                    }
                                    for c in step['output_candidates'][:20]
                                ])
                                st.dataframe(candidates_df, use_container_width=True)


# Page 3: Step Analysis (Cross-Pipeline)
elif page == "Step Analysis":
    st.header("Cross-Pipeline Step Analysis")
    st.markdown("Find patterns across ALL pipelines")

    col1, col2 = st.columns(2)

    with col1:
        step_type = st.selectbox(
            "Step Type",
            ["", "filter", "rank", "transform", "llm_call", "api_call", "select"]
        )
        min_reduction = st.slider("Min Reduction Rate (%)", 0, 100, 0) / 100

    with col2:
        step_name = st.text_input("Step Name (optional)", value="")
        min_duration = st.number_input("Min Duration (ms)", min_value=0, value=0)

    if st.button("Query Steps", type="primary"):
        params = {"limit": 50}
        if step_type:
            params["step_type"] = step_type
        if step_name:
            params["step_name"] = step_name
        if min_reduction > 0:
            params["min_reduction_rate"] = min_reduction
        if min_duration > 0:
            params["min_duration_ms"] = min_duration

        data = api_get("/api/steps", params)

        if data:
            st.success(f"Found {data['total']} matching steps")

            if data['items']:
                steps = []
                for step in data['items']:
                    input_count = len(step.get('input_candidates', []))
                    output_count = len(step.get('output_candidates', []))
                    reduction = ((input_count - output_count) / input_count * 100) if input_count > 0 else 0

                    steps.append({
                        "Step Name": step['step_name'],
                        "Type": step['step_type'],
                        "Input": input_count,
                        "Output": output_count,
                        "Reduction %": f"{reduction:.0f}%",
                        "Duration (ms)": f"{step.get('duration_ms', 0):.0f}",
                        "Timestamp": step['timestamp'][:19],
                    })

                df = pd.DataFrame(steps)
                st.dataframe(df, use_container_width=True)

                # Highlight aggressive filters
                if step_type == "filter":
                    st.info(f"💡 Showing filter steps - look for high reduction rates to find aggressive filters")
            else:
                st.info("No steps found matching criteria")


# Page 4: Analytics
elif page == "Analytics":
    st.header("Performance Analytics")

    pipeline_name = st.text_input("Pipeline Name (optional)", value="")

    if st.button("Get Analytics", type="primary"):
        params = {}
        if pipeline_name:
            params["pipeline_name"] = pipeline_name

        data = api_get("/api/analytics/step-performance", params)

        if data and data.get('analytics'):
            st.success(f"Analytics for {len(data['analytics'])} step types")

            # Convert to DataFrame
            analytics = []
            for item in data['analytics']:
                analytics.append({
                    "Step Name": item['step_name'],
                    "Type": item['step_type'],
                    "Count": item['count'],
                    "Avg Reduction %": f"{item['avg_reduction_rate'] * 100:.1f}%",
                    "Avg Duration (ms)": f"{item['avg_duration_ms']:.0f}",
                    "Max Reduction %": f"{item['max_reduction_rate'] * 100:.1f}%",
                    "Min Reduction %": f"{item['min_reduction_rate'] * 100:.1f}%",
                })

            df = pd.DataFrame(analytics)
            st.dataframe(df, use_container_width=True)

            # Charts
            st.subheader("Visualizations")

            col1, col2 = st.columns(2)

            with col1:
                st.bar_chart(
                    df.set_index("Step Name")["Avg Duration (ms)"].apply(lambda x: float(x)),
                    use_container_width=True
                )
                st.caption("Average Duration by Step")

            with col2:
                st.bar_chart(
                    df.set_index("Step Name")["Avg Reduction %"].apply(lambda x: float(x.replace('%', ''))),
                    use_container_width=True
                )
                st.caption("Average Reduction Rate by Step")
        else:
            st.info("No analytics data available. Run some pipelines first.")


# Footer
st.divider()
st.caption("X-Ray Trace Viewer - Debugging multi-step pipelines")
st.caption(f"API: {API_URL}")
