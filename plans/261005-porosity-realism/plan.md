# Rỗ khí: tìm nguyên nhân C2ST cao và sửa (5/10)

Trạng thái: XONG 5/10, đã đưa vào sản xuất (best = vòng 11, đặt tay có ghi chú).

## Bối cảnh
Mẻ porosity-200 của người dùng (núm vòng 7): C2ST 0,894. Mức "0,923→0,763" báo ở vòng 7 phần lớn là nhiễu 20 ca
(lấy mẫu 20 từ 177 ảnh: C2ST 0,715–0,916). Vấn đề 3 (lỗ quá tròn, quá đặc) chưa xử lý.

## Đo trước (CPU replay trên ảnh trước-làm-tối, 40 ca)
- Nhoè mép 1,0→3,26: độ lệch tâm 0,75→0,72, không phải nguyên nhân.
- Độ thay đổi độ sâu 0→0,65: không phải nguyên nhân.
- Bộ dò Hessian trên mask sạch đọc đúng hình dạng (0,834 / 0,908) → mất dáng ở khâu tạo ảnh.
- Độ sâu: lỗ đậm + đều giữ dáng (0,805) nhưng C2ST 0,956 → đánh đổi nhạt/mềm vs dáng.
- Làm tối giữ dáng (hồ sơ khoảng cách + vệt bất đẳng hướng, 16 cấu hình): sửa được độ lệch tâm, độ đặc, độ đầy hộp
  nhưng mép gắt (độ dốc +0,16…+0,36 có ý nghĩa), C2ST không giảm → KHÔNG tích hợp (R9).

## Kết quả
- Mask ghép (pore_aspect 2,2–2,6, pore_irregularity 3) + làm tối hiện tại:
  - 40 ca: ΔC2ST ghép cặp −0,090 (CI −0,168…−0,002).
  - 200 ca ghép cặp theo seed mẻ người dùng: C2ST 0,894→0,825; độ lệch tâm +0,098 (có ý nghĩa); độ đặc AUC −0,086 (có ý nghĩa);
    không mục tiêu nào hỏng có ý nghĩa.
- Kiểm bằng mắt: rỗ khí cụm ổn; rỗ khí chuỗi: lỗ sát nhau dính thành dải (giống xỉ/không thấu) → tách núm.
- Tách núm rỗ khí chuỗi: `linear_pore_aspect_min/max`, `linear_pore_irregularity_px` (knobs.py, mask_shaping.py,
  generator_hooks.TYPE_KNOBS, sensitivity_propose swap). Kho SX + thử đặt 1,2769/1,2769/0 = giá trị chuỗi đang dùng.
  Kiểm tất định: 6/6 ca cụm + chuỗi trùng điểm ảnh với trước khi tách. Test: `tests/test-realism-linear-porosity-knobs.py` 5/5.

## Chờ duyệt
Đưa núm thử vào SX: pore_aspect 2,2–2,6, pore_irregularity 3 (porosity + clustered); chuỗi giữ nguyên.
