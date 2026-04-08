import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger';
import { IncomingMessage, OutgoingMessage, ChannelAdapter } from '../channels/types';
import { SessionManager } from '../session/manager';
import { SessionData, CustomerProfile, ActiveCase, Suggestion } from '../session/store';
import { TaxEngineClient } from '../grpc/client';
import { TaxEngineError, SessionError } from '../utils/errors';
import {
  generateSuggestions,
  detectContext,
  formatSuggestions,
  isSuggestionChoice,
  getSuggestionAction,
  updateContextFromAction,
  ConversationContext
} from '../services/suggestionGenerator';

/**
 * Message Router - the central orchestrator
 *
 * Flow:
 * 1. Receive unified IncomingMessage from any channel
 * 2. Resolve/create session
 * 3. Handle commands (if applicable)
 * 4. Route to Tax Engine via gRPC
 * 5. Send response back through the originating channel
 */
export class MessageRouter {
  private channelAdapters: Map<string, ChannelAdapter> = new Map();
  /** Tracks users currently being processed to prevent concurrent request overlaps. */
  private processingUsers: Set<string> = new Set();

  constructor(
    private sessionManager: SessionManager,
    private taxEngine: TaxEngineClient,
  ) {}

  /**
   * Register a channel adapter
   */
  registerChannel(adapter: ChannelAdapter): void {
    this.channelAdapters.set(adapter.channel, adapter);

    // Wire up the message handler
    adapter.onMessage(async (message) => {
      await this.handleMessage(message);
    });

    logger.info(`Channel registered: ${adapter.channel}`);
  }

