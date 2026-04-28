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

---

## Section 4 — Personalization theo Profile (Issue 3)

### TC-21 🟢 — `tax_handler='self'` → tin nhắn có hướng dẫn hành động chi tiết

**Tiền điều kiện:** User có `tax_handler='self'`, có deadline urgent.

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn có section hướng dẫn từng bước cụ thể, ví dụ:
  > 💡 Cần có Thông báo thuế khoán từ Chi cục thuế
  > trước khi nộp. Chưa có? Nhắn 'thuế khoán' để tôi
  > hướng dẫn.
- Có CTA dạng "Nhắn '...' để được hướng dẫn"

---

### TC-22 🟢 — `tax_handler='accountant'` → "báo cho kế toán của bạn"

**Tiền điều kiện:** User công ty, có kế toán riêng.

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn có dòng:
  > 💡 Gửi sổ sách tháng này cho kế toán càng sớm càng tốt.
- Tone ngắn gọn hơn, không có hướng dẫn chi tiết từng bước
  (vì user đã có kế toán)

---

### TC-23 🟢 — `tax_handler='unknown'` → kèm link hỏi bot trợ giúp

**Tiền điều kiện:** User chọn "Chưa biết phải làm gì 😅".

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn kèm CTA động viên hỏi bot:
  > Chưa rõ phải làm gì? Nhắn 'tôi cần giúp' để mình
  > hướng dẫn từ đầu.
- Tone thân thiện, không gây áp lực

---

### TC-24 🟢 — Hộ KD + service → nhắc Thông báo thuế khoán

**Tiền điều kiện:** `business_type='household'`, `industry='service'`.

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn có dòng đặc thù cho hộ KD service:
  > 💡 Cần có Thông báo thuế khoán từ Chi cục thuế
  > trước khi nộp.

---

### TC-25 🟢 — Công ty (any industry) → nhắc sổ sách đầu vào/đầu ra

**Tiền điều kiện:** `business_type='company'`.

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn có dòng:
  > 💡 Kiểm tra sổ sách đầu vào / đầu ra trước khi
  > kê khai.

---

### TC-26 🟢 — Cá nhân (any industry) → nhắc lưu chứng từ chi phí

**Tiền điều kiện:** `business_type='individual'`.

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Tin nhắn có dòng:
  > 💡 Nhớ lưu chứng từ chi phí — cuối năm sẽ cần
  > để quyết toán.

---

### TC-27 🟢 — Format VND đúng cho 3 ngưỡng

**Mục đích:** Verify format `format_vnd` trong message_builder.

**Cách test:**
- User A có `revenue_snapshot.amount = 850_000` (< 1tr)
  → Trigger preview → tin nhắn hiện "**850,000 đồng**"
- User B có `revenue_snapshot.amount = 11_400_000`
  → Tin nhắn hiện "**11.4 triệu đồng**"
- User C có `revenue_snapshot.amount = 1_200_000_000`
  → Tin nhắn hiện "**1.2 tỷ đồng**"

**Kết quả mong đợi:** Định dạng đúng cả 3 ngưỡng,
KHÔNG hiển thị "11400000.0" hay "11,400,000".

---

## Section 5 — Anti-spam Rules (Issue 4)

### TC-28 🟢 — User vừa nhận tin <20h → skip lần gửi tiếp theo

**Tiền điều kiện:**
- User đã nhận daily reminder lúc 8:30 sáng nay
- `last_notified_at = today 08:30`

**Thao tác:** Trigger lại daily job ngay lập tức (cùng ngày,
hoặc giả lập 19h sau).

**Kết quả mong đợi:**
- Bot **KHÔNG gửi tin** lần 2
- Log scheduler: `skipped += 1`
- `notification_logs` không có row mới
- `last_notified_at` giữ nguyên

**Verify Acceptance Criteria Issue 4:**
> "Anti-spam: chạy daily_deadline_check 2 lần liên tiếp →
> lần 2 gửi 0 tin"

