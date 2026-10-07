# Nhánh F vòng 3: xác nhận `crack_widen_px=1` với n=120 (sau khi người dùng duyệt rollback 2→0, 7/10)

## Bối cảnh
Vòng trước (n=120, báo cáo `fullstack-developer-261007-0910-...`) phát hiện `crack_widen_px=2`
tệ hơn có ý nghĩa thống kê trên KID so `widen=0`, mặc dù detection tốt hơn. Người dùng quyết
rollback về 0 (sản xuất/ứng viên đã đặt 0, nhánh này không ghi `knobs.json`), và yêu cầu xác
nhận mức trung gian `widen=1` với cùng cỡ mẫu.

## Phương pháp
Dùng lại ĐÚNG 120 ca của vòng trước (`crack_widen_confirm.py`, cùng seed rng `20261007` →
cùng case_id/seed/nền, đã kiểm `assert` 3 ca đầu khớp). Chỉ sinh thêm `widen=1` (2 job 80+40,
giới hạn ≤80 ảnh/lần thuê GPU). Dữ liệu `widen0`/`widen2` dùng lại nguyên trạng, không sinh
lại. GPU đang bận bởi vòng lặp gate (`realism-loop:loop-20261007-093616-808`, ~120 ảnh) khi bắt
đầu; script tự chờ/thử lại 30 giây, không can thiệp vòng lặp, được cấp sau khoảng 20 phút.
Không ghi `knobs.json`/`candidate-knobs.json`; truyền `crack_widen_px=1` qua `REALISM_KNOBS`.

## Kết quả

Thật: detection 0,744. n=120 ca/mức mỗi phía (ca còn vùng cả hai phía để so hình dạng: 77 với
widen0, 78 với widen2).

| Mức | detection (n=120) | C2ST | KID | density | coverage |
|---|---|---|---|---|---|
| widen=0 | 0,642 | 0,860 | 1,501 | 0,660 | 0,688 |
| widen=1 | 0,650 | 0,889 | 1,618 | 0,706 | 0,688 |
| widen=2 | 0,675 | 0,897 | 1,772 | 0,728 | 0,688 |

### widen=1 so widen=0 (mốc hiện tại, mức trong sản xuất/ứng viên)

| Độ đo | delta (1 − 0) | CI 95% | Verdict |
|---|---|---|---|
| detection | +0,008 | [0,000, +0,025] | same (chạm biên dưới 0) |
| C2ST | +0,030 | [−0,134, +0,142] | same |
| KID | +0,117 | [−0,027, +0,396] | same |
| density | −0,047 (phí tổn giảm = tốt hơn) | [−0,101, +0,044] | same |
| coverage | 0,000 | [−0,0625, +0,0625] | same |

Không độ đo nào có verdict "worse" hay "better" so mốc 0: CẢ BỐN độ đo hình dạng + detection
đều "same" (CI phủ 0 hoặc chạm biên). widen=1 không làm hình dạng tệ hơn có ý nghĩa, nhưng
cũng không cải thiện detection rõ rệt (CI detection chạm 0,000 ở biên dưới).

### widen=1 so widen=2 (mức đã rollback)

| Độ đo | delta (1 − 2) | CI 95% | Verdict |
|---|---|---|---|
| detection | −0,025 | [−0,058, 0,000] | same (chạm biên trên 0) |
| C2ST | +0,010 | [−0,136, +0,107] | same |
| KID | −0,165 | [−0,352, −0,060] | **better** (toàn âm) |
| density | +0,018 | [−0,056, +0,077] | same |
| coverage | 0,000 | [−0,0625, +0,0625] | same |

widen=1 có KID tốt hơn widen=2 có ý nghĩa thống kê, khớp với nhận định vòng trước rằng widen=2
quá mạnh làm lệch KID. Mất một ít detection so widen=2 (−2,5 điểm %, chạm biên 0, không chắc có
ý nghĩa) nhưng đổi lại hình dạng không còn bị "worse" như widen=2.

## Kết luận: widen=1 có chấp nhận được không?

**CHẤP NHẬN ĐƯỢC** theo tiêu chí ưu tiên SHAPE trước: so mốc hiện tại (widen=0), KHÔNG độ đo
hình dạng nào (C2ST, KID, density, coverage) có verdict "worse" có ý nghĩa thống kê. Đồng thời
widen=1 sửa được đúng vấn đề của widen=2 (KID "better" so widen=2, có ý nghĩa). Tuy nhiên lợi
ích detection so widen=0 là cận biên (CI [0,000; 0,025], không chắc có ý nghĩa thực), nên
widen=1 là một lựa chọn AN TOÀN nhưng KHÔNG có bằng chứng mạnh để ưu tiên hơn giữ nguyên 0 —
quyết định giữa "giữ 0" và "chuyển sang 1" phụ thuộc mức độ người dùng muốn đánh đổi một lợi
ích detection nhỏ, chưa chắc có ý nghĩa, để đổi vài phần trăm KID/C2ST xấu đi không đáng kể
(cũng không có ý nghĩa thống kê theo hướng đó).

## Dữ liệu & tệp liên quan
- Sinh thêm: `output/realism-loop/crack-widen-confirm-120/widen1-part{0,1}/`
- Dùng lại: `output/realism-loop/crack-widen-confirm-120/widen0-part{0,1}/`,
  `.../widen2-part{0,1}/`
- Script + kết quả thô: scratchpad `crack_widen1_confirm.py`, `crack_widen1_result.json`

## Việc chưa làm / câu hỏi còn mở
- CI detection ở cả hai so sánh chạm đúng biên 0 (0,000) — ranh giới "same" và
  "better/worse" mong manh do B=400 bootstrap với n=120 case; có thể tăng B hoặc n nếu cần
  phân định rõ hơn hướng detection.
- Quyết định cuối (giữ 0 hay chuyển 1) nhượng lại người dùng/điều phối; nhánh này không ghi
  knobs, chỉ báo cáo số liệu.

**Status:** DONE
**Summary:** widen=1 xác nhận bằng n=120: KHÔNG có độ đo hình dạng nào tệ hơn có ý nghĩa so
mốc 0 (toàn bộ 4 độ đo + detection đều "same"), và tốt hơn widen=2 có ý nghĩa trên KID. widen=1
CHẤP NHẬN ĐƯỢC theo tiêu chí ưu tiên shape, nhưng lợi ích detection so 0 chỉ cận biên
(CI chạm 0), không phải bằng chứng mạnh để đổi khỏi mốc hiện tại 0.
**Concerns:** CI detection chạm biên 0 ở cả hai so sánh (chưa dứt khoát); quyết định chọn 0 hay
1 cần người dùng quyết, không tự suy ra từ số liệu "same".
