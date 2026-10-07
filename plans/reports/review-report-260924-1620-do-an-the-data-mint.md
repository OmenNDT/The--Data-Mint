# Review tài liệu: Do-an-The-Data-Mint.docx

Bối cảnh nhận diện: **báo cáo đồ án môn học** (tín hiệu: GVHD, Sinh viên thực hiện, Lời cảm ơn, Chương 1 Tổng quan).
Chuẩn áp dụng: xưng "nhóm", tông trung tính, nêu cả hạn chế, câu 15–30 từ.

Đoạn rà: 653 · Sửa đổi áp được: 67/67 · Số từ: 15.013 → 14.947 (giảm 0,44%)

## Thống kê theo lượt

| Lượt | Loại vấn đề | Số sửa đổi |
|---|---|---|
| L1 | Lối Anh ngữ (bị động thừa, danh từ hoá, câu cụt) | 19 |
| L2 | Từ lệch bối cảnh | 2 |
| L3 | Câu tự biện minh | 2 |
| L4 | Cường điệu | 2 |
| L5 | Cụm đệm rỗng | 1 |
| L6 | Cắt từ thừa | 6 |
| L7a | Nháy kép cong sang nháy thẳng | 35 |
| | **Tổng** | **67** |

Mức giảm từ 0,44%, thấp hơn nhiều so với mốc 10–25% của Lượt 6. Nguyên nhân: bản thảo viết theo đúng bộ quy tắc văn phong này nên gần như không có cụm đệm. Rà cơ học 29 mẫu cụm đệm phổ biến ("có thể nói rằng", "nhìn chung", "trên thực tế", "một cách ...", "đóng vai trò quan trọng"...) chỉ trả về 0 kết quả thật. Không cắt ép để đạt chỉ tiêu, vì cắt thêm sẽ mất thông tin.

Phần lớn sửa đổi rơi vào L1: bị động thừa kiểu Anh ngữ ("được chia thành", "được áp cho", "được đo trực tiếp"). Đây là dấu vết rõ nhất còn sót.

## Hai lỗi script đề xuất nhưng đã loại bỏ

1. **`1.5` → `1,5` (21 chỗ).** Script dấu câu coi đây là dấu thập phân. Thực tế là số phiên bản phần mềm "Stable Diffusion 1.5" / "SD 1.5", thuộc ràng buộc cứng nhóm 2 (tên riêng phần mềm). Đổi sẽ sai tên sản phẩm. Đã loại toàn bộ, gồm cả một chỗ nằm lẫn trong sửa đổi nháy kép.
2. **Gạch ngang trong tên tài liệu tiêu chuẩn (5 chỗ, P394–P396).** Nằm trong mục TÀI LIỆU THAM KHẢO, là trích dẫn nguyên văn tên tiêu chuẩn ISO tiếng Anh. Ràng buộc cứng nhóm 3.

## Lượt 7b — Đồng bộ định dạng & heading

Script `audit-format-consistency.py` báo bốn nhóm vấn đề. Nhóm kiểm lại từng nhóm bằng cách đọc trực tiếp định dạng trong file; **ba trong bốn nhóm là báo nhầm**.

| Script báo | Kiểm chứng thực tế | Kết luận |
|---|---|---|
| 15 "heading giả" P001–P016 | Toàn bộ là dòng trang bìa, in đậm căn giữa theo đúng form mẫu | Báo nhầm, cố ý |
| 109/240 đoạn thân lệch chuẩn | Phần lớn là mục liệt kê (style Compact, không thụt đầu dòng, đúng thiết kế) và đoạn mở mục (First Paragraph). Script đếm "0 mục liệt kê" vì không nhận ra style Compact là danh sách | Báo nhầm |
| 3 chú thích hình lệch chuẩn | Ngược lại: 9 chú thích hình trong thân bài đều thống nhất (Image Caption, 12pt, đậm, căn giữa). 29 dòng script lấy làm "dạng phổ biến" thực ra là dòng trong DANH MỤC HÌNH VẼ và DANH MỤC BẢNG | Báo nhầm |
| Số Hình/Bảng bị trùng và không tăng dần | Do danh mục đầu sách và chú thích trong thân cùng chứa dãy số. Dãy trong thân bài tăng dần, không trùng | Báo nhầm |

**Một vấn đề định dạng có thật, script không nêu:** 20 chú thích bảng trong thân bài chia làm hai style (Body Text 15 đoạn, First Paragraph 5 đoạn). Hình thức hiển thị giống hệt nhau vì đều đặt trực tiếp 12pt đậm căn trái, nhưng nếu sau này sửa qua style thì 5 đoạn kia không đổi theo. Sửa trong Word: chọn 5 đoạn đó, gán lại style Body Text.

## Sửa gốc ở khâu dựng file

Toàn bộ 35 nháy kép cong không do người viết gõ ra mà do pandoc bật sẵn tiện ích mở rộng `smart`, tự đổi `"` thành `“”`. Chỉ sửa trong file .docx thì lần dựng lại sẽ tái phát. Đã xử lý tận gốc:

- `Report/build-report-docx.sh`: đổi `-f markdown` thành `-f markdown-smart`.
- `Report/do-an-the-data-mint.md`: ba dòng MSSV trên trang bìa đổi `--` sang ký tự `–` đúng như form mẫu, vì tắt `smart` thì pandoc không còn tự chuyển nữa.
- Toàn bộ 32 sửa đổi câu chữ đã áp ngược vào file .md nguồn. Dựng lại bằng `bash Report/build-report-docx.sh` cho ra đúng bản đã sửa.

## Chi tiết sửa đổi

35 sửa đổi nháy kép cong sang nháy thẳng lặp cùng một dạng nên không liệt kê từng dòng. 32 sửa đổi còn lại:

| # | Đoạn | Trước | Sau | Lý do |
|---|---|---|---|---|
| 1 | P107 | Toàn bộ 18.158 dòng mã Python được đóng gói sau một giao diện Gradio một nút bấm | Toàn bộ 18.158 dòng mã Python đóng gói sau giao diện Gradio một nút bấm | L6 - bị động thừa và lặp 'một' |
| 2 | P118 | nhiều năm kinh nghiệm tích luỹ | nhiều năm kinh nghiệm | L6 - 'tích luỹ' thừa nghĩa |
| 3 | P124 | Sinh dữ liệu tổng hợp mở ra lối thoát. | Sinh dữ liệu tổng hợp là hướng giải quyết. | L2 - lối viết văn chương lệch văn phong báo cáo kỹ thuật |
| 4 | P167 | dẫn tới việc vẫn phải gán nhãn lại cho ảnh sinh | nên vẫn phải gán nhãn lại cho ảnh sinh | L6 - 'dẫn tới việc' là danh từ hoá thừa |
| 5 | P168 | Ba mảnh ghép này làm cho việc sinh ảnh khuyết tật theo vị trí và hình dạng định trước trở … | Ba mảnh ghép này cho phép sinh ảnh khuyết tật theo vị trí và hình dạng định trước. | L1 - danh từ hoá kiểu Anh ngữ 'làm cho việc ... trở nên' |
| 6 | P191 | Ràng buộc kích thước này được cài thẳng vào | Ràng buộc kích thước này cài thẳng vào | L1 - bị động thừa |
| 7 | P209 | giữa việc bám hình thái khuyết tật và việc giữ kết cấu phim nền | giữa bám hình thái khuyết tật và giữ kết cấu phim nền | L6 - hai lần 'việc' thừa |
| 8 | P247 | Cấu hình 88 luồng CPU được khai thác cho bước sinh mặt nạ song song, vốn hoàn toàn chạy tr… | Bước sinh mặt nạ chạy hoàn toàn trên CPU nên khai thác được 88 luồng, trong khi | L1 - bị động thừa; L6 - lặp 'CPU' |
| 9 | P250 | Hệ thống được chia thành chín giai đoạn nối tiếp | Nhóm chia hệ thống thành chín giai đoạn nối tiếp | L1 - bị động thừa, nêu rõ chủ ngữ |
| 10 | P280 | Các số liệu này được đo trực tiếp từ 876 nhãn của bộ gốc và là cơ sở | Nhóm đo các số liệu này trực tiếp từ 876 nhãn của bộ gốc; đây là cơ sở | L1 - bị động thừa |
| 11 | P282 | Phim gốc được cắt thành các ô vuông | Nhóm cắt phim gốc thành các ô vuông | L1 - bị động thừa |
| 12 | P282 | Các ô được phân thành hai nhóm. | Các ô chia thành hai nhóm. | L1 - bị động thừa |
| 13 | P285 | Một bộ lọc độ sáng được áp cho tập nền: chỉ giữ | Tập nền còn qua một bộ lọc độ sáng: chỉ giữ | L1 - bị động thừa kiểu Anh ngữ |
| 14 | P287 | Toàn bộ 1.809 dòng mã trong mô-đun mask_generator, gồm mười hai lớp sinh mặt nạ | Khối này gồm 1.809 dòng mã trong mô-đun mask_generator: mười hai lớp sinh mặt nạ | L1 - câu cụt, thiếu vị ngữ |
| 15 | P290 | Toạ độ tìm được bị kẹp vào biên an toàn | Toạ độ tìm được kẹp vào biên an toàn | L1 - 'bị' dùng sai sắc thái |
| 16 | P313 | Đây là điểm thiết kế then chốt | Đây là điểm thiết kế quyết định | L4 - 'then chốt' là từ phô trương |
| 17 | P341 | Cấu hình huấn luyện được sinh tự động thành tệp TOML cho kohya-ss | Hệ thống sinh tự động cấu hình huấn luyện thành tệp TOML cho kohya-ss | L1 - bị động thừa |
| 18 | P361 | Lời nhắc được tách thành tệp YAML riêng | Lời nhắc tách thành tệp YAML riêng | L1 - bị động thừa |
| 19 | P394 | cường độ trong lòng khuyết tật được nhân với một hệ số nhỏ hơn 1 | hệ thống nhân cường độ trong lòng khuyết tật với một hệ số nhỏ hơn 1 | L1 - bị động thừa |
| 20 | P429 | Đây là một hạn chế: lô ảnh | Đây là hạn chế: lô ảnh | L6 - 'một' thừa |
| 21 | P476 | môi trường ảo riêng cho pipeline | môi trường ảo riêng cho quy trình | L2 - toàn văn dùng 'quy trình', không dùng 'pipeline' |
| 22 | P513 | Đối chiếu hai lưới ảnh cho một quan sát đáng chú ý: | Đối chiếu hai lưới ảnh cho thấy: | L5 - cụm đệm 'đáng chú ý' không mang thông tin |
| 23 | P534 | độ nét Laplace 324,5 vượt trội so với nhóm còn lại | độ nét Laplace 324,5 cao hơn hẳn nhóm còn lại | L4 - 'vượt trội' phô trương, số liệu đã tự nói |
| 24 | P555 | Bốn cấu hình huấn luyện được chạy trên cùng một kiến trúc YOLOv8 | Nhóm chạy bốn cấu hình huấn luyện trên cùng một kiến trúc YOLOv8 | L1 - bị động thừa |
| 25 | P571 | Vai trò thực tế của hệ thống do đó được xác định rõ: | Vai trò thực tế của hệ thống do đó đã rõ: | L1 - bị động thừa |
| 26 | P590 | Nhóm giữ nguyên số liệu thay vì diễn giải lại theo hướng có lợi. Nguyên nhân | Nguyên nhân | L3 - câu tự biện minh, không mang thông tin về kết quả |
| 27 | P592 | Đây là phần quan trọng nhất của chương, vì nó giải thích vì sao chỉ tiêu mAP chưa đạt. | Các hạn chế này giải thích vì sao chỉ tiêu mAP chưa đạt. | L3 - tự đánh giá tầm quan trọng của chính phần mình viết |
| 28 | P593 | Đây cũng là lý do khác biệt giữa bản có và không có ControlNet nhỏ tới mức khó phân biệt b… | Đây cũng là lý do Hình 4.1 và Hình 4.2 khác nhau ít tới mức khó phân biệt bằng mắt: | L6 - câu rối, rút gọn giữ nguyên ý |
| 29 | P594 | một cách giải thích cho việc mAP tụt mạnh khi huấn luyện | một cách giải thích cho mức tụt mAP khi huấn luyện | L6 - 'cho việc' danh từ hoá thừa |
| 30 | P604 | Toàn bộ được đóng gói sau một giao diện một nút bấm, đưa quy trình | Toàn bộ nằm sau giao diện một nút bấm, đưa quy trình | L1 - bị động thừa; L6 - lặp 'một' |
| 31 | P605 | nên toàn bộ khâu gán nhãn thủ công bị loại bỏ | nên không còn khâu gán nhãn thủ công | L1 - bị động thừa |
| 32 | P605 | hướng tiếp cận “sinh ảnh theo nhãn đã biết trước” đã chứng minh giá trị | cách làm "sinh ảnh theo nhãn đã biết trước" cho kết quả dùng được | L1 - 'hướng tiếp cận' dịch máy từ approach; L4 - 'chứng minh giá trị' tự khen; L7a - nháy cong sang nháy thẳng |
## Chưa áp được — cần sửa tay

