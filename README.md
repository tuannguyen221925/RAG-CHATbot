# BIGRAG 3.0 — React / Python / MySQL

Giao diện React, backend Python/FastAPI và MySQL/TiDB quản lý tài khoản, phiên đăng nhập, tài liệu và chat. RAG, embedding/EasyOCR trên GPU, Chroma và Groq chạy trong cùng tiến trình Python. Không cần backend Node hoặc dịch vụ riêng tại cổng 8000.

## Chạy trên máy hiện tại

Mở **http://localhost:8501**. Database trong `.env` cần truy cập được; chỉ cần chạy MySQL80 khi dùng MySQL local. Sau khi khởi động lại máy, mở PowerShell tại `E:\BIG_RAG`:

```powershell
& .\scripts\start.ps1
```

Script chạy Python ẩn, ghi log vào `storage/web.*.log` và đợi health check thành công. Nếu cổng đã dùng, script báo lỗi để tránh chạy trùng.

### Xem log và tìm lỗi

`npm run dev` hiện log API trong terminal, kể cả khi dùng lại backend chạy ẩn; log Vite và lỗi proxy cũng được lưu. Mỗi request có `rid`, HTTP method/path, status và thời gian xử lý. Lỗi server có traceback, file và dòng code; import lỗi từng PDF cũng được ghi dù cả request trả HTTP 200. Console trình duyệt ghi status và request ID cho lỗi API/upload, không ghi body đăng nhập hay query string.

- `storage/logs/api.log`: hoạt động API/RAG/OCR và lỗi.
- `storage/logs/api-error.log`: lỗi và traceback để tra cứu nhanh.
- `storage/logs/dev.log`: launcher, Vite và lỗi proxy khi chạy `npm run dev`.

```powershell
npm run logs
npm run logs:errors
npm run logs:dev
```

Mỗi lệnh hiện 50 dòng gần nhất rồi theo dõi tiếp; Ctrl+C chỉ dừng xem log. Hoặc dùng `Get-Content .\storage\logs\api-error.log -Tail 50 -Wait`. File log tự xoay khi đạt 5 MB, giữ ba bản cũ. Đặt `LOG_LEVEL=DEBUG` trong `.env` rồi khởi động lại để xem thêm; `BIGRAG_LOG_DIR` đổi thư mục log. Mật khẩu/API key/token từ biến môi trường được che trong log; không ghi nội dung PDF, câu hỏi, cookie hay request body. `storage/web.out.log` và `storage/web.err.log` vẫn giữ stdout/stderr của backend khi chạy ẩn.

Chạy thủ công:

```powershell
.\.ragvenv\Scripts\python.exe -m scripts.serve
```

Sau khi sửa React: `npm run build`, tải lại trình duyệt. Sau khi sửa Python hoặc `.env`: khởi động lại backend. `npm start` vẫn dùng được và gọi Python trong `.ragvenv`.

## Trang giới thiệu

5 trang riêng: Tổng quan (`/`), Tính năng (`/features`), Cách hoạt động (`/how-it-works`), Cá nhân hóa (`/personalization`), Không gian riêng (`/privacy`). Menu cố định khi cuộn, có menu thu gọn cho điện thoại. Trang tính năng dùng 5 thẻ chọn với minh họa, hướng dẫn xem từng bước, FAQ/thông tin sử dụng tài liệu mở rộng khi cần. Preview theme và biệt danh có thể thử trước khi đăng nhập.

Ba ảnh người học/robot chỉ xuất hiện ở trang tổng quan. Nền đường nét, thẻ demo và sticker chuyển động bằng CSS/React; có công tắc tạm dừng và mặc định tôn trọng chế độ giảm chuyển động của thiết bị. Các đường dẫn `/#how`, `/#features`, `/#privacy` cũ chuyển sang trang tương ứng.

## Tài khoản và dữ liệu

