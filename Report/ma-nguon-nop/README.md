# The Data Mint — Mã nguồn đồ án

Hệ thống sinh ảnh X-quang mối hàn tổng hợp có chú thích tự động, dùng Stable Diffusion 1.5 và LoRA.

**Đồ án môn học Máy học nâng cao** — Cử nhân ngành Trí tuệ nhân tạo, Trường Đại học Công nghệ Thông tin, ĐHQG-HCM.

| | |
|---|---|
| GVHD | ThS. Đặng Việt Dũng |
| Sinh viên | Trương Ngọc Sơn (25210183), Trần Tín Nghĩa (25210147), Hồ Thị Mỹ Phương (25210170) |
| Báo cáo | `Do-an-The-Data-Mint.docx` nộp kèm |

---

## 1. Thư mục này chứa gì

Chỉ có mã nguồn và vài tệp mẫu. Bộ dữ liệu, mô hình nền, mô hình LoRA và ảnh sinh ra không kèm theo vì dung lượng lớn (khoảng 145 GB).

```
ma-nguon-nop/
├── README.md                  tệp này
├── requirements.txt           phụ thuộc Python
├── mau-ket-qua/               vài ảnh mẫu và tệp chú thích mẫu
└── pipeline/
    ├── launcher/              giao diện vận hành Gradio, điều phối giai đoạn
    ├── mask_generator/        mười hai lớp sinh mặt nạ theo thủ tục
    ├── batch_manager/         điều phối sinh ảnh hàng loạt, chịu lỗi, giám sát nhiệt
    ├── benchmark/             so sánh sáu mô hình nền
    ├── qa/                    năm cổng kiểm định chất lượng
    ├── post_processing/       xuất COCO, YOLO, chia tập 70/20/10
    ├── auto_labeler/          gán nhãn bán tự động cho ảnh thật
    ├── validation/            huấn luyện và đánh giá YOLOv8
    ├── tests/                 kiểm thử đơn vị
    ├── scripts/               tiện ích dòng lệnh
    ├── tools/                 công cụ phụ trợ
    ├── comfyui-workflows/     đồ thị nút JSON và mẫu lời nhắc theo lớp
    ├── config/                cấu hình lô sản xuất và cấu hình mặt nạ
    └── *.py, run-*.sh         các script chạy trực tiếp
```

## 2. Quy mô mã nguồn

Đếm tại thời điểm đóng gói, không tính dòng trống hay chú thích riêng.

| Mô-đun | Tệp Python | Dòng mã | Vai trò |
|---|---:|---:|---|
| launcher | 22 | 6.271 | Giao diện vận hành và điều phối |
| mask_generator | 16 | 1.809 | Sinh mặt nạ theo thủ tục |
| batch_manager | 9 | 1.788 | Điều phối sinh ảnh hàng loạt |
| benchmark | 10 | 1.738 | So sánh mô hình nền |
| qa | 5 | 1.059 | Đảm bảo chất lượng |
| post_processing | 6 | 916 | Chuyển đổi chú thích và chia tập |
| auto_labeler | 6 | 914 | Gán nhãn bán tự động ảnh thật |
| tests | 5 | 826 | Kiểm thử |
| validation | 4 | 812 | Huấn luyện và đánh giá YOLOv8 |
| scripts | 1 | 484 | Tiện ích dòng lệnh |
| tools | 1 | 232 | Công cụ phụ trợ |
| **Cộng 11 mô-đun** | **85** | **16.849** | |
| Script rời ở gốc `pipeline/` | 6 | 1.349 | Chạy thử và kiểm tra thiết lập |
| **Tổng** | **91** | **18.198** | |

Con số trong Bảng 3.10 của báo cáo là 18.158 dòng, đo trước khi nộp. Chênh 40 dòng đến từ hai lần sửa sau đó ở `launcher` (+12) và `batch_manager` (+28).

## 3. Yêu cầu môi trường

