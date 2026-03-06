import { Context } from 'telegraf';
import { Message, Update } from 'telegraf/types';
import { IncomingMessage, MessageAttachment, MessageType } from '../types';

/**
 * Maps Telegram message to unified IncomingMessage format
 */
export function mapTelegramMessage(ctx: Context<Update.MessageUpdate>): IncomingMessage | null {
  const msg = ctx.message;
  if (!msg) return null;

  const userId = String(msg.from.id);
  const chatId = String(msg.chat.id);
  const firstName = msg.from.first_name || undefined;
  const lastName = msg.from.last_name || undefined;
  const telegramUsername = msg.from.username || undefined;
  const userName = [firstName, lastName].filter(Boolean).join(' ') || telegramUsername || userId;

  const base = {
    channel: 'telegram' as const,
    userId,
    chatId,
    userName,
    telegramUsername,
    firstName,
    lastName,
    timestamp: new Date(msg.date * 1000),
    raw: msg,
  };

  // Text message
  if ('text' in msg && msg.text) {
    return {
      ...base,
      messageId: String(msg.message_id),
      type: 'text',
      text: msg.text,
    };
  }

  // Photo
  if ('photo' in msg && msg.photo) {
    const largest = msg.photo[msg.photo.length - 1];
    return {
      ...base,
      messageId: String(msg.message_id),
      type: 'image',
      text: (msg as Message.PhotoMessage).caption,
      attachments: [{
        fileId: largest.file_id,
        mimeType: 'image/jpeg',
        fileSize: largest.file_size,
      }],
    };
  }

  // Document
  if ('document' in msg && msg.document) {
    return {
      ...base,
      messageId: String(msg.message_id),
      type: 'document',
      text: (msg as Message.DocumentMessage).caption,
      attachments: [{
        fileId: msg.document.file_id,
        mimeType: msg.document.mime_type,
        fileName: msg.document.file_name,
        fileSize: msg.document.file_size,
      }],
    };
  }

  // Voice
  if ('voice' in msg && msg.voice) {
    return {
      ...base,
      messageId: String(msg.message_id),
      type: 'voice',
      attachments: [{
        fileId: msg.voice.file_id,
        mimeType: msg.voice.mime_type || 'audio/ogg',
        fileSize: msg.voice.file_size,
      }],
    };
  }

  // Unknown message type
  return {
    ...base,
    messageId: String(msg.message_id),
    type: 'unknown',
  };
}

/**
 * Map unified MessageType to Telegram-specific info
 */
export function getMessageTypeLabel(type: MessageType): string {
  const labels: Record<MessageType, string> = {
    text: 'tin nhắn văn bản',
    image: 'hình ảnh',
    document: 'tài liệu',
    voice: 'tin nhắn thoại',
    location: 'vị trí',
    sticker: 'sticker',
    unknown: 'không xác định',
  };
  return labels[type];
}
