# Báo cáo sửa lỗi import Mchine Learning

Ngày kiểm tra: 09/10/2026 (Asia/Bangkok).

Đã import thành công 7/7 PDF bản gốc vào chủ đề **Mchine Learning** (`mchine-learning`): 167 trang, 188 đoạn nội dung, 41 trang dùng OCR. Embedding và EasyOCR được xác nhận chạy CUDA trên RTX 2050.

## Kết quả từng file

| File | Trang | Trang OCR | Đoạn | Thời gian (giây) | Kết quả |
| --- | ---: | ---: | ---: | ---: | --- |
| Chapter 2 Supervised Learning_p1-2.pdf | 45 | 4 | 47 | 32.16 | Thành công |
| Chapter 3 Unsupervised Learning.pdf | 30 | 1 | 30 | 2.60 | Thành công |
| Chapter 6_Reinforcement_Learning.pdf | 32 | 13 | 32 | 22.42 | Thành công |
| Chapter4_Semi-Supervised Learning.pdf | 10 | 1 | 10 | 1.22 | Thành công |
| Chapter5_Artificial Neural_Networks.pdf | 18 | 3 | 18 | 5.80 | Thành công |
| ML_Chap1_p1.pdf | 15 | 10 | 16 | 37.86 | Thành công |
| ML_Chap1_p2.pdf | 17 | 9 | 35 | 58.30 | Thành công |

Tổng thời gian import: 160.36 giây, gồm nạp model lần đầu.

## Vì sao lỗi

Môi trường `.ragvenv` đã được di chuyển từ `E:\RAG` sang `E:\BIG_RAG`. Các launcher `streamlit.exe`, `uvicorn.exe`, `pip.exe` vẫn chứa đường dẫn tuyệt đối đến `E:\RAG\.ragvenv\Scripts\python.exe`. Kích hoạt đúng thư mục không thay đổi đường dẫn nằm bên trong launcher.

Bản PyTorch CUDA 2.14.1+cu126 đã cài ở `E:\BIG_RAG`, nhưng lệnh `streamlit run app.py` trong log lại nạp PyTorch CPU từ `E:\RAG`. Khi embedding chuyển model sang thiết bị `cuda`, PyTorch báo `AssertionError: Torch not compiled with CUDA enabled`. EasyOCR cũng tự chuyển về CPU, làm việc đọc các trang ảnh chậm. Lần sửa GPU trước đã cài đúng CUDA nhưng còn sót bước sửa launcher.

`WinError 32` xuất hiện sau khi dừng ứng dụng trong lúc xử lý OCR: một tiến trình còn giữ PDF tạm khi Python dọn thư mục. Đây là lỗi phụ lúc dừng, không phải nguyên nhân lỗi embedding. Cảnh báo thiếu HF_TOKEN không làm import thất bại.

## Đã sửa

- Tạo và chạy `scripts/repair_venv.py`: sửa 76 launcher theo Python hiện tại, cập nhật cấu hình venv và các script activation, giữ nguyên thư viện đã cài.
- Kiểm tra trực tiếp launcher `streamlit`, `uvicorn`, `pip`: đều trỏ về `E:\BIG_RAG\.ragvenv`.
- Thêm kiểm tra CUDA trước khi UI đọc/OCR file để báo rõ môi trường đang chạy sai.
- Embedding, reranker và OCR báo lỗi cấu hình rõ ràng nếu yêu cầu CUDA nhưng không có; OCR không tự hạ xuống CPU trong trường hợp này.
- Dọn thư mục preview với `ignore_cleanup_errors=True` để lỗi dọn tệp trên Windows không che lỗi gốc khi dừng OCR.

## Kiểm chứng

- 43 kiểm thử tự động đều đạt, gồm lỗi PyTorch CPU khi yêu cầu CUDA và kiểm tra GPU trước OCR.
- So sánh SHA-256: cả 7 PDF lưu trong `data/mchine-learning` khớp bản gốc.
- Đếm và đối chiếu vector theo từng file; tổng 188 đoạn trong Chroma.
- Import lại cả 7 file: tất cả trả `skipped`, tổng vector không tăng.
- Truy xuất thử 4 câu hỏi: nhận được nguồn và số trang trong đúng chủ đề.
- Kiểm tra giao diện bằng AppTest: hiển thị 7 PDF và 188 đoạn, ô hỏi đáp hoạt động.
- UI cổng 8501 và API cổng 8000 trả trạng thái khỏe.
- Đoạn dài nhất đưa vào embedding: 483/512 token. Cảnh báo 687 > 512 trong lúc đếm văn bản trước chia đoạn không phải độ dài đoạn thực sự gửi tới model.

## Cách mở lại

Ứng dụng đã được nâng cấp sang React/Node/MySQL sau lần sửa lỗi import này. Mở http://localhost:8501, đăng ký tài khoản đầu tiên để nhận thư viện **Mchine Learning**. Các kết quả AppTest/43 tests ở trên ghi nhận thời điểm bản Streamlit cũ còn hoạt động; kiến trúc hiện tại được kiểm thử riêng theo README.

```powershell
cd E:\BIG_RAG
& .\scripts\start.ps1
```

Runtime hiện tại không dùng Streamlit. Chi tiết vận hành và sao lưu MySQL xem [README](../README.md).
