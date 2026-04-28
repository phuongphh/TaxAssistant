# Phase 1 — Test Cases: Hệ thống Nhắc nhở Thông minh

> **Mục tiêu:** Tài liệu này liệt kê các test case manual để kiểm thử
> Phase 1 — Hệ thống nhắc nhở thông minh trên Telegram bot.
> Tất cả thao tác đều thực hiện qua Telegram (chat với bot TaxAssistant).
>
> **Phạm vi:** Cover toàn bộ 6 issues của Phase 1
> (DB Schema, Deadline Calculator, Message Builder, Scheduler,
> Onboarding Enhancement, REST API Endpoints).
>
> **Tham chiếu:** `docs/strategy/retention-strategy.md` — Phần 3 và Phần 10.
>
> **Quy ước:**
> - 🟢 = Happy case (luồng chuẩn)
> - 🟡 = Corner case (rìa, edge case)
> - 🔴 = Negative case (input sai, lỗi mong đợi)
>
> **Ghi chú:** Đối với các test case liên quan đến scheduler (daily/weekly/monthly job),
> trong môi trường dev có thể trigger thủ công qua endpoint
> `POST /notifications/test/{telegram_id}` thay vì chờ đến đúng giờ.

---

## Section 1 — Onboarding Flow Enhancement (Issue 5)

### TC-01 🟢 — User mới hoàn thành onboarding step 1 (4 câu cơ bản)

**Tiền điều kiện:** Telegram_id chưa tồn tại trong DB.

**Thao tác:**
1. Mở chat với bot, gửi `/start`
2. Bot hỏi "Hình thức kinh doanh" → chọn `[1] Hộ kinh doanh cá thể`
3. Bot hỏi "Doanh thu năm ngoái" → chọn `[2] 100 – 300 triệu/năm`
4. Bot hỏi "Ngành nghề chính" → chọn `[2] Dịch vụ`
5. Bot hỏi "Ai đang lo phần thuế" → chọn `[1] Tự làm`

**Kết quả mong đợi:**
- Bot tiếp tục chuyển sang step 2 (hỏi `tax_period`)
- DB: `user_profiles` có row mới với `business_type='household'`,
  `industry='service'`, `tax_handler='self'`, `onboarding_step=1`

---

### TC-02 🟢 — User mới hoàn thành onboarding step 2 (tax_period + has_employees)

**Tiền điều kiện:** Vừa hoàn thành TC-01.

**Thao tác:**
1. Bot hỏi "Bạn đang kê khai thuế theo kỳ nào?"
   → bấm nút `[🏪 Thuế khoán]`
2. Bot hỏi "Bạn có thuê nhân viên chính thức không?"
   → bấm nút `[🙋 Chỉ mình tôi]`

**Kết quả mong đợi:**
- Bot gửi tin nhắn xác nhận:
  > ✅ Đã cập nhật hồ sơ thuế của bạn!
  > Tôi sẽ nhắc bạn trước mỗi deadline thuế.
  > Nhắc nhở đầu tiên sẽ vào sáng mai lúc 8:30.
- Bot gửi luôn tin nhắn lịch thuế preview (gọi
  `POST /notifications/preview/{telegram_id}`)
- DB: `tax_period='flat_rate'`, `has_employees=FALSE`,
  `onboarding_step=3`

---

### TC-03 🟢 — Chọn "Hàng tháng" → tax_period = monthly

**Tiền điều kiện:** Đang ở step 2.

**Thao tác:** Bấm nút `[📅 Hàng tháng]`.

**Kết quả mong đợi:**
- DB: `tax_period='monthly'`
- Nếu là `business_type='company'`: deadline preview phải có
  cả VAT (ngày 20) và CIT tạm tính (ngày 30 đầu quý sau)

---

### TC-04 🟢 — Chọn "Hàng quý" → tax_period = quarterly

**Thao tác:** Bấm nút `[📆 Hàng quý]`.

**Kết quả mong đợi:**
- DB: `tax_period='quarterly'`
- Hộ KD: chỉ thấy "Thuế khoán" deadline ngày 30 đầu quý sau
- Công ty: thấy VAT quý + CIT tạm tính

---

### TC-05 🟢 — Chọn "Thuế khoán" → tax_period = flat_rate

**Thao tác:** Bấm nút `[🏪 Thuế khoán]`.

**Kết quả mong đợi:**
- DB: `tax_period='flat_rate'`
- Deadline preview hiển thị "Thuế khoán Q{n}/{year}"