  /**
   * Main message processing pipeline — optimized for low latency.
   *
   * Design principles:
   *  1. Commands are handled BEFORE any gRPC call (zero engine cost).
   *  2. Customer-profile fetch and typing-indicator are fired in PARALLEL.
   *  3. Profile is cached in the session so repeat messages skip getOrCreateCustomer.
   *  4. Post-reply persistence (history, context) is fire-and-forget so the
   *     user's reply arrives as soon as the engine responds.
   */
  private async handleMessage(message: IncomingMessage): Promise<void> {
    const requestId = uuidv4();
    const startMs = Date.now();

    logger.info('Processing message', {
      requestId,
      channel: message.channel,
      userId: message.userId,
      type: message.type,
      textPreview: message.text?.slice(0, 80),
    });

    // ── Concurrency guard ─────────────────────────────────────────────────
    // Reject a second message from the same user while the first is still
    // being processed. This prevents "Lịch thuế" + "Tính thuế" from both
    // flying through the engine in parallel and overlapping in the chat.
    const userKey = `${message.channel}:${message.userId}`;
    if (this.processingUsers.has(userKey)) {
      logger.info('Concurrent request blocked for user', { requestId, userKey });
      await this.sendReply(message, {
        text: '⏳ Đang xử lý tin nhắn trước, vui lòng đợi giây lát...',
      });
      return;
    }
    this.processingUsers.add(userKey);

    try {
      // ── 1. Session (single Redis GET) ─────────────────────────────────
      const session = await this.sessionManager.resolveSession(
        message.userId,
        message.channel,
      );

      logger.info('Session resolved: %s, history=%d entries',
        session.sessionId, session.conversationHistory?.length ?? 0);

      // 2. Resolve customer profile (persistent, DB-backed)
      let customerProfile: CustomerProfile | undefined;
      let activeCases: ActiveCase[] = [];
      try {
        customerProfile = await this.taxEngine.getOrCreateCustomer(
          message.channel,
          message.userId,
          {
            username: message.telegramUsername,
            firstName: message.firstName,
            lastName: message.lastName,
          },
        );
        // Sync customer profile data into session and persist to Redis
        if (customerProfile?.customerId) {
          session.customerId = customerProfile.customerId;
          session.customerProfile = customerProfile;
          // Sync customer type from profile → session
          if (customerProfile.customerType && customerProfile.customerType !== 'unknown') {
            session.customerType = customerProfile.customerType as SessionData['customerType'];
          }
          // Persist session so subsequent Redis reads see updated values
          await this.sessionManager.saveSession(session);
        }
        // Get active support cases
        if (customerProfile?.customerId) {
          activeCases = await this.taxEngine.getActiveCases(customerProfile.customerId);
        }
      } catch (profileError: any) {
        logger.warn('Customer profile resolution failed, continuing without profile', {
          error: profileError?.message,
          userId: message.userId,
        });
      }

      // 3. Check if user input is a suggestion choice
      // NOTE: 'completed' is excluded — it's a legacy step meaning step 1 is done.
      // Users at 'completed' should be able to use the service freely; the engine
      // no longer intercepts them for step 2 onboarding.
      const ONBOARDING_ACTIVE_STEPS = new Set([
        'new', 'collecting_type', 'collecting_info',
        'collecting_tax_period', 'collecting_employees'
      ]);
      const isInOnboarding = ONBOARDING_ACTIVE_STEPS.has(customerProfile?.onboardingStep ?? '');

      if (!isInOnboarding && message.text && session.pendingSuggestions && isSuggestionChoice(message.text)) {
        const action = getSuggestionAction(message.text.trim(), session.pendingSuggestions);
        if (action) {
          // Update context based on chosen suggestion
          const newContext = updateContextFromAction(action);
          session.currentContext = newContext;

          // Clear pending suggestions since user made a choice
          session.pendingSuggestions = [];
          await this.sessionManager.saveSession(session);

          // Process the suggestion action
          const suggestionResponse = await this.processSuggestionAction(action, session, message);
          if (suggestionResponse) {
            await this.sendReply(message, suggestionResponse);
            return;
          }
        }
      }

      // 4. Check for bot commands
      const commandResult = await this.handleCommand(message, session);
      if (commandResult) {
        await this.sendReply(message, commandResult);
        logger.info('Command handled', { requestId, elapsedMs: Date.now() - startMs });
        return;
      }

      // 5. Record user message
      if (message.text) {
        this.sessionManager
          .recordUserMessage(session.sessionId, message.text)
          .catch((e) => logger.warn('recordUserMessage failed', { requestId, error: e?.message }));
      }

      // 5.5 Clear pending suggestions if user sends a new query (not a suggestion choice)
      // This ensures suggestions are context-aware for the new query
      if (session.pendingSuggestions && message.text && !isSuggestionChoice(message.text)) {
        session.pendingSuggestions = [];
        session.currentContext = undefined;
      }

      // Resolve text (suggestion shortcuts "1", "2", "3")
      const resolvedText = this.resolveText(message, session);

      // 6. Route to Tax Engine with full context
      logger.info('Calling Tax Engine', { requestId, elapsedMs: Date.now() - startMs });
      const engineResponse = await this.taxEngine.processMessage(
        requestId,
        resolvedText,
        session,
        customerProfile,
        activeCases,
      );

      // 7. Build reply
      const reply: OutgoingMessage = {
        text: engineResponse?.reply ?? '',
        quickReplies: engineResponse?.actions
          ?.filter((a) => a.actionType === 'quick_reply')
          .map((a) => ({ label: a.label, payload: a.payload })),
      };

      // Add references as footer if available
      if (engineResponse.references?.length > 0) {
        const refs = engineResponse.references
          .map((r, i) => `[${i + 1}] ${r.title}`)
          .join('\n');
        reply.text += `\n\n📎 Tham khảo:\n${refs}`;
      }
      logger.info('Reply built', { requestId, elapsedMs: Date.now() - startMs });

      // 7.5 Generate and add context-aware suggestions
      // Only generate suggestions when engine didn't provide its own navigation buttons
      const hasEngineActions = (reply.quickReplies?.length ?? 0) > 0;
      if (!hasEngineActions) {
        const context = detectContext(engineResponse.reply);
        session.currentContext = context;
        const suggestions = generateSuggestions(context);
        session.pendingSuggestions = suggestions;
        if (suggestions.length > 0) {
          reply.text += formatSuggestions(suggestions);
        }
      } else {
        // Clear stale suggestions so the NEXT button click isn't misrouted
        session.pendingSuggestions = [];
        session.currentContext = undefined;
      }

      await this.sessionManager.saveSession(session);
      await this.sendReply(message, reply);
      logger.info('Reply sent', { requestId, elapsedMs: Date.now() - startMs });

      // 8. Record assistant reply (fire & forget)
      this.sessionManager
        .recordAssistantReply(session.sessionId, engineResponse.reply)
        .catch((e) => logger.warn('recordAssistantReply failed', { requestId, error: e?.message }));
    } catch (error: any) {
      const errorName = error?.name ?? 'UnknownError';
      const errorMsg = error?.message ?? String(error);
      logger.error('Message processing failed', {
        requestId,
        errorName,
        errorMsg,
        channel: message.channel,
        userId: message.userId,
        messagePreview: message.text?.slice(0, 80),
      });
      await this.sendReply(message, { text: this.getErrorMessage(error, errorMsg) });
    } finally {
      this.processingUsers.delete(userKey);
    }
  }

