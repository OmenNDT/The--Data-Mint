"""The Data Mint - One-Click Training Launcher (Gradio UI).

Professional Gradio web UI (Vietnamese) for AI engineers.
Covers all 9 pipeline phases with maximum parameter fine-tuning.
Core UX: chọn dataset → bấm Run.
"""

import os
import gradio as gr
import logging
import threading
import queue
from pathlib import Path
from typing import Optional, List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Demo mode detection
DEMO_MODE = os.environ.get("DEMO_MODE", "").strip() in ("1", "true", "yes")

# Import launcher modules
from .pipeline_orchestrator import PipelineOrchestrator, PipelineConfig, PHASE_DEFINITIONS
from .config_preset_manager import ConfigPresetManager
from .launcher_utils import (
    check_gpu_available,
    check_comfyui_connection,
    check_disk_space,
    get_checkpoint_info,
    resolve_pipeline_path
)
from .ui_dataset_panel import (
    show_browser,
    picked_to_path,
    create_dataset_panel,
    update_estimate,
    get_phases_to_run
)
from .ui_progress_panel import (
    create_progress_panel,
    create_phase_stepper_html,
    format_log_line
)
from .ui_results_panel import (
    create_results_panel,
    load_qa_results,
    load_validation_results,
    get_sample_images,
    format_qa_display,
    format_validation_display,
    format_run_summary
)
from .ui_auto_label_panel import create_auto_label_tab
from .ui_training_panel import create_training_tab
from .ui_theme import create_theme, CUSTOM_CSS
from .ui_icons import icon, get_ui_icon, get_tab_label, get_button_label

if DEMO_MODE:
    from .demo_pipeline_runner import MockPipelineOrchestrator
    from .demo_results_data import write_fake_results


