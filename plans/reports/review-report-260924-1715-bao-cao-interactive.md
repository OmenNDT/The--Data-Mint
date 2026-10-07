# Review tài liệu: bao-cao-the-data-mint-interactive.html

Bối cảnh nhận diện: báo cáo đồ án môn học, trình bày dạng trang tương tác một màn hình.
Văn phong chuẩn: kỹ thuật, không xưng ngôi, số liệu dẫn trực tiếp.

Đoạn rà: 174 đoạn HTML hiển thị + 159 chuỗi dữ liệu trong JS (popup 9 giai đoạn, KPI, thư viện hình).
Sửa đổi áp được: 10/10. Không có mục nào phải sửa tay.

## Lưu ý về đối tượng sửa

`bao-cao-the-data-mint-interactive.html` là **tệp dựng ra**, không sửa trực tiếp được (sửa vào đó
sẽ mất khi dựng lại). Mọi sửa đổi áp vào bản nguồn `report-interactive-source.html`, rồi chạy
`build-interactive-html.py` để dựng lại. Đã dựng lại và kiểm chứng trên trình duyệt: JS nguyên vẹn
(9 giai đoạn, 8 khối màn), popup giai đoạn 08 hiển thị đúng bảng đã sửa.

Skill không có nhánh xử lý `.html`. Đã xử theo nhánh `.md/.txt`: sửa trực tiếp, không Track Changes.
Lượt 7b (style Word, heading tự động, đánh số) không áp dụng cho HTML; phần tương đương là tính
nhất quán nhãn và tiêu đề, ghi ở mục riêng bên dưới.

## Thống kê theo lượt

| Lượt | Loại vấn đề | Số sửa đổi |
|---|---|---|
| L1 | Lối Anh ngữ, danh từ hoá, lặp từ | 4 |
| L2 | Từ lệch bối cảnh | 1 |
| L3 | Câu tự biện minh | 0 |
| L4 | Cường điệu | 2 |
| L5 | Cụm đệm rỗng | 0 |
| L6 | Cắt từ thừa | 1 |
| L7a | Dấu câu, gạch ngang xen giữa | 2 |
| **Tổng** | | **10** |

L3 và L5 không có sửa đổi: toàn văn không có câu tự biện minh, không có cụm đệm trong danh sách
catalog ("Có thể nói rằng", "Nhìn chung", "Trên thực tế", "Về cơ bản"...).

## Chi tiết sửa đổi

| # | Đoạn | Trước | Sau | Lý do |
|---|---|---|---|---|
| 1 | H043 | Rò rỉ chéo nguồn bằng 0 **xác nhận điều ngược lại, theo hướng tốt**: không ảnh sinh nào... | Rò rỉ chéo nguồn bằng 0 **là tin tốt**: không ảnh sinh nào... | L1 - bình luận chèn giữa, câu đi vòng |
| 2 | H051 | chia làm hai nhóm rõ rệt, và **ranh giới rơi đúng vào ranh giới** giữa đặc tính chụp... | chia làm hai nhóm, và **đường chia trùng đúng ranh giới** giữa đặc tính chụp... | L1 - lặp "ranh giới" trong cùng câu |
| 3 | J015 | Patch quá tối **cho** tương phản khuyết tật **quá** thấp **và khiến** bước làm tối... | Patch quá tối **làm** tương phản khuyết tật thấp, **và** bước làm tối... | L1 - "cho tương phản" dịch sát tiếng Anh; lặp "quá" |
| 4 | H143 | **hệ quả của việc** tái dùng ảnh nền | **do** tái dùng ảnh nền | L1 - danh từ hoá "việc"; đồng bộ với màn kết luận |
| 5 | H167 | Đây là **đòn bẩy** lớn nhất | **Việc này có tác dụng** lớn nhất | L2 - ẩn dụ kinh doanh, lệch văn phong kỹ thuật |
| 6 | H092 | phần lệch lại là phần dễ chỉnh **nhất** | phần lệch lại là phần dễ chỉnh **hơn** | L4 - "nhất" không có căn cứ so sánh |
| 7 | J090 | SSIM 0,976 xác nhận điều quan trọng nhất: | SSIM 0,976 xác nhận điều quan trọng nhất **của cổng này**: | L4 - bỏ phạm vi làm câu thành khẳng định tuyệt đối; khôi phục phạm vi như đồ án gốc |
| 8 | H100 | ...danh sách **ảnh bị đánh dấu** thì thấy **mọi ảnh bị đánh dấu** đều là ảnh thật | ...danh sách ảnh bị đánh dấu thì thấy **tất cả** đều là ảnh thật | L6 - lặp cụm trong cùng câu |
| 9 | tiêu đề | The Data Mint **—** Báo cáo tương tác | The Data Mint **·** Báo cáo tương tác | L7a - gạch ngang xen giữa; đổi cho khớp nhãn "Đồ án môn học · Nhóm 5" |
| 10 | J092 | 0,976 **—** đạt / 95,0% **—** đạt / 854 lỗi **—** không đạt / lệch 20% **—** không đạt | 0,976 **(đạt)** / 95,0% **(đạt)** / 854 lỗi **(không đạt)** / lệch 20% **(không đạt)** | L7a - 4 gạch ngang xen giữa trong bảng popup giai đoạn 08 |

