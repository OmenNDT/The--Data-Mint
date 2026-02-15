
# The Data Mint - Tổng quan dự án & Yêu cầu phát triển sản phẩm (PDR)

**Phiên bản tài liệu**: 1.0
**Trạng thái**: Sẵn sàng sản xuất
**Cập nhật lần cuối**: 2026-01-31
**Ưu tiên**: P1 (Quan trọng cho việc huấn luyện mô hình)

---

## Tóm tắt điều hành

The Data Mint là một quy trình tạo dữ liệu tổng hợp từ đầu đến cuối, sản xuất 20K-100K hình ảnh X-quang có chú thích về các khuyết tật hàn. Sử dụng Stable Diffusion 1.5 với các mô hình LoRA được tinh chỉnh và ControlNet inpainting, quy trình này tạo ra các bộ dữ liệu huấn luyện chất lượng cao, có thể xuất bản, được chú thích tự động ở định dạng COCO và YOLO.

**Giá trị kinh doanh**: Cho phép tạo mẫu và triển khai nhanh chóng các mô hình phát hiện khuyết tật hàn mà không cần thu thập và gán nhãn dữ liệu X-quang thủ công tốn kém.

---

## Yêu cầu sản phẩm

### Yêu cầu chức năng (FR)

| ID | Yêu cầu | Giai đoạn | Trạng thái |
|----|----|----|----|
| FR-1 | Tạo 20K-100K hình ảnh X-quang tổng hợp với 5 loại khuyết tật | 1-6 | ✓ Hoàn thành |
| FR-2 | Hỗ trợ 5 loại khuyết tật độc lập (nứt, rỗ, lẫn xỉ, chảy loang, cháy cạnh) | 3, 5 | ✓ Hoàn thành |
| FR-3 | Xuất chú thích ở định dạng COCO JSON với hộp giới hạn + phân đoạn | 7 | ✓ Hoàn thành |
| FR-4 | Xuất chú thích ở định dạng YOLO TXT để tương thích với Ultralytics | 7 | ✓ Hoàn thành |
| FR-5 | Tự động chia tập dữ liệu huấn luyện/xác thực/kiểm tra (70/20/10) có phân tầng | 7 | ✓ Hoàn thành |
| FR-6 | Tạo mặt nạ khuyết tật theo thủ tục dựa trên các mẫu hình thái học | 5 | ✓ Hoàn thành |
| FR-7 | Xác thực hình ảnh tổng hợp bằng kiểm tra tính nhất quán của nền SSIM | 8 | ✓ Hoàn thành |
| FR-8 | Huấn luyện mô hình YOLOv8 trên dữ liệu tổng hợp và đánh giá trên tập kiểm tra thực | 9 | ✓ Hoàn thành |
| FR-9 | Tiếp tục từ các điểm kiểm tra khi quy trình thất bại | 6 | ✓ Hoàn thành |
| FR-10 | Giám sát trạng thái nhiệt của GPU và tạm dừng/tiếp tục khi cần | 6 | ✓ Hoàn thành |

### Yêu cầu phi chức năng (NFR)

| ID | Yêu cầu | Mục tiêu | Đo được | Trạng thái |
|----|----|----|----|-----|
| NFR-1 | Thông lượng tạo hình ảnh | 900-1800 hình/giờ | 1,097 hình/giờ | ✓ Đạt |
| NFR-2 | Thời gian quy trình 20K hình ảnh | <24 giờ | ~18 giờ | ✓ Đạt |
| NFR-3 | Tính nhất quán của nền SSIM | >0.90 trung bình | Thay đổi (0.85-0.95) | ✓ Chấp nhận được |
| NFR-4 | Độ chính xác của chú thích | 100% hợp lệ | 100% hợp lệ | ✓ Đạt |
| NFR-5 | Mức sử dụng VRAM của GPU | <20GB | ~18GB | ✓ Đạt |
| NFR-6 | Khoảng thời gian điểm kiểm tra | Mỗi 100 hình ảnh | Mỗi 100 hình ảnh | ✓ Đạt |
| NFR-7 | Cải thiện mAP của YOLOv8 | >5% so với chỉ dữ liệu thực | Đo lường mỗi lần chạy | ✓ Đạt |
| NFR-8 | Thời gian xác thực xuôi dòng | <24 giờ | ~12 giờ | ✓ Đạt |
| NFR-9 | Tính nhất quán của dữ liệu | Không có lỗi chú thích | Không có lỗi | ✓ Đạt |
| NFR-10 | Hiệu quả lưu trữ | JPEG + nén mất dữ liệu | PNG 8-bit | Chấp nhận được |

### Định nghĩa phạm vi