---

### TC-29 🟢 — `notification_enabled=FALSE` → KHÔNG gửi bất kỳ loại nào

**Tiền điều kiện:** User đã `PUT /notifications/settings`
với `notification_enabled=false`.

**Thao tác:** Trigger cả 3 jobs: daily, weekly, monthly.

**Kết quả mong đợi:**
- Cả 3 job đều **skip** user này
- User KHÔNG nhận bất kỳ tin nhắn tự động nào
- User vẫn có thể chủ động nhắn "lịch thuế" để xem
  (vì đó là user-initiated, không bị anti-spam chặn)

---

### TC-30 🟢 — User bật notification trở lại → nhận tin lần sau

**Tiền điều kiện:** Vừa hoàn thành TC-29.

**Thao tác:**
1. Nhắn `bật thông báo` (Node gateway gọi
   `PUT /notifications/settings` với
   `notification_enabled=true`)
2. Đợi đến daily job tiếp theo

**Kết quả mong đợi:**
- Bot xác nhận:
  > ✅ Đã bật lại thông báo. Bạn sẽ nhận lịch nhắc
  > lúc 8:30 mỗi sáng.
- Daily job kế tiếp gửi tin bình thường

---

### TC-31 🔴 — Gửi thất bại 3 lần → log error, KHÔNG retry vô hạn

**Tiền điều kiện:** User đã block bot trên Telegram
(API trả 403 "Forbidden: bot was blocked").

**Thao tác:** Trigger daily job.

**Kết quả mong đợi:**
- Scheduler retry lần 1 sau 5 phút → fail
- Retry lần 2 sau 5 phút → fail
- Lần 3 → log ERROR
- DB: `notification_logs` có row với `was_delivered=FALSE`
- Job vẫn tiếp tục xử lý các user khác (KHÔNG crash)
- Sau lần 3, scheduler **KHÔNG retry thêm** trong job này

---

## Section 6 — Weekly Summary (Issue 4)

### TC-32 🟢 — Thứ Hai 9:00 — active user nhận summary

**Tiền điều kiện:**
- Hôm nay là thứ Hai
- User đã onboarding xong
- `last_active_at` trong vòng 90 ngày qua

**Thao tác:** Đợi đến 9:00 thứ Hai (hoặc trigger thủ công
job `weekly_summary`).

**Kết quả mong đợi:**
- Bot gửi tin nhắn dạng:
  > 📊 Tuần này của [Tên]:
  > • Doanh thu ghi nhận: ...
  > • Thuế GTGT ước tính: ...
  > • Deadline còn lại trong tháng: ...
- Có ít nhất 1 "tip thuế tuần này" (xoay vòng theo chủ đề)
- Anti-spam vẫn được tôn trọng (nếu đã nhận tin <20h
  thì skip)

---

### TC-33 🟡 — Inactive user (>90 ngày) → KHÔNG nhận weekly summary

**Tiền điều kiện:** User có `last_active_at` cách đây 100 ngày.

**Thao tác:** Trigger weekly_summary job.

**Kết quả mong đợi:**
- Bot **KHÔNG gửi** weekly summary cho user này
- Log: `skipped += 1`

---

### TC-34 🟡 — Tuần không có deadline nào → chỉ tip thuế

**Tiền điều kiện:** User active, nhưng tháng này không có
deadline nào sắp đến.

**Thao tác:** Trigger weekly_summary thứ Hai.

**Kết quả mong đợi:**
- Tin nhắn vẫn được gửi
- Section "Deadline còn lại": "Không có deadline trong
  tuần này"
- Vẫn có "tip thuế tuần này" để giữ engagement
- Người dùng có lý do mở bot (Trụ cột Proactive Value)

---

## Section 7 — Monthly Calendar (Issue 4)

### TC-35 🟢 — Ngày 1 hàng tháng 8:00 — nhận lịch tháng

