# Issue #40

[Feature] User feedback collection system with homepage integration

# [Feature] User feedback collection system with homepage integration

**Repository:** phuongphh/TaxAssistant  
**Type:** Feature  
**Priority:** Medium  
**Labels:** enhancement, user-feedback, analytics

## Overview
Implement a user feedback collection system that allows users to provide feedback about the TaxAssistant app. The feature will be integrated into the homepage/main menu as a footer section and will collect textual feedback that can be used for product improvement.

## Business Context
Collecting user feedback is essential for:
1. **Product improvement** - Understand user pain points and needs
2. **User satisfaction** - Show users their opinions are valued
3. **Quality assurance** - Identify bugs and issues
4. **Feature prioritization** - Guide product roadmap based on user input

## Requirements

### **1. Homepage Integration (Footer Section)**
Add a feedback section to the homepage/main menu template (Issue #38) as a footer element:

```
──────────────────────────────────────
📝 **PHẢN HỒI SẢN PHẨM**

Có ý kiến đóng góp về sản phẩm?
Gửi phản hồi giúp chúng tôi cải thiện!

[ Gửi phản hồi ]
──────────────────────────────────────
Bắt đầu bằng cách chọn dịch vụ bên dưới
hoặc gửi câu hỏi trực tiếp cho tôi!
```

**Design Principles:**
- **Non-intrusive** - Doesn't interfere with core services
- **Clear call-to-action** - Easy to understand and use
- **Professional appearance** - Matches overall design aesthetic
- **Optional** - Users can ignore if they don't want to provide feedback

### **2. Feedback Flow**

#### **Step 1: Initiation**
User clicks "Gửi phản hồi" button or types `/feedback` command.

#### **Step 2: Prompt**
```
Bot: Cảm ơn bạn quan tâm! Hãy chia sẻ phản hồi của bạn về TaxAssistant:

• Bạn thích điều gì?
• Điều gì cần cải thiện?
• Tính năng nào bạn mong muốn?
• Gặp vấn đề gì khi sử dụng?

(Viết bằng tiếng Việt, tối đa 1000 ký tự)
```

#### **Step 3: Collection**
User types their feedback (text only, no attachments).

#### **Step 4: Confirmation**
```
Bot: ✅ Cảm ơn phản hồi quý giá của bạn!

Ý kiến của bạn đã được ghi nhận và sẽ giúp chúng tôi cải thiện sản phẩm.

Quay lại menu chính: /start
```

#### **Step 5: Optional Rating (Future Enhancement)**
Potential future addition: 1-5 star rating before/after feedback.

### **3. Database Schema**
Create `user_feedback` table:

```sql
CREATE TABLE user_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR NOT NULL,           -- Telegram user ID
  channel VARCHAR NOT NULL,           -- 'telegram', 'zalo', etc.
  feedback_text TEXT NOT NULL,        -- User's feedback content
  rating INTEGER,                     -- Optional: 1-5 stars (future)
  metadata JSONB DEFAULT '{}',        -- Additional data
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for analytics
CREATE INDEX idx_feedback_user_id ON user_feedback(user_id);
CREATE INDEX idx_feedback_created_at ON user_feedback(created_at);
```

### **4. Data Collection Rules**
- **Maximum length:** 1000 characters
- **Language:** Vietnamese (primary), English accepted
- **Content:** Text only, no images/attachments
- **Optional fields:** User can skip any part
- **No personal data:** Don't prompt for email/phone
- **Anonymous option:** Allow anonymous feedback (user_id = 'anonymous')

### **5. Admin Dashboard (Future Phase)**
**Phase 2 feature:** Admin interface to view feedback:
- List all feedback with timestamps
- Filter by date, user, channel
- Search within feedback text
- Export to CSV/Excel
- Analytics dashboard (feedback volume, trends)

### **6. Privacy & Ethics**
- **Transparency:** Explain how feedback will be used
- **Optional:** Users can choose not to provide feedback
- **No pressure:** Don't repeatedly ask for feedback
- **Data retention:** Consider auto-delete after X months
- **GDPR compliance:** Allow feedback deletion request

## Technical Implementation

### **1. Files to Modify/Create**

#### **Modified Files:**
- `node-gateway/src/channels/telegram/bot.ts` - Add feedback button and command
- `node-gateway/src/services/templateService.ts` - Update homepage template
- `node-gateway/src/router/messageRouter.ts` - Add feedback intent handling

#### **New Files:**
- `node-gateway/src/services/feedbackService.ts` - Feedback collection logic
- `node-gateway/src/repositories/feedbackRepository.ts` - Database operations
- `prisma/migrations/XXXXXX_add_user_feedback_table/` - Database migration
- `node-gateway/src/controllers/feedbackController.ts` - API endpoints (future)

### **2. Feedback Service Structure**
```typescript
class FeedbackService {
  async startFeedbackSession(userId: string, channel: string): Promise<void>;
  async saveFeedback(userId: string, feedbackText: string): Promise<Feedback>;
  async getFeedbackByUser(userId: string): Promise<Feedback[]>;
  async getRecentFeedback(limit: number): Promise<Feedback[]>;
  async getFeedbackStats(): Promise<FeedbackStats>;
}

interface Feedback {
  id: string;
  userId: string;
  channel: string;
  feedbackText: string;
  rating?: number;
  createdAt: Date;
  updatedAt: Date;
}
```

### **3. State Management**
Track feedback session state:
```typescript
interface SessionData {
  // ... existing fields
  feedbackState?: {
    isCollecting: boolean;
    startedAt: Date;
    expectedLength?: number;
  };
}
```

### **4. Integration with Homepage (Issue #38)**
Update the TemplateService to include feedback section:
```typescript
class TemplateService {
  getHomepageTemplate(userName: string): string {
    return `
      ${this.getHeader(userName)}
      ${this.getServicesSection()}
      ${this.getTaxUpdatesSection()}
      ${this.getSmeSupportSection()}
      ${this.getFeedbackSection()}  // ← NEW
      ${this.getFooter()}
    `;
  }
  
  getFeedbackSection(): string {
    return `
──────────────────────────────────────
📝 **PHẢN HỒI SẢN PHẨM**

Có ý kiến đóng góp về sản phẩm?
Gửi phản hồi giúp chúng tôi cải thiện!

[ Gửi phản hồi ]
──────────────────────────────────────
    `;
  }
}
```

### **5. Button Implementation**
```typescript
// In bot.ts - Add feedback button to homepage
const feedbackButton = {
  text: 'Gửi phản hồi',
  callback_data: 'start_feedback'
};

// Handle button click
bot.on('callback_query', async (ctx) => {
  if (ctx.callbackQuery.data === 'start_feedback') {
    await feedbackService.startFeedbackSession(userId, 'telegram');
    await ctx.reply(feedbackPrompt);
  }
});
```

### **6. Command Implementation**
```typescript
// /feedback command
bot.command('feedback', async (ctx) => {
  await feedbackService.startFeedbackSession(userId, 'telegram');
  await ctx.reply(feedbackPrompt);
});
```

## User Experience

### **1. When to Show Feedback Option**
- **Always:** Available on homepage footer
- **Periodically:** After X interactions (configurable)
- **After positive outcomes:** When user successfully completes a task
- **Never:** Don't show during errors or frustration

### **2. Feedback Prompt Design**
```
📝 **GÓP Ý CHO TAXASSISTANT**

Chúng tôi luôn muốn cải thiện! Hãy chia sẻ:

• Điều bạn thích nhất về TaxAssistant?
• Tính năng nào cần thêm/cải thiện?
• Gặp khó khăn gì khi sử dụng?
• Ý tưởng nào cho phiên bản tới?

(Cảm ơn bạn đóng góp! Phản hồi sẽ được xem xét kỹ lưỡng)
```

### **3. Response Handling**
- **Positive feedback:** Thank and encourage sharing
- **Negative feedback:** Apologize and promise improvement
- **Feature requests:** Acknowledge and note for consideration
- **Bug reports:** Log and provide tracking number if possible

## Acceptance Criteria
- [ ] Homepage includes feedback section in footer
- [ ] "Gửi phản hồi" button works and initiates feedback flow
- [ ] `/feedback` command available and functional
- [ ] Feedback collection flow works end-to-end
- [ ] Feedback saved to database with all required fields
- [ ] User receives confirmation after submitting feedback
- [ ] Maximum character limit enforced (1000 chars)
- [ ] No breaking changes to existing functionality
- [ ] Feedback doesn't interfere with normal bot operation
- [ ] Privacy considerations implemented (anonymous option)

## Future Enhancements (Phase 2)

### **1. Feedback Categories**
Allow users to categorize feedback:
- [ ] Bug report
- [ ] Feature request  
- [ ] Usability issue
- [ ] General feedback
- [ ] Praise/compliment

### **2. Rating System**
Add optional 1-5 star rating:
```
Trước khi gửi phản hồi, bạn đánh giá TaxAssistant mấy sao?
⭐⭐⭐⭐⭐
```

### **3. Admin Dashboard**
- Web interface to view/manage feedback
- Analytics and reporting
- Export functionality
- Response management (reply to users)

### **4. Automated Analysis**
- Sentiment analysis on feedback
- Topic clustering (common themes)
- Priority scoring (urgent vs. nice-to-have)
- Integration with issue tracking (GitHub/Jira)

### **5. Feedback Incentives**
- Thank you messages
- Feature update notifications ("Your feedback implemented!")
- Beta testing invitations
- Recognition in changelogs

## Implementation Notes

### **Phase 1 (Current Issue)**
- Basic feedback collection
- Homepage integration
- Database storage
- Simple confirmation flow

### **Phase 2 (Future)**
- Admin dashboard
- Analytics and reporting
- Enhanced features (ratings, categories)
- Integration with product management tools

### **Testing Considerations**
- Test feedback flow end-to-end
- Verify database persistence
- Test character limits and validation
- Verify homepage integration looks correct
- Test on different Telegram clients

## Related Issues
- **Issue #38:** Homepage redesign - feedback section will be added here
- **Issue #30:** User profile management - feedback can be linked to user profiles
- **Issue #35:** Markdown formatting - feedback text should use proper formatting

## Notes
- **Low-friction design** - Make it easy to provide feedback
- **Value demonstration** - Show users their feedback matters
- **Continuous improvement** - Use feedback to drive product development
- **User-centric** - Designed for users, not just data collection