- MySQL lưu người dùng, **bcrypt cost 12**, phiên, chủ đề, tin nhắn, nguồn trích dẫn/usage, **PDF gốc LONGBLOB**, văn bản, vector embedding và bản dịch.
- Mật khẩu tối thiểu 8 ký tự, tối đa 72 byte UTF-8; từ chối mật khẩu quá dài trước khi bcrypt cắt ngầm.
- Phiên bằng cookie **HttpOnly, SameSite=Lax**, 7 ngày; MySQL lưu SHA-256 của token. Đăng xuất thu hồi phiên. Không lưu tài khoản, mật khẩu hay token vào localStorage.
- Giới hạn sai đăng nhập 5 lần/15 phút, kiểm tra nguồn yêu cầu chống CSRF; mọi tài liệu, preview và hội thoại đều kiểm tra chủ sở hữu.
- User MySQL riêng chỉ có SELECT/INSERT/UPDATE/DELETE. `.env` hiện chứa credential ứng dụng, không giữ credential root và không được đưa lên Git/frontend.
- Kết nối MySQL dùng UTC để kiểm tra thời hạn nhất quán. Backend chỉ bind localhost; engine RAG nội bộ nhận token và workspace từ Python API, không được công khai qua `/api`.
- Nếu đặt sau HTTPS reverse proxy, cấu hình `COOKIE_SECURE=true` và `PUBLIC_ORIGIN` theo địa chỉ công khai.

Tài khoản đăng ký đầu tiên nhận thư viện cũ (gồm **Mchine Learning**), các tài khoản sau có tài liệu/chat riêng. Thư viện cũ đã nằm trong MySQL ở `legacy_topics`/`legacy_documents`; việc nhận thư viện cùng transaction với đăng ký, chỉ một chủ sở hữu ngay cả khi đăng ký đồng thời.
Chroma và `data/` là bản phục vụ xử lý/tìm kiếm; MySQL giữ PDF/vector chuẩn. Workspace riêng: `data/.users/<id>`, `vector_db/.users/<id>`.

Sao lưu đầy đủ database được cấu hình trong `.env` bằng MySQL Workbench/mysqldump để giữ PDF, vector và lịch sử; giữ `.env` riêng. Nếu mất cache, phục hồi MySQL, giữ nguyên model embedding rồi chạy:

```powershell
.\.ragvenv\Scripts\python.exe -m scripts.restore_library
```

Script khôi phục workspace đã có tài khoản từ PDF/vector MySQL, không embedding lại. `.\.ragvenv\Scripts\python.exe -m scripts.migrate_library` đồng bộ thư viện cũ trước khi đăng ký.

## Sử dụng

1. Đăng ký/đăng nhập, tạo chủ đề bằng dấu **+** bên cạnh thư viện.
2. **Tài liệu**: chọn PDF rồi **Nhập tài liệu**. Tối đa 10 file, 50 MB/file và 75 MB/lượt. Trùng SHA-256 trong cùng chủ đề được bỏ qua. PDF được gửi lần lượt; bảng tiến trình hiển thị phần trăm tải lên, file đang xử lý, thời gian chờ và kết quả từng file. Phần trăm tổng tính theo số PDF đã xử lý, không ước lượng thời gian OCR. Bạn có thể chuyển tab/thư viện trong lúc nhập; giữ trang mở để tiếp tục gửi các file còn lại. Các file lỗi được giữ lại để thử lại.
3. **Dịch & xem trước khi nhập**: chọn ngôn ngữ, đọc/sửa từng trang, lưu trang, nhập bản gốc hoặc bản dịch. Preview lưu MySQL và xác nhận được ngay cả sau khi worker khởi động lại.
4. **Trò chuyện**: hỏi đáp có nguồn, số trang, đoạn trích. Sidebar cho phép tìm, mở lại, đổi tên và xóa chat; nút tải trong hội thoại xuất `.txt`. Chat mới không xóa lịch sử cũ.
5. **Dịch văn bản**: 19 ngôn ngữ, Groq/Google Cloud Translation, chế độ rà soát/nhanh và thuật ngữ chuyên ngành cho Groq.
6. **Cá nhân hóa** (biểu tượng bảng màu cạnh tên trợ lý): đặt biệt danh cho trợ lý và chọn một trong 7 theme. Tin nhắn của người dùng ở bên phải, bot ở bên trái; tên hiển thị theo tên tài khoản và biệt danh bot. Mỗi thư viện có biệt danh/theme riêng trong MySQL, vẫn giữ sau khi tải lại hoặc đăng nhập lại; có nút khôi phục mặc định.