class PipelineLauncherApp:
    """Main Gradio application for pipeline launcher."""

    def __init__(self, server_port: int = 7860):
        """Initialize the launcher app.

        Args:
            server_port: Port for Gradio server
        """
        self.server_port = server_port

        # Initialize managers
        self.preset_manager = ConfigPresetManager()

        # State
        self.is_running = False
        self.current_orchestrator: Optional[PipelineOrchestrator] = None
        self.log_queue: queue.Queue = queue.Queue()

        logger.info("PipelineLauncherApp initialized")

    def build_ui(self) -> gr.Blocks:
        """Build the Gradio UI.

        Returns:
            Gradio Blocks instance
        """
        # Load presets (value=file stem for load_preset, label=display name)
        presets = self.preset_manager.list_presets()
        preset_choices = [(p.name, p.file_path.stem) for p in presets]
        preset_stems = [p.file_path.stem for p in presets]
        default_preset = "pilot" if "pilot" in preset_stems else (preset_stems[0] if preset_stems else "pilot")

        # Defect types come from the base config's defect_distribution. The user
        # picks WHICH defects to generate; the clean background folder is fixed
        # in config and shown read-only (not user-selectable).
        base_cfg = self.preset_manager._load_yaml(self.preset_manager.base_config_path)
        all_defect_types = list(base_cfg.get("generation", {}).get("defect_distribution", {}).keys())
        fixed_backgrounds_dir = base_cfg.get("paths", {}).get("backgrounds_dir", "")

        # A defect can only be generated if its LoRA exists on disk. Used to warn
        # the user if they pick a defect whose LoRA is not trained yet (e.g. LOSWF).
        lora_models = base_cfg.get("lora_models", {})
        loras_dir = resolve_pipeline_path(".").parent / "comfyui" / "models" / "loras"
        ready_defects = [
            d for d in all_defect_types
            if (loras_dir / lora_models.get(d, "")).exists()
        ]
        # Default: nothing selected — the user must explicitly pick defects to generate.
        default_defects = []

        # Check GPU and ComfyUI on startup (skip in demo mode)
        if DEMO_MODE:
            gpu_available, gpu_msg = True, "Demo Mode"
            comfyui_available, comfyui_msg = True, "Demo Mode"
        else:
            gpu_available, gpu_msg = check_gpu_available()
            # ComfyUI host/port come from config (remote box), not localhost default.
            comfyui_cfg = base_cfg.get("comfyui", {})
            comfyui_available, comfyui_msg = check_comfyui_connection(
                host=comfyui_cfg.get("host", "localhost"),
                port=comfyui_cfg.get("port", 8188),
            )

        # Build UI with custom dark theme
        self._theme = create_theme()
        self._css = CUSTOM_CSS

        with gr.Blocks(
            title="The Data Mint - One-Click Launcher",
            elem_classes=["dm-app"]
        ) as app:
            # ===== HEADER =====
            header_html = f'''
            <div class="dm-header">
                <h1>The Data Mint</h1>
                <p>One-Click Training Launcher — Giao diện chuyên nghiệp cho kỹ sư AI</p>
                <div class="dm-badge">
                    {icon("zap", 12, "#34d399")}
                    <span>Pipeline 9 Phases</span>
                </div>
                <a class="dm-badge" href="/plant-hmi/" target="_blank" rel="noopener"
                   style="text-decoration:none;margin-left:8px">
                    {icon("activity", 12, "#34d399")}
                    <span>Plant HMI</span>
                </a>
            </div>
            '''
            gr.HTML(header_html)

            # ===== DEMO BANNER =====
            if DEMO_MODE:
                gr.HTML(
                    '<div class="dm-demo-banner">'
                    f'{icon("warning", 14, "#fbbf24")}'
                    '<span style="margin-left:8px;">DEMO MODE — Pipeline giả lập, không cần GPU/ComfyUI</span>'
                    '</div>'
                )

            # ===== STATUS BAR =====
            gpu_status_class = "dm-status-indicator" if gpu_available else "dm-status-indicator offline"
            gpu_status_text = "Đã sẵn sàng" if gpu_available else gpu_msg
            comfy_status_class = "dm-status-indicator" if comfyui_available else "dm-status-indicator offline"
            comfy_status_text = "Đã kết nối" if comfyui_available else "Chưa kết nối"

            status_html = f'''
            <div class="dm-status-bar">
                <div class="dm-status-item">
                    <div class="{gpu_status_class}"></div>
                    <span><strong>GPU:</strong> {gpu_status_text}</span>
                </div>
                <div class="dm-status-item">
                    <div class="{comfy_status_class}"></div>
                    <span><strong>ComfyUI:</strong> {comfy_status_text}</span>
                </div>
                <div class="dm-status-item">
                    {icon("clock", 14, "#94a3b8")}
                    <span><strong>Ước tính:</strong> ~30 phút</span>
                </div>
            </div>
            '''
            gr.HTML(status_html)

            with gr.Tab(get_tab_label("tab_setup")):
                # Defect type selection — the user picks WHICH defects to generate.
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("layers", 18, "#10b981")} Loại khuyết tật cần sinh</div>')
                    defect_types = gr.CheckboxGroup(
                        choices=all_defect_types,
                        value=default_defects,
                        label="Chọn loại khuyết tật (tỉ lệ chia đều cho các loại đã chọn)",
                    )

                # Clean background folder is fixed in config — shown read-only.
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("folder", 18, "#10b981")} Ảnh nền sạch (cố định)</div>')
                    dataset_path = gr.Textbox(
                        label="Thư mục ảnh nền sạch (background patches) — cấu hình sẵn",
                        value=fixed_backgrounds_dir,
                        interactive=False,
                    )

                # Preset selection
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("sliders", 18, "#10b981")} Cấu hình</div>')
                    with gr.Row():
                        preset_dropdown = gr.Dropdown(
                            choices=preset_choices,
                            value=default_preset,
                            label="Preset",
                            scale=3
                        )
                        estimate_text = gr.Markdown(
                            value="*Ước tính: ~30 phút*"
                        )

                    # Expert mode
                    expert_checkbox = gr.Checkbox(
                        label="Chế độ Expert (tinh chỉnh tham số)",
                        value=False
                    )

                    with gr.Group(visible=False) as expert_group:
                        with gr.Row():
                            total_images = gr.Number(value=500, label="Số ảnh", minimum=1)
                            epochs = gr.Number(value=20, label="Epochs", minimum=1)
                            batch_size = gr.Number(value=16, label="Batch Size", minimum=1)
                        with gr.Row():
                            model_size = gr.Dropdown(
                                choices=[("Nano", "n"), ("Small", "s"), ("Medium", "m")],
                                value="n",
                                label="Model Size"
                            )

                # Phase selection
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("layers", 18, "#10b981")} Các Phase</div>')
                    with gr.Row():
                        phase6_check = gr.Checkbox(label="6: Tạo ảnh", value=True)
                        phase7_check = gr.Checkbox(label="7: Hậu xử lý", value=True)
                    with gr.Row():
                        phase8_check = gr.Checkbox(label="8: QA", value=True)
                        phase9_check = gr.Checkbox(label="9: Đánh giá")

                    with gr.Group(visible=False) as phase9_group:
                        real_yolo_dir = gr.Textbox(
                            label="Dataset YOLO thực",
                            placeholder="Đường dẫn đến dataset thực (YOLO format)..."
                        )
                        browse_real_btn = gr.Button(get_button_label("browse"), variant="secondary")
                        real_yolo_explorer = gr.FileExplorer(
                            label="Vào thư mục dataset YOLO rồi chọn 1 file bất kỳ (hệ thống lấy thư mục chứa nó). Hoặc gõ tay ở ô trên.",
                            root_dir=str(Path.home()),
                            file_count="single",
                            visible=False,
                        )

                # Checkpoint
                checkpoint_info = get_checkpoint_info()
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("save", 18, "#10b981")} Checkpoint</div>')
                    if checkpoint_info:
                        checkpoint_text = f"**Checkpoint:** {checkpoint_info['images_generated']} ảnh — {checkpoint_info['last_updated']}"
                        resume_checkbox = gr.Checkbox(label="Tiếp tục từ checkpoint", value=False)
                    else:
                        checkpoint_text = "*Không có checkpoint nào được tìm thấy*"
                        resume_checkbox = gr.Checkbox(visible=False)

                    gr.Markdown(checkpoint_text)

                # Action buttons
                with gr.Row():
                    run_btn = gr.Button(
                        get_button_label("run_pipeline"),
                        variant="primary",
                        size="lg",
                        elem_classes=["dm-btn-primary"]
                    )
                    cancel_btn = gr.Button(
                        get_button_label("cancel"),
                        variant="stop",
                        size="lg",
                        visible=False,
                        elem_classes=["dm-btn-danger"]
                    )

            with gr.Tab(get_tab_label("tab_progress")):
                # Phase stepper — dynamic, updated from start_pipeline() while running
                # (was static HTML before, always stuck showing step 1 "Chuẩn bị").
                phase_stepper = gr.HTML(value=create_phase_stepper_html(-1))

                # Progress container
                with gr.Column(elem_classes=["dm-progress-container"]):
                    phase_label = gr.Markdown("**Phase:** Chờ chạy...")
                    with gr.Row():
                        progress_bar = gr.Slider(0, 100, 0, label="Tiến trình", interactive=False, scale=4)
                        progress_pct = gr.Textbox("0%", scale=1, interactive=False)
                    log_display = gr.Textbox(label="Log", lines=25, interactive=False)

            with gr.Tab(get_tab_label("tab_results")):
                # Summary card
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("chart_bar", 18, "#10b981")} Tổng kết</div>')
                    run_summary = gr.Markdown("*Chưa có kết quả*")

                # QA card
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("shield_check", 18, "#10b981")} QA</div>')
                    with gr.Row():
                        qa_ssim = gr.Markdown("**SSIM:** ---")
                        qa_pass = gr.Markdown("**Pass Rate:** ---")

                # Validation card
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("trending_up", 18, "#10b981")} Đánh giá</div>')
                    val_table = gr.Dataframe(
                        headers=["Ratio", "mAP@0.5", "mAP@0.5:0.95"],
                        value=[]
                    )

                # Samples card
                with gr.Column(elem_classes=["dm-card"]):
                    gr.HTML(f'<div class="dm-card-header">{icon("images", 18, "#10b981")} Ảnh mẫu</div>')
                    gallery = gr.Gallery(columns=6)

            with gr.Tab(get_tab_label("tab_training")):
                training_load_info = create_training_tab()

            # The "🖼️ Tạo Ảnh" tab was removed (2026-10-02): batches are composed and started from the
            # Plant HMI (/plant-hmi/: "＋ Tạo mẻ mới", per-run output folder, interlocks, SIGINT stop).
            # ui_generation_panel.py and its helpers are kept on disk but no longer wired.

            with gr.Tab(get_tab_label("tab_labeling")):
                create_auto_label_tab()

            # Event handlers — Phase 9 real dataset folder still uses the
            # in-browser tree (an actual user-chosen path, unlike backgrounds).
            browse_real_btn.click(
                fn=show_browser,
                outputs=[real_yolo_explorer],
            )
            real_yolo_explorer.change(
                fn=picked_to_path,
                inputs=[real_yolo_explorer],
                outputs=[real_yolo_dir],
            )

            preset_dropdown.change(
                fn=lambda name: update_estimate(name, presets),
                inputs=[preset_dropdown],
                outputs=[estimate_text]
            )

            expert_checkbox.change(
                fn=lambda checked: gr.update(visible=checked),
                inputs=[expert_checkbox],
                outputs=[expert_group]
            )

            phase9_check.change(
                fn=lambda checked: gr.update(visible=checked),
                inputs=[phase9_check],
                outputs=[phase9_group]
            )

            # Run pipeline
            run_btn.click(
                fn=self.start_pipeline,
                inputs=[
                    defect_types,
                    preset_dropdown,
                    expert_checkbox,
                    total_images,
                    epochs,
                    batch_size,
                    model_size,
                    phase6_check,
                    phase7_check,
                    phase8_check,
                    phase9_check,
                    real_yolo_dir,
                    resume_checkbox
                ],
                outputs=[
                    run_btn,
                    cancel_btn,
                    phase_stepper,
                    phase_label,
                    progress_bar,
                    progress_pct,
                    log_display,
                    run_summary,
                    qa_ssim,
                    qa_pass,
                    val_table,
                    gallery
                ]
            )

            # Cancel
            cancel_btn.click(
                fn=self.cancel_pipeline,
                outputs=[cancel_btn]
            )

            # Auto-refresh training status on page load
            if training_load_info:
                app.load(
                    fn=training_load_info["load_fn"],
                    outputs=training_load_info["load_outputs"],
                )

        return app, self._theme, self._css

    def start_pipeline(
        self,
        defect_types: List[str],
        preset_name: str,
        expert_mode: bool,
        total_images: int,
        epochs: int,
        batch_size: int,
        model_size: str,
        phase6: bool,
        phase7: bool,
        phase8: bool,
        phase9: bool,
        real_yolo_dir: str,
        resume: bool
    ):
        """Start the pipeline execution.

        Yields progress updates for the UI.
        """
        self.is_running = True
        log_lines = []

        # Validation — at least one defect type must be selected (the pipeline
        # paints these defect shapes onto the fixed clean backgrounds).
        if not defect_types:
            yield (
                gr.update(visible=True),
                gr.update(visible=False),
                create_phase_stepper_html(-1),
                "❌ Lỗi: Vui lòng chọn ít nhất 1 loại khuyết tật",
                0, "0%",
                "Vui lòng chọn ít nhất 1 loại khuyết tật",
                "*Lỗi: chưa chọn khuyết tật*", "---", "---", [], []
            )
            return

        # Get phases to run
        phases = get_phases_to_run(phase6, phase7, phase8, phase9)
        if not phases:
            yield (
                gr.update(visible=True),
                gr.update(visible=False),
                create_phase_stepper_html(-1),
                "❌ Lỗi: Vui lòng chọn ít nhất 1 phase",
                0, "0%",
                "Vui lòng chọn ít nhất 1 phase",
                "*Lỗi: Chưa chọn phase*", "---", "---", [], []
            )
            return

        # Load preset
        try:
            config = self.preset_manager.load_preset(preset_name)
        except Exception as e:
            yield (
                gr.update(visible=True),
                gr.update(visible=False),
                create_phase_stepper_html(-1),
                f"❌ Lỗi load preset: {e}",
                0, "0%",
                f"Lỗi: {e}",
                "*Lỗi*", "---", "---", [], []
            )
            return

        # Apply expert overrides
        if expert_mode:
            overrides = {
                "total_images": total_images,
                "epochs": epochs,
                "batch_size": batch_size,
                "model_size": model_size,
            }
            config = self.preset_manager.apply_overrides(config, overrides)

        # Inject the chosen defect types as an even distribution BEFORE validating.
        # Backgrounds are fixed in config (not user-selectable); the user only picks
        # WHICH defects get painted onto them. This overwrites the base config's
        # distribution (which may not sum to 1.0 once new defect types are added),
        # so it must happen before validate_config checks the sum.
        # BatchJobScheduler reads defect_distribution to build the job list.
        n = len(defect_types)
        even = [round(1.0 / n, 4)] * n
        even[-1] = round(1.0 - sum(even[:-1]), 4)  # last absorbs rounding -> exact 1.0
        config.setdefault("generation", {})["defect_distribution"] = {
            d: even[i] for i, d in enumerate(defect_types)
        }

        # Validate config (now sees the normalized, user-chosen distribution)
        errors = self.preset_manager.validate_config(config)
        if errors:
            yield (
                gr.update(visible=True),
                gr.update(visible=False),
                create_phase_stepper_html(-1),
                f"❌ Lỗi config: {', '.join(errors)}",
                0, "0%",
                f"Lỗi: {', '.join(errors)}",
                "*Lỗi config*", "---", "---", [], []
            )
            return

        # Bake the fully-merged config (base + preset + overrides + defect list)
        # into a temp YAML and point Phase 6 at it. Otherwise the run silently
        # falls back to the default batch-config.yaml and ignores the UI.
        if not DEMO_MODE:
            config["config_path"] = self.preset_manager.write_effective_config(config)

        # Convert to PipelineConfig
        pipeline_config = self.preset_manager.config_to_pipeline_config(config)
        pipeline_config.phases_to_run = phases

        if phase9 and real_yolo_dir:
            pipeline_config.real_yolo_dir = real_yolo_dir

        log_lines.append(f"🚀 Bắt đầu pipeline với preset: {preset_name}")
        log_lines.append(f"📋 Các phase: {phases}")
        log_lines.append(f"🐞 Khuyết tật: {', '.join(defect_types)}")
        log_lines.append(f"🖼️ Số ảnh: {pipeline_config.total_images}")

        # Create orchestrator (mock in demo mode)
        if DEMO_MODE:
            self.current_orchestrator = MockPipelineOrchestrator(
                config=pipeline_config,
                progress_callback=lambda msg: log_lines.append(format_log_line(msg)),
                phases_to_run=phases,
            )
        else:
            # Use the current interpreter so venv packages are available
            import sys
            self.current_orchestrator = PipelineOrchestrator(
                config=pipeline_config,
                progress_callback=lambda msg: log_lines.append(format_log_line(msg)),
                phases_to_run=phases,
                python_executable=sys.executable,
            )

        # Run in background thread
        result_holder = [None]
        error_holder = [None]

        def run_in_thread():
            try:
                result_holder[0] = self.current_orchestrator.run_all()
            except Exception as e:
                error_holder[0] = e

        thread = threading.Thread(target=run_in_thread)
        thread.start()

        # Yield progress updates while running
        total_phases = len(phases)
        current_phase_idx = 0

        while thread.is_alive():
            import time
            time.sleep(0.5)

            # Update progress
            phase_pct = 50  # Simplified - would need progress tracker for real %
            overall_pct = ((current_phase_idx) / total_phases) * 100 + phase_pct / total_phases

            log_text = '\n'.join(log_lines[-30:])  # Last 30 lines

            yield (
                gr.update(visible=False),
                gr.update(visible=True),
                create_phase_stepper_html(phases[current_phase_idx]),
                f"⚙️ Phase {phases[current_phase_idx]}/9: {PHASE_DEFINITIONS.get(phases[current_phase_idx], {}).get('name', 'Unknown')}",
                min(overall_pct, 99),
                f"{overall_pct:.0f}%",
                log_text,
                "*⏳ Đang chạy...*",
                "---",
                "---",
                [],
                []
            )

        thread.join()

        # Get results
        if error_holder[0]:
            log_lines.append(f"❌ Lỗi: {error_holder[0]}")
        elif result_holder[0]:
            result = result_holder[0]
            if result.success:
                log_lines.append("✅ Pipeline hoàn thành!")
            else:
                log_lines.append(f"❌ Pipeline thất bại: {result.error_message}")

        # Load results (use local temp dir in demo mode)
        if DEMO_MODE:
            import tempfile
            output_dir = tempfile.mkdtemp(prefix="datamint_demo_")
            write_fake_results(output_dir)
        else:
            output_dir = pipeline_config.output_dir

        qa_results = load_qa_results(output_dir)
        qa_display = format_qa_display(qa_results)

        val_results = load_validation_results(output_dir)
        val_display = format_validation_display(val_results)

        sample_imgs = get_sample_images(output_dir)

        # Get run summary
        if result_holder[0]:
            result = result_holder[0]
            phases_completed = [r.phase_name for r in result.phase_results if r.success]
            summary = format_run_summary(
                result.total_duration_seconds,
                pipeline_config.total_images,
                phases_completed
            )
        else:
            summary = "*Lỗi khi chạy pipeline*"

        log_text = '\n'.join(log_lines)

        # On completion, mark every requested phase as done (index past the last
        # one so create_phase_stepper_html's "< current" check marks them completed).
        final_stepper = create_phase_stepper_html(max(phases) + 1 if result_holder[0] and result_holder[0].success else -1)

        yield (
            gr.update(visible=True),
            gr.update(visible=False),
            final_stepper,
            "✅ Hoàn thành" if result_holder[0] and result_holder[0].success else "❌ Thất bại",
            100,
            "100%",
            log_text,
            summary,
            qa_display["ssim"],
            qa_display["pass_rate"],
            val_display["table"],
            sample_imgs
        )

        self.is_running = False
        self.current_orchestrator = None

    def cancel_pipeline(self):
        """Cancel the running pipeline."""
        if self.current_orchestrator:
            self.current_orchestrator.cancel()
        self.is_running = False
        yield gr.update(visible=False)
        yield "⏹️ Đã hủy"


def create_app(server_port: int = 7860):
    """Create and return the Gradio app with theme and css.

    Args:
        server_port: Port for server

    Returns:
        Tuple of (Gradio Blocks, theme, css)
    """
    app = PipelineLauncherApp(server_port=server_port)
    return app.build_ui()


def main():
    """Main entry point."""
    import sys
    global DEMO_MODE

    if "--demo" in sys.argv:
        DEMO_MODE = True
        os.environ["DEMO_MODE"] = "1"
        # Re-import demo modules if flag was passed via CLI
        global MockPipelineOrchestrator, write_fake_results
        from .demo_pipeline_runner import MockPipelineOrchestrator
        from .demo_results_data import write_fake_results

    launcher = PipelineLauncherApp()
    app, theme, css = launcher.build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        inbrowser=False,
        theme=theme,
        css=css,
        show_error=True,
        prevent_thread_lock=True,  # FastAPI app exists only after launch; mount extra routes, then block
    )
    try:
        from plant_hmi.plant_hmi_routes import attach_plant_hmi
        attach_plant_hmi(app.app)
    except Exception:  # the plant view is optional; the launcher must still run
        logger.exception("Plant HMI not mounted")
    app.block_thread()


if __name__ == "__main__":
    main()
