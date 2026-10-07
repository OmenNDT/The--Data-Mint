"""
Benchmark Image Generation Runner.

Generates images for all 5 models using identical seeds for fair comparison.
Reuses existing BatchJobScheduler with overridden deterministic seeds.

Usage:
    python3 pipeline/benchmark/run-benchmark-generation.py --model medxray
    python3 pipeline/benchmark/run-benchmark-generation.py --all
    python3 pipeline/benchmark/run-benchmark-generation.py --seeds-only
"""

import json
import random
import logging
import argparse
import sys
import time
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))

BENCHMARK_DIR = PROJECT_ROOT / "output" / "benchmark"
SEEDS_PATH = BENCHMARK_DIR / "seeds.json"
MODELS = ["baseline", "medxray", "realvis", "absreal", "cyberreal", "medxray-direct"]
DEFECTS = ["crack"]
# TODO: restore full list when training data is ready
# DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]
SEEDS_PER_DEFECT = 100
MASTER_SEED = 12345


def generate_seed_manifest() -> dict:
    """Generate deterministic seed manifest for reproducible generation."""
    rng = random.Random(MASTER_SEED)
    seeds = {}
    for defect in DEFECTS:
        seeds[defect] = [rng.randint(0, 2**32 - 1) for _ in range(SEEDS_PER_DEFECT)]
    return seeds


def save_seed_manifest(seeds: dict):
    """Save seed manifest to JSON."""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEEDS_PATH, "w") as f:
        json.dump(seeds, f, indent=2)
    logger.info(f"Saved seed manifest: {SEEDS_PATH}")
    for defect, seed_list in seeds.items():
        logger.info(f"  {defect}: {len(seed_list)} seeds (first: {seed_list[0]})")


def load_seed_manifest() -> dict:
    """Load existing seed manifest or generate new one."""
    if SEEDS_PATH.exists():
        with open(SEEDS_PATH) as f:
            return json.load(f)
    seeds = generate_seed_manifest()
    save_seed_manifest(seeds)
    return seeds


def get_batch_config_path(model: str) -> Path:
    """Return batch config path for given model."""
    if model == "baseline":
        return PROJECT_ROOT / "pipeline" / "config" / "benchmark" / "baseline-batch-config.yaml"
    return PROJECT_ROOT / "pipeline" / "config" / "benchmark" / f"{model}-batch-config.yaml"


def generate_mask(defect_type: str, seed: int, resolution: int = 512) -> tuple:
    """Generate annotation and inpainting masks for a defect type.

    Returns:
        Tuple of (annotation_path, inpaint_path) as temp file paths.
    """
    from mask_generator import (
        CrackMaskGenerator,
        PorosityMaskGenerator,
        LackOfFusionMaskGenerator,
        SlagInclusionMaskGenerator,
        UndercutMaskGenerator,
        dilate_mask_for_inpainting,
    )
    from PIL import Image

    generators = {
        "crack": CrackMaskGenerator,
        "porosity": PorosityMaskGenerator,
        "inclusion": SlagInclusionMaskGenerator,
        "lack_of_fusion": LackOfFusionMaskGenerator,
        "undercut": UndercutMaskGenerator,
    }

    gen = generators[defect_type](height=resolution, width=resolution, seed=seed)
    binary_mask, feathered_mask = gen.generate()

    # Dilate thin mask for inpainting — gives model room to generate visible defects
    inpaint_mask = dilate_mask_for_inpainting(
        binary_mask, kernel_size=11, feather_blur_radius=3
    )

    annotation_tmp = tempfile.NamedTemporaryFile(suffix="_annotation.png", delete=False)
    Image.fromarray(binary_mask, mode="L").save(annotation_tmp.name)
    annotation_tmp.close()

    # Save as RGBA — ComfyUI LoadImage extracts MASK from alpha channel,
    # not pixel values. Without alpha, MASK output is all 1.0 (bug).
    import numpy as np
    rgba = np.stack([inpaint_mask, inpaint_mask, inpaint_mask, inpaint_mask], axis=-1)
    inpaint_tmp = tempfile.NamedTemporaryFile(suffix="_inpaint.png", delete=False)
    Image.fromarray(rgba, mode="RGBA").save(inpaint_tmp.name)
    inpaint_tmp.close()

    return annotation_tmp.name, inpaint_tmp.name


