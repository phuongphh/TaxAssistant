// Node 20+ provides native fetch & Headers — no polyfill needed.
import { Telegraf, Context } from 'telegraf';
import { Update } from 'telegraf/types';
import { config } from '../../config';
import { logger } from '../../utils/logger';
import {
  ChannelAdapter,
  IncomingMessage,
  MessageHandler,
  OutgoingMessage,
} from '../types';
import { mapTelegramMessage } from './mapper';

const TELEGRAM_MAX_LENGTH = 4096;

/**
 * Split a long message into chunks that fit Telegram's limit.
 * Splits at paragraph (\n\n), then line (\n), then at the hard limit.
 */
function splitMessage(text: string, maxLen = TELEGRAM_MAX_LENGTH): string[] {
  if (text.length <= maxLen) return [text];

  const chunks: string[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    if (remaining.length <= maxLen) {
      chunks.push(remaining);
      break;
    }

    // Try to split at paragraph break
    let splitIdx = remaining.lastIndexOf('\n\n', maxLen);
    // Fall back to line break
    if (splitIdx <= 0) splitIdx = remaining.lastIndexOf('\n', maxLen);
    // Last resort: hard cut at max length
    if (splitIdx <= 0) splitIdx = maxLen;

    chunks.push(remaining.slice(0, splitIdx));
    remaining = remaining.slice(splitIdx).replace(/^\n+/, '');
  }

  return chunks;
}

export class TelegramAdapter implements ChannelAdapter {
  readonly channel = 'telegram' as const;
  private bot: Telegraf;
  private messageHandler: MessageHandler | null = null;
  private lastUpdateTime = Date.now();
  private watchdogTimer: ReturnType<typeof setInterval> | null = null;

  /** Check if bot polling is considered alive (received update within threshold) */
  isPollingHealthy(thresholdMs = 120_000): boolean {
    return Date.now() - this.lastUpdateTime < thresholdMs;
  }

  constructor() {
    this.bot = new Telegraf(config.telegram.botToken);
  }

  async initialize(): Promise<void> {
    // === Global error handler — catches middleware & handler errors ===
    this.bot.catch((err: unknown) => {
      logger.error('Telegraf caught error', { error: err });
    });

    // Register message handler
    this.bot.on('message', async (ctx: Context<Update.MessageUpdate>) => {
      this.lastUpdateTime = Date.now();
      try {
        const message = mapTelegramMessage(ctx);
        if (message && this.messageHandler) {
          await this.messageHandler(message);
        }
      } catch (error) {
        logger.error('Error processing Telegram message', { error });
      }
    });

    // Handle inline keyboard button clicks (callback_query)
    this.bot.on('callback_query', async (ctx) => {
      this.lastUpdateTime = Date.now();
      try {
        // Acknowledge the callback to remove loading state on the button
        await ctx.answerCbQuery();

        const cbQuery = ctx.callbackQuery;
        if (!('data' in cbQuery) || !cbQuery.data) return;

        const from = cbQuery.from;
        const chatId = cbQuery.message?.chat?.id;
        if (!chatId) return;

        const firstName = from.first_name || undefined;
        const lastName = from.last_name || undefined;
        const telegramUsername = from.username || undefined;
        const message: IncomingMessage = {
          channel: 'telegram',
          userId: String(from.id),
          chatId: String(chatId),
          userName: [firstName, lastName].filter(Boolean).join(' ') || telegramUsername || String(from.id),
          telegramUsername,
          firstName,
          lastName,
          messageId: String(cbQuery.message?.message_id ?? Date.now()),
          timestamp: new Date(),
          type: 'text',
          text: cbQuery.data,
          raw: cbQuery,
        };

        if (this.messageHandler) {
          await this.messageHandler(message);
        }
      } catch (error) {
        logger.error('Error processing Telegram callback query', { error });
      }
    });

    // Bot commands
    this.bot.command('start', async (ctx) => {
      try {
        await ctx.reply(
          'Xin chào! Tôi là Trợ lý Thuế ảo. 🇻🇳\n\n' +
          'Tôi có thể hỗ trợ bạn các vấn đề về:\n' +
          '• Thuế GTGT (VAT)\n' +
          '• Thuế thu nhập doanh nghiệp (CIT)\n' +
          '• Thuế thu nhập cá nhân (PIT)\n' +
          '• Thuế môn bài\n' +
          '• Kê khai và nộp thuế\n\n' +
          'Hãy gửi câu hỏi của bạn để tôi hỗ trợ!',
        );
        logger.info('/start command processed successfully', {
          userId: ctx.from?.id,
          chatId: ctx.chat?.id
        });
      } catch (error) {
        logger.error('Failed to process /start command', {
          error,
          userId: ctx.from?.id,
          chatId: ctx.chat?.id
        });
        // Try to send error message to user
        try {
          await ctx.reply('Xin lỗi, có lỗi xảy ra khi xử lý lệnh /start. Vui lòng thử lại sau.');
        } catch {
          // Ignore if we can't send error message
        }
      }
    });

    this.bot.command('help', async (ctx) => {
      await ctx.reply(
        'Các lệnh hỗ trợ:\n' +
        '/start - Bắt đầu cuộc trò chuyện\n' +
        '/help - Hiển thị trợ giúp\n' +
        '/loai <SME|hogiadia|cathe> - Đặt loại khách hàng\n' +
        '/reset - Đặt lại phiên trò chuyện\n\n' +
        'Hoặc bạn có thể gửi trực tiếp câu hỏi về thuế.',
      );
    });

    // Setup webhook or polling.
    // Prefer webhook when TELEGRAM_WEBHOOK_URL is set (any environment).
    // Webhook is push-based → no long-polling, no watchdog, no burst API
    // calls that can interfere with other Telegram bots on the same host.
    if (config.telegram.webhookUrl) {
      await this.bot.telegram.setWebhook(config.telegram.webhookUrl, {
        secret_token: config.telegram.webhookSecret,
      });
      logger.info('Telegram webhook set', { url: config.telegram.webhookUrl });
    } else {
      // Fallback: polling mode (local dev without tunnel).
      await this.bot.telegram.deleteWebhook({ drop_pending_updates: false });
      this.bot.launch({ dropPendingUpdates: false }).catch((err) => {
        logger.error('Telegram polling error', { error: err });
      });
      logger.info('Telegram bot started in polling mode');

      // Watchdog: restart polling if no updates for 10 minutes.
      // Threshold is generous to avoid unnecessary restarts when the bot
      // simply has no incoming messages (previously 2 min — too aggressive,
      // caused burst API calls every 60s that interfered with other bots).
      this.watchdogTimer = setInterval(async () => {
        if (!this.isPollingHealthy(600_000)) {
          logger.warn('Telegram polling watchdog: no updates for 10 min, restarting polling');
          try {
            this.bot.stop('SIGTERM');
            await this.bot.telegram.deleteWebhook({ drop_pending_updates: false });
            await this.bot.launch({ dropPendingUpdates: false });
            this.lastUpdateTime = Date.now();
            logger.info('Telegram polling restarted by watchdog');
          } catch (err) {
            logger.error('Watchdog failed to restart polling', { error: err });
          }
        }
      }, 300_000); // Check every 5 minutes instead of every 60s
    }
  }

