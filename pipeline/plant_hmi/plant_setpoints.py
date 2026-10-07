"""Setpoint registry, resolution and validated writes for the Plant HMI reverse
control (phase 5). Persistence (store file, audit log, lock) lives in
`plant_setpoint_store.py`; this module owns the registry and the business rules.

Knob 1: `sampler_steps` (SP-601, KSampler steps). `resolve()` runs INSIDE the
controlled process (`batch-production-main.py`) at start, rule R1: env override
(LOCAL) beats the setpoint store (REMOTE) beats the recipe value from the batch
YAML. It never raises: a bad env value or a corrupt store is ignored, falling
through to the next source, so a malformed setpoint can never block a batch.

The HMI (routes module) only ever WRITES the store; it never resolves a value
for a running process (that would defeat R1: the launch path would matter again).
"""

import os
import time
from typing import Dict, Optional, Tuple

from .plant_setpoint_store import locked_store, read_audit, read_store, write_store_and_audit

MAX_REASON_LEN = 200

REGISTRY: Dict[str, Dict] = {
    "sampler_steps": {
        "env": "PLANT_SP_SAMPLER_STEPS",
        "min": 10,
        "max": 40,
        "default": 25,             # rule L4: recipe missing/invalid never resolves to None
        "unit": "bước",
        "label": "Bước sampler (KSampler)",
        "applies": "next_batch",   # init-time parameter (rule R3): fixed for a running batch
        "config": ("sampler", "steps"),
        "tag": "SP-601",
    },
}


def _is_strict_int(value) -> bool:
    """True for a real int, false for bool (subclass of int) or float."""
    return isinstance(value, int) and not isinstance(value, bool)


def _in_range(key: str, value: int) -> bool:
    spec = REGISTRY[key]
    return spec["min"] <= value <= spec["max"]


def _check_reason(reason) -> str:
    reason = "" if reason is None else str(reason)
    if len(reason) > MAX_REASON_LEN:
        raise ValueError(f"lý do tối đa {MAX_REASON_LEN} ký tự")
    return reason


def resolve(key: str, recipe_value, environ: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    """Resolve one setpoint. Called inside the controlled process at start. Never raises.

    Order: env override ("env", LOCAL) > setpoint store ("setpoint", REMOTE) >
    `recipe_value` from the batch YAML ("recipe"). An out-of-range or malformed
    env/store value is ignored (falls through), never crashes the caller. A
    missing/invalid recipe value falls back to the registry default (rule L4):
    the caller never receives None.
    """
    if key not in REGISTRY:
        return recipe_value, "recipe"
    env = environ if environ is not None else os.environ
    spec = REGISTRY[key]

    raw = env.get(spec["env"])
    if raw is not None:
        try:
            v = int(raw)
            if _in_range(key, v):
                return v, "env"
        except (ValueError, TypeError):
            pass

    try:
        entry = read_store().get(key)
        if isinstance(entry, dict):
            v = entry.get("value")
            if _is_strict_int(v) and _in_range(key, v):
                return v, "setpoint"
    except Exception:
        pass

    if _is_strict_int(recipe_value) and _in_range(key, recipe_value):
        return recipe_value, "recipe"
    fallback = spec.get("default")
    if not _is_strict_int(fallback) or not _in_range(key, fallback):
        fallback = spec["min"]
    return fallback, "recipe"


def get_setpoint(key: str) -> Optional[Dict]:
    return read_store().get(key) if key in REGISTRY else None


def set_setpoint(key: str, value, who: str, reason) -> Dict:
    """Validate and persist one setpoint; append an audit line. Raises `ValueError`
    with a user-facing message on any invalid input (route turns this into 422)."""
    if key not in REGISTRY:
        raise ValueError(f"setpoint không tồn tại: {key}")
    if not _is_strict_int(value):
        raise ValueError("giá trị phải là số nguyên (không phải bool/float)")
    if not _in_range(key, value):
        spec = REGISTRY[key]
        raise ValueError(f"giá trị phải trong khoảng {spec['min']}..{spec['max']}")
    reason = _check_reason(reason)

    with locked_store():
        store = read_store()
        old_entry = store.get(key)
        old_value = old_entry.get("value") if isinstance(old_entry, dict) else None
        now = time.time()
        new_entry = {"value": value, "updated_at": now, "updated_by": who, "reason": reason}
        store[key] = new_entry
        write_store_and_audit(store, {"ts": now, "who": who, "key": key, "old": old_value,
                                       "new": value, "reason": reason})
        return new_entry


def clear_setpoint(key: str, who: str, reason) -> None:
    """Remove a stored override (rule M3): the next `resolve()` in a fresh process
    falls through to the recipe value, so PV becomes RECIPE on the next batch."""
    if key not in REGISTRY:
        raise ValueError(f"setpoint không tồn tại: {key}")
    reason = _check_reason(reason)

    with locked_store():
        store = read_store()
        old_entry = store.pop(key, None)
        old_value = old_entry.get("value") if isinstance(old_entry, dict) else None
        now = time.time()
        write_store_and_audit(store, {"ts": now, "who": who, "key": key, "old": old_value,
                                       "new": None, "reason": reason})


__all__ = ["REGISTRY", "resolve", "get_setpoint", "set_setpoint", "clear_setpoint",
           "read_store", "read_audit"]