Không có. 67/67 sửa đổi áp thành công.

Một sửa đổi ban đầu bị từ chối do chồng lấn vùng với sửa đổi nháy kép trong cùng câu (P605). Đã gộp bốn sửa đổi chồng lấn thành một và áp lại thành công.

## Cần người viết quyết định

1. **Lẫn lộn "ảnh X-quang" và "ảnh chụp phóng xạ".** Tên đề tài trên trang bìa dùng "ảnh X-quang mối hàn", phần thân dùng "chụp ảnh phóng xạ" (đúng thuật ngữ NDT tiếng Việt, tương ứng RT). Không tự sửa vì tên đề tài thuộc ràng buộc cứng nhóm 4. Hai lựa chọn: đổi tên đề tài cho khớp thân bài, hoặc thêm một câu ở mục 2.2 nói rõ hai cách gọi chỉ cùng một thứ.
2. **Gạch ngang trên trang bìa** (`TRƯƠNG NGỌC SƠN – 25210183`). Quy ước văn phong không dùng gạch ngang giữa câu, nhưng form mẫu dùng đúng ký tự này ở đúng vị trí này. Đang giữ theo form. Xác nhận lại nếu muốn đổi.
3. **Dấu chấm trong `1.611`, `18.158`, `1.097`** (22 chỗ). Script hỏi vì dấu chấm nhập nhằng giữa hàng nghìn và thập phân. Ở đây đều là hàng nghìn, đúng quy ước Việt Nam. Không sửa.

## Câu hỏi còn treo

- Có cần đổi tên đề tài để thống nhất thuật ngữ với thân bài không (điểm 1 ở trên)?
- 5 chú thích bảng đang dùng style First Paragraph: sửa luôn trong Word hay để nguyên vì hiển thị đã đúng?
