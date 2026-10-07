#!/usr/bin/env python3
"""
Prepare LoRA training data for 7 new defect classes.

For each class:
- Collects images from source dirs
- Resizes to 512x512 (LANCZOS, preserving grayscale)
- Converts JPG -> PNG
- Copies to kohya-ss training_data structure with sequential naming
- Generates caption TXT files
- Generates TOML training configs
- Generates sample prompt files

Usage:
    python3 prepare-lora-training-data.py
    python3 prepare-lora-training-data.py --dry-run
    python3 prepare-lora-training-data.py --class lack_of_penetration
"""

import os
import sys
import argparse
import shutil
import glob
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow not found. Installing...")
    os.system(f"{sys.executable} -m pip install Pillow")
    from PIL import Image

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")
DATASET_ROOT = PROJECT_ROOT / "dataset"
KOHYA_ROOT = PROJECT_ROOT / "kohya-ss"
TRAINING_DATA_ROOT = KOHYA_ROOT / "training_data"
CONFIGS_DIR = KOHYA_ROOT / "configs"
SAMPLE_PROMPTS_DIR = CONFIGS_DIR / "sample-prompts"
OUTPUT_BASE = KOHYA_ROOT / "output"
ALPHA_NDT_DIR = DATASET_ROOT / "IMAGE RT From AlphaNDT"

W0003_278 = DATASET_ROOT / "4.Welds_W0003_Clear_Defects_278"
W0003_AUG = DATASET_ROOT / "4.Welds_W0003_Clear_Defects_Aug"

# ── Class definitions ──────────────────────────────────────────────────────────
# Each class: (class_name, human_label, [source_dirs], [alphandt_glob_patterns])
CLASSES = [
    {
        "name": "lack_of_penetration",
        "label": "lack of penetration",
        "source_dirs": [
            W0003_278 / "Lack_Of_Penetration",
            W0003_AUG / "Lack_Of_Penetration",
        ],
        "alphanDT_patterns": [],
    },
    {
        "name": "clustered_porosity",
        "label": "clustered porosity",
        "source_dirs": [
            W0003_278 / "Clustered_localized_porosity",
            W0003_AUG / "Clustered_localized_porosity",
        ],
        "alphanDT_patterns": [],
    },
    {
        "name": "slag_inclusion",
        "label": "slag inclusion",
        "source_dirs": [
            W0003_278 / "Slag_inclusions",
            W0003_AUG / "Slag_inclusions",
        ],
        # ESI: 16 numbered + base = 17 files, ISI: 2 files
        "alphanDT_patterns": ["ESI-Elongated Slag Inclusion*.png", "ISI- Isolated Slag Inclusion*.png"],
    },
    {
        "name": "linear_porosity",
        "label": "linear porosity",
        "source_dirs": [
            W0003_278 / "Linear_Porosity",
            W0003_AUG / "Linear_Porosity",
        ],
        # 5 Linear Porosity files (excluding combination files like "Linear Porosity + ISI.png")
        "alphanDT_patterns": ["Linear Porosity*.png"],
        "alphanDT_exclude": ["Linear Porosity + ISI.png"],
    },
    {
        "name": "elongated_cavity",
        "label": "elongated cavity",
        "source_dirs": [
            W0003_278 / "Elongated_Cavity",
            W0003_AUG / "Elongated_Cavity",
        ],
        "alphanDT_patterns": [],
    },
    {
        "name": "metallic_inclusion",
        "label": "metallic inclusion",
        "source_dirs": [
            W0003_278 / "Metallic_Inclusion",
            W0003_AUG / "Metallic_Inclusion",
        ],
        "alphanDT_patterns": [],
    },
    {
        "name": "linear_slag_inclusion",
        "label": "linear slag inclusion",
        "source_dirs": [
            W0003_AUG / "Linear_slag_inclusion",
        ],
        "alphanDT_patterns": [],
    },
]

