"""Review state for auto-label results.

Tracks accept/reject decisions per image and exports only approved
detections to final annotation datasets.
"""

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from importlib import import_module

_dataclass_mod = import_module(
    ".detection-result-dataclass", package="auto_labeler"
)
ImageAutoLabelResult = _dataclass_mod.ImageAutoLabelResult
AutoLabelResult = _dataclass_mod.AutoLabelResult

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AutoLabelReviewState:
    """Manages per-image accept/reject state for review workflow."""

    def __init__(self, auto_label_result: AutoLabelResult):
        self._result = auto_label_result
        # Map image_path_str -> ReviewStatus
        self._status: Dict[str, ReviewStatus] = {
            str(r.image_path): ReviewStatus.PENDING
            for r in auto_label_result.image_results
        }

    @property
    def total(self) -> int:
        return len(self._status)

    @property
    def accepted_count(self) -> int:
        return sum(1 for s in self._status.values() if s == ReviewStatus.ACCEPTED)

    @property
    def rejected_count(self) -> int:
        return sum(1 for s in self._status.values() if s == ReviewStatus.REJECTED)

    @property
    def pending_count(self) -> int:
        return sum(1 for s in self._status.values() if s == ReviewStatus.PENDING)

    def accept(self, image_path: str):
        """Mark an image as accepted."""
        key = str(image_path)
        if key in self._status:
            self._status[key] = ReviewStatus.ACCEPTED

    def reject(self, image_path: str):
        """Mark an image as rejected."""
        key = str(image_path)
        if key in self._status:
            self._status[key] = ReviewStatus.REJECTED

    def accept_all(self):
        """Accept all pending images."""
        for key in self._status:
            if self._status[key] == ReviewStatus.PENDING:
                self._status[key] = ReviewStatus.ACCEPTED

    def get_status(self, image_path: str) -> ReviewStatus:
        return self._status.get(str(image_path), ReviewStatus.PENDING)

    def get_accepted_results(self) -> List[ImageAutoLabelResult]:
        """Return only accepted image results."""
        accepted = []
        for r in self._result.image_results:
            if self._status.get(str(r.image_path)) == ReviewStatus.ACCEPTED:
                accepted.append(r)
        return accepted

    def get_image_at_index(self, index: int) -> Optional[ImageAutoLabelResult]:
        """Get image result by index for gallery navigation."""
        if 0 <= index < len(self._result.image_results):
            return self._result.image_results[index]
        return None

    def save_review_state(self, output_path: Path):
        """Save review decisions to JSON."""
        data = {
            path: status.value
            for path, status in self._status.items()
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Review state saved to {output_path}")

    def load_review_state(self, input_path: Path):
        """Load review decisions from JSON."""
        if not input_path.exists():
            return
        with open(input_path, "r") as f:
            data = json.load(f)
        for path, status_str in data.items():
            if path in self._status:
                self._status[path] = ReviewStatus(status_str)
        logger.info(f"Review state loaded from {input_path}")