  /**
   * Resolve customer profile and active cases with session-level caching.
   *
   * - Cache hit  (profile already in session): skip getOrCreateCustomer,
   *   only fetch fresh active cases.
   * - Cache miss (first message from this user): fetch profile then cases.
   *
   * Errors are swallowed and logged so a DB hiccup never breaks the
   * conversation — the engine will still respond without profile context.
   */
  private async resolveCustomerContext(
    message: IncomingMessage,
    session: SessionData,
  ): Promise<{ customerProfile: CustomerProfile | undefined; activeCases: ActiveCase[] }> {
    try {
      if (session.customerProfile?.customerId) {
        // Cache hit — only need fresh cases
        const activeCases = await this.taxEngine
          .getActiveCases(session.customerProfile.customerId)
          .catch(() => []);
        return { customerProfile: session.customerProfile, activeCases };
      }

      // Cache miss — first contact with this user
      const customerProfile = await this.taxEngine.getOrCreateCustomer(
        message.channel,
        message.userId,
        {
          username: message.telegramUsername,
          firstName: message.firstName,
          lastName: message.lastName,
        },
      );

      const activeCases = customerProfile?.customerId
        ? await this.taxEngine.getActiveCases(customerProfile.customerId).catch(() => [])
        : [];

      return { customerProfile, activeCases };
    } catch (profileError: any) {
      logger.warn('Customer profile resolution failed, continuing without profile', {
        error: profileError?.message,
        userId: message.userId,
      });
      return { customerProfile: undefined, activeCases: [] };
    }
  }

  /**
   * Resolve suggestion shortcuts ("1", "2", "3") to their full text.
   * Falls back to the original message text if no match found.
   */
  private resolveText(message: IncomingMessage, session: SessionData): string {
    const raw = message.text || `[${message.type}]`;
    const trimmed = raw.trim();

    if (/^[1-3]$/.test(trimmed)) {
      const suggestions = session.context?.lastSuggestions as string[] | undefined;
      if (suggestions && suggestions.length >= Number(trimmed)) {
        const resolved = suggestions[Number(trimmed) - 1];
        logger.info('Resolved suggestion shortcut: "%s" → "%s"', trimmed, resolved);
        return resolved;
      }
    }

    return raw;
  }

