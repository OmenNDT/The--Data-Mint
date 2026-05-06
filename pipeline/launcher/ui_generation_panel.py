"""Phase 6 Image Generation tab for the Gradio launcher UI.

Allows users to configure and run ComfyUI batch image generation
directly from the web interface, with model selection, prompt editing,
sampler tuning, and real-time progress tracking.
"""

import logging

import gradio as gr

from .generation_config_utils import (
    DEFECT_TYPES, DEFAULT_SAMPLER,
    scan_checkpoints, scan_controlnets, scan_loras,
    load_prompt_templates, load_batch_config,
)
from .generation_process_manager import run_generation, cancel_generation
from .launcher_utils import check_comfyui_connection
from .ui_icons import icon, get_ui_icon, get_button_label

logger = logging.getLogger(__name__)


def _check_comfyui_status() -> str:
    """Check ComfyUI connection and return status HTML."""
    ok, msg = check_comfyui_connection()
    if ok:
        return f'''
        <div class="dm-status-bar">
            <div class="dm-status-item">
                <div class="dm-status-indicator"></div>
                <span><strong>ComfyUI:</strong> Đã kết nối</span>
            </div>
        </div>
        '''
    return f'''
    <div class="dm-status-bar">
        <div class="dm-status-item">
            <div class="dm-status-indicator offline"></div>
            <span><strong>ComfyUI:</strong> Chưa kết nối — {msg or 'Kiểm tra server đang chạy'}</span>
        </div>
    </div>
    '''


def _create_prompt_section(templates: dict) -> dict:
    """Create per-defect prompt accordion. Returns component dict."""
    components = {}
    with gr.Accordion(f'{icon("file_text", 14, "#94a3b8")} Prompts (chỉnh sửa)', open=False):
        for defect in DEFECT_TYPES:
            tpl = templates.get(defect, {})
            with gr.Group():
                gr.Markdown(f"**{defect}**")
                components[f"{defect}_positive"] = gr.Textbox(
                    value=tpl.get("positive", ""), label="Positive",
                    lines=2, interactive=True,
                )
                components[f"{defect}_negative"] = gr.Textbox(
                    value=tpl.get("negative", ""), label="Negative",
                    lines=2, interactive=True,
                )
                with gr.Row():
                    components[f"{defect}_lora_strength"] = gr.Slider(
                        0.0, 1.5, value=tpl.get("lora_strength", 0.7),
                        step=0.05, label="LoRA Strength", interactive=True,
                    )
                    components[f"{defect}_cn_strength"] = gr.Slider(
                        0.0, 1.5, value=tpl.get("controlnet_strength", 0.8),
                        step=0.05, label="ControlNet Strength", interactive=True,
                    )
                    components[f"{defect}_denoise"] = gr.Slider(
                        0.0, 1.0, value=tpl.get("denoise", 0.85),
                        step=0.05, label="Denoise", interactive=True,
                    )
    return components


def _create_sampler_section(sampler_cfg: dict) -> dict:
    """Create sampler parameters accordion."""
    components = {}
    with gr.Accordion(f'{icon("sliders", 14, "#94a3b8")} Sampler', open=False):
        with gr.Row():
            components["sampler_name"] = gr.Dropdown(
                choices=["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim", "uni_pc"],
                value=sampler_cfg.get("name", "euler"), label="Sampler",
                interactive=True,
            )
            components["scheduler"] = gr.Dropdown(
                choices=["normal", "karras", "exponential", "sgm_uniform"],
                value=sampler_cfg.get("scheduler", "normal"), label="Scheduler",
                interactive=True,
            )
        with gr.Row():
            components["steps"] = gr.Number(
                value=sampler_cfg.get("steps", 20), label="Steps",
                minimum=1, maximum=100, interactive=True,
            )
            components["cfg"] = gr.Number(
                value=sampler_cfg.get("cfg", 7.0), label="CFG Scale",
                minimum=1.0, maximum=30.0, interactive=True,
            )
            components["seed"] = gr.Number(
                value=sampler_cfg.get("seed", -1), label="Seed (-1 = random)",
                interactive=True,
            )
    return components


