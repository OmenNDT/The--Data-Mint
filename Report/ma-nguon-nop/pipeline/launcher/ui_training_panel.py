"""Training LoRA tab for the Gradio launcher UI.

Allows users to configure and run kohya-ss LoRA training
directly from the web interface, with advanced parameter tuning.
"""

import gradio as gr

from .training_config_utils import (
    TRAINING_DATA_DIR, MODELS_DIR, KOHYA_DIR,
    get_available_defect_types, get_available_configs,
    get_existing_loras, load_config_params,
)
from .training_process_manager import (
    detect_running_training, run_training, cancel_training,
)


def _format_running_status(status):
    """Format running training status as Markdown."""
    if status.running:
        return (
            f"### 🔄 Training đang chạy\n"
            f"**Defect:** {status.defect_type} | **PID:** {status.pid} | **Tiến trình:** {status.progress_pct}%"
        )
    return "### ✅ Không có training nào đang chạy"


def _create_advanced_params_section():
    """Create advanced parameters accordion. Returns ordered dict of components."""
    components = {}
    with gr.Accordion("🔧 Tham số chuyên sâu (Advanced)", open=False):
        with gr.Row():
            components["optimizer_type"] = gr.Dropdown(
                choices=["AdamW8bit", "AdamW", "Lion", "SGDNesterov8bit", "Prodigy"],
                value="AdamW8bit", label="Optimizer",
            )
            components["lr_scheduler"] = gr.Dropdown(
                choices=["cosine_with_restarts", "cosine", "constant", "constant_with_warmup", "linear", "polynomial"],
                value="cosine_with_restarts", label="LR Scheduler",
            )
        with gr.Row():
            components["lr_warmup_steps"] = gr.Number(value=200, label="LR Warmup Steps", minimum=0)
            components["lr_scheduler_num_cycles"] = gr.Number(value=4, label="Scheduler Cycles", minimum=1)
            components["gradient_accumulation_steps"] = gr.Number(value=2, label="Gradient Accumulation", minimum=1)
        with gr.Row():
            components["gradient_checkpointing"] = gr.Checkbox(value=True, label="Gradient Checkpointing")
            components["mixed_precision"] = gr.Dropdown(
                choices=["fp16", "bf16", "no"], value="fp16", label="Mixed Precision",
            )
            components["xformers"] = gr.Checkbox(value=True, label="xformers")
        with gr.Row():
            components["clip_skip"] = gr.Number(value=2, label="CLIP Skip", minimum=1, maximum=4)
            components["seed"] = gr.Number(value=42, label="Seed")
            components["save_every_n_epochs"] = gr.Number(value=2, label="Save Every N Epochs", minimum=1)
        with gr.Row():
            components["keep_tokens"] = gr.Number(value=1, label="Keep Tokens", minimum=0)
            components["shuffle_caption"] = gr.Checkbox(value=True, label="Shuffle Caption")
            components["cache_latents"] = gr.Checkbox(value=True, label="Cache Latents")
        with gr.Row():
            components["enable_bucket"] = gr.Checkbox(value=True, label="Enable Bucket")
            components["resolution"] = gr.Textbox(value="512,512", label="Resolution")
    return components


