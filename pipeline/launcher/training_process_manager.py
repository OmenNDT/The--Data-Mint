"""Training process manager - detect, execute, and control LoRA training."""

import os
import re
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Generator

import gradio as gr

from .training_config_utils import (
    KOHYA_DIR, KOHYA_ACCELERATE, CONFIGS_DIR, MODELS_DIR,
    update_config_file,
)

logger = logging.getLogger(__name__)

# Module-level process state
_training_process = None
_training_cancel = False


@dataclass
class TrainingStatus:
    """Status of a detected training process."""
    running: bool = False
    pid: Optional[int] = None
    defect_type: str = ""
    progress_pct: int = 0
    log_tail: str = ""


def detect_running_training() -> TrainingStatus:
    """Detect if train_network.py is currently running (CLI or UI)."""
    global _training_process
    # UI-launched process
    if _training_process and _training_process.poll() is None:
        return TrainingStatus(running=True, pid=_training_process.pid, defect_type="(từ UI)")

    # CLI-launched process via pgrep
    try:
        result = subprocess.run(
            ["pgrep", "-af", "accelerate.*train_network"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            if not line or "train_network" not in line:
                continue
            pid = int(line.split()[0])
            defect = ""
            m = re.search(r"(\w+)-lora-training-config", line)
            if m:
                defect = m.group(1)
            log_tail = _read_training_log(defect)
            pct = _parse_progress(log_tail)
            return TrainingStatus(
                running=True, pid=pid, defect_type=defect,
                progress_pct=pct, log_tail=log_tail,
            )
    except Exception as e:
        logger.debug(f"detect_running_training error: {e}")
    return TrainingStatus(running=False)


def _read_training_log(defect_type: str) -> str:
    """Read last 30 lines from training log file."""
    candidates = [
        Path(f"/tmp/{defect_type}-lora-training-v2.log"),
        Path(f"/tmp/{defect_type}-lora-training.log"),
        Path("/tmp/lora-training.log"),
    ]
    for p in candidates:
        if p.exists():
            try:
                lines = p.read_text().strip().split("\n")
                return "\n".join(lines[-30:])
            except Exception:
                pass
    return ""


def _parse_progress(log_text: str) -> int:
    """Parse progress percentage from log text."""
    if not log_text:
        return 0
    for line in reversed(log_text.split("\n")):
        m = re.search(r"(\d+)/(\d+)\s*\[", line)
        if m:
            current, total = int(m.group(1)), int(m.group(2))
            return int(current / total * 100) if total > 0 else 0
    return 0


def run_training(defect_type, params) -> Generator:
    """Execute training. Yields (log, progress, pct_text, train_btn, cancel_btn)."""
    global _training_process, _training_cancel
    _training_cancel = False

    config_path = CONFIGS_DIR / f"{defect_type}-lora-training-config.toml"
    if not config_path.exists():
        yield "❌ Không có config", 0, "0%", gr.update(visible=True), gr.update(visible=False)
        return

    dataset_path = params.get("dataset_path", "")
    if not dataset_path or not Path(dataset_path).exists():
        yield "❌ Dataset path không tồn tại", 0, "0%", gr.update(visible=True), gr.update(visible=False)
        return

    # Write all params to config
    update_config_file(str(config_path), params)

    cmd = [
        str(KOHYA_ACCELERATE), "launch", "--num_cpu_threads_per_process=4",
        str(KOHYA_DIR / "train_network.py"),
        "--config_file", str(config_path),
    ]

    log_lines = [
        f"🚀 Bắt đầu training {defect_type} LoRA",
        f"Config: {config_path.name}",
        f"Epochs: {params.get('epochs', 20)} | Batch: {params.get('batch_size', 4)} | LR: {params.get('learning_rate', '5e-5')}",
        f"Network: dim={params.get('network_dim', 32)}, alpha={params.get('network_alpha', 16)}",
        f"Optimizer: {params.get('optimizer_type', 'AdamW8bit')} | Scheduler: {params.get('lr_scheduler', 'cosine_with_restarts')}",
        "=" * 50,
    ]
    yield "\n".join(log_lines), 0, "0%", gr.update(visible=False), gr.update(visible=True)

    try:
        _training_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, universal_newlines=True, cwd=str(KOHYA_DIR),
        )
        total_steps = current_step = 0

        for line in iter(_training_process.stdout.readline, ""):
            if _training_cancel:
                _training_process.terminate()
                log_lines.append("\n⏹️ Training đã hủy")
                yield "\n".join(log_lines[-30:]), 0, "Đã hủy", gr.update(visible=True), gr.update(visible=False)
                return

            line = line.rstrip()
            if not line:
                continue

            step_match = re.search(r"(\d+)/(\d+)\s+\[", line)
            if step_match:
                current_step = int(step_match.group(1))
                total_steps = int(step_match.group(2))

            loss_match = re.search(r"avr_loss=([\d.]+)", line)
            loss_str = f" | loss={loss_match.group(1)}" if loss_match else ""

            if "steps:" in line and step_match:
                pct = int(current_step / total_steps * 100) if total_steps > 0 else 0
                progress_line = f"Step {current_step}/{total_steps} ({pct}%){loss_str}"
                if log_lines and log_lines[-1].startswith("Step "):
                    log_lines[-1] = progress_line
                else:
                    log_lines.append(progress_line)
                yield "\n".join(log_lines[-30:]), pct, f"{pct}%", gr.update(visible=False), gr.update(visible=True)
            elif any(kw in line.lower() for kw in ["epoch", "saving", "model saved"]):
                log_lines.append(line)
                pct = int(current_step / total_steps * 100) if total_steps > 0 else 0
                yield "\n".join(log_lines[-30:]), pct, f"{pct}%", gr.update(visible=False), gr.update(visible=True)

        _training_process.wait()
        if _training_process.returncode == 0:
            _handle_training_success(defect_type, log_lines)
            yield "\n".join(log_lines[-30:]), 100, "100%", gr.update(visible=True), gr.update(visible=False)
        else:
            log_lines.append(f"\n❌ Training thất bại (exit code {_training_process.returncode})")
            yield "\n".join(log_lines[-30:]), 0, "Lỗi", gr.update(visible=True), gr.update(visible=False)
    except Exception as e:
        log_lines.append(f"\n❌ Lỗi: {e}")
        yield "\n".join(log_lines[-30:]), 0, "Lỗi", gr.update(visible=True), gr.update(visible=False)
    finally:
        _training_process = None


def _handle_training_success(defect_type, log_lines):
    """Copy trained model to models/loras and symlink to ComfyUI."""
    import shutil
    output_dir = KOHYA_DIR / "output" / defect_type
    lora_files = list(output_dir.glob("*.safetensors"))
    if lora_files:
        dest = MODELS_DIR / "loras" / lora_files[-1].name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lora_files[-1], dest)
        comfyui_loras = MODELS_DIR.parent / "comfyui/models/loras"
        if comfyui_loras.exists():
            link = comfyui_loras / lora_files[-1].name
            link.unlink(missing_ok=True)
            os.symlink(str(dest), str(link))
        log_lines.append(f"\n✅ Training hoàn thành!")
        log_lines.append(f"Model: {dest}")
    else:
        log_lines.append("\n✅ Training xong nhưng không tìm thấy model output")


def cancel_training():
    """Cancel the running training process."""
    global _training_cancel, _training_process
    _training_cancel = True
    if _training_process and _training_process.poll() is None:
        _training_process.terminate()
