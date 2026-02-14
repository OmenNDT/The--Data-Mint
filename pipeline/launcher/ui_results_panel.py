"""UI Results Panel - Results dashboard components."""

import gradio as gr
from pathlib import Path
from typing import List, Optional, Dict, Any
import json


def create_results_panel() -> Dict[str, Any]:
    """Create results dashboard panel components.

    Returns:
        Dict of Gradio components
    """
    components = {}

    with gr.Group():
        # Run summary
        gr.Markdown("### 📊 Tổng kết")

        run_summary = gr.Markdown(
            value="*Chưa có kết quả*",
            elem_classes=["run-summary"]
        )

        # QA Results
        gr.Markdown("### 🔍 Kết quả QA")

        with gr.Row():
            qa_ssim = gr.Markdown(value="**SSIM:** ---")
            qa_pass_rate = gr.Markdown(value="**Pass Rate:** ---")

        with gr.Row():
            qa_coco = gr.Markdown(value="**COCO:** ---")
            qa_yolo = gr.Markdown(value="**YOLO:** ---")

        # Validation Results
        gr.Markdown("### 📈 Kết quả Đánh giá")

        validation_table = gr.Dataframe(
            headers=["Ratio", "mAP@0.5", "mAP@0.5:0.95"],
            datatype=["str", "number", "number"],
            row_count=3,
            value=[],
            wrap=True
        )

        optimal_ratio = gr.Markdown(
            value="*Ratio tối ưu: ---*",
            visible=True
        )

        # Sample images
        gr.Markdown("### 🖼️ Ảnh mẫu")

        image_gallery = gr.Gallery(
            columns=6,
            rows=2,
            object_fit="cover",
            height="auto"
        )

        # Report buttons
        with gr.Row():
            open_qa_btn = gr.Button("📄 Mở báo cáo QA")
            open_validation_btn = gr.Button("📊 Mở báo cáo Đánh giá")

    components = {
        "run_summary": run_summary,
        "qa_ssim": qa_ssim,
        "qa_pass_rate": qa_pass_rate,
        "qa_coco": qa_coco,
        "qa_yolo": qa_yolo,
        "validation_table": validation_table,
        "optimal_ratio": optimal_ratio,
        "image_gallery": image_gallery,
        "open_qa_btn": open_qa_btn,
        "open_validation_btn": open_validation_btn,
    }

    return components


def load_qa_results(output_dir: str) -> Dict[str, Any]:
    """Load QA results from output directory.

    Args:
        output_dir: Base output directory

    Returns:
        Dict with QA results
    """
    qa_results_path = Path(output_dir) / "qa-reports" / "qa-results.json"

    if not qa_results_path.exists():
        return {
            "ssim_mean": None,
            "ssim_std": None,
            "pass_rate": None,
            "coco_valid": None,
            "yolo_valid": None,
        }

    try:
        with open(qa_results_path, 'r') as f:
            data = json.load(f)

        return {
            "ssim_mean": data.get("ssim_mean", 0),
            "ssim_std": data.get("ssim_std", 0),
            "pass_rate": data.get("pass_rate", 0),
            "coco_valid": data.get("coco_validation_valid", False),
            "yolo_valid": data.get("yolo_validation_valid", False),
        }
    except Exception as e:
        return {"error": str(e)}


def load_validation_results(output_dir: str) -> Dict[str, Any]:
    """Load validation results from output directory.

    Args:
        output_dir: Base output directory

    Returns:
        Dict with validation results
    """
    val_results_path = Path(output_dir) / "validation" / "validation-results.json"

    if not val_results_path.exists():
        return {"experiments": [], "optimal_ratio": None}

    try:
        with open(val_results_path, 'r') as f:
            data = json.load(f)

        return {
            "experiments": data.get("experiments", []),
            "optimal_ratio": data.get("optimal_ratio"),
        }
    except Exception as e:
        return {"error": str(e)}


