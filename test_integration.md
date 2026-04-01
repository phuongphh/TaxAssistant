# Integration Test for Issue #26 - Smart Context-Aware Suggestions

## Test Scenario 1: Updated Service Menu
**Action:** User sends `/start` command
**Expected Output:**
```
Xin chào! Tôi là "Bé Thuế" - Trợ lý Thuế ảo. 🇻🇳

Tôi có thể hỗ trợ bạn:

1. **Tính thuế (GTGT, TNDN, TNCN, Môn bài)**
   Ví dụ: "Tính thuế TNCN lương 20 triệu"

2. **Hướng dẫn kê khai và nộp thuế**
   Ví dụ: "Cách kê khai thuế GTGT tháng 3?"

3. **Thời hạn nộp thuế**
   Ví dụ: "Hạn nộp thuế môn bài 2025 là khi nào?"

4. **Đăng ký mã số thuế**
   Ví dụ: "Thủ tục đăng ký MST cá nhân"

5. **Dịch vụ tư vấn về thuế với các dẫn chứng từ văn bản pháp luật**
   Ví dụ: "Tra cứu thông tư 78/2014/TT-BTC"

Hãy gửi câu hỏi của bạn để tôi hỗ trợ!
```

## Test Scenario 2: Tax Calculation with Suggestions
**Action:** User asks "Tính thuế TNCN lương 20 triệu"
**Expected Output:** Tax calculation result followed by:
```
Bạn muốn làm gì tiếp theo?
1. Lưu kết quả vào hồ sơ kê khai thuế
2. Đặt lệnh nhắc thời hạn nộp thuế
3. Tính loại thuế khác
```

## Test Scenario 3: User Chooses Suggestion
**Action:** User sends "1" (chooses first suggestion)
**Expected Output:** "Tôi đã lưu kết quả tính thuế vào hồ sơ kê khai của bạn. Bạn có thể xem lại trong phần lịch sử." followed by new suggestions.

## Test Scenario 4: User Asks New Question (Natural Flow)
**Action:** After seeing suggestions, user asks "Cách nộp thuế TNCN?"
**Expected Output:** Explanation of payment process with new context-aware suggestions:
```
Bạn muốn làm gì tiếp theo?
1. Xem mẫu tờ khai
2. Tính phí chậm nộp
3. Quay lại tính thuế
```

## Test Scenario 5: Deadline Information
**Action:** User asks "Hạn nộp thuế môn bài 2025?"
**Expected Output:** Deadline information followed by:
```
Bạn muốn làm gì tiếp theo?
1. Xem chi tiết cách nộp thuế
2. Tính số tiền thuế phải nộp
3. Quay lại menu chính
```

## Test Scenario 6: Legal Document Lookup
**Action:** User asks "Tra cứu thông tư 78/2014"
**Expected Output:** Legal document information followed by:
```
Bạn muốn làm gì tiếp theo?
1. Tìm văn bản pháp luật khác
2. Áp dụng vào trường hợp cụ thể
3. Tư vấn với chuyên gia
```

## Implementation Verification Checklist:

### ✅ Updated Service Menu
- [x] `/start` command shows updated service menu order
- [x] Service #3 renamed and moved to position #5
- [x] Example text preserved below each service item

### ✅ Smart Context-Aware Suggestions
- [x] After each bot response, 3 context-specific suggestions appear
- [x] Suggestions are numbered text (1, 2, 3), not buttons
- [x] Suggestions are context-aware (tax-calculation, deadline-info, legal-doc, etc.)

### ✅ User Flow Requirements
- [x] User can choose suggestion (1, 2, 3) and bot processes it
- [x] User can ask new question and bot processes it (suggestions ignored)
- [x] User can use commands (/help, etc.) and bot processes them
- [x] Conversation context is maintained across messages
- [x] Suggestions update when conversation topic changes
- [x] No breaking changes to existing functionality

### ✅ Technical Implementation
- [x] SessionData extended with context and suggestions support
- [x] Suggestion generator module created
- [x] Message router updated to handle suggestion choices
- [x] Context detection and suggestion generation logic
- [x] Unit tests created for suggestion generator

## Files Modified/Created:
1. `node-gateway/src/channels/telegram/bot.ts` - Updated /start command
2. `node-gateway/src/session/store.ts` - Extended SessionData interface
3. `node-gateway/src/services/suggestionGenerator.ts` - New module
4. `node-gateway/src/router/messageRouter.ts` - Added suggestion handling
5. `node-gateway/src/services/suggestionGenerator.test.ts` - Unit tests
6. `TaxAssistant/test_integration.md` - This test document