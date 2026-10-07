"""Cắt ảnh sinh (512x512) cùng cỡ ô W0003 thật (278x278) để so sánh. Tách khỏi reference_w0003.py (bước 2
plan 261006-defect-metrics-w0003-reference: giữ các tệp realism/ dưới 200 dòng)."""
import zlib

import numpy as np
from scipy import ndimage as ndi

TILE_SIZE = 278   # cỡ ô khuyết tật W0003 gốc (khớp reference_w0003.TILE_SIZE)


def crop_synthetic(img, mask, size=TILE_SIZE):
    """Cắt ảnh sinh (512×512) quanh trọng tâm mặt nạ lỗi, cỡ `size`, giữ ×1 (không phóng), kẹp trong biên ảnh.
    Dùng để so ảnh sinh với ô W0003 thật cùng cỡ; LƯU Ý (xem báo cáo): ô W0003 thật KHÔNG căn giữa khuyết tật
    (ô cắt lưới cố định từ ảnh gốc lớn), còn hàm này luôn căn giữa quanh lỗi, nên vị trí lỗi trong khung lệch
    nhau có hệ thống giữa hai tập — ảnh hưởng đặc trưng nhạy vị trí biên (vd bien_*) nhiều hơn đặc trưng hình dạng."""
    img = np.asarray(img)
    h, w = img.shape[:2]
    cy, cx = ndi.center_of_mass(np.asarray(mask) > 0)
    y0 = int(np.clip(cy - size // 2, 0, max(h - size, 0)))
    x0 = int(np.clip(cx - size // 2, 0, max(w - size, 0)))
    return img[y0:y0 + size, x0:x0 + size]


def crop_synthetic_grid(img, mask, key, size=TILE_SIZE):
    """Cắt ảnh sinh (512×512) cỡ `size` quanh tâm mặt nạ lỗi NHƯNG lệch tâm một khoảng ngẫu nhiên (20..size-20
    điểm ảnh mỗi trục), seed cố định theo `key` (vd tên tệp ảnh) để tái lập được. Dùng để so ảnh sinh với ô
    W0003 thật (xem rủi ro trong plan, mục 6/10, bước 7): ô W0003 gốc là CẮT LƯỚI CỐ ĐỊNH từ ảnh lớn, khuyết tật
    không nằm giữa khung; `crop_synthetic` (căn giữa đúng tâm) lệch hệ thống so cách cắt đó, nhất là đặc trưng
    nhạy vị trí biên (bien_*). Khung lệch ngẫu nhiên nhưng vẫn LUÔN chứa tâm khuyết tật mô phỏng đúng cách W0003
    cắt theo lưới mà không biết trước lỗi nằm đâu trong ô.

    Gọi hàm này HAI LẦN với cùng (mask, key, size) nhưng `img` khác nhau (ảnh xám + chính mask) cho ra CÙNG
    khung cắt (offset chỉ phụ thuộc mask/key, không phụ thuộc img) — dùng để cắt mặt nạ khớp ảnh đã cắt khi
    cần so vùng đo với mặt nạ thật (xem defect_eval._feature_row, độ đo "đúng đối tượng")."""
    img = np.asarray(img)
    h, w = img.shape[:2]
    cy, cx = ndi.center_of_mass(np.asarray(mask) > 0)
    rng = np.random.default_rng(zlib.crc32(str(key).encode()))
    y0 = int(np.clip(cy - rng.uniform(20, size - 20), 0, max(h - size, 0)))
    x0 = int(np.clip(cx - rng.uniform(20, size - 20), 0, max(w - size, 0)))
    return img[y0:y0 + size, x0:x0 + size]
