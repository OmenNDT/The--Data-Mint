
# Kiến trúc hệ thống - Quy trình The Data Mint

**Phiên bản tài liệu**: 1.0
**Cập nhật lần cuối**: 2026-01-31
**Phạm vi**: Quy trình tạo dữ liệu tổng hợp 9 giai đoạn đầy đủ

---

## Kiến trúc cấp cao

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        QUY TRÌNH THE DATA MINT                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  GIAI ĐOẠN 1: Thiết lập môi trường                                       │
│  ├─ Cài đặt ComfyUI & thiết lập API                                     │
│  ├─ Tải xuống mô hình (SD 1.5, ControlNet v1.1)                         │
│  └─ Cài đặt môi trường ảo Python & các phụ thuộc                        │
│                                                                          │
│  GIAI ĐOẠN 2: Tiền xử lý tập dữ liệu                                      │
│  ├─ Tải hình ảnh X-quang thô GDXray W0003                               │
│  ├─ Chuẩn hóa thành độ phân giải 512×512                                │
│  └─ Trích xuất các vùng nền sạch                                         │
│                                                                          │
│  GIAI ĐOẠN 3: Tinh chỉnh LoRA (kohya-ss)                                │
│  ├─ Huấn luyện 5 mô hình LoRA độc lập (hạng 32, 10 epoch)              │
│  ├─ Theo từng loại khuyết tật: nứt, rỗ, lẫn xỉ, chảy loang, cháy cạnh   │
│  └─ Đầu ra: 5 tệp safetensors (tổng cộng ~185 MB)                       │
│                                                                          │
│  GIAI ĐOẠN 4: Thiết kế quy trình làm việc ComfyUI                        │
│  ├─ Tạo quy trình làm việc inpaint SD1.5 + LoRA + ControlNet            │
│  ├─ Định nghĩa các mẫu lời nhắc theo loại khuyết tật (YAML)             │
│  └─ Thông số bộ lấy mẫu: Euler, 20 bước, CFG 7.0                        │
│                                                                          │
│  GIAI ĐOẠN 5: Tạo mặt nạ theo thủ tục (Song song CPU)                   │
│  ├─ 5 trình tạo khuyết tật (nứt, rỗ, lẫn xỉ, chảy loang, cháy cạnh)     │
│  ├─ Các phép toán hình thái học cho hình dạng thực tế                    │
│  ├─ Ràng buộc ROI (giữ trong khu vực hàn)                               │
│  └─ Làm mờ để inpainting mượt mà                                         │
│                                                                          │
│  GIAI ĐOẠN 6: Sản xuất hàng loạt (Chuyên sâu GPU)                        │
│  ├─ Tìm nạp trước mặt nạ song song (8 worker CPU)                       │
│  ├─ Quản lý hàng đợi công việc ComfyUI (thử lại tối đa 3 lần)           │
│  ├─ Giám sát nhiệt GPU (tạm dừng ở 85°C)                                │
│  ├─ Điểm kiểm tra mỗi 100 hình ảnh (khả năng chịu lỗi)                  │
│  └─ Đầu ra: 20K-100K PNG + mặt nạ + siêu dữ liệu JSON                   │
│                                                                          │
│  GIAI ĐOẠN 7: Xử lý hậu kỳ (Xuất chú thích)                             │
│  ├─ Mặt nạ → COCO JSON (hộp giới hạn + phân đoạn)                       │
│  ├─ Mặt nạ → YOLO TXT (lớp + hộp giới hạn đã chuẩn hóa)                  │
│  ├─ Phân chia Huấn luyện/Xác thực/Kiểm tra (70/20/10 phân tầng)          │
│  └─ Đầu ra: Thư mục COCO JSON + YOLO                                    │
│                                                                          │
│  GIAI ĐOẠN 8: Đảm bảo chất lượng                                         │
│  ├─ Kiểm tra tính nhất quán của nền SSIM (mẫu 500)                      │
│  ├─ Xác thực chú thích (định dạng + giới hạn)                           │
│  ├─ Phân tích phân phối (tỷ lệ loại khuyết tật)                         │
│  ├─ Thư viện kiểm tra trực quan tại chỗ (mẫu HTML 1-2%)                 │
│  └─ Đầu ra: Báo cáo QA (đạt/không đạt + chỉ số)                         │
│                                                                          │
│  GIAI ĐOẠN 9: Xác thực xuôi dòng (YOLOv8)                               │
│  ├─ Huấn luyện YOLOv8 trên nhiều tỷ lệ tổng hợp (20%, 50%, 100%)        │
│  ├─ Đánh giá trên tập kiểm tra thực được giữ lại                        │
│  ├─ So sánh mAP giữa các tỷ lệ                                          │
│  └─ Đầu ra: Báo cáo xác thực + khuyến nghị tỷ lệ tối ưu                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Sơ đồ luồng dữ liệu

