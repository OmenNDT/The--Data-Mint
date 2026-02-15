"""Generate synthetic crack X-ray images using SD 1.5 + trained LoRA.

Uses diffusers pipeline directly (no ComfyUI needed).
Generates images with random seeds for diversity.
"""

import os
import json
import random
import argparse
import logging
from pathlib import Path

import torch
from diffusers import StableDiffusionPipeline, EulerAncestralDiscreteScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
MODEL_PATH = PROJECT_ROOT / "models/checkpoints/sd-v1-5-pruned-emaonly.safetensors"
LORA_PATH = PROJECT_ROOT / "models/loras/xray_crack_lora_r32.safetensors"
OUTPUT_DIR = PROJECT_ROOT / "output/synthetic/crack"
BG_DIR = PROJECT_ROOT / "kohya-ss/training_data/reg/1_xray_clean"

PROMPT = "xray_crack, weld crack defect, radiographic image"
NEGATIVE_PROMPT = "blurry, low quality, text, watermark, color"


def generate_images(num_images: int = 50, batch_size: int = 1):
    """Generate synthetic crack X-ray images."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading SD 1.5 from {MODEL_PATH}")
    pipe = StableDiffusionPipeline.from_single_file(
        str(MODEL_PATH),
        torch_dtype=torch.float16,
        safety_checker=None,
        requires_safety_checker=False,
    )

    # Set scheduler
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipe.scheduler.config
    )

    # Load LoRA
    logger.info(f"Loading LoRA from {LORA_PATH}")
    pipe.load_lora_weights(str(LORA_PATH.parent), weight_name=LORA_PATH.name)

    pipe = pipe.to("cuda")
    pipe.enable_xformers_memory_efficient_attention()

    logger.info(f"Generating {num_images} crack images...")

    for i in range(num_images):
        seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator("cuda").manual_seed(seed)

        result = pipe(
            prompt=PROMPT,
            negative_prompt=NEGATIVE_PROMPT,
            width=512,
            height=512,
            num_inference_steps=20,
            guidance_scale=7.0,
            generator=generator,
        )

        image = result.images[0]
        img_name = f"synth_crack_{i:04d}"
        image.save(OUTPUT_DIR / f"{img_name}.png")

        # Save metadata
        metadata = {
            "seed": seed,
            "prompt": PROMPT,
            "defect_type": "crack",
            "lora": str(LORA_PATH.name),
            "steps": 20,
            "cfg": 7.0,
        }
        with open(OUTPUT_DIR / f"{img_name}.json", "w") as f:
            json.dump(metadata, f, indent=2)

        if (i + 1) % 10 == 0 or i == 0:
            logger.info(f"  Generated {i + 1}/{num_images} (seed={seed})")

    logger.info(f"Done! {num_images} images saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-images", type=int, default=50)
    # Accept --config for compatibility with pipeline launcher (ignored, uses hardcoded paths)
    parser.add_argument("--config", type=str, default=None, help="Config file (unused, for launcher compat)")
    parser.add_argument("--pilot", action="store_true", help="Pilot mode (generate fewer images)")
    args = parser.parse_args()

    num = 10 if args.pilot else args.num_images
    generate_images(num)
