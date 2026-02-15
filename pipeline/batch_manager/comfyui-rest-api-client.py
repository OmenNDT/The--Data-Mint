"""
ComfyUI REST API Client

Synchronous client for ComfyUI API operations:
- Upload images to server
- Submit workflow prompts
- Poll history for completion
- Download generated results
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional

import requests


class ComfyUIClient:
    """Synchronous REST API client for ComfyUI server."""

    def __init__(self, host: str, port: int):
        """
        Initialize ComfyUI client.

        Args:
            host: ComfyUI server hostname or IP
            port: ComfyUI server port
        """
        self.base_url = f"http://{host}:{port}"

    def upload_image(self, image_path: str) -> str:
        """
        Upload image to ComfyUI server.

        Args:
            image_path: Local path to image file

        Returns:
            Filename on server

        Raises:
            RuntimeError: If upload fails
        """
        endpoint = f"{self.base_url}/upload/image"

        with open(image_path, "rb") as f:
            files = {
                "image": (Path(image_path).name, f, "image/png"),
                "type": (None, "input")
            }
            response = requests.post(endpoint, files=files, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(f"Upload failed: {response.text}")

        result = response.json()
        return result.get("name", Path(image_path).name)

    def queue_prompt(self, workflow: Dict) -> str:
        """
        Submit workflow to ComfyUI queue.

        Args:
            workflow: Complete workflow dict

        Returns:
            prompt_id for tracking

        Raises:
            RuntimeError: If submission fails
        """
        endpoint = f"{self.base_url}/prompt"
        payload = {"prompt": workflow}

        response = requests.post(endpoint, json=payload, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(f"Queue prompt failed: {response.text}")

        result = response.json()
        if "error" in result:
            raise RuntimeError(f"Workflow error: {result['error']}")

        prompt_id = result.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"No prompt_id returned: {result}")

        return prompt_id

    def poll_completion(
        self,
        prompt_id: str,
        poll_interval: float = 1.0,
        timeout: int = 300
    ) -> Dict:
        """
        Poll /history endpoint until workflow completes.

        Args:
            prompt_id: ID returned from queue_prompt
            poll_interval: Seconds between polling requests
            timeout: Max seconds to wait

        Returns:
            History entry with outputs

        Raises:
            TimeoutError: If timeout exceeded
        """
        endpoint = f"{self.base_url}/history/{prompt_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(endpoint, timeout=10)

            if response.status_code == 200:
                history = response.json()

                if prompt_id in history:
                    entry = history[prompt_id]

                    # Check if complete
                    if "outputs" in entry:
                        return entry

            time.sleep(poll_interval)

        raise TimeoutError(
            f"Workflow {prompt_id} did not complete within {timeout}s"
        )

    def download_output(self, filename: str, output_path: str):
        """
        Download generated image from ComfyUI server.

        Args:
            filename: Server filename (from history outputs)
            output_path: Local path to save image

        Raises:
            RuntimeError: If download fails
        """
        endpoint = f"{self.base_url}/view"
        params = {"filename": filename, "type": "output"}

        response = requests.get(endpoint, params=params, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(f"Download failed: {response.text}")

        # Save image
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

    def get_queue_status(self) -> Dict:
        """
        Get current queue status.

        Returns:
            Queue info dict with pending/running counts
        """
        endpoint = f"{self.base_url}/queue"
        response = requests.get(endpoint, timeout=10)

        if response.status_code == 200:
            return response.json()

        return {}

    def health_check(self) -> bool:
        """
        Check if ComfyUI server is responsive.

        Returns:
            True if server is reachable
        """
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            return response.status_code == 200
        except:
            return False
