#!/usr/bin/env python3
"""
Kiểm chứng: khuyết tật nhỏ (nhất là Gas_Pore) còn nhìn thấy được không
khi phim full-size ~4990x1300 bị co về độ phân giải train.

Nguồn dữ liệu:
  - Nhãn full-film thật: Quantum_RT/data/processed/yolo-stage1-v2 (33 phim W0003 thật)
  - Kích thước thật (mm): The Data Mint/dataset/gdxray/Welds/W0003/real-values.xls
  - Scale phim: 40.3 micron/px (BAM readme, 630 dpi)
"""

from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from PIL import Image

YOLO_ROOT = Path("/home/sontn/Projects/Quantum_RT/data/processed/yolo-stage1-v2")
XLS = Path("/home/sontn/Projects/The Data Mint/dataset/gdxray/Welds/W0003/real-values.xls")

CLASSES = [
    "Clustered_localized_Porosity", "Gas_Pore", "Linear_Porosity",
    "Lack_of_Root_Fusion", "Lack_of_Side_Wall_Fusion", "Elongate_Cavity",
    "Slag_Inclusions", "Metallic_Inclusions", "Lack_of_Penetration",
    "Continuous_undercut", "Crack",
]

MM_PER_PX_BAM = 0.0403     # BAM readme: 40.3 micron, 630 dpi
MM_PER_PX_SPEC = 0.0334    # con số hai spec đang dùng

# Độ phân giải train ứng viên (cạnh dài)
TRAIN_SIZES = [640, 1280, 1536, 2048, 3200]
YOLO_STRIDE_FLOOR = 8      # tầng P3 — vật thể nhỏ hơn ~8px coi như không phát hiện được


def collect_real_boxes():
    """Đọc nhãn YOLO của phim thật, trả về list dict với kích thước bbox theo pixel gốc."""
    rows = []
    for split in ("train", "val", "test"):
        lbl_dir = YOLO_ROOT / split / "labels"
        img_dir = YOLO_ROOT / split / "images"
        if not lbl_dir.exists():
            continue
        for lbl in sorted(lbl_dir.glob("*.txt")):
            if lbl.name.startswith("syn"):
                continue  # bỏ ảnh synthetic, chỉ lấy phim thật
            img = img_dir / f"{lbl.stem}.png"
            if not img.exists():
                continue
            with Image.open(img) as im:
                W, H = im.size
            for line in lbl.read_text().strip().splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                cid = int(parts[0])
                _, _, w, h = (float(v) for v in parts[1:5])
                rows.append({
                    "film": lbl.stem, "split": split, "class": CLASSES[cid],
                    "img_w": W, "img_h": H,
                    "box_w_px": w * W, "box_h_px": h * H,
                })
    return pd.DataFrame(rows)


def verify_pixel_scale(df):
    """Đối chiếu scale mm/px: chiều dài phim (px) x mm/px so với số ô 1cm trong xls."""
    print("=" * 78)
    print("1. XÁC MINH SCALE mm/px")
    print("=" * 78)

    # hàng 0 của sheet là dòng đơn vị ("(cm)", "(mm)"...) — bỏ đi, giữ header gốc
    xls = pd.read_excel(XLS, sheet_name="REAL VALUES", header=0).iloc[1:]
    xls.columns = [str(c).strip() for c in xls.columns]
    cells = pd.to_numeric(xls["Cells"], errors="coerce").dropna()
    max_cell = cells.max()

    widths = df.groupby("film")["img_w"].first()
    print(f"  Số ô 1cm lớn nhất trong real-values.xls : {max_cell:.0f} ô  → phim dài ≥ {max_cell:.0f} cm")
    print(f"  Chiều rộng phim (px): median {widths.median():.0f}, dải {widths.min():.0f}–{widths.max():.0f}")
    for name, scale in (("BAM readme", MM_PER_PX_BAM), ("spec đang dùng", MM_PER_PX_SPEC)):
        length_cm = widths.median() * scale / 10.0
        print(f"  → với {scale} mm/px ({name:14s}): phim median dài {length_cm:6.1f} cm")
    print(f"\n  Phim RRT chuẩn dài ~20 cm (ô 1cm, tối đa {max_cell:.0f} ô).")
    print("  ⇒ 0.0403 mm/px khớp; 0.0334 mm/px cho ra phim ngắn hơn thực tế ~17%.\n")


