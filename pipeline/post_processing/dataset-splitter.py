#!/usr/bin/env python3
"""
Dataset Splitter

Splits synthetic dataset into train/val/test splits with stratification by defect type.
Ensures balanced distribution of defect types across all splits.
"""

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict


def load_synthetic_dataset(synthetic_dir: Path) -> List[Dict]:
    """
    Load all synthetic images, masks, and metadata from output directory.

    Args:
        synthetic_dir: Path to output/synthetic directory

    Returns:
        List of dicts with image_path, mask_path, defect_type, metadata
    """
    dataset = []

    # Iterate through defect type subdirectories
    for defect_dir in synthetic_dir.iterdir():
        if not defect_dir.is_dir():
            continue

        defect_type = defect_dir.name

        # Find all image files (not masks, not metadata)
        for img_file in defect_dir.glob("*.png"):
            if "_mask" in img_file.name:
                continue  # Skip mask files

            # Find corresponding mask and metadata
            base_name = img_file.stem
            mask_file = defect_dir / f"{base_name}_mask.png"
            metadata_file = defect_dir / f"{base_name}.json"

            if not mask_file.exists():
                print(f"Warning: Missing mask for {img_file}, skipping")
                continue

            # Load metadata if exists
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

            dataset.append({
                "image_path": str(img_file),
                "mask_path": str(mask_file),
                "defect_type": defect_type,
                "metadata": metadata
            })

    return dataset


def stratified_split(
    dataset: List[Dict],
    train_ratio: float = 0.70,
    val_ratio: float = 0.20,
    test_ratio: float = 0.10,
    random_seed: int = 42
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Split dataset into train/val/test with stratification by defect_type.

    Args:
        dataset: List of data items
        train_ratio: Fraction for training set
        val_ratio: Fraction for validation set
        test_ratio: Fraction for test set
        random_seed: Random seed for reproducibility

    Returns:
        (train_set, val_set, test_set)
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.01:
        raise ValueError("Split ratios must sum to 1.0")

    random.seed(random_seed)

    # Group by defect type
    by_type = defaultdict(list)
    for item in dataset:
        by_type[item["defect_type"]].append(item)

    train_set, val_set, test_set = [], [], []

    # Split each defect type independently (stratification)
    for defect_type, items in by_type.items():
        # Shuffle items
        random.shuffle(items)

        n = len(items)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train_items = items[:n_train]
        val_items = items[n_train:n_train + n_val]
        test_items = items[n_train + n_val:]

        train_set.extend(train_items)
        val_set.extend(val_items)
        test_set.extend(test_items)

        print(f"  {defect_type}: {len(train_items)} train, {len(val_items)} val, {len(test_items)} test")

    # Shuffle splits to mix defect types
    random.shuffle(train_set)
    random.shuffle(val_set)
    random.shuffle(test_set)

    return train_set, val_set, test_set


def split_dataset(
    synthetic_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.20,
    test_ratio: float = 0.10,
    random_seed: int = 42
) -> Dict[str, List[Dict]]:
    """
    Load and split synthetic dataset.

    Args:
        synthetic_dir: Path to output/synthetic directory
        train_ratio: Training set fraction
        val_ratio: Validation set fraction
        test_ratio: Test set fraction
        random_seed: Random seed for reproducibility

    Returns:
        Dict with keys 'train', 'val', 'test' containing split datasets
    """
    print(f"Loading dataset from {synthetic_dir}...")
    dataset = load_synthetic_dataset(synthetic_dir)
    print(f"Loaded {len(dataset)} images")

    print(f"\nSplitting dataset (train={train_ratio}, val={val_ratio}, test={test_ratio})...")
    train_set, val_set, test_set = stratified_split(
        dataset, train_ratio, val_ratio, test_ratio, random_seed
    )

    print(f"\nFinal split:")
    print(f"  Train: {len(train_set)} ({len(train_set)/len(dataset)*100:.1f}%)")
    print(f"  Val:   {len(val_set)} ({len(val_set)/len(dataset)*100:.1f}%)")
    print(f"  Test:  {len(test_set)} ({len(test_set)/len(dataset)*100:.1f}%)")

    return {
        "train": train_set,
        "val": val_set,
        "test": test_set
    }


def verify_split_distribution(splits: Dict[str, List[Dict]]):
    """
    Verify that defect type distribution is consistent across splits.

    Args:
        splits: Dict with 'train', 'val', 'test' splits
    """
    print("\n=== Split Distribution Verification ===")

    for split_name, split_data in splits.items():
        by_type = defaultdict(int)
        for item in split_data:
            by_type[item["defect_type"]] += 1

        total = len(split_data)
        print(f"\n{split_name.upper()} ({total} images):")
        for defect_type in sorted(by_type.keys()):
            count = by_type[defect_type]
            pct = count / total * 100
            print(f"  {defect_type}: {count} ({pct:.1f}%)")