# TOML template — mirrors crack config with parameterized fields
TOML_TEMPLATE = """\
[model_arguments]
pretrained_model_name_or_path = "{model_path}"
v2 = false
v_parameterization = false

[dataset_arguments]
train_data_dir = "{train_data_dir}"
reg_data_dir = "{reg_data_dir}"
resolution = "512,512"
enable_bucket = true
min_bucket_reso = 256
max_bucket_reso = 1024
bucket_reso_steps = 64
bucket_no_upscale = true
cache_latents = true
shuffle_caption = true
caption_extension = ".txt"
keep_tokens = 1

[training_arguments]
output_dir = "{output_dir}"
output_name = "{output_name}"
save_precision = "fp16"
save_model_as = "safetensors"

max_train_epochs = {max_epochs}
train_batch_size = 4
gradient_accumulation_steps = 2
gradient_checkpointing = true

learning_rate = 5e-5
lr_scheduler = "cosine_with_restarts"
lr_warmup_steps = 200
lr_scheduler_num_cycles = 4

optimizer_type = "AdamW8bit"
optimizer_args = ["weight_decay=0.01"]

network_module = "networks.lora"
network_dim = 32
network_alpha = 16

mixed_precision = "fp16"
xformers = true
mem_eff_attn = false

seed = 42
clip_skip = 2

logging_dir = "{logs_dir}"
log_prefix = "{class_name}"
save_every_n_epochs = 2
save_state = false

[sample_prompt_arguments]
sample_prompts = "{sample_prompts_path}"
sample_every_n_epochs = 2
sample_sampler = "euler_a"
"""

SAMPLE_PROMPT_TEMPLATE = (
    "xray_{class_name}, weld {label} defect, radiographic image, "
    "industrial NDT, x-ray film --w 512 --h 512 --l 7 --s 20"
)

# Image extensions to collect
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"}


def collect_sources(cls: dict) -> list[Path]:
    """Collect all source image paths for a class, deduplicating by filename."""
    sources: list[Path] = []
    seen_names: set[str] = set()

    # From W0003 dirs
    for src_dir in cls["source_dirs"]:
        if not src_dir.exists():
            print(f"  WARNING: source dir missing: {src_dir}")
            continue
        for p in sorted(src_dir.iterdir()):
            if p.suffix in IMAGE_EXTENSIONS:
                if p.name not in seen_names:
                    sources.append(p)
                    seen_names.add(p.name)

    # From AlphaNDT
    exclude_set = set(cls.get("alphanDT_exclude", []))
    for pattern in cls.get("alphanDT_patterns", []):
        matched = sorted(ALPHA_NDT_DIR.glob(pattern))
        for p in matched:
            if p.name not in exclude_set and p.name not in seen_names:
                sources.append(p)
                seen_names.add(p.name)

    return sources


def epochs_for_count(count: int) -> int:
    """Scale training epochs by dataset size."""
    if count >= 80:
        return 15
    if count >= 40:
        return 12
    return 10


def process_image(src: Path, dst: Path) -> bool:
    """Resize image to 512x512 LANCZOS, convert to PNG grayscale. Returns True on success."""
    try:
        with Image.open(src) as img:
            # Preserve grayscale; convert RGB images to L
            if img.mode not in ("L", "LA"):
                img = img.convert("L")
            img_resized = img.resize((512, 512), Image.LANCZOS)
            img_resized.save(dst, format="PNG")
        return True
    except Exception as e:
        print(f"  ERROR processing {src.name}: {e}")
        return False