def gas_pore_size_from_xls():
    """Kích thước lỗ khí thật (mm) từ bảng BAM, mã ISO 6520 = 2011 (gas pore đơn)."""
    print("=" * 78)
    print("2. KÍCH THƯỚC LỖ KHÍ THẬT THEO BẢNG BAM (ISO 6520 mã 2011)")
    print("=" * 78)

    # hàng 0 của sheet là dòng đơn vị ("(cm)", "(mm)"...) — bỏ đi, giữ header gốc
    xls = pd.read_excel(XLS, sheet_name="REAL VALUES", header=0).iloc[1:]
    xls.columns = [str(c).strip() for c in xls.columns]
    xls["Type"] = xls["Type"].astype(str).str.strip()
    pores = xls[xls["Type"].str.startswith("2011")]
    l_mm = pd.to_numeric(pores["l"], errors="coerce").dropna()

    if l_mm.empty:
        print("  (không đọc được cột l)\n")
        return None

    print(f"  n = {len(l_mm)} lỗ khí có ghi kích thước")
    print(f"  Đường kính (mm): min {l_mm.min():.2f} · p25 {l_mm.quantile(.25):.2f} · "
          f"median {l_mm.median():.2f} · p75 {l_mm.quantile(.75):.2f} · max {l_mm.max():.2f}")
    print(f"  → tại {MM_PER_PX_BAM} mm/px, native = "
          f"{l_mm.min()/MM_PER_PX_BAM:.0f}–{l_mm.max()/MM_PER_PX_BAM:.0f} px "
          f"(median {l_mm.median()/MM_PER_PX_BAM:.0f} px)\n")
    return l_mm


def visibility_table(df):
    """Bảng chính: kích thước bbox sau khi co ảnh về từng độ phân giải train."""
    print("=" * 78)
    print("3. KÍCH THƯỚC KHUYẾT TẬT SAU KHI CO ẢNH VỀ ĐỘ PHÂN GIẢI TRAIN")
    print("=" * 78)

    df = df.copy()
    df["min_side_px"] = df[["box_w_px", "box_h_px"]].min(axis=1)

    print(f"\n  Tổng {len(df)} bbox trên {df['film'].nunique()} phim thật\n")
    print(f"  {'Lớp':<32}{'n':>5}{'cạnh nhỏ nhất @native (px)':>30}")
    print("  " + "-" * 67)
    order = df.groupby("class")["min_side_px"].median().sort_values().index
    for cls in order:
        g = df[df["class"] == cls]["min_side_px"]
        print(f"  {cls:<32}{len(g):>5}   median {g.median():>6.1f}   p10 {g.quantile(.10):>6.1f}")

    print(f"\n\n  Cạnh nhỏ nhất (median) sau khi co — sàn phát hiện YOLO ≈ {YOLO_STRIDE_FLOOR} px")
    print(f"  {'Lớp':<32}" + "".join(f"{s:>9}" for s in TRAIN_SIZES) + f"{'native':>9}")
    print("  " + "-" * (32 + 9 * (len(TRAIN_SIZES) + 1)))

    verdict = defaultdict(dict)
    for cls in order:
        g = df[df["class"] == cls]
        med_native = g["min_side_px"].median()
        line = f"  {cls:<32}"
        for size in TRAIN_SIZES:
            scale = size / g["img_w"].median()
            v = med_native * scale
            verdict[cls][size] = v
            mark = "!" if v < YOLO_STRIDE_FLOOR else " "
            line += f"{v:>8.1f}{mark}"
        line += f"{med_native:>9.1f}"
        print(line)

    print(f"\n  '!' = dưới sàn phát hiện ({YOLO_STRIDE_FLOOR} px)")

    print("\n\n  Tỉ lệ bbox nằm DƯỚI sàn phát hiện, theo độ phân giải:")
    print(f"  {'Lớp':<32}" + "".join(f"{s:>9}" for s in TRAIN_SIZES))
    print("  " + "-" * (32 + 9 * len(TRAIN_SIZES)))
    for cls in order:
        g = df[df["class"] == cls]
        line = f"  {cls:<32}"
        for size in TRAIN_SIZES:
            scale = size / g["img_w"].median()
            frac = (g["min_side_px"] * scale < YOLO_STRIDE_FLOOR).mean()
            line += f"{frac*100:>8.0f}%"
        print(line)
    print()
    return verdict


