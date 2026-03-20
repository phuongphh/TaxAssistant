# Issue #30

[Feature] User profile management - 'Thông tin của tôi' với dynamic business type fields

# [Feature] User profile management - "Thông tin của tôi" với dynamic business type fields

**Repository:** phuongphh/TaxAssistant  
**Type:** Feature  
**Priority:** Medium  
**Labels:** enhancement, user-profile, database

## Overview
Implement comprehensive user profile management system for TaxAssistant bot where users can view and edit their information through natural language. Profile fields are dynamic based on business type (doanh nghiệp, hộ kinh doanh, cá thể).

## Business Context
TaxAssistant needs to collect different information based on user's business type for accurate tax consultation and calculation. Users should be able to manage their profile seamlessly through conversation.

## Requirements

### 1. Dynamic Profile Fields by Business Type

#### **Cá thể (Individual)**
- 👤 Tên đầy đủ
- 📧 Email
- 📞 Số điện thoại
- 🏠 Địa chỉ
- 👫 Tình trạng hôn nhân
- 💼 Nghề nghiệp
- 📊 Thu nhập ước tính

#### **Hộ kinh doanh (Household Business)**
- 🏢 Tên cửa hàng/cơ sở
- 👤 Chủ hộ kinh doanh
- 📍 Địa chỉ kinh doanh
- 🏭 Ngành nghề (dịch vụ giặt là, ăn uống, bán lẻ, etc.)
- 📅 Năm thành lập
- 👥 Số nhân viên
- 💰 Doanh thu ước tính
- 📊 Loại hình hộ kinh doanh

#### **Doanh nghiệp (Enterprise)**
- 🏢 Tên doanh nghiệp
- 🔢 Mã số thuế
- 📍 Địa chỉ trụ sở
- 🏭 Ngành nghề kinh doanh
- 📅 Năm thành lập
- 👥 Quy mô nhân viên
- 💰 Vốn điều lệ
- 📊 Loại hình doanh nghiệp (TNHH, Cổ phần, etc.)

### 2. Data Sources

#### **Automatically Collected (from Telegram)**
- `telegramUserId`: User ID từ Telegram
- `telegramUsername`: Username (@username)
- `firstName`: Tên từ Telegram profile
- `lastName`: Họ từ Telegram profile
- `registrationDate`: Ngày đầu tiên chat với bot

#### **User Input (via Natural Language)**
- Business type (doanh nghiệp, hộ kinh doanh, cá thể)
- Business name/Store name
- Industry/ngành nghề
- Contact information
- Address details
- Revenue/income estimates

### 3. User Interface & Access Points

#### **/start Menu Integration**
Add as item #6 in the main menu:
```
6. Thông tin của tôi 👤
```

#### **Dedicated Command**
- `/profile` - View current profile
- `/profile edit` - Start edit mode

#### **Main Interface Option**
Persistent option in conversation suggestions:
```
Bạn muốn làm gì tiếp theo?
1. Tính thuế
2. Xem hạn nộp
3. Thông tin của tôi 👤
```

### 4. Profile View Format

```
THÔNG TIN CỦA TÔI 👤
────────────────────
🏢 Loại hình: Hộ kinh doanh
📛 Tên cửa hàng: Amie
👤 Chủ hộ: Nguyễn Văn A
🏭 Ngành nghề: Dịch vụ giặt là
📍 Địa chỉ: 123 Đường ABC, Quận 1, HCM
📞 Điện thoại: 0912345678
📧 Email: amie@example.com
📅 Thành lập: 2023
👥 Nhân viên: 3 người
💰 Doanh thu ước tính: 300 triệu/năm
────────────────────
Để sửa thông tin, hãy nói: "Đổi [field] thành [value]"
Ví dụ: "Đổi tên cửa hàng thành Amie Pro"
```

### 5. Natural Language Edit System

#### **Edit Patterns Recognition**
- "Đổi [field] thành [value]"
  - "Đổi tên cửa hàng thành Amie Pro"
  - "Đổi số điện thoại thành 0987654321"
  - "Đổi ngành nghề thành dịch vụ spa"

