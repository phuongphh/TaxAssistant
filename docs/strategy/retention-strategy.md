# TaxAssistant Vietnam — Chiến lược Retention & Engagement

> **Mục tiêu tài liệu:** Định nghĩa toàn bộ chiến lược giữ chân và tăng tương tác người dùng cho sản phẩm TaxAssistant, tập trung vào thị trường SME Việt Nam. Tài liệu này bao gồm chiến lược tổng thể, thiết kế chi tiết hệ thống nhắc nhở thông minh, và các GitHub Issues sẵn sàng để implement.

---

## Mục lục

1. [Hiểu tâm lý SME Việt Nam](#1-hiểu-tâm-lý-sme-việt-nam)
2. [3 Trụ cột Retention](#2-3-trụ-cột-retention)
3. [Trụ cột 1 — Hệ thống nhắc nhở thông minh](#3-trụ-cột-1--hệ-thống-nhắc-nhở-thông-minh-theo-lịch-thuế)
4. [Trụ cột 2 — Giá trị hàng ngày](#4-trụ-cột-2--tạo-giá-trị-hàng-ngày-không-chỉ-mùa-thuế)
5. [Trụ cột 3 — Switching Cost](#5-trụ-cột-3--tạo-switching-cost--khó-bỏ-vì-đã-đầu-tư-dữ-liệu)
6. [Vòng lặp Engagement — Hooked Model](#6-vòng-lặp-engagement--hooked-model)
7. [Aha Moments cần thiết kế](#7-aha-moments-cần-thiết-kế-có-chủ-đích)
8. [Những thứ KHÔNG làm](#8-những-thứ-không-làm)
9. [Metrics cần theo dõi](#9-metrics-cần-theo-dõi)
10. [GitHub Issues — Implementation](#10-github-issues--implementation)

---

## 1. Hiểu tâm lý SME Việt Nam

Trước khi nói về tính năng, cần hiểu **tại sao SME Việt Nam thường bỏ app**:

- Dùng khi **có vấn đề cấp bách**, xong rồi quên — thuế là "reactive", không phải "proactive"
- Không có thói quen dùng app quản lý tài chính — quen Excel, sổ tay, hỏi người quen
- **Không tin tưởng** dữ liệu của mình đưa lên cloud
- Bận — không có thời gian học tool mới nếu không thấy giá trị ngay lập tức

**Vấn đề cốt lõi:** Thuế là sự kiện theo mùa, không phải hàng ngày. Nếu không giải quyết được điều này, retention sẽ luôn thấp dù sản phẩm tốt đến đâu.

**Profile early adopter lý tưởng:**

| Đặc điểm | Mô tả |
|---|---|
| Đau thật sự | Hay bị phạt muộn, không hiểu tờ khai, sợ quyết toán |
| Tech-savvy đủ dùng | Đã dùng Telegram thường xuyên |
| Ngân sách nhỏ | Sẵn sàng trả nếu thấy giá trị rõ ràng |
| Có mạng lưới | Có thể giới thiệu cho người khác |

Cụ thể: **chủ hộ kinh doanh cá thể, freelancer, shop online (Shopee/TikTok Shop), tiệm dịch vụ nhỏ** tại Hà Nội và TP.HCM.

---

## 2. 3 Trụ cột Retention

```
┌─────────────────────────────────────────────────────────────┐
│  TRỤ CỘT 1: PROACTIVE                                       │
│  Hệ thống nhắc nhở thông minh theo lịch thuế                │
│  → Biến thuế từ "reactive" thành "proactive"                │
│  → Tạo lý do mở app trước khi có vấn đề                    │
│  ⭐ TRỌNG TÂM của tài liệu này                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  TRỤ CỘT 2: DAILY VALUE                                     │
│  Hỏi nhanh — trả lời ngay + Mini dashboard tuần            │
│  → Use case hàng ngày / hàng tuần                           │
│  → Thay thế Google search + hỏi bạn bè                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  TRỤ CỘT 3: SWITCHING COST                                  │
│  Lịch sử hỏi đáp + Hồ sơ kinh doanh tích lũy              │
│  → Càng dùng lâu càng khó bỏ                               │
│  → Dữ liệu cá nhân hóa không thể copy                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Trụ cột 1 — Hệ thống nhắc nhở thông minh theo lịch thuế

### 3.1 Tổng quan kiến trúc

Hệ thống nhắc nhở không chỉ là "gửi tin nhắn theo lịch". Gồm 3 lớp:

```
┌─────────────────────────────────────────────────┐
│  LỚP 1: THU THẬP THÔNG TIN (Personalization)    │
│  Biết khách hàng là ai, loại hình gì, deadline  │
│  nào áp dụng cho họ                             │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  LỚP 2: ENGINE TÍNH TOÁN (Intelligence)         │
│  Tính deadline, tính thuế ước tính, phát hiện   │
│  rủi ro, ưu tiên thứ tự nhắc nhở               │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│  LỚP 3: DELIVERY (Communication)                │
│  Gửi đúng người, đúng lúc, đúng ngôn ngữ,      │
│  qua đúng kênh (Telegram)                       │
└─────────────────────────────────────────────────┘
```

### 3.2 Onboarding Flow — Thu thập thông tin

**Nguyên tắc: Hỏi ít, học nhiều.** Chỉ hỏi 4 câu bắt buộc khi đăng ký.

```
Câu 1/4: Hình thức kinh doanh
  [1] Hộ kinh doanh cá thể
  [2] Cá nhân (freelancer, KOL, CTV...)
  [3] Công ty TNHH / Cổ phần
  [4] Chưa đăng ký, đang kinh doanh tự do

Câu 2/4: Doanh thu năm ngoái
  [1] Dưới 100 triệu/năm
  [2] 100 – 300 triệu/năm
  [3] 300 triệu – 1 tỷ/năm
  [4] Trên 1 tỷ/năm

Câu 3/4: Ngành nghề chính
  [1] Bán hàng / thương mại
  [2] Dịch vụ (ăn uống, sửa chữa, làm đẹp, giáo dục...)
  [3] Sản xuất / gia công
  [4] Kinh doanh online / TMĐT
  [5] Tư vấn / chuyên môn (luật, kế toán, thiết kế...)

Câu 4/4: Ai đang lo phần thuế?
  [1] Tự làm
  [2] Có kế toán riêng / dịch vụ
  [3] Chưa biết phải làm gì 😅
```

> **Tại sao câu 4 quan trọng:** Nếu họ có kế toán → tone nhắc nhở khác (nhắc để hỏi kế toán). Nếu tự làm → nhắc kèm hướng dẫn chi tiết hơn.

**Step 2 (bổ sung sau onboarding step 1):**

```
Câu hỏi bổ sung để nhắc thuế chính xác hơn:

Bạn đang kê khai thuế theo kỳ nào?
  [1] Hàng tháng (doanh thu > 50 triệu/tháng)
  [2] Hàng quý (doanh thu < 50 triệu/tháng)
  [3] Thuế khoán cố định (hộ kinh doanh nhỏ)
  [4] Chưa biết / Để hỏi sau

(Nếu có nhân viên):
Bạn có thuê nhân viên chính thức không?
  [1] Có, có nhân viên
  [2] Không, chỉ có mình tôi / cộng tác viên
```

### 3.3 Deadline Rules theo loại hình kinh doanh

| business_type | tax_period | Loại thuế | Deadline |
|---|---|---|---|
| `household` | `quarterly` | Thuế khoán | Ngày 30 tháng đầu quý sau |
| `household` | `monthly` | Kê khai | Ngày 20 tháng sau |
| `company` | `monthly` | VAT | Ngày 20 tháng sau |
| `company` | `monthly` | CIT tạm tính | Ngày 30 tháng đầu quý sau |
| `company` | `quarterly` | VAT | Ngày 30 tháng đầu quý sau |
| `individual` | — | PIT quý | Ngày 30 tháng đầu quý sau |
| `individual` | — | PIT quyết toán | 31/3 năm sau |

**Urgency levels:**

| Level | Điều kiện | Emoji | Tone |
|---|---|---|---|
| `critical` | ≤ 3 ngày | 🔴 | Khẩn cấp, hành động ngay |
| `urgent` | 4–7 ngày | 🟠 | Cần chuẩn bị ngay tuần này |
| `warning` | 8–14 ngày | 🟡 | Lên kế hoạch trong 2 tuần |
| `info` | 15–60 ngày | 🔵 | Thông tin để biết trước |

### 3.4 Timeline nhắc nhở mẫu

```
Ngày 1 mỗi tháng:   📋 "Tháng này bạn có 2 nghĩa vụ thuế cần lưu ý..."
Ngày 15:            🟡 "Còn 5 ngày nộp thuế GTGT tháng trước.
                        Doanh thu tháng bạn nhập là X — thuế ước tính Y triệu."
Ngày 18 (deadline): 🟠 "HÔM NAY là hạn nộp. Bạn đã nộp chưa?"
Ngày 20 (sau hạn):  🔴 "Nếu chưa nộp, phạt chậm nộp là 0.03%/ngày.
                        Muốn tôi tính số tiền phạt không?"
```

### 3.5 Tin nhắn mẫu thực tế

**Trường hợp 1 — Hộ KD dịch vụ, tự làm thuế, urgent:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Deadline thuế đang đến gần — còn dưới 1 tuần!

🟠 Thuế khoán Q3/2025
📆 Hạn nộp: 30/10/2025 — còn 5 ngày
💰 Ước tính: 11.4 triệu đồng (có thể khác thực tế)
⚠️ Phạt chậm: ~3,420đ/ngày (102,600đ/tháng)

💡 Cần có Thông báo thuế khoán từ Chi cục thuế
trước khi nộp. Chưa có? Nhắn 'thuế khoán'
để tôi hướng dẫn.

Nhắn 'hỗ trợ nộp thuế' nếu cần hướng dẫn
khẩn ngay bây giờ.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Trường hợp 2 — Công ty có kế toán, nhiều deadline:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Nhắc nhở thuế — còn 2 tuần để chuẩn bị.

Bạn có 3 nghĩa vụ thuế sắp đến hạn:

1. 🟡 Kê khai VAT tháng 9/2025
   📆 20/10 — Còn 12 ngày

2. 🟡 CIT tạm tính Q3/2025
   📆 30/10 — Còn 22 ngày

3. 🔵 Kê khai VAT tháng 10/2025
   📆 20/11 — Còn 43 ngày

💡 Gửi sổ sách tháng này cho kế toán
càng sớm càng tốt.

Nhắn 'xem lịch thuế' để xem đầy đủ
các deadline sắp tới của bạn.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3.6 Anti-spam Rules — Bắt buộc

- Không gửi quá **1 tin/ngày** cho cùng 1 user
- Nếu user đã nhận tin trong **20 giờ qua** → skip
- Respect `notification_enabled = FALSE` tuyệt đối
- Quá 3 lần gửi thất bại → đánh dấu lỗi, không retry vô hạn

### 3.7 Cá nhân hóa theo profile

| Nhóm | Nhận được |
|---|---|
| Hộ KD tự làm | Deadline + hướng dẫn hành động từng bước |
| Hộ KD có kế toán | Deadline + nhắc báo cho kế toán |
| Công ty kê khai tháng | VAT + CIT tạm tính + PIT nếu có nhân viên |
| Freelancer | PIT quý + nhắc lưu chứng từ |

---

## 4. Trụ cột 2 — Tạo giá trị hàng ngày (không chỉ mùa thuế)

### 4.1 Tính năng "Hỏi nhanh — trả lời ngay"

SME Việt Nam liên tục gặp câu hỏi nhỏ trong kinh doanh hàng ngày:

> *"Hóa đơn này có được khấu trừ không?"*
> *"Khách muốn thanh toán tiền mặt 50 triệu — có vấn đề gì không?"*
> *"Mình thuê cộng tác viên, có phải khấu trừ thuế TNCN không?"*

Sau mỗi câu trả lời, **gợi ý câu hỏi liên quan** để dẫn dắt session tiếp theo:

```
User: "Thuê freelancer 5 triệu có phải khấu trừ thuế không?"

Bot:  "Nếu freelancer không có MST cá nhân và bạn trả
      dưới 2 triệu/lần → không cần khấu trừ.
      Trên 2 triệu/lần → khấu trừ 10% trước khi trả.

      💡 Bạn có muốn tôi nhắc bạn làm chứng từ chi phí
      cho khoản này không? Cuối năm sẽ cần để quyết toán."
```

### 4.2 Mini Dashboard "Sức khỏe thuế" — gửi mỗi thứ Hai

```
📊 Tuần này của [Tên cửa hàng]:
• Doanh thu ghi nhận: 45 triệu
• Thuế GTGT ước tính phát sinh: 4.5 triệu
• Rủi ro cần lưu ý: Bạn chưa có hóa đơn
  cho 2 khoản chi phí lớn

→ Nhắn 'chi tiết' để xem thêm
```

Người dùng không cần làm gì — chỉ cần đọc. Nhưng họ sẽ **mở Telegram để xem**, và thường sẽ hỏi thêm.

---

## 5. Trụ cột 3 — Tạo Switching Cost (khó bỏ vì đã đầu tư dữ liệu)

### 5.1 Lịch sử hỏi đáp có thể tìm lại

Câu trả lời được cá nhân hóa theo **tình huống của họ**, không phải câu trả lời chung. Điều này tạo ra giá trị không thể thay thế bằng cách search Google.

### 5.2 Hồ sơ kinh doanh tích lũy theo thời gian

Mỗi lần tương tác, bot học thêm về người dùng. Sau 3 tháng, bot có thể nói:

> *"Năm ngoái tháng này bạn bị phạt chậm nộp — năm nay mình nhắc sớm hơn nhé."*

Cá nhân hóa như vậy **không thể copy** bởi bất kỳ tool nào khác.

---

## 6. Vòng lặp Engagement — Hooked Model

```
         ┌─────────────────────────────┐
         │   TRIGGER                   │
         │   Nhắc nhở deadline,        │
         │   báo cáo tuần, sự kiện thuế│
         └──────────────┬──────────────┘
                        │
         ┌──────────────▼──────────────┐
         │   ACTION                    │
         │   User mở app, đọc, hỏi    │
         └──────────────┬──────────────┘
                        │
         ┌──────────────▼──────────────┐
         │   REWARD                    │
         │   Câu trả lời rõ ràng,      │
         │   tiết kiệm được tiền/thời  │
         │   gian, tránh được rủi ro   │
         └──────────────┬──────────────┘
                        │
         ┌──────────────▼──────────────┐
         │   INVESTMENT                │
         │   User thêm dữ liệu, lịch  │
         │   sử tích lũy, profile đầy  │
         │   đủ hơn → trigger tốt hơn  │
         └──────────────┬──────────────┘
                        │
              quay lại TRIGGER
```

*(Áp dụng Hooked Model của Nir Eyal vào bài toán thuế SME)*

---

## 7. Aha Moments cần thiết kế có chủ đích

Cần ít nhất **3 aha moments trong 7 ngày đầu** để user quyết định tiếp tục dùng:

| Thời điểm | Aha Moment | Cách trigger |
|---|---|---|
| **Ngày 1** — onboarding | Bot tự tạo lịch thuế cá nhân hóa trong 30 giây | Gửi ngay sau onboarding hoàn thành |
| **Ngày 3** | Bot trả lời đúng câu hỏi họ đang phân vân | Proactive tip theo ngành nghề |
| **Ngày 7** | Bot nhắc một deadline họ sắp quên | Daily reminder job |

> Nếu 7 ngày đầu không có 3 khoảnh khắc này → retention tuần 2 sẽ rất thấp.

---

## 8. Những thứ KHÔNG làm

| ❌ Tránh | Lý do |
|---|---|
| Gamify kiểu "streak", "badge", "điểm thưởng" | SME không có thời gian, cảm thấy bị coi thường |
| Push notification quá 3 tin/tuần không có giá trị | SME Việt Nam rất nhạy cảm với spam → block bot ngay |
| Hỏi quá 5 câu khi onboarding | 60% user sẽ bỏ giữa chừng |
| Scale trước khi có product-market fit | Lãng phí ngân sách, không học được gì từ data |

**Dấu hiệu đã có PMF:**
- User tự giới thiệu mà không cần nhờ
- > 40% nói "rất buồn" nếu sản phẩm biến mất
- Retention sau 30 ngày > 30%

---

## 9. Metrics cần theo dõi

| Metric | Target | Đo khi nào |
|---|---|---|
| D1 Retention (quay lại ngày 2) | > 50% | Từ ngày đầu |
| D30 Retention (còn active sau 30 ngày) | > 30% | Tháng 1 |
| Trial → Paid conversion | > 15% | Tháng 2–3 |
| Notification open rate | > 60% | Từ ngày đầu |
| Notification → Interaction rate | > 25% | Từ ngày đầu |
| NPS Score | > 40 | Hàng tháng |

---

## 10. GitHub Issues — Implementation

> **Hướng dẫn sử dụng:** Các issues dưới đây được viết sẵn để đưa vào GitHub. Implement theo thứ tự phụ thuộc được ghi rõ. Mỗi issue là một đơn vị công việc độc lập có thể assign cho một developer hoặc AI agent.

### Thứ tự implement

```
Issue 1 (DB schema)
    │
    ├── Issue 2 (Deadline Calculator)   ← làm song song với Issue 3
    ├── Issue 3 (Message Builder)       ← làm song song với Issue 2
    │
    └── Issue 4 (Scheduler)             ← cần Issue 2 + 3 xong trước
            │
            ├── Issue 5 (Onboarding)    ← làm song song với Issue 6
            └── Issue 6 (API Endpoints) ← làm song song với Issue 5
```

---

### Issue 1 — `[DB] Enhance user_profiles schema for notification personalization`

**Labels:** `database`, `enhancement`
**Milestone:** Notification System v1

#### Context

Hệ thống hiện tại đã có bảng `user_profiles` và onboarding flow thu thập thông tin cơ bản. Issue này **extend schema hiện tại** — không tạo mới — để hỗ trợ các trường cần thiết cho notification engine.

#### Current State

```
user_profiles hiện tại có: telegram_id, business_type,
revenue_range, industry, tax_handler (hoặc tương đương)
```

#### Requirements

**1. Thêm các cột vào bảng `user_profiles` hiện tại:**

```sql
-- DÙNG ALTER TABLE, KHÔNG DROP TABLE

ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS tax_period
    VARCHAR(20) DEFAULT NULL,
  -- 'monthly' | 'quarterly' | 'flat_rate'
  -- NULL = chưa xác định

  ADD COLUMN IF NOT EXISTS vat_method
    VARCHAR(20) DEFAULT NULL,
  -- 'deduction' | 'direct' | 'exempt'

  ADD COLUMN IF NOT EXISTS has_employees
    BOOLEAN DEFAULT FALSE,
  -- Ảnh hưởng đến PIT withholding

  ADD COLUMN IF NOT EXISTS province_code
    VARCHAR(10) DEFAULT NULL,
  -- Ảnh hưởng đến Chi cục thuế địa phương

  ADD COLUMN IF NOT EXISTS notification_enabled
    BOOLEAN DEFAULT TRUE,

  ADD COLUMN IF NOT EXISTS preferred_notify_hour
    SMALLINT DEFAULT 8,
  -- 0-23, mặc định 8 giờ sáng

  ADD COLUMN IF NOT EXISTS preferred_notify_minute
    SMALLINT DEFAULT 30,
  -- 0-59, mặc định 30 phút

  ADD COLUMN IF NOT EXISTS last_notified_at
    TIMESTAMP DEFAULT NULL,

  ADD COLUMN IF NOT EXISTS onboarding_step
    SMALLINT DEFAULT 1;
  -- 1=basic done, 2=tax_period collected, 3=complete
```

**2. Tạo bảng mới `notification_logs`:**

```sql
CREATE TABLE IF NOT EXISTS notification_logs (
    id                UUID      PRIMARY KEY
                                DEFAULT gen_random_uuid(),
    user_id           UUID      NOT NULL
                                REFERENCES user_profiles(id),
    notification_type VARCHAR(50) NOT NULL,
    -- 'deadline_reminder' | 'weekly_summary' | 'monthly_calendar'
    deadline_types    TEXT[],
    -- Mảng các loại deadline được nhắc, vd: ['vat', 'cit']
    sent_at           TIMESTAMP DEFAULT NOW(),
    was_delivered     BOOLEAN   DEFAULT TRUE,
    user_replied      BOOLEAN   DEFAULT FALSE,
    reply_within_hours SMALLINT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_notification_logs_user_id
  ON notification_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_notification_logs_sent_at
  ON notification_logs(sent_at);
```

**3. Tạo bảng `revenue_snapshots`:**

```sql
CREATE TABLE IF NOT EXISTS revenue_snapshots (
    id         UUID          PRIMARY KEY
                             DEFAULT gen_random_uuid(),
    user_id    UUID          NOT NULL
                             REFERENCES user_profiles(id),
    period     DATE          NOT NULL,
    -- Ngày đầu tháng, vd: 2025-10-01
    amount     DECIMAL(15,0) NOT NULL,
    -- Số tiền VND, không có số lẻ
    source     VARCHAR(20)   DEFAULT 'user_reported',
    -- 'user_reported' | 'inferred'
    created_at TIMESTAMP     DEFAULT NOW(),
    UNIQUE(user_id, period)
);
```

#### Migration Strategy

- Viết Alembic migration script (không dùng raw SQL trực tiếp)
- Migration phải idempotent — chạy lại nhiều lần không lỗi (`IF NOT EXISTS`, `IF EXISTS`)
- Không xóa hoặc rename cột hiện tại
- Rollback script phải được viết kèm

#### Acceptance Criteria

- [ ] Migration chạy thành công trên DB hiện tại không mất data
- [ ] Rollback migration hoạt động
- [ ] Các cột cũ không bị ảnh hưởng
- [ ] Indexes được tạo cho các cột query thường xuyên

---

### Issue 2 — `[Backend] Deadline Calculator Engine`

**Labels:** `python`, `backend`, `core`
**Milestone:** Notification System v1
**Depends on:** Issue 1

#### Context

Tạo module Python mới trong `tax-engine` để tính toán deadline thuế cho từng user dựa trên profile của họ. Đây là **business logic thuần** — không có side effects, dễ test.

#### File Location

```
tax-engine/
  app/
    services/
      deadline_calculator.py    ← file mới
    tests/
      test_deadline_calculator.py ← bắt buộc viết kèm
```

#### Requirements

**Class `DeadlineCalculator` phải implement:**

**1. Method chính:**

```python
def get_deadlines_for_user(
    self,
    profile: dict,
    reference_date: date
) -> list[dict]:
    """
    Input:  profile dict từ DB, date hôm nay
    Output: list deadline trong 60 ngày tới,
            sort theo due_date tăng dần

    Mỗi deadline dict có shape:
    {
      'due_date': date,
      'type': str,
      # 'flat_tax'|'vat'|'cit'|'pit'|'pit_annual'
      'label': str,
      # vd: "Thuế khoán Q3/2025"
      'urgency': str,
      # 'critical'|'urgent'|'warning'|'info'
      'estimated_amount': int | None,
      # VND, None nếu không tính được
      'penalty_per_day': int | None
      # VND phạt/ngày nếu nộp trễ
    }
    """
```

**2. Logic deadline theo loại hình:**

```
household + quarterly  → Thuế khoán ngày 30 tháng đầu quý sau
household + monthly    → Kê khai ngày 20 tháng sau
company + monthly      → VAT ngày 20 tháng sau
                         CIT tạm tính ngày 30 tháng đầu quý sau
company + quarterly    → VAT ngày 30 tháng đầu quý sau
                         CIT tạm tính như trên
individual             → PIT quý ngày 30 tháng đầu quý sau
                         PIT annual ngày 31/3 năm sau
```

**3. Urgency rules:**

```
critical : days_left <= 3
urgent   : 4  <= days_left <= 7
warning  : 8  <= days_left <= 14
info     : 15 <= days_left <= 60
```

**4. Ước tính thuế theo Thông tư 40/2021/TT-BTC:**

```
Thương mại / TMĐT : 1.0% doanh thu   (0.5% VAT + 0.5% PIT)
Dịch vụ           : 7.0% doanh thu   (5.0% VAT + 2.0% PIT)
Sản xuất          : 4.5% doanh thu   (3.0% VAT + 1.5% PIT)
Tư vấn            : 7.0% doanh thu   (5.0% VAT + 2.0% PIT)
```

Chỉ tính được khi có `revenue_snapshots` trong DB. Return `None` nếu không đủ dữ liệu.

#### Test Cases Bắt Buộc

```python
# test_deadline_calculator.py phải cover:

def test_household_quarterly_has_4_deadlines_per_year()
def test_company_monthly_vat_deadline_is_day_20()
def test_company_quarterly_cit_deadline_is_day_30()
def test_february_edge_case_no_crash()
def test_december_31_next_year_handled()
def test_missing_tax_period_returns_empty_list()
def test_urgency_critical_when_3_days_left()
def test_urgency_info_when_30_days_left()
def test_estimated_amount_none_when_no_revenue_data()
```

#### Acceptance Criteria

- [ ] Tất cả test cases pass
- [ ] Không import từ Telegram/Node layer (pure business logic)
- [ ] Xử lý được edge case tháng 2 (28/29 ngày)
- [ ] Xử lý deadline năm sau khi reference_date là cuối tháng 12

---

### Issue 3 — `[Backend] Message Builder — Personalized Notification Content`

**Labels:** `python`, `backend`
**Milestone:** Notification System v1
**Depends on:** Issue 2

#### Context

Module tạo nội dung tin nhắn Telegram từ kết quả của `DeadlineCalculator`. Nội dung phải **cá nhân hóa theo profile** và **thay đổi tone theo urgency**.

#### File Location

```
tax-engine/
  app/
    services/
      message_builder.py    ← file mới
```

#### Requirements

**Class `NotificationMessageBuilder` phải implement:**

**1. `build_deadline_reminder(user, deadlines, today) -> str | None`**
- Trả về string Markdown cho Telegram
- Trả về `None` nếu `deadlines` rỗng (không gửi gì)
- Tone thay đổi theo urgency của deadline gần nhất
- Nếu nhiều deadline: hiển thị tối đa 3, ghi chú số còn lại

**2. `build_weekly_summary(user, deadlines_this_month) -> str`**
- Gửi mỗi thứ Hai
- Tóm tắt deadline còn lại trong tháng
- Kèm 1 "tip thuế tuần này" — xoay vòng theo chủ đề

**3. `build_monthly_calendar(user, deadlines) -> str`**
- Gửi ngày 1 mỗi tháng
- Danh sách đầy đủ deadline tháng đó với ngày cụ thể

**4. Cá nhân hóa bắt buộc:**

```
Theo tax_handler:
  'self'        → thêm hướng dẫn hành động cụ thể
  'accountant'  → nhắc "báo cho kế toán của bạn"
  'unknown'     → thêm link hỏi bot trợ giúp

Theo business_type + industry:
  household + service   → nhắc Thông báo thuế khoán
                          từ Chi cục thuế
  company + any         → nhắc sổ sách đầu vào/đầu ra
  individual + any      → nhắc lưu chứng từ chi phí
```

**5. Format số tiền VND:**

```
< 1,000,000      → "850,000 đồng"
1,000,000+       → "8.5 triệu đồng"
1,000,000,000+   → "1.2 tỷ đồng"
```

**6. Giới hạn kỹ thuật:**
- Output không vượt quá 4,096 ký tự (giới hạn Telegram message)
- Sử dụng Markdown hợp lệ cho Telegram (`*bold*`, `_italic_`)
- Không dùng HTML tags

#### Acceptance Criteria

- [ ] `build_deadline_reminder` trả về `None` khi `deadlines` rỗng
- [ ] Output không vượt 4,096 ký tự trong mọi trường hợp
- [ ] Mỗi loại `tax_handler` cho ra nội dung khác nhau rõ ràng
- [ ] Format tiền VND đúng cho cả 3 ngưỡng

---

### Issue 4 — `[Backend] Notification Scheduler Service`

**Labels:** `python`, `backend`, `infra`
**Milestone:** Notification System v1
**Depends on:** Issue 2, Issue 3

#### Context

Background service dùng APScheduler để chạy các notification jobs định kỳ. Tích hợp vào `tax-engine` hiện tại — **không tạo service mới**, không thay đổi Docker Compose.

#### File Location

```
tax-engine/
  app/
    services/
      notification_scheduler.py    ← file mới
  main.py                          ← sửa để add startup/shutdown hooks
  requirements.txt                 ← thêm apscheduler==3.10.4
```

#### Requirements

**1. Tích hợp vào FastAPI startup:**

```python
# Trong main.py, thêm vào startup/shutdown events
# KHÔNG xóa code startup hiện tại, chỉ append thêm

@app.on_event("startup")
async def startup():
    # ... existing startup code giữ nguyên ...
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    # ... existing shutdown code giữ nguyên ...
    scheduler.shutdown()
```

**2. Ba scheduled jobs:**

```
daily_deadline_check
  Schedule : Mỗi ngày lúc 08:30 (Asia/Ho_Chi_Minh)
  Logic    : Query users có deadline ≤ 14 ngày
             → Build message → Gửi Telegram
             → Log vào notification_logs

weekly_summary
  Schedule : Thứ Hai hàng tuần lúc 09:00
  Logic    : Gửi tóm tắt tuần cho all active users
             (last_active_at trong 90 ngày qua)

monthly_calendar
  Schedule : Ngày 1 hàng tháng lúc 08:00
  Logic    : Gửi lịch thuế tháng mới
```

**3. Anti-spam logic — bắt buộc:**

```python
# Trước khi gửi bất kỳ notification nào:
# 1. Check notification_enabled == TRUE
# 2. Check last_notified_at < NOW() - INTERVAL '20 hours'
# 3. Nếu một trong hai fail → skip user này
# 4. Sau khi gửi thành công → UPDATE last_notified_at = NOW()
```

**4. Retry và error handling:**

```
Gửi thất bại lần 1 → retry sau 5 phút
Gửi thất bại lần 2 → retry sau 5 phút
Gửi thất bại lần 3 → log ERROR, was_delivered=FALSE, tiếp tục
KHÔNG crash toàn bộ job vì 1 user lỗi
```

**5. Logging chuẩn sau mỗi job:**

```
[daily_deadline_check] Complete:
  checked=1,234 | sent=89 | skipped=1,101 | failed=44
  duration=12.3s
```

**6. Dependency cần thêm:**

```
# requirements.txt
apscheduler==3.10.4
pytz==2024.1
```

#### Acceptance Criteria

- [ ] `AsyncIOScheduler` được dùng (không dùng `BackgroundScheduler` — sẽ block event loop)
- [ ] Timezone là `Asia/Ho_Chi_Minh` cho tất cả schedules
- [ ] Restart Docker container → scheduler tự start, không duplicate jobs
- [ ] Anti-spam: chạy `daily_deadline_check` 2 lần liên tiếp → lần 2 gửi 0 tin
- [ ] 1 user lỗi không làm crash cả job

---

### Issue 5 — `[Bot] Onboarding Flow Enhancement — Thu thập Tax Period & Employee Status`

**Labels:** `node`, `telegram-bot`, `enhancement`
**Milestone:** Notification System v1
**Depends on:** Issue 1

#### Context

Onboarding hiện tại đã thu thập thông tin cơ bản. Issue này **thêm step 2** để thu thập `tax_period` và `has_employees` — hai trường cần thiết cho deadline calculator.

**Quan trọng:** Không phá vỡ flow onboarding hiện tại. User cũ (`onboarding_step = 1`) sẽ thấy câu hỏi bổ sung ở lần tương tác tiếp theo sau khi deploy.

#### File Location

```
node-gateway/
  src/
    handlers/
      onboarding.js    ← sửa file hiện tại, thêm step 2
    keyboards/
      tax_period.js    ← file mới: inline keyboard buttons
```

#### Requirements

**1. Step 2 — Câu hỏi kỳ kê khai:**

Trigger khi: user gửi bất kỳ tin nhắn nào VÀ `onboarding_step == 1`

```
Tin nhắn bot gửi:
━━━━━━━━━━━━━━━━━━━━━━━━━
Để nhắc thuế chính xác hơn, mình cần
biết thêm một chút nhé!

Bạn đang kê khai thuế theo kỳ nào?

[📅 Hàng tháng]   [📆 Hàng quý]
[🏪 Thuế khoán]   [❓ Chưa biết]
━━━━━━━━━━━━━━━━━━━━━━━━━
```

Mapping button → DB value:
- "Hàng tháng" → `tax_period = 'monthly'`
- "Hàng quý" → `tax_period = 'quarterly'`
- "Thuế khoán" → `tax_period = 'flat_rate'`
- "Chưa biết" → `tax_period = NULL`, set `onboarding_step = 3` (skip)

**2. Step 2b — Câu hỏi nhân viên (chỉ hiện nếu business_type là `company` hoặc `household`):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━
Câu cuối cùng thôi! 😊

Bạn có thuê nhân viên chính thức không?
(Ảnh hưởng đến nghĩa vụ thuế TNCN)

[👥 Có nhân viên]   [🙋 Chỉ mình tôi]
━━━━━━━━━━━━━━━━━━━━━━━━━
```

**3. Sau khi hoàn thành step 2:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Đã cập nhật hồ sơ thuế của bạn!

Tôi sẽ nhắc bạn trước mỗi deadline thuế.
Nhắc nhở đầu tiên sẽ vào sáng mai lúc 8:30.

Nhắn 'lịch thuế' để xem ngay các deadline
sắp tới của bạn.
━━━━━━━━━━━━━━━━━━━━━━━━━
```

Sau khi gửi tin nhắn này → gọi `POST /notifications/preview/{telegram_id}` để gửi lịch thuế preview ngay lập tức.

**4. Handling user cũ:**

```javascript
// Trong message handler hiện tại, thêm check:
if (user.onboarding_step === 1) {
  // Intercept message, hỏi câu step 2 trước
  // Sau khi trả lời xong mới xử lý message gốc
}
```

#### Acceptance Criteria

- [ ] User cũ (`onboarding_step=1`) nhận câu hỏi step 2 ở lần tương tác tiếp
- [ ] User mới đi qua cả 2 steps liền mạch
- [ ] Skip ("Chưa biết") không crash, default về `quarterly`
- [ ] `onboarding_step` được update đúng sau mỗi step
- [ ] Gọi được `/notifications/preview` sau khi hoàn thành

---

### Issue 6 — `[API] Notification REST Endpoints`

**Labels:** `python`, `api`, `backend`
**Milestone:** Notification System v1
**Depends on:** Issue 4

#### Context

Expose các REST endpoints để Node gateway và admin tương tác với notification system. Dùng cho cả production và debugging.

#### File Location

```
tax-engine/
  app/
    routers/
      notifications.py    ← file mới, register vào main.py
    schemas/
      notification.py     ← Pydantic schemas
```

#### Endpoints

**`GET /notifications/upcoming/{telegram_id}`**

Node gateway gọi khi user nhắn "lịch thuế".

Response `200`:
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
  "generated_at": "2025-10-25T08:30:00+07:00"
}
```

Response `404`: `{"detail": "User not found"}`

---

**`POST /notifications/preview/{telegram_id}`**

Tính toán và gửi ngay tin nhắn lịch thuế preview. Dùng sau onboarding step 2.
Không tính vào anti-spam counter.

Response `200`: `{"sent": true, "message_preview": "..."}`

---

**`PUT /notifications/settings/{telegram_id}`**

Cập nhật notification preferences.

Request body:
```json
{
  "notification_enabled": true,
  "preferred_notify_hour": 8,
  "preferred_notify_minute": 30
}
```

Response `200`: `{"updated": true}`

---

**`GET /notifications/scheduler/status`**

Trạng thái các scheduled jobs — dùng cho monitoring.

Response `200`:
```json
{
  "scheduler_running": true,
  "jobs": [
    {
      "id": "daily_deadline_check",
      "next_run": "2025-10-26T08:30:00+07:00",
      "last_run": "2025-10-25T08:30:00+07:00",
      "last_run_sent": 47,
      "last_run_skipped": 12,
      "last_run_failed": 2
    }
  ]
}
```

---

**`POST /notifications/test/{telegram_id}`** *(Dev/Staging only)*

Trigger gửi tin nhắn test ngay lập tức. Không check anti-spam.

```python
# Bắt buộc guard:
if settings.ENV == "production":
    raise HTTPException(status_code=403,
                        detail="Not available in production")
```

#### Acceptance Criteria

- [ ] Tất cả endpoints có Pydantic request/response schema
- [ ] `telegram_id` không tồn tại → 404, không crash
- [ ] Test endpoint bị block hoàn toàn khi `ENV=production`
- [ ] Endpoint `scheduler/status` hoạt động kể cả khi scheduler chưa chạy job nào
- [ ] Register router vào `main.py` với prefix `/notifications`

---

## Phụ lục — Roadmap tổng thể

```
Tháng 1–2:  Facebook Groups + Kế toán dịch vụ → 20–30 users dùng thử
Tháng 2–3:  Thu testimonial, fix pain points, referral → 50 users
Tháng 3–6:  TikTok content + Partnership đầu tiên → 200 users
Tháng 6–12: Paid acquisition + Scale partnership → 500+ users
```

**Chỉ bắt đầu paid acquisition sau khi:**
- Conversion rate trial → paid > 15%
- D30 Retention > 30%
- NPS > 40

---

*Tài liệu này được tạo như một living document — cập nhật khi có learnings từ user thực tế.*
*Version 1.0 — Tháng 10/2025*
