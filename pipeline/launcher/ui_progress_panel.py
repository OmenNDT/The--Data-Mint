"""UI Progress Panel - Progress bar + log display."""

import gradio as gr
from typing import Any, Dict, Optional


def create_progress_panel() -> Dict[str, Any]:
    """Create progress tracking panel components.

    Returns:
        Dict of Gradio components
    """
    components = {}

    with gr.Group():
        # Phase indicator
        phase_label = gr.Markdown(
            value="**Phase hiện tại:** Chờ chạy...",
            elem_classes=["phase-label"]
        )

        # Progress bar
        with gr.Row():
            progress_bar = gr.Slider(
                minimum=0,
                maximum=100,
                value=0,
                step=1,
                label="Tiến trình",
                interactive=False,
                scale=4
            )
            progress_pct = gr.Textbox(
                value="0%",
                interactive=False,
                scale=1,
                show_label=False,
                container=False
            )

        # GPU info
        gpu_info = gr.Markdown(
            value="*GPU: Chưa kiểm tra*",
            visible=True
        )

        # Log display
        log_display = gr.Textbox(
            label="📝 Log",
            lines=20,
            max_lines=30,
            interactive=False,
            show_copy_button=True
        )

    components = {
        "phase_label": phase_label,
        "progress_bar": progress_bar,
        "progress_pct": progress_pct,
        "gpu_info": gpu_info,
        "log_display": log_display,
    }

    return components


def update_progress_state(
    current_phase: int,
    total_phases: int,
    phase_name: str,
    phase_progress: float
) -> Dict[str, Any]:
    """Update progress display state.

    Args:
        current_phase: Current phase number (1-9)
        total_phases: Total phases to run
        phase_name: Name of current phase
        phase_progress: Progress within current phase (0-100)

    Returns:
        Dict of updates for UI components
    """
    # Calculate overall progress
    completed_phases = current_phase - 1
    overall_progress = (completed_phases / total_phases) * 100 + (phase_progress / total_phases)
    overall_progress = min(100, max(0, overall_progress))

    phase_text = f"**Phase {current_phase}/{total_phases}:** {phase_name}"
    pct_text = f"{overall_progress:.0f}%"

    return {
        "phase_label": phase_text,
        "progress_bar": overall_progress,
        "progress_pct": pct_text,
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
        Formatted line with ANSI color codes (for display)
    """
    line = line.strip()

    if not line:
        return line

    # Add prefixes based on content
    if any(x in line.upper() for x in ['ERROR', 'FAILED', 'CRITICAL']):
        line = f"❌ {line}"
    elif any(x in line.upper() for x in ['WARNING', 'WARN']):
        line = f"⚠️ {line}"
    elif any(x in line.upper() for x in ['SUCCESS', 'COMPLETED', 'DONE']):
        line = f"✅ {line}"
    elif any(x in line.upper() for x in ['CHECKPOINT', 'SAVED']):
        line = f"💾 {line}"

    return line