- "Cập nhật [field] là [value]"
  - "Cập nhật địa chỉ là 456 Đường XYZ"
  - "Cập nhật email là new@email.com"

- "Sửa [field] thành [value]"
  - "Sửa tên tôi thành Phạm Văn B"
  - "Sửa doanh thu thành 500 triệu"

#### **Business Type Change**
- "Tôi là doanh nghiệp"
- "Chuyển thành hộ kinh doanh"
- "Đổi loại hình thành cá thể"

Bot should:
1. Confirm business type change
2. Ask for required fields của business type mới
3. Migrate compatible data
4. Clear incompatible fields

### 6. User Flow Examples

#### **Initial Profile Setup**
```
User: Tôi là hộ kinh doanh, ngành dịch vụ giặt là, cửa hàng tên là Amie
Bot: Đã ghi nhận bạn là hộ kinh doanh! 
     Tên cửa hàng: Amie
     Ngành nghề: Dịch vụ giặt là
     
     Cần thêm thông tin:
     1. Tên chủ hộ?
     2. Địa chỉ kinh doanh?
     3. Số điện thoại?
     
     Hãy cung cấp thông tin hoặc nói "bỏ qua".
```

#### **Profile View**
```
User: /profile
Bot: [Hiển thị profile format như trên]
     Bạn muốn làm gì?
     1. Sửa thông tin
     2. Đổi loại hình
     3. Quay lại menu
```

#### **Natural Language Edit**
```
User: Đổi tên cửa hàng thành Amie Pro
Bot: ✅ Đã cập nhật tên cửa hàng thành "Amie Pro"

User: Cập nhật doanh thu là 400 triệu/năm
Bot: ✅ Đã cập nhật doanh thu ước tính: 400 triệu/năm
```

### 7. Technical Implementation Requirements

#### **Database Schema Extension**
Extend `customers` table or create `user_profiles` table with:
- `user_id` (foreign key to customers)
- `business_type` (individual, household, enterprise)
- `profile_data` (JSONB field với dynamic fields)
- `metadata` (creation_date, last_updated, etc.)

#### **Natural Language Processing**
- Intent recognition for profile edits
- Entity extraction for field-value pairs
- Field mapping (synonyms: "tên cửa hàng" = "store name" = "business name")
- Validation rules per field type

#### **State Management**
- Track profile completion status
- Remember which fields are being collected
- Handle multi-turn profile setup

#### **Business Logic**
- Field requirements per business type
- Data validation (email format, phone number, etc.)
- Business type migration logic
- Default values và auto-population

### 8. Acceptance Criteria

- [ ] `/start` menu includes "Thông tin của tôi 👤" as item #6
- [ ] `/profile` command shows user's profile information
- [ ] Profile fields dynamic based on business type
- [ ] Automatically collects Telegram user data
- [ ] Users can edit via natural language ("Đổi [field] thành [value]")
- [ ] Business type change supported với data migration
- [ ] Profile data persisted in database
- [ ] Multi-language field recognition (synonyms support)
- [ ] Input validation for different field types
- [ ] Profile completion tracking
- [ ] Backward compatible - không break existing functionality

### 9. Implementation Notes

#### **Database**
- Extend existing `customers` table hoặc create `user_profiles`
- JSONB field cho flexible schema per business type
- Indexes for efficient querying

#### **Natural Language Processing**
- Enhance existing intent classifier
- Add profile-related intents và entities
- Field mapping dictionary

#### **User Experience**
- Progressive profile collection (không bắt buộc tất cả fields ngay)
- Clear feedback on changes
- Help text for available fields

#### **Files to Modify**
- `node-gateway/src/channels/telegram/bot.ts` - Add /profile command
- `node-gateway/src/session/store.ts` - Extend session data
- `node-gateway/src/router/messageRouter.ts` - Add profile intent handling
- Database migration for profile fields
- `node-gateway/src/services/profileManager.ts` - New service

## Notes
- This feature enables **personalized tax consultation** based on user's actual business context
- **Natural language interface** makes profile management intuitive
- **Dynamic fields** ensure relevance to user's business type
- **Data quality** improves tax calculation accuracy
- **User engagement** increases with personalized experience
