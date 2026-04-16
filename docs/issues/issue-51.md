# Issue #51

[DB] Enhance user_profiles schema for notification personalization

## Context

Hệ thống hiện tại đã có bảng `user_profiles` và onboarding flow thu thập thông tin cơ bản. Issue này **extend schema hiện tại — không tạo mới** — để hỗ trợ các trường cần thiết cho notification engine.

### Current State
`user_profiles` hiện tại có: `telegram_id`, `business_type`, `revenue_range`, `industry`, `tax_handler` (hoặc tương đương)

---

## Requirements

### 1. Thêm các cột vào bảng `user_profiles` hiện tại

> ⚠️ DÙNG `ALTER TABLE`, KHÔNG `DROP TABLE`

```sql
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS tax_period            VARCHAR(20)  DEFAULT NULL,
  -- 'monthly' | 'quarterly' | 'flat_rate'
  -- NULL = chưa xác định

  ADD COLUMN IF NOT EXISTS vat_method            VARCHAR(20)  DEFAULT NULL,
  -- 'deduction' | 'direct' | 'exempt'

  ADD COLUMN IF NOT EXISTS has_employees         BOOLEAN      DEFAULT FALSE,
  -- Ảnh hưởng đến PIT withholding

  ADD COLUMN IF NOT EXISTS province_code         VARCHAR(10)  DEFAULT NULL,
  -- Ảnh hưởng đến Chi cục thuế địa phương

  ADD COLUMN IF NOT EXISTS notification_enabled  BOOLEAN      DEFAULT TRUE,

  ADD COLUMN IF NOT EXISTS preferred_notify_hour   SMALLINT   DEFAULT 8,
  -- 0-23, mặc định 8 giờ sáng

  ADD COLUMN IF NOT EXISTS preferred_notify_minute SMALLINT   DEFAULT 30,
  -- 0-59, mặc định 30 phút

  ADD COLUMN IF NOT EXISTS last_notified_at      TIMESTAMP    DEFAULT NULL,

  ADD COLUMN IF NOT EXISTS onboarding_step       SMALLINT     DEFAULT 1;
  -- 1=basic done, 2=tax_period collected, 3=complete
```

---

### 2. Tạo bảng mới `notification_logs`

```sql
CREATE TABLE IF NOT EXISTS notification_logs (
  id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID          NOT NULL REFERENCES user_profiles(id),
  notification_type   VARCHAR(50)   NOT NULL,
  -- 'deadline_reminder' | 'weekly_summary' | 'monthly_calendar'
  deadline_types      TEXT[],
  -- Mảng các loại deadline được nhắc, vd: ['vat', 'cit']
  sent_at             TIMESTAMP     DEFAULT NOW(),
  was_delivered       BOOLEAN       DEFAULT TRUE,
  user_replied        BOOLEAN       DEFAULT FALSE,
  reply_within_hours  SMALLINT      DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_notification_logs_user_id ON notification_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_sent_at ON notification_logs(sent_at);
```

---

### 3. Tạo bảng `revenue_snapshots`

```sql
CREATE TABLE IF NOT EXISTS revenue_snapshots (
  id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID           NOT NULL REFERENCES user_profiles(id),
  period      DATE           NOT NULL,
  -- Ngày đầu tháng, vd: 2025-10-01
  amount      DECIMAL(15,0)  NOT NULL,
  -- Số tiền VND, không có số lẻ
  source      VARCHAR(20)    DEFAULT 'user_reported',
  -- 'user_reported' | 'inferred'
  created_at  TIMESTAMP      DEFAULT NOW(),
  UNIQUE(user_id, period)
);
```

---

## Migration Strategy

- Viết **Alembic migration script** (không dùng raw SQL trực tiếp)
- Migration phải **idempotent** — chạy lại nhiều lần không lỗi (`IF NOT EXISTS`, `IF EXISTS`)
- Không xóa hoặc rename cột hiện tại
- **Rollback script** phải được viết kèm

---

## Acceptance Criteria

- [ ] Migration chạy thành công trên DB hiện tại không mất data
- [ ] Rollback migration hoạt động
- [ ] Các cột cũ không bị ảnh hưởng
- [ ] Indexes được tạo cho các cột query thường xuyên
