"""Gradio UI panel for the auto-label feature (YOLO + SAM).

Provides a complete Vietnamese-language tab with:
- Input folder and model weight configuration
- Run button with progress tracking
- Results gallery with bbox/mask overlays
- Review workflow (accept/reject per image, export approved)
"""

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import gradio as gr
import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded pipeline state (avoids heavy imports at tab creation)
_review_state = None
_last_result = None


def _draw_overlay(image_path: str, detections: list) -> Optional[np.ndarray]:
    """Draw bboxes and semi-transparent masks on an image.

    Args:
        image_path: Path to source image
        detections: List of SegmentedDetection objects

    Returns:
        BGR image with overlays, or None on failure
    """
    img = cv2.imread(str(image_path))
    if img is None:
        return None

    overlay = img.copy()
    colors = [
        (0, 0, 255),    # crack - red
        (0, 165, 255),  # porosity - orange
        (0, 255, 0),    # inclusion - green
        (255, 255, 0),  # lack_of_fusion - cyan
        (255, 0, 255),  # undercut - magenta
    ]

    for seg in detections:
        det = seg.detection
        color = colors[det.class_id % len(colors)]

        # Draw mask overlay
        if seg.mask is not None:
            mask_bool = seg.mask > 0
            overlay[mask_bool] = (
                np.array(overlay[mask_bool], dtype=np.float32) * 0.5
                + np.array(color, dtype=np.float32) * 0.5
            ).astype(np.uint8)

        # Draw bbox
        x1, y1, x2, y2 = [int(v) for v in det.bbox_xyxy]
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)

        # Label
        label = f"{det.class_name} {det.confidence:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(overlay, (x1, y1 - th - 6), (x1 + tw, y1), color, -1)
        cv2.putText(
            overlay, label, (x1, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
        )

    # Convert BGR -> RGB for Gradio
    return cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)


def run_auto_label_ui(
    input_dir, yolo_weights, sam_weights, sam_type,
    confidence, batch_size, output_coco, output_yolo,
    progress=gr.Progress(track_tqdm=True),
):
    """Run the auto-label pipeline from UI controls.

    Yields progress updates then final results.
    """
    global _review_state, _last_result

    from importlib import import_module
    _dataclass_mod = import_module(
        ".detection-result-dataclass", package="auto_labeler"
    )
    _pipeline_mod = import_module(
        ".auto-label-pipeline-main", package="auto_labeler"
    )
    _review_mod = import_module(
        ".auto-label-review-state", package="auto_labeler"
    )

    AutoLabelConfig = _dataclass_mod.AutoLabelConfig
    AutoLabelReviewState = _review_mod.AutoLabelReviewState

    # Validate inputs
    if not input_dir or not Path(input_dir).is_dir():
        return (
            "**Loi:** Thu muc anh khong ton tai",
            [], "---", 0, gr.update(), gr.update(),
        )

    if not yolo_weights or not Path(yolo_weights).exists():
        return (
            "**Loi:** File YOLO weights khong ton tai",
            [], "---", 0, gr.update(), gr.update(),
        )

    if not sam_weights or not Path(sam_weights).exists():
        return (
            "**Loi:** File SAM checkpoint khong ton tai",
            [], "---", 0, gr.update(), gr.update(),
        )

    config = AutoLabelConfig(
        input_dir=input_dir,
        yolo_weights=yolo_weights,
        sam_checkpoint=sam_weights,
        sam_model_type=sam_type,
        confidence_threshold=confidence,
        batch_size=int(batch_size),
        output_coco=output_coco,
        output_yolo=output_yolo,
        output_dir=str(Path(input_dir).parent / "auto-labeled-output"),
    )

    # Run pipeline
    progress(0, desc="Dang tai mo hinh...")
    result = _pipeline_mod.run_auto_labeling(
        config,
        progress_callback=lambda stage, c, t: progress(
            c / max(t, 1), desc=f"{stage}: {c}/{t}"
        ),
    )

    if not result.success:
        return (
            f"**Loi:** {result.error}",
            [], "---", 0, gr.update(), gr.update(),
        )

    _last_result = result

    # Build gallery images with overlays
    gallery_images = []
    for img_result in result.image_results:
        if img_result.num_detections > 0:
            overlay = _draw_overlay(
                str(img_result.image_path), img_result.detections,
            )
            if overlay is not None:
                caption = (
                    f"{img_result.image_path.name}: "
                    f"{img_result.num_detections} defect(s)"
                )
                gallery_images.append((overlay, caption))

    # Setup review state
    _review_state = AutoLabelReviewState(result)

    stats = (
        f"**Hoan thanh:** {result.total_detections} defect(s) "
        f"trong {result.total_images} anh\n\n"
        f"**Output:** `{result.output_dir}`"
    )

    review_info = (
        f"Tong: {_review_state.total} | "
        f"Cho duyet: {_review_state.pending_count}"
    )

    return (
        stats,
        gallery_images,
        review_info,
        0,  # review index
        gr.update(interactive=True),   # accept btn
        gr.update(interactive=True),   # reject btn
    )