### Quy trình tạo (Giai đoạn 1-6)

```
                      Nguồn dữ liệu đầu vào
                              │
                    ┌─────────┴─────────┐
                    │                   │
            ┌───────▼────────┐  ┌──────▼──────────┐
            │   GDXray W0003 │  │  Nền đã         │
            │   (Ảnh thô)    │  │  tiền xử lý     │
            └────────────────┘  └─────────┬───────┘
                                          │
                     ┌────────────────────┘
                     │
            ┌────────▼────────────┐
            │  5 mô hình LoRA     │
            │  (hạng 32, 37MB mỗi cái) │
            └────────┬────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    │     ┌──────────▼──────────┐     │ (Song song CPU)
    │     │ Nhóm trình tạo mặt nạ │     │
    │     │ (8 worker, bộ đệm 50) │     │
    │     └──────────┬──────────┘     │
    │                │                │
    │     ┌──────────▼──────────┐     │
    │     │ Mặt nạ theo thủ tục │     │
    │     │ (5 loại khuyết tật) │     │
    │     └──────────┬──────────┘     │
    │                │                │
    ├────────────────┼────────────────┤
    │                │                │
    │     ┌──────────▼────────────────────┐
    │     │ Chính của sản xuất hàng loạt  │
    │     │ - Bộ lập lịch công việc        │
    │     │ - Máy khách API REST ComfyUI   │
    │     │ - Bộ giám sát nhiệt GPU        │
    │     │ - Trình quản lý điểm kiểm tra  │
    │     └──────────┬─────────────────────┘
    │                │
    │     ┌──────────▼──────────┐
    │     │  API ComfyUI        │
    │     │  (http://....:8188) │
    │     │  ↓ Tải lên ảnh nền  │
    │     │  ↓ Đưa lời nhắc vào hàng đợi │
    │     │  ↓ Thăm dò tiến độ  │
    │     └──────────┬──────────┘
    │                │
    │     ┌──────────▼──────────────────┐
    │     │  SD 1.5 + LoRA + ControlNet  │
    │     │  (GPU: RTX 3090)             │
    │     │  Bộ lấy mẫu: Euler, 20 bước  │
    │     └──────────┬──────────────────┘
    │                │
    └────────────────┼────────────────────┘
                     │
            ┌────────▼────────┐
            │ Đầu ra tổng hợp │
            │ - Ảnh PNG        │
            │ - Mặt nạ nhị phân │
            │ - Siêu dữ liệu JSON │
            │ (được tổ chức theo │
            │  loại khuyết tật) │
            └──────────────────┘
```

### Quy trình chú thích (Giai đoạn 7)

