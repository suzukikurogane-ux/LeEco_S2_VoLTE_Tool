# HƯỚNG DẪN SỬ DỤNG: CÔNG CỤ TỰ ĐỘNG FIX VoLTE CHO LeEco Le S2 / Le 2 (MSM8976)

---

## 1. GIỚI THIỆU
Đây là bộ công cụ **1-Click Tự động kích hoạt VoLTE (Voice over LTE) và IMS** dành riêng cho dòng điện thoại LeEco chạy chip **Qualcomm Snapdragon 652 (MSM8976)**.

Công cụ can thiệp trực tiếp vào chip nhớ **Modem Hexagon EFS** thông qua giao thức **Qualcomm DIAG (HDLC framing)** chuẩn, tự động:
* Tắt yêu cầu đàm phán Precondition SIP (`qipcall_precondition_enable = 00`) để tương thích hoàn toàn với mạng Viettel.
* Tắt yêu cầu đàm phán QoS bắt buộc (`qipcall_qos_enabled = 00`).
* Nạp đầy đủ profile dịch vụ MMTel Voice & Video Call vào `qipcall_config_items` và `qp_ims_reg_config_db`.
* Thiết lập chế độ ưu tiên gọi qua IMS LTE (`voice_domain_pref = 03`).
* Tự động thêm APN `ims` chuyên dụng và kích hoạt cờ VoLTE trong Telephony Provider.

---

## 2. DANH SÁCH THIẾT BỊ HỖ TRỢ
* **Hỗ trợ tối ưu (95% - 99% thành công):**
  * LeEco Le S2 (`Le X520`)
  * LeEco Le 2 (`Le X526`)
  * LeEco Le 2 (`Le X527`)
  * LeEco Le S2 (`Le X528`)
* ⚠️ **CẢNH BÁO AN TOÀN (CHỐNG BRICK):**
  * **TUYỆT ĐỐI KHÔNG CHẠY TRÊN:** LeEco Le 2 phiên bản chip **MediaTek Helio X20 (Le X620)**. Tool đã tích hợp chốt chặn tự động nhận diện SoC, nếu phát hiện chip MTK sẽ lập tức dừng lại để bảo vệ máy.

---

## 3. CÁC ĐIỀU KIỆN CẦN CHUẨN BỊ
1. **Điện thoại:**
   * **Trạng thái máy:** Bật nguồn bình thường, mở khóa vào màn hình chính (KHÔNG cần vào TWRP hay Fastboot).
   * **Quyền hạn:** Máy đã Unlock Bootloader và đã cài **Root (Magisk)** để cấp quyền cho tool.
   * **Bật Gỡ lỗi USB:** Vào *Cài đặt ➔ Tùy chọn nhà phát triển ➔ Bật "Gỡ lỗi USB" (USB Debugging)*.
   * *(Lưu ý: Khi cắm cáp, nhớ để ý màn hình điện thoại để bấm "Cho phép gỡ lỗi USB" và bấm "Cho phép" khi Magisk hỏi quyền SuperUser).*
2. **SIM & Nhà mạng (Hỗ trợ tất cả các nhà mạng):**
   * Tool tự động nạp cấu hình APN IMS cho **Viettel**, **VinaPhone** (kể cả Wintel, iTel), **MobiFone** (kể cả FPT) và bất kỳ SIM hiện tại nào.
   * Đảm bảo SIM đã được nhà mạng kích hoạt dịch vụ VoLTE (miễn phí):
     * **Viettel:** Soạn `HDCALL` gửi `191`
     * **VinaPhone / Wintel / iTel:** Soạn `WIFICALL` gửi `888`
     * **MobiFone / FPT:** Soạn `DK VOLTE` gửi `999`
3. **Máy tính:**
   * **KHÔNG CẦN CÀI ĐẶT PYTHON:** Tool đã tích hợp sẵn nhân **Python Portable (Embedded)** chính chủ bên trong thư mục `python/`. Bất kỳ máy tính Windows nào cũng nhấp đúp là chạy ngay.
   * Đã cài đặt **Qualcomm USB Diagnostics Driver** (để máy tính nhận diện cổng COM khi tool mở cổng Diag).

---

## 4. HƯỚNG DẪN THỰC HIỆN TỪNG BƯỚC

### Bước 1: Khởi động công cụ
* Cắm điện thoại vào máy tính (máy vẫn đang mở nguồn bình thường ở màn hình chính).
* Nhấp đúp chuột vào file **`run_tool.bat`**.
* Nếu trên màn hình điện thoại có hiện thông báo hỏi cấp quyền USB Debugging hoặc Magisk SuperUser, hãy bấm **Cho phép (Allow/Grant)**.

### Bước 2: Kiểm tra an toàn thiết bị (Tùy chọn nhưng nên làm)
* Trên menu chính, bấm phím **`1`** (Kiểm tra thiết bị & Tương thích phần cung).
* Tool sẽ kiểm tra xem máy có đúng là chip Snapdragon 652 không và báo xanh nếu an toàn.

### Bước 3: Tự động Fix VoLTE (1-Click)
* Trên menu chính, bấm phím **`3`** (TỰ ĐỘNG FIX VoLTE).
* Tiến trình sẽ tự động thực hiện 4 bước liên hoàn:
  1. **Tự động sao lưu EFS gốc** (`modemst1`, `modemst2`, `fsg`) vào thư mục `backups/` để đảm bảo an toàn tuyệt đối.
  2. **Kích hoạt cổng Qualcomm Diag** và kết nối tới cổng COM.
  3. **Nạp & xác thực 100% byte** toàn bộ 34 NV items VoLTE vào modem EFS.
  4. **Cấu hình APN IMS** và bật cờ `volte_vt_enabled = 1` trên hệ điều hành Android.
* Kết thúc tiến trình, chọn **`Y`** để khởi động lại điện thoại.

---

## 5. KIỂM TRA KẾT QUẢ SAU KHI KHỞI ĐỘNG LẠI
1. **Kiểm tra menu ẩn trên điện thoại:**
   * Mở trình gọi điện, bấm: `*#*#4636#*#*`
   * Chọn **Thông tin điện thoại (Phone Information)** ➔ Bấm dấu 3 chấm góc phải ➔ Chọn **Trạng thái dịch vụ IMS (IMS Service Status)**.
   * Sẽ thấy:
     * *Đăng ký IMS:* **Đã đăng ký (Registered)**
     * *Thoại qua LTE (VoLTE):* **Khả dụng (Available)**
2. **Gọi thử nghiệm:**
   * Gọi tới tổng đài **`198`** hoặc số di động bất kỳ.
   * Máy sẽ giữ nguyên biểu tượng **4G/LTE** trong suốt cuộc gọi, kết nối cuộc gọi siêu nhanh và âm thoại cực kỳ trong trẻo (chuẩn HD Voice AMR-WB).

---

## 6. KHÔI PHỤC (ROLLBACK) KHI CẦN THIẾT
Nếu vì bất kỳ lý do gì người dùng muốn đưa modem trở về trạng thái xuất xưởng:
* Mở tool, chọn phím **`4`** (Khôi phục EFS gốc từ bản sao lưu).
* Chọn bản sao lưu muốn phục hồi và gõ `YES`. Tool sẽ ghi trả lại nguyên trạng phân vùng ban đầu!