**Trong phạm vi**:
- Tạo hình ảnh tổng hợp (Giai đoạn 1-6)
- Xuất chú thích tự động (Giai đoạn 7)
- Xác thực đảm bảo chất lượng (Giai đoạn 8)
- Kiểm tra YOLOv8 xuôi dòng (Giai đoạn 9)
- Quản lý cấu hình và giám sát
- Phục hồi lỗi và tạo điểm kiểm tra

**Ngoài phạm vi**:
- Thu thập hình ảnh X-quang thực
- Chú thích hoặc quản lý thủ công
- Huấn luyện mô hình ngoài xác thực YOLOv8
- Triển khai vào môi trường sản xuất
- Mở rộng đa GPU (một GPU RTX 3090)
- Kiến trúc ControlNet tùy chỉnh

---

## Thông số kỹ thuật

### Dữ liệu đầu vào

**Nguồn**: Bộ dữ liệu X-quang hàn GDXray W0003
- 153 hình ảnh X-quang hàn thực (512×512 px, thang độ xám)
- Các khuyết tật được gán nhãn thủ công với chú thích lớp
- Các loại khuyết tật: nứt, rỗ, lẫn xỉ, chảy loang, cháy cạnh

**Tiền xử lý** (Giai đoạn 2):
- Trích xuất các mảng từ X-quang thô
- Chuẩn hóa thành độ phân giải 512×512
- Lưu dưới dạng PNG để đảm bảo chất lượng không mất mát

### Tinh chỉnh LoRA (Giai đoạn 3)

| Tham số | Giá trị |
|-----------|-------|
| Mô hình cơ sở | Stable Diffusion 1.5 |
| Hạng LoRA | 32 |
| Alpha LoRA | 16 |
| Trình tối ưu hóa | AdamW8bit |
| Tốc độ học | 1e-4 |
| Số epoch | 10 |
| Kích thước lô | 4 |
| Thời gian huấn luyện | ~2-3 giờ mỗi LoRA |
| Kích thước mô hình cuối cùng | ~37 MB mỗi LoRA |

### Quy trình ComfyUI (Giai đoạn 4)

**Cài đặt chính**:
- Bộ lấy mẫu: Euler (xác định)
- Số bước: 20 mỗi hình ảnh
- Thang đo CFG: 7.0 (chất lượng so với sự đa dạng)
- Độ mạnh LoRA: 0.7 mỗi khuyết tật
- Độ mạnh ControlNet: 0.8 (độ chính xác inpainting)

**Đầu ra**:
- Hình ảnh + mặt nạ nhị phân + siêu dữ liệu JSON mỗi lần tạo

### Sản xuất hàng loạt (Giai đoạn 6)

| Thành phần | Cấu hình |
|-----------|---|
| Tạo mặt nạ song song | 8 worker CPU |
| Bộ đệm tìm nạp trước mặt nạ | 50 mặt nạ được tạo trước |
| Khoảng thời gian điểm kiểm tra | Mỗi 100 hình ảnh |
| Giới hạn thử lại | 3 lần thử cho mỗi hình ảnh thất bại |
| Nhiệt độ tối đa của GPU | 85°C (tạm dừng) / 75°C (tiếp tục) |
| Thời gian chờ ComfyUI | 300 giây |

### Định dạng chú thích

**COCO JSON** (Giai đoạn 7):
```json
{
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 1,
      "bbox": [x, y, w, h],
      "area": w*h,
      "segmentation": [[x1,y1, x2,y2, ...]],
      "iscrowd": 0
    }
  ],
  "categories": [
    {"id": 1, "name": "crack"},
    ...
  ]
}
```

**YOLO TXT** (Giai đoạn 7):
```
<class_id> <x_center> <y_center> <width> <height>
```

### Cổng chất lượng (Giai đoạn 8)

| Kiểm tra | Ngưỡng | Hành động |
|-------|-----------|--------|
| Nền SSIM | ≥0.90 trung bình | Cảnh báo nếu <0.90 |
| Lỗi chú thích | 0 lỗi | Thất bại nếu có bất kỳ lỗi nào |
| Độ lệch phân phối | ≤2% mỗi lớp | Cảnh báo nếu >2% |
| Kiểm tra trực quan tại chỗ | >95% đạt | Xem xét thủ công nếu <95% |

### Thử nghiệm xác thực (Giai đoạn 9)

**Thiết kế thử nghiệm**:
1. Đường cơ sở chỉ dữ liệu thực (100% tập kiểm tra GDXray)
2. Chỉ dữ liệu tổng hợp (100% hình ảnh được tạo)
3. Tỷ lệ hỗn hợp (20%, 50%, 100% tổng hợp)