Khung chat mới có menu thư viện/lịch sử thu gọn, lịch sử nhóm theo ngày, ô nhập cố định và bảng thông tin thư viện mở khi cần. Chọn thẻ gợi ý để điền câu hỏi; **Enter** gửi, **Shift + Enter** xuống dòng. Khi đọc tin cũ, nút **Tin nhắn mới nhất** đưa về cuối hội thoại. Câu trả lời hiển thị Markdown (tiêu đề, danh sách, bảng, code), có nút sao chép và nguồn tham khảo mở từng đoạn trích. Giao diện tài liệu, dịch và popup cá nhân hóa cùng dùng theme thư viện. Trên điện thoại, menu chuyển thành ngăn kéo; menu đóng được ẩn khỏi điều hướng bằng bàn phím.

[Báo cáo thiết kế và kiểm thử workspace](reports/workspace-redesign-2026-10-09.md).

**Avatar**: bấm avatar cạnh hồ sơ để đổi ảnh của bạn; bấm avatar bot ở đầu khung chat hoặc **Cá nhân hóa → Đổi avatar bot** để đổi ảnh trợ lý. Có 10 lựa chọn gồm mặc định, robot, thú nhỏ, hoa/cây và vũ trụ. Chọn ảnh JPG/PNG/WebP từ máy (tối đa 5 MB, 20 triệu pixel), zoom/dịch vị trí trong khung tròn rồi **Lưu avatar**. Avatar cá nhân dùng cho mọi thư viện; avatar bot riêng từng thư viện. Ảnh và lựa chọn lưu MySQL, ảnh được chuyển thành JPEG 384 × 384 và chỉ tải được qua phiên của chủ tài khoản. Có nút dùng mặc định và giữ ảnh hiện tại.

Máy hiện tại đã có bảng `avatars`. Khi nâng cấp một database cũ ở máy khác, dùng `MYSQL_ADMIN_USER` / `MYSQL_ADMIN_PASSWORD` tạm thời rồi chạy `.\.ragvenv\Scripts\python.exe -m scripts.migrate_avatars`; migration chỉ thêm bảng cho database được cấu hình. Không cần chạy lại `db:setup`. [Báo cáo avatar](reports/avatar-customization-2026-10-09.md).

Hội thoại gửi tối đa 8 tin nhắn gần đây, 600 token ước lượng; câu trả lời mới trích nguồn truy xuất hiện tại. Groq cần API key khi hỏi/dịch; import bản gốc và OCR chạy local. Google cần `GOOGLE_TRANSLATE_API_KEY` khi chọn provider Google. Chưa có xác minh email hay khôi phục mật khẩu qua email.

Câu hỏi tổng quan như “Tóm tắt nội dung chính của tài liệu” tìm riêng từng PDF, lấy một đoạn đại diện mỗi file và chia đều ngân sách context; mặc định tối đa 12 file (`MAX_CONTEXT_CHUNKS=12`). Câu hỏi chi tiết vẫn dùng `RETRIEVAL_K=4`; khi ghi đúng tên PDF, cả tìm vector và tìm lệnh code đều lọc theo file đó. Số đoạn tham khảo khác số file: giao diện hiện cả hai. Nếu giới hạn context khiến tổng quan chưa dùng đủ các file, giao diện báo số file đã dùng. Log ghi `selected_files`, `sent_files`, `coverage_complete` để phân biệt thiếu vector với thiếu context. Đây là tổng quan từ các trích đoạn, không phải đọc toàn bộ mọi trang cho mỗi câu hỏi.

Kiểm tra SQL/vector và truy xuất từng file mà không import lại hay gọi LLM:

```powershell
.\.ragvenv\Scripts\python.exe -m scripts.check_retrieval_coverage --user-id <id-tai-khoan> --topic <ma-thu-vien> --source "C:\duong-dan\PDF"
```

## GPU và lỗi import

Máy này dùng RTX 2050 4 GB, PyTorch CUDA trong `.ragvenv`, `.env` bật `EMBEDDING_DEVICE=cuda`, `OCR_GPU=true`, batch 16. Reranker mặc định tắt, dùng CUDA khi bật. Đọc PDF/chia đoạn/Chroma dùng CPU; LLM dùng Groq. Giảm batch xuống 8 hoặc 4 nếu thiếu VRAM.

Lỗi cũ: launcher venv trỏ về Python tại `E:\RAG` sau khi chuyển sang `E:\BIG_RAG`; Python đó có PyTorch CPU. Đã sửa launcher, cài CUDA đúng môi trường, thêm kiểm tra thiết bị và sửa lỗi dọn file tạm WinError 32 khi Poppler còn giữ PDF. [Báo cáo import Mchine Learning](reports/import-mchine-learning-2026-10-09.md).

```powershell
.\.ragvenv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Khi lại di chuyển venv:
.\.ragvenv\Scripts\python.exe scripts/repair_venv.py
```

## Cài máy mới / phát triển

Cần Node.js 22+ để build React, Python 3.11+, MySQL 8 hoặc TiDB Cloud, Poppler. Tạo `.ragvenv`, cài `requirements.txt` và `requirements-gpu.txt` cho NVIDIA, chạy `npm ci`, `npm run build`. Copy `.env.example` chỉ khi chưa có `.env`.
Lần đầu, điền credential quản trị MySQL vào `.env`, chạy `.\.ragvenv\Scripts\python.exe -m scripts.setup_mysql` (hoặc `npm run db:setup`): tạo schema, user CRUD, thay credential quản trị bằng credential ứng dụng và tạo secret nội bộ. **Database hiện tại đã setup, không cần chạy lại.** Điền Groq key/đường dẫn Poppler khi cần.
Nếu dùng TiDB Cloud, đặt `MYSQL_MANAGED=true`, `MYSQL_SSL=true` và thông tin kết nối cloud trong `.env`, rồi chạy `npm run db:setup` một lần cho database mới. Chế độ managed tạo các bảng còn thiếu và giữ nguyên credential. Database mới chưa có tài khoản hoặc dữ liệu từ MySQL local.

Chạy cả Python API và React dev bằng một lệnh:

```powershell
npm run dev
```

Mở **http://127.0.0.1:5173**. `npm run dev` tự chạy Python tại `WEB_PORT` (mặc định 8501), đợi API sẵn sàng rồi mở Vite. Nếu API đã chạy thì dùng lại; khi dừng dev chỉ dừng API do lệnh đó tạo. Proxy giữ nguyên header `Host` để kiểm tra CSRF hoạt động. Muốn tự quản lý hai terminal: `npm run dev:api` (Python có `--reload`) và `npm run dev:ui` (chỉ Vite). Kiểm tra `http://127.0.0.1:5173/api/health`: cần có `backend: python`, `schema: ready` và `rag: in-process`.

OCR render từng trang, đóng ảnh và giải phóng layout pdfplumber sau mỗi trang, dùng lại một EasyOCR reader. Trang có ảnh lớn dù có tiêu đề/footer native vẫn được kiểm tra OCR. GPU dùng `OCR_BATCH_SIZE=4`; khi thiếu VRAM, tự giảm batch rồi giảm canvas. Trang không có text OCR được thử lại ở DPI cao hơn và giữ text native nếu có. Kết quả từng trang được lưu trong `.ocr-cache/` của thư viện để thử lại không quét lại các trang đã xong; xóa PDF cũng dọn cache tương ứng. API trả `total_pages` và `empty_pages`, giao diện hiển thị độ phủ trang, lỗi ghi rõ trang thay vì âm thầm bỏ qua. `OCR_PAGE_TIMEOUT=120` là giới hạn render cho từng trang, không áp lên cả file. [Kết quả test 7 PDF, 167 trang](reports/ocr-import-2026-10-10.md).