---

### TC-06 🟡 — Chọn "Chưa biết" → skip nhưng vẫn hoàn tất onboarding

**Thao tác:** Ở step 2, bấm nút `[❓ Chưa biết]`.

**Kết quả mong đợi:**
- DB: `tax_period=NULL`, `onboarding_step=3` (skip thẳng,
  KHÔNG hiện step 2b nhân viên)
- Bot vẫn gửi xác nhận hoàn thành onboarding
- Bot gợi ý: "Bạn có thể cập nhật sau bằng cách nhắn
  'cập nhật hồ sơ'"
- KHÔNG có deadline nào được hiển thị (vì thiếu tax_period)

---

### TC-07 🟡 — User cũ có `onboarding_step=1` gửi tin nhắn bất kỳ

**Tiền điều kiện:** User đã onboarding từ trước khi feature mới deploy
(`onboarding_step=1`, chưa có `tax_period`).

**Thao tác:** Gửi tin nhắn bất kỳ, ví dụ "Hỏi cách tính thuế GTGT".

**Kết quả mong đợi:**
- Bot **intercept** tin nhắn — không trả lời câu hỏi gốc ngay
- Bot hiển thị step 2 (hỏi `tax_period`):
  > Để nhắc thuế chính xác hơn, mình cần biết thêm một chút nhé!
- Sau khi user trả lời step 2 xong, bot mới quay lại
  trả lời câu hỏi gốc về thuế GTGT

---

### TC-08 🟡 — `business_type='individual'` không hỏi câu has_employees

**Tiền điều kiện:** User chọn `[2] Cá nhân (freelancer, KOL, CTV...)`.

**Thao tác:** Hoàn thành step 1, đến step 2 chọn tax_period.

**Kết quả mong đợi:**
- Bot **bỏ qua** câu hỏi nhân viên (vì cá nhân không có nhân viên)
- Đi thẳng đến tin nhắn xác nhận hoàn thành
- DB: `has_employees=FALSE` (mặc định)

---

## Section 2 — Lệnh "lịch thuế" / Upcoming Deadlines (Issue 6)

### TC-09 🟢 — Hộ KD quarterly nhắn "lịch thuế"

**Tiền điều kiện:** User có `business_type='household'`,
`tax_period='quarterly'`, đã hoàn thành onboarding.

**Thao tác:** Gửi tin nhắn `lịch thuế`.

**Kết quả mong đợi:**
- Node gateway gọi `GET /notifications/upcoming/{telegram_id}`
- Bot trả về danh sách deadline trong 60 ngày tới
- Có ít nhất 1 deadline "Thuế khoán Q{n}/{year}" với ngày 30
  của tháng đầu quý kế tiếp
- Mỗi deadline hiển thị: `due_date`, `label`, `days_remaining`,
  `urgency` (emoji 🔴/🟠/🟡/🔵)

---

### TC-10 🟢 — Công ty monthly nhắn "lịch thuế" → VAT + CIT

**Tiền điều kiện:** `business_type='company'`, `tax_period='monthly'`.

**Thao tác:** Gửi `lịch thuế`.

**Kết quả mong đợi:**
- Có ít nhất 2 loại deadline:
  - "Kê khai VAT tháng {n}" (ngày 20 tháng sau)
  - "CIT tạm tính Q{n}" (ngày 30 tháng đầu quý sau)
- Sort theo `due_date` tăng dần

---

### TC-11 🟢 — Cá nhân (`individual`) → thấy PIT quý

**Tiền điều kiện:** `business_type='individual'`.

**Thao tác:** Gửi `lịch thuế`.

**Kết quả mong đợi:**
- Có ít nhất "PIT quý {n}/{year}" — ngày 30 tháng đầu quý sau
- Nếu hôm nay gần 31/3: có thêm "PIT quyết toán năm"

---

### TC-12 🔴 — User chưa onboarding nhắn "lịch thuế"

**Tiền điều kiện:** Telegram_id chưa có row trong `user_profiles`.

**Thao tác:** Gửi `lịch thuế`.

**Kết quả mong đợi:**
- API `GET /notifications/upcoming/{telegram_id}` trả về `404`
- Bot **không crash**, gửi tin nhắn:
  > Bạn chưa hoàn thành thiết lập hồ sơ. Nhắn /start để bắt đầu.

---