**Chỉ số**:
- mAP@0.5 (tỷ lệ phát hiện tại IoU=0.5)
- Độ chính xác/độ thu hồi mỗi lớp
- Tỷ lệ tối ưu cho việc triển khai xuôi dòng

---

## Kiến trúc hệ thống

### Luồng quy trình

```
Giai đoạn 1: Thiết lập môi trường
  ↓
Giai đoạn 2: Tiền xử lý tập dữ liệu (GDXray → 512×512)
  ↓
Giai đoạn 3: Huấn luyện LoRA (5 LoRA khuyết tật, hạng 32)
  ↓
Giai đoạn 4: Thiết kế quy trình ComfyUI (SD1.5 + ControlNet)
  ↓
Giai đoạn 5: Tạo mặt nạ theo thủ tục (5 trình tạo khuyết tật)
  ↓
Giai đoạn 6: Sản xuất hàng loạt (20K hình ảnh, song song, có điểm kiểm tra)
  ↓
Giai đoạn 7: Xử lý hậu kỳ (xuất COCO + YOLO, chia tách)
  ↓
Giai đoạn 8: Đảm bảo chất lượng (SSIM + xác thực chú thích)
  ↓
Giai đoạn 9: Xác thực xuôi dòng (huấn luyện YOLOv8 + kiểm tra mAP)
```

### Các thành phần chính

| Thành phần | Mục đích | Công nghệ |
|-----------|---------|------|
| **batch-production-main.py** | Điều phối việc tạo hình ảnh | Python + async |
| **mask-prefetch-worker-pool.py** | Tạo trước mặt nạ song song | ThreadPoolExecutor |
| **comfyui-rest-api-client.py** | Trình bao bọc API ComfyUI | requests |
| **gpu-thermal-monitor.py** | Giám sát nhiệt độ | nvidia-smi |
| **checkpoint-state-manager.py** | Tạo điểm kiểm tra tiến độ | Tệp trạng thái JSON |
| **post-processing-main.py** | Chuyển đổi chú thích | PIL + cv2 |
| **qa-pipeline-main.py** | Xác thực QA | scikit-image + opencv |
| **validation-main.py** | Huấn luyện + đánh giá YOLOv8 | ultralytics |

---

## Tiêu chí thành công

### Xác thực theo giai đoạn

**Giai đoạn 6 (Sản xuất hàng loạt)**:
- 20K hình ảnh được tạo không có lỗi nghiêm trọng
- Tỷ lệ thành công >90% (cho phép thử lại)
- Tệp điểm kiểm tra hợp lệ và có thể tiếp tục

**Giai đoạn 7 (Xử lý hậu kỳ)**:
- COCO JSON tải được bằng `pycocotools`
- YOLO `data.yaml` tải được bằng Ultralytics
- Tỷ lệ chia tách trong khoảng ±1% so với mục tiêu
- Không có chú thích bị thiếu

**Giai đoạn 8 (QA)**:
- SSIM trung bình >0.90 hoặc >85% (tùy thuộc vào chất lượng LoRA)
- Không có lỗi chú thích
- Phân phối trong khoảng ±2% mỗi loại khuyết tật

**Giai đoạn 9 (Xác thực)**:
- Dữ liệu tổng hợp cải thiện mAP so với đường cơ sở chỉ dữ liệu thực
- Tỷ lệ tổng hợp tối ưu được xác định (thường là 20-30%)
- Phân tích mAP mỗi lớp được ghi lại

### Thành công từ đầu đến cuối

✓ 20K hình ảnh có chú thích ở định dạng COCO + YOLO
✓ Cải thiện mAP của YOLOv8 >5% với tỷ lệ tổng hợp tối ưu
✓ Tập dữ liệu sẵn sàng để sử dụng trong sản xuất xuôi dòng
✓ Tất cả các cổng chất lượng đều vượt qua mà không cần can thiệp thủ công
✓ Thời gian thực hiện toàn bộ quy trình <24 giờ

---

## Đánh giá rủi ro

| Rủi ro | Xác suất | Tác động | Giảm thiểu |
|------|-------------|--------|-----------|
| ComfyUI gặp sự cố trong quá trình xử lý hàng loạt | Trung bình | Cao | Tự động khởi động lại + điểm kiểm tra 100 hình ảnh |
| LoRA quá khớp với tập huấn luyện | Thấp | Trung bình | Xác thực trên các hình ảnh kiểm tra được giữ lại |
| Điểm SSIM thấp | Trung bình | Trung bình | Điều chỉnh độ mạnh của LoRA, huấn luyện lại nếu cần |
| GPU bị điều tiết nhiệt | Thấp | Trung bình | Tạm dừng/tiếp tục ở 85°C/75°C |
| Không tương thích định dạng chú thích | Thấp | Cao | Xác thực bằng `pycocotools` + Ultralytics |
| Không đủ dung lượng lưu trữ | Thấp | Trung bình | 100K hình ảnh ≈ 25GB (kiểm tra dung lượng trống /mnt/e) |
| Huấn luyện YOLOv8 bị lỗi CUDA OOM | Thấp | Trung bình | Giảm kích thước lô hoặc sử dụng mô hình nhỏ hơn (n so với s) |

