import { describe, it, expect } from 'vitest';
import { getTimeBasedGreeting, getHomepageTemplate } from './templateService';

// Helper: create a Date at a specific UTC hour
function utcDate(hour: number): Date {
  const d = new Date('2026-03-22T00:00:00Z');
  d.setUTCHours(hour, 0, 0, 0);
  return d;
}

describe('getTimeBasedGreeting', () => {
  it('returns morning greeting for VN 5:00-10:59 (UTC 22:00-03:59)', () => {
    // UTC 00:00 → VN 07:00 (morning)
    expect(getTimeBasedGreeting(utcDate(0))).toBe('Chào buổi sáng');
    // UTC 03:00 → VN 10:00 (morning)
    expect(getTimeBasedGreeting(utcDate(3))).toBe('Chào buổi sáng');
  });

  it('returns noon greeting for VN 11:00-12:59 (UTC 04:00-05:59)', () => {
    // UTC 04:00 → VN 11:00 (noon)
    expect(getTimeBasedGreeting(utcDate(4))).toBe('Chào buổi trưa');
    // UTC 05:00 → VN 12:00 (noon)
    expect(getTimeBasedGreeting(utcDate(5))).toBe('Chào buổi trưa');
  });

  it('returns afternoon greeting for VN 13:00-17:59 (UTC 06:00-10:59)', () => {
    // UTC 06:00 → VN 13:00 (afternoon)
    expect(getTimeBasedGreeting(utcDate(6))).toBe('Chào buổi chiều');
    // UTC 10:00 → VN 17:00 (afternoon)
    expect(getTimeBasedGreeting(utcDate(10))).toBe('Chào buổi chiều');
  });

  it('returns evening greeting for VN 18:00-04:59 (UTC 11:00-21:59)', () => {
    // UTC 11:00 → VN 18:00 (evening)
    expect(getTimeBasedGreeting(utcDate(11))).toBe('Chào buổi tối');
    // UTC 20:00 → VN 03:00 (night → tối)
    expect(getTimeBasedGreeting(utcDate(20))).toBe('Chào buổi tối');
    // UTC 21:00 → VN 04:00 (night → tối)
    expect(getTimeBasedGreeting(utcDate(21))).toBe('Chào buổi tối');
  });

  it('handles VN midnight correctly (UTC 17:00)', () => {
    // UTC 17:00 → VN 00:00 (tối)
    expect(getTimeBasedGreeting(utcDate(17))).toBe('Chào buổi tối');
  });

  it('handles boundary: VN 5:00 = sáng (UTC 22:00)', () => {
    expect(getTimeBasedGreeting(utcDate(22))).toBe('Chào buổi sáng');
  });

  it('handles boundary: VN 11:00 = trưa (UTC 04:00)', () => {
    expect(getTimeBasedGreeting(utcDate(4))).toBe('Chào buổi trưa');
  });

  it('handles boundary: VN 13:00 = chiều (UTC 06:00)', () => {
    expect(getTimeBasedGreeting(utcDate(6))).toBe('Chào buổi chiều');
  });

  it('handles boundary: VN 18:00 = tối (UTC 11:00)', () => {
    expect(getTimeBasedGreeting(utcDate(11))).toBe('Chào buổi tối');
  });
});

describe('getHomepageTemplate', () => {
  const template = getHomepageTemplate('Broadcaster 2P', utcDate(0));

  it('includes time-based greeting with user name', () => {
    expect(template).toContain('Chào buổi sáng, Broadcaster 2P! 👋');
  });

  it('includes intro line', () => {
    expect(template).toContain('Tôi là Trợ lý Thuế ảo');
  });

  it('lists all 9 services', () => {
    expect(template).toContain('1.  Tính thuế');
    expect(template).toContain('9.  Thông tin của tôi 👤');
  });

  it('includes 2026 tax updates section', () => {
    expect(template).toContain('CẬP NHẬT THUẾ 2026');
    expect(template).toContain('Giảm trừ gia cảnh mới: 11 triệu/người');
  });

  it('includes sample SME questions', () => {
    expect(template).toContain('CÂU HỎI MẪU CHO DOANH NGHIỆP SME');
    expect(template).toContain('Cách tính thuế GTGT cho hộ kinh doanh?');
  });

  it('includes SME support section', () => {
    expect(template).toContain('HỖ TRỢ DOANH NGHIỆP SME');
    expect(template).toContain('Tuân thủ thuế');
    expect(template).toContain('Tối ưu thuế');
    expect(template).toContain('Hỗ trợ 24/7');
  });

  it('includes legal references', () => {
    expect(template).toContain('CĂN CỨ PHÁP LÝ');
    expect(template).toContain('38/2019/QH14');
  });

  it('includes call to action', () => {
    expect(template).toContain('Bắt đầu bằng cách chọn dịch vụ bên dưới');
  });

  it('uses HTML bold tags, not markdown **', () => {
    expect(template).toContain('<b>DỊCH VỤ CHÍNH</b>');
    expect(template).not.toContain('**');
  });

  it('does not use > or • bullets', () => {
    // Check that no line starts with > or •
    const lines = template.split('\n');
    for (const line of lines) {
      expect(line.trimStart()).not.toMatch(/^[>•]/);
    }
  });

  it('is within Telegram character limit (4096)', () => {
    expect(template.length).toBeLessThanOrEqual(4096);
  });

  it('adapts greeting to different times', () => {
    const evening = getHomepageTemplate('Test User', utcDate(11));
    expect(evening).toContain('Chào buổi tối, Test User! 👋');
  });
});