**Tiền điều kiện:** Hôm nay là ngày 1 của tháng.

**Thao tác:** Đợi 8:00 sáng (hoặc trigger
`monthly_calendar` job thủ công).

**Kết quả mong đợi:**
- Bot gửi tin nhắn:
  > 📋 Tháng này bạn có {N} nghĩa vụ thuế cần lưu ý...
- Liệt kê đầy đủ deadline trong tháng đó với ngày cụ thể
- Đúng theo profile user (hộ KD chỉ thấy thuế khoán,
  công ty thấy VAT+CIT, v.v.)

---

### TC-36 🟡 — Tháng 2 (28 ngày) — không crash khi tính deadline

**Tiền điều kiện:** Hôm nay 01/02 (năm không nhuận, tháng có 28 ngày).

**Thao tác:** Trigger `monthly_calendar` job.

**Kết quả mong đợi:**
- Job chạy thành công, KHÔNG ném exception
- Deadline 28/02 được tính đúng (không bị tràn sang tháng 3)
- Tin nhắn gửi đúng định dạng

**Verify Acceptance Criteria Issue 2:**
> "Xử lý được edge case tháng 2 (28/29 ngày)"

---

### TC-37 🟡 — Cuối tháng 12 — deadline phải sang năm sau

**Tiền điều kiện:** Hôm nay là 28/12/2026.

**Thao tác:** Gửi `lịch thuế` hoặc trigger preview.

**Kết quả mong đợi:**
- Deadline tiếp theo (ngày 30/01/2027 hoặc 20/01/2027)
  được tính sang **năm 2027**
- Label hiển thị đúng "Q1/2027" hoặc "tháng 12/2026" tùy loại
- KHÔNG có lỗi off-by-one năm

**Verify Acceptance Criteria Issue 2:**
> "Xử lý deadline năm sau khi reference_date là cuối tháng 12"

---

## Section 8 — Notification Settings (Issue 6 — PUT)

### TC-38 🟢 — User tắt notification

**Thao tác:**
1. Trong chat bot, nhắn `tắt thông báo`
   (hoặc qua nút settings inline keyboard)
2. Node gateway gọi `PUT /notifications/settings/{telegram_id}`
   với body `{"notification_enabled": false}`

**Kết quả mong đợi:**
- API trả `200` `{"updated": true}`
- DB: `notification_enabled=FALSE`
- Bot xác nhận:
  > 🔕 Đã tắt thông báo. Nhắn 'bật thông báo' khi
  > muốn bật lại.

---

### TC-39 🟢 — User đổi giờ nhắc thành 7:30 sáng

**Thao tác:**
1. Nhắn `đổi giờ nhắc 7:30`
2. Node gateway gọi `PUT /notifications/settings` với
   `{"preferred_notify_hour": 7, "preferred_notify_minute": 30}`

**Kết quả mong đợi:**
- DB: `preferred_notify_hour=7`, `preferred_notify_minute=30`
- Bot xác nhận:
  > ⏰ Đã đổi giờ nhắc thành 7:30 sáng (Asia/Ho_Chi_Minh).
- Daily job kế tiếp gửi đúng vào 7:30 thay vì 8:30 mặc định

---

### TC-40 🔴 — Input giờ không hợp lệ (25:00) → reject

**Thao tác:** Gửi request
`PUT /notifications/settings` với body
`{"preferred_notify_hour": 25}`.

**Kết quả mong đợi:**
- API trả `422 Unprocessable Entity` (Pydantic validation)
- DB KHÔNG bị thay đổi
- Bot phản hồi user:
  > ❌ Giờ không hợp lệ. Vui lòng nhập giờ từ 0–23.

---

## Section 9 — Edge Cases & Robustness

### TC-41 🟡 — User đổi `business_type` → deadline được recalc