  onMessage(handler: MessageHandler): void {
    this.messageHandler = handler;
  }

  async sendMessage(chatId: string, message: OutgoingMessage): Promise<void> {
    const telegramChatId = Number(chatId);

    // Split long text into multiple messages (Telegram 4096 char limit)
    if (message.text) {
      const chunks = splitMessage(message.text);
      const keyboard = message.quickReplies?.map((qr) => [{
        text: qr.label,
        callback_data: qr.payload,
      }]);

      for (let i = 0; i < chunks.length; i++) {
        const isLast = i === chunks.length - 1;
        const replyMarkup = isLast && keyboard
          ? { reply_markup: { inline_keyboard: keyboard } }
          : {};

        try {
          // Try HTML parse mode first for nice formatting
          await this.bot.telegram.sendMessage(telegramChatId, chunks[i], {
            parse_mode: 'HTML',
            ...replyMarkup,
          });
        } catch (htmlError: any) {
          // If HTML parsing fails (LLM response contains <, >, & etc.),
          // fall back to plain text
          if (htmlError?.message?.includes("can't parse entities")) {
            logger.warn('Telegram HTML parse failed, falling back to plain text', {
              chatId,
              chunkIndex: i,
              error: htmlError.message,
            });
            await this.bot.telegram.sendMessage(telegramChatId, chunks[i], {
              ...replyMarkup,
            });
          } else {
            throw htmlError;
          }
        }
      }
    }

    // Send attachments
    if (message.attachments) {
      for (const attachment of message.attachments) {
        if (attachment.type === 'document') {
          await this.bot.telegram.sendDocument(telegramChatId, attachment.url, {
            caption: attachment.caption,
          });
        } else if (attachment.type === 'image') {
          await this.bot.telegram.sendPhoto(telegramChatId, attachment.url, {
            caption: attachment.caption,
          });
        }
      }
    }
  }

  /** Returns the Express webhook callback for production use */
  getWebhookCallback() {
    return this.bot.webhookCallback('/webhook/telegram', {
      secretToken: config.telegram.webhookSecret,
    });
  }

  async shutdown(): Promise<void> {
    if (this.watchdogTimer) {
      clearInterval(this.watchdogTimer);
      this.watchdogTimer = null;
    }
    try {
      logger.info('Shutting down Telegram bot gracefully...');

      // Stop receiving new updates first
      this.bot.stop('SIGTERM');

      // Delete webhook to clean up Telegram state (prevents conflict on restart)
      try {
        await this.bot.telegram.deleteWebhook({ drop_pending_updates: true });
      } catch (webhookError) {
        logger.warn('Could not delete webhook during shutdown', { error: webhookError });
      }

      // Wait a moment for cleanup
      await new Promise(resolve => setTimeout(resolve, 1000));

      logger.info('Telegram bot stopped gracefully');
    } catch (error) {
      logger.error('Error during Telegram bot shutdown', { error });
      // Force stop if graceful shutdown fails
      try {
        this.bot.stop();
      } catch {
        // Ignore any further errors
      }
    }
  }
}
