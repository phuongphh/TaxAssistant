# TaxAssistant — CLAUDE.md

> Đây là tài liệu hướng dẫn cho Claude Code và các AI agents.
> Đọc toàn bộ file này trước khi thực hiện bất kỳ thay đổi nào.
> Tài liệu chiến lược đầy đủ: `docs/strategy/retention-strategy.md`

---

## 1. Product Context

TaxAssistant là **Telegram bot trợ lý thuế tự động** cho SME Việt Nam.

**Target users:**
- Hộ kinh doanh cá thể (hộ KD)
- Freelancer / cá nhân kinh doanh
- Công ty TNHH / cổ phần quy mô nhỏ
- Chủ shop online (Shopee, TikTok Shop, Lazada)

**Vấn đề cốt lõi sản phẩm giải quyết:**
Thuế là hành vi "reactive" (chỉ nhớ khi sắp bị phạt).
TaxAssistant biến thuế thành "proactive" — nhắc đúng lúc,
giải thích đúng ngôn ngữ người dùng, cá nhân hóa theo
từng loại hình kinh doanh.

**Luật thuế áp dụng:** Thông tư 40/2021/TT-BTC và các
văn bản liên quan (16 tài liệu đã được index vào ChromaDB).

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  TELEGRAM USER                                          │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│  NODE.JS GATEWAY  (port 3000 / 3001)                    │
│  Telegraf bot framework                                 │
│  Xử lý: routing tin nhắn, inline keyboards,            │
│  conversation state, onboarding flow                    │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP / gRPC
┌───────────────────────▼─────────────────────────────────┐
│  PYTHON / FASTAPI TAX-ENGINE  (port 8000 / 50051)       │
│  Xử lý: AI reasoning, RAG, tax logic, notifications,    │
│  APScheduler jobs, Anthropic API calls                  │
└──────┬─────────────────┬───────────────────────────────┘
       │                 │
┌──────▼──────┐   ┌──────▼──────────────────────────────┐
│ PostgreSQL  │   │  ChromaDB                           │
│ port 5432   │   │  Vector search cho 16 văn bản       │
│ Structured  │   │  luật thuế Việt Nam                 │
│ data        │   └─────────────────────────────────────┘
└──────┬──────┘
       │
┌──────▼──────┐
│   Redis     │
│  port 6379  │
│  Session    │
│  & cache    │
└─────────────┘
```

**Quy tắc phân tầng — KHÔNG được vi phạm:**
- Node.js gateway: CHỈ xử lý messaging, routing, UI bot
- Python tax-engine: TẤT CẢ business logic, AI, tax calculations
- Không đặt tax logic trong Node.js
- Không gọi Telegram API trực tiếp từ Python (phải qua Node gateway
  hoặc qua Telegram Bot API nếu scheduler cần gửi trực tiếp)

---

## 3. Project Structure

```
TaxAssistant/
├── CLAUDE.md                        ← file này
├── docker-compose.yml
├── .env                             ← secrets, KHÔNG commit
├── .env.example                     ← template, được commit
│
├── node-gateway/
│   ├── src/
│   │   ├── bot.js                   ← Telegraf init, middleware
│   │   ├── handlers/
│   │   │   ├── onboarding.js        ← onboarding flow
│   │   │   ├── tax_query.js         ← xử lý câu hỏi thuế
│   │   │   └── commands.js          ← /start, /help, /schedule
│   │   ├── keyboards/               ← inline keyboard definitions
│   │   └── api/
│   │       └── tax_engine_client.js ← HTTP client gọi Python
│   └── package.json
│
├── tax-engine/
│   ├── app/
│   │   ├── main.py                  ← FastAPI app, startup hooks
│   │   ├── routers/
│   │   │   ├── tax.py               ← tax Q&A endpoints
│   │   │   └── notifications.py     ← notification endpoints (mới)
│   │   ├── services/
│   │   │   ├── deadline_calculator.py  ← (mới) tax deadline logic
│   │   │   ├── message_builder.py      ← (mới) notification content
│   │   │   ├── notification_scheduler.py ← (mới) APScheduler jobs
│   │   │   ├── rag_service.py       ← ChromaDB RAG
│   │   │   └── llm_service.py       ← Anthropic API calls
│   │   ├── models/
│   │   │   └── user.py              ← SQLAlchemy models
│   │   ├── schemas/
│   │   │   └── notification.py      ← (mới) Pydantic schemas
│   │   └── db/
│   │       └── migrations/          ← Alembic migration files
│   └── requirements.txt
│
└── docs/
    ├── strategy/
    │   └── retention-strategy.md    ← chiến lược đầy đủ + 6 issues
    └── issues/                      ← (tùy chọn) issues tách riêng
