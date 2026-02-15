# Python GUI Framework Research for ML Training Launcher

**Project**: The Data Mint - One-Click Training Launcher
**Date**: 2026-02-13
**Researcher**: researcher-01

## Executive Summary

Evaluated 6 Python GUI frameworks for building desktop training launcher with file browsing, config UI, subprocess management, and real-time progress display. **Recommendation: Gradio** for fastest development with ML-native features, or **PySide6** for native desktop polish.

---

## Comparison Matrix

| Framework | Dev Speed | File Browser | Real-time Logs | Subprocess | Modern Look | Dependencies | Best For |
|-----------|-----------|--------------|----------------|------------|-------------|--------------|----------|
| **Gradio** | ⭐⭐⭐⭐⭐ | Upload only | ⭐⭐⭐⭐ Custom component | ⭐⭐⭐⭐ Async support | ⭐⭐⭐⭐ Web UI | Medium (FastAPI) | ML demos, rapid prototyping |
| **Streamlit** | ⭐⭐⭐⭐⭐ | Upload only (no folder picker) | ⭐⭐⭐ Polling required | ⭐⭐⭐ Needs API offload | ⭐⭐⭐⭐ Dashboard style | Medium-Heavy (25+ packages) | Dashboards, multi-page apps |
| **NiceGUI** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ Native mode | ⭐⭐⭐ Manual impl | ⭐⭐⭐ Standard | ⭐⭐⭐⭐⭐ Modern web | Medium (FastAPI, uvicorn) | Full web apps, multi-page |
| **PySide6** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ QFileDialog | ⭐⭐⭐⭐⭐ QProcess | ⭐⭐⭐⭐⭐ QProcess signals | ⭐⭐⭐⭐⭐ Native | Heavy (Qt6) | Professional desktop apps |
| **Tkinter** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ Built-in | ⭐⭐ Manual threading | ⭐⭐⭐ subprocess module | ⭐⭐ Basic | None (stdlib) | Simple tools, no deps |
| **Textual** | ⭐⭐⭐ | Limited | ⭐⭐⭐⭐ TUI native | ⭐⭐⭐⭐ Subprocess support | ⭐⭐⭐ Terminal style | Light | Terminal apps, SSH access |

---

## Detailed Analysis

### 1. Gradio (RECOMMENDED for ML Use Case)

**Strengths:**
- ML-native widgets (`gr.Progress()`, `gr.Audio`, `gr.Image`)
- Real-time log streaming via custom component `gradio_logsview` - runs Python code in subprocess, captures logs by level/name
- Progress tracking: Pass `gr.Progress()` instance to function, update with float 0-1 or use `.tqdm()` method
- Generator functions for streaming outputs (yield instead of return)
- Asyncio support for subprocess management with pipe-based stdout/stderr
- One-page app focus - perfect for single-task launcher
- Built-in sharing/embedding capabilities
- Pre-built ML widgets save development time

**Limitations:**
- File uploader doesn't support folder selection (upload only, no native folder picker)
- Fixed UI design - limited customization for unique branding
- Not designed for multi-page apps

**Dependencies:**
- FastAPI backend, pydantic 2.x (with Rust pydantic-core via PyO3)
- Medium installation weight

**Use Case Fit:**
- Excellent for ML training launcher
- Native progress tracking and log streaming
- Rapid prototyping (hours to working prototype)
- Trade-off: No folder browser (users must upload files or enter paths manually)

---

### 2. Streamlit

**Strengths:**
- Multi-page app support built-in
- Strong data caching (`st.session_state` for persistence)
- Excellent for dashboards within corporate firewall
- Rich customization and complex UI/UX capabilities
- Large community and ecosystem
- `st.file_uploader` for individual files

**Limitations:**
- No native folder picker (requires Tkinter workaround or manual path input)
- Long-running ML tasks require API offload pattern (Streamlit polls/WebSocket for progress)
- Heavy dependencies (25+ packages including pandas, numpy)
- More complex for simple subprocess streaming compared to Gradio

**Use Case Fit:**
- Overkill for single-purpose launcher
- Better suited for multi-page training dashboard with analytics
- Folder selection requires custom Tkinter integration

---

### 3. NiceGUI

**Strengths:**
- Native file picker in native mode: `app.native.main_window.create_file_dialog()` with `allow_multiple=True`
- Folder selection: `create_file_dialog(dialog_type=webview.FOLDER_DIALOG)`
- Extensive UI element library (more than Streamlit/Gradio)
- Multi-page routing built-in
- Modern, highly customizable web interface
- Web + native mode support

