/**
 * Template service for building structured Telegram messages.
 * Uses HTML formatting compatible with Telegram's parse_mode: 'HTML'.
 */

const SEPARATOR = '──────────────────────────────────────';

/**
 * Return a Vietnamese greeting based on Vietnam time (UTC+7).
 *
 * Accepts an optional `now` parameter for testability.
 */
export function getTimeBasedGreeting(now: Date = new Date()): string {
  // Convert to Vietnam time (UTC+7)
  const utcHour = now.getUTCHours();
  const vnHour = (utcHour + 7) % 24;

  if (vnHour >= 5 && vnHour < 11) return 'Chào buổi sáng';
  if (vnHour >= 11 && vnHour < 13) return 'Chào buổi trưa';
  if (vnHour >= 13 && vnHour < 18) return 'Chào buổi chiều';
  return 'Chào buổi tối';
}

/**
 * Build the full homepage template shown when a user sends /start.
 *
 * Returns a single HTML-formatted string (≤ 4096 chars).
 */
export function getHomepageTemplate(userName: string, now?: Date): string {
  const greeting = getTimeBasedGreeting(now);

  const sections = [
    // Section 1 — Header
    [
      `${greeting}, ${userName}! 👋`,
      SEPARATOR,
      'Tôi là Trợ lý Thuế ảo, hỗ trợ bạn tuân thủ thuế tại Việt Nam.',
    ].join('\n'),

    // Section 2 — 9 Core Services
    [
      '📊 <b>DỊCH VỤ CHÍNH</b>',
      '',
      '1.  Tính thuế (GTGT, TNDN, TNCN, Môn bài)',
      '2.  Hướng dẫn kê khai và quyết toán thuế',
      '3.  Đăng ký mã số thuế',
      '4.  Kiểm tra hóa đơn/chứng từ',
      '5.  Tư vấn thuế với dẫn chứng pháp luật',
      '6.  Tư vấn xử phạt vi phạm thuế',
      '7.  Hỗ trợ hoàn thuế GTGT',
      '8.  Quyết toán thuế năm',
      '9.  Thông tin của tôi 👤',
    ].join('\n'),

    // Section 3 — 2026 Tax Updates
    [
      '📢 <b>CẬP NHẬT THUẾ 2026</b>',
      '',
      '- Giảm trừ gia cảnh mới: 11 triệu/người',
      '- Miễn thuế TNCN thu nhập dưới 11 triệu/tháng',
      '- Điều chỉnh thuế suất doanh nghiệp nhỏ',
      '- Hỗ trợ gia hạn nộp thuế cho SME',
    ].join('\n'),

    // Section 4 — Sample Questions
    [
      '💡 <b>CÂU HỎI MẪU CHO DOANH NGHIỆP SME</b>',
      '',
      '- "Cách tính thuế GTGT cho hộ kinh doanh?"',
      '- "Hồ sơ đăng ký mã số thuế cần gì?"',
      '- "Làm sao giảm thuế TNDN hợp pháp?"',
      '- "Thời hạn nộp thuế môn bài 2026?"',
      '- "Chính sách ưu đãi thuế cho startup?"',
    ].join('\n'),

    // Section 5 — SME Support
    [
      '🏢 <b>HỖ TRỢ DOANH NGHIỆP SME</b>',
      '',
      '🔹 <b>Tuân thủ thuế:</b>',
      '   - Hướng dẫn kê khai từ A-Z',
      '   - Cảnh báo thời hạn nộp thuế',
      '   - Cập nhật chính sách mới nhất',
      '',
      '🔹 <b>Tối ưu thuế:</b>',
      '   - Tư vấn giảm trừ, miễn giảm',
      '   - Kế hoạch thuế hiệu quả',
      '   - Tránh phạt chậm nộp',
      '',
      '🔹 <b>Hỗ trợ 24/7:</b>',
      '   - Trả lời câu hỏi thuế',
      '   - Hướng dẫn thủ tục',
      '   - Kết nối chuyên gia',
    ].join('\n'),

    // Section 6 — Legal References
    [
      '⚖️ <b>CĂN CỨ PHÁP LÝ</b>',
      'Luật Quản lý thuế 38/2019/QH14',
      'Nghị định 126/2020/NĐ-CP',
      'Thông tư 80/2021/TT-BTC',
    ].join('\n'),

    // Section 7 — Call to Action
    [
      SEPARATOR,
      'Bắt đầu bằng cách chọn dịch vụ bên dưới',
      'hoặc gửi câu hỏi trực tiếp cho tôi!',
    ].join('\n'),
  ];

  return sections.join('\n\n');
}
