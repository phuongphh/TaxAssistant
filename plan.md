# TaxAssistant v2 - Customer Profile, Long Memory & Support Tracking

## Tổng quan thiết kế

Hệ thống hiện tại dùng Redis session (TTL-based, mất khi hết hạn) để lưu `conversationHistory` ngắn hạn. Phiên bản mới cần:
1. **Customer Profile** - Lưu vĩnh viễn trong PostgreSQL, trở thành "long memory" cho bot
2. **Onboarding Flow** - Khi khách hàng mới lần đầu dùng bot → thu thập thông tin + giới thiệu dịch vụ
3. **Support Case Tracking** - Theo dõi trạng thái hỗ trợ, cho phép tiếp tục công đoạn tiếp theo
4. **Scalability** - Thiết kế từ đầu cho 10K → 100K → triệu khách hàng

---

## 1. Database Models (Python Engine - PostgreSQL)

### 1.1 `customers` - Hồ sơ khách hàng (Long Memory)

```python
# python-engine/app/db/models.py

class Customer(Base):
    __tablename__ = "customers"

    id: UUID          # PK
    channel: str      # "telegram" | "zalo"
    channel_user_id: str  # Telegram user_id hoặc Zalo user_id

    # Thông tin kinh doanh (thu thập qua onboarding)
    customer_type: str     # "sme" | "household" | "individual"
    business_name: str | None      # Tên doanh nghiệp / hộ KD
    tax_code: str | None           # Mã số thuế (nếu đã có)
    industry: str | None           # Ngành nghề kinh doanh
    province: str | None           # Tỉnh/thành phố
    annual_revenue_range: str | None  # "under_100m" | "100m_1b" | "1b_10b" | "over_10b"
    employee_count_range: str | None  # "1_5" | "6_20" | "21_50" | "50_plus"

    # Trạng thái onboarding
    onboarding_step: str  # "new" | "collecting_type" | "collecting_info" | "completed"

    # Long memory - JSONB để linh hoạt mở rộng
    preferences: JSONB    # { "language": "vi", "notification_time": "09:00", ... }
    tax_profile: JSONB    # { "vat_method": "deduction", "fiscal_year_end": "12/31",
                          #   "registered_taxes": ["vat","cit","pit","license"], ... }
    notes: JSONB          # Bot ghi nhận điểm quan trọng từ các cuộc hội thoại
                          # [{"date": "...", "note": "KH cần hoàn thuế GTGT Q2"}, ...]

    created_at: datetime
    updated_at: datetime
    last_active_at: datetime

    # Index composite: (channel, channel_user_id) UNIQUE
```

**Tại sao dùng JSONB cho `preferences`, `tax_profile`, `notes`?**
- Linh hoạt mở rộng không cần migration
- PostgreSQL JSONB có GIN index, query nhanh
- Phù hợp với dữ liệu bán cấu trúc (semi-structured)
- Scale tốt hơn so với thêm nhiều cột

### 1.2 `support_cases` - Theo dõi tiến trình hỗ trợ

```python
class SupportCase(Base):
    __tablename__ = "support_cases"

    id: UUID                # PK
    customer_id: UUID       # FK → customers.id

    # Loại dịch vụ (map với service menu)
    service_type: str       # "tax_registration" | "tax_declaration" | "tax_calculation"
                            # | "tax_consultation" | "invoice_check" | "tax_refund"
                            # | "penalty_consultation" | "annual_settlement"

    title: str              # VD: "Đăng ký thuế lần đầu - SME"

    # Trạng thái workflow
    status: str             # "open" | "in_progress" | "waiting_customer" | "completed" | "cancelled"
    current_step: str       # VD: "step_1_collect_docs" | "step_2_review" | "step_3_submit"

    # Dữ liệu tiến trình - JSONB
    steps_data: JSONB       # {
                            #   "step_1_collect_docs": { "status": "completed", "data": {...} },
                            #   "step_2_review": { "status": "in_progress", "data": {...} },
                            # }

    context: JSONB          # Thông tin bổ sung: { "tax_type": "vat", "period": "Q1/2026", ... }

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    # Index: customer_id, status, service_type
```

### 1.3 `conversation_summaries` - Tóm tắt hội thoại (thay vì lưu toàn bộ)

