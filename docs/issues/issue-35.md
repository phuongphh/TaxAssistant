# Issue #35

[Bug] Telegram bot displays raw markdown syntax instead of formatted text

# [Bug] Telegram bot displays raw markdown syntax instead of formatted text

**Repository:** phuongphh/TaxAssistant  
**Type:** Bug  
**Priority:** High  
**Labels:** bug, user-experience, telegram

## Overview
The "Bé Thuế" Telegram bot displays raw markdown syntax (`**bold**`, `*italic*`, `` `code` ``) instead of properly formatted text. This creates a poor user experience where users see formatting codes instead of clean, readable text.

## Current Behavior
When the bot sends responses containing markdown syntax, users see the raw syntax instead of formatted text:

**What users see:**
```
**Cách tính thuế TNCN:**
1. **Bước 1:** Tính thu nhập chịu thuế
2. **Bước 2:** Áp dụng biểu thuế lũy tiến
*Chú ý:* Giảm trừ gia cảnh 11 triệu/người
```

**What users should see:**
```
Cách tính thuế TNCN:
1. Bước 1: Tính thu nhập chịu thuế
2. Bước 2: Áp dụng biểu thuế lũy tiến
Chú ý: Giảm trừ gia cảnh 11 triệu/người
```

## Root Cause Analysis

### 1. **Parse Mode Mismatch**
The Telegram bot is configured with `parse_mode: 'HTML'` (see `bot.ts` line 262), but the LLM (Claude/GPT) generates responses with **Markdown syntax**.

**Code location:** `node-gateway/src/channels/telegram/bot.ts`
```typescript
await this.bot.telegram.sendMessage(telegramChatId, chunks[i], {
  parse_mode: 'HTML',  // ← EXPECTS HTML, GETS MARKDOWN
  ...replyMarkup,
});
```

### 2. **LLM Response Format**
The tax engine/LLM likely returns markdown-formatted text for better readability in other contexts, but this format doesn't work with Telegram's HTML parse mode.

### 3. **Fallback Logic Issue**
There is a fallback to plain text when HTML parsing fails, but this only triggers on specific HTML parsing errors, not markdown syntax issues.

## Technical Details

### Telegram Formatting Support
Telegram bots support three formatting modes:
1. **HTML:** `<b>bold</b>`, `<i>italic</i>`, `<code>code</code>`
2. **MarkdownV2:** `*bold*`, `_italic_`, `` `code` ``
3. **Plain text:** No formatting

### Current Implementation Flow
```
LLM Response → Markdown text → parse_mode: 'HTML' → Raw syntax displayed
```

### Desired Implementation Flow
```
LLM Response → Markdown text → Convert to HTML → parse_mode: 'HTML' → Formatted text
```
OR
```
LLM Response → Markdown text → parse_mode: 'MarkdownV2' → Formatted text
```

## Requirements

### 1. **Fix Formatting Display**
- Remove raw markdown syntax from user-facing messages
- Ensure all text is properly formatted or plain

### 2. **Solution: Markdown-to-HTML Conversion**
Implement a utility function to convert markdown syntax to HTML tags before sending messages to Telegram.

```typescript
function markdownToHtml(text: string): string {
  // Convert **bold** → <b>bold</b>
  // Convert *italic* → <i>italic</i>
  // Convert `code` → <code>code</code>
  // Convert # Header → <b>Header</b>
  // Convert - list items → • list items
  // Convert 1. numbered items → 1. numbered items
}
```

**Why this solution:**
- Maintains existing `parse_mode: 'HTML'` configuration
- Preserves formatting (bold, italic) for better readability
- Handles LLM's natural markdown output format
- Can be implemented as a preprocessing step without major changes
- Keeps the bot responses visually appealing while removing raw syntax

### 3. **Implementation Requirements**

#### **Markdown-to-HTML Conversion:**
- Create `markdownToHtml()` utility function
- Handle common markdown syntax:
  - `**bold**` → `<b>bold</b>`
  - `*italic*` → `<i>italic</i>`
  - `` `code` `` → `<code>code</code>`
  - `# Header` → `<b>Header</b>`
  - `- List item` → `• List item`
  - `1. Numbered item` → `1. Numbered item`
- Apply conversion to all outgoing messages before sending
- Test with various LLM response formats
- Handle edge cases (nested formatting, mixed syntax)

### 4. **Testing Requirements**
- Test with various markdown patterns
- Test edge cases (nested formatting, mixed syntax)
- Test performance with long messages
- Verify Telegram display on actual devices

## Acceptance Criteria
- [ ] No raw markdown syntax (`**`, `*`, `` ` ``, `#`, `-`) visible to users
- [ ] Text is either properly formatted or plain (no formatting codes)
- [ ] All bot responses affected (tax calculations, explanations, menus)
- [ ] No breaking changes to existing functionality
- [ ] Solution handles common markdown patterns from LLM
- [ ] Performance not significantly impacted
- [ ] Tests cover conversion/stripping logic

## Implementation Notes

### Files to Modify
1. `node-gateway/src/channels/telegram/bot.ts` - Message sending logic
2. `node-gateway/src/utils/formatter.ts` - New utility file (if created)
3. `node-gateway/src/channels/telegram/mapper.ts` - Message formatting

### Current Code Reference
```typescript
// Current implementation in bot.ts (lines 258-280):
try {
  // Try HTML parse mode first for nice formatting
  await this.bot.telegram.sendMessage(telegramChatId, chunks[i], {
    parse_mode: 'HTML',  // ← THIS CAUSES THE ISSUE
    ...replyMarkup,
  });
} catch (htmlError: any) {
  // If HTML parsing fails, fall back to plain text
  if (htmlError?.message?.includes("can't parse entities")) {
    await this.bot.telegram.sendMessage(telegramChatId, chunks[i], {
      ...replyMarkup,
    });
  } else {
    throw htmlError;
  }
}
```

### Implementation Approach
**Markdown-to-HTML conversion** is the chosen solution because:
1. Maintains existing `parse_mode: 'HTML'` setup
2. Preserves formatting (bold, italic) for better readability
3. Handles LLM's natural markdown output format
4. Can be implemented as a preprocessing step without major changes

### Sample Implementation
```typescript
// In bot.ts, before sending:
const formattedText = markdownToHtml(originalText);

// markdownToHtml implementation:
function markdownToHtml(text: string): string {
  let html = text;
  
  // Bold: **text** → <b>text</b>
  html = html.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
  
  // Italic: *text* → <i>text</i>
  html = html.replace(/\*(.*?)\*/g, '<i>$1</i>');
  
  // Code: `text` → <code>text</code>
  html = html.replace(/`(.*?)`/g, '<code>$1</code>');
  
  // Headers: # Text → <b>Text</b>
  html = html.replace(/^# (.*$)/gm, '<b>$1</b>');
  
  // Lists: - item → • item
  html = html.replace(/^- (.*$)/gm, '• $1');
  
  return html;
}
```

## Related Issues
- This affects all user-facing messages from the bot
- Particularly noticeable in tax calculation explanations and instructions
- Impacts user experience and professionalism of the bot

## Notes
- **High priority** because it affects every user interaction
- **User experience impact** is significant (looks unprofessional)
- **Simple fix** with high return on investment
- Should be implemented before any major user-facing releases