```
            Đầu ra tổng hợp
          (PNG + Mặt nạ + JSON)
                  │
        ┌─────────┴──────────┐
        │                    │
    ┌───▼──────────┐  ┌──────▼───────┐
    │ Tệp hình ảnh │  │ Mặt nạ nhị phân │
    └────┬─────────┘  └──────┬────────┘
         │                   │
         └─────────┬─────────┘
                   │
        ┌──────────▼───────────┐
        │ Trình chuyển đổi     │
        │ Mặt nạ→Chú thích     │
        │ - Thành phần liên thông │
        │ - Trích xuất hộp giới hạn │
        │ - Đơn giản hóa đa giác │
        └──────────┬───────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
    ┌───▼───────┐      ┌──────▼─────────┐
    │COCO JSON  │      │  YOLO TXT      │
    │- hộp giới hạn │      │  - tọa độ      │
    │- đa giác  │      │    chuẩn hóa   │
    └───┬───────┘      └──────┬─────────┘
        │                     │
        │      ┌──────────────┴────┐
        │      │                   │
        │  ┌───▼───────┐   ┌───────▼──┐
        │  │Chia dữ liệu│   │Chia dữ liệu│
        │  │  70/20/10 │   │ 70/20/10  │
        │  └─────┬─────┘   └────┬──────┘
        │        │              │
        │    ┌───▼─────────┐  ┌─▼────────────┐
        │    │COCO Huấn luyện│  │YOLO Huấn luyện│
        │    │COCO Xác thực │  │YOLO Xác thực │
        │    │COCO Kiểm tra │  │YOLO Kiểm tra │
        │    └─────────────┘  │data.yaml     │
        │                     └──────────────┘
        │
        └─ Đầu ra: /output/dataset/
           ├── annotations/
           │   ├── coco_train.json
           │   ├── coco_val.json
           │   └── coco_test.json
           └── yolo/
               ├── train/images & labels
               ├── val/images & labels
               ├── test/images & labels
               └── data.yaml
```

### Quy trình QA (Giai đoạn 8)

```
        Tập dữ liệu tổng hợp + Chú thích
                    │
        ┌───────────┼───────────┐
        │           │           │
    ┌───▼────┐  ┌───▼──────┐  ┌─▼──────────┐
    │ Trình  │  │Trình xác │  │Trình phân  │
    │kiểm tra│  │thực chú  │  │tích phân   │
    │ SSIM   │  │thích     │  │phối        │
    │        │  │          │  │            │
    │- Nền   │  │- COCO OK │  │- Tỷ lệ     │
    │  nhất quán│  │- YOLO OK │  │  mỗi loại  │
    │- >0.90 │  │- Giới hạn│  │- Độ lệch   │
    │  trung bình│  │- Đa giác │  │  < 2%      │
    └───┬────┘  └────┬─────┘  └─┬──────────┘
        │            │          │
        └────────────┼──────────┘
                     │
        ┌────────────▼─────────────┐
        │ Kiểm tra trực quan tại chỗ (HTML) │
        │ - Mẫu ngẫu nhiên 1-2%     │
        │ - Bố cục lưới            │
        │ - Lớp phủ SSIM          │
        └────────────┬─────────────┘
                     │
        ┌────────────▼──────────────────┐
        │ Báo cáo QA (Markdown)          │
        │ - Thống kê tóm tắt            │
        │ - Đạt/Không đạt mỗi lần kiểm tra │
        │ - Khuyến nghị             │
        └───────────────────────────────┘
```

### Quy trình xác thực (Giai đoạn 9)

```
        Tập dữ liệu YOLO + Tập kiểm tra thực
                    │
        ┌───────────┴────────────┐
        │                        │
    ┌───▼──────────────┐   ┌─────▼─────────┐
    │ Dữ liệu tổng hợp  │   │Tập kiểm tra thực│
    │ (được tổ chức trong │   │(được giữ lại từ│
    │  train/val/test) │   │ GDXray)        │
    └───┬──────────────┘   └────────────────┘
        │
        ├─ Thử nghiệm 1: Chỉ thực (0% tổng hợp)
        ├─ Thử nghiệm 2: 20% tổng hợp + 80% thực
        ├─ Thử nghiệm 3: 50% tổng hợp + 50% thực
        └─ Thử nghiệm 4: Chỉ 100% tổng hợp
                 │
        ┌────────▼──────────┐
        │  Huấn luyện YOLOv8n  │
        │  - 100 epoch       │
        │  - Kích thước lô 16   │
        │  - Tăng cường dữ liệu │
        └────────┬───────────┘
                 │
        ┌────────▼─────────────────┐
        │ Đánh giá trên tập kiểm tra thực │
        │ - mAP@0.5                 │
        │ - mAP@0.5:0.95            │
        │ - Chỉ số mỗi lớp       │
        │ - Thời gian suy luận          │
        └────────┬─────────────────┘
                 │
        ┌────────▼──────────────────┐
        │ So sánh & Phân tích         │
        │ - Vẽ đồ thị đường cong mAP         │
        │ - Tìm tỷ lệ tối ưu      │
        │ - Phân tích mỗi lớp     │
        └────────┬──────────────────┘
                 │
        ┌────────▼────────────────────┐
        │ Báo cáo xác thực           │
        │ - Tỷ lệ tối ưu được xác định  │
        │ - Chỉ số cải thiện mAP   │
        │ - Khuyến nghị            │
        └─────────────────────────────┘
```

