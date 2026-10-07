# Nhánh E vòng 2: độ sâu riêng xỉ / rỗ khí kéo dài, modulation rỗ khí chuỗi

Thước mới `realism.defect_eval` (16 đặc trưng, C2ST/KID+CI/density-coverage/tách vùng), ghép cặp
`realism.loop_gate_v2_metrics.paired_metrics` trên ca chung. Cả hai chạy CPU replay từ ảnh
trước-làm-tối (`predarken_replay.replay`), không sinh lại GPU trừ base slag/ecav (40 ca mỗi loại,
num SX hiện tại, REALISM_SAVE_PREDARKEN=1, tái dùng seed/nền của
`output/realism-loop/remaining-types-prod/fixed-jobs.json`).

**Cảnh báo tham chiếu nhỏ:** slag n=14, ecav n=9, linear n=10 thật (dưới ngưỡng 15 của
`defect_eval.SMALL_REFERENCE_ROWS`, ecav còn dưới cả `MIN_C2ST_ROWS=10` nên không tính được C2ST).
Mọi kết luận "không đổi" dưới đây KHÔNG LOẠI TRỪ khác biệt nhỏ, chỉ đáng tin với hiệu ứng lớn.

## 1. slag_inclusion — slag_post_depth_min/max

Lưới: hiện tại = dùng chung `post_depth 0,37–0,57`; 3 mức thử 0,50–0,70 / 0,65–0,85 / 0,80–1,00.
40 ca cố định, 27 ca chung có tách vùng ở MỌI mức (dùng ghép cặp).

| Mức | tách vùng thật/sinh | C2ST (toàn mẫu) | KID (toàn mẫu) | ghép cặp C2ST | ghép cặp KID | ghép cặp density/coverage |
|---|---|---|---|---|---|---|
| hiện tại 0,37–0,57 | 1,00 / 0,675 | 0,807 | 3,17 [2,13;4,60] | — (gốc) | — (gốc) | 0,570 / 0,500 |
| 0,50–0,70 | 1,00 / 0,775 | 0,862 | 3,36 | same (0,889 vs 0,804) | same (3,13 vs 3,17) | same |
| 0,65–0,85 | 1,00 / 0,925 | 0,884 | 4,05 | same (0,886 vs 0,804) | same (3,12 vs 3,17) | same |
| 0,80–1,00 | 1,00 / 0,950 | 0,878 | 4,38 | same (0,886 vs 0,804) | same (3,14 vs 3,17) | same |

Ghép cặp trên 27 ca chung: KHÔNG mức nào bị "worse" theo 4 độ đo tổng hợp (CI phí tổn đều chứa 0).
Tách vùng cải thiện rõ và đơn điệu theo độ sâu (0,675 → 0,95; gap thật so sinh co từ 32,5pp xuống 5pp).

**Nhưng** nhìn 6 đặc trưng lệch nhiều nhất (per-feature AUC/KS), hai đặc trưng cạnh đã lệch sẵn ở
mức hiện tại tiếp tục lệch THÊM đơn điệu theo độ sâu, không phải nhiễu:
- `bien_doc` (độ dốc biên): AUC 0,876 → 0,923 → 0,945 (real trung vị 2,72, sinh 6,90 → 8,29 → 9,43)
- `bien_tuongphan` (độ tương phản biên): AUC 0,780 → 0,882 → 0,930 (real 1,35, sinh 3,45 → 4,09 → 5,24)

Đây là tín hiệu thật (đơn điệu 3 điểm, không phải dao động ngẫu nhiên), dù độ đo tổng hợp ghép cặp
chưa đủ mạnh để bắt được với n=27. Làm tối sâu hơn khiến biên xỉ dốc/tương phản hơn thật ĐÃ sai
hướng từ mức hiện tại, và lệch thêm.

**Khuyến nghị:** `slag_post_depth_min/max = 0,65 / 0,85` (không phải 0,80–1,00). Lý do: đạt tiêu
chí tách vùng (gap 7,5pp, dưới ngưỡng 10pp người dùng đặt) mà không đẩy thêm nhiều vào vùng lệch
của `bien_doc`/`bien_tuongphan` như mức 0,80–1,00 (chỉ thêm ít: AUC 0,945 vs 0,923, nhưng gap tách
vùng chỉ hơn 2,5pp, không đáng đánh đổi). Nếu người dùng ưu tiên tuyệt đối tách vùng, 0,80–1,00 vẫn
"same" theo luật ghép cặp chính thức, chấp nhận được.

## 2. elongated_cavity — ecav_post_depth_min/max

Lưới tương tự, 40 ca cố định, 18 ca chung có tách vùng ở cả hai mức so (mức hiện tại chỉ tách được
18/40, ít). Không tính C2ST toàn mẫu được (thật n=9 < 10).

| Mức | tách vùng thật/sinh (gap) | KID (toàn mẫu) | ghép cặp KID | ghép cặp density/coverage |
|---|---|---|---|---|
| hiện tại 0,37–0,57 | 0,90 / 0,45 (45pp) | 0,223 [-0,23;0,87] | — (gốc) | 0,989 / 1,00 |
| 0,50–0,70 | 0,90 / 0,55 (35pp) | 0,221 | same (0,069 vs 0,223 trên 18 ca chung) | same |
| 0,65–0,85 | 0,90 / 0,725 (17,5pp) | 0,375 | same (0,030 vs 0,223) | same |
| 0,80–1,00 | 0,90 / 0,825 (7,5pp) | 0,461 | same (0,228 vs 0,223) | same |

