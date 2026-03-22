# Issue #38

[Feature] Redesign homepage/main menu with improved template and time-based greeting

# [Feature] Redesign homepage/main menu with improved template and time-based greeting

**Repository:** phuongphh/TaxAssistant  
**Type:** Feature  
**Priority:** Medium  
**Labels:** enhancement, user-experience, design

## Overview
Redesign the homepage/main menu (triggered by `/start` command) with a comprehensive, visually appealing template that includes time-based greetings, all 8 services, sample questions, 2026 tax updates, and additional SME support content. Fix formatting issues (broken tables, bullet points) and improve overall visual design.

## Current Issues (from screenshot analysis)

### **1. Template Too Short & Sparse**
- Limited content, feels incomplete
- Missing comprehensive service overview

### **2. Formatting Problems**
- **Broken tables:** Inconsistent line breaks, width issues
- **Bullet points (`>`):** Unclean visual appearance
- **Poor visual hierarchy:** No clear sections or separation

### **3. Missing Elements**
- No time-based greeting
- Incomplete service listing
- Limited SME-focused content

## Requirements

### **1. Time-Based Greeting (Vietnam Time)**
Implement dynamic greeting based on Vietnam time (UTC+7):

```typescript
function getTimeBasedGreeting(): string {
  const hour = new Date().getHours(); // Vietnam time (UTC+7)
  
  if (hour >= 5 && hour < 11) return "Chào buổi sáng";
  if (hour >= 11 && hour < 13) return "Chào buổi trưa";
  if (hour >= 13 && hour < 18) return "Chào buổi chiều";
  return "Chào buổi tối";
}
```

**Format:** `[Greeting], [User Name]!`  
**Example:** "Chào buổi sáng, Broadcaster 2P!"

### **2. Comprehensive Template Structure**

#### **Section 1: Header**
```
[Time-Based Greeting], [User Name]! 👋
──────────────────────────────────────
Tôi là Trợ lý Thuế ảo, hỗ trợ bạn tuân thủ thuế tại Việt Nam.
```

#### **Section 2: 9 Core Services (8 from screenshot + Profile)**
List 8 services from screenshot plus "Thông tin của tôi" as item #9 with clean formatting (NO `>` or `•` bullets):

```
📊 **DỊCH VỤ CHÍNH**

1.  Tính thuế (GTGT, TNDN, TNCN, Môn bài)
2.  Hướng dẫn kê khai và quyết toán thuế
3.  Đăng ký mã số thuế
4.  Kiểm tra hóa đơn/chứng từ
5.  Tư vấn thuế với dẫn chứng pháp luật
6.  Tư vấn xử phạt vi phạm thuế
7.  Hỗ trợ hoàn thuế GTGT
8.  Quyết toán thuế năm
9.  Thông tin của tôi 👤
```

#### **Section 3: 2026 Tax Updates**
```
📢 **CẬP NHẬT THUẾ 2026**

•  Giảm trừ gia cảnh mới: 11 triệu/người
•  Miễn thuế TNCN thu nhập dưới 11 triệu/tháng
•  Điều chỉnh thuế suất doanh nghiệp nhỏ
•  Hỗ trợ gia hạn nộp thuế cho SME
```

#### **Section 4: Sample Questions (SME Focused)**
```
💡 **CÂU HỎI MẪU CHO DOANH NGHIỆP SME**

•  "Cách tính thuế GTGT cho hộ kinh doanh?"
•  "Hồ sơ đăng ký mã số thuế cần gì?"
•  "Làm sao giảm thuế TNDN hợp pháp?"
•  "Thời hạn nộp thuế môn bài 2026?"
•  "Chính sách ưu đãi thuế cho startup?"
```

#### **Section 5: SME Support & Compliance**
```
🏢 **HỖ TRỢ DOANH NGHIỆP SME**

🔹 **Tuân thủ thuế:**
   - Hướng dẫn kê khai từ A-Z
   - Cảnh báo thời hạn nộp thuế
   - Cập nhật chính sách mới nhất

🔹 **Tối ưu thuế:**
   - Tư vấn giảm trừ, miễn giảm
   - Kế hoạch thuế hiệu quả
   - Tránh phạt chậm nộp

🔹 **Hỗ trợ 24/7:**
   - Trả lời câu hỏi thuế
   - Hướng dẫn thủ tục
   - Kết nối chuyên gia
```