**Limitations:**
- Smaller community than Streamlit/Gradio (fewer resources)
- More complex than Streamlit/Gradio for simple tasks
- Native mode file picker had issues in some versions (2.1.0, 2.5.0)
- Real-time log streaming requires manual implementation

**Dependencies:**
- FastAPI, uvicorn, python-socketio, webview libraries
- Medium installation weight

**Use Case Fit:**
- Strong contender if native folder picker is critical
- Best for full web-app with multi-page needs
- Requires more dev effort than Gradio for ML-specific features

---

### 4. PySide6 / PyQt6 (RECOMMENDED for Native Desktop)

**Strengths:**
- Professional native desktop application
- `QFileDialog` for robust file/folder selection
- `QProcess` with signals (`.readyReadStandardOutput`, `.readyReadStandardError`) for real-time subprocess output
- `QProgressBar` for progress indication
- Handles gigabyte-sized log files smoothly without UI freeze
- Qt threading system works reliably
- 99.9% identical APIs (PySide6 = LGPL, PyQt6 = GPL/commercial)
- Existing YOLOv8-PySide6-GUI reference implementations available

**Limitations:**
- Steeper learning curve than web frameworks
- More boilerplate code
- Heavier dependencies (Qt6 framework)
- Longer development time (days vs hours)

**Use Case Fit:**
- Best for polished, professional desktop tool
- Superior subprocess and log streaming performance
- Ideal for Windows native app with proper threading
- Proven with YOLOv8 training GUIs

---

### 5. Tkinter

**Strengths:**
- Zero external dependencies (Python stdlib)
- Built-in file/folder dialogs
- Simple for basic UIs
- `ttk.Progressbar` for progress display
- Lightweight

**Limitations:**
- UI freezes with large log files or intensive I/O
- Manual threading required for real-time updates
- Dated appearance
- No modern ML-specific widgets

**Use Case Fit:**
- Acceptable for minimal launcher if zero dependencies required
- Significant effort for real-time log streaming
- Less professional look than alternatives

---

### 6. Textual (TUI)

**Strengths:**
- Terminal-native UI (SSH-friendly)
- Subprocess support via websocket communication
- Web deployment via `textual-serve`
- Lightweight dependencies
- Modern TUI aesthetics

**Limitations:**
- No native file browser (limited compared to GUI)
- Terminal-only interaction (no mouse-driven folder picker)
- Less intuitive for non-technical users

**Use Case Fit:**
- Not suitable for general-use desktop launcher
- Better for devops/server-side tools accessed via SSH
- Poor fit for "one-click" user experience

---

## Installation & Dependencies

| Framework | Install Command | Core Dependencies | Approx Size |
|-----------|----------------|-------------------|-------------|
| Gradio | `pip install gradio` | FastAPI, pydantic 2.x, Rust core | ~50-100 MB |
| Streamlit | `pip install streamlit` | pandas, numpy, 25+ packages | ~200-300 MB |
| NiceGUI | `pip install nicegui` | FastAPI, uvicorn, socketio, webview | ~50-100 MB |
| PySide6 | `pip install PySide6` | Qt6 framework | ~200-400 MB |
| Tkinter | Built-in | None | 0 MB |
| Textual | `pip install textual` | textual core | ~10-20 MB |

*Note: Sizes estimated based on typical installations; actual size varies by platform.*

---

## Recommendations

### Primary: **Gradio**

**Rationale:**
- Fastest path to working launcher (2-4 hours)
- ML-native features (progress bars, log streaming, model widgets)
- Real-time subprocess log capture via `gradio_logsview` custom component
- Async subprocess support with asyncio pipes
- Generator-based streaming outputs
- Web UI runs locally (localhost) - modern, accessible

**Trade-offs:**
- No folder picker (workaround: text input for folder path, or file upload for datasets)
- Less customizable UI than NiceGUI/PySide6

**Workaround for Folder Selection:**
- Use `gr.Textbox()` for manual path entry
- Add file browser button that launches Tkinter dialog via `tkinter.filedialog.askdirectory()`
- Or: Upload dataset as zip file via `gr.File()`

---

### Alternative: **PySide6**

**Rationale:**
- Best for native desktop app with professional polish
- Superior file/folder browsing (`QFileDialog`)
- Excellent subprocess management (`QProcess` signals)
- Proven with YOLOv8 GUIs (YOLOv8-PySide6-GUI reference)
- No browser required

