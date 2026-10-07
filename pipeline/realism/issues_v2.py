"""Mục tiêu độ thật theo thước mới (v2, bước 2a plan w0003-reference): so TUYỆT ĐỐI kết quả đo của một
vòng với mức "hoàn hảo" (null, chia đôi ảnh thật W0003 so chính nó) của TỪNG LOẠI, không so với bản tốt
nhất (việc so sánh ĐÓ là của loop_gate_v2, có ghép cặp ca). Dùng để tính rec["all_pass"] khi best đang ở
thước v2, và để trang Độ thật hiện bảng mục tiêu pass/fail cạnh mức hoàn hảo.

5 mục tiêu mỗi loại có tham chiếu W0003 (reference không None):
    detection_gap  tỉ lệ tách vùng thật trừ sinh không quá 10 điểm % (điều kiện CHẶN của cổng, người dùng duyệt 6/10)
    c2st           không vượt mức hoàn hảo p95 (C2ST càng thấp càng giống thật)
    kid            không vượt mức hoàn hảo p95
    density        nằm trong [p5, p95] mức hoàn hảo (lệch cả hai phía đều xấu: quá thưa hoặc quá đặc so thật)
    coverage       không dưới mức hoàn hảo p5 (coverage thấp nghĩa là nhiều phần thật không có ảnh sinh nào gần)

Loại chưa có mẫu thật W0003 (reference=None) hoặc chưa tính được null (W0003 dưới 4 mẫu, xem
reference_w0003_null.MIN_ROWS) trả targets rỗng: chỉ báo, không chặn all_pass.
"""

TARGET_LABELS = {
    "detection_gap": "Tỉ lệ tách vùng kém thật không quá 10 điểm %",
    "c2st": "C2ST không vượt mức hoàn hảo (p95)",
    "kid": "KID không vượt mức hoàn hảo (p95)",
    "density": "Density nằm trong khoảng hoàn hảo [p5, p95]",
    "coverage": "Coverage không dưới mức hoàn hảo (p5)",
}


def _target(name, value, lo=None, hi=None):
    passed = None if value is None else (lo is None or value >= lo) and (hi is None or value <= hi)
    return {"name": name, "label": TARGET_LABELS[name], "value": value, "lo": lo, "hi": hi, "pass": passed}


def evaluate_type(entry):
    """[{name,label,value,lo,hi,pass}, ...] cho một mục defect_metrics["types"][loại]. Loại chưa có tham chiếu
    W0003 (reference=None) → [] (chỉ báo, không có mục tiêu)."""
    if not entry or entry.get("reference") is None:
        return []
    null = entry.get("null") or {}
    det_real, det_syn = entry.get("detection_rate_real"), entry.get("detection_rate_syn")
    gap = (det_real - det_syn) if det_real is not None and det_syn is not None else None
    c2st_p95 = (null.get("c2st") or {}).get("p95")
    kid_p95 = (null.get("kid") or {}).get("p95")
    dens_null, cov_null = null.get("density") or {}, null.get("coverage") or {}
    dc = entry.get("density_coverage") or {}
    return [
        _target("detection_gap", gap, hi=0.10),
        _target("c2st", entry.get("c2st"), hi=c2st_p95),
        _target("kid", (entry.get("kid") or {}).get("value"), hi=kid_p95),
        _target("density", dc.get("density"), lo=dens_null.get("p5"), hi=dens_null.get("p95")),
        _target("coverage", dc.get("coverage"), lo=cov_null.get("p5")),
    ]


def evaluate_v2(result):
    """{loại: [targets]} cho mọi loại CÓ tham chiếu W0003 trong result["defect_metrics"]["types"]."""
    types = ((result or {}).get("defect_metrics") or {}).get("types") or {}
    return {t: evaluate_type(e) for t, e in types.items() if (e or {}).get("reference") is not None}


def all_pass(result):
    """True nếu mọi mục tiêu ĐO ĐƯỢC (pass không None) của mọi loại có tham chiếu đều đạt, và có ít nhất một
    loại có mục tiêu đo được. False nếu không loại nào có tham chiếu, một loại không đo được mục tiêu nào,
    hoặc có mục tiêu trượt."""
    ev = evaluate_v2(result)
    if not ev:
        return False
    for targets in ev.values():
        known = [t["pass"] for t in targets if t["pass"] is not None]
        if not known or not all(known):
            return False
    return True