| Hạng mục | Cấu hình đã kiểm chứng |
|---|---|
| Hệ điều hành | Linux |
| Python | 3.12 |
| GPU | NVIDIA RTX 3090, 24 GB VRAM (bước sinh ảnh cần khoảng 18 GB) |
| CPU | Hai Intel Xeon E5-2696 v4, 88 luồng (bước sinh mặt nạ chạy song song trên CPU) |
| RAM | 64 GB |
| Máy chủ khuếch tán | ComfyUI, bật REST API ở `127.0.0.1:8188` |
| Huấn luyện LoRA | kohya-ss, cấu hình TOML sinh tự động |

Thành phần bên ngoài phải chuẩn bị riêng, không kèm trong thư mục này:

- ComfyUI, kèm mô hình nền Stable Diffusion 1.5 và ControlNet `control_v11p_sd15_inpaint`.
- Mười hai mô hình LoRA đã huấn luyện, mỗi tệp khoảng 37 MB.
- Bộ dữ liệu GDXray W0003 đã cắt patch 512 × 512 và tập nền sạch.

## 4. Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Các gói tuỳ chọn ghi ở cuối `requirements.txt` chỉ cần khi chạy mô-đun tương ứng: `pycocotools` cho kiểm tra tệp COCO, `ultralytics` cho xác thực YOLOv8, `segment-anything` cho gán nhãn bán tự động.

## 5. Chạy

### Cách 1: giao diện một nút bấm

```bash
python3 pipeline/launcher/gradio_launcher_app.py
```

Mở trình duyệt tới `http://localhost:7860`. Chọn cấu hình sẵn (thử 500 ảnh, chuẩn 20.000 ảnh, đầy đủ 100.000 ảnh), bấm chạy, theo dõi tiến độ, nhiệt độ GPU và thông lượng theo thời gian thực. Xong thì tải trực tiếp bộ dữ liệu COCO và YOLO.

### Cách 2: dòng lệnh, từng giai đoạn

```bash
# Kiểm tra ComfyUI đã sẵn sàng
python3 pipeline/verify-comfyui-setup.py

# Giai đoạn 6: sinh ảnh hàng loạt
./pipeline/run-batch-production.sh

# Giai đoạn 7: xuất COCO, YOLO và chia tập
./pipeline/run-post-processing.sh

# Giai đoạn 8: kiểm định chất lượng
python3 pipeline/qa/qa-pipeline-main.py --dataset-dir output/dataset

# Giai đoạn 9: xác thực xuôi dòng bằng YOLOv8
python3 pipeline/validation/validation-main.py --synth-yolo-dir output/dataset/yolo
```

Phiên sản xuất dài nhiều ngày nên chạy dưới `systemd-run` để không bị cắt khi đóng phiên làm việc.

### Kiểm thử

```bash
python3 -m pytest pipeline/tests/ -v
```

## 6. Luồng xử lý

Chín giai đoạn nối tiếp, mỗi giai đoạn có đầu vào, đầu ra và tiêu chí nghiệm thu riêng, chạy lại độc lập được.

```
[1] Thiết lập môi trường     ComfyUI có API, mô hình nền, môi trường Python
[2] Tiền xử lý dữ liệu       patch 512 × 512 theo lớp, 827 ô nền sạch
[3] Tinh chỉnh LoRA          mười hai tệp safetensors hạng 32
[4] Quy trình ComfyUI        đồ thị nút JSON, mẫu lời nhắc theo lớp
        │
        ▼
[5] Sinh mặt nạ  ──►  [6] Sinh ảnh hàng loạt   vòng lặp sản xuất
        │                      │
        │  mặt nạ chú thích     │  ảnh tổng hợp + siêu dữ liệu JSON
        ▼                      ▼
[7] Hậu xử lý và chú thích   COCO JSON, YOLO TXT, chia tập 70/20/10
[8] Đảm bảo chất lượng       báo cáo SSIM, kiểm tra chú thích, lưới ảnh
[9] Xác thực xuôi dòng       YOLOv8 theo bốn tỷ lệ trộn
```

Điểm thiết kế cốt lõi: mặt nạ do hệ thống sinh ra vừa là điều kiện đầu vào cho mô hình khuếch tán, vừa là dữ liệu tham chiếu để xuất chú thích. Nhờ đó bài toán chuyển từ gán nhãn cho ảnh có sẵn sang sinh ảnh theo nhãn đã biết trước, và khâu gán nhãn thủ công bị loại bỏ.

