# Issue #60

[API] Notification REST Endpoints

## Context

Expose các endpoint để Node gateway và admin có thể tương tác với notification system. Cũng dùng cho testing và monitoring.

**Depends on:** #56

---

## Endpoints Cần Tạo

### 1. `GET /notifications/upcoming/{telegram_id}`
- Trả về danh sách deadline sắp tới cho user
- Node gateway gọi khi user nhắn `"lịch thuế"`

**Response:**
```json
{
  "user_id": "uuid",
  "deadlines": [
    {
      "due_date": "2025-10-30",
      "label": "Thuế khoán Q3/2025",
      "type": "flat_tax",
      "urgency": "urgent",
      "days_remaining": 5,
      "estimated_amount": 11400000
    }
  ],
  "generated_at": "2025-10-25T08:30:00"
}
```

---

### 2. `POST /notifications/preview/{telegram_id}`
- Tính toán và gửi ngay tin nhắn preview lịch thuế
- Dùng sau khi user hoàn thành onboarding step 2
- **Không tính vào anti-spam counter** (vì user chủ động trigger)

---

### 3. `PUT /notifications/settings/{telegram_id}`
- Cập nhật notification preferences

**Request body:**
```json
{
  "notification_enabled": true,
  "preferred_notify_hour": 8,
  "preferred_notify_minute": 30
}
```

---

### 4. `GET /notifications/scheduler/status`
- Trả về trạng thái các scheduled jobs
- Dùng cho monitoring/debugging

**Response:**
```json
{
  "jobs": [
    {
      "id": "daily_deadline_check",
      "next_run": "2025-10-26T08:30:00",
      "last_run": "2025-10-25T08:30:00",
      "last_run_sent": 47,
      "last_run_skipped": 12
    }
  ]
}
```

---

### 5. `POST /notifications/test/{telegram_id}` _(dev/staging only)_
- Trigger gửi tin nhắn test ngay lập tức
- Không check anti-spam
- **Chỉ active khi `ENV != production`**

---

## Acceptance Criteria

- [ ] Tất cả endpoints có Pydantic response schema
- [ ] `telegram_id` không tìm thấy → trả về `404`, không crash
- [ ] Endpoint `/test` bị disable hoàn toàn khi `ENV=production`
- [ ] `GET /notifications/upcoming` trả về đúng danh sách deadline theo profile user
- [ ] `POST /notifications/preview` gửi tin nhắn thành công và không tính anti-spam
- [ ] `PUT /notifications/settings` cập nhật đúng DB
- [ ] `GET /notifications/scheduler/status` trả về đúng trạng thái các jobs