---

## Kiến trúc thành phần

### Phân cấp mô-đun lõi

```
pipeline/
├── batch_manager/                    # Điều phối
│   ├── batch-production-main.py      # Trình điều phối chính (321 LOC)
│   │   └─ Điều phối tất cả các mô-đun khác
│   ├── batch-job-scheduler.py        # Hàng đợi công việc (263 LOC)
│   │   └─ Phân phối công bằng giữa các loại khuyết tật
│   ├── comfyui-rest-api-client.py    # Trình bao bọc REST (183 LOC)
│   │   └─ Đưa công việc vào hàng đợi, thăm dò trạng thái, tải xuống kết quả
│   ├── mask-prefetch-worker-pool.py  # Nhóm luồng (173 LOC)
│   │   └─ Tạo trước mặt nạ trong khi GPU bận
│   ├── gpu-thermal-monitor.py        # Nhiệt (143 LOC)
│   │   └─ Tạm dừng/tiếp tục dựa trên nhiệt độ
│   └── checkpoint-state-manager.py   # Trạng thái (109 LOC)
│       └─ Lưu/tiếp tục tiến độ
│
├── mask_generator/                   # Mặt nạ theo thủ tục (CPU)
│   ├── base-defect-mask-generator.py # Lớp cơ sở (58 LOC)
│   ├── crack-mask-generator.py       # Vết nứt (127 LOC)
│   ├── porosity-mask-generator.py    # Lỗ rỗng (94 LOC)
│   ├── slag-inclusion-mask-generator.py  # Lẫn xỉ (121 LOC)
│   ├── lack-of-fusion-mask-generator.py  # Đường nối (91 LOC)
│   ├── undercut-mask-generator.py    # Rãnh (96 LOC)
│   ├── feathering-utility.py         # Trộn cạnh (29 LOC)
│   └── weld-roi-constraint.py        # Mặt nạ vùng (40 LOC)
│
├── post_processing/                  # Xuất chú thích
│   ├── post-processing-main.py       # Trình điều phối (203 LOC)
│   ├── mask-to-annotation-converter.py  # Hộp giới hạn+đa giác (154 LOC)
│   ├── coco-dataset-builder.py       # COCO JSON (160 LOC)
│   ├── yolo-dataset-builder.py       # YOLO TXT (182 LOC)
│   └── dataset-splitter.py           # Phân chia train/val/test (185 LOC)
│
├── qa/                               # Đảm bảo chất lượng
│   ├── qa-pipeline-main.py           # Trình điều phối (347 LOC)
│   ├── ssim-background-checker.py    # Xác thực SSIM (166 LOC)
│   ├── annotation-validator.py       # Kiểm tra định dạng (273 LOC)
│   └── visual-spot-check-grid.py     # Thư viện HTML (244 LOC)
│
├── validation/                       # Kiểm tra YOLOv8
│   ├── validation-main.py            # Trình chạy thử nghiệm (388 LOC)
│   ├── yolo-trainer.py               # Trình bao bọc huấn luyện (190 LOC)
│   └── evaluation-metrics.py         # Phân tích chỉ số (208 LOC)
│
├── comfyui-api-batch-inpaint-client.py  # Máy khách một hình ảnh (376 LOC)
├── verify-comfyui-setup.py               # Kiểm tra trước khi chạy (197 LOC)
└── config/                               # Cấu hình
    ├── batch-config.yaml             # Cấu hình chính (68 dòng)
    └── mask-config.yaml              # Thông số mặt nạ (TBD)
```

### Biểu đồ phụ thuộc