**Tiền điều kiện:** User đang là `household`, sau đó đổi
sang `company` (qua nhắn "cập nhật hồ sơ" hoặc admin cập nhật DB).

**Thao tác:**
1. Đổi `business_type='company'`, `tax_period='monthly'`
2. Gửi `lịch thuế`

**Kết quả mong đợi:**
- Deadline list được tính lại theo profile mới
- Hiển thị VAT tháng + CIT tạm tính (thay vì thuế khoán)
- KHÔNG còn deadline "Thuế khoán" cũ
- DB không bị duplicate row

---

### TC-42 🔴 — User block bot trên Telegram → mark error, không crash job

**Tiền điều kiện:** User block bot, Telegram API trả về
`403 Forbidden: bot was blocked by the user`.

**Thao tác:** Trigger daily job có user này trong batch.

**Kết quả mong đợi:**
- Sau 3 lần retry fail → log ERROR
- DB: `notification_logs` có row với
  `was_delivered=FALSE`
- Job vẫn xử lý các user còn lại, **KHÔNG crash**
- Khuyến nghị: cân nhắc set `notification_enabled=FALSE`
  cho user này để không spam log nữa (improvement)

---

### TC-43 🟡 — User chưa có `revenue_snapshots` → `estimated_amount=None`

**Tiền điều kiện:** User mới, chưa nhập doanh thu lần nào.

**Thao tác:** Trigger daily job khi có deadline urgent.

**Kết quả mong đợi:**
- API `GET /notifications/upcoming` vẫn trả deadline,
  nhưng `estimated_amount: null`
- Tin nhắn KHÔNG hiển thị dòng "💰 Ước tính: ..."
- Thay vào đó có CTA:
  > 📝 Mình chưa biết doanh thu của bạn. Nhắn 'báo doanh thu'
  > để mình tính giúp số thuế ước tính.

**Verify Acceptance Criteria Issue 2:**
> "Return `None` nếu không đủ dữ liệu"

---

### TC-44 🟢 — User reply tin nhắn notification → log `user_replied=TRUE`

**Tiền điều kiện:** User vừa nhận daily reminder.

**Thao tác:** User reply tin nhắn đó (ví dụ nhắn
"đã nộp" hoặc "tính phạt giúp tôi") trong vòng 24 giờ.

**Kết quả mong đợi:**
- DB: `notification_logs.user_replied=TRUE`
- DB: `notification_logs.reply_within_hours` = số giờ
  từ `sent_at` đến lúc reply
- Đây là input cho metrics
  "Notification → Interaction rate > 25%"

---

### TC-45 🟡 — Tin nhắn dài → không vượt 4,096 ký tự

**Tiền điều kiện:** User có 8+ deadline trong 60 ngày,
profile dài (tên cửa hàng dài, tỉnh dài, v.v.).

**Thao tác:** Trigger `monthly_calendar` job.

**Kết quả mong đợi:**
- Tin nhắn gửi qua Telegram thành công (không bị
  Telegram reject vì quá độ dài)
- Nếu nội dung quá dài: truncate hoặc chia thành nhiều tin
- Vẫn giữ phần quan trọng nhất (deadline gần nhất)

**Verify Acceptance Criteria Issue 3:**
> "Output không vượt 4,096 ký tự trong mọi trường hợp"

---

### TC-46 🟢 — Restart Docker container → scheduler tự khởi động, không duplicate job

**Thao tác:**
```
docker compose restart tax-engine
# Đợi container up
curl http://localhost:8000/notifications/scheduler/status
```

**Kết quả mong đợi:**
- Endpoint trả `scheduler_running: true`
- Có đúng **3 jobs**: `daily_deadline_check`,
  `weekly_summary`, `monthly_calendar`
- KHÔNG có job duplicate (ví dụ 2 daily_deadline_check)
- `next_run` của mỗi job hiển thị đúng theo timezone
  `Asia/Ho_Chi_Minh`