  /**
   * Handle bot commands (e.g., /loai, /reset)
   */
  private async handleCommand(
    message: IncomingMessage,
    session: SessionData,
  ): Promise<OutgoingMessage | null> {
    if (!message.text || !message.text.startsWith('/')) return null;

    const [command, ...args] = message.text.split(' ');

    switch (command) {
      case '/loai': {
        const typeMap: Record<string, SessionData['customerType']> = {
          sme: 'sme',
          hogiadia: 'household',
          cathe: 'individual',
        };
        const type = typeMap[args[0]?.toLowerCase()];
        if (type) {
          await this.sessionManager.setCustomerType(session.sessionId, type);
          const labels: Record<string, string> = {
            sme: 'Doanh nghiệp vừa và nhỏ (SME)',
            household: 'Hộ gia đình',
            individual: 'Cá thể kinh doanh',
          };
          return { text: `Đã cập nhật loại khách hàng: ${labels[type]}` };
        }
        return {
          text: 'Sử dụng: /loai <SME|hogiadia|cathe>\n\nVí dụ: /loai SME',
          quickReplies: [
            { label: 'SME', payload: '/loai SME' },
            { label: 'Hộ gia đình', payload: '/loai hogiadia' },
            { label: 'Cá thể KD', payload: '/loai cathe' },
          ],
        };
      }

      case '/reset': {
        await this.sessionManager.resetSession(session.sessionId);
        return { text: 'Phiên trò chuyện đã được đặt lại. Bạn có thể bắt đầu câu hỏi mới.' };
      }

      // /profile is handled by the Python engine (intent classifier)
      case '/profile':
        return null;

      // /start and /help are handled by individual channel adapters
      default:
        return null;
    }
  }

  /**
   * Process suggestion action and generate appropriate response
   */
  private async processSuggestionAction(
    action: string,
    session: SessionData,
    message: IncomingMessage
  ): Promise<OutgoingMessage | null> {
    logger.info('Processing suggestion action', {
      action,
      sessionId: session.sessionId,
      userId: message.userId,
    });

    // Map action to appropriate response
    const actionResponses: Record<string, string> = {
      'calculate_another_tax': 'Bạn muốn tính loại thuế nào? (GTGT, TNDN, TNCN, Môn bài)',
      'show_declaration_guide': 'Dưới đây là hướng dẫn kê khai chi tiết:\n1. Chuẩn bị hồ sơ chứng từ\n2. Điền thông tin vào tờ khai\n3. Nộp tờ khai và chờ xác nhận',
      'check_deadline': 'Bạn muốn kiểm tra thời hạn nộp cho loại thuế nào?',
      'check_other_deadlines': 'Dưới đây là thời hạn nộp các loại thuế chính:\n- Thuế môn bài: 30/1 hàng năm\n- Thuế GTGT: 20th của tháng sau\n- Thuế TNDN tạm tính: 30th hàng quý\n- Thuế TNCN: 20th của tháng sau',
      'calculate_late_fee': 'Để tính phí chậm nộp, vui lòng cung cấp:\n- Số tiền thuế phải nộp\n- Ngày hạn nộp\n- Ngày thực tế nộp',
      'show_online_payment_guide': 'Hướng dẫn nộp thuế trực tuyến:\n1. Đăng ký tài khoản trên trang web của Tổng cục Thuế\n2. Tạo giao dịch nộp thuế\n3. Thanh toán qua ngân hàng hoặc ví điện tử',
      'find_related_documents': 'Bạn muốn tìm văn bản pháp luật liên quan đến lĩnh vực nào?',
      'show_application_guide': 'Hướng dẫn áp dụng văn bản pháp luật:\n1. Xác định phạm vi áp dụng\n2. Kiểm tra điều kiện áp dụng\n3. Thực hiện theo quy định',
      'check_latest_documents': 'Tôi sẽ kiểm tra các văn bản pháp luật mới nhất về thuế cho bạn.',
      'show_document_preparation': 'Hướng dẫn chuẩn bị hồ sơ đăng ký MST:\n1. CMND/CCCD bản sao công chứng\n2. Đơn đăng ký theo mẫu\n3. Giấy tờ chứng minh địa điểm kinh doanh',
      'register_online': 'Hướng dẫn đăng ký MST trực tuyến:\n1. Truy cập trang web dichvucong.gdt.gov.vn\n2. Điền thông tin theo hướng dẫn\n3. Nộp hồ sơ và chờ phê duyệt',
      'check_registration_status': 'Để kiểm tra tình trạng hồ sơ, vui lòng cung cấp số hồ sơ hoặc mã tra cứu.',
      'download_form': 'Bạn cần tải mẫu tờ khai cho loại thuế nào?',
      'show_filling_guide': 'Hướng dẫn điền tờ khai chi tiết:\n1. Điền đầy đủ thông tin cá nhân/doanh nghiệp\n2. Kê khai doanh thu, chi phí\n3. Tính toán số thuế phải nộp',
      'check_common_errors': 'Các lỗi thường gặp khi kê khai:\n1. Sai thông tin cá nhân/doanh nghiệp\n2. Tính toán sai số thuế\n3. Nộp chậm hạn quy định',
      'calculate_tax': 'Bạn muốn tính loại thuế nào? (GTGT, TNDN, TNCN, Môn bài)',
      'check_deadlines': 'Bạn muốn xem hạn nộp cho loại thuế nào?',
      'search_legal_docs': 'Bạn muốn tra cứu văn bản pháp luật nào về thuế?',
    };

    const responseText = actionResponses[action] || 'Tôi đã xử lý yêu cầu của bạn. Bạn cần hỗ trợ gì thêm?';

    // Generate new suggestions for the response
    const context = updateContextFromAction(action);
    const suggestions = generateSuggestions(context);

    const reply: OutgoingMessage = {
      text: responseText + formatSuggestions(suggestions),
    };

    // Update session with new context and suggestions
    session.currentContext = context;
    session.pendingSuggestions = suggestions;
    await this.sessionManager.saveSession(session);

    return reply;
  }

