"""UI Progress Panel - Progress tracking with phase stepper and custom progress bar.

Replaces simple slider with professional phase stepper + animated progress bar.
"""

import gradio as gr
from typing import Any, Dict, Optional

from .ui_icons import icon
from .pipeline_orchestrator import PHASE_DEFINITIONS

# Short labels for the stepper (same 9 phases as PHASE_DEFINITIONS, phase_id 1-9)
PHASE_SHORT_LABELS = {
    1: "Thiết lập", 2: "Tiền xử lý", 3: "LoRA", 4: "Workflow", 5: "Mask",
    6: "Tạo ảnh", 7: "Hậu xử lý", 8: "QA", 9: "Đánh giá",
}


def create_phase_stepper_html(current_phase_id: int = 0) -> str:
    """Create HTML phase stepper for the 9 pipeline phases (ids 1-9, matching
    PHASE_DEFINITIONS in pipeline_orchestrator.py — NOT an arbitrary 1-9 index).

    Args:
        current_phase_id: The phase_id (1-9) currently running; 0/-1 = not started.

    Returns:
        HTML string for phase stepper
    """
    html = '<div class="dm-phase-stepper">'
    for phase_id in sorted(PHASE_DEFINITIONS.keys()):
        status = ""
        if phase_id < current_phase_id:
            status = "completed"
        elif phase_id == current_phase_id:
            status = "active"

        label = PHASE_SHORT_LABELS.get(phase_id, PHASE_DEFINITIONS[phase_id]["name"])
        html += f'''
        <div class="dm-phase-step {status}">
            <div class="dm-phase-step-number">{phase_id}</div>
            <div class="dm-phase-step-label">{label}</div>
        </div>
        '''
    html += '</div>'
    return html


def create_progress_html(phase_name: str, overall_pct: float, phase_pct: float,
                         elapsed: str = "0:00", estimate: str = "--:--") -> str:
    """Create custom progress bar HTML.

    Args:
        phase_name: Current phase name
        overall_pct: Overall progress percentage (0-100)
        phase_pct: Current phase progress percentage (0-100)
        elapsed: Elapsed time string
        estimate: Estimated remaining time string

    Returns:
        HTML string for progress display
    """
    return f'''
    <div class="dm-progress-container">
        <div class="dm-progress-header">
            <div class="dm-progress-phase">{icon("activity", 14, "#10b981")} <span style="margin-left:6px;">{phase_name}</span></div>
            <div class="dm-progress-pct">{overall_pct:.0f}%</div>
        </div>
        <div class="dm-progress-bar-track">
            <div class="dm-progress-bar-fill" style="width: {overall_pct}%"></div>
        </div>
        <div class="dm-progress-stats">
            <span>Phase: {phase_pct:.0f}%</span>
            <span class="dm-progress-estimate">⏱ {elapsed} / ~{estimate} còn lại</span>
        </div>
    </div>
    '''


def create_progress_panel() -> Dict[str, Any]:
    """Create progress tracking panel components.

    Returns:
        Dict of Gradio components
    """
    components = {}

    # Phase stepper (HTML)
    phase_stepper = gr.HTML(
        value=create_phase_stepper_html(-1),
        label="Pipeline Progress"
    )

    # Progress container (HTML)
    progress_html = gr.HTML(
        value=create_progress_html("Chờ chạy...", 0, 0),
        label="Progress"
    )

    # GPU info
    gpu_info = gr.HTML(
        value=f'''
        <div class="dm-status-bar">
            <div class="dm-status-item">
                {icon("gpu", 14, "#94a3b8")}
                <span><strong>GPU:</strong> Chưa kiểm tra</span>
            </div>
        </div>
        ''',
        visible=True
    )

    # Log display
    log_display = gr.Textbox(
        label="Log",
        lines=20,
        max_lines=30,
        interactive=False,
        show_copy_button=True,
    )

    components = {
        "phase_stepper": phase_stepper,
        "progress_html": progress_html,
        "gpu_info": gpu_info,
        "log_display": log_display,
    }

    return components


def update_progress_state(
    current_phase: int,
    total_phases: int,
    phase_name: str,
    phase_progress: float,
    elapsed_seconds: int = 0,
    estimated_seconds: int = 0
) -> Dict[str, Any]:
    """Update progress display state.

    Args:
        current_phase: Current phase number (1-9)
        total_phases: Total phases to run
        phase_name: Name of current phase
        phase_progress: Progress within current phase (0-100)
        elapsed_seconds: Elapsed time in seconds
        estimated_seconds: Estimated remaining time in seconds

    Returns:
        Dict of updates for UI components
    """
    # Calculate overall progress
    completed_phases = current_phase - 1
    overall_progress = (completed_phases / total_phases) * 100 + (phase_progress / total_phases)
    overall_progress = min(100, max(0, overall_progress))

    # Format times
    def fmt_time(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        mins = seconds // 60
        secs = seconds % 60
        if mins < 60:
            return f"{mins}:{secs:02d}"
        hours = mins // 60
        mins = mins % 60
        return f"{hours}:{mins:02d}:{secs:02d}"

    elapsed_str = fmt_time(elapsed_seconds)
    estimate_str = fmt_time(estimated_seconds) if estimated_seconds > 0 else "--:--"

    return {
        "phase_stepper": create_phase_stepper_html(current_phase),
        "progress_html": create_progress_html(
            f"Phase {current_phase}/{total_phases}: {phase_name}",
            overall_progress,
            phase_progress,
            elapsed_str,
            estimate_str
        ),
    }


def append_log(log_text: str, new_line: str) -> str:
    """Append a new line to log display.

    Args:
        log_text: Current log text
        new_line: New line to append

    Returns:
        Updated log text
    """
    if not new_line:
        return log_text

    # Keep last 50 lines
    lines = log_text.split('\n') if log_text else []
    lines.append(new_line)
    lines = lines[-50:]

    return '\n'.join(lines)


def format_log_line(line: str) -> str:
    """Format a log line with color coding.

    Args:
        line: Raw log line

    Returns:
        Formatted line with prefixes
    """
    line = line.strip()

    if not line:
        return line

    # Add prefixes based on content
    if any(x in line.upper() for x in ['ERROR', 'FAILED', 'CRITICAL']):
        line = f"[ERR] {line}"
    elif any(x in line.upper() for x in ['WARNING', 'WARN']):
        line = f"[WRN] {line}"
    elif any(x in line.upper() for x in ['SUCCESS', 'COMPLETED', 'DONE']):
        line = f"[OK]  {line}"
    elif any(x in line.upper() for x in ['CHECKPOINT', 'SAVED']):
        line = f"[CHK] {line}"
    elif any(x in line.upper() for x in ['INFO', 'LOG']):
        line = f"[INF] {line}"

    return line
