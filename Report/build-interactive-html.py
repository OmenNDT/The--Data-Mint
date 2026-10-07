#!/usr/bin/env python3
"""Ghép ảnh vào tệp báo cáo tương tác thành một tệp HTML tự chứa.

Đọc `report-interactive-source.html`, thay mọi token `{{IMG:tên-tệp}}` bằng data URI
của ảnh tương ứng (nén lại để giữ kích thước tệp ở mức mở được trên mọi máy),
rồi ghi ra `bao-cao-the-data-mint-interactive.html`.
"""
import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "report-interactive-source.html"
OUTPUT = HERE / "bao-cao-the-data-mint-interactive.html"

# Nơi tìm ảnh, theo thứ tự ưu tiên
SEARCH_DIRS = [HERE, HERE / "figures", HERE / "figures-audit"]

MAX_WIDTH = 1500      # px, đủ để phóng to xem chi tiết mà không phình tệp
JPEG_QUALITY = 86


def find_image(name: str) -> Path:
    for directory in SEARCH_DIRS:
        candidate = directory / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Không tìm thấy ảnh: {name}")


def to_data_uri(path: Path) -> str:
    """Thu nhỏ, nén JPEG rồi mã hoá base64."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        if img.width > MAX_WIDTH:
            height = round(img.height * MAX_WIDTH / img.width)
            img = img.resize((MAX_WIDTH, height), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def main() -> int:
    html = SOURCE.read_text(encoding="utf-8")
    cache: dict[str, str] = {}

    def replace(match: re.Match) -> str:
        name = match.group(1).strip()
        if name not in cache:
            path = find_image(name)
            cache[name] = to_data_uri(path)
            print(f"  nhúng {name}  ({path.stat().st_size // 1024} KB gốc)")
        return cache[name]

    html = re.sub(r"\{\{IMG:([^}]+)\}\}", replace, html)

    leftover = re.findall(r"\{\{IMG:[^}]+\}\}", html)
    if leftover:
        print("Còn token chưa thay:", leftover, file=sys.stderr)
        return 1

    OUTPUT.write_text(html, encoding="utf-8")
    print(f"\nĐã ghi {OUTPUT.name} — {OUTPUT.stat().st_size / 1_048_576:.2f} MB, {len(cache)} ảnh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
