"""Đánh giá lại một phiên đo độ nhạy đã sinh xong, chỉ bằng CPU (không sinh ảnh lại):

    python3 -m realism.sensitivity_reassess <run_id> [--write-state]

Dùng khi mã đo (evaluate) hoặc thống kê ghép cặp (paired_stats) thay đổi sau khi ảnh đã sinh: đo lại thư mục
base và từng biến thể trong output/realism-sensitivity/<run_id>/, ghép hiệu ứng lại, ghi đè
runs/<run_id>/sensitivity.json. --write-state: chép thêm sang realism/state/sensitivity.json (chỉ khi không pilot).
"""
import argparse
import json

from . import evaluate, sensitivity_groups
from . import sensitivity_screen_effects as effects_mod
from . import sensitivity_screen_gen as gen
from .runlog import RunLog, read_json


def reassess(run_id, write_state=False, workers=16):
    sens = read_json(run_id, "sensitivity.json")
    if not sens:
        raise SystemExit(f"không có runs/{run_id}/sensitivity.json")
    run_dir = gen.OUT_ROOT / run_id
    log = RunLog(run_id)
    log.emit("stage", stage="reassess", state="start")
    base_result = evaluate.run(run_dir / "base", sens["base_eval_run"], workers=workers)
    effects = {}
    for v in sens["variants"]:
        result = evaluate.run(run_dir / v["id"], v["eval_run"], workers=workers)
        effects[v["id"]] = effects_mod.assemble_effects(base_result, result,
                                                        sensitivity_groups.GROUPS[v["group"]]["types"])
    sens["effects"] = effects
    sens["reassessed"] = True
    log.write_json("sensitivity.json", sens)
    if write_state and not sens.get("pilot"):
        from .sensitivity_screen import _write_production_copy
        _write_production_copy(sens)
    log.emit("stage", stage="reassess", state="end")
    return sens


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_id")
    ap.add_argument("--write-state", action="store_true")
    a = ap.parse_args()
    s = reassess(a.run_id, a.write_state)
    print(json.dumps({"run_id": s["run_id"], "variants": len(s["variants"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
