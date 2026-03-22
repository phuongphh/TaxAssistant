import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger';
import { IncomingMessage, OutgoingMessage, ChannelAdapter } from '../channels/types';
import { SessionManager } from '../session/manager';
import { SessionData, CustomerProfile, ActiveCase } from '../session/store';
import { TaxEngineClient } from '../grpc/client';
import { TaxEngineError, SessionError } from '../utils/errors';

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

    try {
      // ── 1. Session (single Redis GET) ─────────────────────────────────
      const session = await this.sessionManager.resolveSession(
        message.userId,
        message.channel,
      );

      // ── 2. Local commands — zero gRPC cost ────────────────────────────
      // Check BEFORE fetching the customer profile so /loai and /reset
      // never trigger unnecessary gRPC round-trips.
      const commandResult = await this.handleCommand(message, session);
      if (commandResult) {
        await this.sendReply(message, commandResult);
        logger.info('Command handled', { requestId, elapsedMs: Date.now() - startMs });
        return;
      }

      // ── 3. Parallel setup ─────────────────────────────────────────────
      // a) Customer profile + cases (gRPC, with session-level cache)
      // b) Typing-indicator placeholder (Telegram API round-trip)
      // c) Record user message in history (Redis write — non-blocking)
      if (message.text) {
        this.sessionManager
          .recordUserMessage(session.sessionId, message.text)
          .catch((e) => logger.warn('recordUserMessage failed', { requestId, error: e?.message }));
      }

      const adapter = this.channelAdapters.get(message.channel);
      const [profileResult, streamResult] = await Promise.allSettled([
        this.resolveCustomerContext(message, session),
        adapter?.sendStreamStart ? adapter.sendStreamStart(message.chatId) : Promise.resolve(undefined),
      ]);

      const { customerProfile, activeCases } =
        profileResult.status === 'fulfilled'
          ? profileResult.value
          : { customerProfile: session.customerProfile, activeCases: [] };

      const streamHandle =
        streamResult.status === 'fulfilled' ? streamResult.value : undefined;

      // Persist profile update to session if it changed (non-blocking)
      if (customerProfile?.customerId && customerProfile.customerId !== session.customerId) {
        session.customerId = customerProfile.customerId;
        session.customerProfile = customerProfile;
        if (customerProfile.customerType && customerProfile.customerType !== 'unknown') {
          session.customerType = customerProfile.customerType as SessionData['customerType'];
        }
        this.sessionManager
          .saveSession(session)
          .catch((e) => logger.warn('Session profile sync failed', { requestId, error: e?.message }));
      }

      // ── 4. Resolve text (suggestion shortcuts "1", "2", "3") ──────────
      const resolvedText = this.resolveText(message, session);

      // ── 5. Tax Engine ─────────────────────────────────────────────────
      logger.info('Calling Tax Engine', { requestId, elapsedMs: Date.now() - startMs });
      const engineResponse = await this.taxEngine.processMessage(
        requestId,
        resolvedText,
        session,
        customerProfile,
        activeCases,
      );

      // ── 6. Send reply ─────────────────────────────────────────────────
      const reply = this.buildReply(engineResponse);
      if (streamHandle) {
        await streamHandle.finalize(reply);
      } else {
        await this.sendReply(message, reply);
      }
      logger.info('Reply sent', { requestId, elapsedMs: Date.now() - startMs });

      // ── 7. Post-reply persistence (fire & forget) ─────────────────────
      // These don't affect the user's experience so we don't await them.
      this.sessionManager
        .recordAssistantReply(session.sessionId, engineResponse.reply)
        .catch((e) => logger.warn('recordAssistantReply failed', { requestId, error: e?.message }));

      const quickReplies =
        engineResponse.actions
          ?.filter((a: { actionType: string }) => a.actionType === 'quick_reply')
          .map((a: { payload: string }) => a.payload) ?? [];
      if (quickReplies.length > 0) {
        this.sessionManager
          .updateContext(session.sessionId, { lastSuggestions: quickReplies })
          .catch((e) => logger.warn('updateContext failed', { requestId, error: e?.message }));
      }
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
   * Build an OutgoingMessage from a TaxEngineResponse.
   */
  private buildReply(engineResponse: { reply: string; actions?: Array<{ actionType: string; label: string; payload: string }>; references?: Array<{ title: string }> }): OutgoingMessage {
    const reply: OutgoingMessage = {
      text: engineResponse.reply,
      // Show quick_reply actions as inline buttons.
      quickReplies: engineResponse.actions
        ?.filter((a) => a.actionType === 'quick_reply')
        .map((a) => ({ label: a.label, payload: a.payload })),
    };

    if (engineResponse.references?.length) {
      const refs = engineResponse.references
        .map((r, i) => `[${i + 1}] ${r.title}`)
        .join('\n');
      reply.text += `\n\n📎 Tham khảo:\n${refs}`;
    }

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
