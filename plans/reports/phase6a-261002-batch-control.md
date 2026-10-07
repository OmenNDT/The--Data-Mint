# Phase 6A — batch start/stop với interlock: báo cáo cho main wire

Trạng thái: HOÀN THÀNH (code + test). Chưa wire vào `plant_hmi_routes.py` /
`plant-hmi-app.js` / `plant-hmi.html` — các file đó không nằm trong ownership
của subagent này, main tự gắn.

## Tên chính xác để main wire

- Router Python: `from .plant_batch_control_routes import router as batch_control_router`
  trong `plant_hmi_routes.py`, gắn bằng
  `app.include_router(batch_control_router, prefix="/plant-hmi")` (cạnh
  `setpoint_router`). Router tự có `prefix="/api/control/batch"` nên full path
  cuối cùng là `/plant-hmi/api/control/batch` (+ `/start`, `/stop`, `/audit`),
  khớp đúng spec plan.md mục 6A.
- JS entry: `import { initBatchControl } from './plant-hmi-batch-control.js'`
  trong `plant-hmi-app.js`, gọi `initBatchControl(document.getElementById('batch-control'))`
  (thêm `<section class="card"><h2>...</h2><div id="batch-control"></div></section>`
  trong `plant-hmi.html`, và `<link rel="stylesheet" href="/plant-hmi/static/plant-hmi-batch-control.css">`
  trong `<head>`). Không cần gọi gì khác, module tự poll 5s khi tab visible.
- `asset()` trong `plant_hmi_routes.py` đã whitelist theo đuôi file
  (`.css`/`.js`, thư mục flat) nên 3 file JS + 1 CSS mới tự động phục vụ được,
  không cần sửa whitelist.

## Files tạo (owned)

- `pipeline/plant_hmi/plant_batch_control.py` (65 dòng) — `evaluate_permissives(state)`
  thuần, `blocking_failures(permissives)`.
- `pipeline/plant_hmi/plant_batch_config_whitelist.py` (78 dòng) — `list_configs()`,
  `resolve_config_name(name)` (chống traversal + symlink escape, test có escape thật).
- `pipeline/plant_hmi/plant_batch_process_ops.py` (136 dòng) — `build_start_argv`,
  `start_batch` (systemd-run + poll is-active ≤5s), `stop_batch` (systemctl stop unit
  hoặc SIGTERM pid, chỉ nhận pid nằm trong `live_pids`), `find_unit_for_pid`,
  `find_training_processes`.
- `pipeline/plant_hmi/plant_batch_audit.py` (50 dòng) — append/read JSONL tại
  `pipeline/plant_hmi/control/batch-audit.jsonl` (dir đã có trong `.gitignore`
  sẵn, không cần sửa).
- `pipeline/plant_hmi/plant_batch_control_routes.py` (190 dòng) — router FastAPI
  `GET /api/control/batch`, `POST /start`, `POST /stop`, `GET /audit`; mọi route
  ghi qua `require_trusted_request` (CSRF).
- `pipeline/plant_hmi/static/plant-hmi-batch-control.js` — `initBatchControl(container)`.
- `pipeline/plant_hmi/static/plant-hmi-batch-control-api.js` — fetch wrapper.
- `pipeline/plant_hmi/static/plant-hmi-batch-control-panel.js` — persistent DOM
  controllers (start card + stop row/pid), two-step Arm→Xác nhận/Huỷ.
- `pipeline/plant_hmi/static/plant-hmi-batch-control.css` — dark neumorphism,
  tái dùng token `plant-hmi.css`.
- `pipeline/tests/test-plant-hmi-batch-control.py` — 34 test, mock subprocess/os.kill
  chỉ ở test boundary.

## Hợp đồng API thực tế (field chi tiết hơn plan.md một chút)

`GET /api/control/batch[?config=<name>]` trả:
```
{configs:[{name, path, output_dir, main_silo}],
 permissives:[{code, ok, blocking, message}],
 live:[{pid, unit, config_name, config_path, pilot, start_ts}],
 selected_config_name}
```
`permissives[].blocking=false` chỉ xảy ra với `MAIN_SILO` (cảnh báo, không chặn);
5 permissive còn lại luôn `blocking=true`. Input không rõ (ComfyUI probe `None`,
RAM/swap chưa đọc được) fail-safe thành chặn, không bao giờ coi là "qua".

`POST /start` body `{config: "<name từ list>", pilot, resume, reason}`:
- 400 nếu `config` không whitelist.
- 409 `{error, failures:[...]}` nếu bị permissive chặn.
- 200 `{unit, accepted:true}` nếu thành công; 500 `{error, unit}` nếu
  `systemd-run` chạy nhưng unit không active trong 5s (báo đúng lỗi, không giả vờ OK).

