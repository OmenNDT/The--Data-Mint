#!/usr/bin/env python3
"""Data Mint MCP Server — Synthetic NDT Data Pipeline tools for OpenClaw agents."""

from fastmcp import FastMCP
from pathlib import Path

# Project root for all path resolution
PROJECT_ROOT = Path("/home/sontn/Projects/The Data Mint")

mcp = FastMCP("data-mint")

# Import and register tools from modules
from tools.pipeline_status_tool import register as register_pipeline_status
from tools.dataset_info_tool import register as register_dataset_info
from tools.comfyui_health_tool import register as register_comfyui_health
from tools.train_model_tool import register as register_train_model
from tools.benchmark_results_tool import register as register_benchmark_results
from tools.run_phase_tool import register as register_run_phase

register_pipeline_status(mcp, PROJECT_ROOT)
register_dataset_info(mcp, PROJECT_ROOT)
register_comfyui_health(mcp, PROJECT_ROOT)
register_train_model(mcp, PROJECT_ROOT)
register_benchmark_results(mcp, PROJECT_ROOT)
register_run_phase(mcp, PROJECT_ROOT)


# --- MCP Resources ---

@mcp.resource("config://batch-config")
def get_batch_config() -> str:
    """Batch generation configuration (defect distribution, sampler, thermal limits)."""
    config_path = PROJECT_ROOT / "pipeline" / "config" / "batch-config.yaml"
    return config_path.read_text() if config_path.exists() else "batch-config.yaml not found"


@mcp.resource("config://mask-config")
def get_mask_config() -> str:
    """Mask generation configuration (defect parameters, ROI, feathering)."""
    config_path = PROJECT_ROOT / "pipeline" / "config" / "mask-config.yaml"
    return config_path.read_text() if config_path.exists() else "mask-config.yaml not found"


@mcp.resource("dataset://riawelc-stats")
def get_riawelc_stats() -> str:
    """Pre-computed RIAWELC dataset statistics."""
    riawelc_root = PROJECT_ROOT / "dataset" / "RIAWELC" / "extracted" / "DB - Copy"
    if not riawelc_root.exists():
        return "RIAWELC dataset not found"

    stats = {"total": 0, "splits": {}}
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

    import json
    return json.dumps(stats, indent=2)


@mcp.resource("report://latest-qa")
def get_latest_qa_report() -> str:
    """Latest QA report content."""
    qa_report = PROJECT_ROOT / "output" / "qa-reports" / "qa-report.md"
    if qa_report.exists():
        return qa_report.read_text()
    return "No QA report found"


if __name__ == "__main__":
    mcp.run()