**Trade-offs:**
- 3-5x longer development time
- Heavier dependencies
- More complex code

---

### Budget/Minimal: **Tkinter + Gradio Hybrid**

Use Tkinter only for folder picker dialog, Gradio for main UI:
```python
import gradio as gr
from tkinter import Tk, filedialog

def browse_folder():
    root = Tk()
    root.withdraw()
    folder = filedialog.askdirectory()
    root.destroy()
    return folder

with gr.Blocks() as app:
    folder_path = gr.Textbox(label="Dataset Folder")
    browse_btn = gr.Button("Browse").click(browse_folder, outputs=folder_path)
```

---

## Implementation Checklist

For Gradio-based launcher:

- [ ] Install Gradio + `gradio_logsview` custom component
- [ ] Build UI with `gr.Blocks()`:
  - [ ] Textbox for dataset path (+ Tkinter browse button)
  - [ ] Dropdowns for model type, epochs, batch size
  - [ ] "Run Training" button
  - [ ] `LogsView.run_python()` for real-time subprocess logs
  - [ ] `gr.Progress()` for progress bar
- [ ] Subprocess management:
  - [ ] Use asyncio with `subprocess.create_subprocess_exec()`
  - [ ] Stream stdout/stderr to `LogsView` component
  - [ ] Parse training logs for epoch/batch progress
- [ ] Results display:
  - [ ] Show metrics (mAP, loss) in `gr.DataFrame()`
  - [ ] Display generated images with `gr.Gallery()`
- [ ] Test on Windows with WSL, RTX 3090 environment
- [ ] Package with `requirements.txt` (gradio, ultralytics, torch)

---

## Sources

- [Streamlit, Gradio, NiceGUI, and Mesop: Building Data Apps Without Web Devs](https://medium.com/@manikolbe/streamlit-gradio-nicegui-and-mesop-building-data-apps-without-web-devs-4474106778f5)
- [Gradio — Streamlit — NiceGUI: Python UI Framework Part 2](https://medium.com/towardsdev/gradio-streamlit-nicegui-python-ui-framework-part-2-2df3ea6ef097)
- [Gradio vs Streamlit in 2025: Comparing AI-App Frameworks](https://www.squadbase.dev/en/blog/streamlit-vs-gradio-in-2025-a-framework-comparison-for-ai-apps)
- [PyQt vs. Tkinter: Which Should You Choose?](https://www.pythonguis.com/faq/pyqt-vs-tkinter/)
- [Which Python GUI library should you use in 2026?](https://www.pythonguis.com/faq/which-python-gui-library/)
- [Run external programs in PyQt6 with QProcess](https://www.pythonguis.com/tutorials/pyqt6-qprocess-external-programs/)
- [GitHub: YOLOv8-PySide6-GUI](https://github.com/Jai-wei/YOLOv8-PySide6-GUI)
- [Gradio Progress Bars Guide](https://www.gradio.app/guides/progress-bars)
- [Real time logs from subprocesses - Gradio Issue #10108](https://github.com/gradio-app/gradio/issues/10108)
- [Gradio LogsView Custom Component](https://huggingface.co/spaces/Wauplin/gradio_logsview/blob/main/README.md)
- [Streamlit File Uploader Docs](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader)
- [File browser to select a folder or a file - Streamlit Discussion](https://discuss.streamlit.io/t/file-browser-to-select-a-folder-or-a-file/49325)
- [How to Create a Folder Selector in Streamlit](https://medium.com/@kjavaman12/how-to-create-a-folder-selector-in-streamlit-e44816c06afd)
- [NiceGUI Local File Picker Example](https://github.com/zauberzeug/nicegui/blob/main/examples/local_file_picker/local_file_picker.py)
- [NiceGUI File picker or folder selector discussion](https://github.com/zauberzeug/nicegui/discussions/283)
- [Textual Documentation](https://textual.textualize.io/)
- [Textual GitHub Repository](https://github.com/Textualize/textual)

---

## Unresolved Questions

1. **Dataset size limits**: If users select folders with 10,000+ images, will Gradio file upload handle it? (Recommend path-based approach)
2. **GPU monitoring**: Should UI show real-time GPU utilization (VRAM, temp)? (Requires `nvidia-smi` polling)
3. **Multi-GPU training**: Does launcher need to support distributed training across multiple GPUs? (Affects config UI)
4. **Results persistence**: Should training history be stored in local DB (SQLite) or just display last run?
5. **Docker deployment**: Will launcher run inside Docker container or directly on Windows host?