#### **Section 6: Legal References**
```
⚖️ **CĂN CỨ PHÁP LÝ**
Luật Quản lý thuế 38/2019/QH14
Nghị định 126/2020/NĐ-CP
Thông tư 80/2021/TT-BTC
```

#### **Section 7: Call to Action**
```
──────────────────────────────────────
Bắt đầu bằng cách chọn dịch vụ bên dưới
hoặc gửi câu hỏi trực tiếp cho tôi!
```

### **3. Visual Design Improvements**

#### **Fix Formatting Issues:**
- **NO `>` or `•` bullets** - use clean numbering/indentation
- **Consistent line widths** - prevent broken tables
- **Proper spacing** - between sections
- **Visual separators** ─────────────────────

#### **Typography & Hierarchy:**
- **Bold headers** for sections (`<b>DỊCH VỤ CHÍNH</b>`)
- **Emoji icons** for visual cues (📊, 💡, 🏢, ⚖️)
- **Indentation** for sub-items
- **Clear section breaks**

#### **Character Limit Management:**
- Telegram limit: 4096 characters per message
- Split into logical chunks if needed
- Prioritize essential content

### **4. Buttons (Inline Keyboard)**
Maintain existing buttons with improved context:
```
[[ "Tính thuế", "Tra cứu quy định", "Hướng dẫn kê khai" ]]
```

Consider adding:
```
[[ "Dịch vụ chính", "Cập nhật 2026" ]]
[[ "Hỗ trợ SME", "Câu hỏi mẫu" ]]
```

### **5. Additional SME-Focused Content Suggestions**

#### **A. Compliance Checklist**
```
✅ **CHECKLIST TUÂN THỦ THUẾ SME**
[ ] Đăng ký mã số thuế
[ ] Kê khai thuế định kỳ  
[ ] Nộp thuế đúng hạn
[ ] Lưu trữ hóa đơn 5 năm
[ ] Báo cáo tài chính năm
```

#### **B. Common SME Pain Points**
```
⚠️ **VẤN ĐỀ THƯỜNG GẶP**
•  Quên thời hạn nộp thuế
•  Không biết cách tính thuế GTGT
•  Thiếu hồ sơ kê khai
•  Không cập nhật chính sách mới
```

#### **C. Success Stories/Testimonials**
```
🌟 **DOANH NGHIỆP ĐÃ SỬ DỤNG**
"Tiết kiệm 20% thời gian kê khai thuế"
"Tránh phạt 15 triệu đồng nhờ nhắc hạn nộp"
"Được tư vấn giảm 30% thuế TNDN"
```

## Technical Implementation

### **1. Files to Modify**
- `node-gateway/src/channels/telegram/bot.ts` - `/start` command handler
- `node-gateway/src/services/templateService.ts` - New template service
- `node-gateway/src/utils/formatter.ts` - Formatting utilities

### **2. Template Service Structure**
```typescript
class TemplateService {
  getTimeBasedGreeting(): string;
  getHomepageTemplate(userName: string): string;
  formatServiceList(services: Service[]): string;
  formatTaxUpdates(): string;
  formatSmeSupport(): string;
  formatSampleQuestions(): string;
}
```

### **3. Formatting Rules**
- Use **HTML formatting** (`<b>`, `<i>`) with `parse_mode: 'HTML'`
- **NO markdown syntax** (`**`, `*`) - convert to HTML
- **Line breaks:** `\n` for new lines
- **Sections:** Separated by `\n\n`
- **Indentation:** Spaces for sub-items

### **4. Character Limit Handling**
```typescript
function ensureMessageLength(text: string): string[] {
  if (text.length <= 4096) return [text];
  // Split by sections, prioritize essential content
  return splitBySections(text);
}
```

