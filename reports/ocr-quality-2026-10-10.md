# Kiểm tra lại chất lượng OCR — 10/10/2026

Phản hồi của người dùng cho thấy chatbot vẫn gặp đoạn OCR sai. Kiểm tra độ phủ 167 trang trước đó chưa chứng minh độ chính xác của code. Đối chiếu nguồn thật xác định trang 9 của `ML_Chap1_p2.pdf` chứa bảng NumPy ba cột, ảnh gốc chỉ 1024 × 725 pixel; nhiều ký tự code bị nhận sai.

## Thay đổi

- Dùng PP-OCRv5 trên CPU cho tiếng Anh/Việt; embedding tiếp tục dùng GPU. Các ngôn ngữ khác giữ EasyOCR.
- Lấy ảnh nội dung nhúng trong PDF, giữ cả các hình nhỏ, tách cột theo khoảng trắng và đọc từng dòng. Chọn bộ đọc tiếng Anh theo nhiều trang native để tránh nhận nhầm ngôn ngữ từ trang bìa Việt.
- Cache phân biệt engine, ngôn ngữ và phiên bản thuật toán. Đã dựng lại chỉ mục của bảy PDF khớp SHA-256 cho tài khoản Nhi và tài khoản thư viện cũ, giữ PDF gốc, ID và lịch sử chat.
- Kiểm tra hỏi đáp phát hiện semantic/MMR lấy nhầm đoạn kiểu dữ liệu thay cho đoạn chứa hàm được hỏi. Đã bổ sung tìm kiếm literal tên hàm/câu lệnh, ưu tiên tối đa hai đoạn code và kết hợp với kết quả semantic; câu hỏi thông thường giữ cách truy xuất hiện có.
- Chốt Kubernetes client ở phiên bản tương thích với yêu cầu PyYAML của PaddleX; `pip check` không còn dependency bị xung đột.

## Kết quả thực tế

| Mục kiểm tra | OCR trước | OCR mới |
| --- | --- | --- |
| 24 mẫu code/tên hàm trên trang NumPy | 0/24 | 17/24 |
| 3 dòng code nguyên văn được đối chiếu | 0/3 | 3/3 |

Ba dòng kiểm tra là `import numpy as np`, `np.arange(10,25,5)` và `np.linspace(0,2,9)`; phép so code chỉ bỏ qua khoảng trắng. Các mẫu tham chiếu được đọc từ ảnh gốc, gồm lời gọi phương thức `e.dot(f)`. Đây là kiểm tra một trang khó, không phải tỷ lệ đúng của toàn bộ PDF. Đọc trang này mất 52,69 giây gồm khởi tạo model; không khẳng định chế độ chất lượng mới nhanh hơn EasyOCR GPU.

Dựng lại 14 bản PDF hoàn tất trong 937,25 giây, dùng lại kết quả OCR giữa hai tài khoản. Mỗi tài khoản đủ 7 PDF, 167 trang, trong đó 59 trang dùng OCR. Bước kiểm tra sau khi lưu đối chiếu tất cả ID đoạn, text, metadata và embedding giữa SQL với Chroma: khớp; nội dung NumPy đã sửa có trong cả hai tài khoản; các tin nhắn lịch sử còn nguyên.

59 bài kiểm thử Python đạt; 8 bài SQL integration mặc định được bỏ qua ở lượt chạy này. Việc sửa dữ liệu và đối chiếu trên SQL thật đã chạy thành công. Health qua Vite `127.0.0.1:5173` trả API Python, SQL/schema sẵn sàng, RAG chạy trong tiến trình.

Kiểm tra hỏi đáp thật qua web với tài khoản Nhi: yêu cầu trích lệnh import và ví dụ arange/linspace, không đưa trước các tham số số trong câu hỏi. Câu trả lời và trích đoạn nguồn cùng khớp 3/3 dòng code; dẫn `ML_Chap1_p2.pdf`, trang 9. Chi tiết ở `storage/ocr-quality-live-check.json`.

Hỏi lại đúng câu ban đầu “Tóm tắt nội dung chính của tài liệu” trong chat mới: câu trả lời đề cập học bán giám sát, lịch sử mạng nơ-ron và API trực quan hóa. Vẫn có một tên kiến trúc bị sai theo text OCR, nên không coi việc câu trả lời mới không báo “nhiều lỗi OCR” là chứng nhận chất lượng. Chi tiết ở `storage/ocr-library-summary-check.json`.

## Giới hạn

Ảnh chữ/code gốc quá nhỏ vẫn còn ký tự nhận sai, gồm dấu câu và một số tên hàm. Không dùng LLM để đoán rồi ghi đè code OCR. Tin nhắn cũ không tự được tạo lại; dùng cuộc trò chuyện mới để hỏi trên chỉ mục mới.

Chi tiết cục bộ: `storage/ocr-quality-final.json`, `storage/ocr-quality-repair/report.json`; backup từng tài liệu ở `storage/ocr-quality-repair/*-before.json`. Các báo cáo không chứa mật khẩu hoặc cookie đăng nhập.
