#!/usr/bin/env python3
"""
Test Workflow Building Logic

Validates that workflows can be built correctly from config without running generation.
"""

import sys
import json
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from batch_manager import BatchJobScheduler, ComfyUIClient


def test_workflow_build():
    """Test workflow building from config."""
    print("Testing workflow build logic...")
    print("="*60)

    # Load config
    config_path = "/mnt/e/The Data Mint/pipeline/config/batch-config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Override for test
    config["generation"]["total_images"] = 5
    config["generation"]["defect_distribution"] = {
        "crack": 0.2,
        "porosity": 0.2,
        "inclusion": 0.2,
        "lack_of_fusion": 0.2,
        "undercut": 0.2
    }

    # Initialize scheduler
    print("\n1. Initializing scheduler...")
    scheduler = BatchJobScheduler(config)
    print(f"   Created {len(scheduler.jobs)} jobs")

    # Test workflow building for each defect type
    print("\n2. Testing workflow building...")

    for job in scheduler.jobs:
        defect_type = job["defect_type"]
        print(f"\n   Testing {defect_type}...")

        # Build workflow
        workflow = scheduler.build_workflow(
            job,
            background_filename="test_bg.png",
            mask_filename="test_mask.png"
        )

        # Validate workflow structure
        assert "2" in workflow, "Missing LoRA node"
        assert "3" in workflow, "Missing positive prompt node"
        assert "5" in workflow, "Missing background load node"
        assert "6" in workflow, "Missing mask load node"
        assert "10" in workflow, "Missing sampler node"
        assert "12" in workflow, "Missing save node"

        # Check LoRA name
        lora_name = workflow["2"]["inputs"]["lora_name"]
        print(f"     LoRA: {lora_name}")

        # Check prompt
        prompt = workflow["3"]["inputs"]["text"]
        print(f"     Prompt: {prompt[:60]}...")

        # Check seed
        seed = workflow["10"]["inputs"]["seed"]
        print(f"     Seed: {seed}")

        # Check sampler config
        steps = workflow["10"]["inputs"]["steps"]
        cfg = workflow["10"]["inputs"]["cfg"]
        print(f"     Sampler: {steps} steps, CFG {cfg}")

    print("\n3. Testing client health check...")
    client = ComfyUIClient(
        config["comfyui"]["host"],
        config["comfyui"]["port"]
    )

    if client.health_check():
        print("   ✓ ComfyUI server is reachable")
    else:
        print("   ✗ ComfyUI server is NOT reachable")

    print("\n" + "="*60)
    print("✓ All tests passed!")


if __name__ == "__main__":
    test_workflow_build()
