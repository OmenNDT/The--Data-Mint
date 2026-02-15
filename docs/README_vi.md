
# The Data Mint - Chỉ mục Tài liệu

**Cập nhật lần cuối**: 2026-01-31
**Phiên bản Tài liệu**: 1.0
**Trạng thái**: Sẵn sàng cho Sản xuất

---

## Tổng quan về Tài liệu

Tài liệu kỹ thuật hoàn chỉnh cho quy trình tạo tia X tổng hợp cho khuyết tật hàn của The Data Mint. Thư mục này chứa 5 tài liệu cốt lõi bao gồm các yêu cầu dự án, cấu trúc mã nguồn, tiêu chuẩn phát triển, kiến trúc hệ thống và lộ trình dự án.

**Tổng số Tài liệu**: 3,026 dòng trong 5 tệp markdown
**Phạm vi bao phủ**: 100% (tất cả 9 giai đoạn, tất cả các thành phần, tất cả các API)

---

## Điều hướng nhanh

### Dành cho các đối tượng khác nhau

**Quản lý dự án & Các bên liên quan**:
1. Bắt đầu: [Root README.md](/README.md) (đọc 5 phút)
2. Tìm hiểu sâu: [Lộ trình dự án](./project-roadmap.md) (đọc 15 phút)
3. Yêu cầu: [Tổng quan dự án & PDR](./project-overview-pdr.md) (đọc 20 phút)

**Lập trình viên (Mới tham gia dự án)**:
1. Bắt đầu: [Root README.md](/README.md) (đọc 5 phút)
2. Cài đặt: Phần Bắt đầu nhanh trong README
3. Tham khảo: [Tóm tắt mã nguồn](./codebase-summary.md) (đọc 20 phút)
4. Tiêu chuẩn: [Tiêu chuẩn mã hóa](./code-standards.md) (đọc 20 phút)

**Lập trình viên (Sửa đổi mã)**:
1. Tham khảo: [Tóm tắt mã nguồn](./codebase-summary.md) (tìm mô-đun của bạn)
2. Tiêu chuẩn: [Tiêu chuẩn mã hóa](./code-standards.md) (tuân thủ các quy ước)
3. Kiến trúc: [Kiến trúc hệ thống](./system-architecture.md) (hiểu tác động)
4. Kiểm thử: Xem phần kiểm thử trong code-standards.md

**Kiến trúc sư & Lập trình viên cao cấp**:
1. Tổng quan: [Kiến trúc hệ thống](./system-architecture.md) (đọc 30 phút)
2. Yêu cầu: [Tổng quan dự án & PDR](./project-overview-pdr.md) (đọc 15 phút)
3. Tiêu chuẩn: [Tiêu chuẩn mã hóa](./code-standards.md) (các mẫu phát triển)

**Kỹ sư triển khai**:
1. Bắt đầu nhanh: [Root README.md](/README.md) - Cấu hình & Xử lý sự cố
2. Vận hành: Xem Giai đoạn 6+ trong [Lộ trình dự án](./project-roadmap.md)
3. Giám sát: [Kiến trúc hệ thống](./system-architecture.md) - Giám sát & Quan sát

---

## Mô tả Tài liệu

### 1. [project-overview-pdr.md](./project-overview-pdr.md)
**Loại**: Yêu cầu Phát triển Sản phẩm
**Độ dài**: 345 dòng
**Đối tượng**: Quản lý dự án, các bên liên quan, kiến trúc sư

**Nội dung**:
- Tóm tắt điều hành & giá trị kinh doanh
- 10 yêu cầu chức năng (tất cả đã hoàn thành)
- 10 yêu cầu phi chức năng với các chỉ số
- Định nghĩa phạm vi (trong/ngoài phạm vi)
- Thông số kỹ thuật (LoRA, ComfyUI, tham số lô)
- Tổng quan kiến trúc hệ thống
- Tiêu chí thành công theo từng giai đoạn
- Đánh giá rủi ro (7 rủi ro + biện pháp giảm thiểu)
- Phụ thuộc (dịch vụ, gói, phần cứng)
- Quy trình vận hành
- Lộ trình cải tiến trong tương lai

