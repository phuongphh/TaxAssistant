# Issue #48

[Bug] Duplicate follow-up prompt - Remove "Bạn muốn làm gì tiếp theo?" text

## Bug Description
After the bot provides a tax consultation response, there are two redundant follow-up prompts displayed simultaneously:
1. **"Gợi ý tiếp theo"** — inline buttons with suggested next actions ✅ (keep this)
2. **"Bạn muốn làm gì tiếp theo?"** — plain text prompt ❌ (remove this)

This creates a confusing and repetitive user experience.

## Steps to Reproduce
1. Start a conversation with the bot
2. Ask any tax-related question
3. Observe the response — both prompts appear at the end of the message

## Expected Behavior
Only the **"Gợi ý tiếp theo"** inline buttons should appear. The text "Bạn muốn làm gì tiếp theo?" should be removed entirely.

## Actual Behavior
Both "Gợi ý tiếp theo" buttons AND "Bạn muốn làm gì tiếp theo?" text are displayed together, causing duplicate/redundant UI.

## Fix
Remove the "Bạn muốn làm gì tiếp theo?" text from the bot response template. Keep only the inline suggestion buttons.
