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

import cv2
import numpy as np
import yaml
from PIL import Image

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from plant_hmi import plant_telemetry_emitter as telemetry
from plant_hmi.plant_setpoints import resolve as resolve_setpoint
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


def load_mask_config() -> Dict:
    """Load mask-config.yaml for dilation settings."""
    mask_config_path = Path(__file__).parent.parent / "config" / "mask-config.yaml"
    if mask_config_path.exists():
        with open(mask_config_path, "r") as f:
            return yaml.safe_load(f)
    return {}


def apply_dark_defect_convention(
    image_path: Path, annotation_mask_path: str, background_path: str = None, defect_type: str = None
):
    """
    Post-process generated image to make defects appear dark (correct RT convention).

    Two-step approach:
    1. Restore original background OUTSIDE annotation mask → eliminates LoRA/inpaint halo
    2. Darken inside annotation mask → correct RT film convention (void = dark)

    Args:
        image_path: Path to generated PNG to modify in-place
        annotation_mask_path: Path to binary annotation mask (white = defect region)
        background_path: Path to original clean background patch used for inpainting
        defect_type: Skip darkening for metallic_inclusion (dense metal = bright)
    """
    # metallic_inclusion is dense metal → absorbs more X-ray → appears bright (correct, skip)
    if defect_type == "metallic_inclusion":
        return

    try:
        img_pil = Image.open(image_path).convert("L")
        mask_pil = Image.open(annotation_mask_path).convert("L").resize(img_pil.size, Image.NEAREST)

        img = np.array(img_pil, dtype=np.float32)
        mask_arr = np.array(mask_pil, dtype=np.uint8)  # binary: 0 or 255

        # --- Step 1: Hard-replace background OUTSIDE annotation mask ---
        # Root cause of halo: LoRA generates bright seam in zone [annot_mask → inpaint_mask].
        # Wide blend_mask let 50% of halo bleed through → visible on dark backgrounds.
        # Fix: near-hard cut with sigma=1.5 (3px aliasing only) → ~97% halo replaced by bg.
        if background_path:
            bg_pil = Image.open(background_path).convert("L").resize(img_pil.size, Image.BILINEAR)
            bg = np.array(bg_pil, dtype=np.float32)

            # Minimal anti-aliasing only — NOT a wide blend. No dilation.
            keep_mask = cv2.GaussianBlur(mask_arr.astype(np.float32), (0, 0), sigmaX=1.5) / 255.0
            if keep_mask.max() > 0:
                keep_mask = keep_mask / keep_mask.max()  # normalize core to 1.0

            # Outside annotation mask → pure original background (halo eliminated)
            # Inside annotation mask → keep inpainted content (to be darkened next)
            img = img * keep_mask + bg * (1.0 - keep_mask)

        # --- Step 2: Darken defect interior to correct RT convention (void = dark) ---
        # sigma=2 → 4-5px smooth edge, no concentric rings
        darken_mask = cv2.GaussianBlur(mask_arr.astype(np.float32), (0, 0), sigmaX=2.0) / 255.0
        if darken_mask.max() > 0:
            darken_mask = darken_mask / darken_mask.max()  # normalize: core peak = 1.0

        # Per-defect darkening strength (LOF/LOP subtler: blends into background like in real RT)
        DARKEN_BY_TYPE = {
            "lack_of_fusion": 0.85,
            "lack_of_penetration": 0.78,
            "elongated_cavity": 0.65,  # Softer than default 0.92 — wormhole blends into metal
        }
        DARKEN_STRENGTH = DARKEN_BY_TYPE.get(defect_type, 0.92)
        result = img * (1.0 - darken_mask * DARKEN_STRENGTH)
        result = np.clip(result, 0, 255).astype(np.uint8)
        Image.fromarray(result, mode="L").save(str(image_path))
    except Exception as e:
        print(f"  [warn] Dark convention post-processing skipped: {e}")


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

    # Plant HMI setpoint (rule R1): resolve INSIDE this process, env > store > recipe.
    _recipe_steps = (config.get("sampler") or {}).get("steps")
    sp_sampler_steps, sp_sampler_steps_source = resolve_setpoint("sampler_steps", _recipe_steps)
    config.setdefault("sampler", {})["steps"] = sp_sampler_steps
    print(f"  SP sampler_steps={sp_sampler_steps} (source={sp_sampler_steps_source})")
    mask_config = load_mask_config()

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
    prefetcher = MaskPrefetcher(config, mask_config=mask_config)

    # Post-processing switch: default True preserves existing behaviour for old configs
    dark_convention_enabled = config.get("post_processing", {}).get("dark_convention", True)
    print(f"  {'✓' if dark_convention_enabled else '○'} Dark-convention post-processing: "
          f"{'on' if dark_convention_enabled else 'off'}")

    dilation_enabled = mask_config.get("inpaint_dilation", {}).get("enabled", False)
    if dilation_enabled:
        dil_cfg = mask_config["inpaint_dilation"]
        print(f"  ✓ Mask dilation enabled: kernel={dil_cfg['kernel_size']}px, shape={dil_cfg['kernel_shape']}")
    thermal_monitor = GPUThermalMonitor(config["thermal"])
    checkpoint_manager = CheckpointManager(config)

    # Plant HMI telemetry: wrap the expensive steps once, where they are constructed.
    # Wrappers pass results/exceptions through untouched; PLANT_TELEMETRY=0 disables.
    from batch_manager.mask_prefetch_worker_pool import _generate_mask_worker
    generate_mask = _generate_mask_worker
    dark_convention = apply_dark_defect_convention
    if telemetry.enable(f"{Path(config_path).stem}-{os.getpid()}"):
        for method, call_kind in (("upload_image", "upload"), ("queue_prompt", "queue"),
                                  ("poll_completion", "infer"), ("download_output", "download")):
            setattr(client, method, telemetry.instrument(getattr(client, method), "P-601", call_kind))
        thermal_monitor.wait_until_cool = telemetry.instrument(
            thermal_monitor.wait_until_cool, "U-901", "thermal_hold")
        generate_mask = telemetry.instrument(_generate_mask_worker, "R-201", "mask")
        dark_convention = telemetry.instrument(apply_dark_defect_convention, "R-401", "post")
        # PV (rule R2): report the value the scheduler actually holds, not the SP we passed.
        telemetry.emit_config({"key": "sampler_steps", "value": scheduler.config["sampler"]["steps"],
                               "source": sp_sampler_steps_source})

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

    # Mask generation: inline per-job (guarantees type/seed match)
    print("\n[3/7] Mask generation: inline mode (no prefetch buffer)")

    # Main loop
    print("\n[4/7] Starting main production loop...")
    print(f"  Target: {len(scheduler.jobs)} images")
    print(f"  Checkpoint interval: every {config['reliability']['checkpoint_interval']} images")
    print()

    start_time = time.time()
    retry_counts = {}
    # Cache masks per job_id so retries reuse the same mask (don't drain prefetcher buffer)
    cached_masks = {}

    while True:
        # Get next job
        job = scheduler.get_next_job()
        if job is None:
            break

        job_id = job["job_id"]
        defect_type = job["defect_type"]
        telemetry.set_job(job_id, defect_type)
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

            # Generate mask inline to guarantee type/seed match (no async buffer swap risk)
            if job_id in cached_masks:
                mask_result = cached_masks[job_id]
            else:
                bg_str = str(job["background_image"]) if job.get("background_image") else None
                mask_result = generate_mask(
                    defect_type, job["seed"], config["generation"]["resolution"],
                    mask_config.get("inpaint_dilation") if mask_config else None,
                    bg_str,
                )
                cached_masks[job_id] = mask_result

            annotation_mask_path = mask_result["annotation_path"]
            inpaint_mask_path = mask_result["inpaint_path"]

            # Upload background image
            bg_path = str(job["background_image"])
            bg_filename = client.upload_image(bg_path)

            # Upload dilated inpainting mask to ComfyUI
            mask_filename = client.upload_image(inpaint_mask_path)

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

            # Apply dark defect convention: reflect bright LoRA defects to dark.
            # Only needed for workflows that keep ControlNet — there the mask image is fed
            # as the control image, so SD paints a bright blob shaped like the mask and this
            # step inverts it. Workflows without ControlNet already produce dark, textured
            # defects, so inverting would destroy them. Default stays on for old configs.
            if dark_convention_enabled:
                dark_convention(
                    output_path, annotation_mask_path, str(job["background_image"]),
                    defect_type=job["defect_type"]
                )

            # Save original thin mask as ground truth annotation
            if config["output"]["save_masks"]:
                mask_output_path = scheduler.get_output_path(job, is_mask=True)
                Image.open(annotation_mask_path).save(mask_output_path)

            # Save metadata if configured
            if config["output"]["save_metadata"]:
                save_metadata(job, output_path, config)

            # Cleanup temp mask files
            Path(annotation_mask_path).unlink(missing_ok=True)
            Path(inpaint_mask_path).unlink(missing_ok=True)

            # Mark complete and clear mask cache for this job
            scheduler.mark_complete(job)
            cached_masks.pop(job_id, None)
            telemetry.job_outcome("ok")

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

                telemetry.job_outcome("retry", e)
                print(f"  Retrying ({retry_count}/{max_retries}) in {retry_delay}s...")
                time.sleep(retry_delay)

                # Don't advance index, retry same job
                continue

            else:
                print(f"  Failed after {max_retries} retries, skipping job")
                scheduler.mark_failed(job, str(e))
                telemetry.job_outcome("failed", e)
                cached_masks.pop(job_id, None)
                traceback.print_exc()

    # Shutdown
    print("\n[5/7] Shutting down...")

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
        default=str(Path(__file__).parent.parent / "config" / "batch-config.yaml"),
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