  /**
   * Map error to a user-friendly Vietnamese message.
   */
  private getErrorMessage(error: any, errorMsg: string): string {
    if (error instanceof TaxEngineError) {
      if (errorMsg.includes('DEADLINE_EXCEEDED')) {
        return 'Hệ thống đang xử lý lâu hơn dự kiến. Vui lòng thử lại hoặc đặt câu hỏi ngắn gọn hơn.';
      }
      // Check for specific LLM error keywords forwarded from Python engine
      const msg = errorMsg.toLowerCase();
      if (msg.includes('credit') || msg.includes('billing') || msg.includes('payment')) {
        return (
          '⚠️ Hệ thống AI tạm thời không khả dụng do hết hạn mức sử dụng.\n\n' +
          'Bạn vẫn có thể sử dụng các tính năng tính thuế cơ bản (VD: "tính thuế GTGT 500 triệu").\n' +
          'Xin lỗi vì sự bất tiện này!'
        );
      }
      if (msg.includes('rate limit') || msg.includes('rate_limit')) {
        return 'Hệ thống đang nhận nhiều yêu cầu cùng lúc. Vui lòng thử lại sau 1-2 phút.';
      }
      if (msg.includes('overload')) {
        return 'Hệ thống AI đang quá tải tạm thời. Vui lòng thử lại sau ít phút.';
      }
      return 'Hệ thống tư vấn thuế tạm thời không khả dụng. Vui lòng thử lại sau ít phút.';
    }

    if (error instanceof SessionError) {
      return 'Phiên làm việc gặp lỗi. Vui lòng gửi /reset để bắt đầu lại.';
    }

    return 'Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.';
  }

  /**
   * Send reply through the appropriate channel adapter
   */
  private async sendReply(originalMessage: IncomingMessage, reply: OutgoingMessage): Promise<void> {
    const adapter = this.channelAdapters.get(originalMessage.channel);
    if (!adapter) {
      logger.error('No adapter found for channel', { channel: originalMessage.channel });
      return;
    }

    await adapter.sendMessage(originalMessage.chatId, reply);
  }
}
