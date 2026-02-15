"""Generation config utilities - model scanning, prompt templates, batch config I/O.

Provides helper functions for the Phase 6 image generation UI panel:
- Scan model directories for checkpoints, ControlNets, LoRAs
- Load/write defect prompt templates from YAML
- Load/write batch-config.yaml for generation runs
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
BATCH_CONFIG_PATH = PIPELINE_DIR / "config" / "batch-config.yaml"
PROMPT_TEMPLATES_PATH = PIPELINE_DIR / "comfyui-workflows" / "defect-type-prompt-templates.yaml"
BATCH_MAIN_SCRIPT = PIPELINE_DIR / "batch_manager" / "batch-production-main.py"

DEFECT_TYPES = ["crack", "porosity", "inclusion", "lack_of_fusion", "undercut"]

DEFAULT_SAMPLER = {
    "name": "euler",
    "scheduler": "normal",
    "steps": 20,
    "cfg": 7.0,
    "seed": -1,
}


def scan_checkpoints() -> List[Tuple[str, str]]:
    """Scan models/checkpoints/ for .safetensors files.

    Returns:
        List of (display_name, full_path) tuples.
    """
    ckpt_dir = MODELS_DIR / "checkpoints"
    if not ckpt_dir.exists():
        return []
    files = sorted(ckpt_dir.glob("*.safetensors"))
    return [(f.name, str(f)) for f in files]


def scan_controlnets() -> List[Tuple[str, str]]:
    """Scan models/controlnet/ for .pth and .safetensors files.

    Returns:
        List of (display_name, full_path) tuples.
    """
    cn_dir = MODELS_DIR / "controlnet"
    if not cn_dir.exists():
        return []
    files = sorted(
        list(cn_dir.glob("*.pth")) + list(cn_dir.glob("*.safetensors"))
    )
    return [(f.name, str(f)) for f in files]


def scan_loras() -> List[Tuple[str, str]]:
    """Scan models/loras/ for .safetensors files.

    Returns:
        List of (display_name, full_path) tuples.
    """
    lora_dir = MODELS_DIR / "loras"
    if not lora_dir.exists():
        return []
    files = sorted(lora_dir.glob("*.safetensors"))
    return [(f.name, str(f)) for f in files]


def load_prompt_templates() -> Dict:
    """Load defect prompt templates from YAML.

    Returns:
        Dict keyed by defect type with prompt/strength params.
        Falls back to minimal defaults if file missing.
    """
    if not PROMPT_TEMPLATES_PATH.exists():
        logger.warning(f"Prompt templates not found: {PROMPT_TEMPLATES_PATH}")
        return {d: _default_prompt(d) for d in DEFECT_TYPES}

    try:
        with open(PROMPT_TEMPLATES_PATH) as f:
            data = yaml.safe_load(f)
        return data.get("defect_prompts", {})
    except Exception as e:
        logger.error(f"Failed to load prompt templates: {e}")
        return {d: _default_prompt(d) for d in DEFECT_TYPES}


def _default_prompt(defect_type: str) -> Dict:
    """Fallback prompt for a defect type."""
    return {
        "positive": f"xray_{defect_type}, weld defect, radiographic image",
        "negative": "color, photograph, blurry, text, watermark, low quality",
        "lora_strength": 0.7,
        "controlnet_strength": 0.8,
        "denoise": 0.85,
    }


def load_batch_config() -> Dict:
    """Load batch-config.yaml and return parsed config dict.

    Returns:
        Full config dict, or sensible defaults if file missing.
    """
    if not BATCH_CONFIG_PATH.exists():
        logger.warning(f"Batch config not found: {BATCH_CONFIG_PATH}")
        return _default_batch_config()

    try:
        with open(BATCH_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load batch config: {e}")
        return _default_batch_config()


def write_batch_config(params: Dict) -> str:
    """Update batch-config.yaml with UI params before a generation run.

    Args:
        params: Dict with keys matching batch-config structure.

    Returns:
        Path to written config file.
    """
    config = load_batch_config()

    # Generation params
    if "total_images" in params:
        config["generation"]["total_images"] = int(params["total_images"])
    if "defect_distribution" in params:
        config["generation"]["defect_distribution"] = params["defect_distribution"]

    # Sampler params
    sampler = config.get("sampler", {})
    for key in ("name", "scheduler", "steps", "cfg"):
        if f"sampler_{key}" in params:
            sampler[key] = params[f"sampler_{key}"]
    config["sampler"] = sampler

    # Paths
    paths = config.get("paths", {})
    if "backgrounds_dir" in params and params["backgrounds_dir"]:
        paths["backgrounds_dir"] = params["backgrounds_dir"]
    if "output_base_dir" in params and params["output_base_dir"]:
        paths["output_base_dir"] = params["output_base_dir"]
    config["paths"] = paths

    BATCH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BATCH_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    return str(BATCH_CONFIG_PATH)


def _default_batch_config() -> Dict:
    """Sensible default batch config when file is missing."""
    return {
        "comfyui": {"host": "127.0.0.1", "port": 8188},
        "generation": {
            "total_images": 100,
            "resolution": 512,
            "defect_distribution": {d: 0.2 for d in DEFECT_TYPES},
        },
        "sampler": dict(DEFAULT_SAMPLER),
        "paths": {
            "backgrounds_dir": str(PROJECT_ROOT / "kohya-ss" / "training_data" / "reg" / "1_xray_clean"),
            "output_base_dir": str(PROJECT_ROOT / "output" / "synthetic"),
            "checkpoint_dir": str(PIPELINE_DIR / "checkpoints"),
            "logs_dir": str(PIPELINE_DIR / "logs"),
        },
        "output": {"save_masks": True, "save_metadata": True, "organize_by_defect": True},
        "thermal": {"enabled": True, "max_temp_celsius": 85, "resume_temp_celsius": 75, "check_interval_seconds": 30},
        "reliability": {"max_retries": 3, "retry_delay_seconds": 5, "checkpoint_interval": 100, "timeout_seconds": 300},
        "performance": {"mask_prefetch_count": 50, "mask_prefetch_workers": 8},
    }
