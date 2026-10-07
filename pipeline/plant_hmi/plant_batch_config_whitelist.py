"""Whitelist resolution for batch config files offered to the Plant HMI start control.

The start request carries a config NAME taken from `list_configs()`, never an arbitrary
path (rule: no traversal, no symlink escape). Only two directories are offered:
`pipeline/config/*.yaml` (direct children, name = filename) and
`pipeline/config/_generated/*.yaml` (name = `_generated/<filename>`). Both resolved
against the real filesystem path (`Path.resolve()`) so a symlink inside either
directory cannot point outside it.
"""

from pathlib import Path
from typing import Dict, List, Optional

from . import plant_production_readers as production

CONFIG_DIR = production.PIPELINE_DIR / "config"
GENERATED_DIR = CONFIG_DIR / "_generated"
MAIN_SILO_DIR = (production.PIPELINE_DIR.parent / "output" / "synthetic").resolve()


def _resolved_parent_matches(path: Path, allowed_dir: Path) -> bool:
    """True if `path` resolves to a real file whose real parent dir is exactly
    `allowed_dir` resolved too: blocks symlink escape and `..` traversal alike."""
    try:
        real = path.resolve(strict=True)
    except (OSError, ValueError):
        # ValueError: embedded NUL byte survives JSON parsing (L1) but `Path.resolve`
        # rejects it; caught here defensively even though `resolve_config_name`
        # already screens control chars out before ever building a `Path`.
        return False
    return real.is_file() and real.parent == allowed_dir.resolve()


def _has_control_char(name: str) -> bool:
    """NUL or any other C0 control character (L1): reject before touching the
    filesystem at all, so a malformed name is a clean 400, never an unhandled
    500 from `os`/`pathlib` raising `ValueError: embedded null byte`."""
    return any(ord(c) < 0x20 or ord(c) == 0x7F for c in name)


def resolve_config_name(name: str) -> Optional[Path]:
    """Resolve a whitelisted config name to its real path, or None if it is not
    one of the two offered directories (direct `.yaml` child, or `_generated/`
    direct child)."""
    if not name or not name.endswith(".yaml") or "\\" in name or _has_control_char(name):
        return None
    if name.startswith("_generated/"):
        rest = name[len("_generated/"):]
        if "/" in rest or rest in ("", ".", ".."):
            return None
        candidate = GENERATED_DIR / rest
        return candidate if _resolved_parent_matches(candidate, GENERATED_DIR) else None
    if "/" in name or name in (".", ".."):
        return None
    candidate = CONFIG_DIR / name
    return candidate if _resolved_parent_matches(candidate, CONFIG_DIR) else None


def _describe(name: str, path: Path) -> Dict:
    cfg = production.load_batch_config(str(path))
    output_dir = production.section(cfg, "paths").get("output_base_dir")
    main_silo = False
    if output_dir:
        try:
            main_silo = Path(output_dir).resolve() == MAIN_SILO_DIR
        except OSError:
            main_silo = False
    return {"name": name, "path": str(path), "output_dir": output_dir, "main_silo": main_silo}


def list_configs() -> List[Dict]:
    """Every whitelisted config file, newest/base config first for a stable, obvious
    default in the UI (`batch-config.yaml` before the rest, alphabetical after)."""
    out: List[Dict] = []
    try:
        direct = sorted(p.name for p in CONFIG_DIR.glob("*.yaml") if p.is_file())
    except OSError:
        direct = []
    direct.sort(key=lambda n: (n != "batch-config.yaml", n))
    for n in direct:
        out.append(_describe(n, CONFIG_DIR / n))
    try:
        generated = sorted(p.name for p in GENERATED_DIR.glob("*.yaml") if p.is_file())
    except OSError:
        generated = []
    for n in generated:
        out.append(_describe(f"_generated/{n}", GENERATED_DIR / n))
    return out
