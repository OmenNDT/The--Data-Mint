"""Dataset info tool — statistics for synthetic and RIAWELC datasets."""

from pathlib import Path


CLASS_MAP = {
    "Difetto1": "lack_of_penetration",
    "Difetto2": "porosity",
    "Difetto4": "crack",
    "NoDifetto": "clean",
}


def register(mcp, project_root: Path):
    @mcp.tool()
    def dataset_info(dataset_type: str = "synthetic") -> dict:
        """Get dataset statistics.

        Args:
            dataset_type: 'synthetic', 'riawelc', or 'all'
        """
        result = {}
        if dataset_type in ("synthetic", "all"):
            result["synthetic"] = _synthetic_stats(project_root)
        if dataset_type in ("riawelc", "all"):
            result["riawelc"] = _riawelc_stats(project_root)
        return result


def _synthetic_stats(project_root: Path) -> dict:
    """Count synthetic output images and annotations."""
    output_dir = project_root / "output" / "synthetic"
    yolo_dir = project_root / "output" / "dataset" / "yolo"
    coco_dir = project_root / "output" / "dataset" / "annotations"

    stats = {"images": {}, "total_images": 0}

    if output_dir.exists():
        for defect_dir in sorted(output_dir.iterdir()):
            if defect_dir.is_dir():
                count = len(list(defect_dir.glob("*.png")))
                stats["images"][defect_dir.name] = count
                stats["total_images"] += count

    # Check annotation availability
    stats["has_yolo"] = yolo_dir.exists() and any(yolo_dir.rglob("*.txt"))
    stats["has_coco"] = coco_dir.exists() and any(coco_dir.rglob("*.json"))

    # Disk usage
    if output_dir.exists():
        total_bytes = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
        stats["disk_mb"] = round(total_bytes / (1024 * 1024), 1)

    return stats


def _riawelc_stats(project_root: Path) -> dict:
    """Count RIAWELC images per class and split."""
    riawelc_root = project_root / "dataset" / "RIAWELC" / "extracted" / "DB - Copy"
    if not riawelc_root.exists():
        return {"status": "not_found", "path": str(riawelc_root)}

    stats = {"splits": {}, "total": 0, "class_map": CLASS_MAP}

    for split in ["training", "validation", "testing"]:
        split_dir = riawelc_root / split
        if not split_dir.exists():
            continue
        split_stats = {}
        for class_dir in sorted(split_dir.iterdir()):
            if class_dir.is_dir():
                count = len(list(class_dir.glob("*.png")))
                split_stats[class_dir.name] = count
                stats["total"] += count
        stats["splits"][split] = split_stats

    stats["image_size"] = "224x224"
    stats["format"] = "PNG 8-bit grayscale"
    return stats
