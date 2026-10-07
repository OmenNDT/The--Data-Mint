# Kế Hoạch Nâng Cấp Pipeline Sinh Ảnh

**Tạo**: 2026-08-09 · **Sửa lớn**: 2026-08-09 (chuyển sang chế độ phim full-size) · **Branch**: master

## Mục tiêu

Sinh phim X-quang mối hàn synthetic đủ chân thực để đứng chung phân bố với phim W0003 thật, nhằm bù trần dữ liệu 68 phim và nâng hiệu năng của QuantumRT (VQC) + non-VQC trên tập test phim thật.

## Bộ quyết định đã chốt

| # | Hạng mục | Quyết định |
|---|---|---|
| 1 | Base model | Giữ SD1.5 + LoRA r32 đã train |
| 2 | Cách sinh | **Inpaint khuyết tật lên nền phim thật train-side**; đầu ra = phim full-size (~4990×1300) |
| 3 | Mật độ khuyết tật/phim | **Khớp phân phối thật**: median 1, mean ~1,3, dải 1–24 |
| 4 | Trần tái sử dụng nền | Thử 5× / 20× / 50× mỗi nền, chốt bằng số đo |
| 5 | Đưa vào model | **Cắt mảnh 512 từ phim** — chia train/test ở mức **phim** trước, cắt sau |

## Ranh giới trách nhiệm

Kế hoạch này chỉ lo **sinh ảnh**. Việc chia tập, cắt tile, chọn `imgsz`, kiến trúc model thuộc phía QuantumRT / non-VQC.

**Đầu vào tôi cần từ phía train** (bắt buộc, chặn Phase 05):
- Danh sách phim W0003 thuộc **phía train**. Tôi inpaint lên nền phim thật, nên nếu lấy nhầm nền của phim phía test là tự tạo rò rỉ mà phía train không phát hiện được.

**Đầu ra tôi bàn giao**:
- Phim synthetic full-size (~4990×1300, grayscale 8-bit)
- Nhãn ở **toạ độ phim full-size** (class + bbox + mask), để phía train tự cắt tile theo cách của họ
- Metadata mỗi phim: `source_film` (phim thật cho nền), danh sách khuyết tật, seed, tham số sinh

**Không thuộc phạm vi**: cơ chế split, tham số tile, độ phân giải train, huấn luyện và đo mAP/F1.

## Tài liệu yêu cầu

- `docs/SPEC-pipeline-upgrade-for-QuantumRT.md` — yêu cầu phía VQC
- `docs/pipeline-fix-spec-nonvqc.md` — yêu cầu phía non-VQC
- `docs/pipeline-generation-current.md` — hiện trạng pipeline
- `plans/reports/verification-260809-1954-small-object-visibility-at-train-resolution.md` — phép kiểm độ phân giải

## Chẩn đoán gốc

`apply_dark_defect_convention()` (`batch-production-main.py:56-118`) thay cứng mọi pixel ngoài annotation mask bằng nền gốc, rồi nhân lòng mask với hệ số tối 0,92. Ảnh cuối ≈ `nền + hình mask làm tối`; output của SD bị vứt bỏ.

Bước 7 này là **miếng vá** cho việc LoRA vẽ quầng sáng ở vành đai giữa annotation mask và inpaint mask. Vì vậy không gỡ nó trước — phải khử halo tại gốc rồi mới gỡ được.

## Ba số liệu phải sửa trước khi triển khai

| Hạng mục | Spec đang ghi | Đúng phải là | Nguồn |
|---|---|---|---|
| Scale phim | 0,0334 mm/px | **0,0403 mm/px** | `W0003_readme.txt`: 40,3 micron / 630 dpi; kiểm chéo: 4986 px × 0,0403 = 20,1 cm khớp 20 ô 1 cm trong `real-values.xls` |
| Dải Gas_Pore | 0,5–1,2 mm | **0,20–6,00 mm** (median 0,86) | `real-values.xls` mã ISO 6520 = 2011, n = 90 |
| Chế độ train | tile hoá sau khi train ảnh full | cắt tile 512 để train | quyết định #5 |

## Hai vấn đề tự tiêu khi đổi chế độ

1. **Tranh cãi hệ số tối S** (0,92 → 0,30 → 0,15–0,25 giữa hai spec) trở nên vô nghĩa: Phase 03 thay hẳn phép nhân hệ số bằng mô hình suy giảm Beer–Lambert. Không tinh chỉnh S, mà bỏ S.
2. **Nhánh sinh hard-negative** (QuantumRT C4, non-VQC §1.1) không cần dựng riêng: mật độ thật + cắt tile cho ra ~95% mảnh nền sạch mang vân phim thật. Chỉ cần chỉnh tỉ lệ lấy mẫu mảnh âm tính.

## Các phase

