

# Tiêu chuẩn mã hóa & Hướng dẫn phát triển - The Data Mint

**Phiên bản**: 1.0
**Ngày hiệu lực**: 2026-01-31
**Áp dụng cho**: Tất cả các tệp Python, Shell và cấu hình trong `pipeline/`, `kohya-ss/`, `dataset/`

---

## Đặt tên & Tổ chức tệp

### Tệp Python

**Quy ước**: kebab-case với tên mô tả

✓ **Ví dụ tốt**:
```
batch-production-main.py       # Điểm vào chính
comfyui-rest-api-client.py     # Trình bao bọc REST API
mask-prefetch-worker-pool.py   # Nhóm worker cho các tác vụ song song
gpu-thermal-monitor.py         # Giám sát nhiệt độ GPU
crack-mask-generator.py        # Trình tạo dành riêng cho khuyết tật
post-processing-main.py        # Điểm vào xử lý hậu kỳ
yolo-dataset-builder.py        # Trình tạo định dạng tập dữ liệu
```

✗ **Tránh**:
```
BatchProduction.py             # PascalCase không được sử dụng cho tệp
batch_production.py            # Sử dụng kebab-case thay thế
batchProduction.py             # camelCase không được sử dụng cho tệp
main.py                        # Quá chung chung, không tự mô tả
```

**Lý do**: Tên tệp kebab-case dễ đọc trong danh sách tệp và chỉ rõ mục đích mà không cần kiểm tra nội dung tệp.

### Giới hạn kích thước tệp

**Mục tiêu**: <200 dòng mỗi tệp Python

**Lý do**:
- Cải thiện khả năng đọc mã
- Quản lý ngữ cảnh LLM dễ dàng hơn
- Nguyên tắc trách nhiệm đơn lẻ
- Chu kỳ nhập nhanh hơn

**Khi nào cần tách**:
- Tệp gần 200 dòng
- Nhiều lớp độc lập
- Các miền chức năng riêng biệt

**Ví dụ tái cấu trúc**:
```
Trước: comfyui-api.py (350 dòng)
  - Lớp ComfyUIClient
  - Quản lý quy trình làm việc
  - Tải lên/tải xuống hình ảnh
  - Xử lý lỗi

Sau:
  - comfyui-rest-api-client.py (180 dòng) — Trình bao bọc API
  - comfyui-workflow-manager.py (110 dòng) — Logic quy trình làm việc
  - comfyui-error-handling.py (60 dòng) — Phục hồi lỗi
```

### Cấu trúc thư mục

```
pipeline/
├── batch_manager/           # Điều phối Giai đoạn 6
│   ├── __init__.py         # Xuất mô-đun
│   ├── batch-production-main.py
│   ├── batch-job-scheduler.py
│   ├── comfyui-rest-api-client.py
│   └── [các mô-đun khác <200 dòng]
├── mask_generator/          # Tạo mặt nạ Giai đoạn 5
│   ├── __init__.py
│   ├── base-defect-mask-generator.py
│   ├── crack-mask-generator.py
│   └── [các trình tạo khác]
├── post_processing/         # Xuất chú thích Giai đoạn 7
│   ├── __init__.py
│   ├── post-processing-main.py
│   └── [các mô-đun khác <200 dòng]
├── qa/                      # Xác thực QA Giai đoạn 8
├── validation/              # Kiểm thử YOLOv8 Giai đoạn 9
├── config/                  # Cấu hình YAML/TOML
├── comfyui-workflows/       # Quy trình làm việc JSON + lời nhắc YAML
├── tests/                   # Kiểm thử tích hợp
├── logs/                    # Log thời gian chạy
└── checkpoints/             # Điểm kiểm tra tiến độ
```

---

## Kiểu mã Python

### Đặt tên lớp & hàm

**Lớp**: PascalCase
```python
class BatchJobScheduler:          # ✓
class ComfyUIClient:              # ✓
class MaskPrefetcher:             # ✓
class batch_job_scheduler:        # ✗
```

**Hàm/Phương thức**: snake_case
```python
def load_config(path):            # ✓
def batch_production_loop():      # ✓
def get_next_mask():              # ✓
def LoadConfig():                 # ✗
```

**Hằng số**: UPPER_SNAKE_CASE
```python
MAX_RETRIES = 3                   # ✓
DEFAULT_BATCH_SIZE = 16           # ✓
GPU_THERMAL_MAX = 85              # ✓
max_retries = 3                   # ✗
```

