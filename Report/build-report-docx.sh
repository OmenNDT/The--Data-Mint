#!/usr/bin/env bash
# Dựng bản DOCX của báo cáo đồ án từ file Markdown nguồn.
# Cách dùng: bash Report/build-report-docx.sh
set -euo pipefail

cd "$(dirname "$0")/.."

FORM="Report/Nhóm 5 - Hệ thống cảnh báo sớm hư hỏng trên máy bơm.docx"
SRC="Report/do-an-the-data-mint.md"
OUT="Report/Do-an-The-Data-Mint.docx"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# 1. Reference-doc sạch: gỡ font nhúng, thêm các styleId pandoc cần
python3 Report/make-reference-doc.py "$FORM" "$WORK/reference-clean.docx"

# 2. Đổi \newpage sang ngắt trang OOXML (pandoc chỉ hiểu \newpage cho đầu ra LaTeX)
python3 - "$SRC" "$WORK/source.md" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
page_break = '```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```'
text = open(src, encoding="utf-8").read().replace("\\newpage", page_break)
open(dst, "w", encoding="utf-8").write(text)
PY

# 3. Chuyển sang DOCX
pandoc "$WORK/source.md" \
  --reference-doc="$WORK/reference-clean.docx" \
  --resource-path="Report" \
  -f markdown-smart -t docx -o "$OUT"   # tắt smart: giữ nháy thẳng theo quy ước văn phong

# 4. Áp định dạng của form mẫu và chèn trường mục lục
python3 Report/apply-form-formatting.py "$OUT"

echo "Xong: $OUT"