**Verify Acceptance Criteria Issue 4:**
> "Restart Docker container → scheduler tự start,
> không duplicate jobs"

---

### TC-47 🟡 — Năm nhuận, ngày 29/02 — không crash

**Tiền điều kiện:** Hôm nay 29/02/2028 (năm nhuận).

**Thao tác:** Trigger tất cả 3 jobs.

**Kết quả mong đợi:**
- Tất cả jobs chạy thành công
- Deadline tính ra (ví dụ 30/03 cho thuế khoán Q1)
  đúng theo lịch
- Không có lỗi `ValueError: day is out of range for month`

---

### TC-48 🟢 — `has_employees=TRUE` → có nhắc PIT withholding cho công ty

**Tiền điều kiện:** Công ty `business_type='company'`,
`has_employees=TRUE`.

**Thao tác:** Trigger daily job hoặc gửi `lịch thuế`.

**Kết quả mong đợi:**
- Tin nhắn có deadline thêm: "PIT khấu trừ nhân viên"
- Có gợi ý:
  > 💡 Đừng quên kê khai PIT cho nhân viên trong tháng.
- Nếu `has_employees=FALSE`: KHÔNG hiện section này

---

### TC-49 🔴 — Nội dung có ký tự đặc biệt → Markdown Telegram không bị lỗi

**Tiền điều kiện:** Tên cửa hàng user chứa ký tự đặc biệt
như `*`, `_`, `[`, `]`, `(`, `)`, ví dụ "Quán *Hoa Mai*".

**Thao tác:** Trigger daily job — tin nhắn nhúng tên này
qua Markdown.

**Kết quả mong đợi:**
- Telegram render đúng — KHÔNG bị break formatting
  (escape `*` thành `\*`, v.v.)
- KHÔNG bị Telegram trả lỗi `400 Bad Request: can't parse
  entities`
- Tin nhắn vẫn được gửi thành công

**Verify CLAUDE.md:**
> "Sử dụng Markdown hợp lệ cho Telegram, không dùng HTML tags"

---

### TC-50 🟡 — Concurrent: scheduler chạy chồng (overlapping) → không gửi duplicate

**Tiền điều kiện:** Daily job cũ chưa kết thúc (đang xử lý
1000 user) thì đến giờ trigger lần kế tiếp (rất hiếm,
nhưng có thể nếu 1 job chạy quá 24h vì lỗi).

**Thao tác:** Giả lập bằng cách trigger thủ công 2 lần
liên tiếp `POST /notifications/test/{telegram_id}`
(nhưng test endpoint này KHÔNG check anti-spam, nên cần
test với daily job thật).

**Kết quả mong đợi:**
- Anti-spam check (`last_notified_at < NOW() - 20h`)
  ngăn việc gửi tin trùng
- User chỉ nhận **1 tin** dù job chạy 2 lần
- APScheduler config `max_instances=1` cho mỗi job
  (best practice — verify khi review code)

---

### TC-51 🟢 — Endpoint `GET /notifications/scheduler/status` ngay khi vừa start

**Tiền điều kiện:** Tax-engine vừa start, chưa có job
nào chạy lần nào.

**Thao tác:** `curl http://localhost:8000/notifications/scheduler/status`

**Kết quả mong đợi:**
- Trả `200` với:
  ```json
  {
    "scheduler_running": true,
    "jobs": [
      {
        "id": "daily_deadline_check",
        "next_run": "<future ISO timestamp>",
        "last_run": null,
        "last_run_sent": null,
        "last_run_skipped": null,
        "last_run_failed": null
      },
      ...
    ]
  }
  ```
- KHÔNG crash khi `last_run` là `null`

**Verify Acceptance Criteria Issue 6:**
> "Endpoint scheduler/status hoạt động kể cả khi
> scheduler chưa chạy job nào"

---

### TC-52 🔴 — `POST /notifications/test/{telegram_id}` bị block khi `ENV=production`