```
batch-production-main.py (điểm vào)
    ├─ BatchJobScheduler
    │   └─ load_config()
    ├─ ComfyUIClient
    │   └─ thư viện requests
    ├─ MaskPrefetcher
    │   ├─ ThreadPoolExecutor
    │   └─ get_generator(defect_type)
    │       ├─ CrackMaskGenerator
    │       ├─ PorosityMaskGenerator
    │       ├─ SlagInclusionMaskGenerator
    │       ├─ LackOfFusionMaskGenerator
    │       └─ UndercutMaskGenerator
    ├─ GPUThermalMonitor
    │   └─ nvidia-smi (tiến trình con)
    └─ CheckpointManager
        └─ tuần tự hóa JSON

post-processing-main.py (điểm vào)
    ├─ MaskToAnnotationConverter
    │   └─ cv2, numpy
    ├─ COCODatasetBuilder
    │   └─ pycocotools (tùy chọn)
    ├─ YOLODatasetBuilder
    │   └─ yaml
    └─ DatasetSplitter
        └─ random, numpy

qa-pipeline-main.py (điểm vào)
    ├─ SSIMBackgroundChecker
    │   └─ scikit-image
    ├─ AnnotationValidator
    │   └─ pycocotools, yaml
    └─ VisualSpotCheckGallery
        └─ PIL, numpy

validation-main.py (điểm vào)
    ├─ YOLOv8Trainer
    │   └─ ultralytics (YOLOv8)
    └─ EvaluationMetrics
        └─ numpy, pandas
```

---

## Cấu trúc dữ liệu

### Định nghĩa công việc (Bộ lập lịch)

```python
Job = {
    "job_id": int,                          # ID tăng dần duy nhất
    "defect_type": str,                     # crack|porosity|inclusion|lof|undercut
    "seed": int,                            # Hạt giống ngẫu nhiên để có thể tái tạo
    "background_image": Path,               # Đường dẫn đến PNG nền
    "lora_model": str,                      # Tên tệp LoRA (ví dụ: xray_crack_lora_r32.safetensors)
}
```

### Trạng thái điểm kiểm tra

```python
Checkpoint = {
    "job_id": int,                          # Công việc hoàn thành cuối cùng
    "timestamp": str,                       # Dấu thời gian định dạng ISO
    "defect_counts": {                      # Số lượng tích lũy
        "crack": int,
        "porosity": int,
        "inclusion": int,
        "lack_of_fusion": int,
        "undercut": int,
    }
}
```

### Chú thích COCO

```python
COCOAnnotation = {
    "id": int,
    "image_id": int,
    "category_id": int,                     # 1=crack, 2=porosity, v.v.
    "bbox": [x, y, width, height],          # Trên cùng bên trái + kích thước
    "area": float,                          # width * height
    "segmentation": [                       # Các đỉnh đa giác
        [x1, y1, x2, y2, x3, y3, ...]
    ],
    "iscrowd": 0
}
```

### Nhãn YOLO

```
<class_id> <x_center_norm> <y_center_norm> <width_norm> <height_norm>
# Ví dụ: 0 0.5 0.5 0.2 0.3  (lớp 0, tâm ở 50%, chiều rộng 20%)
```

---

## Xử lý lỗi & Phục hồi

### Chiến lược chịu lỗi

```
┌─ Lỗi tạo hình ảnh
│  ├─ Thử lại tối đa 3 lần (với độ trễ 5 giây)
│  ├─ Ghi lại cảnh báo nếu tất cả các lần thử lại đều thất bại
│  └─ Tiếp tục công việc tiếp theo (không hủy bỏ)
│
├─ Không thể truy cập API ComfyUI
│  ├─ Kiểm tra kết nối khi khởi động (verify-comfyui-setup.py)
│  ├─ Thử lại khi có lỗi tạm thời (ConnectionError)
│  ├─ Cảnh báo nếu kéo dài (ghi log CRITICAL)
│  └─ Hỗ trợ khởi động lại thủ công nếu cần
│
├─ Điều tiết nhiệt GPU
│  ├─ Giám sát mỗi 30 giây
│  ├─ Tạm dừng tạo nếu nhiệt độ > 85°C
│  ├─ Tiếp tục khi nhiệt độ < 75°C (trễ)
│  └─ Ghi lại các sự kiện tạm dừng/tiếp tục
│
└─ Sự cố sản xuất hàng loạt
   ├─ Lưu điểm kiểm tra mỗi 100 hình ảnh
   ├─ Khi khởi động lại, tự động tiếp tục từ điểm kiểm tra
   ├─ Xác minh tính toàn vẹn của tệp điểm kiểm tra (JSON)
   └─ Khởi động lại ComfyUI nếu cần
```

