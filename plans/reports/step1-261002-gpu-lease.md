# Bước 1 — Phiếu thuê GPU + vòng lặp chạy qua systemd-run

Status: DONE

## Files mới
- `pipeline/plant_hmi/plant_gpu_lease.py` (105 dòng): `acquire(owner, purpose, pid)`, `release(owner)`,
  `current()`. File `plant_hmi/control/gpu-lease.json` + flock `gpu-lease.lock`, ghi nguyên tử (`os.replace`).
  Phiếu hết hiệu lực khi pid chết HOẶC start_ts không khớp (chống tái dùng pid, slack 2 s như L4). Không TTL.
- `pipeline/tests/test-plant-hmi-gpu-lease.py` (8 test): acquire/release, chủ cũ re-acquire, chủ khác bị từ
  chối, release không phải chủ là no-op, pid chết bị từ chối, phiếu trên pid chết tự hết (`current()` None),
  pid tái dùng (start_ts giả) bị coi là hết hiệu lực, 2 tiến trình OS thật đua `acquire()` (multiprocessing
  spawn) chỉ một thắng.
- `pipeline/plant_hmi/plant_realism_job_status.py` (71 dòng): tách `unit_for/alive/log_tail/job/batch_running`
  ra khỏi `plant_realism_routes.py` để giữ dưới 200 dòng (như mẫu `plant_batch_state_builder.py`).

## Files sửa
- `pipeline/realism/loop.py`: thêm `class GpuBusy`; `_other_batch_running(own_owner=None)` kiểm thêm
  `plant_gpu_lease.current()` (phòng trường hợp find_batch_processes() không thấy); `do_auto(..., owner=None)`
  truyền owner xuống; `main()` xin phiếu bằng `os.getpid()` cho action `cycle`/`auto` trước khi gọi, nhả trong
  `finally`; không xin được ghi lý do rõ ("GPU đang được ... giữ") vào run log, không touch `do_evaluate`,
  `do_propose`, `_gen_config`, `do_generate` (phần của subagent B). File đã có sẵn 297 dòng (bước 2 của agent
  khác thêm `exam_set`/`fixed_jobs`) — vượt 200 dòng nhưng không thuộc phạm vi tôi sửa/modularize lần này.
- `pipeline/plant_hmi/plant_realism_routes.py`: bỏ Popen + `_PROCS`; `/api/run` khởi chạy bằng `systemd-run
  --user --unit=tdm-realism-<run_id> --service-type=exec --collect --expand-environment=no`; unit suy ra tất
  định từ run_id (không bảng trong RAM, sống sót qua restart tdm-backend). `/api/stop` giữ cờ `stop.flag` như
  cũ cho lần gọi đầu; gọi lại sau `STOP_GRACE_S=30s` thì escalate `systemctl --user stop <unit>`. `_job()` khi
  chưa có event dùng `is_unit_active()` (từ `plant_batch_process_ops`) thay cho poll Popen; `_log_tail` đọc
  `journalctl --user -u <unit>` (stdout không còn ra file `loop.log` khi chạy qua systemd-run).
- `pipeline/plant_hmi/plant_batch_control.py`: thêm permissive `GPU_FREE` (blocking), đọc `state["gpu_lease"]`;
  nêu rõ ai giữ, mục đích, từ giờ nào trong message khi chặn.
- `pipeline/plant_hmi/plant_batch_state_builder.py`: `permissive_state()` trả thêm `"gpu_lease":
  gpu_lease.current()`.
- `pipeline/plant_hmi/plant_batch_process_ops.py`: `start_batch()` trả thêm `"pid"` (pid batch vừa thấy trong
  /proc) ở mọi nhánh return, cần cho route xin phiếu bằng đúng pid.
- `pipeline/plant_hmi/plant_batch_control_routes.py`: sau `ops.start_batch()` thành công, xin phiếu GPU owner
  `hmi-batch:<unit>` bằng pid batch, vẫn trong `start_lock()`. Thua đua hiếm (giữa lúc GPU_FREE check và lúc
  này) → dừng batch vừa mở, trả lỗi (đường code đã có, không cần route riêng). Phiếu tự hết khi batch thoát,
  không cần release thủ công lúc stop.
- `pipeline/plant_hmi/plant_snapshot_builder.py`: thêm field gốc `"gpu_lease": gpu_lease.current()`.
- `pipeline/plant_hmi/static/plant-hmi-pid-update.js`: `gpuState(g, lease)` thêm " · giữ: <owner>" vào sub
  text hộp U-901 khi có phiếu.

## Tests đã sửa (ngoài sở hữu, bắt buộc vì đổi contract `start_batch()`)
- `test-plant-hmi-batch-control.py`: thêm 3 test GPU_FREE (rảnh không chặn, bị giữ thì chặn kèm tên chủ trong
  message, thiếu key mặc định rảnh); `test_start_accepted_calls_ops_and_audits` cập nhật mock trả thêm `"pid"`
  + mock `gpu_lease.acquire` (contract `start_batch()` đổi, test phải theo).
- `test-realism-loop.py`: thêm 4 test route (argv systemd-run đúng list không qua shell, 500 khi systemd-run
  lỗi, cờ dừng lần đầu rồi escalate systemctl sau grace).

## Tests: kết quả
- `test-plant-hmi-gpu-lease.py`: 8/8 OK
- `test-plant-hmi-batch-control.py`: 50/50 OK
- `test-realism-loop.py`: 24/25 OK — 1 fail `PairedStatsTest.test_compare_paired_detects_shift_but_not_noise`
  trong `realism/paired_stats.py`, file của Bước 2 (subagent B), tôi không chạm; xác nhận bằng `git status`
  (file untracked, không trong danh sách sở hữu của tôi).
- Toàn bộ `test-plant-hmi-*.py` khác (alarm-rules, alarm-state, batch-compose, comfyui-progress, historian,
  operator-tools, request-guards, setpoints, telemetry): OK, không bị ảnh hưởng.
- `node tests/js/check-alarm-list-buttons.mjs`: "all assertions passed".

## Việc không làm (đúng yêu cầu)
- Không restart service, không start batch/realism loop thật, không commit.

## Vấn đề chưa giải quyết / cần lưu ý
- `realism/loop.py` hiện 297 dòng (vượt chuẩn 200), do cộng dồn 2 bước trong cùng lần làm song song; để
  subagent B hoặc một lượt dọn riêng modularize, tôi chỉ thêm ~25 dòng localized cho phiếu GPU.
- Escalation `systemctl --user stop <unit>` gửi SIGTERM mặc định (không có `KillSignal=SIGINT` cho unit
  realism, khác với batch unit); hợp lý vì đây là lối thoát cuối sau khi cờ `stop.flag` đã được vòng lặp bỏ
  qua quá 30s, nhưng cần nhớ khi debug nếu thấy vòng lặp chết đột ngột lúc escalate.
