import { IncomingMessage, MessageType } from '../types';

/**
 * Zalo OA Webhook event types
 * Reference: https://developers.zalo.me/docs/api/official-account-api
 */

export interface ZaloWebhookEvent {
  app_id: string;
  sender: {
    id: string;
  };
  recipient: {
    id: string;
  };
  event_name: string;
  message?: ZaloMessagePayload;
  timestamp: string;
}

export interface ZaloMessagePayload {
  msg_id: string;
  text?: string;
  attachments?: ZaloAttachment[];
}

export interface ZaloAttachment {
  type: 'image' | 'file' | 'audio' | 'video' | 'sticker' | 'gif' | 'link';
  payload: {
    url?: string;
    thumbnail?: string;
    description?: string;
    title?: string;
    size?: number;
    name?: string;
  };
}

function mapZaloAttachmentType(type: ZaloAttachment['type']): MessageType {
  switch (type) {
    case 'image':
    case 'gif':
      return 'image';
    case 'file':
      return 'document';
    case 'audio':
      return 'voice';
    case 'sticker':
      return 'sticker';
    default:
      return 'unknown';
  }
}

/**
 * Maps Zalo OA webhook event to unified IncomingMessage format
 */
export function mapZaloMessage(event: ZaloWebhookEvent): IncomingMessage | null {
  // Only handle user_send_text and user_send_image, etc.
  if (!event.event_name.startsWith('user_send_')) return null;

  const messagePayload = event.message;
  if (!messagePayload) return null;

  const base = {
    messageId: messagePayload.msg_id,
    channel: 'zalo' as const,
    userId: event.sender.id,
    chatId: event.sender.id, // In Zalo, chatId = userId for 1:1 conversations
    userName: '', // Zalo doesn't send username in webhook, need to fetch via API
    timestamp: new Date(Number(event.timestamp)),
    raw: event,
  };

  // Text message
  if (event.event_name === 'user_send_text' && messagePayload.text) {
    return {
      ...base,
      type: 'text',
      text: messagePayload.text,
    };
  }

  // Messages with attachments
  if (messagePayload.attachments && messagePayload.attachments.length > 0) {
    const firstAttachment = messagePayload.attachments[0];
    return {
      ...base,
      type: mapZaloAttachmentType(firstAttachment.type),
      text: messagePayload.text,
      attachments: messagePayload.attachments.map((att) => ({
        fileId: messagePayload.msg_id,
        fileUrl: att.payload.url,
        fileName: att.payload.name,
        fileSize: att.payload.size,
      })),
    };
  }

  return {
    ...base,
    type: 'unknown',
  };
}