## Acceptance Criteria
- [ ] `/start` command shows redesigned homepage
- [ ] Time-based greeting (Vietnam time) implemented
- [ ] All 9 services listed clearly (8 from screenshot + "Thông tin của tôi")
- [ ] 2026 tax updates section included
- [ ] Sample questions for SMEs included
- [ ] Additional SME support content added
- [ ] NO `>` or `•` bullets in lists
- [ ] NO broken tables or formatting issues
- [ ] Clean visual hierarchy with sections
- [ ] Character limit respected (≤4096)
- [ ] Buttons maintained/improved
- [ ] Backward compatible - existing functionality preserved

## Implementation Notes

### **Design Principles:**
1. **Professional yet approachable** - SME business focus
2. **Comprehensive but not overwhelming** - balance content
3. **Visually clean** - no formatting artifacts
4. **Action-oriented** - clear next steps

### **Content Strategy:**
- **Essential:** Greeting, services, updates
- **Value-add:** SME support, sample questions
- **Trust-building:** Legal references, success stories
- **Action:** Clear CTAs, buttons

### **Testing:**
- Test at different times (morning, afternoon, evening, night)
- Test on different devices (mobile, desktop)
- Verify character count
- Check formatting on actual Telegram app

## Sample Output

```
Chào buổi sáng, Broadcaster 2P! 👋
──────────────────────────────────────
Tôi là Trợ lý Thuế ảo, hỗ trợ bạn tuân thủ thuế tại Việt Nam.

📊 DỊCH VỤ CHÍNH

1.  Tính thuế (GTGT, TNDN, TNCN, Môn bài)
2.  Hướng dẫn kê khai và quyết toán thuế
3.  Đăng ký mã số thuế
4.  Kiểm tra hóa đơn/chứng từ
5.  Tư vấn thuế với dẫn chứng pháp luật
6.  Tư vấn xử phạt vi phạm thuế
7.  Hỗ trợ hoàn thuế GTGT
8.  Quyết toán thuế năm
9.  Thông tin của tôi 👤

📢 CẬP NHẬT THUẾ 2026

•  Giảm trừ gia cảnh mới: 11 triệu/người
•  Miễn thuế TNCN thu nhập dưới 11 triệu/tháng
•  Điều chỉnh thuế suất doanh nghiệp nhỏ
•  Hỗ trợ gia hạn nộp thuế cho SME

💡 CÂU HỎI MẪU CHO DOANH NGHIỆP SME

•  "Cách tính thuế GTGT cho hộ kinh doanh?"
•  "Hồ sơ đăng ký mã số thuế cần gì?"
•  "Làm sao giảm thuế TNDN hợp pháp?"
•  "Thời hạn nộp thuế môn bài 2026?"
•  "Chính sách ưu đãi thuế cho startup?"

🏢 HỖ TRỢ DOANH NGHIỆP SME

🔹 Tuân thủ thuế:
   - Hướng dẫn kê khai từ A-Z
   - Cảnh báo thời hạn nộp thuế
   - Cập nhật chính sách mới nhất

🔹 Tối ưu thuế:
   - Tư vấn giảm trừ, miễn giảm
   - Kế hoạch thuế hiệu quả
   - Tránh phạt chậm nộp

🔹 Hỗ trợ 24/7:
   - Trả lời câu hỏi thuế
   - Hướng dẫn thủ tục
   - Kết nối chuyên gia

⚖️ CĂN CỨ PHÁP LÝ
Luật Quản lý thuế 38/2019/QH14
Nghị định 126/2020/NĐ-CP
Thông tư 80/2021/TT-BTC

──────────────────────────────────────
Bắt đầu bằng cách chọn dịch vụ bên dưới
hoặc gửi câu hỏi trực tiếp cho tôi!
```

## Related Issues
- This replaces/updates the current `/start` command response
- Should work in conjunction with issue #26 (smart suggestions)
- Formatting improvements relate to issue #35 (markdown formatting)

## Notes
- **First impression matters** - homepage is the user's first experience
- **SME focus** - tailor content for small/medium business needs
- **Professional design** - reflects credibility of tax service
- **Actionable content** - guides users to next steps
