# Vòng cải thiện độ thật ảnh sinh (trong Plant HMI, cổng 7860)

Nguồn phát hiện: so sáu tiêu chí hình dạng và biên (độ đặc, góc nghiêng vùng, độ dao động dọc biên, độ lệch tâm, độ đầy
hộp bao, độ dốc tại biên) giữa RIAWELC thật (21.964 mảnh) và output/synthetic, cùng đường ống mặt nạ kernel v2
(Data_Science/stories/datamint/shape-gap-riawelc-vs-synthetic.py). Bộ phân loại trên sáu tiêu chí tách thật/sinh AUC 0,96–0,99.

## 5 vấn đề → núm vặn (mặc định = hành vi cũ)

| # | Vấn đề | Núm vặn | Chỗ sửa |
|---|---|---|---|
| 1 | Mép quá gắt, quá đều | post_depth_min/max, post_modulation, post_modulation_sigma, post_edge_blur_sigma | apply_dark_defect_convention |
| 2 | Nứt chỉ một hướng, mảnh | crack_transverse_share, crack_widen_px | realism/mask_shaping.py |
| 3 | Rỗ khí quá tròn, quá đặc | pore_aspect_min/max, pore_axis_jitter_deg, pore_irregularity_px | realism/mask_shaping.py |
| 4 | Không thấu thẳng tắp | lop_tilt_max_deg, lop_wave_amp_px, lop_gap_max | realism/mask_shaping.py |
| 5 | Giữ chỗ đã giống thật | (không; chốt hồi quy) | realism/issues.py |

Kèm: chặn mặt nạ trống (28 ảnh rỗ khí, 3 lẫn xỉ); lẫn kim loại vẫn trả nền gốc (trước đây hàm thoát sớm, bỏ cả bước trả nền).

## Luật (skill software-plant-hmi)

- R1: núm vặn giải trong tiến trình sinh: env REALISM_KNOBS > realism/state/knobs.json > mặc định; đóng băng cả đợt (R3).
- R2: đợt sinh ghi `realism-knobs-used.json` (giá trị đã nạp + nguồn) vào thư mục đầu ra: đó là PV.
- R4: telemetry vòng lặp không làm hỏng việc; R8: dừng chỉ nhóm tiến trình do vòng lặp mở.

## Pha

- [x] P1 Gói realism: knobs (hai kho: thử / sản xuất, khoá ghi), mask_shaping, post_darkening (tối theo nền), features
      (khớp bảng RIAWELC tới 1e-6), reference, evaluate (ảnh hỏng chỉ loại riêng), issues (một bước mỗi núm mỗi vòng)
- [x] P2 Móc vào bộ sinh: worker mặt nạ (chặn rỗng, tạo hình, làm mềm mép đúng bán kính từng loại), hậu xử lý (lẫn kim
      loại vẫn trả nền; lỗi luôn tối hơn nền khi núm khác mặc định), PV theo thư mục và theo từng ảnh (JSON metadata)
- [x] P3 Vòng lặp: từng bước / tự lặp (dừng khi đạt, khi không còn núm để đổi, khi có đợt sinh khác, hoặc chạm trần);
      ComfyUI sản xuất nếu liên lạc được, không thì 127.0.0.1; số vòng luôn mới; SIGKILL khi dừng quá 60 giây
- [x] P4 /plant-hmi/realism (CSRF chung với tuyến giá trị đặt): 5 vấn đề, sáu tiêu chí, núm thử / sản xuất / PV,
      "Đưa núm thử vào sản xuất", "Sản xuất về mặc định", lịch sử + đồ thị C2ST, 2 nút chạy, ô số ảnh
- [x] P5 Kiểm: tests/test-realism-loop.py 15/15; các bộ thử cũ vẫn qua; hai đợt sinh thật nhỏ (6 và 9 ảnh) để thấy lỗi
      đổi thành sáng và nứt đứng tràn khung, đã sửa rồi xoá dấu vết thử; code-reviewer rà, đã sửa các mục High/Medium;
      tdm-backend khởi động lại khi không có việc đang chạy

## Câu hỏi còn mở

- ComfyUI trong batch-config.yaml là 10.86.201.250:8188, hiện không liên lạc được; vòng lặp đang lùi về 127.0.0.1.
- Tuyến launcher (generation_process_manager) chưa kiểm vòng lặp đang chạy trước khi mở đợt sinh (tệp của người dùng, chưa sửa).

- Ngưỡng mục tiêu lấy theo RIAWELC (phim khác W0003); sau khi có khung đánh dấu W0003 thật có thể đổi mốc.

## Cập nhật 2026-10-02 (phiên Plant HMI)
- Evaluator: thứ tự ảnh cố định (sắp theo đường dẫn) + C2ST lấy trung vị 5 seed. Trước đó cùng 96 ảnh LF cho 0,877 hoặc 0,975
  tuỳ thứ tự worker trả về; nay 3 lần chạy liền đều 0,969.
- Vấn đề 1 thêm cặp LP↔lack_of_fusion (3 mục tiêu biên + vùng chạm lỗi); vòng lặp sinh lại cả lack_of_fusion mặc định.
- Núm mới `controlnet_strength` (vấn đề 1, 0,3–1,0, mặc định = đề xuất = 0,8 = giá trị cũ trong workflow): batch-job-scheduler
  ghi vào node 9 ControlNetApplyAdvanced; vòng lặp không tự đổi (chưa có số đo, R9), người vận hành đặt tay để thử.
- "Đánh giá bộ mới nhất" chọn bộ mới hơn giữa vòng lặp gần nhất và thư mục lần chạy HMI `output/synthetic/<ngày_giờ>_<config>/`.
  Vòng 1 = lô LF 100 (2026-10-02_090143): chưa đạt (độ dốc biên 2,6× thật, dao động biên AUC 0,06; vùng chạm lỗi 0,96 đạt).
- Test: tests/test-realism-lf-controlnet.py 5/5, tests/test-realism-loop.py 15/15.
- (2/10, người dùng duyệt) Vòng lặp tự chỉnh `controlnet_strength`: vòng đầu 0,7 (giá trị đề xuất); độ dốc biên còn trượt
  → −0,05/vòng; vùng chạm lỗi < 0,7 → +0,05 và chặn bước giảm. Kẹp 0,3–1,0. Test 9/9 (test-realism-lf-controlnet.py).