def darken_background_in_mask_region(
    bg_image_path: str, inpaint_mask_path: str, target_brightness: int = 3
) -> str:
    """Darken background pixels inside the inpainting mask region.

    The VAEEncode + SetLatentNoiseMask approach preserves (1-denoise) fraction
    of the original latent.  On bright backgrounds this biases crack generation
    toward gray/white instead of the desired dark color.  Pre-darkening the
    masked region ensures the preserved latent starts dark, producing
    consistently dark cracks regardless of the original background brightness.

    Returns:
        Path to a temp file containing the modified background (PNG).
    """
    from PIL import Image
    import numpy as np

    bg = np.array(Image.open(bg_image_path).convert("RGB")).astype(np.float32)
    mask = np.array(Image.open(inpaint_mask_path).convert("L")).astype(np.float32) / 255.0

    # Expand mask to 3-channel for broadcasting
    mask_3ch = mask[:, :, np.newaxis]

    # Blend: inside mask → target_brightness, outside → original
    darkened = bg * (1.0 - mask_3ch) + target_brightness * mask_3ch
    darkened = np.clip(darkened, 0, 255).astype(np.uint8)

    tmp = tempfile.NamedTemporaryFile(suffix="_darkened_bg.png", delete=False)
    Image.fromarray(darkened, mode="RGB").save(tmp.name)
    tmp.close()
    return tmp.name