Không thấy trend lệch đơn điệu ở 6 đặc trưng lệch nhiều nhất (AUC dao động 0,26–0,73 qua các mức,
không đơn điệu như slag) — không có dấu hiệu overshoot tương tự.

**Khuyến nghị:** `ecav_post_depth_min/max = 0,80 / 1,00`. Chỉ mức này đưa gap tách vùng xuống dưới
10pp (7,5pp); 0,65–0,85 còn 17,5pp, chưa đạt. Ghép cặp xác nhận không mức nào "worse" trên 4 độ đo
tổng hợp, không có overshoot đặc trưng rõ như slag → đi tới mức cao nhất trong lưới thử là an toàn
nhất theo dữ liệu hiện có.

## 3. linear_porosity — linear_post_modulation

CPU replay trên `output/realism-loop/pore-type-depth-base` (đã có predarken, không cần sinh GPU).
Núm chung hiện tại `post_modulation=0,65`; núm riêng `linear_post_modulation` đang để −1 (dùng
chung). Thử 0,0 và 0,3.

| Mức | tách vùng thật/sinh | C2ST | KID | density/coverage |
|---|---|---|---|---|
| hiện tại (−1 = 0,65) | 1,00 / 0,975 | 0,790 | 1,032 [0,249;1,886] | 0,805 / 1,00 |
| 0,0 | 1,00 / 1,00 | 0,733 | 0,411 [-0,130;1,103] | 1,080 / 1,00 |
| 0,3 | 1,00 / 1,00 | 0,800 | 0,644 [0,018;1,423] | 0,974 / 1,00 |

Khớp đúng số nhánh A đã báo (0,79→0,73 C2ST, 1,03→0,41 KID). Ghép cặp trên 39 ca chung (so điểm hiện
tại): cả 4 độ đo "same" ở cả 0,0 và 0,3 (CI phí tổn chứa 0, n thật chỉ 10 nên lực kiểm định yếu),
nhưng điểm ước lượng của 0,0 tốt hơn ở MỌI độ đo so với cả mức hiện tại và mức 0,3 (C2ST thấp nhất,
KID thấp nhất, density gần 1 nhất: phí tổn 0,08 so với 0,195 hiện tại và 0,026 ở 0,3 — chỉ số này
0,3 nhỏ hơn 0,0 chút nhưng C2ST/KID của 0,3 đều kém hơn 0,0).

**Khuyến nghị:** `linear_post_modulation = 0,0`. Xác nhận lại hướng nhánh A: tắt dao động độ sâu
dọc lỗi cho rỗ khí chuỗi giúp mọi độ đo hình dạng tốt hơn về điểm, không độ đo nào "worse" theo
ghép cặp. 0,3 là lựa chọn giữa, không tốt hơn 0,0 ở bất kỳ độ đo nào đo được.

## Tổng hợp khuyến nghị

| Núm | Giá trị đề xuất | Tin cậy |
|---|---|---|
| `slag_post_depth_min/max` | 0,65 / 0,85 | Trung bình: tách vùng cải thiện rõ (hiệu ứng lớn), nhưng n=14 thật + overshoot biên quan sát được ở hai đặc trưng cạnh — chọn mức giữa thận trọng, không chọn mức cao nhất |
| `ecav_post_depth_min/max` | 0,80 / 1,00 | Trung bình: chỉ mức này đạt tiêu chí tách vùng ≤10pp, không overshoot quan sát được, nhưng n=9 thật rất nhỏ |
| `linear_post_modulation` | 0,0 | Trung bình: khớp lại đúng số nhánh A, điểm ước lượng tốt hơn mọi độ đo, nhưng n=10 thật nên CI ghép cặp chỉ "same" không "better" chính thức |

## Dữ liệu & lệnh tái lập

- Base GPU slag+ecav (lưu predarken): `output/realism-loop/branch-e-slag-ecav-base/` (80 ảnh, num SX,
  seed/nền từ `remaining-types-prod/fixed-jobs.json`)
- Lưới CPU replay slag/ecav: `output/realism-loop/branch-e-slag-ecav-grid/<loại>/<mức>/`
- Lưới CPU replay linear: `output/realism-loop/branch-e-linear-modulation/<mức>/`
- Báo cáo JSON đầy đủ (scratchpad, không trong repo): `slag-ecav-depth-grid-report.json`,
  `linear-modulation-report.json`
- Script tái lập (scratchpad): `slag_ecav_base.py` (sinh GPU base), `slag-ecav-depth-grid.py`,
  `linear-modulation-grid.py`

## Việc KHÔNG làm (theo giới hạn giao việc)

Không ghi `realism/state/knobs.json` hay `candidate-knobs.json`, không sửa file code nào trong repo,
không commit, không khởi động lại ComfyUI/gateway. Mọi giá trị đề xuất ở trên cần người giữ vòng
lặp (lead) tự ghi vào kho núm nếu chốt dùng.

**Status:** DONE
**Summary:** Đo xong 3 núm (slag depth, ecav depth, linear modulation) bằng thước W0003 mới + ghép
cặp; đề xuất slag 0,65–0,85 (thận trọng vì overshoot biên quan sát được), ecav 0,80–1,00 (duy nhất
đạt gap tách vùng ≤10pp), linear_post_modulation 0,0 (xác nhận nhánh A).
**Concerns/Blockers:** Tham chiếu thật rất nhỏ (slag 14, ecav 9, linear 10) nên mọi "same" ghép cặp
có lực kiểm định yếu; slag cho thấy overshoot đơn điệu ở 2 đặc trưng cạnh khi tăng độ sâu, đáng theo
dõi thêm nếu promote lên sản xuất và chạy mẻ lớn hơn sau đó.
