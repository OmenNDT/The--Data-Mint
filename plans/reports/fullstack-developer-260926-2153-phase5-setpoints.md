# Phase 5 báo cáo: setpoint reverse control (sampler_steps, SP-601)

## Files tạo/sửa
- `pipeline/plant_hmi/plant_setpoints.py` (mới, 172 dòng): REGISTRY, `resolve()`, store
  `setpoints/setpoints.json` (atomic tmp+os.replace, `fcntl.flock` + `threading.Lock`),
  audit `setpoints/setpoints-audit.jsonl`, `read_store()`, `read_audit()`, `set_setpoint()`.
- `pipeline/plant_hmi/plant_setpoint_routes.py` (mới, 123 dòng): `APIRouter(prefix="/api/control")`
  với `GET /setpoints`, `PUT /setpoints/{key}`, `GET /audit`.
- `pipeline/plant_hmi/plant_telemetry_emitter.py` (sửa, +12 dòng): thêm `emit_config(record)`.
- `pipeline/plant_hmi/plant_telemetry_collector.py` (sửa, +24 dòng): `kind=config` giữ ở
  `self._config[pid][key]` (ngoài buffer), thêm `config_for(pid, start_ts)`, prune 24h.
- `pipeline/batch_manager/batch-production-main.py` (sửa, CRLF giữ nguyên, +14 dòng thực,
  phần diff còn lại 33 dòng là thay đổi cũ có sẵn trước phiên làm việc): resolve ngay sau
  `load_config`, `emit_config` đặt SAU `telemetry.enable(...)` bên trong khối `if`.
- `pipeline/plant_hmi/static/plant-hmi-setpoint-faceplate.js` (mới, 161 dòng) +
  `plant-hmi-setpoint-faceplate.css` (mới, 50 dòng).
- `pipeline/tests/test-plant-hmi-setpoints.py` (mới, 22 test, tất cả pass).