def run_generation_for_model(model: str, seeds: dict, count: int = 100, rev: str = None):
    """Run image generation for a single model with fixed seeds."""
    import yaml
    from batch_manager import BatchJobScheduler, ComfyUIClient

    config_path = get_batch_config_path(model)
    if not config_path.exists():
        logger.error(f"Config not found: {config_path}. Run generate-benchmark-configs.py first.")
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Override output directory for revision runs
    if rev:
        config["paths"]["output_base_dir"] = str(BENCHMARK_DIR / rev / model)

    # Override total images
    config["generation"]["total_images"] = count * len(DEFECTS)

    # Create scheduler (loads prompts/workflow from config paths internally)
    scheduler = BatchJobScheduler(config)

    # Filter backgrounds: only use bright images (mean >= 140) to match
    # real X-ray weld radiograph brightness (~150-190 on 0-255 scale)
    from PIL import Image
    import numpy as np

    all_bg = sorted(scheduler.background_images)
    bg_images = []
    for bg_path in all_bg:
        mean_val = np.array(Image.open(bg_path).convert("L")).mean()
        if mean_val >= 140:
            bg_images.append(bg_path)
    if not bg_images:
        logger.warning("No bright backgrounds found (mean>=140), using all")
        bg_images = all_bg
    logger.info(f"Using {len(bg_images)}/{len(all_bg)} bright backgrounds (mean>=140)")

    jobs = []
    for defect in DEFECTS:
        seed_list = seeds[defect][:count]
        for i, seed in enumerate(seed_list):
            jobs.append({
                "job_id": len(jobs),
                "defect_type": defect,
                "seed": seed,
                "background_image": bg_images[len(jobs) % len(bg_images)],
                "status": "pending",
            })

    scheduler.jobs = jobs
    scheduler.current_index = 0

    # Output directory
    output_dir = Path(config["paths"]["output_base_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    resolution = config["generation"]["resolution"]

    # Connect to ComfyUI
    host = config["comfyui"]["host"]
    port = config["comfyui"]["port"]
    client = ComfyUIClient(host, port)

    # Clear execution cache and unload models to ensure correct checkpoint loading
    client.free_memory(unload_models=True, free_memory=True)
    logger.info(f"Cleared ComfyUI cache for model switch")

    logger.info(f"Generating {len(jobs)} images for {model} -> {output_dir}")
    start_time = time.time()
    completed = 0
    skipped = 0

    for job in jobs:
        defect = job["defect_type"]
        defect_dir = output_dir / defect
        defect_dir.mkdir(parents=True, exist_ok=True)
        masks_dir = defect_dir / "masks"
        masks_dir.mkdir(parents=True, exist_ok=True)

        # Check if already generated (resume support)
        expected_prefix = f"{defect}_{job['job_id']:06d}"
        existing = list(defect_dir.glob(f"{expected_prefix}.png"))
        if existing:
            skipped += 1
            continue

        annotation_path = None
        inpaint_path = None
        try:
            # Generate mask pair using job's seed for determinism
            annotation_path, inpaint_path = generate_mask(defect, job["seed"], resolution)

            # Upload original background and inpainting mask.
            # With denoise=1.0 the masked region starts from pure noise
            # so background brightness doesn't leak into crack generation.
            # Composite step after download restores original bg outside mask.
            bg_filename = client.upload_image(str(job["background_image"]))
            mask_filename = client.upload_image(inpaint_path)

            # Build and submit workflow
            workflow = scheduler.build_workflow(job, bg_filename, mask_filename)
            prompt_id = client.queue_prompt(workflow)
            history = client.poll_completion(
                prompt_id,
                poll_interval=1.0,
                timeout=config["reliability"]["timeout_seconds"],
            )

            # Extract output filename from history
            outputs = history.get("outputs", {})
            server_filename = None
            for node_output in outputs.values():
                if "images" in node_output:
                    server_filename = node_output["images"][0]["filename"]
                    break

            if not server_filename:
                raise RuntimeError("No image output in ComfyUI history")

            # Download generated image to temp, then composite onto bright bg
            from PIL import Image
            import numpy as np

            gen_tmp = tempfile.NamedTemporaryFile(suffix="_gen.png", delete=False)
            gen_tmp.close()
            client.download_output(server_filename, gen_tmp.name)

            # Composite: use inpaint mask to blend generated crack
            # onto original bright background.  Crack region from
            # generated image, everything else from original bg.
            gen_img = np.array(Image.open(gen_tmp.name).convert("RGB")).astype(np.float32)
            orig_bg = np.array(
                Image.open(str(job["background_image"])).convert("RGB")
            ).astype(np.float32)
            blend_mask = np.array(
                Image.open(inpaint_path).convert("L")
            ).astype(np.float32) / 255.0
            blend_3ch = blend_mask[:, :, np.newaxis]

            composited = orig_bg * (1.0 - blend_3ch) + gen_img * blend_3ch
            composited = np.clip(composited, 0, 255).astype(np.uint8)

            img_path = defect_dir / f"{expected_prefix}.png"
            Image.fromarray(composited, mode="RGB").save(str(img_path))
            Path(gen_tmp.name).unlink(missing_ok=True)

            # Save annotation mask for YOLO conversion
            mask_out = masks_dir / f"{expected_prefix}_mask.png"
            Image.open(annotation_path).save(str(mask_out))

            completed += 1
            if completed % 50 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                logger.info(f"  [{model}] {completed}/{len(jobs)} ({rate:.1f} img/s)")

        except Exception as e:
            logger.error(f"  [{model}] Job {job['job_id']} failed: {e}")
        finally:
            # Cleanup temp files
            for p in [annotation_path, inpaint_path]:
                if p:
                    Path(p).unlink(missing_ok=True)

    elapsed = time.time() - start_time
    logger.info(
        f"[{model}] Done: {completed} generated, {skipped} skipped, "
        f"{elapsed:.0f}s ({elapsed/max(completed,1):.1f}s/img)"
    )

    # Save generation metadata
    metadata = {
        "model": model,
        "config_path": str(config_path),
        "total_images": completed + skipped,
        "generated": completed,
        "skipped": skipped,
        "generation_time_seconds": round(elapsed, 1),
        "seeds_per_defect": count,
    }
    meta_path = output_dir / "generation-metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Benchmark image generation")
    parser.add_argument("--model", type=str, help="Model to generate for")
    parser.add_argument("--all", action="store_true", help="Generate for all models")
    parser.add_argument("--seeds-only", action="store_true", help="Only generate seed manifest")
    parser.add_argument("--count", type=int, default=100, help="Images per defect (default: 100)")
    parser.add_argument("--rev", type=str, default=None, help="Revision tag (e.g. rev02) — overrides output to benchmark/{rev}/{model}")
    args = parser.parse_args()

    seeds = load_seed_manifest()

    if args.seeds_only:
        return

    models_to_run = []
    if args.all:
        models_to_run = MODELS
    elif args.model:
        if args.model not in MODELS:
            logger.error(f"Unknown model: {args.model}. Options: {MODELS}")
            return
        models_to_run = [args.model]
    else:
        parser.print_help()
        return

    for model in models_to_run:
        run_generation_for_model(model, seeds, args.count, rev=args.rev)


if __name__ == "__main__":
    main()