### Điểm kiểm tra & Phục hồi

```
Thực thi bình thường:
┌─ Công việc 0
├─ Công việc 1
├─ ...
└─ [ĐIỂM KIỂM TRA] Công việc 99 (lưu vào checkpoint.json)
   ├─ Công việc 100
   ├─ ...
   └─ [ĐIỂM KIỂM TRA] Công việc 199
      ...

Khi gặp sự cố ở Công việc 145:
├─ Khởi động lại thủ công: python batch-production-main.py ...
├─ Tự động tải điểm kiểm tra (Công việc 99 đã hoàn thành)
├─ Tiếp tục từ Công việc 100
├─ Tiếp tục bình thường
```

---

## Đặc tính hiệu suất

### Sản xuất hàng loạt (Giai đoạn 6)

| Thành phần | Thông lượng | Nút cổ chai |
|-----------|-----------|-----------|
| Tạo mặt nạ | ~100 mặt nạ/giây | CPU (không giới hạn) |
| Tạo GPU | ~1,097 hình/giờ | GPU (RTX 3090) |
| Bộ đệm tìm nạp trước | Điền trước 50 mặt nạ | Trước GPU |
| Ghi điểm kiểm tra | <100ms mỗi 100 hình ảnh | Không đáng kể |
| **Từ đầu đến cuối** | **~1,097 hình/giờ** | **GPU** |

**Đối với 20K hình ảnh**:
- Tổng thời gian: 20,000 ÷ 1,097 ≈ 18.2 giờ
- Điểm kiểm tra: 200 (mỗi 100 hình ảnh)
- Lưu trữ: ~25 GB (PNG 8-bit, nén mất dữ liệu)

### Xử lý hậu kỳ (Giai đoạn 7)

| Thành phần | Thông lượng | Thời gian cho 20K |
|-----------|-----------|-----------|
| Mặt nạ→Chú thích | ~450 hình/giây | ~45 giây |
| Xây dựng COCO JSON | Không đáng kể | <5 giây |
| Ghi YOLO TXT | ~500 nhãn/giây | ~40 giây |
| Siêu dữ liệu phân chia | ~1000 hoạt động/giây | <5 giây |
| **Tổng cộng** | - | **~2 phút** |

### Đảm bảo chất lượng (Giai đoạn 8)

| Thành phần | Thông lượng | Kích thước mẫu | Thời gian |
|-----------|-----------|-----------|------|
| Kiểm tra SSIM | ~1 hình/giây | 500 hình ảnh | ~8 phút |
| Xác thực chú thích | ~100K chú thích/giây | Tất cả (~20K chú thích) | <1 giây |
| Phân tích phân phối | ~500K hoạt động/giây | Số lượng mỗi loại | <1 giây |
| Thư viện kiểm tra tại chỗ | ~10 hình/giây | 200-400 hình ảnh | ~30 giây |
| **Tổng cộng** | - | - | **~9-10 phút** |

### Xác thực (Giai đoạn 9)

| Thành phần | Số lượng | Thời gian mỗi thử nghiệm | Ghi chú |
|-----------|-------|-----------|-------|
| Huấn luyện YOLOv8 | 100 epoch | ~1.2 giờ | 50 epoch/giờ trên RTX 3090 |
| Đánh giá | Mỗi mô hình | ~30 giây | Suy luận nhanh trên tập kiểm tra |
| Tạo báo cáo | Thống kê tóm tắt | ~10 giây | Tổng hợp & vẽ đồ thị |
| **Tổng cộng cho 4 thử nghiệm** | - | **~4.8 giờ** | Tuần tự |

---

## Khả năng mở rộng & Hạn chế

### Phần cứng hiện tại

```
Phần cứng: Dual Xeon E5-2696v4 + RTX 3090 24GB + 64GB ECC
Ràng buộc:
  - Một GPU (không có DDP)
  - ~18GB VRAM có sẵn để suy luận
  - 8 worker CPU để tạo mặt nạ (bão hòa CPU)
```

