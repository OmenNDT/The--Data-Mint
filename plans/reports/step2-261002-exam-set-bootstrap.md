# Bước 2: Bộ đề thi cố định + bootstrap ghép cặp

Plan: `plans/261002-1006-realism-loop-safety-paired-gate/plan.md` — Bước 2 (subagent B).

## Tóm tắt

Scheduler nhận khoá `generation.fixed_jobs`, dùng đúng danh sách ca, không random/shuffle; vắng khoá
hành vi cũ y nguyên (test xác nhận). `realism/exam_set.py` tạo bộ đề thi 240 ca (6 loại × 40, seed
20261002) tất định, ghi `realism/state/exam-set.json`. `realism/loop.py._gen_config` sinh lại trên bộ
đề thi (kẹp n_per_type ≤ 40), ghi `fixed-jobs.json` cạnh ảnh ra để `evaluate.py` ghép case_id theo
job_id, không cần sửa `batch-production-main.py`. `realism/paired_stats.py` (mới, 181 dòng): bootstrap
theo ca B=1000, `compare_paired` ghép cặp theo case_id chung. Kiểm chứng tất định THẬT trên ComfyUI
đang chạy: sinh lại 2 ca giống nhau 2 lần, ảnh và mask BẰNG NHAU TUYỆT ĐỐI (max_abs_diff=0).

## File đã sửa/tạo

- `pipeline/batch_manager/batch-job-scheduler.py` (sửa, +37 dòng, CRLF giữ nguyên, xác nhận bằng `file`):
  `_build_job_list` tách thành `_build_fixed_job_list` (mới, đọc JSON, job_id=index, mang case_id) và
  `_build_random_job_list` (hành vi cũ, nguyên văn).
- `pipeline/realism/exam_set.py` (mới, 107 dòng): `build_exam_set`, `load_exam_set`, `subset`, CLI.
  6 loại lấy từ `evaluate.PAIRS` (sorted set) = clustered_porosity, crack, lack_of_fusion,
  lack_of_penetration, linear_porosity, porosity.
- `pipeline/realism/evaluate.py` (sửa, 143→177 dòng): `_job_id_of`, `load_case_map` (đọc
  `<source>/fixed-jobs.json`); `measure()` nhận case_id tuỳ chọn (tương thích args 2-tuple cũ);
  `compare()` trả thêm `cases` (list theo case_id, 6 tiêu chí + hit) bên cạnh `pairs` cũ không đổi;
  `run()` ghi `result.json` có thêm khoá `"cases"`.
- `pipeline/realism/paired_stats.py` (mới, 181 dòng): `bootstrap_targets`, `bootstrap_criteria`,
  `compare_paired` — API chi tiết ở dưới.
- `pipeline/realism/loop.py` (sửa, cùng file với bước 1 của subagent A — không đụng phần lease của họ):
  thêm `_round_cases` (lấy ca từ bộ đề thi, kẹp n, tự tạo bộ đề thi lần đầu), `_gen_config` dùng
  `fixed_jobs` thay `defect_distribution` random, ghi bản sao `fixed-jobs.json` vào thư mục ảnh ra;
  `do_generate`/`do_cycle` cập nhật theo chữ ký mới của `_gen_config` (trả thêm `n_clamped`). Không sửa
  `do_auto`, `main()`, lease code (đã thấy `GpuBusy`/`gpu_lease.acquire` của subagent A khi đọc lại file
  — giữ nguyên, không đụng).
- `pipeline/tests/test-realism-loop.py` (sửa, thêm ~150 dòng): `SchedulerFixedJobsTest`,
  `ExamSetTest`, `EvaluateCaseRowsTest`, `PairedStatsTest`.

Không sửa `batch-production-main.py` (đúng yêu cầu: đọc, không sửa). case_id không cần vào metadata
JSON vì `fixed-jobs.json` (bản sao cạnh ảnh ra) đã đủ để `evaluate.load_case_map()` ghép job_id→case_id.

## API cho bước 3 (cổng nghiệm thu)

