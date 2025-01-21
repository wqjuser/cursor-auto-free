# Công Cụ Tự Động Hóa Cursor Pro

README cũng có sẵn bằng: [中文](./README.md), [English](./README.EN.md)

## Lời Nhắc
Gần đây có người mang phần mềm này bán trên các trang thương mại, việc này nên hạn chế. Không phải cái gì cũng cần kiếm tiền.

## Tuyên Bố Giấy Phép
Dự án này sử dụng giấy phép [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/).  
Điều đó có nghĩa là bạn có thể:  
- **Chia sẻ** — Sao chép và phân phối tác phẩm này trên mọi phương tiện hoặc định dạng.  
Nhưng phải tuân thủ các điều kiện sau:
- **Phi thương mại** — Không được sử dụng tác phẩm này cho mục đích thương mại.

## Giới Thiệu Tính Năng
Tự động đăng ký tài khoản, tự động làm mới token, giải phóng đôi tay.

## Địa Chỉ Tải Về
[https://github.com/chengazhen/cursor-auto-free/releases](https://github.com/chengazhen/cursor-auto-free/releases)

## Lưu Ý Quan Trọng
1. **Hãy đảm bảo bạn đã cài đặt trình duyệt Chrome. Nếu chưa, [tải về tại đây](https://www.google.com/intl/en_pk/chrome/).**  
2. **Bạn cần đăng nhập vào tài khoản, dù tài khoản có hiệu lực hay không, đăng nhập là bắt buộc.**  
3. **Cần có kết nối mạng ổn định, ưu tiên sử dụng máy chủ nước ngoài. Không bật proxy toàn cầu.**

## Hướng Dẫn Cấu Hình

### 1. Chuyển Tiếp Email tempmail.plus
- Cần sử dụng email theo tên miền Cloudflare. Hãy tìm hiểu cách sử dụng.  
- **(Rất quan trọng)** Cần sử dụng email tạm thời từ tempmail.plus. Hãy tìm hiểu cách sử dụng.  
- Chuyển tiếp email từ tên miền Cloudflare sang tempmail.plus.  
- Tải tệp `.env.example` về thư mục gốc của chương trình và đổi tên thành `.env`.

Cấu hình tệp `.env`:
```bash
DOMAIN='xxxxx.me'    # Tên miền email của bạn (tự tìm hiểu cách sử dụng Cloudflare email)
TEMP_MAIL='xxxxxx'   # Email tạm thời, là địa chỉ đích bạn đã thiết lập trong Cloudflare, sử dụng email từ https://tempmail.plus/zh/#!
```
Ví dụ:
```bash
DOMAIN='wozhangsan.me'
TEMP_MAIL='ccxxxxcxx'
```
Chương trình sẽ tự tạo ngẫu nhiên email với đuôi `@wozhangsan.me`.

### 2. Sử Dụng IMAP Thay Thế tempmail.plus
Nếu bạn không thể sử dụng tempmail.plus hoặc muốn một phương pháp an toàn hơn để nhận mã xác minh, bạn có thể cấu hình như sau:
```bash
DOMAIN='wozhangsan.me'
TEMP_MAIL=null

# Máy chủ IMAP
IMAP_SERVER=imap.xxxxx.com
# Cổng SSL IMAP
IMAP_PORT=993
# Email được chuyển tiếp từ CF
IMAP_USER=xxxxxx@xxxxx.com
# Mã xác thực email
IMAP_PASS=xxxxxxxxxxxxx
# [Tùy chọn] Mặc định là hộp thư đến (inbox)
# Bạn có thể đặt thành các thư mục khác nơi bạn có thể nhận email
IMAP_DIR=
```

## Cách Chạy Chương Trình

### Phiên Bản Mac
1. Mở Terminal và truy cập thư mục chứa ứng dụng.  
2. Cấp quyền thực thi tệp:  
```bash
chmod +x ./CursorPro
```  
3. Chạy chương trình:
   - Trong Terminal:  
```bash
./CursorPro
```  
   - Hoặc nhấp đôi vào tệp trong Finder.  

Nếu gặp lỗi, tham khảo [giải pháp](https://sysin.org/blog/macos-if-crashes-when-opening/).

### Phiên Bản Windows
Nhấp đúp chuột vào tệp `CursorPro.exe`.

## Xác Minh Hiệu Quả
Sau khi chạy script, khởi động lại trình chỉnh sửa. Nếu tài khoản hiển thị giống như trong log, chương trình đã hoạt động thành công.

## Lưu Ý Khi Sử Dụng
1. Yêu cầu môi trường:
   - Kết nối mạng ổn định.
   - Quyền hệ thống đủ cao.

2. Trong quá trình sử dụng:
   - Chờ chương trình tự hoàn tất.
   - Đợi thông báo "hoàn thành" trước khi đóng chương trình.

## Giải Quyết Vấn Đề Thường Gặp
1. Chương trình bị treo:
   - Kiểm tra kết nối mạng.
   - Khởi động lại chương trình.

## Tuyên Bố Miễn Trừ
Công cụ này chỉ dành cho mục đích học tập và nghiên cứu. Người dùng tự chịu trách nhiệm về mọi hậu quả. Nghiêm cấm sử dụng cho mục đích thương mại. Vi phạm giấy phép sẽ chịu trách nhiệm pháp lý.

## Tài Trợ Để Có Thêm Cập Nhật
![image](./screen/afdian-[未认证]阿臻.jpg)

## Nhật Ký Cập Nhật
- **2025-01-09**: Thêm nhật ký và tính năng tự động xây dựng.
- **2025-01-10**: Chuyển sang sử dụng email tên miền Cloudflare.
- **2025-01-11**: Thêm chế độ không giao diện và cấu hình proxy thông qua tệp .env.
- **2025-01-20**: Thêm chế độ IMAP để thay thế tempmail.plus.
Lấy cảm hứng từ [gpt-cursor-auto](https://github.com/hmhm2022/gpt-cursor-auto); đã tối ưu hóa logic xác minh và đăng ký email tự động; đã giải quyết vấn đề không thể nhận mã xác minh email.
