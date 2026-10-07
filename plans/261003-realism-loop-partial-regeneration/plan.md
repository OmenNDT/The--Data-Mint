# Bước 5: 20 ảnh/loại, chỉ sinh lại loại bị ảnh hưởng

Trạng thái: XONG 3/10. Người dùng duyệt 2/10: bước 5 chỉ 2 mục. Plan trước: `plans/261002-1430-realism-knob-sensitivity-screening/`.

## (a) 20 ảnh/loại
- Mặc định n_per_type 50 → 20 ở `realism/loop.py` (CLI), `plant_realism_routes.py` (/api/run), ô nhập trên trang Độ thật.
- Lý do: bộ đề thi cố định + ghép cặp + khoá làm tối theo ca (sửa 2/10) → nhiễu giữa vòng thấp, 20 ca đủ cho cổng.

## (b) Chỉ sinh lại loại bị ảnh hưởng
- `realism/loop_partial.py`:
  - `affected_types(cand, best, selected)`: núm đổi so bản tốt nhất. Núm riêng một loại (`generator_hooks.TYPE_KNOBS`: nứt,
    không thấu, 3 loại rỗ khí) → chỉ loại đó; núm chung (làm tối, nhoè, ControlNet) → mọi loại đã chọn.
  - `plan_cycle(types, n)`: loại cần sinh = bị ảnh hưởng + loại bản tốt nhất chưa có đủ n ca (đọc fixed-jobs.json của nguồn
    bản tốt nhất). Không có bản tốt nhất → sinh hết.
  - `merge(new, best, reused_types)`: ghép pairs + cases: loại sinh lại lấy số đo mới, loại dùng lại lấy nguyên của bản tốt nhất;
    ghi `reused` (eval_run nguồn, danh sách loại).
- `loop.do_cycle`: chỉ sinh `gen_types`; đo; ghép; ghi đè result.json của lượt đo trước khi qua cổng. Lịch sử ghi
  `generated_types`, `reused_types`. Núm thử trùng bản tốt nhất và không thiếu loại → bỏ qua, không sinh.
- Vì sao an toàn: loại dùng lại có núm liên quan KHÔNG đổi, cùng ca, khoá làm tối theo ca → ảnh sinh lại sẽ trùng ảnh cũ
  (đã kiểm 2/10: SD tất định, làm tối tất định theo ca). Cổng thấy số đo y hệt ở loại dùng lại, không nhiễu thêm.

## Nghiệm thu
1. Test đơn vị: affected_types (riêng/chung/không đổi), plan_cycle (thiếu loại, thiếu ca), merge, do_cycle sinh đúng loại.
2. Thật: đặt núm thử nứt đứng 0,3 (núm riêng nứt) → bấm Sinh lại → chỉ sinh 20 ảnh nứt, 3 loại kia dùng lại; cổng xét.
3. Kiểm chứng tất định: sinh lại 1 loại không đổi núm, số đo trùng bản tốt nhất.

## Kết quả (3/10)
- Code: `realism/loop_partial.py` (affected_types, plan_cycle, coverage, merge), `loop.do_cycle`/`do_evaluate(reuse=)`,
  `loop_generate.clamp_n`, `loop_common.other_batch_running` (chuyển từ loop.py, giữ ≤200 dòng); n mặc định 20 (CLI, route, trang).
  Kết quả ghép ghi `reused` + `coverage` (vòng chỉ sinh vài loại vẫn biết bản tốt nhất phủ đủ loại nào).
- Test: `tests/test-realism-loop-partial.py` 11/11; 8 bộ realism + route độ nhạy đều đạt.
- Chạy khô trên trạng thái thật: núm trùng → bỏ qua; núm nứt → chỉ nứt; nhoè (chung) → cả 4; n=40 → cả 4.
- Nghiệm thu bằng click: đặt núm thử nứt đứng 0,3 → vòng 8 chỉ sinh 20 ảnh nứt (~3 phút thay ~8), 3 loại dùng lại có C2ST
  trùng từng chữ số vòng 7. Nứt đứng 0,06→0,235 (ngưỡng 0,25), không chỉ tiêu nào khác rõ → cổng "không khác rõ" (neutral).
- Kiểm tất định: sinh lại 20 ca rỗ khí núm vòng 7 → trùng TỪNG ĐIỂM ẢNH 20/20 với ảnh vòng 7 (lệch tối đa 0). Giả định dùng lại đứng vững.
- Ghi nhận: C2ST một loại ở 20 ca dao động ~±0,1 do nhiễu (vòng 8 nứt: báo 0,718→0,603, ghép cặp trên ca chung +0,048,
  CI −0,12…+0,09). Cổng đã tính nhiễu này; không đọc chênh 0,1 trên trang như cải thiện thật.
- Núm thử còn giữ nứt đứng 0,3 (cổng neutral không lùi núm); bản tốt nhất và sản xuất vẫn là vòng 7.
