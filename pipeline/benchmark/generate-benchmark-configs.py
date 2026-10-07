"""
Generate benchmark batch configs and prompt templates for all 4 models.

Creates per-model:
- pipeline/comfyui-workflows/benchmark/defect-type-prompt-templates-{model}.yaml
- pipeline/config/benchmark/{model}-batch-config.yaml

Usage:
    python3 pipeline/benchmark/generate-benchmark-configs.py [--dry-run]
"""

import json
import logging
import argparse
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
REGISTRY_PATH = PROJECT_ROOT / "models" / "checkpoints" / "benchmark" / "model-registry.json"

PROD_PROMPTS = PROJECT_ROOT / "pipeline" / "comfyui-workflows" / "defect-type-prompt-templates.yaml"
PROD_BATCH = PROJECT_ROOT / "pipeline" / "config" / "batch-config.yaml"

BENCHMARK_PROMPTS_DIR = PROJECT_ROOT / "pipeline" / "comfyui-workflows" / "benchmark"
BENCHMARK_BATCH_DIR = PROJECT_ROOT / "pipeline" / "config" / "benchmark"

STD_WORKFLOW = PROJECT_ROOT / "pipeline" / "comfyui-workflows" / "sd15-lora-controlnet-inpaint-single-defect-workflow.json"
EXT_VAE_WORKFLOW = BENCHMARK_PROMPTS_DIR / "sd15-lora-controlnet-inpaint-external-vae-workflow.json"

DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

# LoRA name mapping: defect -> lora base name (without model suffix)
LORA_BASE_NAMES = {
    "crack": "xray_crack",
    "porosity": "xray_porosity",
    "inclusion": "xray_inclusion",
    "lack_of_fusion": "xray_lof",
    "undercut": "xray_undercut",
}


def load_registry() -> dict:
    """Load model registry JSON."""
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def generate_prompt_template(prod_prompts: dict, model_key: str, model_info: dict) -> dict:
    """Generate model-specific prompt template from production template."""
    import copy
    prompts = copy.deepcopy(prod_prompts)

    # Update LoRA names to model-specific versions
    for defect in DEFECTS:
        if defect in prompts["defect_prompts"]:
            base = LORA_BASE_NAMES[defect]
            prompts["defect_prompts"][defect]["lora_name"] = (
                f"{base}_{model_key}_lora_r32.safetensors"
            )

    # Update model paths
    prompts["model_paths"] = {
        "checkpoint": model_info["checkpoint_path"],
        "controlnet": "controlnet/control_v11p_sd15_inpaint.pth",
        "lora_dir": "loras/",
    }
    if model_info.get("vae"):
        prompts["model_paths"]["vae"] = model_info["vae"]

    return prompts


def generate_batch_config(prod_batch: dict, model_key: str, model_info: dict) -> dict:
    """Generate model-specific batch config from production template."""
    import copy
    config = copy.deepcopy(prod_batch)

    # Update prompts and workflow paths
    prompts_path = str(BENCHMARK_PROMPTS_DIR / f"defect-type-prompt-templates-{model_key}.yaml")
    config["comfyui"]["prompts_path"] = prompts_path

    # Use external VAE workflow for models that need it
    if model_info.get("vae"):
        config["comfyui"]["workflow_path"] = str(EXT_VAE_WORKFLOW)
    else:
        config["comfyui"]["workflow_path"] = str(STD_WORKFLOW)

    # Equal defect distribution for benchmarking
    config["generation"]["defect_distribution"] = {d: 0.2 for d in DEFECTS}
    config["generation"]["total_images"] = 500

    # Model-specific LoRA names
    config["lora_models"] = {}
    for defect in DEFECTS:
        base = LORA_BASE_NAMES[defect]
        config["lora_models"][defect] = f"{base}_{model_key}_lora_r32.safetensors"

    # Benchmark output directory
    config["paths"]["output_base_dir"] = str(
        PROJECT_ROOT / "output" / "benchmark" / model_key
    )

    return config


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark configs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = load_registry()

    with open(PROD_PROMPTS) as f:
        prod_prompts = yaml.safe_load(f)
    with open(PROD_BATCH) as f:
        prod_batch = yaml.safe_load(f)

    BENCHMARK_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    BENCHMARK_BATCH_DIR.mkdir(parents=True, exist_ok=True)

    # Generate for each benchmark model (skip baseline)
    benchmark_models = {k: v for k, v in registry.items() if k != "baseline"}

    for model_key, model_info in benchmark_models.items():
        # Prompt template
        prompts = generate_prompt_template(prod_prompts, model_key, model_info)
        prompts_path = BENCHMARK_PROMPTS_DIR / f"defect-type-prompt-templates-{model_key}.yaml"

        # Batch config
        batch = generate_batch_config(prod_batch, model_key, model_info)
        batch_path = BENCHMARK_BATCH_DIR / f"{model_key}-batch-config.yaml"

        if args.dry_run:
            logger.info(f"[DRY] {model_key}: {prompts_path.name}, {batch_path.name}")
            continue

        with open(prompts_path, "w") as f:
            yaml.dump(prompts, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Created: {prompts_path}")

        with open(batch_path, "w") as f:
            yaml.dump(batch, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Created: {batch_path}")

    # Also create baseline benchmark batch config (uses production prompts/workflow)
    baseline_batch = generate_batch_config(prod_batch, "baseline", registry["baseline"])
    baseline_batch["comfyui"]["prompts_path"] = str(PROD_PROMPTS)
    baseline_batch["comfyui"]["workflow_path"] = str(STD_WORKFLOW)
    # Baseline uses production LoRA names
    baseline_batch["lora_models"] = prod_batch["lora_models"]
    baseline_path = BENCHMARK_BATCH_DIR / "baseline-batch-config.yaml"

    if not args.dry_run:
        with open(baseline_path, "w") as f:
            yaml.dump(baseline_batch, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Created: {baseline_path}")

    logger.info(f"\nGenerated configs for {len(benchmark_models)} benchmark models + baseline")


if __name__ == "__main__":
    main()
