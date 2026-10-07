"""
Generate 20 TOML training configs (5 defects x 4 base models) for benchmark.

Reads existing production configs as templates. Only modifies:
- pretrained_model_name_or_path
- output_dir, output_name, log_prefix
- save_every_n_epochs (set to 5 for epoch 10/15/20 checkpoints)

Usage:
    python3 pipeline/benchmark/generate-training-configs.py [--dry-run]
"""

import re
import logging
import argparse
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
CONFIGS_DIR = PROJECT_ROOT / "kohya-ss" / "configs"
BENCHMARK_CONFIGS_DIR = CONFIGS_DIR / "benchmark"
BENCHMARK_OUTPUT_DIR = PROJECT_ROOT / "kohya-ss" / "output" / "benchmark"

DEFECTS = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

MODELS = {
    "medxray": "medical-xray-sd15.safetensors",
    "realvis": "realistic-vision-v51.safetensors",
    "absreal": "absolute-reality-v181.safetensors",
    "cyberreal": "cyberrealistic-v42.safetensors",
}


def generate_config(
    template_text: str, model_short: str, model_filename: str, defect: str
) -> str:
    """Replace model path, output dir, output name, log prefix in TOML text."""
    text = template_text

    # Replace pretrained_model_name_or_path
    checkpoint_path = str(
        PROJECT_ROOT / "models" / "checkpoints" / "benchmark" / model_filename
    )
    text = re.sub(
        r'pretrained_model_name_or_path\s*=\s*"[^"]*"',
        f'pretrained_model_name_or_path = "{checkpoint_path}"',
        text,
    )

    # Replace output_dir
    output_dir = str(BENCHMARK_OUTPUT_DIR / model_short / defect)
    text = re.sub(
        r'output_dir\s*=\s*"[^"]*"',
        f'output_dir = "{output_dir}"',
        text,
    )

    # Replace output_name
    output_name = f"xray_{defect}_{model_short}_lora_r32"
    text = re.sub(
        r'output_name\s*=\s*"[^"]*"',
        f'output_name = "{output_name}"',
        text,
    )

    # Replace log_prefix
    text = re.sub(
        r'log_prefix\s*=\s*"[^"]*"',
        f'log_prefix = "{defect}_{model_short}"',
        text,
    )

    # Update save_every_n_epochs to 5 (capture checkpoints at 10, 15, 20)
    text = re.sub(
        r"save_every_n_epochs\s*=\s*\d+",
        "save_every_n_epochs = 5",
        text,
    )

    return text


def main():
    parser = argparse.ArgumentParser(description="Generate benchmark training configs")
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    args = parser.parse_args()

    generated = 0

    for model_short, model_filename in MODELS.items():
        model_dir = BENCHMARK_CONFIGS_DIR / model_short
        model_dir.mkdir(parents=True, exist_ok=True)

        for defect in DEFECTS:
            # Read production template
            template_path = CONFIGS_DIR / f"{defect}-lora-training-config.toml"
            if not template_path.exists():
                logger.error(f"Template not found: {template_path}")
                continue

            template_text = template_path.read_text()
            config_text = generate_config(
                template_text, model_short, model_filename, defect
            )

            output_path = model_dir / f"{defect}-lora-training-config.toml"

            if args.dry_run:
                logger.info(f"[DRY] {model_short}/{defect} -> {output_path.name}")
                continue

            output_path.write_text(config_text)
            generated += 1

    # Print summary table
    logger.info(f"\nGenerated {generated} benchmark configs:")
    logger.info(f"{'Model':<12} {'Defect':<18} {'Output Name'}")
    logger.info("-" * 65)
    for model_short in MODELS:
        for defect in DEFECTS:
            output_name = f"xray_{defect}_{model_short}_lora_r32"
            logger.info(f"{model_short:<12} {defect:<18} {output_name}")

    # Validate all generated configs parse correctly
    if not args.dry_run:
        logger.info("\nValidating configs...")
        errors = 0
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        for model_short in MODELS:
            for defect in DEFECTS:
                config_path = (
                    BENCHMARK_CONFIGS_DIR / model_short / f"{defect}-lora-training-config.toml"
                )
                try:
                    with open(config_path, "rb") as f:
                        config = tomllib.load(f)
                    # Verify key fields
                    assert MODELS[model_short] in config["model_arguments"]["pretrained_model_name_or_path"]
                    assert model_short in config["training_arguments"]["output_name"]
                except Exception as e:
                    logger.error(f"Validation failed {config_path}: {e}")
                    errors += 1

        if errors == 0:
            logger.info(f"All {generated} configs validated OK")
        else:
            logger.error(f"{errors} configs failed validation")


if __name__ == "__main__":
    main()
