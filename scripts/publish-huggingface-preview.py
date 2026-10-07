#!/usr/bin/env python3
"""
Publish 100-image weld RT preview dataset to HuggingFace Hub.

Usage:
  # Dry run (validate only, no upload)
  python3 scripts/publish-huggingface-preview.py --dry-run

  # Publish to HuggingFace
  python3 scripts/publish-huggingface-preview.py --repo-id "thedatamint/weld-xray-defect-preview"

  # With custom token
  python3 scripts/publish-huggingface-preview.py --repo-id "thedatamint/weld-xray-defect-preview" --token "hf_xxx"

Prerequisites:
  pip install huggingface_hub
  huggingface-cli login  # or pass --token
"""

import argparse
import sys
from pathlib import Path

from huggingface_hub import HfApi, create_repo


PREVIEW_DIR = Path(__file__).resolve().parent.parent / "output" / "huggingface-preview"

EXPECTED_CLASSES = [
    "crack", "porosity", "clustered_porosity", "linear_porosity",
    "elongated_cavity", "lack_of_fusion", "lack_of_penetration",
    "slag_inclusion", "linear_slag_inclusion", "metallic_inclusion",
]

IMAGES_PER_CLASS = 10


def validate(preview_dir: Path) -> bool:
    """Validate folder structure and image counts."""
    ok = True
    readme = preview_dir / "README.md"
    if not readme.exists():
        print(f"  MISSING: {readme}")
        ok = False
    else:
        print(f"  OK: README.md ({readme.stat().st_size:,} bytes)")

    total = 0
    for cls in EXPECTED_CLASSES:
        cls_dir = preview_dir / cls
        if not cls_dir.is_dir():
            print(f"  MISSING dir: {cls}/")
            ok = False
            continue
        images = list(cls_dir.glob("*.png"))
        count = len(images)
        total += count
        status = "OK" if count == IMAGES_PER_CLASS else "WARN"
        print(f"  {status}: {cls}/ — {count} images")

    print(f"\n  Total: {total} images (expected {len(EXPECTED_CLASSES) * IMAGES_PER_CLASS})")
    return ok


def publish(preview_dir: Path, repo_id: str, token: str | None = None, private: bool = False):
    """Create repo and upload preview dataset."""
    api = HfApi(token=token)

    print(f"\n Creating repo: {repo_id}")
    create_repo(repo_id, repo_type="dataset", private=private, exist_ok=True, token=token)

    print(f" Uploading {preview_dir} → {repo_id}")
    api.upload_folder(
        folder_path=str(preview_dir),
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Initial upload: 100-image weld RT defect preview (10 classes × 10 images)",
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"\n Done! Dataset published at: {url}")
    return url


def main():
    parser = argparse.ArgumentParser(description="Publish weld RT preview to HuggingFace")
    parser.add_argument("--repo-id", default="thedatamint/weld-xray-defect-preview",
                        help="HuggingFace dataset repo ID (default: thedatamint/weld-xray-defect-preview)")
    parser.add_argument("--token", default=None, help="HuggingFace API token (or use huggingface-cli login)")
    parser.add_argument("--private", action="store_true", help="Create as private dataset")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't upload")
    parser.add_argument("--preview-dir", default=str(PREVIEW_DIR), help="Path to preview folder")
    args = parser.parse_args()

    preview_dir = Path(args.preview_dir)
    if not preview_dir.is_dir():
        print(f"Error: Preview directory not found: {preview_dir}")
        sys.exit(1)

    print(f"=== Validating: {preview_dir} ===\n")
    valid = validate(preview_dir)

    if not valid:
        print("\n Validation failed. Fix issues above before publishing.")
        sys.exit(1)

    if args.dry_run:
        print("\n Dry run complete. All checks passed.")
        return

    publish(preview_dir, args.repo_id, args.token, args.private)


if __name__ == "__main__":
    main()
