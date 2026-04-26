# Issue #4

[Feature] Onboarding và quản lý khách hàng theo user_id và user_name

---
name: Tax Assistant Feature
about: Feature for Tax Assistant with compliance requirement
title: [FEATURE] 
labels: feature
assignees:
---

## 1. Business Context
- Target user: all (SME / Hộ kinh doanh / Cá thể)

## 2. Problem Statement
Khi khách hàng chat lần đầu tiên sang bot telegram, tôi muốn cần phải lưu lại khách hàng này ở cơ sở dữ liệu và sử dụng như context cho lần chat tiếp theo của khách. Như vậy, thông tin như user_id, user_name của khách cần phải được lưu vào bộ nhớ lâu dài. Khi nhận được câu trả lời của khách hàng về các thông tin khác như loại kinh doanh, hay mô tả kinh doanh của khách hàng (ví dụ như: tôi là chủ cửa hàng hoa) thì cần lưu về trong bộ nhớ dài hạn. Những lần sau cần phải chào khách hàng bằng user_name.

## 3. Acceptance Criteria
- Bot lưu thông tin user khi nhận message đầu tiên từ Telegram (user_id, username, first_name, last_name).
- Hệ thống kiểm tra user_id để tránh tạo duplicate user.
- Bot lưu thông tin business khi user cung cấp trong hội thoại.
- Dữ liệu user và business được lưu trong long-term storage.
- Khi user chat lại, bot load user context từ database.
- Bot sử dụng user_name để chào user trong response.
- Business context được đưa vào prompt khi gọi LLM.

## 4. Technical Constraints
- user_id từ Telegram phải được dùng làm unique identifier.
- User data phải được lưu trong persistent storage (không dùng in-memory).
- Message processing phải idempotent để tránh duplicate user records.
- Business information extraction không được block message response.
- Context gửi vào LLM phải giới hạn ở structured user profile.
- User business profile phải hỗ trợ update.
- Bot phải xử lý trường hợp thiếu username hoặc last_name.
- Memory system phải hỗ trợ multi-agent access.

## 5. Test Requirements
- Verify user record is created when receiving the first Telegram message.
- Verify duplicate user records are not created.
- Verify business information is extracted and stored correctly.
- Verify stored context is used in bot responses.
- Verify system handles missing Telegram fields (username, last_name).
- Verify message retry does not create duplicate data.
- Verify user data persists after bot restart.