### Tùy chọn mở rộng (Tương lai)

1. **Xử lý hàng loạt đa GPU**
   - Phân phối công việc trên nhiều GPU
   - Chia sẻ trạng thái điểm kiểm tra qua mạng
   - Yêu cầu bộ lập lịch nhận biết DDP

2. **Mô hình lớn hơn**
   - SDXL thay vì SD 1.5 (chất lượng cao hơn)
   - Yêu cầu VRAM 48GB+
   - Sẽ cần GPU A100/H100

3. **Kỹ thuật LoRA nâng cao**
   - Hợp nhất nhiều LoRA (trộn nhiều loại khuyết tật)
   - Lycoris (LoRA mở rộng) để có chất lượng tốt hơn
   - Yêu cầu huấn luyện lại (Giai đoạn 3)

4. **Suy luận nhanh hơn**
   - Giảm số bước khuếch tán (15 thay vì 20)
   - Bộ mã hóa VAE được chưng cất
   - Sẽ yêu cầu xác thực chất lượng

### Yêu cầu lưu trữ

```
Đầu ra Giai đoạn 6 (20K hình ảnh):
  - Hình ảnh PNG (512×512, 8-bit): ~3 byte/pixel × 262K pixel = 786 KB/hình ảnh
  - 20K hình ảnh × 786 KB = ~15.7 GB
  - Mặt nạ nhị phân: ~250 KB/hình ảnh = ~5 GB
  - Siêu dữ liệu JSON: ~1 KB/hình ảnh = ~20 MB
  Tổng cộng: ~20-25 GB (với nén)

Đầu ra Giai đoạn 7 (Chú thích):
  - COCO JSON: ~50-100 MB
  - Tệp YOLO TXT: ~5 MB
  - Bản sao của hình ảnh: ~15.7 GB
  Tổng cộng: ~16 GB

Tích lũy:
  - Thô tổng hợp: ~20-25 GB
  - Tập dữ liệu có chú thích: ~16 GB
  - Báo cáo QA: ~50 MB
  - Kết quả xác thực: ~100 MB
  Tổng cộng: ~36-41 GB cho 20K hình ảnh
```

---

## Điểm tích hợp

### API bên ngoài

```
API REST ComfyUI
  ├─ Điểm cuối: http://172.21.192.1:8188/api/
  ├─ Giao thức: HTTP JSON RPC
  ├─ Xác thực: Không có (mạng cục bộ)
  ├─ Độ trễ: <100ms (cục bộ)
  └─ Được sử dụng bởi: ComfyUIClient
```

### Hệ thống tệp

```
Đầu vào:
  └─ /mnt/e/The Data Mint/kohya-ss/training_data/reg/1_xray_clean/
     (hình ảnh nền, ~100 tệp PNG)

Đầu ra:
  ├─ /mnt/e/The Data Mint/output/synthetic/{defect_type}/
  │  ├─ {defect}_{id}.png (hình ảnh)
  │  ├─ {defect}_{id}_mask.png (mặt nạ)
  │  └─ {defect}_{id}.json (siêu dữ liệu)
  ├─ /mnt/e/The Data Mint/output/dataset/
  │  ├─ annotations/ (COCO JSON)
  │  └─ yolo/ (định dạng YOLO)
  ├─ /mnt/e/The Data Mint/output/qa-reports/
  │  └─ *.md, *.json, *.html
  └─ /mnt/e/The Data Mint/output/validation/
     └─ *.md, *.json, weights/
```

### Ghi log

```
Log:
  ├─ /mnt/e/The Data Mint/pipeline/logs/batch-production-*.log
  │  (Giai đoạn 6, điều phối chính)
  ├─ /mnt/e/The Data Mint/output/dataset/post-processing-report.txt
  │  (Giai đoạn 7, chuyển đổi chú thích)
  ├─ /mnt/e/The Data Mint/output/qa-reports/qa-report.md
  │  (Giai đoạn 8, kiểm tra chất lượng)
  └─ /mnt/e/The Data Mint/output/validation/validation-report.md
     (Giai đoạn 9, kết quả YOLOv8)
```

---

## Giám sát & Khả năng quan sát

