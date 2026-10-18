# Kiểm tra truy xuất 7 PDF — 2026-10-10

Thư viện `mchine-learning` hiện có đủ 7 PDF, 167 trang, 193 chunk/vector. Đối chiếu SHA-256 với 7 file nguồn tại `C:/Users/khanh/Desktop/Mchine Learning`, ID chunk, nội dung, metadata, embedding SQL/Chroma và số trang đều khớp. Không có trang thiếu, không cần import/OCR lại.

| PDF | Trang | Vector |
| --- | ---: | ---: |
| Chapter 2 Supervised Learning_p1-2.pdf | 45 | 47 |
| Chapter 3 Unsupervised Learning.pdf | 30 | 30 |
| Chapter 6_Reinforcement_Learning.pdf | 32 | 32 |
| Chapter4_Semi-Supervised Learning.pdf | 10 | 10 |
| Chapter5_Artificial Neural_Networks.pdf | 18 | 18 |
| ML_Chap1_p1.pdf | 15 | 15 |
| ML_Chap1_p2.pdf | 17 | 41 |

## Lỗi và thay đổi

Trước sửa, câu “Tóm tắt nội dung chính của tài liệu” chỉ truy xuất 4 đoạn từ 4 file vì `RETRIEVAL_K=4`, `MAX_CONTEXT_CHUNKS=5`. Tìm theo tên một PDF cũng lẫn các file khác. File đã được index nhưng không được chọn vào context.

Sau sửa, câu hỏi tổng quan tìm vector riêng từng PDF, chọn một đoạn có nội dung thay vì ưu tiên trang bìa/liên kết, chia ngân sách token cho các file. `MAX_CONTEXT_CHUNKS` mặc định và cấu hình máy này là 12, câu hỏi chi tiết vẫn lấy 4 đoạn. Tên PDF xuất hiện trong câu hỏi được dùng để lọc cả tìm vector và tìm lệnh code. Lịch sử không làm thay đổi phạm vi tổng quan của câu hỏi hiện tại.

Context/log lưu số file đã chọn, số file gửi model và trạng thái đủ file. Giao diện phân biệt số đoạn với số tài liệu; báo phạm vi chưa đủ khi cấu hình/ngân sách chỉ cho phép một phần thư viện. Tổng quan dựa trên trích đoạn đại diện, không đọc toàn bộ 167 trang trong mỗi lượt hỏi. Thư viện lớn hơn giới hạn 12 file có thể cần hỏi theo nhóm hoặc từng file.

## Kiểm thử thực tế

- Báo cáo trước sửa: `storage/retrieval-coverage-before.json` — kiểm tra vector đạt, tổng quan chỉ dùng 4 file, 7 câu hỏi theo tên file đều lẫn nguồn.
- Báo cáo sau sửa: `storage/retrieval-coverage-after.json` — tổng quan đủ 7/7 file, cả 7 truy vấn theo tên PDF đều chỉ lấy đúng file; context tổng quan 1.487 token ước lượng, dưới ngân sách 1.800.
- Gọi RAG nội bộ và model Groq thật: `storage/retrieval-live-answer.json` — 7 nguồn, câu trả lời 7 mục dẫn đủ [1]–[7], không bị cắt. Không ghi thêm hội thoại/tài liệu vào tài khoản người dùng.
- Python: 73 test đạt, 8 test SQL được bỏ qua trong lượt kiểm thử này; các test mới dùng Chroma thật với embedding kiểm thử, kiểm tra 7 file, file lớn không lấn file nhỏ, lọc lệnh code theo file, ngân sách context và trạng thái thiếu phạm vi.
- React: 13 kiểm tra render đạt; production build đạt. Không chạy kiểm tra UI bằng trình duyệt.

Tái chạy kiểm tra đọc dữ liệu và tìm vector không gọi LLM bằng `python -m scripts.check_retrieval_coverage --user-id <id> --topic mchine-learning --source "C:/Users/khanh/Desktop/Mchine Learning"`.
