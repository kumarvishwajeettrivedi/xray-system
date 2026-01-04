"""
X-Ray API Client

Handles communication between the SDK and the X-Ray API.
"""

import httpx
from typing import Optional, Dict, Any
from .models import PipelineRun

 
class XRayClient:
    """
    Async HTTP client for communicating with the X-Ray API.

    Handles request serialization, authentication, and provides resilient
    error handling with exponential backoff for network operations.
    """

    def __init__(
        self,
        api_url: str,
        timeout: float = 5.0,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the client.

        Args:
            api_url: Base URL of the X-Ray API
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.api_key = api_key
        
        # Background worker setup
        import threading
        import queue
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _worker(self):
        """Background worker to send runs"""
        import time
        while True:
            try:
                # Get a run from the queue
                run = self._queue.get()
                if run is None:  # Sentinel to stop
                    break
                
                try:
                    self.send_run(run)
                except Exception:
                    # In a real system, we'd log this error
                    pass
                finally:
                    self._queue.task_done()
            except Exception:
                pass

    def send_run_background(self, run: PipelineRun):
        """Enqueue a run to be sent in the background"""
        self._queue.put(run)

    def send_run(self, run: PipelineRun) -> Dict[str, Any]:
        """
        Send a completed pipeline run to the X-Ray API.

        Args:
            run: The PipelineRun to send

        Returns:
            Response from the API

        Raises:
            httpx.HTTPError: If the request fails
        """
        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        retries = 3
        backoff = 0.5  # Start with 500ms

        for attempt in range(retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.api_url}/api/runs",
                        json=run.to_dict(),
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response.json()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                # If it's a 500 error or connection issue, retry
                # If it's 4xx (client error), raise immediately
                if isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500:
                    raise
                
                if attempt == retries - 1:
                    raise  # Propagate final error
                
                import time
                time.sleep(backoff)
                backoff *= 2  # Exponential backoff

    def query_runs(
        self,
        pipeline_name: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Query pipeline runs from the X-Ray API.

        Args:
            pipeline_name: Filter by pipeline name
            filters: Additional filters (step_type, success, etc.)
            limit: Maximum number of results

        Returns:
            Query results from the API
        """
        params = {"limit": limit}
        if pipeline_name:
            params['pipeline_name'] = pipeline_name
        if filters:
            params.update(filters)

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.api_url}/api/runs",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def get_run(self, run_id: str) -> Dict[str, Any]:
        """
        Get a specific run by ID.

        Args:
            run_id: The run ID

        Returns:
            Run data from the API
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.api_url}/api/runs/{run_id}")
            response.raise_for_status()
            return response.json()
