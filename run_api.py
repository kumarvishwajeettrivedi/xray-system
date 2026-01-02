#!/usr/bin/env python3
"""
Convenience script to run the X-Ray API server.

Usage:
    python run_api.py

The API will be available at:
    - http://localhost:8000
    - Interactive docs: http://localhost:8000/docs
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting X-Ray API Server")
    print("=" * 60)
    print("\nAPI will be available at:")
    print("  - http://localhost:8000")
    print("  - Interactive docs: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop\n")
    print("=" * 60)

    uvicorn.run(
        "xray_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