## Lượt 7a — phần đã quét, không có lỗi

- Nháy cong `“”‘’` và ba chấm `…`: không có.
- Dấu thập phân: toàn văn dùng dấu phẩy (`0,854`, `0,976`, `1,55`). Các chuỗi `1.12`, `13.5`...
  chỉ nằm trong CSS, không phải văn bản hiển thị.
- Hàng nghìn: thống nhất dấu chấm (`1.097`, `1.611`, `18.158`, `20.000`).
- Phần trăm viết liền: đúng toàn văn, không có `0,5 %`.
- Khoảng trắng trước dấu phẩy, khoảng trắng đôi: không có trong phần văn bản.
- Tên phiên bản giữ dấu chấm theo đúng tên gốc (`Stable Diffusion 1.5`, `SD 1.5`) - thuộc nhóm
  ràng buộc cứng, không đổi.

## Lượt 7b — nhất quán nhãn và tiêu đề (phần tương đương với HTML)

Đã kiểm, **không tự sửa**:

1. **Nhịp tiêu đề ba cột màn kết luận lệch.** "Làm được" và "Chưa đạt" là hai từ, cột thứ ba là
   "Việc nên làm, theo thứ tự". Cụm "theo thứ tự" mang thông tin thật (danh sách đã xếp ưu tiên)
   nên không cắt được mà không mất ý. Muốn cân nhịp thì phải đánh số 1-5 vào các gạch đầu dòng rồi
   rút tiêu đề còn "Việc nên làm".
2. Nhãn phần (`sc-kicker`), tiêu đề khối (`panel h3`), nhãn khối nhấn (`callout .tagline`):
   nhất quán, không có ngoại lệ.
3. Kết thúc mục liệt kê: thống nhất không dấu chấm cuối ở cả ba cột màn kết luận.
4. Chú thích hình (`figcaption`): nhất quán, không dấu chấm cuối.

## Cần người viết quyết định

**1. Hai cách gọi cho cùng một khái niệm: "ảnh sinh" và "ảnh tổng hợp".**

- "ảnh tổng hợp" - khoảng 8 chỗ: màn KPI, popup giai đoạn 06/08/09, cột "Làm được".
- "ảnh sinh" - khoảng 20 chỗ: toàn bộ ba màn hậu kiểm, cột "Chưa đạt".

Không sửa vì hai lý do: đụng tiêu đề màn ("Một con số đủ để nhận ra ảnh sinh") và nhãn cột bảng
("Thật | Sinh"), và có thể là chủ ý giữ đúng thuật ngữ của hai nguồn khác nhau, đồ án dùng
"ảnh tổng hợp", báo cáo hậu kiểm dùng "ảnh sinh".

Đề xuất: chọn **"ảnh tổng hợp"** làm chuẩn toàn văn cho khớp bản DOCX nộp. Đồng ý thì tôi đổi
20 chỗ, gồm cả tiêu đề màn và nhãn cột.

**2. Hai cách gọi cho ô ảnh cắt: "patch" và "ô".**

"Cắt phim gốc thành ô vuông 512 × 512", "827 patch nền sạch", "patch 512 cắt từ phim GDXray".
Bản đồ án gốc cũng lẫn hai cách này ở mục 3.2.2 nên không phải lỗi phát sinh khi làm slide.
Thống nhất một cách sẽ lệch với đồ án. Cần chốt ở cả hai tài liệu cùng lúc, không chốt riêng slide.

## Ngoài phạm vi skill

Skill này chỉ rà ngôn ngữ. Không kiểm tính đúng đắn của số liệu, không kiểm logic lập luận,
không kiểm mã. Các con số trong tài liệu giữ nguyên toàn bộ.

## Câu còn treo

1. Chọn "ảnh tổng hợp" hay "ảnh sinh" làm chuẩn? Nếu chốt thì nên chốt cho cả `do-an-the-data-mint.md`.
2. Có đánh số 1-5 vào cột "Việc nên làm" để rút gọn tiêu đề không?
