"""Training config utilities - paths, discovery, and TOML config I/O."""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
KOHYA_DIR = PROJECT_ROOT / "kohya-ss"
KOHYA_ACCELERATE = KOHYA_DIR / ".venv/bin/accelerate"
CONFIGS_DIR = KOHYA_DIR / "configs"
TRAINING_DATA_DIR = KOHYA_DIR / "training_data"
MODELS_DIR = PROJECT_ROOT / "models"

# Default training parameters
DEFAULT_PARAMS = {
    "epochs": 20, "batch_size": 4, "learning_rate": "5e-5",
    "network_dim": 32, "network_alpha": 16,
    "optimizer_type": "AdamW8bit", "lr_scheduler": "cosine_with_restarts",
    "lr_warmup_steps": 200, "lr_scheduler_num_cycles": 4,
    "gradient_accumulation_steps": 2, "gradient_checkpointing": True,
    "mixed_precision": "fp16", "xformers": True,
    "clip_skip": 2, "seed": 42, "save_every_n_epochs": 2,
    "keep_tokens": 1, "shuffle_caption": True, "cache_latents": True,
    "enable_bucket": True, "resolution": "512,512",
}

# TOML key → param name mappings
_INT_PARAMS = {
    "max_train_epochs": "epochs", "train_batch_size": "batch_size",
    "network_dim": "network_dim", "network_alpha": "network_alpha",
    "lr_warmup_steps": "lr_warmup_steps",
    "lr_scheduler_num_cycles": "lr_scheduler_num_cycles",
    "gradient_accumulation_steps": "gradient_accumulation_steps",
    "clip_skip": "clip_skip", "seed": "seed",
    "save_every_n_epochs": "save_every_n_epochs",
    "keep_tokens": "keep_tokens",
}
_STR_PARAMS = {
    "learning_rate": "learning_rate", "optimizer_type": "optimizer_type",
    "lr_scheduler": "lr_scheduler", "mixed_precision": "mixed_precision",
    "resolution": "resolution",
}
_BOOL_PARAMS = {
    "gradient_checkpointing": "gradient_checkpointing",
    "xformers": "xformers", "shuffle_caption": "shuffle_caption",
    "cache_latents": "cache_latents", "enable_bucket": "enable_bucket",
}


def get_available_defect_types():
    """Scan training_data dir for available defect types."""
    defects = []
    if TRAINING_DATA_DIR.exists():
        for d in sorted(TRAINING_DATA_DIR.iterdir()):
            if d.is_dir() and d.name != "reg":
                img_dir = list(d.glob("*_xray_*"))
                count = len(list(img_dir[0].glob("*.png"))) if img_dir else 0
                defects.append((d.name, count))
    return defects


def get_available_configs():
    """List available training config files."""
    configs = []
    if CONFIGS_DIR.exists():
        for f in sorted(CONFIGS_DIR.glob("*-lora-training-config.toml")):
            name = f.stem.replace("-lora-training-config", "")
            configs.append((name, str(f)))
    return configs


def get_existing_loras():
    """List already trained LoRA models."""
    loras_dir = MODELS_DIR / "loras"
    if not loras_dir.exists():
        return []
    return sorted([f.name for f in loras_dir.glob("*.safetensors")])


def load_config_params(config_path):
    """Read all params from a TOML config file. Returns dict."""
    params = dict(DEFAULT_PARAMS)
    if not config_path or not Path(config_path).exists():
        return params

    text = Path(config_path).read_text()
    for toml_key, param_key in _INT_PARAMS.items():
        m = re.search(rf"{toml_key}\s*=\s*(\d+)", text)
        if m:
            params[param_key] = int(m.group(1))
    for toml_key, param_key in _STR_PARAMS.items():
        m = re.search(rf'{toml_key}\s*=\s*"?([^"\n]+)"?', text)
        if m:
            params[param_key] = m.group(1).strip().strip('"')
    for toml_key, param_key in _BOOL_PARAMS.items():
        m = re.search(rf"{toml_key}\s*=\s*(true|false)", text)
        if m:
            params[param_key] = m.group(1) == "true"
    return params


def update_config_file(config_path, params):
    """Update a TOML config file with the given parameters."""
    text = Path(config_path).read_text()
    _REV_INT = {v: k for k, v in _INT_PARAMS.items()}
    _REV_STR = {v: k for k, v in _STR_PARAMS.items()}
    _REV_BOOL = {v: k for k, v in _BOOL_PARAMS.items()}

    for param_key, value in params.items():
        if param_key in _REV_INT:
            tk = _REV_INT[param_key]
            text = re.sub(rf"{tk}\s*=\s*\d+", f"{tk} = {int(value)}", text)
        elif param_key in _REV_STR:
            tk = _REV_STR[param_key]
            if tk == "learning_rate":
                text = re.sub(rf"{tk}\s*=\s*[\d.e-]+", f"{tk} = {value}", text)
            else:
                text = re.sub(rf'{tk}\s*=\s*"[^"]*"', f'{tk} = "{value}"', text)
        elif param_key in _REV_BOOL:
            tk = _REV_BOOL[param_key]
            text = re.sub(rf"{tk}\s*=\s*(true|false)", f"{tk} = {'true' if value else 'false'}", text)

    # Special fields: base model, dataset paths
    if "base_model" in params and params["base_model"] and Path(params["base_model"]).exists():
        text = re.sub(
            r'pretrained_model_name_or_path\s*=\s*"[^"]*"',
            f'pretrained_model_name_or_path = "{params["base_model"]}"', text,
        )
    if "dataset_path" in params:
        text = re.sub(r'train_data_dir\s*=\s*"[^"]*"', f'train_data_dir = "{params["dataset_path"]}"', text)
    if "reg_path" in params and params["reg_path"] and Path(params["reg_path"]).exists():
        text = re.sub(r'reg_data_dir\s*=\s*"[^"]*"', f'reg_data_dir = "{params["reg_path"]}"', text)

    Path(config_path).write_text(text)
