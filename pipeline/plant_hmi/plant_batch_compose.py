"""Compose a new batch config from the HMI "Tạo mẻ mới" form (new-batch form).

Validates every field server-side (`plant_batch_compose_validate.py`), allocates
per-defect job counts so they sum to `total_images` EXACTLY (largest-remainder
method), writes a ratio for each defect such that the scheduler's own
`int(total_images * ratio)` (`batch_manager/batch-job-scheduler.py:_build_job_list`,
read-only) reproduces that exact count despite floating-point rounding, and
writes `config/_generated/<name>.yaml` without ever mutating the base config's
nested dicts (those are shared, cached objects: `plant_production_readers._cache`).
"""

import time
from typing import Dict, List, Optional

import yaml

from . import plant_batch_allocate as allocate
from . import plant_batch_config_whitelist as whitelist
from . import plant_batch_compose_validate as validate
from . import plant_production_readers as production
from .plant_batch_compose_validate import ComposeError, err  # re-exported for route/test callers

PROJECT_ROOT = production.PIPELINE_DIR.parent
LORAS_DIR = (PROJECT_ROOT / "comfyui" / "models" / "loras").resolve()
DEFAULT_TEMPLATES_PATH = production.PIPELINE_DIR / "comfyui-workflows" / "defect-type-prompt-templates.yaml"

# Mirrors the `generators` dict keys in batch_manager/mask_prefetch_worker_pool.py
# (`_generate_mask_worker`, read-only file). Duplicated as a plain set here, not
# imported, because that module does a lazy numpy/PIL/mask_generator import meant
# only for the actual mask-generation worker process, not a request-handling route.
MASK_GENERATOR_DEFECTS = {
    "crack", "porosity", "clustered_porosity", "linear_porosity", "lack_of_fusion",
    "lack_of_penetration", "lack_of_side_wall_fusion", "slag_inclusion",
    "linear_slag_inclusion", "metallic_inclusion", "elongated_cavity", "undercut",
    "inclusion",
}


def load_templates(templates_path) -> Dict:
    data = production.load_batch_config(str(templates_path))
    prompts = data.get("defect_prompts") if isinstance(data, dict) else None
    return prompts if isinstance(prompts, dict) else {}


def lora_present(lora_name: Optional[str]) -> bool:
    if not lora_name:
        return False
    try:
        return (LORAS_DIR / lora_name).is_file()
    except OSError:
        return False


def defect_options(base_cfg: Dict) -> List[Dict]:
    """Every defect defined in the base config's own templates file: label,
    lora_present, mask_generator and the base config's current weight (0 if
    the defect is absent from its distribution)."""
    comfy_cfg = production.section(base_cfg, "comfyui")
    templates_path = comfy_cfg.get("prompts_path") or str(DEFAULT_TEMPLATES_PATH)
    prompts = load_templates(templates_path)
    gen = production.section(base_cfg, "generation")
    distribution = gen.get("defect_distribution")
    distribution = distribution if isinstance(distribution, dict) else {}
    out = []
    for defect, spec in prompts.items():
        lora_name = spec.get("lora_name") if isinstance(spec, dict) else None
        try:
            default_weight = float(distribution.get(defect) or 0.0)
        except (TypeError, ValueError):
            default_weight = 0.0
        out.append({
            "defect": defect,
            "label": defect.replace("_", " "),
            "lora_name": lora_name,
            "lora_present": lora_present(lora_name),
            "mask_generator": defect in MASK_GENERATOR_DEFECTS,
            "default_weight": default_weight,
        })
    return out


def missing_for_config(cfg: Dict) -> List[str]:
    """Defects with weight > 0 in `cfg`'s OWN distribution that lack a LoRA
    file or a mask generator (LORA_PRESENT permissive input, gates starting
    this already-selected config, independent of the compose form)."""
    options = {o["defect"]: o for o in defect_options(cfg)}
    gen = production.section(cfg, "generation")
    distribution = gen.get("defect_distribution")
    distribution = distribution if isinstance(distribution, dict) else {}
    missing = []
    for defect, weight in distribution.items():
        try:
            w = float(weight)
        except (TypeError, ValueError):
            w = 0.0
        if w <= 0:
            continue
        opt = options.get(defect)
        if opt is None or not opt["lora_present"] or not opt["mask_generator"]:
            missing.append(defect)
    return missing


def compose_options(base_name: str) -> Dict:
    config_path = whitelist.resolve_config_name(base_name)
    if config_path is None:
        err("base_config", "base config không nằm trong whitelist")
    base_cfg = production.load_batch_config(str(config_path))
    gen = production.section(base_cfg, "generation")
    paths = production.section(base_cfg, "paths")
    return {
        "base_config": base_name,
        "defects": defect_options(base_cfg),
        "default_total_images": gen.get("total_images"),
        "default_backgrounds_dir": paths.get("backgrounds_dir"),
    }


def compose_config(*, name: str, base_config: str, total_images, distribution: Dict,
                    backgrounds_dir: Optional[str], reason: str, overwrite: bool, who: str) -> Dict:
    """Validate, allocate, and write `config/_generated/<name>.yaml`. Raises
    `ComposeError` (caller returns 400) on any invalid input; never touches
    `base_config` on disk."""
    base_path = whitelist.resolve_config_name(base_config)
    if base_path is None:
        err("base_config", "base config không nằm trong whitelist")
    base_cfg = production.load_batch_config(str(base_path))
    if not base_cfg:
        err("base_config", "base config rỗng hoặc không đọc được")

    target = validate.validate_name(name, overwrite)
    total = validate.validate_total(total_images)

    options_by_defect = {o["defect"]: o for o in defect_options(base_cfg)}
    weights = validate.validate_distribution(distribution, options_by_defect)

    base_paths = production.section(base_cfg, "paths")
    bg_dir = validate.validate_backgrounds_dir(backgrounds_dir or base_paths.get("backgrounds_dir"),
                                                base_paths.get("backgrounds_dir"))

    counts = allocate.allocate_counts(total, weights)
    ratios = {d: allocate.ratio_for_count(c, total) for d, c in counts.items() if c > 0}

    # Shallow copy only: `generation`/`paths` get brand-new dicts below, so the
    # cached nested dicts inside `base_cfg` (shared with other readers via
    # production._cache) are never mutated in place.
    new_cfg = dict(base_cfg)
    new_cfg["generation"] = {**production.section(base_cfg, "generation"),
                              "total_images": total, "defect_distribution": ratios}
    new_cfg["paths"] = {**base_paths, "backgrounds_dir": bg_dir}
    new_cfg.pop("lora_models", None)  # unused/misleading key (review doc): never copied forward
    new_cfg["plant_hmi_compose"] = {
        "source_config": base_config, "created": time.time(), "who": who, "reason": reason,
    }

    whitelist.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if target.parent.resolve() != whitelist.GENERATED_DIR.resolve():
        err("name", "đường dẫn config không hợp lệ")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(new_cfg, allow_unicode=True, sort_keys=False))
    tmp.replace(target)

    return {
        "config_name": f"_generated/{target.name}",
        "counts": counts,
        "total_images": total,
        "backgrounds_dir": bg_dir,
    }