**Các phần chính**:
- Bảng Yêu cầu Chức năng (10 FR)
- Bảng Yêu cầu Phi chức năng (10 NFR)
- Bảng Tham số Tinh chỉnh LoRA
- Bảng Cài đặt Quy trình ComfyUI
- Bảng Cổng chất lượng theo Giai đoạn
- Ma trận Đánh giá Rủi ro

---

### 2. [codebase-summary.md](./codebase-summary.md)
**Loại**: Tham khảo Thành phần & Tài liệu API
**Độ dài**: 647 dòng
**Đối tượng**: Lập trình viên, kiến trúc sư, người đánh giá mã

**Nội dung**:
- Hướng dẫn điều hướng nhanh (7 phần)
- Lõi quy trình (điểm vào, máy khách)
- Mô-đun quản lý lô (6 tệp, ~1,400 LOC)
  - Tài liệu chi tiết về lớp/phương thức cho mỗi mô-đun
- Mô-đun tạo mặt nạ (8 tệp, ~600 LOC)
  - Triển khai và thuật toán của trình tạo
- Mô-đun xử lý hậu kỳ (5 tệp, ~880 LOC)
  - Trình tạo chú thích COCO/YOLO
- Mô-đun đảm bảo chất lượng (4 tệp, ~1,000 LOC)
  - Các thành phần xác thực và kiểm tra
- Mô-đun xác thực (3 tệp, ~790 LOC)
  - Huấn luyện và đánh giá YOLOv8
- Tham khảo cấu hình (tham số YAML/TOML)
- Tích hợp dịch vụ bên ngoài (API ComfyUI, mô hình LoRA)
- Đặc tính hiệu suất (bảng thông lượng)
- Chiến lược tổ chức tệp
- Phụ thuộc & phiên bản

**Các bảng chính**:
- Thành phần Quản lý Lô (tên lớp, LOC, mục đích)
- Trình tạo Mặt nạ (thuật toán, tham số, đầu ra)
- Mô hình LoRA (5 mô hình với kích thước, trạng thái)
- Chỉ số Hiệu suất (thông lượng thành phần)
- Phụ thuộc (các gói Python với phiên bản)

---

### 3. [code-standards.md](./code-standards.md)
**Loại**: Quy ước Phát triển & Thực hành Tốt nhất
**Độ dài**: 724 dòng
**Đối tượng**: Tất cả lập trình viên

**Nội dung**:
- Đặt tên & tổ chức tệp (kebab-case, <200 dòng)
- Kiểu mã Python (quy ước đặt tên)
- Gợi ý kiểu (định dạng bắt buộc với ví dụ)
- Chuỗi tài liệu (mẫu kiểu Google)
- Mẫu xử lý lỗi (quy tắc try-catch)
- Tổ chức import (cấu trúc 3 nhóm)
- Quản lý cấu hình (hướng dẫn YAML/TOML)
- Ghi log (mẫu ghi log Python, 5 cấp độ)
- Kiểm thử (đơn vị + tích hợp, độ bao phủ >80%)
- Chú thích & tài liệu (chú thích nội tuyến thưa thớt, thuật toán chi tiết)
- Hiệu suất & tối ưu hóa (quy tắc định hình)
- Phụ thuộc & phiên bản (phiên bản được ghim)
- Thông điệp commit Git (định dạng Conventional Commits)
- Bảo mật & bí mật (xử lý thông tin xác thực)
- Danh sách kiểm tra đánh giá mã (xác minh 11 điểm)
- Quy trình phát triển (các bước thiết lập cục bộ)
- Phần Hỏi & Đáp (6 câu hỏi thường gặp)

**Ví dụ về mã**:
- Hơn 40 ví dụ về mã minh họa các thực hành tốt
- Các mẫu tốt và xấu với giải thích
- Mẫu lớp/hàm hoàn chỉnh

---

### 4. [system-architecture.md](./system-architecture.md)
**Loại**: Kiến trúc & Tìm hiểu sâu về Kỹ thuật
**Độ dài**: 769 dòng
**Đối tượng**: Kiến trúc sư, lập trình viên cao cấp