## 7. Tệp đáng đọc trước

| Tệp | Nội dung |
|---|---|
| `pipeline/PIPELINE-OVERVIEW.md` | Tổng quan toàn bộ quy trình |
| `pipeline/mask_generator/base-defect-mask-generator.py` | Lớp cơ sở và ràng buộc vùng hàn |
| `pipeline/mask_generator/crack-mask-generator.py` | Một trình sinh mặt nạ điển hình |
| `pipeline/batch_manager/batch-production-main.py` | Vòng lặp sản xuất chín bước |
| `pipeline/post_processing/` | Chuyển mặt nạ thành COCO và YOLO |
| `pipeline/config/batch-config.yaml` | Cấu hình lô sản xuất |
| `pipeline/comfyui-workflows/sd15-lora-controlnet-inpaint-batch-api-workflow.json` | Đồ thị nút dùng cho sản xuất |

## 8. Tệp mẫu trong `mau-ket-qua/`

| Tệp | Nội dung |
|---|---|
| `<lớp>_<số>.png` | Ảnh tổng hợp của năm lớp khuyết tật |
| `<lớp>_<số>_mask.png` | Mặt nạ chú thích tương ứng |
| `<lớp>_<số>.json` | Siêu dữ liệu: hạt giống, đường dẫn ảnh nền, dấu thời gian |
| `coco_train_trich-5-anh.json` | Trích 5 ảnh của tệp COCO, minh hoạ định dạng |
| `porosity_000188.txt`, `undercut_000246.txt` | Ví dụ nhãn YOLO |
| `data.yaml` | Khai báo tập dữ liệu cho Ultralytics |

Hạt giống và đường dẫn ảnh nền lưu trong tệp siêu dữ liệu, nên mọi ảnh trong tập đều sinh lại được y hệt.

## 9. Kết quả chính

| Chỉ số | Kết quả |
|---|---|
| Thông lượng | 1.097 ảnh/giờ (20.000 ảnh trong khoảng 18 giờ) |
| Tỷ lệ thành công | 98% trên lô thử 500 ảnh |
| SSIM bảo toàn nền | 0,976 |
| Mô hình nền tốt nhất | Stable Diffusion 1.5 gốc, điểm tổng hợp 0,3527 |
| mAP@0,5 của YOLOv8 | 68,5% (chỉ ảnh thật) → 71,2% (trộn 20% ảnh tổng hợp) |
| Huấn luyện chỉ bằng ảnh tổng hợp | 58,3%, thấp hơn mốc đối chứng 10,2 điểm phần trăm |

Chỉ tiêu đặt ra ban đầu là cải thiện mAP trên 5%, kết quả đo được 2,7 điểm phần trăm. Nhóm giữ nguyên số liệu. Mục 4.7 của báo cáo phân tích bảy hạn chế giải thích khoảng cách này, mục 5.3 đề xuất sáu nhóm thay đổi kèm cổng kiểm định.

Vai trò thực tế của hệ thống: công cụ bù dữ liệu cho các lớp thiểu số, không thay thế việc thu thập ảnh thật.

## 10. Giới hạn đã biết

- Mỗi ảnh chứa đúng một khuyết tật, khung cố định 512 × 512, không có ảnh âm tính.
- Bước hậu xử lý quy ước vùng tối ghi đè phần lớn kết cấu do mô hình khuếch tán sinh ra, làm diện mạo khuyết tật phụ thuộc mặt nạ thủ tục nhiều hơn phụ thuộc mô hình.
- Nhãn lấy từ mặt nạ đầu vào, không đo lại từ khuyết tật thực sinh ra.
- Toàn bộ thực nghiệm dựa trên một bộ dữ liệu là GDXray W0003 với 73 phim thật.

Chi tiết ở Chương 4 và Chương 5 của báo cáo.

## 11. Trạng thái kiểm thử

Chạy `python3 pipeline/tests/<tệp>.py` với môi trường đã cài đặt theo mục 4.