```

---

## 4. Environment & Secrets

**TUYỆT ĐỐI KHÔNG:**
- Hardcode token, API key, password vào bất kỳ file nào
- Commit file `.env` lên git
- Log ra giá trị của secrets

**Tất cả secrets phải ở `.env`:**

```bash
# .env (không commit)
TELEGRAM_BOT_TOKEN=...
ANTHROPIC_API_KEY=...
POSTGRES_URL=postgresql://user:pass@localhost:5432/taxassistant
REDIS_URL=redis://localhost:6379
ENV=development   # hoặc production
```

**Đọc trong Python:**
```python
from app.config import settings  # dùng pydantic BaseSettings
# KHÔNG dùng os.environ trực tiếp trong business logic
```

---

## 5. Database Rules

### Schema changes — BẮT BUỘC tuân theo

```sql
-- ✅ ĐÚNG: Thêm cột mới
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS tax_period VARCHAR(20) DEFAULT NULL;

-- ❌ SAI: Không bao giờ làm điều này
DROP TABLE user_profiles;
CREATE TABLE user_profiles (...);

-- ❌ SAI: Không rename cột đang có data
ALTER TABLE user_profiles RENAME COLUMN old_name TO new_name;
```

**Mọi schema change phải:**
1. Viết Alembic migration script (trong `tax-engine/app/db/migrations/`)
2. Migration phải idempotent (`IF NOT EXISTS`, `IF EXISTS`)
3. Có rollback script đi kèm
4. Test rollback trước khi merge

### Kiểu dữ liệu cho tiền VND

```python
# ✅ ĐÚNG
from decimal import Decimal
amount = Decimal('11400000')  # 11.4 triệu VND

# Trong SQLAlchemy model
amount = Column(Numeric(15, 0))  # 15 chữ số, 0 số lẻ

# ❌ SAI — float gây sai số với tiền tệ
amount = 11400000.0
```

### Các bảng quan trọng

```
user_profiles       ← profile người dùng, onboarding data
notification_logs   ← lịch sử notification đã gửi
revenue_snapshots   ← doanh thu user tự báo cáo
```

Xem schema đầy đủ trong migration files và
`docs/strategy/retention-strategy.md` — Issue 1.

---

## 6. Python / Tax-Engine Conventions

### Timezone — BẮT BUỘC

```python
# Tất cả scheduler jobs và timestamp phải dùng:
TIMEZONE = "Asia/Ho_Chi_Minh"

# APScheduler:
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Khi tạo datetime:
from zoneinfo import ZoneInfo
vn_tz = ZoneInfo("Asia/Ho_Chi_Minh")
now = datetime.now(vn_tz)

# ❌ SAI — không dùng UTC rồi convert sau
datetime.utcnow()
```

### Tax domain constants

```python
# Tỷ lệ thuế khoán theo Thông tư 40/2021/TT-BTC
TAX_RATES = {
    "trading":    Decimal("0.01"),   # Thương mại: 1%
    "service":    Decimal("0.07"),   # Dịch vụ: 7%
    "production": Decimal("0.045"),  # Sản xuất: 4.5%
    "online":     Decimal("0.01"),   # TMĐT: 1%
    "consulting": Decimal("0.07"),   # Tư vấn: 7%
}

# Deadline rules
VAT_MONTHLY_DEADLINE_DAY    = 20   # Ngày 20 tháng sau
VAT_QUARTERLY_DEADLINE_DAY  = 30   # Ngày 30 tháng đầu quý sau
CIT_PROVISIONAL_DEADLINE    = 30   # Ngày 30 tháng đầu quý sau
FLAT_TAX_QUARTERLY_DEADLINE = 30   # Ngày 30 tháng đầu quý sau