```python
class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: UUID
    customer_id: UUID       # FK → customers.id
    support_case_id: UUID | None  # FK → support_cases.id (nếu thuộc case)

    session_date: date      # Ngày của phiên hội thoại
    summary: str            # Tóm tắt nội dung (do LLM tạo)
    key_topics: JSONB       # ["vat_calculation", "deadline_q1"]
    action_items: JSONB     # ["Cần nộp tờ khai mẫu 01/GTGT trước 30/4"]

    created_at: datetime
```

**Scalability note**: Thay vì lưu toàn bộ tin nhắn (explodes at scale), ta lưu **tóm tắt** hội thoại. Mỗi phiên kết thúc → LLM tóm tắt → lưu summary. Khi phục vụ lại → load summaries gần nhất làm context.

---

## 2. Onboarding Flow - Giới thiệu dịch vụ & Thu thập thông tin

### 2.1 Flow khi khách hàng mới lần đầu

```
Khách hàng gửi tin nhắn đầu tiên
    ↓
Gateway: resolveSession → check Customer in DB
    ↓ (không tìm thấy)
Tạo Customer mới (onboarding_step = "new")
    ↓
Bot gửi WELCOME MESSAGE + SERVICE MENU:
────────────────────────────────────────
"Xin chào! Tôi là Trợ lý Thuế - hỗ trợ tư vấn thuế cho doanh nghiệp,
hộ kinh doanh và cá nhân tại Việt Nam.

🔹 Dịch vụ của chúng tôi:
1. 📊 Tính thuế (GTGT, TNDN, TNCN, Môn bài)
2. 📋 Hướng dẫn kê khai & quyết toán thuế
3. 📝 Đăng ký mã số thuế
4. 🔍 Tra cứu quy định & văn bản pháp luật
5. 📄 Kiểm tra hóa đơn, chứng từ
6. ⚠️ Tư vấn xử phạt & vi phạm thuế
7. 💰 Hỗ trợ hoàn thuế GTGT

Để phục vụ bạn tốt hơn, bạn thuộc nhóm nào?
"
Quick Replies: [SME] [Hộ kinh doanh] [Cá nhân KD]
────────────────────────────────────────
    ↓
Khách chọn loại → onboarding_step = "collecting_info"
    ↓
Bot hỏi tiếp (tùy loại):
- SME: "Tên doanh nghiệp? Đã có MST chưa? Ngành nghề?"
- Household: "Bạn kinh doanh ngành gì? Doanh thu ước tính?"
- Individual: "Nguồn thu nhập chính? Có người phụ thuộc?"
    ↓
Thu thập xong → onboarding_step = "completed"
    ↓
Bot: "Cảm ơn! Tôi đã ghi nhận thông tin. Bây giờ bạn muốn
tôi hỗ trợ dịch vụ nào?" + Service Menu
```

### 2.2 Flow khi khách hàng quay lại

```
Khách hàng gửi tin nhắn
    ↓
Gateway: resolveSession → check Customer in DB
    ↓ (tìm thấy customer + load profile)
Inject customer profile vào TaxRequest context
    ↓
Tax Engine nhận được context đầy đủ:
- customer_type, business_name, tax_code, industry
- tax_profile (phương pháp VAT, thuế đã đăng ký)
- notes (điểm quan trọng từ lần trước)
- recent conversation summaries
- open support cases
    ↓
Bot phục vụ có ngữ cảnh:
"Chào anh/chị [business_name]! Lần trước chúng ta đang hỗ trợ
[case: Kê khai thuế GTGT Q1/2026 - bước 2]. Bạn muốn tiếp tục
hay cần hỗ trợ khác?"
```

---

## 3. Service Menu & Support Case Workflow

### 3.1 Danh sách dịch vụ (Service Types)

