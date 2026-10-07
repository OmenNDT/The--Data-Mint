"""Bộ điều khiển vòng cải thiện độ thật: chạy như một tiến trình riêng, HMI (tuyến /plant-hmi/realism) mở và theo dõi.

    python3 -m realism.loop --action evaluate|propose|cycle|auto [--n-per-type 20] [--types crack,porosity,...]
                            [--max-iter 5] [--run-id loop-...]

evaluate: đo bộ mới nhất (vòng gần nhất, chưa có thì output/synthetic) → một dòng lịch sử, qua CỔNG NGHIỆM THU
           (loop_gate.gate, bước 3): nhận/giữ nguyên/loại so với bản tốt nhất đã có trên bộ đề thi cố định.
propose:  đề xuất núm theo 5 vấn đề từ kết quả mới nhất (có áp bộ nhớ hướng vặn tuning_memory), ghi vào KHO NÚM
           THỬ (candidate; sản xuất không đổi).
cycle:    sinh N ảnh mỗi loại với núm thử (truyền qua env REALISM_KNOBS) vào output/realism-loop/iter-XX, đo, qua
           cổng nghiệm thu; vòng bị loại tự lùi núm thử về bản tốt nhất.
auto:     lặp [propose → cycle] tới khi không còn vấn đề trượt, không còn núm để đổi, 2 vòng liên tiếp "không cải
           thiện", hoặc chạm --max-iter.
Dừng: tệp state/stop.flag (HMI tạo). Sinh ảnh gọi đúng batch-production-main.py với cấu hình riêng
(config/_generated/realism-iter-XX.yaml, điểm lưu riêng: không đụng điểm lưu của đợt sản xuất chính). Máy ComfyUI:
của cấu hình sản xuất nếu liên lạc được, không thì 127.0.0.1:8188; máy đã dùng ghi vào lịch sử.
"""
import argparse
import json
import os
import time
from pathlib import Path

from . import evaluate, issues, knobs, loop_gate, loop_generate, loop_partial, sensitivity_propose, tuning_memory
from .loop_common import (BASELINE, DEFAULT_TYPES, GpuBusy, HISTORY, STATE, STOP, Stopped, candidate, history,
                          other_batch_running as _other_batch_running)
from .runlog import RunLog, read_json

PIPELINE = loop_generate.PIPELINE


