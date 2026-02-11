import { v4 as uuidv4 } from 'uuid';
import { logger } from '../utils/logger';
import { IncomingMessage, OutgoingMessage, ChannelAdapter } from '../channels/types';
import { SessionManager } from '../session/manager';
import { SessionData } from '../session/store';
import { TaxEngineClient } from '../grpc/client';

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

    logger.debug('Processing message', {
      requestId,
      channel: message.channel,
      userId: message.userId,
      type: message.type,
    });

    try {
      // 1. Resolve session
      const session = await this.sessionManager.resolveSession(
        message.userId,
        message.channel,
      );

      // 2. Check for bot commands
      const commandResult = await this.handleCommand(message, session);
      if (commandResult) {
        await this.sendReply(message, commandResult);
        return;
      }

      // 3. Record user message
      if (message.text) {
        await this.sessionManager.recordUserMessage(session.sessionId, message.text);
      }

      // 4. Route to Tax Engine
      const engineResponse = await this.taxEngine.processMessage(
        requestId,
        message.text || `[${message.type}]`,
        session,
      );

      // 5. Build and send reply
      const reply: OutgoingMessage = {
        text: engineResponse.reply,
        quickReplies: engineResponse.actions
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

      await this.sendReply(message, reply);

      // 6. Record assistant reply
      await this.sessionManager.recordAssistantReply(session.sessionId, engineResponse.reply);
    } catch (error) {
      logger.error('Message processing failed', { requestId, error });

      await this.sendReply(message, {
        text: 'Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.',
      });
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
