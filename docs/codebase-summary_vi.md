
# Tóm tắt cơ sở mã - The Data Mint

**Tạo ngày**: 2026-01-31
**Token Repomix**: 1,861,620 (6.55 triệu ký tự)
**Tổng số tệp**: 5,116
**Tệp nguồn**: ~800 (Python, Shell, YAML, Config)

---

## Điều hướng nhanh

- **[Lõi quy trình](#lõi-quy-trình)** — Điều phối chính & máy khách API
- **[Trình quản lý lô](#trình-quản-lý-lô)** — Tạo và lập lịch hình ảnh
- **[Tạo mặt nạ](#tạo-mặt-nạ)** — Mặt nạ khuyết tật theo thủ tục
- **[Xử lý hậu kỳ](#xử-lý-hậu-kỳ)** — Chuyển đổi chú thích
- **[Đảm bảo chất lượng](#đảm-bảo-chất-lượng)** — Xác thực QA
- **[Xác thực](#xác-thực)** — Huấn luyện và kiểm tra YOLOv8
- **[Cấu hình](#cấu-hình)** — Cấu hình YAML/TOML
- **[Dịch vụ bên ngoài](#dịch-vụ-bên-ngoài)** — Phụ thuộc và tích hợp

---

## Lõi quy trình

### Điểm vào & Điều phối

**`pipeline/run-batch-production.sh`** (43 dòng)
- Trình khởi chạy sản xuất lô chính
- Kích hoạt venv, chạy batch-production-main.py
- Ghi log đầu ra vào `pipeline/logs/batch-production-*.log`

**`pipeline/run-post-processing.sh`** (73 dòng)
- Trình điều phối xử lý hậu kỳ
- Chạy trình chuyển đổi mặt nạ sang chú thích, trình tạo COCO, trình tạo YOLO, trình chia tách
- Hỗ trợ các tham số tùy chỉnh: `--synthetic-dir`, `--output-dir`, `--train-ratio`

**`pipeline/comfyui-api-batch-inpaint-client.py`** (376 dòng)
- **Lớp**: `ComfyUIInpaintClient`
- **Các phương thức chính**:
  - `__init__(host, port)` — Khởi tạo kết nối
  - `upload_image(image_path)` — Tải hình ảnh lên ComfyUI
  - `queue_prompt(workflow_json, prompt_dict)` — Đưa công việc tạo vào hàng đợi
  - `poll_progress(prompt_id, timeout)` — Chờ hoàn thành
  - `get_image(output_dir, workflow)` — Lấy hình ảnh đã tạo + siêu dữ liệu
  - `reload_models(model_names)` — Tải LoRA vào bộ nhớ
  - `validate_connection()` — Kiểm tra tình trạng

**`pipeline/verify-comfyui-setup.py`** (197 dòng)
- Kiểm tra trước khi chạy:
  - Kết nối API ComfyUI
  - Các mô hình bắt buộc (SD1.5, ControlNet)
  - Tệp safetensors LoRA
  - Tính hợp lệ của JSON quy trình làm việc
  - Quyền thư mục đầu ra

---

## Trình quản lý lô

**Vị trí**: `pipeline/batch_manager/`
**Mục đích**: Giai đoạn 6 - Điều phối việc tạo 20K hình ảnh với độ tin cậy
**Tổng LOC**: ~1,400

### Mô-đun lõi

**`batch_manager/__init__.py`** (51 dòng)
- Xuất: `ComfyUIClient`, `BatchJobScheduler`, `MaskPrefetcher`, `GPUThermalMonitor`, `CheckpointManager`
- Khởi tạo mô-đun

**`batch-production-main.py`** (321 dòng)
- **Điểm vào để tạo lô**
- **Vòng lặp chính**:
  1. Tải cấu hình (YAML)
  2. Kiểm tra kết nối ComfyUI
  3. Khởi tạo bộ lập lịch, bộ tìm nạp trước, bộ giám sát nhiệt, trình quản lý điểm kiểm tra
  4. Tiếp tục từ điểm kiểm tra nếu tồn tại
  5. Điền trước bộ đệm mặt nạ (50 mặt nạ)
  6. Lặp cho đến khi `total_images`:
     - Kiểm tra nhiệt (tạm dừng nếu >85°C)
     - Lấy công việc tiếp theo từ bộ lập lịch
     - Tìm nạp trước mặt nạ
     - Tải lên hình ảnh nền
     - Đưa lời nhắc ComfyUI vào hàng đợi
     - Thăm dò kết quả
     - Lưu hình ảnh + siêu dữ liệu + mặt nạ
     - Điểm kiểm tra mỗi 100 hình ảnh
  7. Tạo báo cáo cuối cùng

- **Các hàm chính**:
  - `load_config(config_path)` — Phân tích cú pháp YAML
  - `save_metadata(job, output_path, config)` — Siêu dữ liệu JSON cho mỗi hình ảnh
  - `run_batch_production(config_path, pilot_mode)` — Trình điều phối chính

### Lập lịch

**`batch-job-scheduler.py`** (263 dòng)
- **Lớp**: `BatchJobScheduler`
- **Mục đích**: Phân phối công bằng cho 5 loại khuyết tật
- **Các phương thức chính**:
  - `__init__(total_images, defect_distribution, backgrounds_dir)` — Khởi tạo hàng đợi
  - `next_job()` — Lấy công việc tiếp theo (xoay vòng các loại khuyết tật dựa trên phân phối)
  - `get_status()` — Theo dõi tiến độ
  - `reset()` — Xóa hàng đợi

- **Cấu trúc dữ liệu**:
  ```python
  Job = {
    "job_id": int,
    "defect_type": str,  # crack, porosity, inclusion, LOF, undercut
    "seed": int,
    "background_image": Path,
    "lora_model": str
  }
  ```

### Trình bao bọc API ComfyUI

**`comfyui-rest-api-client.py`** (183 dòng)
- **Lớp**: `ComfyUIClient`
- **URL cơ sở**: `http://{host}:{port}/api/`
- **Các phương thức chính**:
  - `upload_image(image_path)` → tên hình ảnh cho quy trình làm việc
  - `queue_prompt(workflow_json, prompt_dict)` → prompt_id
  - `get_prompt_status(prompt_id)` → execution_status
  - `poll_completion(prompt_id, timeout=300)` → (thành công, hình ảnh)
  - `get_generated_images()` → danh sách các tệp đã tạo
  - `reload_lora(lora_name)` → tải vào vRAM
  - `validate()` → kiểm tra tình trạng (GET /status)

- **Xử lý lỗi**:
  - Thử lại khi có lỗi kết nối (tối đa 3 lần)
  - Hết thời gian chờ sau 300 giây cho mỗi hình ảnh
  - Xóa bộ đệm lời nhắc khi thất bại

### Tìm nạp trước mặt nạ

**`mask-prefetch-worker-pool.py`** (173 dòng)
- **Lớp**: `MaskPrefetcher`
- **Mục đích**: Tạo trước mặt nạ trong khi GPU xử lý hình ảnh trước đó
- **Các phương thức chính**:
  - `__init__(mask_generators, workers=8, buffer_size=50)` — Khởi tạo nhóm luồng
  - `prefetch_next(defect_type)` — Đưa việc tạo mặt nạ vào hàng đợi
  - `get_next_mask(timeout=60)` → PIL.Image (mặt nạ nhị phân)
  - `close()` — Dọn dẹp các luồng worker

- **Triển khai**:
  - ThreadPoolExecutor với 8 worker
  - Đồng bộ hóa dựa trên hàng đợi
  - Điền trước bộ đệm với 50 mặt nạ trước khi vòng lặp chính bắt đầu

### Quản lý nhiệt GPU

**`gpu-thermal-monitor.py`** (143 dòng)
- **Lớp**: `GPUThermalMonitor`
- **Mục đích**: Ngăn chặn điều tiết nhiệt
- **Các phương thức chính**:
  - `__init__(max_temp=85, resume_temp=75, check_interval=30)` — Khởi tạo ngưỡng
  - `check_temperature()` → float (độ C)
  - `should_pause()` → bool (nhiệt độ > max_temp)
  - `can_resume()` → bool (nhiệt độ < resume_temp)
  - `wait_for_safe()` → chặn cho đến khi nhiệt độ an toàn

- **Triển khai**:
  - Đọc đầu ra của `nvidia-smi`
  - Phân tích cú pháp nhiệt độ GPU từ chuỗi truy vấn
  - Ghi log các sự kiện tạm dừng/tiếp tục
  - Ngưỡng có thể cấu hình trong batch-config.yaml

### Trạng thái & Điểm kiểm tra

**`checkpoint-state-manager.py`** (109 dòng)
- **Lớp**: `CheckpointManager`
- **Mục đích**: Tiếp tục khi có lỗi
- **Các phương thức chính**:
  - `__init__(checkpoint_dir)` — Đặt thư mục điểm kiểm tra
  - `save_checkpoint(job_id, defect_counts, timestamp)` → None
  - `load_checkpoint()` → (job_id, defect_counts) hoặc (None, {})
  - `clear_checkpoint()` → Xóa tệp điểm kiểm tra

- **Định dạng điểm kiểm tra** (JSON):
  ```json
  {
    "job_id": 1234,
    "timestamp": "2026-01-31 14:25:30",
    "defect_counts": {
      "crack": 2500,
      "porosity": 2500,
      "inclusion": 2000,
      "lack_of_fusion": 1500,
      "undercut": 1500
    }
  }
  ```

- **Phục hồi**: Điểm kiểm tra mỗi 100 hình ảnh, tự động tiếp tục khi khởi động lại

---

## Tạo mặt nạ

**Vị trí**: `pipeline/mask_generator/`
**Mục đích**: Giai đoạn 5 - Tạo mặt nạ khuyết tật theo thủ tục để inpainting
**Tổng LOC**: ~600

### Lớp cơ sở

**`base-defect-mask-generator.py`** (58 dòng)
- **Lớp**: `BaseDefectMaskGenerator`
- **Các phương thức trừu tượng**:
  - `generate(background_shape, roi_mask, seed) → np.ndarray` (mặt nạ nhị phân)
  - `get_defect_name() → str`

- **Tiện ích**:
  - `apply_roi_constraint(mask, roi_mask)` — Giữ khuyết tật trong khu vực hàn
  - `feather_edges(mask, feather_width)` — Làm mịn ranh giới
  - `validate_mask(mask)` → bool

### Các trình tạo khuyết tật

**`crack-mask-generator.py`** (127 dòng)
- **Lớp**: `CrackMaskGenerator(BaseDefectMaskGenerator)`
- **Thuật toán**: Mô phỏng sự lan truyền của vết nứt thông qua xói mòn + giãn nở
  - Đi bộ ngẫu nhiên trên lưới
  - Các phép toán hình thái cho hình học vết nứt thực tế
  - Phân nhánh cho các vết nứt phức tạp
- **Tham số**:
  - Chiều rộng vết nứt: 2-8 pixel
  - Chiều dài vết nứt: 50-200 pixel
  - Xác suất phân nhánh: 0.1-0.3

**`porosity-mask-generator.py`** (94 dòng)
- **Lớp**: `PorosityMaskGenerator(BaseDefectMaskGenerator)`
- **Thuật toán**: Cụm lỗ rỗng hình tròn
  - Phân phối Gaussian ngẫu nhiên của các tâm lỗ rỗng
  - Các vòng tròn chồng chéo với bán kính khác nhau
  - Hợp nhất các lỗ rỗng liền kề
- **Tham số**:
  - Bán kính lỗ rỗng: 3-15 pixel
  - Số lượng lỗ rỗng: 10-50 mỗi vùng khuyết tật

**`slag-inclusion-mask-generator.py`** (121 dòng)
- **Lớp**: `SlagInclusionMaskGenerator(BaseDefectMaskGenerator)`
- **Thuật toán**: Các tạp chất góc cạnh không đều
  - Bao lồi của các điểm ngẫu nhiên
  - Nhiều đa giác chồng chéo
  - Ranh giới góc cạnh/lởm chởm
- **Tham số**:
  - Kích thước tạp chất: 20-60 pixel
  - Số lượng tạp chất: 3-10
  - Độ góc cạnh: 0.5-1.0

**`lack-of-fusion-mask-generator.py`** (91 dòng)
- **Lớp**: `LackOfFusionMaskGenerator(BaseDefectMaskGenerator)`
- **Thuật toán**: Các đường nối/khoảng trống tuyến tính
  - Các đường ngang hoặc nghiêng
  - Độ dày thay đổi (2-6 pixel)
  - Các cạnh lởm chởm thông qua giãn nở
- **Tham số**:
  - Chiều dài đường nối: 100-300 pixel
  - Độ dày đường nối: 2-6 pixel
  - Góc: 0-45 độ

**`undercut-mask-generator.py`** (96 dòng)
- **Lớp**: `UndercutMaskGenerator(BaseDefectMaskGenerator)`
- **Thuật toán**: Các rãnh bề mặt dọc theo cạnh hàn
  - Các đặc điểm tuyến tính ở ranh giới hàn
  - Các vùng mỏng, thon dài
  - Theo chu vi ROI
- **Tham số**:
  - Chiều rộng rãnh: 1-4 pixel
  - Chiều dài rãnh: 80-200 pixel

### Tiện ích

**`feathering-utility.py`** (29 dòng)
- **Hàm**: `apply_feathering(mask, width=5) → np.ndarray`
- Làm mờ Gaussian + ngưỡng để làm mịn ranh giới inpainting

**`weld-roi-constraint.py`** (40 dòng)
- **Hàm**: `generate_roi_mask(image_shape, roi_type='center') → np.ndarray`
- Hạn chế khuyết tật trong vùng hàn (80% trung tâm của hình ảnh)

### Khởi tạo

**`mask_generator/__init__.py`** (51 dòng)
- Xuất tất cả 5 trình tạo
- Phương thức factory: `get_generator(defect_type) → BaseDefectMaskGenerator`

---

## Xử lý hậu kỳ

**Vị trí**: `pipeline/post_processing/`
**Mục đích**: Giai đoạn 7 - Chuyển đổi mặt nạ thành chú thích COCO/YOLO
**Tổng LOC**: ~880

### Điểm vào

**`post-processing-main.py`** (203 dòng)
- **Vòng lặp chính**:
  1. Phân tích cú pháp các đối số dòng lệnh
  2. Quét `synthetic_dir` để tìm các thư mục con của khuyết tật
  3. Đối với mỗi loại khuyết tật:
     - Tải các cặp hình ảnh + mặt nạ
     - Chuyển đổi mặt nạ thành chú thích
     - Nhóm theo phân chia (train/val/test)
  4. Xây dựng tập dữ liệu COCO (chú thích + hình ảnh)
  5. Xây dựng tập dữ liệu YOLO (hình ảnh + tệp TXT nhãn)
  6. Tạo báo cáo

- **Các hàm chính**:
  - `process_defect_type(defect_type, images_dir, masks_dir, output_dir)` → None
  - `generate_report(stats) → str` (tóm tắt markdown)

### Chuyển đổi chú thích

**`mask-to-annotation-converter.py`** (154 dòng)
- **Lớp**: `MaskToAnnotationConverter`
- **Các phương thức chính**:
  - `mask_to_bbox(mask) → (x, y, w, h)` — Trích xuất hộp giới hạn
  - `mask_to_polygon(mask, simplify=True) → [(x1,y1), (x2,y2), ...]` — Phân đoạn đa giác
  - `create_coco_annotation(image_id, bbox, polygon, category_id) → dict`

- **Tính năng**:
  - Phân tích thành phần được kết nối cho các khuyết tật đa vùng
  - Đơn giản hóa đa giác Douglas-Peucker (epsilon=1.0)
  - Lọc diện tích (tối thiểu 50 pixel²)

### Định dạng COCO

**`coco-dataset-builder.py`** (160 dòng)
- **Lớp**: `COCODatasetBuilder`
- **Cấu trúc**:
  ```python
  {
    "info": {...},
    "licenses": [...],
    "images": [
      {"id": 1, "file_name": "crack_000000.png", "height": 512, "width": 512}
    ],
    "annotations": [
      {
        "id": 1,
        "image_id": 1,
        "category_id": 1,
        "bbox": [x, y, w, h],
        "area": w*h,
        "segmentation": [[x1,y1,x2,y2,...]],
        "iscrowd": 0
      }
    ],
    "categories": [
      {"id": 1, "name": "crack"},
      ...
    ]
  }
  ```
- **Xác thực**: kiểm tra tương thích pycocotools

### Định dạng YOLO

**`yolo-dataset-builder.py`** (182 dòng)
- **Lớp**: `YOLODatasetBuilder`
- **Cấu trúc đầu ra**:
  ```
  yolo/
  ├── train/images/ ├── labels/
  ├── val/images/ ├── labels/
  ├── test/images/ ├── labels/
  └── data.yaml
  ```
- **Định dạng nhãn** (một dòng cho mỗi khuyết tật):
  ```
  <class_id> <x_center> <y_center> <width> <height>
  ```
  (tất cả được chuẩn hóa thành [0, 1])
- **data.yaml**:
  ```yaml
  path: /absolute/path
  train: train/images
  val: val/images
  test: test/images
  nc: 5
  names: [crack, porosity, inclusion, lack_of_fusion, undercut]
  ```

### Phân chia tập dữ liệu

**`dataset-splitter.py`** (185 dòng)
- **Lớp**: `DatasetSplitter`
- **Các phương thức chính**:
  - `stratified_split(image_list, train_ratio, val_ratio) → (train, val, test)`
  - `split_by_defect_type(images, defect_classes, ratios) → splits`

- **Tính năng**:
  - Phân chia phân tầng (duy trì phân phối khuyết tật trên các phần chia)
  - Có thể tái tạo thông qua seed
  - Cân bằng cho mỗi loại khuyết tật

---

## Đảm bảo chất lượng

**Vị trí**: `pipeline/qa/`
**Mục đích**: Giai đoạn 8 - Xác thực hình ảnh và chú thích tổng hợp
**Tổng LOC**: ~1,000

### Điểm vào

**`qa-pipeline-main.py`** (347 dòng)
- **Các bước thực thi**:
  1. Kiểm tra tính nhất quán của nền SSIM (mẫu 500)
  2. Xác thực định dạng chú thích COCO/YOLO
  3. Kiểm tra phân phối trên các loại khuyết tật
  4. Tạo thư viện kiểm tra trực quan tại chỗ
  5. Biên soạn báo cáo QA (markdown)
  6. Lưu kết quả (JSON)

- **Đầu ra**:
  - `qa-report.md` — Tóm tắt + đạt/không đạt
  - `qa-results.json` — Các chỉ số chi tiết
  - `spot-check-gallery.html` — HTML kiểm tra trực quan

**`annotation-validator.py`** (273 dòng)
- **Lớp**: `AnnotationValidator`
- **Kiểm tra**:
  - COCO JSON có thể tải bằng pycocotools
  - YOLO data.yaml có thể tải bằng Ultralytics
  - Hộp giới hạn trong giới hạn hình ảnh [0, W] × [0, H]
  - Tọa độ đa giác hợp lệ và không tự cắt nhau
  - Số lượng hình ảnh khớp với số lượng chú thích
  - ID danh mục khớp với các loại khuyết tật dự kiến
  - Không có chú thích trùng lặp

- **Các phương thức chính**:
  - `validate_coco_format(coco_dict) → (hợp lệ, lỗi)`
  - `validate_yolo_format(yolo_dir) → (hợp lệ, lỗi)`
  - `check_bbox_bounds(bbox, img_w, img_h) → bool`

**`ssim-background-checker.py`** (166 dòng)
- **Lớp**: `SSIMBackgroundChecker`
- **Mục đích**: Xác minh inpainting không làm biến dạng nền
- **Thuật toán**:
  - So sánh nền hình ảnh tổng hợp với nền gốc
  - Che vùng khuyết tật (sử dụng mặt nạ)
  - Tính toán Chỉ số tương đồng cấu trúc (SSIM)
  - Ngưỡng: trung bình ≥0.90, tỷ lệ đạt ≥85%

- **Các phương thức chính**:
  - `compute_ssim_for_image(synth_img, background_img, defect_mask) → float`
  - `batch_check(synth_dir, sample_size=500) → (trung bình, độ lệch chuẩn, tỷ lệ đạt)`

**`visual-spot-check-grid.py`** (244 dòng)
- **Lớp**: `VisualSpotCheckGallery`
- **Mục đích**: Thư viện HTML để QA thủ công
- **Tính năng**:
  - Mẫu ngẫu nhiên 1-2% của tập dữ liệu
  - Bố cục lưới (5 cột × N hàng)
  - Mỗi hình ảnh: tổng hợp + mặt nạ + siêu dữ liệu
  - Các phần loại khuyết tật có thể thu gọn
  - Lớp phủ điểm SSIM
  - Chỉ báo đạt/không đạt

- **Đầu ra**: Tệp HTML đơn, độc lập (~2-5MB)

---

## Xác thực

**Vị trí**: `pipeline/validation/`
**Mục đích**: Giai đoạn 9 - Xác thực xuôi dòng YOLOv8
**Tổng LOC**: ~790

### Điểm vào

**`validation-main.py`** (388 dòng)
- **Thiết kế thử nghiệm**:
  1. Tải tập kiểm tra thực (hình ảnh GDXray được giữ lại ở định dạng YOLO)
  2. Tạo cấu hình thử nghiệm cho các tỷ lệ tổng hợp khác nhau
  3. Đối với mỗi tỷ lệ: huấn luyện YOLOv8, đánh giá trên tập kiểm tra thực
  4. So sánh mAP trên các tỷ lệ
  5. Tạo báo cáo xác thực (markdown + JSON)

- **Thử nghiệm**:
  - Đường cơ sở chỉ thực (0% tổng hợp)
  - 20% tổng hợp + 80% thực
  - 50% tổng hợp + 50% thực
  - Chỉ 100% tổng hợp

- **Đầu ra**:
  - `validation-report.md` — Tóm tắt + các chỉ số cho mỗi lớp
  - `validation-results.json` — Các chỉ số thô
  - `results/{experiment_name}/weights/best.pt` — Các mô hình đã huấn luyện

**`yolo-trainer.py`** (190 dòng)
- **Lớp**: `YOLOv8Trainer`
- **Các phương thức chính**:
  - `__init__(model_size='n', epochs=100, batch_size=16, device='cuda:0')`
  - `train(data_yaml_path, experiment_name) → results`
  - `evaluate(weights_path, test_data_yaml) → metrics`

- **Tham số**:
  - Kích thước mô hình: n (nano), s (small), m (medium) — mặc định 'n'
  - Epoch: thường là 100
  - Kích thước lô: 16 (điều chỉnh cho VRAM)
  - Tăng cường: mosaic, mixup, HSV
  - Kiên nhẫn: 50 (dừng sớm)

**`evaluation-metrics.py`** (208 dòng)
- **Lớp**: `EvaluationMetrics`
- **Các phương thức chính**:
  - `extract_metrics(results_dir) → dict` (mAP, độ chính xác, độ thu hồi)
  - `compare_experiments(results_list) → comparison_df`
  - `get_optimal_ratio(results) → str` (tỷ lệ được đề xuất)

- **Các chỉ số được tính toán**:
  - mAP@0.5 (chỉ số chính)
  - mAP@0.5:0.95 (chỉ số nghiêm ngặt)
  - Độ chính xác/độ thu hồi cho mỗi lớp
  - Thời gian suy luận

---

## Cấu hình

**`pipeline/config/batch-config.yaml`** (68 dòng)

| Khóa | Mặc định | Mô tả |
|-----|---------|-------------|
| `comfyui.host` | 172.21.192.1 | Máy chủ API ComfyUI |
| `comfyui.port` | 8188 | Cổng API ComfyUI |
| `generation.total_images` | 20000 | Số lượng hình ảnh cần tạo |
| `generation.resolution` | 512 | Độ phân giải đầu ra (px) |
| `generation.defect_distribution` | crack: 0.25, ... | Tỷ lệ phần trăm cho mỗi khuyết tật |
| `lora_models.*` | xray_*_lora_r32.safetensors | Tên tệp LoRA |
| `sampler.steps` | 20 | Các bước khuếch tán |
| `sampler.cfg` | 7.0 | Hướng dẫn không có bộ phân loại |
| `thermal.max_temp_celsius` | 85 | Ngưỡng tạm dừng |
| `thermal.resume_temp_celsius` | 75 | Ngưỡng tiếp tục |
| `reliability.checkpoint_interval` | 100 | Điểm kiểm tra cho mỗi N hình ảnh |
| `performance.mask_prefetch_workers` | 8 | Các luồng worker CPU |

**`pipeline/config/mask-config.yaml`** (tùy chọn)
- Các tham số của trình tạo cho mỗi khuyết tật
- Chưa được triển khai (sử dụng các giá trị mặc định được mã hóa cứng trong các trình tạo)

**`kohya-ss/configs/*.toml`** (5 tệp, ~60 dòng mỗi tệp)
- Các siêu tham số huấn luyện LoRA
- Tệp:
  - `crack-lora-training-config.toml`
  - `porosity-lora-training-config.toml`
  - `inclusion-lora-training-config.toml`
  - `lack-of-fusion-lora-training-config.toml`
  - `undercut-lora-training-config.toml`

**`pipeline/comfyui-workflows/`**
- `sd15-lora-controlnet-inpaint-single-defect-workflow.json` — JSON quy trình làm việc
- `defect-type-prompt-templates.yaml` — Lời nhắc cho mỗi loại khuyết tật

---

## Dịch vụ bên ngoài

### Tích hợp API ComfyUI

**Điểm cuối**: `http://172.21.192.1:8188/api/`

**Các tuyến chính**:
- `GET /status` — Kiểm tra tình trạng
- `POST /upload/image` — Tải lên hình ảnh nền
- `POST /prompt` — Đưa công việc tạo vào hàng đợi
- `GET /history/{prompt_id}` — Trạng thái công việc & đầu ra

**JSON quy trình làm việc**:
- Các nút: Load Model, Load LoRA, Load ControlNet, KSampler, VAE Decode, Save Image
- Lời nhắc: Được chèn cho mỗi loại khuyết tật (tải từ YAML)
- Đầu ra: PNG đã tạo + siêu dữ liệu

### Các mô hình LoRA

**Lưu trữ**: `/mnt/e/The Data Mint/kohya-ss/output/{defect_type}/`

| Mô hình | Tên tệp | Kích thước | Trạng thái |
|-------|----------|------|--------|
| Crack | xray_crack_lora_r32.safetensors | ~37 MB | ✓ Đã huấn luyện |
| Porosity | xray_porosity_lora_r32.safetensors | ~37 MB | ✓ Đã huấn luyện |
| Inclusion | xray_inclusion_lora_r32.safetensors | ~37 MB | ✓ Đã huấn luyện |
| LOF | xray_lof_lora_r32.safetensors | ~37 MB | ✓ Đã huấn luyện |
| Undercut | xray_undercut_lora_r32.safetensors | ~37 MB | ✓ Đã huấn luyện |

---

## Các chỉ số chính & Hiệu suất

| Thành phần | Thông lượng | Nút cổ chai |
|-----------|-----------|-----------|
| Tạo mặt nạ | ~100 mặt nạ/giây | CPU (không giới hạn) |
| Tạo ComfyUI | ~1,097 hình/giờ | GPU (RTX 3090) |
| Xử lý hậu kỳ | ~450 hình/giây | I/O |
| QA (SSIM) | ~1 hình/giây | CPU (scikit-image) |
| Huấn luyện YOLOv8 | ~50 epoch/giờ | GPU (batch_size=16) |

---

## Chiến lược tổ chức tệp

**Quy ước**:
- Tên tệp kebab-case: `batch-production-main.py`, `comfyui-rest-api-client.py`
- Kích thước mô-đun: <200 dòng mỗi tệp (trách nhiệm đơn lẻ)
- Kiểm tra: `pipeline/tests/` (hiện có 3 tệp kiểm tra)
- Log: `pipeline/logs/batch-production-*.log`

**Imports**:
- Import tương đối trong các mô-đun: `from batch_manager import ComfyUIClient`
- Import tuyệt đối cho các phụ thuộc: `import yaml`, `import numpy`
- Không có phụ thuộc vòng tròn

---

## Phụ thuộc & Phiên bản

**Python**: 3.8+

**Cốt lõi**:
- opencv-python 4.8.1
- numpy 1.24
- pillow 10.1
- pyyaml 6.0
- tqdm 4.66

**QA**:
- scikit-image 0.21 (SSIM)

**Xác thực**:
- ultralytics 8.0+ (YOLOv8)
- torch 2.0+ (suy luận GPU)
- torchvision 0.15+ (thao tác hình ảnh)

**Tùy chọn**:
- pycocotools 2.0.6 (xác thực COCO)
- nvidia-ml-py 11.0+ (nhiệt độ GPU)

---

**Cập nhật lần cuối**: 2026-01-31
**Phiên bản**: 1.0
**Tổng số dòng mã**: ~6,800 (thư mục pipeline)