**Nội dung**:
- Sơ đồ kiến trúc cấp cao (quy trình 9 giai đoạn)
- Sơ đồ luồng dữ liệu (4 luồng ASCII chi tiết)
  - Quy trình tạo (Giai đoạn 1-6)
  - Quy trình chú thích (Giai đoạn 7)
  - Quy trình xác thực QA (Giai đoạn 8)
  - Quy trình xác thực YOLOv8 (Giai đoạn 9)
- Kiến trúc thành phần (phân cấp mô-đun)
- Biểu đồ phụ thuộc (mối quan hệ import)
- Cấu trúc dữ liệu (Job, Checkpoint, COCO, YOLO)
- Xử lý lỗi & phục hồi (chiến lược chịu lỗi)
- Đặc tính hiệu suất (3 bảng chi tiết)
- Khả năng mở rộng & hạn chế (ràng buộc phần cứng)
- Điểm tích hợp (ComfyUI, hệ thống tệp, ghi log)
- Giám sát & quan sát (chỉ số & cấp độ log)
- Chiến lược kiểm thử (tổ chức đơn vị + tích hợp)
- Cân nhắc bảo mật (xử lý dữ liệu, mô hình)

**Các sơ đồ chính**:
- Sơ đồ ASCII quy trình 9 giai đoạn
- Quy trình tạo với song song GPU/CPU
- Luồng chuyển đổi chú thích
- Kiểm tra song song xác thực QA
- Luồng thử nghiệm xác thực
- Cây phân cấp thành phần
- Biểu đồ phụ thuộc mô-đun

---

### 5. [project-roadmap.md](./project-roadmap.md)
**Loại**: Trạng thái Dự án & Theo dõi Tiến độ
**Độ dài**: 541 dòng
**Đối tượng**: Quản lý dự án, các bên liên quan, lập trình viên

**Nội dung**:
- Tóm tắt điều hành (tất cả 9 giai đoạn đã hoàn thành)
- Trạng thái hoàn thành theo từng giai đoạn (với ngày & sản phẩm bàn giao)
  - Mỗi giai đoạn: trạng thái, nỗ lực, ngày bắt đầu/kết thúc, sản phẩm bàn giao
  - Các phát hiện chính và chỉ số cho mỗi giai đoạn
- Mốc thời gian & các mốc quan trọng (đường găng)
- Sẵn sàng triển khai sản xuất (danh sách kiểm tra)
- Các vấn đề đã biết & biện pháp giảm thiểu (3 vấn đề được ghi nhận)
- Chỉ số thành công & KPI (hơn 15 chỉ số qua 4 giai đoạn)
- Các bước tiếp theo & cải tiến trong tương lai
  - Ngay lập tức (sẵn sàng ngay)
  - Ngắn hạn (1-2 tháng)
  - Dài hạn (3-6 tháng)
- Phân bổ tài nguyên (trạng thái phần cứng hiện tại)
- Tài liệu & cơ sở kiến thức
- Phần ký duyệt & phê duyệt
- Lịch sử phiên bản

**Các bảng chính**:
- Trạng thái Hoàn thành Giai đoạn (9 giai đoạn, tất cả đã hoàn thành)
- Các mô hình LoRA đã huấn luyện (5 mô hình, mỗi mô hình 37 MB)
- Kết quả Thí điểm Giai đoạn 6 (500 hình ảnh, chỉ số)
- Kết quả QA Giai đoạn 8 (5 kiểm tra, đạt/không đạt)
- Thử nghiệm Xác thực Giai đoạn 9 (4 tỷ lệ được kiểm tra)
- Chỉ số Thành công (hơn 15 KPI với mục tiêu/đạt được)

---

## Vị trí tệp (Đường dẫn tuyệt đối)

Tất cả các tệp tài liệu đều nằm trong `/mnt/e/The Data Mint/docs/`:

```
/mnt/e/The Data Mint/
├── README.md                              (Hướng dẫn bắt đầu nhanh)
├── docs/
│   ├── README.md                          (Tệp này - chỉ mục tài liệu)
│   ├── project-overview-pdr.md            (Yêu cầu & PDR)
│   ├── codebase-summary.md                (Tham khảo thành phần)
│   ├── code-standards.md                  (Quy ước phát triển)
│   ├── system-architecture.md             (Kiến trúc & luồng dữ liệu)
│   └── project-roadmap.md                 (Trạng thái giai đoạn & lộ trình)
├── repomix-output.xml                     (Nén toàn bộ mã nguồn)
└── plans/
    └── reports/
        └── docs-manager-260131-1409-initial-documentation-creation.md
            (Báo cáo tạo chi tiết)
```

---

## Thống kê nội dung

| Tệp | Dòng | Trọng tâm | Đối tượng |
|------|-------|-------|----------|
| project-overview-pdr.md | 345 | Yêu cầu | PM, Các bên liên quan |
| codebase-summary.md | 647 | Thành phần | Lập trình viên |
| code-standards.md | 724 | Quy ước | Tất cả Lập trình viên |
| system-architecture.md | 769 | Kiến trúc | Kiến trúc sư |
| project-roadmap.md | 541 | Trạng thái | PM, Lập trình viên |
| **TỔNG CỘNG** | **3,026** | **Hoàn chỉnh** | **Tất cả** |

---

## Các tài nguyên chính

### Tài liệu bên ngoài

- **ComfyUI**: https://github.com/comfyanonymous/ComfyUI
- **Stable Diffusion 1.5**: https://huggingface.co/runwayml/stable-diffusion-v1-5
- **Huấn luyện LoRA (kohya-ss)**: https://github.com/bmaltais/kohya_ss
- **ControlNet**: https://github.com/lllyasviel/ControlNet
- **YOLOv8**: https://docs.ultralytics.com
- **Định dạng Tập dữ liệu COCO**: https://cocodataset.org/#format-data

### Tham khảo nội bộ

- **Root README**: `/mnt/e/The Data Mint/README.md` (Bắt đầu nhanh)
- **Tổng quan Quy trình**: `/mnt/e/The Data Mint/pipeline/PIPELINE-OVERVIEW.md` (Hướng dẫn vận hành)
- **Kế hoạch Triển khai**: `/mnt/e/The Data Mint/plans/260130-0849-the-data-mint-xray-defect-pipeline/plan.md`
- **Nén Mã nguồn**: `/mnt/e/The Data Mint/repomix-output.xml` (Toàn bộ mã nguồn)

---

## Sử dụng Tài liệu này

### Chiến lược đọc

**Để hiểu nhanh** (30 phút):
1. Đọc: Root [README.md](/README.md)
2. Lướt qua: [Lộ trình dự án](./project-roadmap.md) - Tóm tắt các giai đoạn
3. Xong! Bạn đã hiểu dự án

**Để có kiến thức chi tiết** (2 giờ):
1. Đọc: [Root README.md](/README.md)
2. Đọc: [Tổng quan dự án & PDR](./project-overview-pdr.md)
3. Đọc: [Kiến trúc hệ thống](./system-architecture.md)
4. Lướt qua: [Tóm tắt mã nguồn](./codebase-summary.md)
5. Lướt qua: [Tiêu chuẩn mã hóa](./code-standards.md)

**Để triển khai** (hơn 3 giờ):
1. Đọc kỹ tất cả 5 tệp tài liệu
2. Xem lại: Các ví dụ về mã trong [Tiêu chuẩn mã hóa](./code-standards.md)
3. Nghiên cứu: Các API thành phần trong [Tóm tắt mã nguồn](./codebase-summary.md)
4. Tham khảo: Các sơ đồ luồng dữ liệu trong [Kiến trúc hệ thống](./system-architecture.md)

### Tìm kiếm thông tin cụ thể

**Tôi cần...**

