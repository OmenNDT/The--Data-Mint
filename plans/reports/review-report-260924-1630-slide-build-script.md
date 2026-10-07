# Review tài liệu: Report/build-slides-pptx.py

Bối cảnh nhận diện: **báo cáo đồ án môn học** (chuỗi nội dung slide bảo vệ, có GVHD, sinh viên thực hiện, cấu trúc 5 chương) | Đoạn rà: 201 | Sửa đổi áp được: 19 (mục 1 sửa hai lượt theo yêu cầu người viết) | Số từ: 3.237 → 3.234 (giảm 0,1%)

## Lưu ý về định dạng đầu vào

File là `.py`, ngoài 4 định dạng skill hỗ trợ. Nội dung rà là 201 chuỗi tiếng Việt trong hàm `build_cover` và `build_content` (chữ in ra slide). Track Changes không áp được cho `.py`; sửa đổi áp trực tiếp, bản gốc lưu tại `Report/build-slides-pptx.py.bak-before-review` (thư mục `Report/` chưa đưa vào git), xem diff bằng `diff Report/build-slides-pptx.py.bak-before-review Report/build-slides-pptx.py`.

Code, tên biến, tên hàm, chuỗi kỹ thuật không chứa tiếng Việt: **không đụng tới**.

## Thống kê theo lượt

| Lượt | Loại vấn đề | Số sửa đổi |
|---|---|---|
| L1 | Lối Anh ngữ (bị động thừa, khôi phục nghĩa gốc) | 4 |
| L2 | Từ lệch bối cảnh, thống nhất thuật ngữ | 3 |
| L3 | Câu tự biện minh | 0 |
| L4 | Cường điệu | 1 |
| L5 | Cụm đệm rỗng | 0 |
| L6 | Cắt từ thừa, tách câu dài | 5 |
| L7a | Dấu câu, gạch ngang xen giữa | 6 |
| L7b | Định dạng, heading | không áp dụng (không phải .docx) |

L3 và L5 không có sửa đổi: nội dung slide rút từ bản báo cáo đã qua rà soát, không còn câu tự khen hay cụm đệm.

Mức cắt từ 0,1% thay vì 10–25% theo chuẩn: nguồn đã là văn bản cô đọng, cắt sâu hơn sẽ mất số liệu hoặc mất ý.

## Chi tiết sửa đổi

| # | Đoạn | Trước | Sau | Lý do |
|---|---|---|---|---|
| 1 | P011 | ...mối hàn, **được quy phạm coi là** bằng chứng nghiệm thu. | ...mối hàn**. Quy phạm coi phim chụp là** bằng chứng nghiệm thu. | L1 bị động thừa; tách câu để chủ thể của "bằng chứng" là phim chụp |
| 2 | P014 | loại bỏ khâu **gán nhãn tay** | loại bỏ khâu **gán nhãn thủ công** | L2 thống nhất thuật ngữ với P173 |
| 3 | P024 | thu thập phim mới, **gán nhãn tay** | thu thập phim mới, **gán nhãn thủ công** | L2 thống nhất thuật ngữ |
| 4 | P082 | tương phản khuyết tật **quá thấp và bị** bước làm tối | tương phản khuyết tật **thấp, lại bị** bước làm tối | L6 bỏ lặp "quá", cắt từ thừa |
| 5 | P085 | ...dùng xuất COCO và YOLO**;** mặt nạ inpaint giãn nở... | ...dùng xuất COCO và YOLO**. M**ặt nạ inpaint giãn nở... | L6 tách câu 48 từ |
| 6 | P086 | vùng mô hình **được vẽ** nhưng không thuộc vùng chú thích | vùng mô hình **được phép vẽ** nhưng không thuộc vùng chú thích | L1 khôi phục nghĩa gốc trong báo cáo |
| 7 | P111 | mọi pixel ngoài mặt nạ chú thích **được thay bằng** pixel nền gốc | **thay** mọi pixel ngoài mặt nạ chú thích **bằng** pixel nền gốc | L1 bỏ bị động thừa |
| 8 | P111 | sigma 1,5, **nhằm** xoá quầng sáng | sigma 1,5, **để** xoá quầng sáng | L6 cắt từ |
| 9 | P115 | 3.6 **–** 3.9 CHÚ THÍCH TỰ ĐỘNG... | 3.6 **ĐẾN** 3.9 CHÚ THÍCH TỰ ĐỘNG... | L7 bỏ gạch ngang xen giữa |
| 10 | P120 | 4.1 **–** 4.2 MÔI TRƯỜNG... | 4.1 **VÀ** 4.2 MÔI TRƯỜNG... | L7 bỏ gạch ngang xen giữa |
| 11 | P129 | ...bốn chữ số**:** giả thiết ... **không được dữ liệu ủng hộ**. | ...bốn chữ số**.** **Dữ liệu không ủng hộ** giả thiết rằng... | L1 bỏ bị động, tách câu |
| 12 | P130 | 4.4 **&** 4.6 KIỂM ĐỊNH... | 4.4 **VÀ** 4.6 KIỂM ĐỊNH... | L2 ký hiệu "&" không dùng trong tiêu đề tiếng Việt |
| 13 | P132 | 900 **–** 1.800 ảnh/giờ | 900 **tới** 1.800 ảnh/giờ | L7 bỏ gạch ngang |
| 14 | P150 | không phải lỗi quy trình**:** thư mục kiểm..., **và** bản khai báo | không phải lỗi quy trình**. T**hư mục kiểm...**;** bản khai báo | L6 tách câu 44 từ |
| 15 | P173 | loại bỏ **hoàn toàn** khâu gán nhãn thủ công | loại bỏ khâu gán nhãn thủ công | L4 bỏ từ cường điệu |
| 16 | P178 | Đo bằng mAP trên ảnh thật **đã** phơi bày | Đo bằng mAP trên ảnh thật phơi bày | L6 bỏ "đã" thừa |
| 17 | P183 | giảm denoise xuống 0,55 **–** 0,65 | giảm denoise xuống 0,55 **tới** 0,65 | L7 bỏ gạch ngang |
| 18 | P187 | tỷ số phương sai 0,8 **–** 1,2 | tỷ số phương sai 0,8 **tới** 1,2 | L7 bỏ gạch ngang |
| 19 | P189 | trộn 20% **–** 30% vào tập huấn luyện | trộn 20% **tới** 30% vào tập huấn luyện | L7 bỏ gạch ngang |