| Service Type | Tên hiển thị | Steps |
|---|---|---|
| `tax_calculation` | Tính thuế | Xác định loại thuế → Thu thập số liệu → Tính toán → Kết quả |
| `tax_declaration` | Kê khai thuế | Xác định tờ khai → Hướng dẫn điền → Review → Nộp |
| `tax_registration` | Đăng ký MST | Chuẩn bị hồ sơ → Hướng dẫn nộp → Theo dõi |
| `tax_consultation` | Tư vấn quy định | Tiếp nhận câu hỏi → Tra cứu → Trả lời |
| `invoice_check` | Kiểm tra hóa đơn | Upload → OCR → Xác minh → Kết quả |
| `tax_refund` | Hoàn thuế GTGT | Xác định điều kiện → Hồ sơ → Hướng dẫn nộp |
| `penalty_consultation` | Tư vấn xử phạt | Mô tả tình huống → Tra cứu → Tư vấn |
| `annual_settlement` | Quyết toán năm | Xác định nghĩa vụ → Checklist → Hướng dẫn |

### 3.2 Support Case Lifecycle

```
[open] → Bot tạo case khi KH bắt đầu dịch vụ
   ↓
[in_progress] → Bot đang hướng dẫn qua các bước
   ↓
[waiting_customer] → Bot chờ KH cung cấp thông tin / upload tài liệu
   ↓ (KH quay lại)
[in_progress] → Tiếp tục từ current_step
   ↓
[completed] → Hoàn thành dịch vụ
```

---

## 4. Thay đổi cần thực hiện (Chi tiết code changes)

### 4.1 Python Engine Changes

**File mới:**
- `python-engine/app/db/customer_repository.py` - CRUD cho customers
- `python-engine/app/db/case_repository.py` - CRUD cho support_cases
- `python-engine/app/db/summary_repository.py` - CRUD cho conversation_summaries
- `python-engine/app/core/onboarding.py` - Onboarding flow logic
- `python-engine/app/core/case_manager.py` - Support case lifecycle management
- `python-engine/app/core/memory.py` - Long memory assembly (profile + summaries + cases → LLM context)

**File sửa:**
- `python-engine/app/db/models.py` - Thêm 3 model mới
- `python-engine/app/core/tax_engine.py` - Integrate onboarding check + case routing + memory context
- `python-engine/app/grpc_server.py` - Pass customer profile qua gRPC handler
- `python-engine/app/core/intent_classifier.py` - Thêm intents: `ONBOARDING_RESPONSE`, `SERVICE_SELECT`, `CASE_CONTINUE`

### 4.2 Proto Changes

**File sửa:** `proto/tax_service.proto`

```protobuf
// Thêm CustomerProfile vào SessionContext
message CustomerProfile {
  string customer_id = 1;
  string business_name = 2;
  string tax_code = 3;
  string industry = 4;
  string province = 5;
  string annual_revenue_range = 6;
  string onboarding_step = 7;
  map<string, string> tax_profile = 8;
  repeated string recent_notes = 9;
}

// Thêm ActiveCase
message ActiveCase {
  string case_id = 1;
  string service_type = 2;
  string title = 3;
  string status = 4;
  string current_step = 5;
}

// Mở rộng TaxRequest
message TaxRequest {
  // ... existing fields ...
  CustomerProfile customer_profile = 7;     // NEW
  repeated ActiveCase active_cases = 8;      // NEW
  repeated string conversation_summaries = 9; // NEW
}

// Thêm RPC mới
service TaxEngine {
  // ... existing RPCs ...
  rpc GetOrCreateCustomer(CustomerLookup) returns (CustomerProfile);
  rpc UpdateCustomerProfile(CustomerProfileUpdate) returns (CustomerProfile);
  rpc CreateSupportCase(CreateCaseRequest) returns (ActiveCase);
  rpc UpdateSupportCase(UpdateCaseRequest) returns (ActiveCase);
  rpc GetActiveCases(CustomerLookup) returns (ActiveCasesResponse);
}
```

### 4.3 Node.js Gateway Changes

**File sửa:**
- `node-gateway/src/session/store.ts` - Thêm `customerId` vào `SessionData`, cache customer profile trong Redis
- `node-gateway/src/router/messageRouter.ts` - Gọi `GetOrCreateCustomer` RPC khi resolve session, inject profile vào TaxRequest
- `node-gateway/src/grpc/client.ts` - Thêm client methods cho new RPCs

**Logic mới trong `messageRouter.ts`:**

