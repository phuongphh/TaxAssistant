# Issue #56

[Backend] Notification Scheduler Service

## Context

Background service dùng APScheduler để chạy các notification jobs định kỳ. Tích hợp vào `python-engine` hiện tại — **không tạo service mới**.

**Depends on:** #52 (Deadline Calculator Engine), #54 (Message Builder)

---

## Requirements

### 1. Scheduler khởi động cùng FastAPI app

```python
# Trong main.py hiện tại, thêm vào startup event:
@app.on_event("startup")
async def startup():
    # ... existing startup code ...
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
```

---

### 2. Ba jobs bắt buộc

| Job ID | Schedule | Logic |
|--------|----------|-------|
| `daily_deadline_check` | Mỗi ngày 8:30 sáng | Gửi nhắc nếu có deadline ≤ 14 ngày |
| `weekly_summary` | Thứ Hai 9:00 sáng | Gửi tóm tắt tuần cho all active users |
| `monthly_calendar` | Ngày 1 mỗi tháng 8:00 sáng | Gửi lịch tháng mới |

---

### 3. Anti-spam logic — bắt buộc

- Không gửi quá **1 tin/ngày** cho cùng 1 user
- Kiểm tra `notification_logs` trước khi gửi
- Nếu user đã nhận tin trong **20 giờ qua** → skip
- Respect `notification_enabled = FALSE`

---

### 4. Retry logic

- Nếu gửi Telegram thất bại → retry sau **5 phút**, tối đa **3 lần**
- Sau 3 lần thất bại → log error, đánh dấu `was_delivered = FALSE`, tiếp tục user tiếp theo (**không crash toàn bộ job**)

---

### 5. Observability

- Log rõ ràng mỗi job: bao nhiêu user được check, bao nhiêu tin được gửi, bao nhiêu skip, bao nhiêu lỗi
- Expose endpoint:
  ```
  GET /notifications/scheduler/status
  ```
  Trả về trạng thái các jobs (next run time, last run time, status)

---

### 6. Dependencies cần thêm vào `requirements.txt`

```
apscheduler==3.10.4
```

---

## Acceptance Criteria

- [ ] Scheduler không block FastAPI event loop (phải dùng `AsyncIOScheduler`)
- [ ] Tắt/bật lại Docker container → scheduler tự restart, không duplicate jobs
- [ ] Anti-spam hoạt động: chạy job 2 lần liên tiếp → lần 2 không gửi gì
- [ ] Retry logic hoạt động đúng: tối đa 3 lần, sau đó `was_delivered = FALSE`
- [ ] `GET /notifications/scheduler/status` trả về đúng trạng thái các jobs
- [ ] Log đầy đủ: user checked / sent / skipped / error cho mỗi job run
- [ ] `notification_enabled = FALSE` được respect — không gửi tin cho user đã tắt thông báo