**Phương thức riêng tư**: Dấu gạch dưới ở đầu
```python
def _validate_connection(self):    # ✓ (sử dụng nội bộ)
def validate_connection(self):     # ✓ (API công khai)
```

### Đặt tên biến

**Rõ ràng & Mô tả**: Luôn chọn sự rõ ràng thay vì sự ngắn gọn

✓ **Tốt**:
```python
background_image = load_image(path)
defect_distribution = config["generation"]["defect_distribution"]
mask_prefetch_buffer = deque(maxlen=50)
max_thermal_temp_celsius = 85
```

✗ **Tránh**:
```python
img = load_image(path)             # Quá ngắn
dist = config["gen"]["def_dist"]   # Viết tắt
buf = deque(maxlen=50)             # Khó hiểu
max_t = 85                         # Không mô tả
```

### Gợi ý kiểu

**Yêu cầu**: Thêm gợi ý kiểu vào tất cả các chữ ký hàm

```python
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import numpy as np

def load_config(config_path: str) -> Dict:
    """Tải cấu hình lô từ tệp YAML."""
    ...

def get_next_mask(timeout: int = 60) -> Optional[np.ndarray]:
    """Lấy mặt nạ được tạo trước tiếp theo, hoặc None nếu hết thời gian chờ."""
    ...

def create_annotation(
    image_id: int,
    bbox: Tuple[int, int, int, int],
    category_id: int
) -> Dict:
    """Tạo từ điển chú thích COCO."""
    ...
```

### Chuỗi tài liệu

**Định dạng**: Chuỗi tài liệu kiểu Google cho các API công khai

```python
def batch_production_loop(config_path: str, pilot_mode: bool = False) -> None:
    """
    Vòng lặp sản xuất lô chính để tạo hình ảnh tổng hợp.

    Điều phối việc tạo mặt nạ song song, quản lý hàng đợi ComfyUI,
    giám sát nhiệt và khả năng chịu lỗi dựa trên điểm kiểm tra.

    Args:
        config_path: Đường dẫn đến batch-config.yaml (bắt buộc)
        pilot_mode: Nếu True, chỉ tạo 5 hình ảnh (1 cho mỗi loại khuyết tật)

    Returns:
        None

    Raises:
        FileNotFoundError: Nếu config_path không tồn tại
        ConnectionError: Nếu không thể truy cập API ComfyUI
        RuntimeError: Khi có lỗi nghiêm trọng (được ghi lại để xem xét thủ công)

    Example:
        >>> batch_production_loop("config/batch-config.yaml", pilot_mode=False)
        # Tạo 20K hình ảnh với ghi log tiến độ
    """
```

### Xử lý lỗi

**Mẫu**: Try-catch với các loại ngoại lệ cụ thể

```python
import logging
import traceback

logger = logging.getLogger(__name__)

try:
    result = comfyui_client.queue_prompt(workflow, prompts)
except ConnectionError as e:
    logger.error(f"Kết nối ComfyUI thất bại: {str(e)}")
    # Thử lại hoặc đưa ra ngoại lệ
except TimeoutError as e:
    logger.warning(f"Hết thời gian chờ tạo hình ảnh: {str(e)}")
    # Xử lý một cách nhẹ nhàng
except Exception as e:
    logger.critical(f"Lỗi không mong muốn: {str(e)}\n{traceback.format_exc()}")
    raise
```

**Không có lỗi im lặng**:
```python
# ✗ Xấu
try:
    do_something()
except:
    pass  # Âm thầm bỏ qua tất cả các lỗi

# ✓ Tốt
try:
    do_something()
except SpecificError as e:
    logger.error(f"Chi tiết lỗi: {e}")
    raise  # Đưa lại ngoại lệ cho người gọi
```

### Imports

**Tổ chức**:
1. Thư viện chuẩn
2. Gói của bên thứ ba
3. Mô-đun cục bộ
4. Dòng trống giữa các nhóm

```python
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import yaml
from PIL import Image

from batch_manager import BatchJobScheduler, ComfyUIClient
from mask_generator import get_generator
from config import load_config
```

**Tránh Import vòng tròn**:
- Sử dụng `from . import module` thay vì `import module`
- Định nghĩa các kiểu chia sẻ trong một tệp `types.py` riêng nếu cần

---

## Quản lý cấu hình

### Tệp YAML (batch-config.yaml)

**Cấu trúc**: Phân cấp với các phần rõ ràng

