# Issue #54

[Backend] Message Builder — Personalized Notification Content

## Context

Module tạo nội dung tin nhắn Telegram từ kết quả của `DeadlineCalculator`. Nội dung phải cá nhân hóa theo profile và thay đổi tone theo urgency.

**Depends on:** #52

---

## File Location

```
python-engine/
  app/
    services/
      message_builder.py   ← file mới
```

---

## Requirements

### Class `NotificationMessageBuilder`

---

### Method: `build_deadline_reminder(user, deadlines, today)`

- Trả về `string` đã format Markdown cho Telegram
- Tone thay đổi theo urgency của deadline gần nhất
- Nếu nhiều deadline: hiển thị tối đa 3, ghi chú số còn lại

#### Cá nhân hóa theo `tax_handler`:
| tax_handler  | Behavior |
|--------------|----------|
| `self`       | Thêm hướng dẫn hành động cụ thể |
| `accountant` | Nhắc "báo cho kế toán của bạn" |
| `unknown`    | Thêm link hỏi bot trợ giúp |

#### Cá nhân hóa theo `business_type` + `industry`:
- Tip cuối mỗi tin nhắn phải liên quan đến tình huống thực tế của user
- Ví dụ: hộ KD dịch vụ → nhắc *Thông báo thuế khoán từ Chi cục thuế*

---

### Method: `build_weekly_summary(user, deadlines_this_month)`

- Gửi mỗi **thứ Hai**
- Tóm tắt deadline còn lại trong tháng
- Kèm 1 **"tip thuế tuần này"** — rotate theo chủ đề

---

### Method: `build_monthly_calendar(user, deadlines)`

- Gửi **ngày 1 mỗi tháng**
- Danh sách đầy đủ deadline tháng đó với ngày cụ thể

---

### Format số tiền VND:

| Giá trị | Format hiển thị |
|---------|-----------------|
| < 1,000,000 | "850,000 đồng" |
| ≥ 1,000,000 | "8.5 triệu đồng" |
| ≥ 1,000,000,000 | "1.2 tỷ đồng" |

---

## Acceptance Criteria

- [ ] Không có hardcoded string nào trong logic — tất cả template tách riêng
- [ ] Output không vượt quá 4096 ký tự (giới hạn Telegram)
- [ ] Test với user có 0 deadline → trả về `None` (không gửi gì)
- [ ] Tone thay đổi đúng theo urgency (critical/urgent/warning/info)
- [ ] Cá nhân hóa đúng theo `tax_handler` (self/accountant/unknown)
- [ ] Format số tiền VND đúng theo quy tắc
- [ ] Tất cả 3 methods hoạt động đúng và có unit tests