def get_sample_images(
    output_dir: str,
    count: int = 12
) -> List[str]:
    """Get sample generated images.

    Args:
        output_dir: Base output directory
        count: Number of images to return

    Returns:
        List of image paths
    """
    import random

    synthetic_dir = Path(output_dir) / "synthetic"

    if not synthetic_dir.exists():
        return []

    # Find all PNG files
    image_files = []
    for defect_dir in synthetic_dir.iterdir():
        if defect_dir.is_dir():
            image_files.extend(list(defect_dir.glob("*.png")))

    if not image_files:
        return []

    # Random sample
    sample = random.sample(
        image_files,
        min(count, len(image_files))
    )

    return [str(p) for p in sample]


def format_qa_display(qa_results: Dict[str, Any]) -> Dict[str, Any]:
    """Format QA results for display.

    Args:
        qa_results: QA results dict

    Returns:
        Dict of formatted strings for UI
    """
    if "error" in qa_results:
        return {
            "ssim": "**SSIM:** Lỗi",
            "pass_rate": "**Pass Rate:** Lỗi",
            "coco": "**COCO:** Lỗi",
            "yolo": "**YOLO:** Lỗi",
        }

    ssim = qa_results.get("ssim_mean")
    if ssim is not None:
        ssim_text = f"**SSIM:** {ssim:.3f} ± {qa_results.get('ssim_std', 0):.3f}"
    else:
        ssim_text = "**SSIM:** ---"

    pass_rate = qa_results.get("pass_rate")
    if pass_rate is not None:
        pass_text = f"**Pass Rate:** {pass_rate*100:.1f}%"
    else:
        pass_text = "**Pass Rate:** ---"

    coco = qa_results.get("coco_valid")
    coco_text = f"**COCO:** {'✅ Hợp lệ' if coco else ('❌ Không hợp lệ' if coco is not None else '---')}"

    yolo = qa_results.get("yolo_valid")
    yolo_text = f"**YOLO:** {'✅ Hợp lệ' if yolo else ('❌ Không hợp lệ' if yolo is not None else '---')}"

    return {
        "ssim": ssim_text,
        "pass_rate": pass_text,
        "coco": coco_text,
        "yolo": yolo_text,
    }


def format_validation_display(val_results: Dict[str, Any]) -> Dict[str, Any]:
    """Format validation results for display.

    Args:
        val_results: Validation results dict

    Returns:
        Dict of formatted data for UI
    """
    if "error" in val_results:
        return {
            "table": [],
            "optimal": "*Ratio tối ưu: Lỗi*",
        }

    experiments = val_results.get("experiments", [])

    # Build table data
    table_data = []
    for exp in experiments:
        ratio = exp.get("ratio", "N/A")
        map_50 = exp.get("map50", 0)
        map_50_95 = exp.get("map50_95", 0)
        table_data.append([str(ratio), f"{map_50:.3f}", f"{map_50_95:.3f}"])

    # Optimal ratio
    optimal = val_results.get("optimal_ratio")
    if optimal is not None:
        optimal_text = f"*Ratio tối ưu: {optimal*100:.0f}% synthetic*"
    else:
        optimal_text = "*Ratio tối ưu: ---*"

    return {
        "table": table_data,
        "optimal": optimal_text,
    }


def format_run_summary(
    total_seconds: float,
    images_generated: int,
    phases_completed: List[str]
) -> str:
    """Format run summary for display.

    Args:
        total_seconds: Total runtime in seconds
        images_generated: Number of images generated
        phases_completed: List of completed phase names

    Returns:
        Formatted markdown string
    """
    hours = int(total_seconds // 3600)
    mins = int((total_seconds % 3600) // 60)
    secs = int(total_seconds % 60)

    if hours > 0:
        time_str = f"{hours}h {mins}p {secs}giây"
    elif mins > 0:
        time_str = f"{mins}p {secs}giây"
    else:
        time_str = f"{secs}giây"

    phases_str = ", ".join(phases_completed) if phases_completed else "Không có"

    return f"""
**⏱️ Thời gian:** {time_str}

**🖼️ Số ảnh:** {images_generated:,}

**✅ Các Phase hoàn thành:** {phases_str}
"""