```yaml
# Cấu hình sản xuất lô

comfyui:
  host: "172.21.192.1"
  port: 8188
  # Chú thích giải thích mỗi cài đặt

generation:
  total_images: 20000
  resolution: 512
  defect_distribution:
    crack: 0.25        # 5000 hình ảnh (25%)
    porosity: 0.25     # 5000 hình ảnh

lora_models:
  crack: "xray_crack_lora_r32.safetensors"  # Phải khớp với tên tệp thực tế

thermal:
  enabled: true
  max_temp_celsius: 85   # Ngưỡng tạm dừng
  resume_temp_celsius: 75  # Ngưỡng tiếp tục
```

**Xác thực**:
```python
def validate_config(config: Dict) -> bool:
    """Xác thực các khóa bắt buộc và phạm vi giá trị."""
    required_keys = ["comfyui", "generation", "lora_models"]
    for key in required_keys:
        assert key in config, f"Thiếu khóa cấu hình bắt buộc: {key}"

    assert config["generation"]["total_images"] > 0
    assert config["thermal"]["max_temp_celsius"] > 60
    assert sum(config["generation"]["defect_distribution"].values()) == 1.0
    return True
```

### Tệp TOML (kohya-ss/configs/*.toml)

**Quy ước**: Một cấu hình cho mỗi loại LoRA

```toml
# Cấu hình huấn luyện Crack LoRA

[model_arguments]
pretrained_model_name_or_path = "runwayml/stable-diffusion-v1-5"
v2 = false
v_parameterization = false

[train_arguments]
output_dir = "./output/crack"
training_steps = 1000
learning_rate = 1e-4
batch_size = 4
enable_bucket = true

[network_arguments]
network_module = "networks.lora"
network_dim = 32
network_alpha = 16
```

---

## Ghi log

### Mẫu: Sử dụng mô-đun logging của Python

```python
import logging

logger = logging.getLogger(__name__)

def process_image(image_path: str) -> np.ndarray:
    logger.debug(f"Đang tải hình ảnh: {image_path}")
    img = cv2.imread(image_path)

    if img is None:
        logger.warning(f"Không thể tải hình ảnh: {image_path}")
        return None

    logger.info(f"Tải hình ảnh thành công: {img.shape}")
    return img
```

### Cấp độ log

| Cấp độ | Khi nào sử dụng | Ví dụ |
|-------|------------|---------|
| DEBUG | Thông tin phát triển | "Đang tải cấu hình từ..." |
| INFO | Tiến trình bình thường | "Đã tạo 1000 hình ảnh..." |
| WARNING | Vấn đề có thể phục hồi | "Điểm SSIM thấp (0.82)" |
| ERROR | Lỗi không nghiêm trọng | "Không thể tải mặt nạ, đang thử lại..." |
| CRITICAL | Lỗi nghiêm trọng | "Không thể truy cập API ComfyUI, đang hủy bỏ" |

### Ghi log điểm kiểm tra & trạng thái

```python
if job_id % 100 == 0:
    logger.info(f"[CHECKPOINT] Đã tạo {job_id} hình ảnh, đã trôi qua: {elapsed:.1f}s")
    checkpoint_manager.save_checkpoint(job_id, defect_counts, timestamp)
```

---

## Kiểm thử

### Kiểm thử đơn vị

**Vị trí**: `pipeline/tests/test_*.py`
**Framework**: pytest

```python
import pytest
from batch_manager import BatchJobScheduler

def test_scheduler_initialization():
    """Kiểm tra bộ lập lịch tạo phân phối khuyết tật chính xác."""
    scheduler = BatchJobScheduler(
        total_images=1000,
        defect_distribution={"crack": 0.5, "porosity": 0.5},
        backgrounds_dir="/tmp"
    )
    assert scheduler.total_images == 1000

def test_scheduler_respects_distribution():
    """Kiểm tra bộ lập lịch duy trì phân phối khuyết tật."""
    scheduler = BatchJobScheduler(total_images=100, ...)

    counts = {"crack": 0, "porosity": 0}
    for _ in range(100):
        job = scheduler.next_job()
        counts[job["defect_type"]] += 1

    assert counts["crack"] == 50  # Trong giới hạn dung sai
    assert counts["porosity"] == 50
```

**Chạy kiểm thử**:
```bash
cd pipeline
python -m pytest tests/ -v
```

### Kiểm thử tích hợp

**Vị trí**: `pipeline/tests/test_integration_*.py`

