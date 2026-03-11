# Issue #10

[Bug] be_thue_bot không phản hồi với một số tin nhắn cụ thể - lỗi lặp lại

# [Bug] be_thue_bot không phản hồi với một số tin nhắn cụ thể - lỗi lặp lại

**Repository:** phuongphh/TaxAssistant  
**Type:** Bug  
**Priority:** High  
**Labels:** bug, critical, bot, telegram

## Description
be_thue_bot không phản hồi với một số tin nhắn cụ thể (ví dụ: /start, Chạy chưa?) trong khi vẫn hoạt động bình thường với các tin nhắn khác. Lỗi xảy ra lần thứ 3 mặc dù đã có bản fix tối qua (10/03).

## Evidence (Screenshot)
![Bug Evidence](attachment://screenshot.png)
*Bot vẫn trả lời về Step 4 thuế nhưng không phản hồi /start và Chạy chưa?*

## Timeline
- **First occurrence:** Tối 10/03 (đã fix)
- **Second occurrence:** Sáng 11/03 (khoảng 11h)
- **Third occurrence:** [Cần xác nhận thời gian]

## Environment
- **Server:** Mac mini M4
- **Deployment:** Docker container
- **Bot:** be_thue_bot (Telegram bot Bé Thuế)
- **Stack:** [Cần xác định - Python/Node.js?]

## Steps to Reproduce
1. Mở chat với be_thue_bot trên Telegram
2. Gửi tin nhắn /start
3. Bot không phản hồi
4. Gửi tin nhắn Chạy chưa?
5. Bot không phản hồi
6. Gửi tin nhắn khác (ví dụ: Cách tính thuế TNCN?)
7. Bot phản hồi bình thường

## Expected Behavior
Bot phải phản hồi tất cả tin nhắn, đặc biệt là command /start và các câu hỏi thông thường.

## Actual Behavior
Bot im lặng với một số tin nhắn cụ thể nhưng vẫn hoạt động với tin nhắn khác.

## Root Cause Hypothesis
1. **Command handler issue:** /start command handler bị lỗi
2. **Message filtering:** Bot filter một số từ/cụm từ cụ thể
3. **Rate limiting:** Telegram API rate limit cho một số loại tin nhắn
4. **Async processing hang:** Xử lý async bị treo với một số pattern
5. **Database lock:** Transaction lock khi xử lý một số loại tin nhắn

## Acceptance Criteria
- [ ] Bot phải phản hồi TẤT CẢ tin nhắn (không được im lặng)
- [ ] /start command phải hoạt động 100%
- [ ] Implement comprehensive logging để debug message flow
- [ ] Add health check endpoint (/health) với bot status
- [ ] Add alerting khi bot không phản hồi trong X phút
- [ ] Test với các loại tin nhắn khác nhau

## Claude Code Prompt


## Notes
- Đây là bug CRITICAL vì ảnh hưởng trực tiếp đến user experience
- Cần fix triệt để, không phải workaround
- Cần monitoring để phát hiện sớm nếu tái phát