def review_navigate(direction: str, current_idx: int):
    """Navigate review gallery by direction.

    Args:
        direction: "next" or "prev"
        current_idx: Current image index

    Returns:
        Tuple of (image, status_text, new_index)
    """
    global _review_state, _last_result

    if _review_state is None or _last_result is None:
        return None, "Chua co ket qua", 0

    total = _review_state.total
    if total == 0:
        return None, "Khong co anh", 0

    if direction == "next":
        new_idx = min(current_idx + 1, total - 1)
    else:
        new_idx = max(current_idx - 1, 0)

    img_result = _review_state.get_image_at_index(new_idx)
    if img_result is None:
        return None, "Loi", new_idx

    # Draw overlay
    overlay = _draw_overlay(str(img_result.image_path), img_result.detections)
    status = _review_state.get_status(str(img_result.image_path))

    status_text = (
        f"Anh {new_idx + 1}/{total} | "
        f"Trang thai: {status.value} | "
        f"Defects: {img_result.num_detections}"
    )

    return overlay, status_text, new_idx


def review_accept(current_idx: int):
    """Accept current image."""
    global _review_state
    if _review_state is None:
        return "Chua co ket qua"

    img_result = _review_state.get_image_at_index(current_idx)
    if img_result:
        _review_state.accept(str(img_result.image_path))

    return (
        f"Chap nhan: {_review_state.accepted_count} | "
        f"Tu choi: {_review_state.rejected_count} | "
        f"Cho: {_review_state.pending_count}"
    )


def review_reject(current_idx: int):
    """Reject current image."""
    global _review_state
    if _review_state is None:
        return "Chua co ket qua"

    img_result = _review_state.get_image_at_index(current_idx)
    if img_result:
        _review_state.reject(str(img_result.image_path))

    return (
        f"Chap nhan: {_review_state.accepted_count} | "
        f"Tu choi: {_review_state.rejected_count} | "
        f"Cho: {_review_state.pending_count}"
    )


def review_accept_all():
    """Accept all pending images."""
    global _review_state
    if _review_state is None:
        return "Chua co ket qua"

    _review_state.accept_all()
    return (
        f"Chap nhan: {_review_state.accepted_count} | "
        f"Tu choi: {_review_state.rejected_count} | "
        f"Cho: {_review_state.pending_count}"
    )


def export_approved():
    """Export only accepted images to final annotations."""
    global _review_state, _last_result
    if _review_state is None or _last_result is None:
        return "Chua co ket qua de xuat"

    from importlib import import_module
    _pipeline_mod = import_module(
        ".auto-label-pipeline-main", package="auto_labeler"
    )

    accepted = _review_state.get_accepted_results()
    if not accepted:
        return "Khong co anh nao duoc chap nhan"

    output_dir = _last_result.output_dir / "approved"
    pairs = _pipeline_mod.save_masks(accepted, output_dir)
    _pipeline_mod.build_annotations(pairs, output_dir)

    # Save review state
    _review_state.save_review_state(output_dir / "review-state.json")

    return (
        f"Da xuat {len(accepted)} anh duoc chap nhan "
        f"vao `{output_dir}`"
    )