def create_training_tab():
    """Create the Training LoRA tab UI.

    Returns:
        dict with 'load_fn' and 'load_outputs' for parent to wire demo.load().
    """
    configs = get_available_configs()
    defect_choices = [(name, name) for name, _ in get_available_defect_types()]
    config_map = {name: path for name, path in configs}

    # --- Running training status (updated dynamically on page load) ---
    with gr.Group():
        running_status_md = gr.Markdown("### ⏳ Đang kiểm tra trạng thái training...")
        running_log = gr.Textbox(
            value="", label="Log (CLI training)", lines=8, interactive=False, visible=False,
        )
        refresh_btn = gr.Button("🔄 Làm mới trạng thái", size="sm")

    # --- Output location & existing LoRAs ---
    existing = get_existing_loras()
    lora_list = f"**LoRA đã có:** {', '.join(existing)}" if existing else "*Chưa có LoRA nào*"
    gr.Markdown(
        f"### 📦 Output\n"
        f"- **Model cuối cùng:** `{MODELS_DIR / 'loras'}/`\n"
        f"- **Checkpoint theo epoch:** `{KOHYA_DIR / 'output'}/<defect_type>/`\n"
        f"- **Sample images:** `{KOHYA_DIR / 'output'}/<defect_type>/sample/`\n"
        f"- {lora_list}"
    )

    # --- Defect type ---
    with gr.Group():
        gr.Markdown("### 🎯 Chọn Defect Type")
        defect_dropdown = gr.Dropdown(
            choices=defect_choices,
            value=defect_choices[0][1] if defect_choices else None,
            label="Loại khuyết tật",
        )
        defect_info = gr.Markdown("*Chọn defect type để xem thông tin*")

    # --- Dataset paths ---
    with gr.Group():
        gr.Markdown("### 📁 Dataset")
        dataset_input = gr.Textbox(
            label="Thư mục Training Data",
            value=str(TRAINING_DATA_DIR / "crack") if (TRAINING_DATA_DIR / "crack").exists() else "",
        )
        reg_input = gr.Textbox(
            label="Thư mục Regularization (ảnh sạch)",
            value=str(TRAINING_DATA_DIR / "reg") if (TRAINING_DATA_DIR / "reg").exists() else "",
        )

    # --- Training parameters ---
    with gr.Group():
        gr.Markdown("### ⚙️ Training Parameters")
        checkpoints = sorted((MODELS_DIR / "checkpoints").glob("*.safetensors")) if (MODELS_DIR / "checkpoints").exists() else []
        base_model_input = gr.Dropdown(
            choices=[(f.name, str(f)) for f in checkpoints],
            value=str(checkpoints[0]) if checkpoints else "",
            label="Base Model (Checkpoint)",
        )
        with gr.Row():
            epochs_input = gr.Number(value=20, label="Epochs", minimum=1, maximum=100)
            batch_input = gr.Number(value=4, label="Batch Size", minimum=1, maximum=16)
            lr_input = gr.Textbox(value="5e-5", label="Learning Rate")
        with gr.Row():
            dim_input = gr.Number(value=32, label="Network Dim (rank)", minimum=4, maximum=128)
            alpha_input = gr.Number(value=16, label="Network Alpha", minimum=1, maximum=128)

    # --- Advanced parameters ---
    adv = _create_advanced_params_section()
    adv_keys = list(adv.keys())
    adv_components = list(adv.values())

    # --- Buttons ---
    with gr.Row():
        train_btn = gr.Button("🚀 Bắt đầu Training", variant="primary", size="lg")
        cancel_btn = gr.Button("⏹️ Hủy Training", variant="stop", size="lg", visible=False)

    # --- Training log ---
    with gr.Group():
        gr.Markdown("### 📝 Training Log")
        with gr.Row():
            train_progress = gr.Slider(0, 100, 0, label="Tiến trình", interactive=False, scale=4)
            train_pct = gr.Textbox("0%", scale=1, interactive=False)
        train_log = gr.Textbox(label="Log", lines=20, interactive=False)

    # --- Event: refresh running status (on page load + button click) ---
    def on_refresh():
        s = detect_running_training()
        return _format_running_status(s), gr.update(value=s.log_tail, visible=s.running)

    refresh_btn.click(fn=on_refresh, outputs=[running_status_md, running_log])

    # --- Event: defect type change → update all params from config ---
    def on_defect_change(defect_name):
        defects = get_available_defect_types()
        info = ""
        for name, count in defects:
            if name == defect_name:
                info = f"📊 **{name}**: {count} ảnh training"
                break
        ds_path = str(TRAINING_DATA_DIR / defect_name) if (TRAINING_DATA_DIR / defect_name).exists() else ""
        config_path = config_map.get(defect_name, "")
        p = load_config_params(config_path)
        basic = [info, ds_path, p["epochs"], p["batch_size"], p["learning_rate"], p["network_dim"], p["network_alpha"]]
        advanced = [p[k] for k in adv_keys]
        return basic + advanced

    basic_outputs = [defect_info, dataset_input, epochs_input, batch_input, lr_input, dim_input, alpha_input]
    defect_dropdown.change(
        fn=on_defect_change, inputs=[defect_dropdown],
        outputs=basic_outputs + adv_components,
    )

    # --- Event: start training ---
    def on_train(defect_type, dataset_path, reg_path, base_model,
                 epochs, batch_size, lr, dim, alpha, *adv_values):
        params = {
            "epochs": epochs, "batch_size": batch_size, "learning_rate": lr,
            "network_dim": dim, "network_alpha": alpha,
            "dataset_path": dataset_path, "reg_path": reg_path, "base_model": base_model,
        }
        for key, val in zip(adv_keys, adv_values):
            params[key] = val
        yield from run_training(defect_type, params)

    train_btn.click(
        fn=on_train,
        inputs=[defect_dropdown, dataset_input, reg_input, base_model_input,
                epochs_input, batch_input, lr_input, dim_input, alpha_input] + adv_components,
        outputs=[train_log, train_progress, train_pct, train_btn, cancel_btn],
    )
    cancel_btn.click(fn=cancel_training)

    # Return load-event info for parent to wire demo.load()
    return {"load_fn": on_refresh, "load_outputs": [running_status_md, running_log]}