- **Hiểu phạm vi dự án**: Đọc [project-overview-pdr.md](./project-overview-pdr.md)
- **Tìm một mô-đun/lớp cụ thể**: Tìm kiếm [codebase-summary.md](./codebase-summary.md)
- **Học các quy ước mã hóa**: Đọc [code-standards.md](./code-standards.md)
- **Hiểu luồng dữ liệu**: Nghiên cứu [system-architecture.md](./system-architecture.md)
- **Kiểm tra trạng thái giai đoạn**: Xem [project-roadmap.md](./project-roadmap.md)
- **Nhận câu trả lời nhanh**: Kiểm tra phần FAQ trong [Root README.md](/README.md)
- **Xem ví dụ về mã**: [Tiêu chuẩn mã hóa](./code-standards.md) có hơn 40 ví dụ
- **Hiểu hiệu suất**: [Kiến trúc hệ thống](./system-architecture.md) có các bảng chi tiết

---

## Bảo trì & Cập nhật

### Quyền sở hữu Tài liệu

- **Tổng thể**: Nhóm Phát triển & Quản lý Dự án
- **PDR**: Quản lý Dự án, Trưởng nhóm Kỹ thuật
- **Tóm tắt Mã nguồn**: Nhóm Phát triển (tự động tạo từ mã)
- **Tiêu chuẩn Mã hóa**: Trưởng nhóm Kỹ thuật, Lập trình viên Cao cấp
- **Kiến trúc**: Trưởng nhóm Kỹ thuật, Kiến trúc sư
- **Lộ trình**: Quản lý Dự án, Chủ sở hữu Sản phẩm

### Lịch cập nhật

- **Tiêu chuẩn Mã hóa**: Khi cần (sau khi tái cấu trúc)
- **Tóm tắt Mã nguồn**: Sau các thay đổi lớn (đánh giá hàng quý)
- **Kiến trúc**: Sau các thay đổi thiết kế (đánh giá hàng quý)
- **Lộ trình**: Hàng tháng (hoàn thành giai đoạn, các bước tiếp theo)
- **PDR**: Hàng năm hoặc khi có thay đổi phạm vi

### Kiểm soát phiên bản

Tất cả tài liệu đều được kiểm soát phiên bản trong Git:

```bash
git log docs/                    # Xem các thay đổi tài liệu
git diff HEAD~1 docs/            # Xem các thay đổi mới nhất
git blame docs/file.md           # Xem ai đã thay đổi gì
```

---

## Đảm bảo chất lượng

### Tiêu chuẩn Tài liệu

✓ **Tất cả các tệp đều đáp ứng tiêu chuẩn**:
- Dòng: <800 mỗi tệp (tối đa 769)
- Định dạng: Markdown với hệ thống tiêu đề phù hợp
- Ví dụ: Hơn 40 ví dụ về mã với tô sáng cú pháp
- Liên kết: Tất cả các liên kết nội bộ đã được xác minh (đường dẫn tương đối)
- Độ chính xác: Tất cả các chỉ số từ dữ liệu thí điểm đã đo
- Phạm vi bao phủ: 100% các thành phần mã nguồn

### Danh sách kiểm tra xác thực

- [x] Tất cả các tệp đã được tạo và đặt đúng vị trí
- [x] Không có liên kết bị hỏng (đường dẫn tương đối đã được xác minh)
- [x] Các ví dụ về mã khớp với triển khai thực tế
- [x] Các tham số cấu hình từ batch-config.yaml
- [x] Các chỉ số từ dữ liệu thí điểm đã được xác minh
- [x] Kích thước tệp trong giới hạn (<800 dòng)
- [x] Các tham chiếu chéo toàn diện
- [x] Độ chính xác kỹ thuật đã được xác minh

---

## Đóng góp vào Tài liệu

### Khi nào cần cập nhật

1. **Sau khi thay đổi mã**: Cập nhật [codebase-summary.md](./codebase-summary.md)
2. **Sau khi thay đổi thiết kế**: Cập nhật [system-architecture.md](./system-architecture.md)
3. **Sau khi hoàn thành giai đoạn**: Cập nhật [project-roadmap.md](./project-roadmap.md)
4. **Tiêu chuẩn/Quy ước mới**: Cập nhật [code-standards.md](./code-standards.md)
5. **Thay đổi phạm vi**: Cập nhật [project-overview-pdr.md](./project-overview-pdr.md)

### Cách cập nhật

