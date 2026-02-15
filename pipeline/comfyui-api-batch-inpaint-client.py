#!/usr/bin/env python3
"""
ComfyUI API Client for Batch Inpainting
========================================

This client automates defect inpainting by:
1. Loading workflow template JSON
2. Substituting dynamic parameters (LoRA, images, seed)
3. Uploading images to ComfyUI
4. Submitting workflow via REST API
5. Polling for completion
6. Downloading generated results

Usage:
    python comfyui-api-batch-inpaint-client.py \
        --background /path/to/clean.png \
        --mask /path/to/mask.png \
        --defect-type crack \
        --output /path/to/output.png \
        --seed 42
"""

import argparse
import json
import os
import random
import time
from pathlib import Path
from typing import Dict, Optional

import requests
import yaml
from PIL import Image


class ComfyUIInpaintClient:
    """Client for ComfyUI API batch inpainting operations."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8188",
        workflow_path: str = None,
        prompts_path: str = None,
    ):
        self.server_url = server_url.rstrip("/")

        # Default paths
        script_dir = Path(__file__).parent
        self.workflow_path = workflow_path or str(
            script_dir / "comfyui-workflows" / "sd15-lora-controlnet-inpaint-batch-api-workflow.json"
        )
        self.prompts_path = prompts_path or str(
            script_dir / "comfyui-workflows" / "defect-type-prompt-templates.yaml"
        )

        # Load templates
        with open(self.workflow_path, "r") as f:
            self.workflow_template = json.load(f)

        with open(self.prompts_path, "r") as f:
            self.prompts_config = yaml.safe_load(f)

    def upload_image(self, image_path: str, image_type: str = "input") -> str:
        """
        Upload image to ComfyUI server.

        Args:
            image_path: Local path to image file
            image_type: Type of upload ("input" or "mask")

        Returns:
            Filename on server
        """
        endpoint = f"{self.server_url}/upload/image"

        with open(image_path, "rb") as f:
            files = {
                "image": (Path(image_path).name, f, "image/png"),
                "type": (None, image_type)
            }
            response = requests.post(endpoint, files=files)

        if response.status_code != 200:
            raise RuntimeError(f"Upload failed: {response.text}")

        result = response.json()
        return result.get("name", Path(image_path).name)

    def substitute_workflow_params(
        self,
        defect_type: str,
        background_filename: str,
        mask_filename: str,
        seed: int,
        output_prefix: str = "defect_output",
    ) -> Dict:
        """
        Substitute template placeholders with actual values.

        Args:
            defect_type: One of: crack, porosity, inclusion, lack_of_fusion, undercut
            background_filename: Filename of uploaded background image
            mask_filename: Filename of uploaded mask image
            seed: Random seed for reproducibility
            output_prefix: Prefix for saved output images

        Returns:
            Complete workflow dict with substituted values
        """
        if defect_type not in self.prompts_config["defect_prompts"]:
            raise ValueError(
                f"Unknown defect type: {defect_type}. "
                f"Valid types: {list(self.prompts_config['defect_prompts'].keys())}"
            )

        defect_config = self.prompts_config["defect_prompts"][defect_type]

        # Deep copy workflow template
        workflow = json.loads(json.dumps(self.workflow_template))

        # Substitute placeholders
        workflow_str = json.dumps(workflow)
        substitutions = {
            "{{LORA_NAME}}": defect_config["lora_name"],
            "{{POSITIVE_PROMPT}}": defect_config["positive"],
            "{{BACKGROUND_IMAGE}}": background_filename,
            "{{MASK_IMAGE}}": mask_filename,
            "{{SEED}}": str(seed),
            "{{OUTPUT_PREFIX}}": output_prefix,
        }

        for placeholder, value in substitutions.items():
            workflow_str = workflow_str.replace(placeholder, value)

        # Also update numeric values (LoRA/ControlNet strength, denoise)
        workflow = json.loads(workflow_str)
        workflow["2"]["inputs"]["strength_model"] = defect_config.get("lora_strength", 0.7)
        workflow["2"]["inputs"]["strength_clip"] = defect_config.get("lora_strength", 0.7)
        workflow["9"]["inputs"]["strength"] = defect_config.get("controlnet_strength", 0.8)
        workflow["10"]["inputs"]["denoise"] = defect_config.get("denoise", 0.85)

        return workflow

    def queue_prompt(self, workflow: Dict) -> str:
        """
        Submit workflow to ComfyUI queue.

        Args:
            workflow: Complete workflow dict

        Returns:
            prompt_id for tracking
        """
        endpoint = f"{self.server_url}/prompt"
        payload = {"prompt": workflow}

        response = requests.post(endpoint, json=payload)

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
        self, prompt_id: str, poll_interval: float = 1.0, timeout: int = 300
    ) -> Dict:
        """
        Poll /history endpoint until workflow completes.

        Args:
            prompt_id: ID returned from queue_prompt
            poll_interval: Seconds between polling requests
            timeout: Max seconds to wait before raising timeout error

        Returns:
            History entry with outputs
        """
        endpoint = f"{self.server_url}/history/{prompt_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(endpoint)

            if response.status_code == 200:
                history = response.json()

                if prompt_id in history:
                    entry = history[prompt_id]

                    # Check if complete
                    if "outputs" in entry:
                        return entry

            time.sleep(poll_interval)

        raise TimeoutError(f"Workflow {prompt_id} did not complete within {timeout}s")

    def download_output(self, filename: str, output_path: str):
        """
        Download generated image from ComfyUI server.

        Args:
            filename: Server filename (from history outputs)
            output_path: Local path to save image
        """
        endpoint = f"{self.server_url}/view"
        params = {"filename": filename, "type": "output"}

        response = requests.get(endpoint, params=params)

        if response.status_code != 200:
            raise RuntimeError(f"Download failed: {response.text}")

        # Save image
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

    def inpaint(
        self,
        background_path: str,
        mask_path: str,
        defect_type: str,
        output_path: str,
        seed: Optional[int] = None,
        poll_interval: float = 1.0,
        timeout: int = 300,
    ) -> str:
        """
        Complete inpainting pipeline: upload, queue, poll, download.

        Args:
            background_path: Local path to clean background image
            mask_path: Local path to binary mask image
            defect_type: Defect type (crack, porosity, etc.)
            output_path: Local path to save result
            seed: Random seed (None = random)
            poll_interval: Polling interval in seconds
            timeout: Max wait time in seconds

        Returns:
            Path to downloaded output image
        """
        print(f"[1/5] Uploading background: {background_path}")
        bg_filename = self.upload_image(background_path, "input")

        print(f"[2/5] Uploading mask: {mask_path}")
        mask_filename = self.upload_image(mask_path, "input")

        print(f"[3/5] Building workflow for defect type: {defect_type}")
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        output_prefix = Path(output_path).stem
        workflow = self.substitute_workflow_params(
            defect_type=defect_type,
            background_filename=bg_filename,
            mask_filename=mask_filename,
            seed=seed,
            output_prefix=output_prefix,
        )

        print(f"[4/5] Queueing workflow (seed={seed})")
        prompt_id = self.queue_prompt(workflow)
        print(f"    Prompt ID: {prompt_id}")

        print(f"[5/5] Polling for completion...")
        history = self.poll_completion(prompt_id, poll_interval, timeout)

        # Extract output filename from history
        outputs = history.get("outputs", {})
        save_image_node = None

        # Find SaveImage node output (node ID "12" in our workflow)
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                save_image_node = node_output
                break

        if not save_image_node:
            raise RuntimeError(f"No image output found in history: {history}")

        server_filename = save_image_node["images"][0]["filename"]

        print(f"    Downloading: {server_filename}")
        self.download_output(server_filename, output_path)

        print(f"    Saved to: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description="ComfyUI API client for batch defect inpainting"
    )
    parser.add_argument(
        "--background",
        required=True,
        help="Path to clean background image (512x512 PNG)",
    )
    parser.add_argument(
        "--mask",
        required=True,
        help="Path to binary mask image (512x512 PNG, white=defect region)",
    )
    parser.add_argument(
        "--defect-type",
        required=True,
        choices=["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"],
        help="Type of defect to inpaint",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to save output image",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (default: random)",
    )
    parser.add_argument(
        "--server-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI server URL (default: http://127.0.0.1:8188)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max wait time in seconds (default: 300)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.background).exists():
        print(f"Error: Background image not found: {args.background}")
        return 1

    if not Path(args.mask).exists():
        print(f"Error: Mask image not found: {args.mask}")
        return 1

    # Run inpainting
    try:
        client = ComfyUIInpaintClient(server_url=args.server_url)
        output_path = client.inpaint(
            background_path=args.background,
            mask_path=args.mask,
            defect_type=args.defect_type,
            output_path=args.output,
            seed=args.seed,
            timeout=args.timeout,
        )
        print(f"\n✓ Success! Output saved to: {output_path}")
        return 0

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