`POST /stop` body `{pid, reason}`: 409 nếu pid không nằm trong batch sống hiện tại
(chặn kill tiến trình lạ); 200 `{accepted:true, unit}` khi dừng qua
`systemctl --user stop <unit>` (ưu tiên) hoặc SIGTERM trực tiếp.

`config` trong `list_configs()` chỉ nhận 2 dạng tên: file trực tiếp trong
`pipeline/config/*.yaml` (name = tên file) hoặc `_generated/*.yaml`
(name = `_generated/<tên file>`); `benchmark/`, `presets/` không được liệt kê
(đúng spec "chỉ trực tiếp trong 2 thư mục").

## Test

- `py_compile` cả 5 file Python: pass.
- `node --check` cả 3 file JS: pass.
- `tests/test-plant-hmi-batch-control.py`: 34/34 pass (permissive thuần, whitelist +
  symlink escape thật, argv list không shell=True, stop refuse pid lạ, route CSRF/409/500/422,
  audit ghi cả accept/refuse).
- Suite hiện có vẫn pass không regress: `test-plant-hmi-alarm-rules` (18),
  `test-plant-hmi-telemetry` (16), `test-plant-hmi-historian` (21),
  `test-plant-hmi-comfyui-progress` (12), `test-plant-hmi-setpoints` (38).

## Chưa làm / để main tự kiểm tra khi live-test

- Chưa gắn router/JS/CSS vào main app (theo đúng phân công, main làm).
- Chưa chạy `systemd-run` thật (user yêu cầu không start/stop batch thật trong
  phiên này). Main cần test thật: start pilot từ HMI, stop giữa chừng, restart
  `tdm-backend` không giết job (rule R8, vì `systemd-run --user` tạo unit độc
  lập ngoài cgroup `tdm-backend.service`).
- `comfy_cfg.get("host")` trong `batch-config.yaml` hiện là `10.86.201.250`
  (không phải `127.0.0.1`) — probe `COMFY_UP` dùng đúng host/port từ config đã
  chọn nên vẫn đúng dù máy đặt tên khác, không ảnh hưởng permissive.
- `NO_TRAINING` dò theo chuỗi `"train_network"` trong argv (khớp
  `kohya-ss/train-*.sh` gọi `train_network.py`); nếu kohya-ss đổi tên script
  sau này, permissive này sẽ không còn thấy — không phát hiện trong phiên này
  vì không có job train nào đang chạy.

## Unresolved questions

- Không có. Toàn bộ đã khớp contract trong plan.md mục 6A; phần mở rộng field
  (`blocking`, `selected_config_name`) chỉ thêm, không đổi tên field đã chốt.

Status: DONE
Summary: Đủ 5 module Python + 4 file static JS/CSS + 1 test file theo đúng ownership; 34 test mới + 5 suite cũ đều pass; chưa wire vào main app và chưa chạy batch thật (đúng phân công, main làm phần đó).

---

## Cập nhật 261002: fix sau code review (code-reviewer-261002-phase6.md, mục 6A)

File mới: `pipeline/plant_hmi/plant_batch_state_builder.py` (108 dòng, tách khỏi
routes để giữ <200 dòng), `pipeline/plant_hmi/plant_batch_training_scan.py`
(32 dòng, tách `find_training_processes` ra khỏi process_ops). Routes giờ import
`state_builder.permissive_state/live_batches/checkpoint_info` thay vì hàm nội bộ
cũ `_permissive_state`/`_live_batches` (main/subagent khác patch test theo tên
module mới nếu có tham chiếu).

- **H2 (start đua nhau, 2 batch cùng GPU):** `ops.start_lock()`
  (`plant_batch_process_ops.py`) = `threading.Lock` + `fcntl.flock` file
  `pipeline/plant_hmi/control/batch-start.lock`. `/start` giữ lock xuyên suốt
  evaluate permissive → `systemd-run` → chờ pid hiện trong
  `find_batch_processes()` (cửa sổ phụ `VISIBLE_WAIT_S=3s` sau khi unit active).
  UI: nút Xác nhận tự khoá (`mode='pending'`, disable Xác nhận+Huỷ) ngay khi
  bấm, chặn double-submit.