```python
from realism import exam_set, paired_stats

exam_set.build_exam_set(backgrounds_dir, types=None, per_type=40, seed=20261002)  # một lần
exam_set.load_exam_set(path=None) -> dict
exam_set.subset(types, n, exam=None) -> list[case]

# result: dict từ evaluate.run() (có "pairs" VÀ "cases")
paired_stats.bootstrap_targets(result, B=1000, seed=0)
    -> [{"pair", "crit", "stat", "label", "measured", "n", "ci_low"?, "ci_high"?}, ...]
    # một dòng / mục tiêu issues.py, CI 95% của giá trị đo trên MỘT vòng (không ghép cặp)

paired_stats.bootstrap_criteria(result, B=1000, seed=0)
    -> {pair: {"n", "crit": {k: {"median","ci_low","ci_high","auc"?}}, "c2st"?: {"value","ci_low","ci_high"}}}
    # CI 95% trung vị + AUC từng tiêu chí, và C2ST, theo cặp loại — dùng cho "C2ST TB các loại đang nhắm (có CI)"

paired_stats.compare_paired(prev, new, B=1000, seed=0)
    -> {label: {"pair","crit","stat","prev","new","delta","n_common","ci_low"?,"ci_high"?,"significant"?}}
    # so 2 vòng trên ca CHUNG (case_id); significant = CI 95% của delta không chứa 0
    # bước 3: "tốt hơn rõ" = significant và delta đúng hướng mục tiêu; "tệ hơn rõ" = significant và
    # delta sai hướng ở mục tiêu bản tốt nhất đang đạt; còn lại = "không khác"
```

`issues.ISSUES`/`issues.value_of` không đổi — `paired_stats` tự tính `measured` từ `result["pairs"]`
nếu có (vòng thật luôn có), tự tính thẳng từ `result["cases"]` nếu không (test đơn vị, hoặc vòng thiếu
pairs vì lý do khác) — không phụ thuộc cứng vào cấu trúc `pairs`.

Score tổng cho bước 3 (gợi ý, chưa code): `n_pass = sum(issues.evaluate(result) status=="pass")`,
C2ST trung bình các cặp đang nhắm lấy từ `bootstrap_criteria(result)[pair]["c2st"]["value"]` cùng CI.

## Kiểm chứng tất định (ComfyUI THẬT, không mock)

ComfyUI 127.0.0.1:8188 đang chạy (RTX 3090, không ai giữ phiếu GPU, không batch khác đang chạy).
Sinh 2 ca cố định (loại crack, seed 1166519849 và 2529486474) hai lần vào
`output/realism-loop/determinism-check-<ts>/{run1,run2}` qua `batch-production-main.py --config ... --resume`
(cwd `batch_manager/`, đúng cách `loop.do_generate` gọi). Kết quả: `max_abs_diff=0, mean_abs_diff=0.0`
cho cả 2 ảnh và 2 mask; metadata JSON seed khớp đúng giá trị trong fixed_jobs. Đã xoá thư mục tạm sau
khi đo.

## Test

Chạy toàn bộ: `pipeline/.venv/bin/python tests/test-realism-loop.py` → 25/25 OK (gồm 7 test mới của
tôi + các test lease/systemd-run của subagent A, không xung đột).
`tests/test-realism-lf-controlnet.py` → 9/9 OK. 10 file `tests/test-plant-hmi-*.py` → tất cả OK (bao
gồm `test-plant-hmi-gpu-lease.py` của subagent A).

## Vấn đề/quyết định cần lưu ý

- `n_per_type` mặc định CLI vòng lặp vẫn là 50 (giữ nguyên, không đổi hành vi CLI cũ) nhưng bị KẸP về
  per_type của bộ đề thi (40) trong `_gen_config`/`_round_cases`; `do_generate` log sự kiện
  `n_clamped` khi có kẹp. Nếu muốn n>40, phải tăng `per_type` khi tạo lại bộ đề thi (gọi
  `exam_set.build_exam_set(..., per_type=...)`), KHÔNG tự mở rộng ngầm (giữ tất định).
- `paired_stats.bootstrap_criteria` chạy C2ST lại B lần mỗi cặp (mặc định 6 cặp × 1000) — có thể chậm
  (c2st tự fit hồi quy logistic 5-fold mỗi lần); bước 3 nên gọi với B nhỏ hơn (vd 200) cho vòng
  tương tác qua HMI, dùng B=1000 cho báo cáo cuối.
- Exam set production đã được tạo THẬT ở `realism/state/exam-set.json` (240 ca, không phải dữ liệu
  test) như một phần của việc chạy kiểm chứng tất định — đây đúng là hành động "tạo một lần" plan yêu
  cầu, không phải side effect ngoài ý muốn.

## Bước 3: Cổng nghiệm thu, giữ bản tốt nhất, tự lùi

Plan: cùng file, mục "Bước 3". Bắt đầu sau khi subagent A báo xong bước 1 (lease/systemd-run) và không
còn sửa `realism/loop.py`; đã đọc lại file trước khi sửa, xác nhận `GpuBusy`/`gpu_lease.acquire/release`
còn nguyên, không đụng.

### Thiết kế đã làm theo đúng quyết định của điều phối viên