```python
def test_batch_production_pilot(tmp_path):
    """Kiểm tra chạy thí điểm 5 hình ảnh từ đầu đến cuối."""
    config = load_config("config/batch-config.yaml")
    config["generation"]["total_images"] = 5

    run_batch_production(config_path, pilot_mode=True)

    # Xác minh đầu ra
    assert (tmp_path / "output/synthetic/crack").exists()
    images = list((tmp_path / "output/synthetic/crack").glob("*.png"))
    assert len(images) == 1
```

### Mục tiêu độ bao phủ

**Tối thiểu**: 80% độ bao phủ dòng cho các mô-đun quan trọng
- batch-production-main.py: 85%+
- batch-job-scheduler.py: 80%+
- trình tạo mặt nạ: 75%+

**Loại trừ**: (có thể bỏ qua)
- Các đường dẫn phục hồi lỗi
- Mã chỉ để ghi log
- Giả lập API bên ngoài

---

## Chú thích & Tài liệu

### Chú thích nội tuyến

**Sử dụng một cách tiết kiệm**: Chỉ cho "tại sao", không phải "cái gì"

```python
# ✓ Tốt - giải thích ý định
for i, job in enumerate(scheduler.jobs):
    # Xoay vòng qua các loại khuyết tật để duy trì phân phối đồng đều
    job["defect_type"] = defect_types[i % len(defect_types)]

# ✗ Xấu - chỉ lặp lại mã
job_id += 1  # Tăng job_id
mask = generate_mask()  # Tạo mặt nạ
```

### Chú thích thuật toán phức tạp

```python
def apply_feathering(mask: np.ndarray, width: int = 5) -> np.ndarray:
    """
    Áp dụng làm mờ Gaussian cho các cạnh của khuyết tật để làm mịn quá trình inpainting.

    Việc làm mờ tạo ra một sự chuyển tiếp mềm mại giữa vùng khuyết tật
    và nền, ngăn chặn các cạnh cứng xuất hiện trong các khu vực được inpainting.
    Sử dụng hạt nhân Gaussian được chuẩn hóa với sigma = width/2.
    """
    sigma = width / 2.0
    return cv2.GaussianBlur(mask, (width, width), sigma)
```

---

## Hiệu suất & Tối ưu hóa

### Định hình

**Khi nào cần định hình**: Trước khi đưa ra các tuyên bố tối ưu hóa

```python
import cProfile
import pstats

def profile_batch_generation():
    profiler = cProfile.Profile()
    profiler.enable()

    # Chạy mã để định hình
    batch_production_loop(config_path)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # 10 hàm hàng đầu theo thời gian
```

### Hướng dẫn tối ưu hóa

**Thứ tự ưu tiên**:
1. **Tính đúng đắn** — Luôn hoạt động, tạo ra các đầu ra hợp lệ
2. **Khả năng đọc** — Mã rõ ràng mà người khác có thể bảo trì
3. **Hiệu suất** — Cải thiện tốc độ chỉ khi cần thiết

**Tránh tối ưu hóa sớm**:
```python
# ✗ Tối ưu hóa quá mức, không rõ ràng
masks = np.array([m.ravel()[i] for m, i in zip(ms, idx)])

# ✓ Rõ ràng và đủ nhanh
masks = [generate_mask(d, seed) for d, seed in jobs]
```

---

## Phụ thuộc & Phiên bản

### requirements.txt

**Vị trí**: `pipeline/requirements.txt`

```
# Cốt lõi
opencv-python==4.8.1.78
numpy==1.24.3
pillow==10.0.0
pyyaml==6.0
tqdm==4.66.1

# QA
scikit-image==0.21.0

# Xác thực
ultralytics==8.0.192
torch==2.0.1
torchvision==0.15.2

# Tùy chọn
pycocotools==2.0.6
nvidia-ml-py==11.525.112
```

**Chính sách cập nhật**:
- Ghim các phiên bản chính.phụ (ví dụ: `==4.8.*`)
- Kiểm thử trước khi nâng cấp các phụ thuộc
- Ghi lại các thay đổi đột phá trong ghi chú nâng cấp

---

## Thông điệp commit Git

### Định dạng: Conventional Commits

```
<loại>(<phạm vi>): <chủ đề>

<nội dung>

<chân trang>
```

### Các loại

| Loại | Mục đích |
|------|---------|
| feat | Tính năng mới |
| fix | Sửa lỗi |
| refactor | Tái tổ chức mã (không thay đổi tính năng) |
| perf | Cải thiện hiệu suất |
| test | Thêm/cập nhật kiểm thử |
| docs | Thay đổi tài liệu |
| chore | Công cụ, phụ thuộc, dọn dẹp |

### Ví dụ