1. Đọc kỹ tệp (hiểu ngữ cảnh)
2. Thực hiện các thay đổi chính xác (chỉ thêm/cập nhật những gì đã thay đổi)
3. Xác minh các liên kết vẫn hoạt động (đường dẫn tương đối)
4. Xác minh các ví dụ về mã vẫn biên dịch được
5. Cập nhật ngày sửa đổi cuối cùng trong tiêu đề
6. Commit với thông điệp rõ ràng: `docs: update <file> for <reason>`

### Giới hạn kích thước

Nếu một tệp gần 800 dòng:
1. Xác định các ranh giới chủ đề tự nhiên
2. Tạo các tệp chủ đề con: `docs/{topic}/index.md` + các tệp thành phần
3. Cập nhật chỉ mục này để liên kết cấu trúc mới
4. Ví dụ: `docs/api-reference/` với `batch-manager.md`, `mask-generator.md`, v.v.

---

## Câu hỏi thường gặp

**H: Tôi nên đọc tài liệu nào trước?**
Đ: [Root README.md](/README.md) - nó cung cấp cho bạn cái nhìn tổng quan hoàn chỉnh trong 10 phút.

**H: Tài liệu API ở đâu?**
Đ: Trong [codebase-summary.md](./codebase-summary.md) - mỗi mô-đun có tài liệu về lớp/phương thức.

**H: Làm cách nào để thiết lập môi trường phát triển?**
Đ: [Root README.md](/README.md) - Phần Bắt đầu, hoặc [Tiêu chuẩn mã hóa](./code-standards.md) - Quy trình phát triển.

**H: Trạng thái dự án là gì?**
Đ: [Lộ trình dự án](./project-roadmap.md) - Tất cả 9 giai đoạn đã hoàn thành, sẵn sàng cho sản xuất.

**H: Làm cách nào để chạy toàn bộ quy trình?**
Đ: [Root README.md](/README.md) - Phần Chạy quy trình.

**H: Các quy ước mã hóa là gì?**
Đ: [Tiêu chuẩn mã hóa](./code-standards.md) - hướng dẫn kiểu hoàn chỉnh với các ví dụ.

**H: Tôi có thể sửa đổi mã không?**
Đ: Có, nhưng trước tiên hãy tuân thủ [Tiêu chuẩn mã hóa](./code-standards.md), sau đó là [Danh sách kiểm tra đánh giá mã](./code-standards.md#code-review-checklist).

**H: Hiệu suất như thế nào?**
Đ: [Kiến trúc hệ thống](./system-architecture.md) - Phần Đặc tính hiệu suất.

---

## Hỗ trợ & Phản hồi

### Báo cáo sự cố

- **Sự cố mã**: Tham chiếu đến tệp cụ thể trong [Tóm tắt mã nguồn](./codebase-summary.md)
- **Sự cố tài liệu**: Tạo sự cố với tham chiếu đến tài liệu cụ thể
- **Sự cố kiến trúc**: Tham chiếu [Kiến trúc hệ thống](./system-architecture.md)

### Yêu cầu cải tiến

- Đối với các tính năng mới: Cập nhật [Lộ trình dự án](./project-roadmap.md)
- Đối với các thay đổi kiến trúc: Cập nhật [Kiến trúc hệ thống](./system-architecture.md)
- Đối với các thay đổi mã: Cập nhật [Tóm tắt mã nguồn](./codebase-summary.md)

---

## Tóm tắt

Tài liệu này cung cấp phạm vi bao phủ toàn diện về dự án The Data Mint:

- **345 dòng** yêu cầu & tiêu chí thành công
- **647 dòng** API thành phần & tham khảo
- **724 dòng** quy ước phát triển
- **769 dòng** kiến trúc & luồng dữ liệu
- **541 dòng** trạng thái dự án & lộ trình
- **Tổng cộng 3,026 dòng** tài liệu sẵn sàng cho sản xuất

Tất cả tài liệu đều được cập nhật, chính xác và sẵn sàng để phân phối cho nhóm.

---

**Trạng thái Tài liệu**: ✓ Sẵn sàng cho Sản xuất
**Cập nhật lần cuối**: 2026-01-31
**Đánh giá tiếp theo**: 2026-02-28
