# Issue #58

[Bot] Onboarding Flow Enhancement — Thu thập Tax Period

## Context

Onboarding hiện tại đã thu thập `business_type`, `revenue_range`, `industry`, `tax_handler`. Issue này thêm **step 2** vào onboarding để thu thập `tax_period` và `has_employees` — hai trường cần thiết cho deadline calculator.

**Depends on:** #52

> ⚠️ **Quan trọng:** Không phá vỡ flow onboarding hiện tại. User đã hoàn thành onboarding cũ → trigger step 2 lần sau họ tương tác.

---

## Requirements

### 1. Step 2 — Thu thập Tax Period

Sau khi user hoàn thành onboarding step 1 hiện tại, bot hỏi thêm:

```
Câu hỏi bổ sung để nhắc thuế chính xác hơn:

Bạn đang kê khai thuế theo kỳ nào?

[1] Hàng tháng (doanh thu > 50 triệu/tháng)
[2] Hàng quý (doanh thu < 50 triệu/tháng)
[3] Thuế khoán cố định (hộ kinh doanh nhỏ)
[4] Chưa biết / Để hỏi sau
```

---

### 2. Thu thập has_employees (có điều kiện)

Nếu `business_type` là `company` hoặc `household` có nhân viên:

```
Bạn có thuê nhân viên chính thức không?
(Ảnh hưởng đến nghĩa vụ thuế TNCN)

[1] Có, có nhân viên
[2] Không, chỉ có mình tôi / cộng tác viên
```

---

### 3. Xử lý user đã onboard trước đây (`onboarding_step = 1`)

- Lần tương tác tiếp theo sau khi deploy → hiển thị câu hỏi bổ sung
- Có thể **skip** bằng cách nhắn `"bỏ qua"` → set `onboarding_step = 3`, `tax_period = NULL`
- Nếu skip → notification vẫn hoạt động nhưng deadline tính theo **conservative default (quarterly)**

---

### 4. Confirmation message sau khi hoàn thành step 2

```
✅ Đã cập nhật hồ sơ thuế của bạn!

Tôi sẽ nhắc bạn trước mỗi deadline thuế.
Nhắc nhở đầu tiên sẽ vào sáng mai lúc 8:30.

Nhắn 'lịch thuế' để xem ngay các deadline
sắp tới của bạn.
```

---

### 5. API call từ Node sang Python engine

Sau khi lưu vào DB, gọi:
```
POST /notifications/preview/{user_id}
```
Để trigger gửi lịch thuế preview ngay lập tức cho user.

---

## onboarding_step Logic

| Giá trị | Ý nghĩa |
|---------|---------|
| `1` | Step 1 hoàn thành (basic info collected) |
| `2` | Đang ở step 2 (tax_period chưa thu thập) |
| `3` | Hoàn thành toàn bộ (hoặc đã skip) |

---

## Acceptance Criteria

- [ ] User cũ (`onboarding_step = 1`) không bị hỏi lại step 1
- [ ] User mới đi qua cả 2 steps liên tục
- [ ] Skip flow không crash, default về `quarterly`
- [ ] `onboarding_step` được update đúng trong DB
- [ ] `tax_period` và `has_employees` được lưu đúng sau step 2
- [ ] API `POST /notifications/preview/{user_id}` được gọi sau khi hoàn thành step 2
- [ ] Confirmation message hiển thị đúng sau khi hoàn thành