```typescript
// Trong handleMessage():
// 1. Resolve session (existing)
const session = await this.sessionManager.resolveSession(userId, channel);

// 2. NEW: Resolve/create customer profile
let customerProfile = await this.getCustomerProfile(session);
if (!customerProfile) {
  customerProfile = await this.taxEngine.getOrCreateCustomer(channel, userId);
  await this.cacheCustomerProfile(session.sessionId, customerProfile);
}

// 3. NEW: Get active cases
const activeCases = await this.taxEngine.getActiveCases(customerProfile.customerId);

// 4. Route to Tax Engine with full context
const engineResponse = await this.taxEngine.processMessage(
  requestId, message, session, customerProfile, activeCases
);
```

### 4.4 Alembic Migration

```
python-engine/alembic/versions/001_add_customers_table.py
python-engine/alembic/versions/002_add_support_cases_table.py
python-engine/alembic/versions/003_add_conversation_summaries_table.py
```

---

## 5. Scalability Design (10K → 100K → Triệu)

### Phase 1: 10K khách hàng (Hiện tại + changes trên)

**Đủ với:**
- Single PostgreSQL 16 instance (customers, cases, summaries)
- Redis cho session cache + customer profile cache (TTL 1h)
- Connection pooling: asyncpg pool size 20-50

**Indexes cần thiết:**
```sql
CREATE UNIQUE INDEX idx_customers_channel_user ON customers(channel, channel_user_id);
CREATE INDEX idx_customers_type ON customers(customer_type);
CREATE INDEX idx_support_cases_customer ON support_cases(customer_id);
CREATE INDEX idx_support_cases_status ON support_cases(status) WHERE status != 'completed';
CREATE INDEX idx_summaries_customer ON conversation_summaries(customer_id);
CREATE INDEX idx_summaries_date ON conversation_summaries(session_date DESC);
```

**Estimated storage:**
- 10K customers × ~2KB/row = ~20MB
- 50K cases × ~1KB/row = ~50MB
- 100K summaries × ~500B/row = ~50MB
- Total: < 200MB → fits in RAM easily

### Phase 2: 100K khách hàng

**Thêm:**
- PostgreSQL read replicas (1-2) cho query load
- Redis Cluster (3 nodes) cho session + cache
- Customer profile cache tại Gateway (in-memory LRU, 10K entries)
- Background job queue (Celery/Redis) cho conversation summarization
- Partition `conversation_summaries` by month
- Partition `support_cases` by status (active vs completed)

### Phase 3: Triệu khách hàng

**Thêm:**
- PostgreSQL horizontal sharding by customer_id (Citus hoặc manual)
- Dedicated Redis cluster cho sessions vs cache
- CDN cho static responses / service menus
- Read-through cache layer (Gateway ↔ Redis ↔ PostgreSQL)
- Event-driven architecture: Customer events → Kafka/NATS → processors
- Conversation summarization: async pipeline (không block response)
- Rate limiting per customer tier
- Database connection pooling: PgBouncer

---

## 6. Thứ tự triển khai (Implementation Order)

### Step 1: Database Models + Migration
- Thêm `Customer`, `SupportCase`, `ConversationSummary` models
- Tạo Alembic migrations
- Thêm indexes

### Step 2: Customer Repository + Memory Module
- CRUD operations cho customers
- Memory assembly: load profile + recent summaries → context string cho LLM

### Step 3: Onboarding Flow
- Detect new customer → trigger onboarding
- Service menu display
- Collect customer info step by step
- Store in Customer table

### Step 4: Proto + gRPC Changes
- Extend proto với CustomerProfile, ActiveCase
- Add new RPCs
- Update gRPC server + client

### Step 5: Gateway Integration
- Customer profile resolution in message router
- Cache customer profile in Redis
- Pass full context to Tax Engine

### Step 6: Support Case Manager
- Case creation when customer selects service
- Step-by-step workflow tracking
- Resume from last step

### Step 7: Tax Engine Integration
- Inject customer memory into LLM prompts
- Personalized responses based on profile
- Case-aware routing

### Step 8: Conversation Summarization
- End-of-session summary generation (LLM)
- Store summaries, link to cases
- Load recent summaries as context

### Step 9: Tests
- Unit tests cho Customer, Case, Summary repositories
- Onboarding flow tests
- Case lifecycle tests
- Memory assembly tests
- Integration tests
