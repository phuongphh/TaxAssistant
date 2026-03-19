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
   * Main message processing pipeline
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
      // 1. Resolve session
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

      // 3. Check for bot commands
      const commandResult = await this.handleCommand(message, session);
      if (commandResult) {
        await this.sendReply(message, commandResult);
        return;
      }

      // 3.5. Resolve suggestion shortcuts ("1", "2", "3")
      let resolvedText = message.text || `[${message.type}]`;
      const trimmed = resolvedText.trim();
      if (/^[1-3]$/.test(trimmed)) {
        const suggestions = session.context?.lastSuggestions as string[] | undefined;
        if (suggestions && suggestions.length >= Number(trimmed)) {
          resolvedText = suggestions[Number(trimmed) - 1];
          logger.info('Resolved suggestion shortcut: "%s" → "%s"', trimmed, resolvedText);
        }
      }

      // 4. Record user message
      if (message.text) {
        await this.sessionManager.recordUserMessage(session.sessionId, message.text);
      }

      // 5. Route to Tax Engine with full context
      // Always use the unary processMessage RPC — it has the complete
      // engine pipeline (onboarding, intent routing, RAG, fallbacks,
      // timeout handling).  The streaming handle is used only for UX:
      // show a "processing" placeholder while waiting for the response.
      const adapter = this.channelAdapters.get(message.channel);
      const streamHandle = adapter?.sendStreamStart
        ? await adapter.sendStreamStart(message.chatId)
        : undefined;

      const engineResponse = await this.taxEngine.processMessage(
        requestId,
        resolvedText,
        session,
        customerProfile,
        activeCases,
      );

      // 6. Build and send reply (filter out text_suggestion actions)
      const reply = this.buildReply(engineResponse);

      if (streamHandle) {
        // Replace the "💭 Đang xử lý..." placeholder with the final reply
        await streamHandle.finalize(reply);
      } else {
        await this.sendReply(message, reply);
      }

      // 7. Store suggestions in session for next-turn shortcut resolution
      const textSuggestions = engineResponse.actions
        ?.filter((a: { actionType: string }) => a.actionType === 'text_suggestion')
        .map((a: { payload: string }) => a.payload) ?? [];
      if (textSuggestions.length > 0) {
        await this.sessionManager.updateContext(session.sessionId, { lastSuggestions: textSuggestions });
      }

      // 8. Record assistant reply
      await this.sessionManager.recordAssistantReply(session.sessionId, engineResponse.reply);
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

      const userMessage = this.getErrorMessage(error, errorMsg);
      await this.sendReply(message, { text: userMessage });
    }
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
      // Only show quick_reply actions as inline buttons; text_suggestion
      // actions are rendered as numbered text in the reply body itself.
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