## Tên chính xác để main gắn (wiring)
- Router import: `from plant_hmi.plant_setpoint_routes import router as setpoint_router`
  (đường dẫn module `pipeline/plant_hmi/plant_setpoint_routes.py`, giống cách
  `plant_hmi_routes.py` import `history_router`). Gắn `app.include_router(setpoint_router)`
  cùng chỗ `history_router` (đã có prefix `/plant-hmi` từ `plant_hmi_routes.router`? Không:
  `setpoint_router` tự có prefix `/api/control`, cần include vào app CHUNG với
  `plant_hmi_routes.router` (prefix `/plant-hmi`) — dùng cùng pattern
  `plant_hmi_routes.router.include_router(setpoint_router)` như file đó đã làm với
  `history_router` (dòng `from .plant_history_routes import router as history_router` rồi
  include vào `router` cục bộ). Kết quả path cuối: `/plant-hmi/api/control/setpoints` v.v.
  (đúng theo spec).
- JS init: `import { initSetpointFaceplate } from '/plant-hmi/static/plant-hmi-setpoint-faceplate.js';`
  gọi `initSetpointFaceplate(containerEl)`. CSS: `<link rel="stylesheet" href="/plant-hmi/static/plant-hmi-setpoint-faceplate.css">`.
  Không cần route riêng để phục vụ file tĩnh: `asset()` trong `plant_hmi_routes.py` đã
  whitelist `.js`/`.css` theo tên phẳng.
- Snapshot: KHÔNG cần thêm field nào cho phase 5 (faceplate tự fetch riêng
  `/plant-hmi/api/control/setpoints` mỗi 5s, không qua snapshot builder).

## Kiểm tra
- `py_compile` toàn bộ file Python đã sửa: OK.
- `node --check` file JS mới: OK.
- `file` xác nhận `batch-production-main.py` vẫn CRLF; `python -c ast.parse` (AST) parse thành công.
- Chạy toàn bộ `pipeline/tests/test-plant-hmi-*.py` (bao gồm phase 4 agent song song
  `test-plant-hmi-comfyui-progress.py`): 5 file, tất cả OK, không có test nào fail.
- `git diff --stat` cho `batch-production-main.py`: 45 insertions/7 deletions; xác nhận qua
  `git diff` rằng CHỈ 3 hunk là của tôi (import, resolve block, emit_config sau enable),
  các hunk còn lại là thay đổi có sẵn từ trước phiên (dark_convention switch, set_job,
  generate_mask refactor) đã có trong git status trước khi tôi bắt đầu.

## Ghi chú thiết kế
- `resolve()` không bao giờ raise: env sai định dạng/ngoài khoảng, store hỏng/kiểu sai đều
  rơi xuống nguồn tiếp theo, cuối cùng về `recipe_value` truyền vào.
- `set_setpoint()` raise `ValueError` khi key lạ/không phải int strict (bool/float bị từ
  chối)/ngoài khoảng/reason quá 200 ký tự; route bắt và trả 422 (404 riêng cho key lạ để
  phân biệt với lỗi giá trị).
- PV lấy qua `plant_host_readers.find_batch_processes()` (tiến trình mới nhất còn sống) +
  `collector.config_for(pid, start_ts)`, chặn pid tái dùng bằng `ts >= start_ts - 2`.
- `X-Plant-HMI: 1` bắt buộc cho PUT (403 nếu thiếu); `updated_by`/`who` = `request.client.host`.
- Faceplate JS: state draft cục bộ (`Map`) tách biệt server rows, refresh 5s không đè draft
  chưa lưu hoặc đang chờ xác nhận; hiển thị text lỗi 422/403 nguyên văn từ server.

## Việc chưa làm (ngoài phạm vi sở hữu của tôi)
- Wiring thực tế vào `plant_hmi_routes.py`/`plant-hmi.html`/`plant-hmi-app.js`, restart
  service, đo R9 (pilot 15 vs 25 steps) — thuộc main session theo phân công.

**Status:** DONE
**Summary:** Setpoint registry/store/audit, collector config_for (pid-reuse guard), emit_config,
batch-production-main.py wiring (CRLF preserved), routes (422/403/200), faceplate JS+CSS, 22
tests mới đều pass, toàn bộ test suite plant-hmi hiện có vẫn xanh.
**Concerns/Blockers:** không có; router cần main include vào `plant_hmi_routes.router` (không
phải `app` trực tiếp) để có prefix `/plant-hmi` đúng theo path GET/PUT trong spec.

---

## Cập nhật: fix review findings (H1, H2, L1, L3, L4, M3, M4, L7)

Không đổi wiring/tên export nào (`initSetpointFaceplate`, router path) — vẫn dùng nguyên như trên.

### Files thêm/sửa lần này
- `pipeline/plant_hmi/plant_setpoint_store.py` (mới, 96 dòng): tách persistence (path, lock,
  atomic write+fsync, audit) ra khỏi `plant_setpoints.py` để cả hai file < 200 dòng.
- `pipeline/plant_hmi/plant_setpoints.py` (viết lại, 140 dòng): thêm `default: 25` vào REGISTRY,
  `resolve()` fallback về default khi recipe None/sai kiểu/ngoài khoảng (L4); thêm `clear_setpoint()`
  (M3); dùng `plant_setpoint_store` cho I/O.
- `pipeline/plant_hmi/plant_setpoint_routes.py` (sửa, 169 dòng): `_require_trusted_request()`
  thay `_require_origin_header()` — kiểm tra thêm `Origin` khớp `Host` và `Sec-Fetch-Site` phải
  `same-origin`/`none` (H1); thêm `DELETE /setpoints/{key}` (M3, body `{reason}`); `list_setpoints()`
  gọi `collector.poll()` trước khi đọc PV (L7).
- `pipeline/plant_hmi/plant_telemetry_emitter.py` (sửa, 124 dòng): `emit_config()` cache bản ghi
  mới nhất theo key vào `_last_config`; `job_outcome("ok")` đếm và cứ mỗi 50 lần re-emit toàn bộ
  cache (M4) — không cần sửa `batch-production-main.py`.
- `pipeline/plant_hmi/plant_telemetry_collector.py` (sửa, 197 dòng): `_scan_head_for_config()`
  đọc 64KB đầu file ngay lần đầu thấy file (trước khi quyết định tail/idle-skip), bắt được config
  record mà cách đọc tail cũ bỏ lỡ (M4); `_prune_old_files()` xoá config theo pid còn sống
  (`os.kill(pid,0)`), không theo tuổi nữa (M4).
- JS tách thành 4 file nhỏ (đều <200 dòng, `node --check` OK):
  - `plant-hmi-setpoint-dom.js` (15 dòng): `h()`, `fmtTime()` dùng chung.
  - `plant-hmi-setpoint-api.js` (29 dòng): fetch wrapper + `putSetpoint`/`clearSetpoint`.
  - `plant-hmi-setpoint-row.js` (132 dòng): controller một dòng/knob, DOM dựng 1 lần,
    `update(row)` chỉ sửa textContent/attribute, KHÔNG bao giờ `replaceChildren` phần
    controls trừ khi người dùng bấm Arm/"Về công thức"/Huỷ (H2) — input lý do không bao
    giờ bị dựng lại nên focus/caret/IME còn nguyên; SP box luôn đọc `row.sp` (L1), draft chỉ
    hiện ở ô stepper riêng.
  - `plant-hmi-setpoint-faceplate.js` (62 dòng, giữ tên export `initSetpointFaceplate`):
    orchestration, cache 1 controller/row theo key, không dựng lại card khi poll.
  - CSS: thêm `.sp-btn-clear` cho nút "Về công thức (RECIPE)".
- `pipeline/tests/test-plant-hmi-setpoints.py` (viết lại, 38 test): thêm test H1 (Origin lạ
  403, same-origin 200, không Origin 200, Sec-Fetch-Site cross-site 403), M3 (DELETE xoá +
  audit new=null, 403 thiếu header/Origin lạ), M4 (re-emit đúng sau N job ok, không đếm
  retry/failed, head-scan bắt được config mà tail bỏ lỡ, prune theo pid sống/chết), L3 (audit
  append lỗi vẫn 200/không raise), L4 (recipe None/sai kiểu/ngoài khoảng → default), L7
  (list_setpoints gọi `collector.poll()`). Patch mock trỏ vào `plant_setpoint_store` (đường dẫn
  đã chuyển sang module mới).

### Ghi chú kỹ thuật
- H1: `_require_trusted_request()` giữ nguyên yêu cầu header `X-Plant-HMI: 1`, cộng thêm: nếu có
  `Origin` thì `urlparse(origin).netloc` phải bằng header `Host`; nếu có `Sec-Fetch-Site` thì phải
  là `same-origin`/`none`. Không có 2 header này (curl, cùng-tiến-trình test client) vẫn qua, vì
  đây là header trình duyệt tự gắn, không phải bằng chứng tấn công.
- H2: kiến trúc controller theo key khiến việc "không dựng lại khi có focus" trở thành hệ quả tự
  nhiên: `update()` không bao giờ gọi `replaceChildren` trên phần chứa `<input>` trừ khi mode đổi
  do người dùng bấm nút (khi đó mất focus là hợp lý vì chuyển sang view khác).
- L1: bug gốc do `setDraft()` cũ có giá trị mặc định `value: null` khi tạo draft lần đầu (khi
  gõ lý do trước khi bấm stepper). Kiến trúc mới: `draftValue` khởi tạo `null` nghĩa là "chưa có
  thay đổi", `currentValue()` luôn fallback về `row.sp`; gõ lý do chỉ set biến `reason`, không
  đụng `draftValue`.
- M4: chọn "đếm trong `job_outcome`" theo gợi ý đơn giản nhất trong yêu cầu — không cần sửa
  `batch-production-main.py` (file CRLF nhạy cảm), giảm rủi ro.
- Không đụng `plant_alarm_rules.py`, không phải file phase-4, không restart service, không chạy
  batch, đúng theo giới hạn coordinator giao.

### Kiểm tra
- `py_compile` mọi file Python sửa: OK.
- `node --check` cả 4 file JS: OK.
- Toàn bộ 5 suite `pipeline/tests/test-plant-hmi-*.py` (161 test tổng, gồm 38 test setpoints
  mới + suite song song của phase 4 `test-plant-hmi-comfyui-progress.py`): tất cả OK, không
  regressions.
- Tất cả file Python/JS sửa/tạo đều < 200 dòng.

**Status:** DONE
**Summary:** Đã xử lý H1/H2/L1/L3/L4/M3/M4/L7. Router/export names không đổi. 38 test setpoints
mới + 4 suite khác đều xanh; mọi file <200 dòng; không đụng batch-production-main.py,
plant_alarm_rules.py hay file phase-4.
**Concerns/Blockers:** không có.
