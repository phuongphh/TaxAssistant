# Issue #26

[Feature] Enhance TaxAssistant with smart context-aware suggestions and updated service menu

# [Feature] Enhance TaxAssistant with smart context-aware suggestions and updated service menu

**Repository:** phuongphh/TaxAssistant  
**Type:** Feature  
**Priority:** Medium  
**Labels:** enhancement, user-experience, chatbot

## Overview
Enhance the Bé Thuế Telegram bot with:
1. **Reordered service menu** - move legal document lookup to bottom with updated name
2. **Smart context-aware suggestions** - add 3 optional suggestions after each bot response
3. **Natural conversation flow** - suggestions are optional, users can ask new questions anytime

## Current Behavior (from screenshot)
**Service Menu (/start command):**
1. Tính thuế (GTGT, TNDN, TNCN, Môn bài)
2. Hướng dẫn kê khai và nộp thuế
3. Tra cứu văn bản pháp luật về thuế
4. Thời hạn nộp thuế
5. Đăng ký mã số thuế

**Quick-reply buttons:** Tính thuế, Kê khai thuế, Hạn nộp thuế, Đăng ký MST

## Requirements

### 1. Updated Service Menu
**New order for  command:**
1. Tính thuế (GTGT, TNDN, TNCN, Môn bài)
2. Hướng dẫn kê khai và nộp thuế  
3. Thời hạn nộp thuế
4. Đăng ký mã số thuế
5. **Dịch vụ tư vấn về thuế với các dẫn chứng từ văn bản pháp luật** (renamed from #3)

**Keep the example text below each service item unchanged.**

### 2. Smart Context-Aware Suggestions
After each bot response, add **3 relevant text-based suggestions**.

**Format:** Numbered text options (not buttons)


**Examples by context:**

#### After Tax Calculation:


#### After Deadline Information:


#### After Legal Document Lookup:


### 3. Critical User Flow Requirements
**Suggestions are OPTIONAL, not mandatory:**
- ✅ User can **choose a number** (1, 2, 3) → bot processes that option
- ✅ User can **ask a new question** → bot processes the new query
- ✅ User can **use a command** (/start, /help) → bot processes the command
- ✅ User can **ignore suggestions entirely** → conversation continues naturally

**Example flow:**


### 4. Technical Implementation Requirements

#### State Management:
- Track **current conversation context** (tax calculation, deadline, legal, etc.)
- Store **pending suggestions** with their action mappings
- Maintain **context across multiple messages**

#### Suggestion Generation:
- **Context-aware:** Suggestions based on current topic
- **Relevant:** 3 most likely next actions for the context
- **Useful:** Actually helpful, not random options

#### User Input Processing:
- Detect if message is **suggestion choice** (1, 2, 3)
- Detect if message is **new query** (text, command)
- **Priority:** New query > Suggestion choice

#### Fallback Handling:
- If user ignores suggestions → continue conversation
- If context changes → update suggestions
- If no relevant suggestions → show generic options

### 5. Design Constraints
- **No buttons:** Use text-based numbered options only
- **Non-intrusive:** Suggestions don't block natural flow
- **Context-persistent:** Remember topic across turns
- **User-friendly:** Clear, helpful, Vietnamese language

## Acceptance Criteria
- [ ]  command shows updated service menu order
- [ ] Service #3 renamed and moved to position #5
- [ ] After each bot response, 3 context-specific suggestions appear
- [ ] Suggestions are numbered text (1, 2, 3), not buttons
- [ ] User can choose suggestion (1, 2, 3) and bot processes it
- [ ] User can ask new question and bot processes it (suggestions ignored)
- [ ] User can use commands (/help, etc.) and bot processes them
- [ ] Conversation context is maintained across messages
- [ ] Suggestions update when conversation topic changes
- [ ] No breaking changes to existing functionality

## Claude Code Prompt


## Notes
- This is a **user experience enhancement**, not core functionality change
- **Backward compatibility** is important - don't break existing flows
- **Performance** should not be impacted
- **Testing** is critical for the suggestion logic

## Related Files
-  - Main bot implementation
-  - Message types
-  - Message routing
