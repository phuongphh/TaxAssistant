import { logger } from '../utils/logger';
import { Suggestion } from '../session/store';

/**
 * Suggestion Generator - creates context-aware suggestions for the Tax Assistant
 * 
 * This module generates 3 relevant text-based suggestions based on the current
 * conversation context. Suggestions are numbered (1, 2, 3) and are optional
 * for the user to choose from.
 */

export type ConversationContext = 'tax-calculation' | 'deadline-info' | 'legal-doc' | 'tax-registration' | 'declaration-guide' | 'general';

export interface SuggestionConfig {
  context: ConversationContext;
  suggestions: Suggestion[];
}

/**
 * Generate suggestions based on conversation context
 */
export function generateSuggestions(context: ConversationContext): Suggestion[] {
  const suggestionMap: Record<ConversationContext, Suggestion[]> = {
    'tax-calculation': [
      { id: 1, text: 'Tính thuế cho một khoản thu nhập khác', action: 'calculate_another_tax', context: 'tax-calculation' },
      { id: 2, text: 'Xem hướng dẫn kê khai loại thuế này', action: 'show_declaration_guide', context: 'tax-calculation' },
      { id: 3, text: 'Kiểm tra thời hạn nộp thuế', action: 'check_deadline', context: 'tax-calculation' }
    ],
    'deadline-info': [
      { id: 1, text: 'Xem thời hạn nộp các loại thuế khác', action: 'check_other_deadlines', context: 'deadline-info' },
      { id: 2, text: 'Tính phạt chậm nộp', action: 'calculate_late_fee', context: 'deadline-info' },
      { id: 3, text: 'Hướng dẫn nộp thuế trực tuyến', action: 'show_online_payment_guide', context: 'deadline-info' }
    ],
    'legal-doc': [
      { id: 1, text: 'Tìm văn bản pháp luật liên quan', action: 'find_related_documents', context: 'legal-doc' },
      { id: 2, text: 'Xem hướng dẫn áp dụng văn bản', action: 'show_application_guide', context: 'legal-doc' },
      { id: 3, text: 'Kiểm tra văn bản mới nhất', action: 'check_latest_documents', context: 'legal-doc' }
    ],
    'tax-registration': [
      { id: 1, text: 'Hướng dẫn chuẩn bị hồ sơ đăng ký', action: 'show_document_preparation', context: 'tax-registration' },
      { id: 2, text: 'Đăng ký mã số thuế trực tuyến', action: 'register_online', context: 'tax-registration' },
      { id: 3, text: 'Kiểm tra tình trạng hồ sơ', action: 'check_registration_status', context: 'tax-registration' }
    ],
    'declaration-guide': [
      { id: 1, text: 'Tải mẫu tờ khai', action: 'download_form', context: 'declaration-guide' },
      { id: 2, text: 'Hướng dẫn điền tờ khai chi tiết', action: 'show_filling_guide', context: 'declaration-guide' },
      { id: 3, text: 'Kiểm tra lỗi thường gặp khi kê khai', action: 'check_common_errors', context: 'declaration-guide' }
    ],
    'general': [
      { id: 1, text: 'Tính thuế GTGT/TNDN/TNCN', action: 'calculate_tax', context: 'general' },
      { id: 2, text: 'Xem thời hạn nộp thuế', action: 'check_deadlines', context: 'general' },
      { id: 3, text: 'Tra cứu văn bản pháp luật', action: 'search_legal_docs', context: 'general' }
    ]
  };

  return suggestionMap[context] || suggestionMap.general;
}

/**
 * Detect conversation context from user message or bot response
 */
export function detectContext(text: string): ConversationContext {
  const lowerText = text.toLowerCase();
  
  // Tax calculation context
  if (lowerText.includes('tính thuế') || 
      lowerText.includes('tính toán thuế') ||
      lowerText.includes('thuế gtgt') ||
      lowerText.includes('thuế tndn') ||
      lowerText.includes('thuế tncn') ||
      lowerText.includes('thuế môn bài') ||
      lowerText.includes('vat') ||
      lowerText.includes('cit') ||
      lowerText.includes('pit')) {
    return 'tax-calculation';
  }
  
  // Deadline context
  if (lowerText.includes('hạn nộp') ||
      lowerText.includes('thời hạn') ||
      lowerText.includes('deadline') ||
      lowerText.includes('chậm nộp')) {
    return 'deadline-info';
  }
  
  // Legal document context
  if (lowerText.includes('văn bản') ||
      lowerText.includes('pháp luật') ||
      lowerText.includes('thông tư') ||
      lowerText.includes('nghị định') ||
      lowerText.includes('luật thuế')) {
    return 'legal-doc';
  }
  
  // Tax registration context
  if (lowerText.includes('đăng ký mã số thuế') ||
      lowerText.includes('mst') ||
      lowerText.includes('tax code') ||
      lowerText.includes('đăng ký thuế')) {
    return 'tax-registration';
  }
  
  // Declaration guide context
  if (lowerText.includes('kê khai') ||
      lowerText.includes('tờ khai') ||
      lowerText.includes('nộp thuế') ||
      lowerText.includes('declaration') ||
      lowerText.includes('payment')) {
    return 'declaration-guide';
  }
  
  return 'general';
}

/**
 * Format suggestions as text for display
 */
export function formatSuggestions(suggestions: Suggestion[]): string {
  if (!suggestions || suggestions.length === 0) {
    return '';
  }
  
  let formatted = '\n\nBạn muốn làm gì tiếp theo?\n';
  suggestions.forEach(suggestion => {
    formatted += `${suggestion.id}. ${suggestion.text}\n`;
  });
  
  return formatted;
}

/**
 * Check if user input is a suggestion choice (1, 2, or 3)
 */
export function isSuggestionChoice(text: string): boolean {
  const trimmed = text.trim();
  return ['1', '2', '3'].includes(trimmed);
}

/**
 * Get suggestion action based on choice number
 */
export function getSuggestionAction(choice: string, suggestions: Suggestion[]): string | null {
  const choiceNum = parseInt(choice, 10);
  const suggestion = suggestions.find(s => s.id === choiceNum);
  return suggestion ? suggestion.action : null;
}

/**
 * Update context based on suggestion action
 */
export function updateContextFromAction(action: string): ConversationContext {
  const actionContextMap: Record<string, ConversationContext> = {
    'calculate_another_tax': 'tax-calculation',
    'show_declaration_guide': 'declaration-guide',
    'check_deadline': 'deadline-info',
    'check_other_deadlines': 'deadline-info',
    'calculate_late_fee': 'deadline-info',
    'show_online_payment_guide': 'declaration-guide',
    'find_related_documents': 'legal-doc',
    'show_application_guide': 'legal-doc',
    'check_latest_documents': 'legal-doc',
    'show_document_preparation': 'tax-registration',
    'register_online': 'tax-registration',
    'check_registration_status': 'tax-registration',
    'download_form': 'declaration-guide',
    'show_filling_guide': 'declaration-guide',
    'check_common_errors': 'declaration-guide',
    'calculate_tax': 'tax-calculation',
    'check_deadlines': 'deadline-info',
    'search_legal_docs': 'legal-doc'
  };
  
  return actionContextMap[action] || 'general';
}