# Phạt chậm nộp
LATE_PENALTY_RATE_PER_DAY = Decimal("0.0003")  # 0.03%/ngày
```

### Urgency levels

```python
# Dùng nhất quán trong toàn bộ codebase
URGENCY_CRITICAL = "critical"  # <= 3 ngày
URGENCY_URGENT   = "urgent"    # 4–7 ngày
URGENCY_WARNING  = "warning"   # 8–14 ngày
URGENCY_INFO     = "info"      # 15–60 ngày
```

### Format tiền VND

```python
def format_vnd(amount: int) -> str:
    """
    < 1,000,000       → "850,000 đồng"
    1,000,000+        → "8.5 triệu đồng"
    1,000,000,000+    → "1.2 tỷ đồng"
    """
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.1f} tỷ đồng"
    elif amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f} triệu đồng"
    else:
        return f"{amount:,} đồng".replace(",", ".")
```

### Notification anti-spam — BẮT BUỘC check trước mọi lần gửi

```python
# Trước khi gửi notification cho bất kỳ user nào:
# 1. Check notification_enabled == True
# 2. Check last_notified_at < NOW() - 20 giờ
# 3. Nếu một trong hai fail → skip, không raise exception
# Xem implementation đầy đủ: notification_scheduler.py
```

---

## 7. Node.js / Gateway Conventions

### Fetch fix cho Telegraf (đã được giải quyết)

```javascript
// bot.js — PHẢI có dòng này TRƯỚC khi import Telegraf
// Fix lỗi ETIMEDOUT trong Docker container
const fetch = require('node-fetch');
globalThis.fetch = fetch;

const { Telegraf } = require('telegraf');
```

### Base image Docker cho Node

```dockerfile
# ✅ ĐÚNG — Debian slim, ít lỗi DNS hơn Alpine
FROM node:20-slim

# ❌ Tránh — Alpine có musl libc gây lỗi DNS trong một số môi trường
FROM node:20-alpine
```

### Conversation state

```javascript
// Dùng Redis để lưu conversation state
// Key pattern: `session:{telegram_id}`
// TTL: 24 giờ cho active sessions

// KHÔNG lưu state trong memory (sẽ mất khi restart container)
```

---

## 8. Anthropic API / LLM Usage

### Model selection

```python
# MVP: dùng Sonnet cho tất cả
MODEL = "claude-sonnet-4-20250514"

# Tương lai (khi có đủ data để benchmark):
# - Haiku cho câu hỏi đơn giản (tra cứu, FAQ)
# - Sonnet cho reasoning phức tạp (quyết toán, tư vấn)
```

### Prompt caching — BẮT BUỘC cho system prompt

```python
# System prompt chứa 16 văn bản luật thuế rất dài
# → PHẢI dùng prompt caching để giảm chi phí

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": VIETNAMESE_TAX_LAW_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"}
                # ← cache_control bắt buộc cho system prompt lớn
            },
            {
                "type": "text",
                "text": user_question
            }
        ]
    }
]
```

### RAG pipeline

```python
# Trước khi gọi LLM, luôn query ChromaDB trước:
# 1. Embed câu hỏi của user
# 2. Query ChromaDB lấy top-3 đoạn văn bản luật liên quan
# 3. Đưa context vào prompt
# Xem: tax-engine/app/services/rag_service.py
```

---

## 9. Docker & Infrastructure

### Docker Compose — các service và port

```yaml
# Tham khảo docker-compose.yml
# tax-engine:    port 8000 (HTTP), 50051 (gRPC)
# node-gateway:  port 3000, 3001
# postgres:      port 5432
# redis:         port 6379
```

### DNS fix trong Docker (đã được giải quyết)

```yaml
# docker-compose.yml — thêm vào service có vấn đề DNS
services:
  node-gateway:
    dns_search:
      - "."
```

### Khi thêm dependency mới

```bash
# Python — BẮT BUỘC dùng flag này trên Docker/Ubuntu
pip install package-name --break-system-packages

# Sau đó update requirements.txt:
pip freeze | grep package-name >> requirements.txt
```

---

## 10. GitHub Workflow

### Branch naming convention

```
feature/issue-{number}-{short-description}
fix/issue-{number}-{short-description}
chore/issue-{number}-{short-description}

Ví dụ:
feature/issue-12-deadline-calculator
fix/issue-15-scheduler-timezone
```

### PR tự động với PAT_TOKEN

```yaml
# GitHub Actions dùng PAT_TOKEN (không phải GITHUB_TOKEN)
# để bot-created PRs trigger downstream CI/CD workflows
# Secret name trong repo: PAT_TOKEN
```

### Project board

- GitHub Project V2, Project #2, owner: phuongphh
- Mọi issue phải được add vào project board

---

## 11. Retention Targets — Mọi feature phải phục vụ điều này

**3 mục tiêu retention cốt lõi:**

```
1. PROACTIVE VALUE
   Tạo lý do mở app khi KHÔNG có deadline khẩn cấp.
   → Hệ thống nhắc nhở thông minh (notification system)
   → Weekly tax health summary mỗi thứ Hai

