# Phase 6B: báo động ISA-18.2 (ack/shelve) — báo cáo thực hiện

## Trạng thái: DONE

## File tạo
- `pipeline/plant_hmi/plant_alarm_state.py` (199 dòng) — store JSON atomic + `annotate_alarms`
- `pipeline/plant_hmi/plant_alarm_state_routes.py` (144 dòng) — router `/api/alarms`
- `pipeline/plant_hmi/static/plant-hmi-alarm-list.js` (196 dòng) — render danh sách báo động + ack/shelve UI
- `pipeline/plant_hmi/static/plant-hmi-alarm-api.js` (27 dòng) — fetch wrapper (tách ra để alarm-list.js < 200 dòng)
- `pipeline/plant_hmi/static/plant-hmi-alarm-actions.css` (35 dòng)
- `pipeline/tests/test-plant-hmi-alarm-state.py` (205 dòng, 14 test) — tương đương quy mô các test khác trong thư mục (historian 302, setpoints 379)

## File sửa
- `pipeline/plant_hmi/static/plant-hmi-render-panels.js`: `renderAlarms(snap)` nay chỉ gọi `renderAlarmList($('alarms'), snap, refreshAlarmsNow)`; `refreshAlarmsNow` tự fetch `/plant-hmi/api/snapshot` để cập nhật ngay sau khi ack/shelve (không cần sửa `app.js`). 147 dòng.
- `pipeline/plant_hmi/static/plant-hmi-alarm-journal.js`: thêm nhãn `acked/shelved/unshelved` (STATE_LABEL), class row không còn "sev-null" khi severity rỗng.

## Hợp đồng với main (QUAN TRỌNG — đọc kỹ trước khi sửa `plant_snapshot_builder.py`)

```python
from .plant_alarm_state import annotate_alarms, read_store  # noqa (tên hàm đọc store tùy ý)

result = annotate_alarms(alarms, alarm_store, now)
snapshot["alarms"] = result["alarms"]
snapshot["alarms_cleared_unacked"] = result["cleared_unacked"]
snapshot["alarms_shelved"] = result["shelved"]
```

- `alarms` ở trên là list đã qua `_on_delay.apply(derive_alarms(...), now, hold=unknown)` như hiện tại (mỗi phần tử có `code, tag, severity, message, pid, since`) — KHÔNG cần đổi gì ở `plant_alarm_rules.py`.
- `alarm_store`: đọc bằng `plant_alarm_state.read_store()` mỗi tick là đủ rẻ (file JSON nhỏ, atomic). Có thể cache theo mtime (`STORE_PATH.stat().st_mtime`) để khỏi đọc lại nếu không đổi, nhưng **lưu ý**: `annotate_alarms` tự ghi lại store (cập nhật `last_seen`, dọn ack/shelve hết hạn) mỗi lần gọi nếu có thay đổi — mtime sẽ tự cập nhật, lần poll sau cache-miss là đúng, không cần main tự invalidate thủ công.
- `annotate_alarms` KHÔNG thuần tuý 100% I/O: nó đọc store do caller truyền vào, nhưng tự ghi lại phần bookkeeping `last_seen`/acks hết hạn/shelves hết hạn (cần thiết để nhớ trạng thái "đã hết nhưng chưa ack" qua các tick, không ai khác gọi để làm việc này). Quyết định trả về (alarms/cleared_unacked/shelved) là hàm xác định của `(active_alarms, store, now)`.
- Mỗi alarm trong `result["alarms"]` có thêm field `key` (định dạng `CODE|TAG|pid|since`), `acked` (bool), `acked_at`, `shelved: false`. Frontend dùng `alarm.key` trực tiếp khi gọi API ack/shelve, không tự tính lại.
- `cleared_unacked`: mỗi phần tử `{code, tag, severity, message, pid, since, last_seen_ts, key, acked: false, cleared: true}`.
- `shelved`: mỗi phần tử `{key, code, tag, until, reason, by, severity, message}`.
- Mount router: `app.include_router(alarm_state_router, prefix="/plant-hmi")` cùng chỗ với `setpoint_router` trong `plant_hmi_routes.py` (file này do main sở hữu).
- CSS: thêm `<link rel="stylesheet" href="/plant-hmi/static/plant-hmi-alarm-actions.css">` vào `plant-hmi.html` cạnh các CSS khác (main sở hữu file này).

