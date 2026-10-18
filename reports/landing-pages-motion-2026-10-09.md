# Cập nhật trang giới thiệu BIGRAG

## Kết quả

- Menu cố định trên cùng khi cuộn; 5 trang riêng: Tổng quan, Tính năng, Cách hoạt động, Cá nhân hóa và Không gian riêng.
- Rút các đoạn giải thích dài thành tiêu đề, một câu mô tả và thẻ minh họa. Trang tính năng có 5 nút chọn, chỉ hiện phần đang xem; hướng dẫn có 5 bước chọn được và nút tiếp theo. FAQ và thông tin sử dụng tài liệu mở rộng khi cần.
- Minh họa bằng HTML/CSS và icon: giấy PDF vào thư viện, chat kèm nguồn, hai bản dịch, lịch sử chat và bảng màu. Sticker, giấy, tin nhắn, nền đường nét chuyển động nhẹ.
- Ba ảnh người dùng cung cấp chỉ ở trang tổng quan: hai người học quanh cửa sổ demo và robot bên cạnh. Cửa sổ chuyển giữa thư viện, hỏi đáp và bản dịch; có nhãn minh họa.
- Tông nền pastel dịu hơn, chữ chính tương phản rõ, giảm phần trang trí lặp lại. Theme và biệt danh vẫn có bản thử trực tiếp trước đăng nhập.
- Có công tắc chuyển động. Mặc định tôn trọng chế độ giảm chuyển động của thiết bị; người xem có thể bật thủ công. Tạm dừng vẫn giữ đầy đủ nội dung.

## Kiểm tra

- `npm run build` thành công.
- Kiểm tra trực tiếp trình duyệt: chuyển cả 5 thẻ tính năng, đi hết 5 bước hướng dẫn, mở FAQ, đổi theme/biệt danh và bật/tắt chuyển động.
- Xác nhận CSS animation chuyển sang `running` khi bật, cả 3 ảnh tải thành công. Ảnh chỉ dùng ở trang tổng quan.
- Khi cuộn tới FAQ: scrollY = 264, header vẫn top = 0, position = fixed.
- Kiểm tra menu, thẻ tính năng, form đăng ký/đăng nhập ở chiều rộng 390 px; kiểm tra thêm 320 px và sửa thanh menu/thẻ minh họa cho màn hình hẹp. Không tràn ngang.
- Tải lại trực tiếp `/features`, quay lại trong trình duyệt và chuyển `/#how` sang `/how-it-works` thành công. Không có lỗi console sau kiểm tra.

## Mã và ảnh kết quả

- `src/marketing/Landing.jsx`, `src/marketing/marketing.css`, tích hợp tại `src/App.jsx`.
- Ảnh cung cấp: `public/images/learner-one.png`, `learner-two.png`, `robot-assistant.png`.
- [Tổng quan](landing-overview-visual.png)
- [Tính năng](landing-features-visual.png)
- [Menu khi cuộn](landing-sticky-navigation.png)
- [Giao diện di động](landing-features-mobile.png)