def prepare_class(cls: dict, dry_run: bool = False) -> dict:
    """
    Prepare training data for one class.
    Returns summary dict with counts.
    """
    class_name = cls["name"]
    label = cls["label"]

    # Target training dir: kohya-ss/training_data/{class}/10_xray_{class}/
    target_dir = TRAINING_DATA_ROOT / class_name / f"10_xray_{class_name}"

    print(f"\n[{class_name}]")
    print(f"  Target: {target_dir}")

    sources = collect_sources(cls)
    print(f"  Sources found: {len(sources)} images")

    if not sources:
        print(f"  SKIP: no source images found")
        return {"class": class_name, "prepared": 0, "skipped": 0, "errors": 0}

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    # Check idempotency: if destination already has images, skip
    existing = list(target_dir.glob("*.png")) if target_dir.exists() else []
    if existing and not dry_run:
        print(f"  SKIP (idempotent): {len(existing)} images already in {target_dir}")
        return {"class": class_name, "prepared": len(existing), "skipped": len(sources), "errors": 0}

    prepared = 0
    errors = 0
    caption = f"xray_{class_name}, weld {label} defect, radiographic image, industrial NDT"

    for idx, src in enumerate(sources):
        dst_name = f"{class_name}_{idx:06d}.png"
        dst_img = target_dir / dst_name
        dst_txt = target_dir / f"{class_name}_{idx:06d}.txt"

        if dry_run:
            print(f"  [DRY] {src.name} -> {dst_name}")
            prepared += 1
            continue

        if process_image(src, dst_img):
            dst_txt.write_text(caption, encoding="utf-8")
            prepared += 1
        else:
            errors += 1

    print(f"  Prepared: {prepared} | Errors: {errors}")
    return {"class": class_name, "prepared": prepared, "skipped": 0, "errors": errors}


def generate_toml(cls: dict, img_count: int, dry_run: bool = False) -> bool:
    """Generate TOML training config for a class."""
    class_name = cls["name"]
    config_path = CONFIGS_DIR / f"{class_name}-lora-training-config.toml"

    if config_path.exists():
        print(f"  TOML exists, skipping: {config_path.name}")
        return True

    epochs = epochs_for_count(img_count)
    content = TOML_TEMPLATE.format(
        model_path=str(PROJECT_ROOT / "models/checkpoints/sd-v1-5-pruned-emaonly.safetensors"),
        train_data_dir=str(TRAINING_DATA_ROOT / class_name),
        reg_data_dir=str(KOHYA_ROOT / "training_data/reg"),
        output_dir=str(OUTPUT_BASE / class_name),
        output_name=f"xray_{class_name}_lora_r32",
        max_epochs=epochs,
        logs_dir=str(KOHYA_ROOT / "logs"),
        class_name=class_name,
        sample_prompts_path=str(SAMPLE_PROMPTS_DIR / f"{class_name}-sample-prompts.txt"),
    )

    if not dry_run:
        CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        config_path.write_text(content, encoding="utf-8")
        # Also create output directory
        (OUTPUT_BASE / class_name).mkdir(parents=True, exist_ok=True)

    print(f"  TOML created: {config_path.name} (epochs={epochs})")
    return True


def generate_sample_prompt(cls: dict, dry_run: bool = False) -> bool:
    """Generate sample prompts file for a class."""
    class_name = cls["name"]
    label = cls["label"]
    prompt_path = SAMPLE_PROMPTS_DIR / f"{class_name}-sample-prompts.txt"

    if prompt_path.exists():
        print(f"  Prompt exists, skipping: {prompt_path.name}")
        return True

    content = SAMPLE_PROMPT_TEMPLATE.format(class_name=class_name, label=label)

    if not dry_run:
        SAMPLE_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(content, encoding="utf-8")

    print(f"  Prompt created: {prompt_path.name}")
    return True