## L7a — 7 sửa đổi tự sinh bị loại bỏ

Script `audit-punctuation.py` đề xuất đổi dấu thập phân ở 7 chỗ. **Loại toàn bộ**, đều là dương tính giả thuộc ràng buộc cứng:

| Chuỗi | Script đề xuất | Thực chất | Ràng buộc |
|---|---|---|---|
| `Stable Diffusion 1.5` (4 chỗ) | `1,5` | Số hiệu phiên bản phần mềm | Tên riêng |
| `3.6 – 3.9`, `4.1 – 4.2`, `4.4 & 4.6` | `3,9` `4,2` `4,6` | Số hiệu mục trong báo cáo | Tiêu đề mục theo biểu mẫu |

## Đã kiểm tra, giữ nguyên

- **Dấu chấm hàng nghìn** (12 chỗ: 18.158, 1.809, 6.259, 1.097, 1.611, 20.000, 100.000): đúng quy ước Việt Nam, khớp bản báo cáo gốc.
- **Thiếu khoảng trắng sau dấu chấm** (3 chỗ): tên tệp `5. Mẫu Slide báo cáo.pptx`, `batch-production-main.py`, `data.yaml`.
- **`mAP@0,5` và `mAP@0,5:0,95`**: thuật ngữ đã chuẩn hoá trong báo cáo, giữ đồng bộ.
- **Toàn bộ số liệu**: 0,976 · 1.097 ảnh/giờ · 68,5% → 71,2% · +2,7 điểm phần trăm · FID 198 tới 215 · 10,2 điểm phần trăm · 18.158 dòng. Đối chiếu lại với `Report/do-an-the-data-mint.md`, khớp.
- **Tên riêng**: GDXray W0003, RIAWELC, ComfyUI, kohya-ss, YOLOv8, ISO 6520-1, control_v11p_sd15_inpaint, các mô hình nền.
- **Chính tả nhất quán sẵn có**: "hoá/oà" (mã hoá, bão hoà, đồ hoạ), "tỷ lệ", "mô-đun" đồng bộ toàn văn, không cần sửa.

## Kiểm chứng sau sửa

- 19/19 sửa đổi khớp duy nhất, không có mục `unmatched`.
- Chạy lại `audit-punctuation.py` trên bản sau: mục "gạch ngang giữa câu" hết, còn lại chỉ 2 nhóm đã xác nhận giữ nguyên.
- Dựng lại `Slide-bao-cao-The-Data-Mint.pptx`: 23 slide, render PDF và soát ảnh các slide bị ảnh hưởng (3, 10, 13, 14, 15, 16, 17, 21). Không tràn chữ, không đè ảnh, tiêu đề dài vẫn nằm một dòng.

## Cần người viết quyết định

> P011 đã chốt: tách thành hai câu, chủ thể của "bằng chứng nghiệm thu" là phim chụp. Áp ngày 2026-09-24.

1. **P115 tiêu đề "3.6 ĐẾN 3.9"**: slide gộp bốn mục. Nếu hội đồng quen cách ghi khác (ví dụ "MỤC 3.6 – 3.9"), anh chốt lại cách ghi để tôi sửa đồng bộ.
2. **"ảnh tổng hợp" và "ảnh sinh"** dùng xen kẽ, kế thừa từ báo cáo gốc. Hai từ đang mang sắc thái hơi khác nhau nên tôi không gộp. Muốn thống nhất một cách gọi thì phải sửa cả báo cáo, không chỉ slide.