### TC-13 🟡 — User có `tax_period=NULL` (skip "Chưa biết")

**Tiền điều kiện:** User đã onboarding nhưng chọn "Chưa biết".

**Thao tác:** Gửi `lịch thuế`.

**Kết quả mong đợi:**
- API trả về `200` với `deadlines: []`
- Bot hiển thị:
  > Mình chưa biết kỳ kê khai của bạn nên chưa thể tính
  > deadline. Nhắn 'cập nhật hồ sơ' để bổ sung nhé.
- KHÔNG crash, KHÔNG gửi list trống không kèm hướng dẫn

---

### TC-14 🟡 — Không có deadline nào trong 60 ngày tới

**Tiền điều kiện:** Hôm nay là 02/01, user là cá nhân
(deadline gần nhất là PIT quyết toán 31/3 — hơn 60 ngày).

**Thao tác:** Gửi `lịch thuế`.

**Kết quả mong đợi:**
- Bot hiển thị:
  > 🎉 Bạn không có deadline thuế nào trong 60 ngày tới.
  > Mình sẽ nhắc khi có deadline mới gần đến.
- KHÔNG hiển thị list rỗng

---

## Section 3 — Daily Deadline Notification — Urgency (Issue 4 + 3)

### TC-15 🟢 — Urgency `critical` (≤ 3 ngày) → 🔴 tone khẩn cấp

**Tiền điều kiện:**
- User: hộ KD service, tax_period=flat_rate, tax_handler=self
- Hôm nay: 27/10, deadline thuế khoán: 30/10 (còn 3 ngày)

**Thao tác:** Trigger daily job lúc 8:30 sáng (hoặc gọi
`POST /notifications/test/{telegram_id}`).

**Kết quả mong đợi:**
- Tin nhắn có:
  - Emoji 🔴 ở dòng tiêu đề
  - Tone "khẩn cấp, hành động ngay"
  - Có dòng "⚠️ Phạt chậm: ~{X}đ/ngày..."
  - Có CTA: "Nhắn 'hỗ trợ nộp thuế' nếu cần hướng dẫn khẩn"
- DB: `notification_logs` có row mới với
  `notification_type='deadline_reminder'`
- DB: `user_profiles.last_notified_at = NOW()`

---

### TC-16 🟢 — Urgency `urgent` (4-7 ngày) → 🟠

**Tiền điều kiện:** Hôm nay 25/10, deadline 30/10 (còn 5 ngày).

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Emoji 🟠
- Tone "Cần chuẩn bị ngay tuần này"
- Tin nhắn ngắn hơn `critical`, vẫn có ước tính tiền

---

### TC-17 🟢 — Urgency `warning` (8-14 ngày) → 🟡

**Tiền điều kiện:** Hôm nay 18/10, deadline 30/10 (còn 12 ngày).

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Emoji 🟡
- Tone "Lên kế hoạch trong 2 tuần"
- Có gợi ý chuẩn bị (ví dụ với công ty: "Gửi sổ sách
  tháng này cho kế toán càng sớm càng tốt")

---

### TC-18 🟢 — Urgency `info` (15-60 ngày) → 🔵

**Tiền điều kiện:** Hôm nay 01/10, deadline 30/10 (còn 29 ngày).

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Emoji 🔵
- Tone nhẹ "Thông tin để biết trước"
- KHÔNG có ngôn ngữ khẩn cấp

---

### TC-19 🟡 — Có nhiều hơn 3 deadline → hiển thị tối đa 3

**Tiền điều kiện:** User có 5 deadline trong 60 ngày tới
(ví dụ: VAT tháng, CIT tạm tính, PIT quý, VAT tháng kế,
CIT tạm tính quý kế).

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn hiển thị **đúng 3 deadline đầu tiên** (gần nhất)
- Có ghi chú: "...và {N} deadline khác. Nhắn 'lịch thuế'
  để xem đầy đủ."
- Không vượt quá 4,096 ký tự

---

### TC-20 🟡 — User không có deadline nào trong 14 ngày tới → KHÔNG gửi

**Tiền điều kiện:** Deadline gần nhất còn > 14 ngày.

**Thao tác:** Trigger daily job (job chỉ check deadline ≤ 14 ngày).

**Kết quả mong đợi:**
- Bot **không gửi tin nhắn nào**
- DB: `notification_logs` KHÔNG có row mới
- Log scheduler: `skipped += 1` cho user này
- `last_notified_at` không bị update