- **H3 (stop = SIGTERM nhưng batch không bắt SIGTERM):** unit khởi chạy với
  `-p KillSignal=SIGINT -p TimeoutStopSec=120`; fallback không-unit dùng
  `os.kill(pid, signal.SIGINT)` thay vì SIGTERM. Đã sửa comment sai
  ("checkpoint-save path"). **QUAN TRỌNG, main cần biết:** SIGINT chỉ giúp
  thoát êm hơn (không chết giữa chừng ghi file), KHÔNG tự đảm bảo checkpoint
  mới nhất — `batch-production-main.py` chỉ ghi checkpoint định kỳ
  (`checkpoint_interval` ảnh, dòng 387-388) + một lần "final" sau khi vòng lặp
  chính trả về bình thường (dòng 420-422). `KeyboardInterrupt` (do SIGINT) nếu
  nổ ra giữa một job thì chỉ bị `except Exception` (dòng 392) bắt khi nó là
  `Exception` thường; `KeyboardInterrupt` kế thừa `BaseException` nên lọt qua,
  bỏ luôn đoạn "final checkpoint" (420-422). **Main cần thêm** một
  `try/except KeyboardInterrupt` quanh vòng `while True` (dòng 280) trong
  `run_batch_production`, gọi `checkpoint_manager.save_checkpoint(scheduler.get_state())`
  trước khi re-raise/return, để stop từ HMI không mất quá
  `checkpoint_interval-1` ảnh. Không tự sửa file này (ngoài ownership).
- **M1 (timeout client ngắn hơn worst-case server):** `plant-hmi-batch-control-api.js`
  tách `READ_TIMEOUT_MS=8000` (GET/audit) và `WRITE_TIMEOUT_MS=30000` (start/stop).
- **M5 (swap meter chỉ đọc lúc GET):** thread nền `bc-swap-sampler` trong
  `plant_batch_state_builder.py` gọi `_swap_meter.rate()` mỗi 5s độc lập traffic.
- **M6 (resume mặc định tắt, mất tiến độ im lặng):** GET trả thêm
  `checkpoint: {current_index, total}` khi có checkpoint dở dang; UI tự bật
  `resume` lần đầu thấy checkpoint cho mỗi config (không ghi đè lựa chọn thủ
  công sau đó); confirm text thêm "— sẽ sao lưu checkpoint và chạy lại từ đầu"
  khi resume tắt mà vẫn có checkpoint.
- **M7 (Type=simple active trước exec, unit treo khi fail):** thêm
  `--service-type=exec --collect --expand-environment=no`. Đã kiểm tra
  `systemd-run --version` (systemd 255) hỗ trợ cả 3 cờ, test sống bằng
  `/bin/sleep` xác nhận `Type=exec`, `KillSignal=2`, và `--collect` tự dọn unit
  sau khi xong (không cần start/stop batch thật).
- **L1 (NUL/control char → 500):** `plant_batch_config_whitelist.py` chặn
  control char (`ord < 0x20` hoặc `0x7F`) trước khi chạm `Path`, trả 400 +
  audit như mọi tên không hợp lệ khác; `_resolved_parent_matches` cũng bắt
  thêm `ValueError` phòng hờ.
- **L2 (`$` trong path bị systemd-run expand):** gộp chung vào M7
  (`--expand-environment=no`).
- **L3 (exception ở `_permissive_state` ngoài try → 500 không audit):** toàn
  bộ evaluate-lại-permissive nằm trong khối `try` bọc `ops.start_lock()`, có
  test `test_start_permissive_exception_is_audited_not_unhandled`.
- **L4 (stop theo pid, không khoá start_ts → tái sử dụng pid):** `StopBody`
  nhận thêm `start_ts` (optional, UI luôn gửi từ dòng live đang hiển thị); route
  so khớp với entry sống hiện tại (sai lệch > 2s = từ chối 409, audit, KHÔNG
  gọi `ops.stop_batch`). Thiếu `start_ts` (client cũ) bỏ qua kiểm tra này.

### Test
34 → 48 test trong `test-plant-hmi-batch-control.py` (thêm: argv có đủ cờ
mới, `start_lock` khoá thật chéo tiến trình bằng `flock` thứ hai không chặn
được, SIGINT thay SIGTERM, checkpoint_info 4 case, control-char 400-không-500,
permissive-exception-vẫn-audit, pid-reuse từ chối/bỏ qua). Toàn bộ 8 suite
`test-plant-hmi-*.py` (bao gồm `alarm-state` của 6B và `request-guards` của
main, không đụng tới) = 179/179 pass, không regress.

### Chưa làm / không thuộc ownership subagent này
- Không sửa `batch-production-main.py` (yêu cầu main làm, xem mục H3 ở trên).
- Không chạy start/stop batch thật, không restart service (đúng chỉ thị).
- Không đổi `plant_request_guards.py` (Host allowlist, H4) — main tự làm.

Status: DONE
Summary: Đã fix H2/H3/M1/M5/M6/M7/L1/L2/L3/L4 trong phạm vi 6A; 48 test mới + 179 test toàn bộ suite pass; main cần thêm try/except KeyboardInterrupt + save checkpoint cuối cùng trong `batch-production-main.py` (chi tiết ở mục H3) để stop qua HMI không mất tiến độ ngoài ý muốn.