**Tiền điều kiện:** Tax-engine chạy với env `ENV=production`.

**Thao tác:** `curl -X POST http://prod/notifications/test/123456`

**Kết quả mong đợi:**
- Trả `403 Forbidden`
  `{"detail": "Not available in production"}`
- KHÔNG có tin nhắn nào được gửi
- Log warning để admin biết có người thử endpoint này

**Verify Acceptance Criteria Issue 6:**
> "Test endpoint bị block hoàn toàn khi ENV=production"

---

### TC-53 🟢 — Aha Moment Ngày 1: Sau onboarding, nhận lịch thuế ngay

**Tham chiếu:** Phần 7 retention-strategy.md — Aha Moment Ngày 1.

**Thao tác:** User mới đăng ký, hoàn thành cả step 1 + 2.

**Kết quả mong đợi:**
- **Trong vòng 30 giây** sau onboarding hoàn thành,
  user nhận tin nhắn lịch thuế cá nhân hóa
  (qua `POST /notifications/preview/{telegram_id}`)
- Tin nhắn có ít nhất 1 deadline cụ thể với ngày
- Đây là **aha moment đầu tiên** — nếu thiếu sẽ ảnh hưởng
  D1 retention

---

### TC-54 🟢 — Aha Moment Ngày 7: Nhận daily reminder đầu tiên

**Tiền điều kiện:** User đăng ký ngày 1, đến ngày 7.

**Thao tác:** Đợi đến 8:30 sáng ngày 7 (hoặc đổi
`preferred_notify_hour`).

**Kết quả mong đợi:**
- User nhận daily reminder đầu tiên không phải do họ
  yêu cầu (proactive)
- Đây là khoảnh khắc xác nhận giá trị "không quên deadline"
- Verify metric: `notification_open_rate > 60%`

---

### TC-55 🟡 — `last_notified_at` được update chính xác sau gửi

**Thao tác:**
1. Trước job: `SELECT last_notified_at FROM user_profiles
   WHERE telegram_id={X};` → giả sử là `2026-04-27 08:30`
2. Trigger daily job lúc 2026-04-28 08:30
3. Kiểm tra lại `last_notified_at`

**Kết quả mong đợi:**
- Giá trị mới = thời điểm gửi thành công
  (`2026-04-28 08:30:xx`)
- Múi giờ: `Asia/Ho_Chi_Minh` (KHÔNG phải UTC)
- Nếu gửi fail (TC-31): `last_notified_at` KHÔNG update

---

## Phụ lục — Mapping Test Case ↔ Issue

| Issue | Test Cases liên quan |
|---|---|
| Issue 1 — DB Schema | TC-01, TC-02, TC-44 (qua DB verification) |
| Issue 2 — Deadline Calculator | TC-09 → TC-14, TC-36, TC-37, TC-43, TC-47 |
| Issue 3 — Message Builder | TC-15 → TC-19, TC-21 → TC-27, TC-45, TC-49 |
| Issue 4 — Scheduler | TC-15 → TC-20, TC-28 → TC-37, TC-46, TC-50, TC-55 |
| Issue 5 — Onboarding | TC-01 → TC-08 |
| Issue 6 — REST API | TC-09 → TC-14, TC-38 → TC-40, TC-51, TC-52 |

## Phụ lục — Mapping Test Case ↔ Trụ cột Retention

| Trụ cột | Test Cases liên quan |
|---|---|
| Trụ cột 1 — Proactive Value | TC-15 → TC-20, TC-32 → TC-37, TC-53, TC-54 |
| Trụ cột 2 — Daily Value | TC-32 → TC-34 (weekly summary) |
| Trụ cột 3 — Personalization & Switching Cost | TC-21 → TC-27, TC-41, TC-43, TC-44, TC-48 |

---

*File này là living document — cập nhật khi có feature mới
hoặc bug pattern phát hiện trong production.*
*Version 1.0 — 2026-04*
