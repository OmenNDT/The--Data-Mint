---
description: Tọa mới/cập nhật/chỉnh sửa sơ đồ luồng dữ liệu HTML (IN→xử lý→OUT) từ code bằng skill data-flow-graph
argument-hint: <file(s) hoặc mô tả> [+ câu hỏi luồng dữ liệu]
---

Kích hoạt skill **`data-flow-graph`** để phân tích code và render **một sơ đồ luồng dữ liệu HTML liền mạch** (mỗi block hiển thị `IN → xử lý → OUT`, nối nhau bằng mũi tên có nhãn).

## Yêu cầu người dùng
$ARGUMENTS

## Hướng dẫn thực thi
1. **BẮT BUỘC** dùng công cụ Skill để gọi skill `data-flow-graph` TRƯỚC KHI làm bất cứ việc gì khác.
2. Xác định (các) file code mục tiêu từ `$ARGUMENTS`:
   - Nếu là đường dẫn file cụ thể → đọc & phân tích file đó.
   - Nếu là mô tả (vd "batch-pipeline-dataflow", "ComfyUI") → dò trong `src/` để tìm file khớp, xác nhận nếu mơ hồ.
   - Nếu trống → hỏi lại file/mô tả cần vẽ.
3. Trích câu hỏi về luồng dữ liệu (nếu có) để làm rõ trọng tâm sơ đồ (vd "từ ảnh raw đến logits", "chỗ nào lưu checkpoint").
4. Xuất file HTML self-contained theo template của skill; báo lại đường dẫn file để mở trên trình duyệt.

**Lưu ý dự án:** file thường nằm ở `/home/sontn/Projects/The Data Mint/pipeline`, `/home/sontn/Projects/The Data Mint/scripts`, `/home/sontn/Projects/The Data Mint/comfyui`.