def create_generation_tab():
    """Create the Phase 6 Image Generation tab UI.

    Returns:
        dict with 'load_fn' and 'load_outputs' for parent to wire demo.load().
    """
    templates = load_prompt_templates()
    batch_cfg = load_batch_config()
    paths_cfg = batch_cfg.get("paths", {})
    gen_cfg = batch_cfg.get("generation", {})
    sampler_cfg = batch_cfg.get("sampler", DEFAULT_SAMPLER)
    dist = gen_cfg.get("defect_distribution", {d: 0.2 for d in DEFECT_TYPES})

    # --- ComfyUI status ---
    with gr.Column(elem_classes=["dm-card"]):
        comfyui_status_md = gr.HTML("<div class='dm-status-bar'><div class='dm-status-item'><div class='dm-status-indicator offline'></div><span><strong>ComfyUI:</strong> Đang kiểm tra...</span></div></div>")
        refresh_btn = gr.Button(get_button_label("refresh"), size="sm", variant="secondary")
    

    # --- Models ---
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("cpu", 18, "#10b981")} Models</div>')
        checkpoint_choices = scan_checkpoints()
        gr.Dropdown(
            choices=checkpoint_choices,
            value=checkpoint_choices[0][1] if checkpoint_choices else "",
            label="Checkpoint (.safetensors)",
            allow_custom_value=True, interactive=True,
        )
        controlnet_choices = scan_controlnets()
        gr.Dropdown(
            choices=controlnet_choices,
            value=controlnet_choices[0][1] if controlnet_choices else "",
            label="ControlNet (.pth / .safetensors)",
            allow_custom_value=True, interactive=True,
        )
        lora_choices = scan_loras()
        gr.CheckboxGroup(
            choices=[name for name, _ in lora_choices],
            value=[name for name, _ in lora_choices],
            label="LoRA models (chọn để sử dụng)",
            interactive=True,
        )
    

    # --- Defect config ---
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("target", 18, "#10b981")} Cấu hình Defect</div>')
        total_images_input = gr.Number(
            value=gen_cfg.get("total_images", 100),
            label="Tổng số ảnh", minimum=1, interactive=True,
        )
        gr.Markdown("*Phân bổ % (tổng nên = 100%):*")
        dist_sliders = {}
    with gr.Row():
        for defect in DEFECT_TYPES:
            pct = round(dist.get(defect, 0.2) * 100)
            dist_sliders[defect] = gr.Slider(
                0, 100, value=pct, step=5,
                label=defect.replace("_", " ").title(),
                interactive=True,
            )
    

    # --- Prompts & Sampler ---
    _create_prompt_section(templates)
    sampler_components = _create_sampler_section(sampler_cfg)

    # --- Paths ---
    with gr.Column(elem_classes=["dm-card"]):
        gr.HTML(f'<div class="dm-card-header">{icon("folder_open", 18, "#10b981")} Đường dẫn</div>')
        bg_dir_input = gr.Textbox(
            value=paths_cfg.get("backgrounds_dir", ""),
            label="Thư mục ảnh nền (background)", interactive=True,
        )
        output_dir_input = gr.Textbox(
            value=paths_cfg.get("output_base_dir", ""),
            label="Thư mục output", interactive=True,
        )
        pilot_checkbox = gr.Checkbox(
            label="Pilot mode (5 ảnh test nhanh)", value=False,
            interactive=True,
        )
    

    # --- Buttons ---
    with gr.Row():
        run_btn = gr.Button(get_button_label("run_pipeline"), variant="primary", size="lg", elem_classes=["dm-btn-primary"])
        cancel_btn = gr.Button(get_button_label("cancel"), variant="stop", size="lg", visible=False, elem_classes=["dm-btn-danger"])

    # --- Progress (read-only) ---
    with gr.Column(elem_classes=["dm-progress-container"]):
        gr.HTML(f'<div class="dm-card-header">{icon("activity", 18, "#10b981")} Tiến trình</div>')
    with gr.Row():
        gen_progress = gr.Slider(0, 100, 0, label="Tiến trình", interactive=False, scale=4)
        gen_pct = gr.Textbox("0%", scale=1, interactive=False)
    gen_log = gr.Textbox(label="Log", lines=20, interactive=False)
    

    # --- Events ---
    refresh_btn.click(fn=_check_comfyui_status, outputs=[comfyui_status_md])

    def on_run(total_images, bg_dir, output_dir, pilot_mode, *slider_and_sampler_values):
        slider_vals = list(slider_and_sampler_values[:5])
        sampler_vals = list(slider_and_sampler_values[5:])

        defect_dist = {}
        for i, defect in enumerate(DEFECT_TYPES):
            defect_dist[defect] = slider_vals[i]
        total_pct = sum(defect_dist.values())
        if total_pct > 0:
            defect_dist = {k: round(v / total_pct, 4) for k, v in defect_dist.items()}

        params = {
            "total_images": total_images,
            "defect_distribution": defect_dist,
            "backgrounds_dir": bg_dir,
            "output_base_dir": output_dir,
            "pilot_mode": pilot_mode,
            "sampler_name": sampler_vals[0] if len(sampler_vals) > 0 else "euler",
            "sampler_scheduler": sampler_vals[1] if len(sampler_vals) > 1 else "normal",
            "sampler_steps": int(sampler_vals[2]) if len(sampler_vals) > 2 else 20,
            "sampler_cfg": float(sampler_vals[3]) if len(sampler_vals) > 3 else 7.0,
        }
        yield from run_generation(params)

    slider_inputs = [dist_sliders[d] for d in DEFECT_TYPES]
    sampler_inputs = [
        sampler_components["sampler_name"],
        sampler_components["scheduler"],
        sampler_components["steps"],
        sampler_components["cfg"],
    ]

    run_btn.click(
        fn=on_run,
        inputs=[total_images_input, bg_dir_input, output_dir_input, pilot_checkbox]
               + slider_inputs + sampler_inputs,
        outputs=[gen_log, gen_progress, gen_pct, run_btn, cancel_btn],
    )
    cancel_btn.click(fn=cancel_generation)

    return {"load_fn": _check_comfyui_status, "load_outputs": [comfyui_status_md]}
