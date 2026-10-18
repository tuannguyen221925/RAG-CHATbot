# Kiểm tra khởi động và OCR — 10/10/2026

Đã tạo tài khoản **Nhi**, email **nhinm@gmail.com**, với mật khẩu do người dùng cung cấp. Không lưu mật khẩu vào báo cáo hoặc script. Thư viện thử nghiệm: **Machine Learning OCR Test**. Tài liệu của tài khoản khác không bị thay đổi.

## Nguyên nhân và thay đổi

- `npm run dev` trước đây chỉ mở Vite, nên proxy báo `ECONNREFUSED` nếu Python tại cổng 8501 chưa chạy. Lệnh hiện gọi `scripts.dev`, tự khởi động API, đợi health check rồi mở Vite; dùng lại API đang chạy. `dev:ui` và `dev:api` vẫn hỗ trợ chạy riêng.
- Loader người dùng sửa đã render toàn bộ PDF thành danh sách ảnh khi gặp trang OCR đầu tiên. Thời gian render 120 giây áp lên toàn bộ file và ảnh giữ trong RAM đến hết file. Nay render từng trang, đóng ảnh và giải phóng layout pdfplumber sau mỗi trang.
- Khôi phục hàm `ocr_page`; các bài kiểm tra cũ đang sử dụng hàm này đã thất bại với loader trước đó.
- Phát hiện thêm slide có tiêu đề/footer native nhưng nội dung nằm trong ảnh lớn, thay vì chỉ dùng ngưỡng số ký tự.
- Cache OCR từng trang trong workspace riêng, dùng lại khi import lỗi rồi thử lại. Khi xóa PDF/thư viện, cache tương ứng cũng được dọn.
- Dùng batch nhận dạng nhỏ trên GPU (`OCR_BATCH_SIZE=4`), giảm xuống 1 rồi giảm canvas nếu thiếu VRAM. Thoát khỏi khối exception trước khi thu hồi bộ nhớ để traceback không giữ tensor của lần lỗi.
- Thử DPI cao hơn nếu OCR chưa thấy chữ; giữ text native nếu OCR rỗng. Lỗi thật ghi số trang và làm import file thất bại, không coi file đọc dở là thành công.
- API trả số trang tổng và các trang không có chữ; giao diện tiến trình hiển thị số trang đã nhập, số trang OCR và số trang không đọc được nếu có.

## Import thật qua API, EasyOCR CUDA và embedding thật

7 PDF tại thư mục người dùng cung cấp, tổng 167 trang. Ít nhất 41 trang dưới ngưỡng 40 ký tự native; cơ chế phát hiện ảnh lớn đã chọn thêm các trang phù hợp.

| PDF | Trang gốc | Trang trong chỉ mục | Trang OCR | Thời gian (giây) |
| --- | ---: | ---: | ---: | ---: |
| Chapter 2 Supervised Learning_p1-2.pdf | 45 | 45 | 6 | 38.22 |
| Chapter 3 Unsupervised Learning.pdf | 30 | 30 | 4 | 8.61 |
| Chapter 6_Reinforcement_Learning.pdf | 32 | 32 | 15 | 25.38 |
| Chapter4_Semi-Supervised Learning.pdf | 10 | 10 | 8 | 15.16 |
| Chapter5_Artificial Neural_Networks.pdf | 18 | 18 | 6 | 17.41 |
| ML_Chap1_p1.pdf | 15 | 15 | 10 | 58.66 |
| ML_Chap1_p2.pdf | 17 | 17 | 10 | 92.75 |
| **Tổng** | **167** | **167** | **59** | **258.58 gồm kiểm tra cuối** |

Không có trang thiếu trong metadata vector; cả 7 PDF có trạng thái sẵn sàng trong SQL. Chế độ tự động dùng OCR cho 59 trang cần thiết, trích xuất text native ở các trang còn lại. Đây là kiểm tra độ phủ trang, không phải chứng nhận đúng mọi ký tự/công thức.

Đợt import đầy đủ chạy với batch nhận dạng 1. Sau đó cấu hình batch 4 được kiểm tra riêng trên trang 9 của ML_Chap1_p2 (cheat sheet nhiều cột, chữ nhỏ): nhận dạng 3.511 ký tự, có 5/6 từ khóa kiểm tra, hoàn tất trong 20.52 giây gồm khởi tạo model. Không dùng kết quả này để khẳng định mức tăng tốc so với batch 1.

Sau khi nạp lại backend cuối cùng, đăng nhập Nhi qua proxy 5173 và gửi lại 7 PDF: tất cả được bỏ qua đúng theo SHA-256, không tạo bản sao; vẫn đủ 167 trang, kiểm tra mất 3.75 giây.

## Kiểm thử

- Bộ Python: 49 passed, 8 SQL tests skipped; chạy riêng cả 8 SQL integration tests: 8 passed.
- Sau các sửa cuối cho batch/cache: 8 OCR tests passed, gồm giới hạn render một trang, đóng ảnh, retry DPI, retry VRAM, cache sau lỗi, giữ native text và dọn cache đúng PDF.
- 9 kiểm tra render chat, 6 nhóm kiểm tra upload/progress và production build: đạt.
- Chạy dev dùng API có sẵn: health qua 5173 trả `backend=python`, `schema=ready`, `rag=in-process`.
- Chạy dev từ đầu trên cặp cổng thử 8512/5175: API được tự tạo, health qua proxy thành công. Khi dừng API thử, dev phát hiện và dừng Vite thử. Các tiến trình thử đã dọn; backend chính ở 8501, frontend ở 5173.

Chi tiết máy đọc: `storage/pdf-audit.json`, `storage/live-import-report.json`, `storage/live-import-recheck.json`, `storage/ocr-dense-page-sample.json`. Các file này không chứa mật khẩu hay cookie đăng nhập.