| # | Phase | Ưu tiên | Ước lượng | Trạng thái | Phụ thuộc |
|---|-------|---------|-----------|-----------|-----------|
| 01 | [Đo lường & A/B harness](./phase-01-metrics-baseline-and-ab-harness.md) | P0 | 8h | ⏳ | — |
| 02 | [Khử halo tại gốc, gỡ bước 7](./phase-02-seamless-blend-restore-diffusion.md) | P0 | 12h | ⏳ | 01 |
| 03 | [Kết xuất theo vật lý RT](./phase-03-radiographic-physics-rendering.md) | P0 | 12h | ⏳ | 02 |
| 04 | [Hình thái, cực tính, hiệu chuẩn mm](./phase-04-mask-morphology-and-polarity-fixes.md) | P1 | 12h | ⏳ | 01 |
| 05 | [Soạn phim full-size & cắt tile](./phase-05-full-film-composition-and-tiling.md) | P1 | 14h | ⏳ | 02, 04 |
| 06 | [Nhãn đo từ ảnh sinh & cổng chất lượng](./phase-06-label-fidelity-and-quality-gate.md) | P1 | 10h | ⏳ | 03, 05 |
| 07 | [Thông lượng & dọn nợ kỹ thuật](./phase-07-throughput-and-tech-debt.md) | P2 | 10h | ⏳ | 06 |

**Tổng**: ~78h. Đường găng: 01 → 02 → 03 → 05 → 06. Phase 04 song song với 02/03.

## Tiêu chí nghiệm thu

**Tầng ảnh** (Phase 01–06)
1. Cường độ vành đai halo giảm **≥70%** so hiện trạng (cổng G3 của spec).
2. FID giảm ≥30% so mốc, đo trên tile cắt từ phim synthetic vs tile phim thật; ngưỡng hiệu chuẩn bằng sàn W0003-augment vs W0003-gốc, không dùng số tuyệt đối.
3. Tỉ số phương sai nhiễu lòng khuyết tật / vùng lân cận ∈ **[0,8; 1,2]**.
4. Đúng cực tính RT ở 12/12 lớp — riêng `lack_of_penetration` (đang ra sáng) và `metallic_inclusion`.
5. Phân phối số khuyết tật/phim khớp thật: **KS-test p > 0,05**.
6. Kích thước khuyết tật sinh khớp bảng BAM theo lớp (quy đổi ở 0,0403 mm/px).

**Tầng dữ liệu** (Phase 05–06)

7. IoU giữa nhãn đo từ ảnh sinh và mask ý đồ: loại ảnh nếu **< 0,5**; median toàn lô mục tiêu **≥ 0,7**.
8. Mọi phim synthetic đều có `source_film` trỏ về một phim **phía train**; không phim nào lấy nền từ phía test.
9. Nhãn bàn giao ở toạ độ phim full-size, tải lại được và vẽ chồng đúng vị trí.

**Tầng kết quả** (ngoài phạm vi — phía QuantumRT/non-VQC đo)

10. Recall/F1 của các lớp yếu tăng thực trên tập phim thật giữ riêng.

## Rủi ro chính

| Rủi ro | Giảm thiểu |
|---|---|
| Gỡ bước 7 làm halo quay lại | Phase 02 khử halo tại gốc trước, chỉ gỡ bước 7 sau khi G3 đạt ≥70% |
| Chỉ ~50 nền train-side, dùng lại nhiều lần ⇒ model thuộc lòng nền | Quyết định #4: đo bão hoà ở 5×/20×/50×; kèm biến đổi nền nhẹ |
| LoRA hiện tại quá yếu, không vẽ nổi khuyết tật chân thực | Phase 01 đo riêng đóng góp của SD; nếu ≈ 0 thì escalate sang retrain LoRA |
| Lấy nhầm nền phim phía test | Đọc danh sách phim train-side từ một file cấu hình duy nhất; Phase 05 chặn cứng, không có đường vòng |
| Ba tài liệu (2 spec + kế hoạch) lệch nhau | Kế hoạch này là bản thi công; mọi số liệu lấy theo bảng "Ba số liệu phải sửa" ở trên |

## Câu hỏi chưa giải quyết

1. **Danh sách phim phía train** — chặn Phase 05, cần trước khi sinh ảnh đầu tiên.
2. Có sửa trực tiếp hai file spec theo bảng số liệu đã đính chính không, hay để nguyên và chỉ kế hoạch này dùng số đúng?
3. Ảnh âm tính: mảnh nền sạch cắt từ phim đã đủ chưa, hay vẫn cần nhánh hard-negative sinh riêng (vân mối hàn, xước phim, artifact)?
4. Nhãn `Lack_of_Root_Fusion` có p10 = 8,5 px trong khi median 51 px — nhãn khoanh sai hay khuyết tật thật mảnh? Ảnh hưởng tới hình thái tôi phải sinh cho lớp này.
