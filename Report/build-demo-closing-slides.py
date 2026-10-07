#!/usr/bin/env python3
"""Dung hai tam hinh ket cho video demo: luoi anh tong hop va the ket.

Anh lay tu Report/ma-nguon-nop/mau-ket-qua, deu la anh do chinh he thong sinh ra.

    python3 Report/build-demo-closing-slides.py [thu-muc-dau-ra]
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
SAMPLES = BASE / "ma-nguon-nop" / "mau-ket-qua"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-1000/demo-closing")

W, H = 1600, 900
BG = (13, 20, 33)
CARD = (22, 32, 50)
TEXT = (226, 232, 240)
DIM = (148, 163, 184)
MINT = (16, 185, 129)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(f"{FONT_DIR}/{name}", size)
    except OSError:
        return ImageFont.load_default()


def centered(draw, text, y, f, fill):
    w = draw.textbbox((0, 0), text, font=f)[2]
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)


def build_grid():
    """Luoi anh tong hop va mat na chu thich cua nam lop khuyet tat."""
    pairs = []
    for img in sorted(SAMPLES.glob("*.png")):
        if img.name.endswith("_mask.png"):
            continue
        mask = img.with_name(img.stem + "_mask.png")
        if mask.exists():
            pairs.append((img, mask, img.stem.rsplit("_", 1)[0]))
    pairs = pairs[:5]

    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    centered(draw, "Ảnh tổng hợp và mặt nạ chú thích do hệ thống sinh ra", 48, font(34, True), TEXT)

    cell = 240
    gap = 28
    total = len(pairs) * cell + (len(pairs) - 1) * gap
    x0 = (W - total) // 2

    for i, (img_path, mask_path, label) in enumerate(pairs):
        x = x0 + i * (cell + gap)
        draw.rounded_rectangle([x - 10, 130, x + cell + 10, 716], 14, fill=CARD)
        for row, path in enumerate((img_path, mask_path)):
            im = Image.open(path).convert("RGB").resize((cell, cell), Image.LANCZOS)
            canvas.paste(im, (x, 160 + row * (cell + 24)))
        name = label.replace("_", " ")
        w = draw.textbbox((0, 0), name, font=font(17))[2]
        draw.text((x + (cell - w) / 2, 678), name, font=font(17), fill=DIM)

    centered(draw, "Hàng trên: ảnh tổng hợp     Hàng dưới: mặt nạ dùng để xuất COCO và YOLO",
             752, font(22), DIM)
    centered(draw, "Mặt nạ vừa là điều kiện đầu vào cho mô hình khuếch tán, vừa là nhãn",
             794, font(22), MINT)
    return canvas


def build_card():
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    centered(draw, "The Data Mint", 250, font(72, True), TEXT)
    centered(draw, "Sinh ảnh X-quang mối hàn tổng hợp có chú thích tự động", 350, font(30), DIM)
    centered(draw, "Stable Diffusion 1.5  ·  LoRA  ·  ComfyUI", 405, font(26), MINT)

    stats = [
        ("1.097 ảnh/giờ", "thông lượng"),
        ("0,976", "SSIM bảo toàn nền"),
        ("68,5% → 71,2%", "mAP@0,5 khi trộn 20% ảnh tổng hợp"),
    ]
    box_w, gap = 400, 30
    total = len(stats) * box_w + (len(stats) - 1) * gap
    x0 = (W - total) // 2
    for i, (value, label) in enumerate(stats):
        x = x0 + i * (box_w + gap)
        draw.rounded_rectangle([x, 520, x + box_w, 650], 16, fill=CARD)
        vw = draw.textbbox((0, 0), value, font=font(34, True))[2]
        draw.text((x + (box_w - vw) / 2, 548), value, font=font(34, True), fill=MINT)
        lw = draw.textbbox((0, 0), label, font=font(18))[2]
        draw.text((x + (box_w - lw) / 2, 600), label, font=font(18), fill=DIM)

    centered(draw, "Đồ án môn học Máy học nâng cao  ·  Trường Đại học Công nghệ Thông tin, ĐHQG-HCM",
             730, font(22), DIM)
    centered(draw, "Trương Ngọc Sơn  ·  Trần Tín Nghĩa  ·  Hồ Thị Mỹ Phương", 772, font(22), DIM)
    return canvas


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build_grid().save(OUT / "closing-1-grid.png")
    build_card().save(OUT / "closing-2-card.png")
    print("Da tao:", OUT / "closing-1-grid.png")
    print("Da tao:", OUT / "closing-2-card.png")


if __name__ == "__main__":
    main()
