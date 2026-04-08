import { describe, it, expect } from 'vitest';
import {
  generateSuggestions,
  detectContext,
  formatSuggestions,
  isSuggestionChoice,
  getSuggestionAction,
  updateContextFromAction,
  ConversationContext
} from './suggestionGenerator';

describe('Suggestion Generator', () => {
  describe('detectContext', () => {
    it('should detect tax-calculation context', () => {
      expect(detectContext('Tính thuế TNCN lương 20 triệu')).toBe('tax-calculation');
      expect(detectContext('tính thuế gtgt cho 500 triệu')).toBe('tax-calculation');
      expect(detectContext('Thuế TNDN phải nộp bao nhiêu?')).toBe('tax-calculation');
      expect(detectContext('Tính toán thuế môn bài')).toBe('tax-calculation');
    });

    it('should detect deadline-info context', () => {
      expect(detectContext('Hạn nộp thuế môn bài 2025')).toBe('deadline-info');
      expect(detectContext('Thời hạn nộp thuế GTGT')).toBe('deadline-info');
      expect(detectContext('Khi nào nộp thuế TNCN?')).toBe('deadline-info');
      expect(detectContext('Deadline nộp thuế')).toBe('deadline-info');
    });

    it('should detect legal-doc context', () => {
      expect(detectContext('Tra cứu thông tư 78/2014/TT-BTC')).toBe('legal-doc');
      expect(detectContext('Văn bản pháp luật về thuế')).toBe('legal-doc');
      expect(detectContext('Nghị định về thuế')).toBe('legal-doc');
      expect(detectContext('Dẫn chứng pháp lý')).toBe('legal-doc');
    });

    it('should detect tax-registration context', () => {
      expect(detectContext('Đăng ký mã số thuế cá nhân')).toBe('tax-registration');
      expect(detectContext('Thủ tục đăng ký MST')).toBe('tax-registration');
      expect(detectContext('Cấp mã số thuế doanh nghiệp')).toBe('tax-registration');
    });

    it('should detect declaration-guide context', () => {
      expect(detectContext('Cách kê khai thuế GTGT')).toBe('declaration-guide');
      expect(detectContext('Hướng dẫn nộp thuế')).toBe('declaration-guide');
      expect(detectContext('Mẫu tờ khai thuế')).toBe('declaration-guide');
    });

    it('should return general for unknown context', () => {
      expect(detectContext('Xin chào')).toBe('general');
      expect(detectContext('Cảm ơn')).toBe('general');
      expect(detectContext('')).toBe('general');
    });
  });

  describe('generateSuggestions', () => {
    it('should generate tax-calculation suggestions', () => {
      const suggestions = generateSuggestions('tax-calculation');
      expect(suggestions).toHaveLength(3);
      expect(suggestions[0].id).toBe(1);
      expect(suggestions[0].text).toBe('Tính thuế cho một khoản thu nhập khác');
      expect(suggestions[0].context).toBe('tax-calculation');
    });

    it('should generate deadline-info suggestions', () => {
      const suggestions = generateSuggestions('deadline-info');
      expect(suggestions).toHaveLength(3);
      expect(suggestions[0].id).toBe(1);
      expect(suggestions[0].text).toBe('Xem thời hạn nộp các loại thuế khác');
    });

    it('should generate legal-doc suggestions', () => {
      const suggestions = generateSuggestions('legal-doc');
      expect(suggestions).toHaveLength(3);
      expect(suggestions[0].id).toBe(1);
      expect(suggestions[0].text).toBe('Tìm văn bản pháp luật liên quan');
    });

    it('should generate tax-registration suggestions', () => {
      const suggestions = generateSuggestions('tax-registration');
      expect(suggestions).toHaveLength(3);
      expect(suggestions[0].id).toBe(1);
      expect(suggestions[0].text).toBe('Hướng dẫn chuẩn bị hồ sơ đăng ký');
    });

    it('should generate declaration-guide suggestions', () => {
      const suggestions = generateSuggestions('declaration-guide');
      expect(suggestions).toHaveLength(3);
      expect(suggestions[0].id).toBe(1);
      expect(suggestions[0].text).toBe('Tải mẫu tờ khai');
    });

    it('should generate general suggestions for unknown context', () => {
      const suggestions = generateSuggestions('unknown' as ConversationContext);
      expect(suggestions).toHaveLength(3);
      expect(suggestions[0].text).toBe('Tính thuế GTGT/TNDN/TNCN');
    });
  });

  describe('formatSuggestions', () => {
    it('should format suggestions correctly', () => {
      const suggestions = generateSuggestions('tax-calculation');
      const formatted = formatSuggestions(suggestions);
      
      expect(formatted).toContain('Bạn muốn làm gì tiếp theo?');
      expect(formatted).toContain('1. Tính thuế cho một khoản thu nhập khác');
      expect(formatted).toContain('2. Xem hướng dẫn kê khai loại thuế này');
      expect(formatted).toContain('3. Kiểm tra thời hạn nộp thuế');
    });

    it('should return empty string for empty suggestions', () => {
      expect(formatSuggestions([])).toBe('');
    });
  });

  describe('isSuggestionChoice', () => {
    it('should recognize suggestion choices', () => {
      expect(isSuggestionChoice('1')).toBe(true);
      expect(isSuggestionChoice('2')).toBe(true);
      expect(isSuggestionChoice('3')).toBe(true);
      expect(isSuggestionChoice(' 1 ')).toBe(true);
    });

    it('should reject non-suggestion choices', () => {
      expect(isSuggestionChoice('4')).toBe(false);
      expect(isSuggestionChoice('0')).toBe(false);
      expect(isSuggestionChoice('hello')).toBe(false);
      expect(isSuggestionChoice('')).toBe(false);
      expect(isSuggestionChoice('12')).toBe(false);
    });
  });

  describe('getSuggestionAction', () => {
    it('should get action for valid choice', () => {
      const suggestions = generateSuggestions('tax-calculation');
      expect(getSuggestionAction('1', suggestions)).toBe('calculate_another_tax');
      expect(getSuggestionAction('2', suggestions)).toBe('show_declaration_guide');
      expect(getSuggestionAction('3', suggestions)).toBe('check_deadline');
    });

    it('should return null for invalid choice', () => {
      const suggestions = generateSuggestions('tax-calculation');
      expect(getSuggestionAction('4', suggestions)).toBeNull();
      expect(getSuggestionAction('0', suggestions)).toBeNull();
      expect(getSuggestionAction('abc', suggestions)).toBeNull();
    });
  });

  describe('updateContextFromAction', () => {
    it('should update context based on action', () => {
      expect(updateContextFromAction('calculate_another_tax')).toBe('tax-calculation');
      expect(updateContextFromAction('show_declaration_guide')).toBe('declaration-guide');
      expect(updateContextFromAction('check_deadline')).toBe('deadline-info');
      expect(updateContextFromAction('find_related_documents')).toBe('legal-doc');
      expect(updateContextFromAction('show_document_preparation')).toBe('tax-registration');
    });

    it('should return general for unknown action', () => {
      expect(updateContextFromAction('unknown_action')).toBe('general');
    });
  });
});