```
feat(batch-manager): thêm giám sát nhiệt độ GPU

- Giám sát nhiệt độ GPU mỗi 30 giây
- Tạm dừng tạo nếu nhiệt độ vượt quá 85°C
- Tiếp tục khi nhiệt độ giảm xuống 75°C
- Ngưỡng có thể cấu hình trong batch-config.yaml

Fixes #42
```

```
fix(mask-generator): xử lý trường hợp biên cho hình ảnh nhỏ

Trước đây bị treo khi kích thước hình ảnh < 50px.
Bây giờ bỏ qua việc tạo và ghi lại cảnh báo.
```

```
docs: cập nhật README với dữ liệu thông lượng 1,097 hình/giờ

Dựa trên trung bình chạy thí điểm 500 hình ảnh.
```

---

## Bảo mật & Bí mật

### Khóa API & Thông tin xác thực

**Không bao giờ commit**:
- Tệp `.env` (sử dụng `.env.example`)
- Khóa API, token, mật khẩu
- Thông tin xác thực cơ sở dữ liệu
- Tệp cấu hình riêng tư

**Mẫu an toàn**:
```python
import os
from dotenv import load_dotenv

load_dotenv(".env.local")  # Chỉ cục bộ, không có trong git

COMFYUI_API_KEY = os.getenv("COMFYUI_API_KEY")
assert COMFYUI_API_KEY, "Thiếu COMFYUI_API_KEY trong .env"
```

### Quyền tệp

**Tệp an toàn**:
```bash
# Không commit cấu hình riêng tư
echo ".env*" >> .gitignore
echo "*.pem" >> .gitignore
echo "checkpoint-state.json" >> .gitignore
```

---

## Danh sách kiểm tra đánh giá mã

Trước khi gửi PR:

- [ ] Không có lỗi cú pháp (chạy `python -m py_compile`)
- [ ] Tất cả các gợi ý kiểu đều có mặt
- [ ] Chuỗi tài liệu cho các hàm công khai
- [ ] Kiểm thử được thêm/cập nhật
- [ ] Độ bao phủ kiểm thử ≥80%
- [ ] Không có đường dẫn được mã hóa cứng (sử dụng cấu hình)
- [ ] Ghi log ở các cấp độ phù hợp
- [ ] Không có câu lệnh print() (sử dụng logger)
- [ ] Không có khoảng trắng ở cuối dòng
- [ ] Imports được tổ chức & sắp xếp
- [ ] Tệp <200 dòng (hoặc có lý do chính đáng)

---

## Quy trình phát triển

### Thiết lập cục bộ

```bash
cd /mnt/e/The\ Data\ Mint/pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Chạy kiểm thử
pytest tests/ -v

# Chạy linting (nếu được cấu hình)
python -m flake8 --max-line-length=100 batch_manager/ mask_generator/
```

### Trước khi commit

```bash
# Định dạng mã
python -m black batch_manager/ mask_generator/  # Tùy chọn

# Chạy kiểm thử
pytest tests/ -v --cov=batch_manager --cov-fail-under=80

# Xác minh không có imports nào bị hỏng
python -c "from batch_manager import *; from mask_generator import *"
```

---

## Hỏi & Đáp

**H: Tại sao lại dùng kebab-case cho tệp?**
Đ: Nhất quán, dễ đọc trong đầu ra `ls`, dễ dàng cho các công cụ LLM phân tích ý định.

**H: <200 dòng có vẻ hạn chế. Nếu logic mạch lạc thì sao?**
Đ: Trách nhiệm đơn lẻ tốt hơn về lâu dài. Nếu nó cảm thấy mạch lạc, nó có thể được tách ra một cách mạch lạc.

**H: Nếu tôi cần import từ thư mục cha thì sao?**
Đ: Chỉ sử dụng `sys.path.insert(0, str(Path(__file__).parent.parent))` trong các điểm vào.

**H: Tôi có thể bỏ qua kiểm thử cho những thay đổi nhỏ không?**
Đ: Không. Tất cả các thay đổi mã cần có độ bao phủ kiểm thử hoặc bỏ qua một cách rõ ràng với tài liệu.

**H: Thư viện bên ngoài không tuân theo các tiêu chuẩn này. Tôi có cần tuân theo không?**
Đ: Có, chỉ đối với mã bạn viết. Điều chỉnh mã bên ngoài khi cần thiết.

---

**Cập nhật lần cuối**: 2026-01-31
**Phiên bản**: 1.0
**Người bảo trì**: Nhóm phát triển