2. PERSONALIZATION
   Mỗi user nhận trải nghiệm khác nhau dựa trên profile.
   → Cá nhân hóa theo: business_type, tax_period,
     tax_handler, industry, has_employees
   → Tip và hướng dẫn khác nhau cho từng nhóm

3. SWITCHING COST
   Càng dùng lâu càng khó bỏ vì đã đầu tư dữ liệu.
   → Lưu toàn bộ lịch sử hỏi đáp
   → Profile tích lũy theo thời gian
   → Cảnh báo cá nhân hóa dựa trên lịch sử ("năm ngoái
     tháng này bạn bị phạt...")
```

**Metrics target:**

| Metric | Target |
|---|---|
| D1 Retention | > 50% |
| D30 Retention | > 30% |
| Notification open rate | > 60% |
| Trial → Paid conversion | > 15% |
| NPS | > 40 |

**Khi implement bất kỳ feature nào, hãy hỏi:**
> *"Feature này phục vụ mục tiêu retention nào trong 3 mục tiêu trên?"*
> Nếu không trả lời được → cần discuss trước khi code.

---

## 12. Implementation Roadmap — Notification System

Đây là module đang được implement. Thứ tự phụ thuộc:

```
Issue 1: DB Schema Enhancement         ← LÀM TRƯỚC TIÊN
         (ALTER TABLE user_profiles,
          tạo notification_logs,
          revenue_snapshots)
    │
    ├── Issue 2: Deadline Calculator    ← Làm song song
    │   tax-engine/app/services/        với Issue 3
    │   deadline_calculator.py
    │
    ├── Issue 3: Message Builder        ← Làm song song
    │   tax-engine/app/services/        với Issue 2
    │   message_builder.py
    │
    └── Issue 4: Notification Scheduler ← Cần Issue 2+3 xong
        tax-engine/app/services/
        notification_scheduler.py
              │
              ├── Issue 5: Onboarding   ← Làm song song
              │   Enhancement           với Issue 6
              │
              └── Issue 6: REST API     ← Làm song song
                  Endpoints             với Issue 5
```

Spec chi tiết từng issue:
`docs/strategy/retention-strategy.md` — Phần 10.

---

## 13. Known Issues & Gotchas

| Vấn đề | Trạng thái | Giải pháp |
|---|---|---|
| Telegraf `ETIMEDOUT` trong Docker | ✅ Resolved | Patch `globalThis.fetch` với `node-fetch` trước khi import Telegraf |
| Alpine Linux DNS resolution | ✅ Resolved | Dùng `node:20-slim` (Debian) thay Alpine |
| Bot-created PRs không trigger CI/CD | ✅ Resolved | Dùng `PAT_TOKEN` thay `GITHUB_TOKEN` |
| Telegram token bị hardcode | ✅ Resolved | Đã chuyển vào `.env` |
| Float precision với tiền VND | ⚠️ Watch out | Luôn dùng `Decimal`, không dùng `float` |
| APScheduler block event loop | ⚠️ Watch out | Dùng `AsyncIOScheduler`, không dùng `BackgroundScheduler` |

---

## 14. Quick Reference — Lệnh thường dùng

```bash
# Khởi động toàn bộ stack
cd ~/TaxAssistant
docker compose up -d

# Xem logs
docker compose logs -f tax-engine
docker compose logs -f node-gateway

# Chạy migration
docker compose exec tax-engine alembic upgrade head

# Rollback migration
docker compose exec tax-engine alembic downgrade -1

# Restart một service
docker compose restart tax-engine

# Vào PostgreSQL
docker compose exec postgres psql -U postgres -d taxassistant

# Test notification endpoint (chỉ trên dev)
curl -X POST http://localhost:8000/notifications/test/{telegram_id}

# Xem scheduler status
curl http://localhost:8000/notifications/scheduler/status
```

---

*CLAUDE.md — TaxAssistant v1.0*
*Cập nhật file này mỗi khi có thay đổi kiến trúc hoặc convention mới.*
*Tài liệu đầy đủ: `docs/strategy/retention-strategy.md`*
