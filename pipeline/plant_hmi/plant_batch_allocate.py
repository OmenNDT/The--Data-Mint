"""Pure job-count allocation for the compose form, split out of
`plant_batch_compose.py` purely to keep that file under the 200-line
guideline. No I/O: `compose_config` is the only caller.
"""

import math
from typing import Dict


def allocate_counts(total: int, weights: Dict[str, float]) -> Dict[str, int]:
    """Largest-remainder allocation: counts always sum to exactly `total`.
    Weights need not already sum to 1 (normalised here); zero/absent weights
    get 0. Tie-break on defect name for deterministic, testable output."""
    positive = {d: w for d, w in weights.items() if w > 0}
    counts = {d: 0 for d in weights}
    if not positive:
        return counts
    wsum = sum(positive.values())
    raw = {d: (total * w / wsum) for d, w in positive.items()}
    floors = {d: int(math.floor(v)) for d, v in raw.items()}
    remainder = total - sum(floors.values())
    order = sorted(positive, key=lambda d: (-(raw[d] - floors[d]), d))
    counts.update(floors)
    for d in order[:remainder]:
        counts[d] += 1
    return counts


def ratio_for_count(count: int, total: int) -> float:
    """A float ratio such that `int(total * ratio)` (the scheduler's own
    formula, `batch_manager/batch-job-scheduler.py:_build_job_list`, read-only)
    reproduces `count` exactly, immune to the rounding a plain `count / total`
    division can introduce. `math.nextafter` nudges the ratio by the smallest
    representable step until the floor matches."""
    if count <= 0:
        return 0.0
    ratio = count / total
    guard = 0
    while int(total * ratio) < count and guard < 64:
        ratio = math.nextafter(ratio, 1.0)
        guard += 1
    guard = 0
    while int(total * ratio) > count and guard < 64:
        ratio = math.nextafter(ratio, 0.0)
        guard += 1
    return ratio