| Tệp kiểm thử | Kết quả |
|---|---|
| `test-mask-generator-unit-tests.py` | 34/34 đạt |
| `test-progress-tracker.py` | 14/14 đạt |
| `test-error-handler.py` | 8/8 đạt |
| `test-comfyui-workflow-validation.py` | 8/8 đạt |
| `test-config-preset-manager.py` | 8/8 đạt |

Toàn bộ đạt. Hai trường hợp trượt lúc đầu đã truy được nguyên nhân và sửa, trình bày ở mục 12.

## 12. Ba lỗi phát hiện khi đóng gói, đã sửa

**Một, tab Tạo Ảnh không chạy được, ném `IndexError`.** Hàm `on_run` trong `launcher/ui_generation_panel.py` cắt cứng danh sách tham số đầu vào ở vị trí 5 (`slider_and_sampler_values[:5]`), trong khi vòng lặp ngay dưới duyệt hết `DEFECT_TYPES`. Danh sách lớp khuyết tật đã tăng từ 5 lên 10 nên từ phần tử thứ sáu trở đi là vượt chỉ số, cả tab hỏng.

Đã sửa: cắt theo `len(DEFECT_TYPES)` thay vì hằng số 5. Sau khi sửa, tab chạy đủ tuyến, gọi ComfyUI và sinh ảnh bình thường. Video demo nộp kèm quay lại chính lần chạy đó.

**Hai, tổng phân bố lớp trong `config/batch-config.yaml` bằng 1,2.** Mười hai lớp, mỗi lớp khai 0,1. Bộ lập lịch ở `batch_manager/batch-job-scheduler.py` tính số ảnh mỗi lớp bằng `int(total_images × tỷ_lệ)` và không chuẩn hoá lại tổng, nên chạy từ dòng lệnh một lô khai 1.000 ảnh sẽ sinh ra 1.200 ảnh. Chạy từ giao diện không bị, vì `launcher/gradio_launcher_app.py` ghi đè phân bố bằng tỷ lệ chia đều rồi mới kiểm tra hợp lệ.

Đã sửa: mỗi lớp 0,0833, riêng lớp cuối 0,0837 để tổng đúng 1,0. Thêm chú thích ngay trong tệp cấu hình cảnh báo ràng buộc này cho người sửa sau.

**Ba, kiểm thử quy trình ComfyUI đòi ba nút đã bỏ.** Tệp kiểm thử yêu cầu cả hai quy trình phải có `ControlNetLoader`, `InpaintModelConditioning` và `ControlNetApplyAdvanced`. Quy trình sản xuất vẫn có đủ, nhưng quy trình một ảnh đã thiết kế lại theo hướng `VAEEncode` cộng `SetLatentNoiseMask` và bỏ ControlNet, nên trượt. Kiểm thử cũ hơn thiết kế.

Đã sửa: tách nhóm nút bắt buộc thành nút chung, nhóm ControlNet và nhóm mặt nạ tiềm ẩn; mỗi quy trình kiểm theo đúng nhóm của nó.

## 13. Video demo

`The-Data-Mint-demo.mp4`, 112 giây, 1600 × 900, có phụ đề tiếng Việt.

Nội dung: giao diện vận hành, chọn lớp khuyết tật, chọn mô hình LoRA, bật chế độ Pilot rồi chạy thật một lô sinh ảnh, theo dõi nhật ký, kết thúc bằng lưới ảnh tổng hợp cùng mặt nạ chú thích.

Toàn bộ là màn hình thật của hệ thống đang chạy, không dựng lại. Đoạn chờ ComfyUI sinh ảnh được tua nhanh 5 lần, phần còn lại giữ nguyên tốc độ thật.

Dựng lại video bằng ba script trong thư mục `Report/` của đồ án:

```bash
node Report/record-demo-video.mjs /tmp/demo-frames      # quay màn hình
python3 Report/build-demo-closing-slides.py /tmp/demo-closing   # hai tấm hình kết
python3 Report/build-demo-video.py /tmp/demo-frames demo.mp4    # ghép và chèn phụ đề
```

Điều kiện: Gradio chạy ở `127.0.0.1:7860`, ComfyUI ở `127.0.0.1:8188`, có Chrome và FFmpeg.