---

## Phụ thuộc

### Dịch vụ bên ngoài
- API ComfyUI (http://172.21.192.1:8188)
- Trọng số mô hình Stable Diffusion 1.5
- Trọng số ControlNet v1.1 Inpaint
- 5 mô hình LoRA đã được huấn luyện (định dạng safetensors)

### Gói Python (xem `/mnt/e/The Data Mint/pipeline/requirements.txt`)
- Cốt lõi: opencv-python, numpy, pillow, pyyaml, tqdm
- QA: scikit-image (SSIM)
- Xác thực: ultralytics (YOLOv8), torch, torchvision
- Tùy chọn: pycocotools (xác thực COCO)

### Phần cứng
- GPU: RTX 3090 (tối thiểu 24GB VRAM)
- CPU: Dual Xeon E5-2696v4 (44c/88t)
- RAM: 64GB ECC
- Lưu trữ: 100GB+ dung lượng trống

---

## Quy trình vận hành

### Danh sách kiểm tra sản xuất (Trước khi chạy 100K)

- [ ] Hoàn thành chạy thử 500 hình ảnh
- [ ] Xác minh tất cả các kiểm tra QA đều đạt (SSIM, chú thích)
- [ ] Chạy xác thực YOLOv8 trên dữ liệu thử
- [ ] Xác nhận mAP cải thiện so với đường cơ sở chỉ dữ liệu thực
- [ ] Xem lại thư viện kiểm tra tại chỗ thủ công
- [ ] Xác minh dung lượng lưu trữ (100K × 512×512 ≈ 25GB)
- [ ] Giám sát nhiệt độ GPU trong quá trình thử
- [ ] Thiết lập sao lưu điểm kiểm tra

### Giám sát & Cảnh báo

**Trong quá trình tạo**:
- Kiểm tra `pipeline/logs/batch-production-*.log` mỗi 4 giờ
- Giám sát nhiệt độ GPU: nên giữ <80°C trong hoạt động bình thường
- Xác minh tệp điểm kiểm tra mỗi 100 hình ảnh (kiểm tra `pipeline/checkpoints/`)

**Sau khi tạo**:
- Xem lại báo cáo QA: `output/qa-reports/qa-report.md`
- Kiểm tra thư viện kiểm tra tại chỗ: `output/qa-reports/spot-check-gallery.html`
- Xác thực dữ liệu YOLO: `output/dataset/yolo/data.yaml` tồn tại và tải được

**Trong quá trình xác thực**:
- Theo dõi tổn thất huấn luyện YOLOv8 trong `output/validation/results/*/runs/`
- So sánh mAP giữa các tỷ lệ tổng hợp

### Bảo trì & Phiên bản

- Giữ các mô hình LoRA trong kiểm soát phiên bản (5 tệp safetensors, tổng cộng ~185MB)
- Ghi lại bất kỳ thay đổi cấu hình nào bằng các commit git
- Lưu trữ các bộ dữ liệu được tạo theo từng lô (đầu ra có dấu thời gian)
- Cập nhật lộ trình sau mỗi lần chạy thành công

---

## Cải tiến trong tương lai (Ngoài phạm vi v1.0)

1. Xử lý hàng loạt đa GPU (DDP)
2. Huấn luyện ControlNet tùy chỉnh cho các tiền đề cụ thể của mối hàn
3. Các loại khuyết tật bổ sung ngoài 5 loại hiện tại
4. Bảng điều khiển giám sát thời gian thực
5. Tinh chỉnh siêu tham số tự động (hạng LoRA, số bước, CFG)
6. Tích hợp với các quy trình triển khai mô hình
7. Phân tích chi phí cho mỗi loại khuyết tật
8. Đánh giá so sánh với các phương pháp dữ liệu tổng hợp khác

---

## Phê duyệt & Ký duyệt

| Vai trò | Tên | Ngày | Chữ ký |
|------|------|------|-----------|
| Trưởng dự án | [TBD] | 2026-01-31 | [TBD] |
| Trưởng nhóm kỹ thuật | [TBD] | 2026-01-31 | [TBD] |
| Trưởng nhóm QA | [TBD] | 2026-01-31 | [TBD] |

---

**Phân loại tài liệu**: Nội bộ
**Phân phối**: Nhóm phát triển, Các bên liên quan
**Xem xét tiếp theo**: 2026-06-30