def _record(it, source, eval_run, log, extra=None):
    result = read_json(eval_run, "result.json")
    ev = issues.evaluate(result)
    st = [i["status"] for i in ev]
    rec = {"iter": it, "ts": time.time(), "source": str(source), "eval_run": eval_run,
           "knobs": (result.get("knobs_pv") or {}).get("knobs") if result else None,
           "issues": {i["id"]: i["status"] for i in ev},
           "c2st": {p["pair"]: p["c2st"] for p in (result or {}).get("pairs", [])},
           "all_pass": "fail" not in st and "pass" in st, **(extra or {})}  # vấn đề "chưa đo" (na) không chặn
    rec = loop_gate.gate(rec)                                   # cổng nghiệm thu (bước 3): quyết định + tác dụng phụ
    STATE.mkdir(parents=True, exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.emit("iteration", **{k: rec[k] for k in ("iter", "issues", "all_pass", "c2st", "decision", "reasons")})
    return rec


class RunLogProxy(RunLog):
    """Kết quả đo ghi vào thư mục riêng của lượt đo, còn tiến độ báo chung vào nhật ký vòng lặp."""

    def __init__(self, parent, run_id):
        super().__init__(run_id)
        self.parent = parent

    def emit(self, kind, **fields):
        self.parent.emit(kind, **fields)


def latest_source():
    """"Bộ mới nhất": bộ ảnh mới hơn giữa vòng lặp gần nhất và lần chạy HMI mới nhất (mỗi lần Start từ HMI ghi vào
    thư mục riêng output/synthetic/<YYYY-MM-DD_HHMMSS>_<config>/). Không có cả hai thì cả silo (output/synthetic)."""
    h = history()
    cands = [p for p in BASELINE.glob("20*") if p.is_dir()]
    if h and Path(h[-1]["source"]) != BASELINE:
        cands.append(Path(h[-1]["source"]))
    cands = [p for p in cands if p.is_dir()]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else BASELINE


def do_evaluate(log, source=None, it=None, extra=None, reuse=None):
    h = history()
    source = Path(source or latest_source())
    it = it if it is not None else (h[-1]["iter"] if h and Path(h[-1]["source"]) == source else len(h))
    eval_run = f"{log.run_id}-eval-{it:02d}"
    evaluate.run(source, eval_run, log=RunLogProxy(log, eval_run))
    if reuse and reuse[0]:                                     # bước 5: ghép số đo loại dùng lại trước khi qua cổng
        loop_partial.merge_into_eval_run(eval_run, *reuse)
    return _record(it, source, eval_run, log, extra)


def do_propose(log, who="vòng lặp"):
    h = history()
    # Vòng vừa bị loại: núm thử đã lùi về bản tốt nhất, nên đề xuất phải dựa trên số đo của bản tốt nhất.
    best = loop_gate.read_best() if h and h[-1].get("decision") == "rejected" else None
    run = (best or {}).get("eval_run") or (h[-1]["eval_run"] if h else None)
    result = read_json(run, "result.json") if run else None
    if result is None:
        raise RuntimeError("chưa có kết quả đo nào để đề xuất: chạy Đánh giá trước")
    cur = candidate()
    sens = sensitivity_propose.read_sensitivity()
    new, why, mode = sensitivity_propose.propose(result, cur, sens)
    new = tuning_memory.apply_to_proposal(cur, new)              # bước 3: nửa bước / đổi hướng cho núm vừa bị loại
    changes = {k: v for k, v in new.items() if v != cur[k]}
    if changes:
        knobs.write_many(changes, who, "; ".join(why)[:200], store="candidate")
    log.emit("stage", stage="propose", state="end", changes=changes, why=why, propose_mode=mode)
    return changes


def do_cycle(log, types, n):
    """Bước 5: chỉ sinh loại bị núm vừa đổi chạm tới (loop_partial), loại khác dùng lại số đo bản tốt nhất."""
    gen, reused, best = loop_partial.plan_cycle(candidate(), types, loop_generate.clamp_n(n))
    log.emit("stage", stage="cycle", state="plan", generate=gen, reuse=reused)
    if not gen:
        log.emit("stage", stage="cycle", state="skip", reason="núm thử trùng bản tốt nhất, không loại nào cần sinh lại")
        return {"all_pass": history()[-1]["all_pass"] if history() else False, "decision": "skipped"}
    it, out, host, n_used = loop_generate.do_generate(log, gen, n)
    if STOP.exists():
        raise Stopped("dừng theo yêu cầu")
    extra = {"comfyui": host, "types": types, "n_per_type": n_used, "generated_types": gen, "reused_types": reused}
    return do_evaluate(log, out, it, extra, reuse=(reused, best))


def _two_consecutive_neutral():
    h = history()
    return len(h) >= 2 and h[-1].get("decision") == "neutral" and h[-2].get("decision") == "neutral"


def do_auto(log, types, n, max_iter, owner=None):
    if not history():
        do_evaluate(log)                                       # vòng 0: đo bộ hiện có làm mốc
    for k in range(max_iter):
        reason = "các vấn đề đo được đều đạt" if history()[-1]["all_pass"] else None
        if not reason and _two_consecutive_neutral():
            reason = "2 vòng liên tiếp không cải thiện so bản tốt nhất"
        if not reason and STOP.exists():
            raise Stopped("dừng theo yêu cầu")
        if not reason and _other_batch_running(owner):
            reason = "có đợt sinh khác đang chạy, nhường GPU"
        if not reason and not do_propose(log):
            reason = "không còn núm nào để đổi (đã chạm giới hạn hoặc không có luật cho mục tiêu trượt)"
        if reason:
            log.emit("stage", stage="auto", state="end", reason=reason)
            return
        rec = do_cycle(log, types, n)
        log.emit("stage", stage="auto", state="progress", round=k + 1, max_iter=max_iter, all_pass=rec["all_pass"],
                 decision=rec.get("decision"))
    log.emit("stage", stage="auto", state="end", reason=f"chạm trần {max_iter} vòng")


def main():
    ap = argparse.ArgumentParser(description="Vòng cải thiện độ thật ảnh sinh")
    ap.add_argument("--action", choices=["evaluate", "propose", "cycle", "auto"], required=True)
    ap.add_argument("--n-per-type", type=int, default=40)                 # bước 2a: sau khi lọc has_region, 20 ca
                                                                            # còn quá ít hàng cho cổng v2 ghép cặp
                                                                            # (cần >= 10 ca chung có vùng mỗi loại)
    ap.add_argument("--types", default=",".join(DEFAULT_TYPES))
    ap.add_argument("--max-iter", type=int, default=5)
    ap.add_argument("--run-id", default=time.strftime("loop-%Y%m%d-%H%M%S"))
    ap.add_argument("--source", default=None, help="evaluate: thư mục ảnh cần đo (mặc định bộ mới nhất)")
    a = ap.parse_args()
    types = [t for t in a.types.split(",") if t]
    log = RunLog(a.run_id)
    STOP.unlink(missing_ok=True)
    log.emit("config", action=a.action, n_per_type=a.n_per_type, types=types, max_iter=a.max_iter, knobs=candidate())
    # Vòng lặp xin phiếu GPU (plant_gpu_lease) bằng pid của CHÍNH tiến trình này, giữ SUỐT
    # phiên cycle/auto (nhiều lượt sinh bên trong do_auto vẫn dưới một phiếu), nhả trong
    # finally. evaluate/propose chỉ CPU (đo bằng torch trên CPU), không xin phiếu.
    owner = f"realism-loop:{a.run_id}"
    lease_held = False
    try:
        if a.action in ("cycle", "auto"):
            from plant_hmi import plant_gpu_lease as gpu_lease
            ok, holder = gpu_lease.acquire(owner, f"vòng lặp realism ({a.action})", os.getpid())
            if not ok:
                who = (holder or {}).get("owner", "không rõ")
                purpose = (holder or {}).get("purpose", "")
                raise GpuBusy(f"GPU đang được {who} giữ ({purpose}), không xin được phiếu")
            lease_held = True
        {"evaluate": lambda: do_evaluate(log, a.source), "propose": lambda: do_propose(log, "HMI"),
         "cycle": lambda: do_cycle(log, types, a.n_per_type),
         "auto": lambda: do_auto(log, types, a.n_per_type, a.max_iter, owner)}[a.action]()
        log.emit("done")
    except Stopped as e:
        log.emit("error", message=str(e), stopped=True)
    except GpuBusy as e:
        log.emit("error", message=str(e))
    except Exception as e:
        log.emit("error", message=f"{type(e).__name__}: {e}"[:300])
        raise
    finally:
        if lease_held:
            from plant_hmi import plant_gpu_lease as gpu_lease
            gpu_lease.release(owner)
        STOP.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