def make_visual(df, out_path):
    """Ảnh trực quan: một lỗ khí thật, xem ở native rồi co dần về từng độ phân giải."""
    print("=" * 78)
    print("4. KIỂM BẰNG MẮT")
    print("=" * 78)

    pores = df[df["class"] == "Gas_Pore"].copy()
    pores["min_side_px"] = pores[["box_w_px", "box_h_px"]].min(axis=1)
    if pores.empty:
        print("  (không có bbox Gas_Pore)\n")
        return

    # lấy lỗ có kích thước gần median — đại diện, không phải trường hợp cực đoan
    target = pores["min_side_px"].median()
    pick = pores.iloc[(pores["min_side_px"] - target).abs().argsort().iloc[0]]

    # tìm lại toạ độ tâm từ file nhãn
    for split in ("train", "val", "test"):
        lbl = YOLO_ROOT / split / "labels" / f"{pick['film']}.txt"
        if lbl.exists():
            img_path = YOLO_ROOT / split / "images" / f"{pick['film']}.png"
            break
    cx = cy = None
    for line in lbl.read_text().strip().splitlines():
        p = line.split()
        if int(p[0]) == 1:  # Gas_Pore
            w, h = float(p[3]) * pick["img_w"], float(p[4]) * pick["img_h"]
            if abs(min(w, h) - pick["min_side_px"]) < 0.5:
                cx, cy = float(p[1]) * pick["img_w"], float(p[2]) * pick["img_h"]
                break
    if cx is None:
        print("  (không khớp lại được toạ độ)\n")
        return

    film = Image.open(img_path).convert("L")
    W = pick["img_w"]
    CROP = 200  # cửa sổ 200px quanh lỗ, ở độ phân giải gốc
    box = (int(cx - CROP // 2), int(cy - CROP // 2), int(cx + CROP // 2), int(cy + CROP // 2))
    crop_native = film.crop(box)

    VIEW = 260  # mỗi ô hiển thị 260px
    panels = []
    labels = []
    # native
    panels.append(crop_native.resize((VIEW, VIEW), Image.LANCZOS))
    labels.append(f"native  pore~{pick['min_side_px']:.0f}px")
    # từng độ phân giải: co cả phim rồi cắt lại đúng vùng đó
    for size in TRAIN_SIZES[::-1]:
        s = size / W
        small = film.resize((max(1, int(W * s)), max(1, int(pick['img_h'] * s))), Image.LANCZOS)
        c = int(CROP * s)
        b = (int(cx * s - c // 2), int(cy * s - c // 2), int(cx * s + c // 2), int(cy * s + c // 2))
        # phóng lại về VIEW bằng NEAREST để thấy đúng lượng thông tin còn lại
        panels.append(small.crop(b).resize((VIEW, VIEW), Image.NEAREST))
        labels.append(f"@{size}  pore~{pick['min_side_px']*s:.1f}px")

    from PIL import ImageDraw
    PAD, BAR = 8, 22
    sheet = Image.new("L", (len(panels) * (VIEW + PAD) + PAD, VIEW + BAR + 2 * PAD), 20)
    d = ImageDraw.Draw(sheet)
    for i, (p, t) in enumerate(zip(panels, labels)):
        x = PAD + i * (VIEW + PAD)
        sheet.paste(p, (x, PAD))
        d.text((x + 2, PAD + VIEW + 4), t, fill=230)
    sheet.save(out_path)
    print(f"  Phim {pick['film']}, lỗ khí tại ({cx:.0f},{cy:.0f}), cạnh {pick['min_side_px']:.0f}px @native")
    print(f"  Đã lưu: {out_path}\n")


if __name__ == "__main__":
    df = collect_real_boxes()
    verify_pixel_scale(df)
    gas_pore_size_from_xls()
    visibility_table(df)
    make_visual(df, "/tmp/claude-1000/-home-sontn-Projects-The-Data-Mint/5c68a1c4-dc07-4f54-928e-dbc6f7c3fe20/scratchpad/gas-pore-visibility.png")