def create_auto_label_tab():
    """Create the auto-label Gradio tab contents.

    Call this inside a gr.Tab() context in the main app.
    """
    with gr.Group():
        gr.Markdown("### Dau vao")
        input_dir = gr.Textbox(
            label="Thu muc anh",
            placeholder="Duong dan den thu muc chua anh X-ray...",
        )

    with gr.Group():
        gr.Markdown("### Mo hinh")
        with gr.Row():
            yolo_weights = gr.Textbox(
                label="YOLO Weights (.pt)",
                placeholder="Duong dan den file .pt...",
                scale=2,
            )
            sam_weights = gr.Textbox(
                label="SAM Checkpoint (.pth)",
                placeholder="Duong dan den file .pth...",
                scale=2,
            )
        with gr.Row():
            sam_type = gr.Dropdown(
                choices=["vit_b", "vit_l", "vit_h"],
                value="vit_b",
                label="SAM Model Type",
                scale=1,
            )
            confidence = gr.Slider(
                minimum=0.1, maximum=0.95, value=0.5, step=0.05,
                label="Nguong tin cay",
                scale=2,
            )

    with gr.Group():
        gr.Markdown("### Tuy chinh")
        with gr.Row():
            batch_size = gr.Number(value=8, label="Batch Size", minimum=1)
            output_coco = gr.Checkbox(label="Xuat COCO", value=True)
            output_yolo = gr.Checkbox(label="Xuat YOLO", value=True)

    with gr.Row():
        run_btn = gr.Button("Chay Auto-Label", variant="primary", size="lg")

    # Results section
    with gr.Group():
        gr.Markdown("### Ket qua")
        stats_display = gr.Markdown("*Chua chay*")
        gallery = gr.Gallery(label="Anh ket qua", columns=4, height=400)

    # Review section
    with gr.Group():
        gr.Markdown("### Duyet ket qua")
        review_info = gr.Markdown("---")
        review_index = gr.State(value=0)

        review_image = gr.Image(label="Anh dang duyet", height=400)
        review_status = gr.Markdown("---")

        with gr.Row():
            prev_btn = gr.Button("Truoc", size="sm")
            accept_btn = gr.Button(
                "Chap nhan", variant="primary", size="sm", interactive=False,
            )
            reject_btn = gr.Button(
                "Tu choi", variant="stop", size="sm", interactive=False,
            )
            next_btn = gr.Button("Tiep", size="sm")

        with gr.Row():
            accept_all_btn = gr.Button("Chap nhan tat ca", size="sm")
            export_btn = gr.Button(
                "Xuat anh da duyet", variant="primary", size="sm",
            )
        export_status = gr.Markdown("")

    # Wire events
    run_btn.click(
        fn=run_auto_label_ui,
        inputs=[
            input_dir, yolo_weights, sam_weights, sam_type,
            confidence, batch_size, output_coco, output_yolo,
        ],
        outputs=[
            stats_display, gallery, review_info,
            review_index, accept_btn, reject_btn,
        ],
    )

    prev_btn.click(
        fn=lambda idx: review_navigate("prev", idx),
        inputs=[review_index],
        outputs=[review_image, review_status, review_index],
    )

    next_btn.click(
        fn=lambda idx: review_navigate("next", idx),
        inputs=[review_index],
        outputs=[review_image, review_status, review_index],
    )

    accept_btn.click(
        fn=review_accept,
        inputs=[review_index],
        outputs=[review_info],
    )

    reject_btn.click(
        fn=review_reject,
        inputs=[review_index],
        outputs=[review_info],
    )

    accept_all_btn.click(
        fn=review_accept_all,
        outputs=[review_info],
    )

    export_btn.click(
        fn=export_approved,
        outputs=[export_status],
    )
