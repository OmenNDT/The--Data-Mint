"""UI Results Panel - Results dashboard components with metric cards and empty states."""

import gradio as gr
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

from .ui_icons import icon, get_ui_icon, get_button_label


def create_empty_state_html(icon_name: str, title: str, description: str) -> str:
    """Create empty state HTML.

    Args:
        icon_name: Icon name from ui_icons
        title: Empty state title
        description: Empty state description

    Returns:
        HTML string for empty state
    """
    return f'''
    <div class="dm-empty-state">
        <div class="dm-empty-state-icon">{icon(icon_name, 48, "#475569")}</div>
        <div class="dm-empty-state-title">{title}</div>
        <div class="dm-empty-state-desc">{description}</div>
    </div>
    '''


def create_metric_card_html(value: str, label: str, status: str = "") -> str:
    """Create metric card HTML.

    Args:
        value: Metric value
        label: Metric label
        status: Optional status class (success, warning, danger)

    Returns:
        HTML string for metric card
    """
    status_class = f" {status}" if status else ""
    return f'''
    <div class="dm-metric-card{status_class}">
        <div class="dm-metric-value">{value}</div>
        <div class="dm-metric-label">{label}</div>
    </div>
    '''


def create_results_panel() -> Dict[str, Any]:
    """Create results dashboard panel components.

    Returns:
        Dict of Gradio components
    """
    components = {}

    # Run summary card
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("chart_bar", 18, "#10b981")} Tổng kết</div>')
        run_summary = gr.HTML(
            value=create_empty_state_html("chart_bar", "Chưa có kết quả", "Chạy pipeline để xem tổng kết chi tiết về thời gian, số ảnh và các phase đã hoàn thành."),
        )
    

    # QA Results card
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("shield_check", 18, "#10b981")} QA</div>')
    with gr.Row():
        qa_ssim = gr.HTML(
            value=create_metric_card_html("---", "SSIM"),
        )
        qa_pass_rate = gr.HTML(
            value=create_metric_card_html("---", "Pass Rate"),
        )
    with gr.Row():
        qa_coco = gr.HTML(
            value=create_metric_card_html("---", "COCO"),
        )
        qa_yolo = gr.HTML(
            value=create_metric_card_html("---", "YOLO"),
        )
    

    # Validation Results card
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("trending_up", 18, "#10b981")} Đánh giá</div>')
        validation_table = gr.Dataframe(
            headers=["Ratio", "mAP@0.5", "mAP@0.5:0.95"],
            datatype=["str", "number", "number"],
            row_count=3,
            value=[],
            wrap=True
        )
        optimal_ratio = gr.HTML(
            value='<div class="dm-helper-text">*Ratio tối ưu: ---*</div>',
            visible=True
        )
    

    # Sample images card
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("images", 18, "#10b981")} Ảnh mẫu</div>')
        image_gallery = gr.Gallery(
            columns=6,
            rows=2,
            object_fit="cover",
            height="auto"
        )
    

    # Report buttons
    with gr.Row():
        open_qa_btn = gr.Button(get_button_label("open"), variant="secondary")
        open_validation_btn = gr.Button(get_button_label("open"), variant="secondary")

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
        ssim_text = f"{ssim:.3f} ± {qa_results.get('ssim_std', 0):.3f}"
        ssim_status = "success" if ssim > 0.8 else "warning"
    else:
        ssim_text = "---"
        ssim_status = ""

    pass_rate = qa_results.get("pass_rate")
    if pass_rate is not None:
        pass_text = f"{pass_rate*100:.1f}%"
        pass_status = "success" if pass_rate > 0.8 else "warning"
    else:
        pass_text = "---"
        pass_status = ""

    coco = qa_results.get("coco_valid")
    if coco is True:
        coco_text = "Hợp lệ"
        coco_status = "success"
    elif coco is False:
        coco_text = "Không hợp lệ"
        coco_status = "danger"
    else:
        coco_text = "---"
        coco_status = ""

    yolo = qa_results.get("yolo_valid")
    if yolo is True:
        yolo_text = "Hợp lệ"
        yolo_status = "success"
    elif yolo is False:
        yolo_text = "Không hợp lệ"
        yolo_status = "danger"
    else:
        yolo_text = "---"
        yolo_status = ""

    return {
        "ssim": create_metric_card_html(ssim_text, "SSIM", ssim_status),
        "pass_rate": create_metric_card_html(pass_text, "Pass Rate", pass_status),
        "coco": create_metric_card_html(coco_text, "COCO", coco_status),
        "yolo": create_metric_card_html(yolo_text, "YOLO", yolo_status),
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

    # Build metric cards for summary
    time_card = create_metric_card_html(time_str, "Thời gian")
    images_card = create_metric_card_html(f"{images_generated:,}", "Số ảnh")
    phases_card = create_metric_card_html(str(len(phases_completed)), "Phase hoàn thành")

    phases_list = ""
    if phases_completed:
        phases_list = "<ul style='margin-top:8px;padding-left:20px;color:#cbd5e1;'>"
        for p in phases_completed:
            phases_list += f"<li>{p}</li>"
        phases_list += "</ul>"

    return f'''
    <div class="dm-metric-grid">
        {time_card}
        {images_card}
        {phases_card}
    </div>
    <div style="margin-top:16px;color:#94a3b8;font-size:0.875rem;">
        <strong style="color:#cbd5e1;">Các Phase hoàn thành:</strong>
        {phases_list if phases_list else '<span style="color:#64748b;"> Không có</span>'}
    </div>
    '''
