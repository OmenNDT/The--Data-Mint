#!/usr/bin/env python3
"""
Batch Production Main Entry Point

Orchestrates automated synthetic X-ray defect image generation:
1. Load config and check ComfyUI connection
2. Initialize scheduler, mask prefetcher, thermal monitor, checkpoint manager
3. Resume from checkpoint if exists
4. Pre-fill mask buffer
5. Main loop: thermal check -> get mask -> upload -> queue -> poll -> save
6. Track progress, handle errors, save checkpoints
7. Generate final report
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Dict

import yaml
from PIL import Image

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from batch_manager import (
    ComfyUIClient,
    BatchJobScheduler,
    MaskPrefetcher,
    GPUThermalMonitor,
    CheckpointManager
)


def load_config(config_path: str) -> Dict:
    """Load batch configuration from YAML file."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


def save_metadata(job: Dict, output_path: Path, config: Dict):
    """Save job metadata as JSON alongside output image."""
    metadata = {
        "job_id": job["job_id"],
        "defect_type": job["defect_type"],
        "seed": job["seed"],
        "background_image": str(job["background_image"]),
        "resolution": config["generation"]["resolution"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    metadata_path = output_path.with_suffix(".json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def run_batch_production(config_path: str, pilot_mode: bool = False, auto_resume: bool = False):
    """
    Main batch production loop.

    Args:
        config_path: Path to batch-config.yaml
        pilot_mode: If True, run with only 5 images (1 per defect type)
        auto_resume: If True, auto-resume from checkpoint without prompting.
                     If False and running non-interactively, start fresh.
    """
    # Load config
    print("="*60)
    print("Batch Production Pipeline")
    print("="*60)

    config = load_config(config_path)

    # Pilot mode: reduce total images but keep user's defect distribution
    if pilot_mode:
        dist = config["generation"].get("defect_distribution", {})
        active = {k: v for k, v in dist.items() if v > 0}
        count = max(len(active), 1)
        print(f"\n[PILOT MODE] Generating {count} images ({', '.join(active.keys())})")
        config["generation"]["total_images"] = count

    # Create output directories
    for path_key in ["output_base_dir", "checkpoint_dir", "logs_dir"]:
        Path(config["paths"][path_key]).mkdir(parents=True, exist_ok=True)

    # Initialize components
    print("\n[1/7] Initializing components...")

    client = ComfyUIClient(
        config["comfyui"]["host"],
        config["comfyui"]["port"]
    )

    # Health check
    print(f"  Checking ComfyUI server at {client.base_url}...")
    if not client.health_check():
        raise RuntimeError(f"ComfyUI server not reachable at {client.base_url}")
    print(f"  ✓ ComfyUI server OK")

    scheduler = BatchJobScheduler(config)
    prefetcher = MaskPrefetcher(config)
    thermal_monitor = GPUThermalMonitor(config["thermal"])
    checkpoint_manager = CheckpointManager(config)

    # Check for existing checkpoint
    print("\n[2/7] Checking for checkpoint...")
    checkpoint = checkpoint_manager.load_checkpoint()

    if checkpoint:
        if auto_resume:
            scheduler.restore_state(checkpoint)
            print(f"  ✓ Auto-resumed from checkpoint")
        elif sys.stdin.isatty():
            response = input("  Resume from checkpoint? (y/n): ")
            if response.lower() == 'y':
                scheduler.restore_state(checkpoint)
                print(f"  ✓ Resumed from checkpoint")
            else:
                checkpoint_manager.backup_checkpoint()
                print(f"  Checkpoint backed up, starting fresh")
        else:
            checkpoint_manager.backup_checkpoint()
            print(f"  Non-interactive mode, starting fresh (checkpoint backed up)")

    # Pre-fill mask buffer
    print("\n[3/7] Pre-filling mask buffer...")
    prefetcher.prefill_buffer(scheduler.jobs)

    # Main loop
    print("\n[4/7] Starting main production loop...")
    print(f"  Target: {len(scheduler.jobs)} images")
    print(f"  Checkpoint interval: every {config['reliability']['checkpoint_interval']} images")
    print()

    start_time = time.time()
    retry_counts = {}

    while True:
        # Get next job
        job = scheduler.get_next_job()
        if job is None:
            break

        job_id = job["job_id"]
        defect_type = job["defect_type"]
        retry_count = retry_counts.get(job_id, 0)

        # Progress info
        completed, total, percentage = scheduler.get_progress()
        elapsed = time.time() - start_time
        rate = completed / elapsed if elapsed > 0 else 0
        eta_seconds = (total - completed) / rate if rate > 0 else 0

        print(f"[{completed}/{total}] ({percentage:.1f}%) Job {job_id} | {defect_type} | ETA: {eta_seconds/3600:.1f}h")

        try:
            # Thermal check
            if thermal_monitor.check_and_throttle():
                thermal_monitor.wait_until_cool()

            # Get pre-generated mask
            mask_path = prefetcher.get_next_mask()

            if mask_path is None:
                raise RuntimeError("Mask prefetcher returned None")

            # Submit next mask generation task
            next_job_idx = scheduler.current_index + prefetcher.max_buffer_size
            if next_job_idx < len(scheduler.jobs):
                next_job = scheduler.jobs[next_job_idx]
                prefetcher.submit_prefetch(next_job["defect_type"], next_job["seed"])

            # Upload background image
            bg_path = str(job["background_image"])
            bg_filename = client.upload_image(bg_path)

            # Upload mask
            mask_filename = client.upload_image(mask_path)

            # Build workflow
            workflow = scheduler.build_workflow(job, bg_filename, mask_filename)

            # Queue prompt
            prompt_id = client.queue_prompt(workflow)

            # Poll completion
            history = client.poll_completion(
                prompt_id,
                poll_interval=1.0,
                timeout=config["reliability"]["timeout_seconds"]
            )

            # Extract output filename
            outputs = history.get("outputs", {})
            save_image_node = None

            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    save_image_node = node_output
                    break

            if not save_image_node:
                raise RuntimeError("No image output in history")

            server_filename = save_image_node["images"][0]["filename"]

            # Download result
            output_path = scheduler.get_output_path(job, is_mask=False)
            client.download_output(server_filename, str(output_path))

            # Save mask copy if configured
            if config["output"]["save_masks"]:
                mask_output_path = scheduler.get_output_path(job, is_mask=True)
                Image.open(mask_path).save(mask_output_path)

            # Save metadata if configured
            if config["output"]["save_metadata"]:
                save_metadata(job, output_path, config)

            # Cleanup temp mask file
            Path(mask_path).unlink()

            # Mark complete
            scheduler.mark_complete(job)

            # Checkpoint
            if checkpoint_manager.should_checkpoint(scheduler.completed_count):
                checkpoint_manager.save_checkpoint(scheduler.get_state())

            print(f"  ✓ Saved to: {output_path}")

        except Exception as e:
            print(f"  ✗ Error: {e}")

            # Retry logic
            max_retries = config["reliability"]["max_retries"]

            if retry_count < max_retries:
                retry_count += 1
                retry_counts[job_id] = retry_count
                retry_delay = config["reliability"]["retry_delay_seconds"]

                print(f"  Retrying ({retry_count}/{max_retries}) in {retry_delay}s...")
                time.sleep(retry_delay)

                # Don't advance index, retry same job
                continue

            else:
                print(f"  Failed after {max_retries} retries, skipping job")
                scheduler.mark_failed(job, str(e))
                traceback.print_exc()

    # Shutdown
    print("\n[5/7] Shutting down...")
    prefetcher.shutdown()

    # Final checkpoint
    print("\n[6/7] Saving final state...")
    checkpoint_manager.save_checkpoint(scheduler.get_state())

    # Report
    print("\n[7/7] Generation complete!")
    print("="*60)

    completed, total, percentage = scheduler.get_progress()
    elapsed = time.time() - start_time

    print(f"\nResults:")
    print(f"  Total images: {completed}/{total}")
    print(f"  Success rate: {percentage:.1f}%")
    print(f"  Failed jobs: {len(scheduler.failed_jobs)}")
    print(f"  Elapsed time: {elapsed/3600:.2f} hours")
    print(f"  Throughput: {completed/(elapsed/3600):.0f} images/hour")

    if scheduler.failed_jobs:
        print(f"\nFailed jobs:")
        for job in scheduler.failed_jobs:
            print(f"  Job {job['job_id']} ({job['defect_type']}): {job.get('error', 'unknown')}")

    # Cleanup checkpoint if 100% complete
    if completed == total:
        checkpoint_manager.delete_checkpoint()

    print(f"\nOutput directory: {config['paths']['output_base_dir']}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Batch production pipeline for synthetic X-ray defect images"
    )
    parser.add_argument(
        "--config",
        default="/mnt/e/The Data Mint/pipeline/config/batch-config.yaml",
        help="Path to batch config YAML file"
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Run pilot mode (5 images, 1 per defect type)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Auto-resume from checkpoint without prompting"
    )

    args = parser.parse_args()

    try:
        run_batch_production(args.config, pilot_mode=args.pilot, auto_resume=args.resume)
        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Progress saved to checkpoint.")
        return 130

    except Exception as e:
        print(f"\nFatal error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