1. Điểm vòng = `(n_pass, mean_c2st)` — `loop_gate.score(result, types)`: n_pass từ `issues.evaluate`,
   C2ST trung bình các cặp đang nhắm (lọc theo `rec["types"]`, lấy thẳng `pairs[*]["c2st"]` đã tính sẵn,
   không bootstrap lại — rẻ). So sánh dùng n_pass trước (tắt/mở ngay nếu khác), C2ST có CI (bootstrap
   theo ca, `loop_gate._mean_c2st_delta`, B=200 trong vòng lặp/HMI qua `GATE_B`, gọi lại B=1000 cho báo
   cáo cuối nếu cần bằng cách truyền `B=1000` vào `gate(rec, B=1000)`).
2. `loop_gate.gate(rec)` sau mỗi `do_evaluate`/`do_cycle` (gọi từ `_record` trong `loop.py`, trước khi
   ghi dòng lịch sử): so bản mới với `best.json`, không phải vòng ngay trước.
   - accept: không mục tiêu "phải giữ" nào trượt, VÀ điểm tốt hơn rõ (n_pass tăng, hoặc n_pass bằng mà
     C2ST giảm rõ theo CI) → ghi best.json, `tuning_memory.clear()` các núm vừa đổi.
   - neutral: không khác rõ, núm thử GIỮ NGUYÊN (không lùi) → ghi "không cải thiện"; hai dòng neutral
     liên tiếp (`loop._two_consecutive_neutral`) làm `do_auto` dừng.
   - reject: một mục tiêu "phải giữ" (đang đạt ở bản tốt nhất, `loop_gate._must_keep_targets` — THAY hẳn
     vấn đề 5 cứng, bao trùm luôn các mục tiêu của vấn đề 5 vì chúng cũng nằm trong `issues.evaluate`)
     bị trượt HOẶC điểm tệ hơn rõ → núm thử LÙI về đúng núm bản tốt nhất (`knobs.write_many(...,
     store="candidate")`), `tuning_memory.record_rejection` ghi hướng.
   - Vòng không có `result["cases"]` (bộ ngẫu nhiên cũ, không phải bộ đề thi) không so được: nếu best
     cũng chưa có "cases" → neutral kèm lý do; vòng CÓ "cases" đầu tiên tự thành best ("mốc mới: bộ đề
     thi"), không so sánh ghép cặp.
3. `realism/state/best.json` `{iter, eval_run, knobs, score, ts}` — `loop_gate.read_best()/_write_best()`.
   Promote (`plant_realism_routes.promote`) đổi hẳn sang dùng núm best, không dùng candidate nữa; 409 nếu
   chưa có best; nhãn lý do `"đưa bản tốt nhất (vòng N) vào sản xuất"` ghi vào audit log.
4. Lịch sử mỗi dòng thêm `decision`/`reasons`/`compared_to`. HMI: `plant-hmi-realism-issues.js` thêm cột
   "Cổng" (✓ mốc / ✓ tốt hơn / = không đổi / ✗ bị loại, title = lý do) + đường nét đứt "tốt nhất tới lúc
   đó" trên đồ thị C2ST; `plant-hmi-realism-knobs.js` hiện "Bản tốt nhất: vòng N · đạt n/5 · C2ST TB x"
   cạnh nút promote, nút promote đổi nhãn theo vòng best, khoá (disabled) khi chưa có best.
5. `realism/loop.py` (297→192 dòng) chẻ thành `loop_common.py` (36, hằng số/ngoại lệ/`history`/
   `candidate` dùng chung), `loop_generate.py` (100, `_gen_config`/`do_generate`), giữ nguyên
   `loop_gate.py` (161, mới) và `tuning_memory.py` (80, mới). Không đổi hành vi sinh ảnh/lease ngoài
   việc thêm gọi cổng nghiệm thu trong `_record`.

### File đã sửa/tạo (bước 3)

- `pipeline/realism/loop_common.py` (mới, 36 dòng), `pipeline/realism/loop_generate.py` (mới, 100
  dòng), `pipeline/realism/loop_gate.py` (mới, 161 dòng), `pipeline/realism/tuning_memory.py` (mới, 80
  dòng), `pipeline/realism/loop.py` (viết lại, 192 dòng — vẫn `python3 -m realism.loop ...` y nguyên).
- `pipeline/plant_hmi/plant_realism_routes.py` (179 dòng): `/api/state` thêm `"best"`; `/api/promote`
  dùng best.json, 409 khi chưa có.
- `pipeline/plant_hmi/static/plant-hmi-realism-issues.js` (94 dòng), `plant-hmi-realism-knobs.js` (70
  dòng), `plant-hmi-realism-app.js` (88 dòng) — cả ba vẫn dưới 200 dòng, dữ liệu không tin cậy đều qua
  `esc()` (title lý do, nhãn best).
- `pipeline/tests/test-realism-loop.py`: thêm `GateTest`, `TuningMemoryTest`, `AutoStopTest` (14 test
  mới), sửa `KnobDir.setUp` cô lập `loop_gate.BEST_PATH/STATE` và `tuning_memory.PATH` vào thư mục tạm,
  sửa `test_writes_need_csrf_header_and_valid_values` theo ngữ nghĩa promote mới (409 trước khi có best,
  200 sau khi ghi best.json giả).

### Quyết định kỹ thuật cần lưu ý

- `must_keep` dùng `issues.evaluate` trên `result["pairs"]` (toàn bộ ảnh đã đo, không bootstrap) để biết
  mục tiêu nào "đang đạt ở best" và có còn đạt ở vòng mới không — tất định, không phụ thuộc nhiễu bootstrap
  (plan dùng từ "PASSES"/"now fails", không nói "significant", nên cố ý không bootstrap bước này).
  `score_worse`/`score_better` MỚI dùng CI (qua `_mean_c2st_delta`, bootstrap theo ca).
- `_mean_c2st_delta` tính C2ST thật (không phải giá trị đã lưu sẵn trong `pairs[*]["c2st"]`) từ
  `result["cases"]`, ghép theo case_id chung mỗi cặp, B lần. Tốn: B × 2 × (số cặp đang nhắm) lần fit
  hồi quy logistic 5-fold; với B=200 và ~4 cặp ≈ 1600 lần fit — vài giây, chấp nhận được cho vòng
  lặp/HMI tương tác (đã dùng GATE_B=200 theo quyết định điều phối viên).
- `tuning_memory`: 1 lần bị loại theo một hướng → nhớ nửa bước CÙNG hướng; nửa bước đó bị loại tiếp
  (cùng hướng) → đổi hướng, về bước đầy đủ; nếu hướng đã đổi mà VẪN bị loại → nửa bước tiếp (không lặp
  đổi hướng vô hạn — phần này plan không nói rõ, tự quyết định hợp lý để tránh dao động mãi).
  `apply_to_proposal` chỉ áp bộ nhớ cho núm mà `issues.propose` ĐANG đề xuất đổi (không tự áp khi
  không vấn đề nào gọi tới núm đó nữa).
- `do_propose` giữ dùng kết quả đo GẦN NHẤT (có thể là vòng vừa bị loại) để biết mục tiêu nào còn trượt,
  dù núm thử đã lùi về best — propose không quan tâm núm nào tạo ra kết quả, chỉ quan tâm mục tiêu nào
  còn trượt; hành vi này giữ nguyên như trước bước 3 (chưa thấy plan yêu cầu đổi).
- `promote` trả 409 khi chưa có best.json (trước đây luôn 200 vì promote candidate luôn có giá trị, kể
  cả mặc định) — thay đổi hành vi API có chủ ý theo yêu cầu "Đưa núm thử vào sản xuất" → "Đưa bản tốt
  nhất vào sản xuất"; test cũ đã sửa theo (ghi best.json giả trước khi gọi promote).

### Test (bước 3)

`tests/test-realism-loop.py`: 36/36 OK (22 cũ + 14 mới: `GateTest` ×6 — mốc đầu tiên/accept/neutral/
reject theo điểm/reject theo must-keep/non-exam bị bỏ qua; `TuningMemoryTest` ×4 — nửa bước/đổi hướng/
clear/không bộ nhớ không đổi gì; `AutoStopTest` ×1 — 2 neutral liên tiếp dừng; sửa
`test_writes_need_csrf_header_and_valid_values` theo promote mới). `tests/test-realism-lf-controlnet.py`
9/9 OK. 11 file `tests/test-plant-hmi-*.py` (gồm `gpu-lease` của subagent A) đều OK.
`node tests/js/check-alarm-list-buttons.mjs` → pass (không liên quan trực tiếp realism, chạy theo yêu
cầu). Không khởi động dịch vụ, không chạy vòng lặp thật, không commit.

**Status:** DONE
**Summary:** Bước 2 và bước 3 xong. Scheduler/exam_set/evaluate/paired_stats (bước 2) + loop_gate/
tuning_memory/loop tách module/promote dùng best + HMI hiện quyết định (bước 3). 36 test
test-realism-loop.py + 9 lf-controlnet + 11 plant-hmi suite + 1 JS test đều pass. Kiểm chứng tất định
thật trên ComfyUI (bước 2) cho kết quả bit-identical.
**Concerns:** Không có blocker. Hai điểm tự quyết định ngoài phạm vi plan nói rõ (ghi trên): hành vi
`tuning_memory` sau lần đổi hướng thứ hai (tự chọn nửa bước tiếp, tránh dao động vô hạn), và `do_propose`
vẫn dùng kết quả đo gần nhất bất kể núm đã lùi hay chưa. `bootstrap_criteria`/B=1000 vẫn chậm cho báo
cáo cuối như đã ghi ở bước 2 — bước 3 dùng GATE_B=200 riêng, không ảnh hưởng.
