from setuptools import setup, find_packages

setup(
    name="xray-sdk",
    version="0.1.0",
    description="X-Ray: Observability for non-deterministic pipelines",
    author="X-Ray Team",
    packages=find_packages(include=["xray_sdk", "xray_sdk.*"]),
    install_requires=[
        "httpx>=0.25.0",
    ],
    python_requires=">=3.9",
)