**Chất lượng OCR cho slide/code:** máy hiện tại dùng `OCR_ENGINE=paddle` với PP-OCRv5 chạy CPU, giữ VRAM cho embedding. Cài ở máy mới bằng `python -m pip install -r requirements-ocr-quality.txt`, rồi đặt `OCR_ENGINE=paddle` trong `.env`. Pipeline lấy trực tiếp ảnh nội dung từ PDF, giữ cả hình nhỏ, bỏ nền/logo trang trí, tách cột tại khoảng trắng và đọc từng dòng. Tự chọn bộ đọc tiếng Anh theo text native của nhiều trang; giữ bộ Latin cho tài liệu Việt. Các ngôn ngữ khác dùng EasyOCR. `OCR_GPU`/`OCR_BATCH_SIZE` áp dụng cho EasyOCR, không điều khiển Paddle CPU.

Cache có mã engine, ngôn ngữ và phiên bản thuật toán để không dùng lại text OCR cũ. Khi đổi engine, PDF đã có vector vẫn cần dựng lại chỉ mục: `scripts/repair_ocr_index.py` chỉ cập nhật các PDF gốc khớp SHA-256 trong tài khoản được chỉ định, lưu backup chunk/vector, giữ PDF, ID và chat. Script này chỉnh dữ liệu thật; dùng email và thư mục nguồn cụ thể. Kiểm tra chất lượng bằng `scripts/check_ocr_quality.py`: so tên hàm và dòng code thực tế, thay cho chỉ đếm số trang/từ khóa chung. Ảnh nguồn quá nhỏ vẫn có thể sai ký tự; không dùng LLM để tự đoán rồi ghi đè code.

[Báo cáo kiểm tra chất lượng OCR và dựng lại chỉ mục](reports/ocr-quality-2026-10-10.md).

Backend: `api/web.py` (route public), `api/security.py` (auth), `api/db.py` / `api/schema.sql` (SQL), `api/avatars.py`, `api/library.py`. `api/main.py` là engine RAG gọi trong tiến trình, không phải lệnh khởi động website. Bcrypt và cookie cũ vẫn tương thích; không cần tạo lại tài khoản, PDF hoặc chat sau khi chuyển từ Node trên cùng database.

## Kiểm thử

```powershell
# Opt-in SQL integration: tạo database test riêng và dọn sau từng test.
$env:BIGRAG_RUN_DB_TESTS = '1'
.\.ragvenv\Scripts\python.exe -m pytest -q
npm run test:ui
npm run test:import
npm run build
```

Python kiểm tra RAG bằng PDF/Chroma thật trong thư mục tạm và embedding xác định, không gọi Groq. `tests/test_web.py` kiểm tra API public với SQL thật: bcrypt, cookie/session cũ, hết hạn/đăng xuất, CSRF, hai tài khoản, PDF blob/vector, chat, theme, avatar, preview sau khi mất cache và đăng ký đồng thời. Khi bật `BIGRAG_RUN_DB_TESTS=1`, credential test cần quyền CREATE/DROP DATABASE; mỗi test tạo tên ngẫu nhiên `big_rag_tests_<hex>` và chỉ xóa database đó. Nếu không bật, 7 SQL tests được bỏ qua. `npm run test:api` chỉ chạy bộ API này.

`test:ui` có 9 kiểm tra render chat: Markdown, bảng, code, tên tài khoản, biệt danh/nguồn PDF, trạng thái bắt đầu, avatar người dùng/bot và chặn HTML/link không an toàn/ảnh từ xa. JavaScript còn lại thuộc frontend React, cấu hình Vite, dữ liệu theme/avatar và kiểm tra render giao diện; backend và các script SQL/migration dùng Python.
Mã Streamlit/SQLite cũ được lưu tại `.ragvenv/legacy-streamlit/`, không tham gia runtime.
