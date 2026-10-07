"""Field validation for the "Tạo mẻ mới" compose form, split out of
`plant_batch_compose.py` purely to keep that file under the 200-line
guideline; both change together and `compose_config` is the only caller.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from . import plant_batch_config_whitelist as whitelist
from . import plant_production_readers as production

PROJECT_ROOT = production.PIPELINE_DIR.parent
DATASET_DIR = (PROJECT_ROOT / "dataset").resolve()

NAME_RE = re.compile(r"^[a-z0-9-]{1,60}$")
MAX_TOTAL_IMAGES = 20000
IMAGE_EXTS = (".png", ".jpg", ".jpeg")


class ComposeError(Exception):
    """Carries a list of {field, message} errors for a clean 400 response."""

    def __init__(self, errors: List[Dict]):
        super().__init__("; ".join(e["message"] for e in errors))
        self.errors = errors


def err(field: str, message: str) -> None:
    raise ComposeError([{"field": field, "message": message}])


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_name(name: str, overwrite: bool) -> Path:
    if not NAME_RE.match(name or ""):
        err("name", "tên phải là slug chữ thường/số/gạch ngang, tối đa 60 ký tự")
    target = whitelist.GENERATED_DIR / f"{name}.yaml"
    if target.exists() and not overwrite:
        err("name", f"config '{name}' đã tồn tại, cần overwrite=true để ghi đè")
    return target


def validate_total(total_images) -> int:
    if isinstance(total_images, bool) or not isinstance(total_images, int) or \
            not (1 <= total_images <= MAX_TOTAL_IMAGES):
        err("total_images", f"total_images phải là số nguyên 1..{MAX_TOTAL_IMAGES}")
    return total_images


def validate_distribution(distribution: Dict, options_by_defect: Dict) -> Dict[str, float]:
    if not isinstance(distribution, dict) or not distribution:
        err("distribution", "cần ít nhất một defect trong distribution")
    errors = []
    weights: Dict[str, float] = {}
    for defect, weight in distribution.items():
        if defect not in options_by_defect:
            errors.append({"field": "distribution", "message": f"defect '{defect}' không có trong defect_prompts"})
            continue
        try:
            w = float(weight)
        except (TypeError, ValueError):
            errors.append({"field": "distribution", "message": f"trọng số '{defect}' không hợp lệ"})
            continue
        if w < 0:
            errors.append({"field": "distribution", "message": f"trọng số '{defect}' phải >= 0"})
            continue
        weights[defect] = w
    if errors:
        raise ComposeError(errors)
    if not any(w > 0 for w in weights.values()):
        err("distribution", "phải có ít nhất một defect với trọng số > 0")
    missing = []
    for defect, w in weights.items():
        if w <= 0:
            continue
        opt = options_by_defect[defect]
        if not opt["lora_present"]:
            missing.append(f"{defect} (thiếu LoRA {opt['lora_name'] or '?'})")
        elif not opt["mask_generator"]:
            missing.append(f"{defect} (thiếu mask generator)")
    if missing:
        err("distribution", "không thể dùng các defect sau: " + "; ".join(missing))
    return weights


def validate_backgrounds_dir(backgrounds_dir: Optional[str], base_backgrounds_dir: Optional[str]) -> str:
    if not backgrounds_dir:
        err("backgrounds_dir", "backgrounds_dir không được để trống")
    try:
        real = Path(backgrounds_dir).resolve(strict=True)
    except (OSError, ValueError):
        err("backgrounds_dir", "backgrounds_dir không tồn tại")
    if not real.is_dir():
        err("backgrounds_dir", "backgrounds_dir phải là thư mục")
    try:
        with os.scandir(real) as it:
            has_image = any(e.is_file() and e.name.lower().endswith(IMAGE_EXTS) for e in it)
    except OSError:
        has_image = False
    if not has_image:
        err("backgrounds_dir", "backgrounds_dir không có ảnh png/jpg nào")
    allowed_parents = [DATASET_DIR]
    if base_backgrounds_dir:
        try:
            allowed_parents.append(Path(base_backgrounds_dir).resolve().parent)
        except OSError:
            pass
    if not any(_is_relative_to(real, p) for p in allowed_parents):
        err("backgrounds_dir",
            "backgrounds_dir phải nằm trong dataset/ hoặc cùng thư mục cha với backgrounds_dir của base config")
    return str(real)
