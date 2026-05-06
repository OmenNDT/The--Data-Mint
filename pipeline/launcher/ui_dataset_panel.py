"""UI Dataset Panel - Dataset selection + config components."""

import gradio as gr
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

from .config_preset_manager import ConfigPresetManager, PresetInfo
from .ui_icons import icon, get_ui_icon, get_button_label


def browse_folder() -> str:
    """Open native folder dialog and return selected path."""
    if not HAS_TKINTER:
        return ""

    def _browse():
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        folder_selected = filedialog.askdirectory(title="Chọn thư mục dataset")

        root.destroy()
        return folder_selected

    # Run in thread to avoid blocking
    result = [None]

    def thread_func():
        result[0] = _browse()

    t = threading.Thread(target=thread_func)
    t.start()
    t.join()

    return result[0] or ""


def create_dataset_panel(
    preset_manager: ConfigPresetManager
) -> Dict[str, Any]:
    """Create dataset selection and config panel components.

    Args:
        preset_manager: ConfigPresetManager instance

    Returns:
        Dict of Gradio components
    """
    # Load presets
    presets = preset_manager.list_presets()
    preset_choices = [(p.name, p.file_path.stem) for p in presets]
    preset_stems = [p.file_path.stem for p in presets]

    # Default to pilot
    default_preset = "pilot" if "pilot" in preset_stems else (preset_stems[0] if preset_stems else "pilot")

    components = {}

    with gr.Group():
        # Dataset folder
        with gr.Row():
            dataset_path = gr.Textbox(
                label="Thư mục Dataset",
                placeholder="Chọn thư mục chứa ảnh X-ray gốc...",
                scale=4
            )
            browse_btn = gr.Button(get_button_label("browse"), scale=1, variant="secondary")

        # Preset selection
        with gr.Row():
            preset_dropdown = gr.Dropdown(
                choices=preset_choices,
                value=default_preset,
                label="Preset",
                scale=3
            )
            estimate_text = gr.Markdown(
                value="*Ước tính: ~30 phút*",
                scale=2
            )

        # Expert mode toggle
        expert_checkbox = gr.Checkbox(
            label="Chế độ Expert (tinh chỉnh tham số)",
            value=False
        )

        # Expert override fields (hidden by default)
        with gr.Group(visible=False) as expert_group:
            with gr.Row():
                total_images = gr.Number(
                    value=500,
                    label="Số lượng ảnh",
                    minimum=1,
                    maximum=100000,
                    step=100
                )
                epochs = gr.Number(
                    value=20,
                    label="Epochs",
                    minimum=1,
                    maximum=1000,
                    step=1
                )
                batch_size = gr.Number(
                    value=16,
                    label="Batch Size",
                    minimum=1,
                    maximum=256,
                    step=1
                )

            with gr.Row():
                model_size = gr.Dropdown(
                    choices=[("Nano", "n"), ("Small", "s"), ("Medium", "m"), ("Large", "l")],
                    value="n",
                    label="Model Size"
                )
                train_ratio = gr.Slider(
                    minimum=0.5,
                    maximum=0.9,
                    value=0.7,
                    step=0.05,
                    label="Train Ratio"
                )

    # Phase selection
    with gr.Group():
        gr.Markdown(f'{icon("layers", 16, "#10b981")} **Các Phase chạy**')

        with gr.Row():
            phase6_check = gr.Checkbox(label="Phase 6: Tạo ảnh", value=True)
            phase7_check = gr.Checkbox(label="Phase 7: Hậu xử lý", value=True)
        
        with gr.Row():
            phase8_check = gr.Checkbox(label="Phase 8: Kiểm tra QA", value=True)
            phase9_check = gr.Checkbox(label="Phase 9: Đánh giá (cần dataset thực)")

        # Real dataset path for Phase 9
        with gr.Group(visible=False) as phase9_group:
            with gr.Row():
                real_yolo_dir = gr.Textbox(
                    label="Đường dẫn Dataset YOLO thực",
                    placeholder="Đường dẫn đến dataset thực (YOLO format)..."
                )
                browse_real_btn = gr.Button(get_button_label("browse"), variant="secondary")

    # Checkpoint resume
    with gr.Group():
        gr.Markdown(f'{icon("save", 16, "#10b981")} **Checkpoint**')
        
        resume_info = gr.Markdown(
            value="*Không có checkpoint nào được tìm thấy*",
            visible=True
        )
        resume_checkbox = gr.Checkbox(
            label="Tiếp tục từ checkpoint",
            value=False,
            visible=False
        )

    components = {
        "dataset_path": dataset_path,
        "browse_btn": browse_btn,
        "preset_dropdown": preset_dropdown,
        "estimate_text": estimate_text,
        "expert_checkbox": expert_checkbox,
        "expert_group": expert_group,
        "total_images": total_images,
        "epochs": epochs,
        "batch_size": batch_size,
        "model_size": model_size,
        "train_ratio": train_ratio,
        "phase6_check": phase6_check,
        "phase7_check": phase7_check,
        "phase8_check": phase8_check,
        "phase9_check": phase9_check,
        "phase9_group": phase9_group,
        "real_yolo_dir": real_yolo_dir,
        "browse_real_btn": browse_real_btn,
        "resume_info": resume_info,
        "resume_checkbox": resume_checkbox,
        "presets": presets,
    }

    return components


def update_estimate(preset_name: str, presets: List[PresetInfo]) -> str:
    """Update runtime estimate when preset changes."""
    for p in presets:
        if p.file_path.stem == preset_name:
            hours = p.estimated_minutes // 60
            mins = p.estimated_minutes % 60
            if hours > 0:
                return f"*Ước tính: ~{hours}h {mins}p*"
            else:
                return f"*Ước tính: ~{mins} phút*"
    return "*Ước tính: ---*"


def get_phases_to_run(
    phase6: bool,
    phase7: bool,
    phase8: bool,
    phase9: bool
) -> List[int]:
    """Get list of phases to run based on checkbox states."""
    phases = []
    if phase6:
        phases.append(6)
    if phase7:
        phases.append(7)
    if phase8:
        phases.append(8)
    if phase9:
        phases.append(9)
    return phases