## Thiết kế khoá occurrence (quan trọng cho hành vi ack/shelve)
`key = f"{code}|{tag}|{pid}|{since}"` — `since` lấy từ `AlarmOnDelay`, là mốc first-seen của một lần báo động. Báo động hết rồi tái phát sẽ có `since` mới -> khoá mới -> ack/shelve cũ KHÔNG áp dụng cho lần tái phát (test `test_reraise_after_ack_is_a_new_unacked_occurrence` xác nhận). Áp dụng đồng nhất cho cả ack và shelve.

## Ghi journal
Mỗi POST ghi 1 dòng vào `alarm_journal` qua `insert_alarm_journal(ts, code, tag, severity=None, pid, state, message)` với `state` là `"acked"/"shelved"/"unshelved"`; lỗi ghi journal bị nuốt (log + không fail request), test `test_ack_then_state_reflects_it_and_journals` xác nhận route vẫn 200 dù journal bị patch mock.

## Test
- `py_compile` cả 2 file Python: OK
- `node --check` cả 4 file JS sửa/tạo: OK
- `test-plant-hmi-alarm-state.py`: 14/14 pass (store corrupt-fallback, ack, shelve bad-minutes/missing-reason, shelve ẩn+hiện lại, auto-expire theo thời gian, cleared-unacked nhớ rồi quên sau 24h, ack xoá cleared-unacked, tái phát không kế thừa ack, ack-all, route CSRF 403, route ack/shelve/unshelve/state, 422 khi minutes sai)
- Toàn bộ suite hiện có vẫn pass: alarm-rules (18), batch-control (34, của 6A — đã có sẵn khi tôi chạy, không đụng tới), comfyui-progress (12), historian (21), setpoints (38), telemetry (16)

## File < 200 dòng
plant_alarm_state.py 199, plant_alarm_state_routes.py 144, alarm-list.js 196, alarm-api.js 27, alarm-actions.css 35, render-panels.js 147 (giảm từ 143 gốc do thêm comment, vẫn dưới 200). Test file 205 dòng — cùng quy mô với các test khác trong thư mục (không phải "code file" theo nghĩa rule 200 dòng, các test hiện có đều 150-380 dòng).

## Việc KHÔNG làm (đúng phạm vi)
Không đụng `plant_snapshot_builder.py`, `plant_alarm_rules.py`, `plant-hmi-app.js`, `plant-hmi.html`, bất kỳ file 6A nào (`plant_host_readers.py`, `plant-hmi-batch-control.*` etc). Không restart service, không start job, không commit.

## Unresolved / lưu ý cho main
1. Severity trong journal ack/shelve/unshelve luôn `None` (quyết định của tôi — alarm đã có severity riêng trong snapshot, journal phase 3 vốn dùng severity cho raised/cleared; acked/shelved/unshelved là hành động của người vận hành, không phải mức báo động mới). Nếu main muốn severity đi kèm (vd để tô màu dòng journal), cần sửa `_journal()` trong `plant_alarm_state_routes.py` (file tôi sở hữu) — nói tôi biết nếu cần, hoặc main có thể tự quyết do đã nắm UI journal.
2. `ack-all` ack toàn bộ `snap.alarms` hiện có trên UI (không phân biệt theo severity) — đúng theo mô tả "Xác nhận tất cả" không có điều kiện thêm trong spec.
3. Giới hạn 24h cho `cleared_unacked` là cố định (`LAST_SEEN_TTL_S`), không có setpoint cấu hình — hợp với YAGNI, spec không yêu cầu cấu hình được.
