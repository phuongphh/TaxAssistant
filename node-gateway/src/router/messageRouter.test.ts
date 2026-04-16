import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MessageRouter } from './messageRouter';
import { SessionManager } from '../session/manager';
import { TaxEngineClient } from '../grpc/client';
import { SessionData } from '../session/store';

// Mock dependencies
const mockSessionManager = {
  resolveSession: vi.fn(),
  recordUserMessage: vi.fn(),
  recordAssistantReply: vi.fn(),
  setCustomerType: vi.fn(),
  resetSession: vi.fn(),
  saveSession: vi.fn(),
  getSession: vi.fn(),
};

const mockTaxEngine = {
  processMessage: vi.fn(),
  getOrCreateCustomer: vi.fn(),
  getActiveCases: vi.fn(),
};

const mockChannelAdapter = {
  channel: 'telegram',
  onMessage: vi.fn(),
  sendMessage: vi.fn(),
  initialize: vi.fn(),
  shutdown: vi.fn(),
  getWebhookCallback: vi.fn(),
};

describe('MessageRouter - Suggestion Handling', () => {
  let messageRouter: MessageRouter;

  beforeEach(() => {
    vi.clearAllMocks();
    messageRouter = new MessageRouter(
      mockSessionManager as unknown as SessionManager,
      mockTaxEngine as unknown as TaxEngineClient
    );
  });

  describe('Suggestion Choice Detection', () => {
    it('should handle suggestion choice "1"', async () => {
      const session: SessionData = {
        sessionId: 'test-session',
        userId: 'user123',
        channel: 'telegram',
        customerType: 'individual',
        conversationHistory: [],
        context: {},
        createdAt: new Date().toISOString(),
        lastActiveAt: new Date().toISOString(),
        currentContext: 'tax-calculation',
        pendingSuggestions: [
          { id: 1, text: 'Tính thuế khác', action: 'calculate_another_tax', context: 'tax-calculation' },
          { id: 2, text: 'Xem hướng dẫn', action: 'show_declaration_guide', context: 'tax-calculation' },
          { id: 3, text: 'Kiểm tra hạn nộp', action: 'check_deadline', context: 'tax-calculation' },
        ],
      };

      mockSessionManager.resolveSession.mockResolvedValue(session);
      mockTaxEngine.getOrCreateCustomer.mockResolvedValue(null);
      mockTaxEngine.getActiveCases.mockResolvedValue([]);

      const message = {
        channel: 'telegram',
        userId: 'user123',
        chatId: 'chat123',
        userName: 'Test User',
        messageId: 'msg123',
        timestamp: new Date(),
        type: 'text' as const,
        text: '1',
        telegramUsername: 'testuser',
        firstName: 'Test',
        lastName: 'User',
      };

      // Mock the sendReply method
      const sendReplySpy = vi.spyOn(messageRouter as any, 'sendReply').mockResolvedValue(undefined);

      await (messageRouter as any).handleMessage(message);

      // Should call saveSession with updated suggestions
      expect(mockSessionManager.saveSession).toHaveBeenCalled();
      expect(sendReplySpy).toHaveBeenCalled();
    });

    it('should handle suggestion choice "2"', async () => {
      const session: SessionData = {
        sessionId: 'test-session',
        userId: 'user123',
        channel: 'telegram',
        customerType: 'individual',
        conversationHistory: [],
        context: {},
        createdAt: new Date().toISOString(),
        lastActiveAt: new Date().toISOString(),
        currentContext: 'deadline-info',
        pendingSuggestions: [
          { id: 1, text: 'Xem hạn nộp khác', action: 'check_other_deadlines', context: 'deadline-info' },
          { id: 2, text: 'Tính phạt chậm nộp', action: 'calculate_late_fee', context: 'deadline-info' },
          { id: 3, text: 'Hướng dẫn nộp online', action: 'show_online_payment_guide', context: 'deadline-info' },
        ],
      };

      mockSessionManager.resolveSession.mockResolvedValue(session);
      mockTaxEngine.getOrCreateCustomer.mockResolvedValue(null);
      mockTaxEngine.getActiveCases.mockResolvedValue([]);

      const message = {
        channel: 'telegram',
        userId: 'user123',
        chatId: 'chat123',
        userName: 'Test User',
        messageId: 'msg123',
        timestamp: new Date(),
        type: 'text' as const,
        text: '2',
        telegramUsername: 'testuser',
        firstName: 'Test',
        lastName: 'User',
      };

      const sendReplySpy = vi.spyOn(messageRouter as any, 'sendReply').mockResolvedValue(undefined);

      await (messageRouter as any).handleMessage(message);

      expect(mockSessionManager.saveSession).toHaveBeenCalled();
      expect(sendReplySpy).toHaveBeenCalled();
    });

    it('should handle regular message when suggestions exist', async () => {
      const session: SessionData = {
        sessionId: 'test-session',
        userId: 'user123',
        channel: 'telegram',
        customerType: 'individual',
        conversationHistory: [],
        context: {},
        createdAt: new Date().toISOString(),
        lastActiveAt: new Date().toISOString(),
        currentContext: 'tax-calculation',
        pendingSuggestions: [
          { id: 1, text: 'Tính thuế khác', action: 'calculate_another_tax', context: 'tax-calculation' },
          { id: 2, text: 'Xem hướng dẫn', action: 'show_declaration_guide', context: 'tax-calculation' },
          { id: 3, text: 'Kiểm tra hạn nộp', action: 'check_deadline', context: 'tax-calculation' },
        ],
      };

      mockSessionManager.resolveSession.mockResolvedValue(session);
      mockTaxEngine.getOrCreateCustomer.mockResolvedValue(null);
      mockTaxEngine.getActiveCases.mockResolvedValue([]);
      mockTaxEngine.processMessage.mockResolvedValue({
        reply: 'Thuế TNCN phải nộp là 1.5 triệu đồng.',
        actions: [],
        references: [],
      });

      const message = {
        channel: 'telegram',
        userId: 'user123',
        chatId: 'chat123',
        userName: 'Test User',
        messageId: 'msg123',
        timestamp: new Date(),
        type: 'text' as const,
        text: 'Tính thuế TNCN lương 20 triệu',
        telegramUsername: 'testuser',
        firstName: 'Test',
        lastName: 'User',
      };

      const sendReplySpy = vi.spyOn(messageRouter as any, 'sendReply').mockResolvedValue(undefined);

      await (messageRouter as any).handleMessage(message);

      // Should process through tax engine
      expect(mockTaxEngine.processMessage).toHaveBeenCalled();
      expect(mockSessionManager.recordUserMessage).toHaveBeenCalledWith('test-session', 'Tính thuế TNCN lương 20 triệu');
      expect(sendReplySpy).toHaveBeenCalled();
    });
  });

  describe('Suggestion Generation', () => {
    it('should add suggestions to tax engine response', async () => {
      const session: SessionData = {
        sessionId: 'test-session',
        userId: 'user123',
        channel: 'telegram',
        customerType: 'individual',
        conversationHistory: [],
        context: {},
        createdAt: new Date().toISOString(),
        lastActiveAt: new Date().toISOString(),
      };

      mockSessionManager.resolveSession.mockResolvedValue(session);
      mockTaxEngine.getOrCreateCustomer.mockResolvedValue(null);
      mockTaxEngine.getActiveCases.mockResolvedValue([]);
      mockTaxEngine.processMessage.mockResolvedValue({
        reply: 'Thuế TNCN phải nộp là 1.5 triệu đồng.',
        actions: [],
        references: [],
      });

      const message = {
        channel: 'telegram',
        userId: 'user123',
        chatId: 'chat123',
        userName: 'Test User',
        messageId: 'msg123',
        timestamp: new Date(),
        type: 'text' as const,
        text: 'Tính thuế TNCN lương 20 triệu',
        telegramUsername: 'testuser',
        firstName: 'Test',
        lastName: 'User',
      };

      const sendReplySpy = vi.spyOn(messageRouter as any, 'sendReply').mockResolvedValue(undefined);

      await (messageRouter as any).handleMessage(message);

      // Check that sendReply was called with a message containing suggestions
      expect(sendReplySpy).toHaveBeenCalled();
      const callArgs = sendReplySpy.mock.calls[0];
      const replyMessage = callArgs[1] as { text: string };

      // Reply should contain the tax engine response
      expect(replyMessage.text).toContain('Thuế TNCN phải nộp là 1.5 triệu đồng.');
      // And should contain suggestions
      expect(replyMessage.text).toContain('Bạn muốn làm gì tiếp theo?');
    });
  });
});