def update_training_script(new_classes: list[str], dry_run: bool = False) -> bool:
    """
    Update train-all-loras-wsl.sh to include new class names.
    Reads current DEFECTS array and appends missing classes.
    """
    script_path = KOHYA_ROOT / "train-all-loras-wsl.sh"
    if not script_path.exists():
        print(f"  ERROR: training script not found: {script_path}")
        return False

    content = script_path.read_text(encoding="utf-8")

    # Find DEFECTS array line
    import re
    match = re.search(r'DEFECTS=\(([^)]+)\)', content)
    if not match:
        print("  ERROR: could not find DEFECTS array in training script")
        return False

    existing_raw = match.group(1)
    existing = re.findall(r'"([^"]+)"', existing_raw)
    print(f"  Existing defects: {existing}")

    to_add = [c for c in new_classes if c not in existing]
    if not to_add:
        print("  All new classes already in DEFECTS array, skipping.")
        return True

    all_defects = existing + to_add
    new_array_inner = " ".join(f'"{d}"' for d in all_defects)
    new_defects_line = f'DEFECTS=({new_array_inner})'

    # Also update the usage/help line
    old_defects_str = match.group(0)
    new_content = content.replace(old_defects_str, new_defects_line, 1)

    # Update usage echo line that lists defect names
    old_usage_pattern = r'(echo "Usage: \$0 \[all\|pilot\|remaining\|)([^"]+)("\]")'
    usage_match = re.search(old_usage_pattern, new_content)
    if usage_match:
        new_usage_classes = "|".join(all_defects)
        new_usage = f'{usage_match.group(1)}{new_usage_classes}{usage_match.group(3)}'
        new_content = new_content[:usage_match.start()] + new_usage + new_content[usage_match.end():]

    # Also update comment at top
    old_comment_match = re.search(r'# Trains \d+ LoRA models', new_content)
    if old_comment_match:
        new_content = new_content[:old_comment_match.start()] + \
            f"# Trains {len(all_defects)} LoRA models" + \
            new_content[old_comment_match.end():]

    if not dry_run:
        script_path.write_text(new_content, encoding="utf-8")

    print(f"  Added to DEFECTS: {to_add}")
    print(f"  Total defects now: {len(all_defects)}")
    return True


def print_summary_table(results: list[dict], config_ready: list[str], prompts_ready: list[str]):
    """Print final summary table."""
    print("\n" + "=" * 75)
    print(f"{'CLASS':<30} {'IMAGES':>8} {'CONFIG':>8} {'PROMPTS':>8}")
    print("-" * 75)
    for r in results:
        cls = r["class"]
        imgs = r["prepared"]
        cfg = "YES" if cls in config_ready else "NO"
        pmt = "YES" if cls in prompts_ready else "NO"
        print(f"{cls:<30} {imgs:>8} {cfg:>8} {pmt:>8}")
    print("=" * 75)
    total = sum(r["prepared"] for r in results)
    print(f"{'TOTAL':<30} {total:>8}")
    print("=" * 75)


def main():
    parser = argparse.ArgumentParser(description="Prepare LoRA training data for new defect classes")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing files")
    parser.add_argument("--class", dest="only_class", help="Process only this class name")
    args = parser.parse_args()

    dry = args.dry_run
    if dry:
        print("DRY RUN MODE — no files will be written\n")

    classes_to_process = CLASSES
    if args.only_class:
        classes_to_process = [c for c in CLASSES if c["name"] == args.only_class]
        if not classes_to_process:
            print(f"ERROR: class '{args.only_class}' not found. Available: {[c['name'] for c in CLASSES]}")
            sys.exit(1)

    results = []
    config_ready = []
    prompts_ready = []

    # Step 1: Prepare training data for each class
    print("=" * 60)
    print("STEP 1: Preparing training data")
    print("=" * 60)
    for cls in classes_to_process:
        result = prepare_class(cls, dry_run=dry)
        results.append(result)

    # Step 2: Generate TOML configs
    print("\n" + "=" * 60)
    print("STEP 2: Generating TOML configs")
    print("=" * 60)
    for cls, result in zip(classes_to_process, results):
        img_count = result["prepared"] if result["prepared"] > 0 else len(collect_sources(cls))
        ok = generate_toml(cls, img_count, dry_run=dry)
        if ok:
            config_ready.append(cls["name"])

    # Step 3: Generate sample prompts
    print("\n" + "=" * 60)
    print("STEP 3: Generating sample prompts")
    print("=" * 60)
    for cls in classes_to_process:
        ok = generate_sample_prompt(cls, dry_run=dry)
        if ok:
            prompts_ready.append(cls["name"])

    # Step 4: Update training script
    print("\n" + "=" * 60)
    print("STEP 4: Updating train-all-loras-wsl.sh")
    print("=" * 60)
    new_class_names = [cls["name"] for cls in classes_to_process]
    update_training_script(new_class_names, dry_run=dry)

    # Final summary
    print_summary_table(results, config_ready, prompts_ready)

    print("\nNext step: cd kohya-ss && ./train-all-loras-wsl.sh all")


if __name__ == "__main__":
    main()
