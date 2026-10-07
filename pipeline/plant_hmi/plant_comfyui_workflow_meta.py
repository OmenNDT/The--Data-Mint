"""Node id -> display metadata, read from a ComfyUI API-format workflow JSON.

Split out of `plant_comfyui_progress_observer.py` to keep that file under the
200-line budget; this loader has no state of its own and no I/O beyond one
`read_text()` per call (cheap, called once per reconnect attempt).
"""

import json
from pathlib import Path
from typing import Dict, Optional

MAX_WORKFLOW_BYTES = 5 << 20  # a workflow JSON is a few hundred KB at most


def load_node_meta(workflow_path: Optional[str]) -> Dict[str, Dict[str, str]]:
    """Node id -> {"title", "class_type"}. `title` prefers `_meta.title`, falls
    back to `class_type`; an unreadable/oversized/malformed file yields no
    metadata (node id shown bare in the panel instead of a friendly name)."""
    if not workflow_path:
        return {}
    try:
        path = Path(workflow_path)
        if not path.is_file() or path.stat().st_size > MAX_WORKFLOW_BYTES:
            return {}
        data = json.loads(path.read_text())
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    meta: Dict[str, Dict[str, str]] = {}
    for node_id, node in data.items():
        if not isinstance(node, dict):
            continue
        node_meta = node.get("_meta")
        title = node_meta.get("title") if isinstance(node_meta, dict) else None
        class_type = node.get("class_type")
        meta[str(node_id)] = {"title": title or class_type or str(node_id), "class_type": class_type}
    return meta
