"""Generation process manager - execute and control batch image generation."""

import re
import subprocess
import sys
import logging
from typing import Generator

import gradio as gr

from pathlib import Path

from .generation_config_utils import (
    BATCH_MAIN_SCRIPT, DEFECT_TYPES,
    write_batch_config, load_prompt_templates, scan_loras,
)

logger = logging.getLogger(__name__)

# Module-level process state
_generation_process = None
_generation_cancel = False


def run_generation(params: dict) -> Generator:
    """Execute batch generation subprocess.

    Yields (log, progress, pct_text, run_btn_update, cancel_btn_update).

    Args:
        params: Dict with generation parameters (total_images, defect_distribution,
                backgrounds_dir, output_base_dir, pilot_mode, sampler_*).
    """
    global _generation_process, _generation_cancel
    _generation_cancel = False

    # Validate: check LoRA files exist for selected defects
    dist = params.get("defect_distribution", {})
    active_defects = [d for d, pct in dist.items() if pct > 0]
    if not active_defects:
        yield "❌ Chưa chọn loại defect nào (tất cả = 0%)", 0, "0%", gr.update(visible=True), gr.update(visible=False)
        return

    templates = load_prompt_templates()
    available_loras = {name for name, _ in scan_loras()}
    missing = []
    for defect in active_defects:
        tpl = templates.get(defect, {})
        lora_name = tpl.get("lora_name", "")
        if lora_name and lora_name not in available_loras:
            missing.append(f"  - {defect}: {lora_name}")
    if missing:
        msg = "❌ Thiếu LoRA cho các defect đã chọn:\n" + "\n".join(missing)
        msg += f"\n\nLoRA hiện có: {', '.join(sorted(available_loras)) or '(không có)'}"
        msg += "\n\n💡 Hãy train LoRA trước (tab Training) hoặc đặt % = 0 cho defect thiếu LoRA."
        yield msg, 0, "0%", gr.update(visible=True), gr.update(visible=False)
        return

    config_path = write_batch_config(params)

    cmd = [
        sys.executable,
        str(BATCH_MAIN_SCRIPT),
        "--config", config_path,
    ]
    if params.get("pilot_mode"):
        cmd.append("--pilot")

    log_lines = [
        f"🚀 Bắt đầu tạo ảnh (Phase 6)",
        f"Tổng ảnh: {params.get('total_images', '?')}",
        f"Pilot mode: {'Có' if params.get('pilot_mode') else 'Không'}",
        f"Config: {config_path}",
        "=" * 50,
    ]
    yield "\n".join(log_lines), 0, "0%", gr.update(visible=False), gr.update(visible=True)

    try:
        _generation_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, universal_newlines=True,
            cwd=str(BATCH_MAIN_SCRIPT.parent),
        )

        for line in iter(_generation_process.stdout.readline, ""):
            if _generation_cancel:
                _generation_process.terminate()
                log_lines.append("\n⏹️ Đã hủy tạo ảnh")
                yield "\n".join(log_lines[-30:]), 0, "Đã hủy", gr.update(visible=True), gr.update(visible=False)
                return

            line = line.rstrip()
            if not line:
                continue

            # Parse progress: [completed/total] (percentage%)
            progress_match = re.search(r"\[(\d+)/(\d+)\]\s*\((\d+\.?\d*)%\)", line)
            if progress_match:
                completed = int(progress_match.group(1))
                total = int(progress_match.group(2))
                pct = float(progress_match.group(3))

                eta_match = re.search(r"ETA:\s*([\d.]+)h", line)
                eta_str = f" | ETA: {eta_match.group(1)}h" if eta_match else ""

                progress_line = f"[{completed}/{total}] ({pct:.1f}%){eta_str}"
                if log_lines and log_lines[-1].startswith("[") and "/" in log_lines[-1][:20]:
                    log_lines[-1] = progress_line
                else:
                    log_lines.append(progress_line)
                yield "\n".join(log_lines[-30:]), pct, f"{pct:.0f}%", gr.update(visible=False), gr.update(visible=True)
            elif any(kw in line for kw in ["✓", "✗", "Error", "Results:", "Throughput:", "complete", "PILOT"]):
                log_lines.append(line)
                yield "\n".join(log_lines[-30:]), 0, "", gr.update(visible=False), gr.update(visible=True)

        _generation_process.wait()
        if _generation_process.returncode == 0:
            log_lines.append("\n✅ Tạo ảnh hoàn thành!")
            yield "\n".join(log_lines[-30:]), 100, "100%", gr.update(visible=True), gr.update(visible=False)
        else:
            log_lines.append(f"\n❌ Tạo ảnh thất bại (exit code {_generation_process.returncode})")
            yield "\n".join(log_lines[-30:]), 0, "Lỗi", gr.update(visible=True), gr.update(visible=False)

    except Exception as e:
        log_lines.append(f"\n❌ Lỗi: {e}")
        yield "\n".join(log_lines[-30:]), 0, "Lỗi", gr.update(visible=True), gr.update(visible=False)
    finally:
        _generation_process = None


def cancel_generation():
    """Cancel the running generation process."""
    global _generation_cancel, _generation_process
    _generation_cancel = True
    if _generation_process and _generation_process.poll() is None:
        _generation_process.terminate()
