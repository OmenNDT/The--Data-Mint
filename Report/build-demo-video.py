#!/usr/bin/env python3
"""Ghep khung hinh da quay thanh video demo MP4 co phu de tieng Viet.

Dung sau khi chay record-demo-video.mjs.

    python3 Report/build-demo-video.py [thu-muc-khung-hinh] [tep-mp4-dau-ra]

Doan theo doi tien trinh dai hon muc can thiet nen duoc tua nhanh bang cach
lay thua khung hinh; moc thoi gian phu de duoc tinh lai theo dung ty le tua.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

FPS = 5

FRAMES_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-1000/demo-frames")
OUT_MP4 = Path(sys.argv[2] if len(sys.argv) > 2
               else "/home/sontn/Projects/The Data Mint/Report/The-Data-Mint-demo.mp4")

# Hai tam hinh ket, moi tam giu bao nhieu giay. Sinh boi build-demo-closing-slides.py
CLOSING_DIR = Path("/tmp/claude-1000/demo-closing")
CLOSING = [("closing-1-grid.png", 7), ("closing-2-card.png", 5)]

# (giay bat dau, giay ket thuc, he so tua). He so 1 la toc do that.
# Doan giua la luc cho ComfyUI sinh anh, man hinh gan nhu dung yen.
SPEED_PLAN = [
    (0, 48, 1),
    (48, 229, 5),
    (229, 10_000, 1),
]


def speed_at(t):
    for start, end, factor in SPEED_PLAN:
        if start <= t < end:
            return factor
    return 1


def build_frame_list(frames):
    """Chon khung hinh theo ke hoach tua, tra ve danh sach duong dan va anh xa thoi gian."""
    picked = []
    # time_map[i] = (thoi diem goc, thoi diem trong video moi)
    time_map = []
    counter = {}
    for index, path in enumerate(frames):
        t_src = index / FPS
        factor = speed_at(t_src)
        counter[factor] = counter.get(factor, 0) + 1
        if counter[factor] % factor != 0 and factor > 1:
            continue
        time_map.append((t_src, len(picked) / FPS))
        picked.append(path)
    return picked, time_map


def remap(t_src, time_map):
    """Doi moc thoi gian goc sang moc trong video da tua."""
    best = 0.0
    for src, dst in time_map:
        if src <= t_src:
            best = dst
        else:
            break
    return best


def srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    frames = sorted(FRAMES_DIR.glob("frame-*.png"))
    if not frames:
        sys.exit(f"Khong tim thay khung hinh trong {FRAMES_DIR}")
    captions = json.loads((FRAMES_DIR / "captions.json").read_text(encoding="utf-8"))

    picked, time_map = build_frame_list(frames)
    print(f"Khung hinh goc: {len(frames)} ({len(frames)/FPS:.0f}s)")
    print(f"Khung hinh giu: {len(picked)} ({len(picked)/FPS:.0f}s)")

    staging = FRAMES_DIR.parent / "demo-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    index = 0
    for src in picked:
        (staging / f"f-{index:06d}.png").hardlink_to(src)
        index += 1

    # Noi hai tam hinh ket bang cach lap lai khung hinh tinh
    recorded_end = index / FPS
    for name, seconds in CLOSING:
        src = CLOSING_DIR / name
        if not src.exists():
            print(f"Bo qua hinh ket thieu: {src}")
            continue
        for _ in range(int(seconds * FPS)):
            (staging / f"f-{index:06d}.png").hardlink_to(src)
            index += 1
    total_seconds = index / FPS

    srt_path = staging / "phude.srt"
    lines = []
    for i, cap in enumerate(captions, start=1):
        start = remap(cap["start"], time_map)
        end = remap(min(cap["end"], len(frames) / FPS), time_map)
        if end - start < 0.8:
            end = start + 0.8
        lines.append(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{cap['text']}\n")
    # Hai tam ket da co chu san trong anh nen khong chen phu de chong len
    srt_path.write_text("\n".join(lines), encoding="utf-8")

    style = ("FontName=DejaVu Sans,FontSize=17,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00201008,BorderStyle=4,BackColour=&HB0000000,"
             "Outline=0,Shadow=0,MarginV=28,Alignment=2")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(staging / "f-%06d.png"),
        "-vf", f"subtitles={srt_path}:force_style='{style}',format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "26",
        "-r", "25",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    print("Dang ma hoa ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-3000:])
        sys.exit("FFmpeg that bai")

    size_mb = OUT_MP4.stat().st_size / 1024 / 1024
    print(f"Xong: {OUT_MP4}  ({size_mb:.1f} MB, {total_seconds:.0f} giay, "
          f"trong do {recorded_end:.0f} giay quay man hinh)")


if __name__ == "__main__":
    main()