### Chỉ số chính

**Trong quá trình tạo (Giai đoạn 6)**:
```
- Hình ảnh/giờ (thông lượng)
- % sử dụng GPU
- Nhiệt độ GPU (°C)
- Mức sử dụng bộ nhớ (VRAM)
- Khoảng thời gian điểm kiểm tra (100 hình ảnh)
- Tỷ lệ thử lại (hình ảnh thất bại/tổng số)
```

**Trong quá trình QA (Giai đoạn 8)**:
```
- SSIM trung bình & độ lệch chuẩn
- % tỷ lệ đạt
- Lỗi chú thích
- % độ lệch phân phối
- % tỷ lệ đạt kiểm tra tại chỗ
```

**Trong quá trình xác thực (Giai đoạn 9)**:
```
- mAP@0.5 mỗi thử nghiệm
- mAP@0.5:0.95 mỗi thử nghiệm
- Độ chính xác/độ thu hồi mỗi lớp
- Đường cong tổn thất huấn luyện
- Tốc độ suy luận (hình/giây)
```

### Cấp độ ghi log

```
DEBUG   - Luồng chi tiết (tìm nạp trước mặt nạ, gọi API)
INFO    - Tiến độ (đạt điểm kiểm tra, bắt đầu giai đoạn)
WARNING - Các vấn đề có thể phục hồi (SSIM thấp, thử lại)
ERROR   - Lỗi không nghiêm trọng (tạo hình ảnh thất bại, thử lại)
CRITICAL- Tình trạng nghiêm trọng (không thể truy cập API, hủy bỏ)
```

---

## Chiến lược kiểm tra

### Kiểm tra đơn vị

```
batch_manager/
  ├─ test_batch_job_scheduler.py
  │  └─ Tính công bằng của phân phối, thứ tự công việc
  ├─ test_comfyui_client.py
  │  └─ Giả lập API, xử lý lời nhắc
  └─ test_checkpoint_manager.py
     └─ Lưu/tải, tính toàn vẹn

mask_generator/
  ├─ test_mask_generators.py
  │  └─ Xác thực hình dạng, ràng buộc ROI
  └─ test_feathering.py
     └─ Làm mịn cạnh
```

### Kiểm tra tích hợp

```
test_batch_production_pilot.py
  ├─ Tạo 5 hình ảnh kiểm tra (1 cho mỗi khuyết tật)
  ├─ Xác minh cấu trúc đầu ra
  ├─ Xác thực siêu dữ liệu
  └─ Kiểm tra phục hồi điểm kiểm tra

test_post_processing_pipeline.py
  ├─ Chuyển đổi mặt nạ thành COCO/YOLO
  ├─ Xác minh tính hợp lệ của JSON (pycocotools)
  ├─ Kiểm tra tỷ lệ phân chia
  └─ Xác thực định dạng nhãn

test_qa_pipeline.py
  ├─ Tính toán SSIM
  ├─ Xác thực chú thích
  └─ Tạo thư viện

test_validation_pipeline.py
  ├─ Huấn luyện YOLOv8 (tập dữ liệu đồ chơi)
  ├─ Trích xuất chỉ số
  └─ Logic so sánh
```

---

## Cân nhắc bảo mật

### Xử lý dữ liệu

```
✓ Không có PII (tất cả dữ liệu tổng hợp)
✓ Không lưu trữ thông tin xác thực trong mã (sử dụng .env)
✓ Không có khóa API trong git (thêm vào .gitignore)
✓ Quyền tệp: 0644 cho đầu ra

Tệp nhạy cảm:
  .env (Khóa API ComfyUI nếu được thêm sau)
  checkpoint-state.json (trạng thái tiến độ)
```

### Lưu trữ mô hình

```
Mô hình LoRA:
  - Được lưu trữ tại /mnt/e/The Data Mint/kohya-ss/output/
  - Tổng cộng ~185 MB (5 mô hình × 37 MB)
  - Kiểm tra tính toàn vẹn trước khi tải (tùy chọn)
  - Kiểm soát phiên bản bằng Git LFS (nếu cần)
```

---

**Cập nhật lần cuối**: 2026-01-31
**Phiên bản**: 1.0
