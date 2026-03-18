/**
 * Unified message format across all messaging channels.
 * Each channel adapter maps platform-specific messages to this format.
 */

export type ChannelType = 'telegram' | 'zalo' | 'whatsapp';

export type MessageType = 'text' | 'image' | 'document' | 'voice' | 'location' | 'sticker' | 'unknown';

export interface IncomingMessage {
  /** Unique message ID from the source platform */
  messageId: string;

  /** Source channel */
  channel: ChannelType;

  /** User identifier on the platform */
  userId: string;

  /** Display name of the user (full name or computed) */
  userName: string;

  /** Platform @username (e.g., Telegram username, may be undefined) */
  telegramUsername?: string;

  /** First name from platform profile */
  firstName?: string;

  /** Last name from platform profile */
  lastName?: string;

  /** Conversation/chat ID */
  chatId: string;

  /** Message type */
  type: MessageType;

  /** Text content (for text messages) */
  text?: string;

  /** Attachments (images, documents, etc.) */
  attachments?: MessageAttachment[];

  /** Original raw message from the platform (for debugging) */
  raw?: unknown;

  /** Timestamp */
  timestamp: Date;
}

export interface MessageAttachment {
  fileId: string;
  fileUrl?: string;
  mimeType?: string;
  fileName?: string;
  fileSize?: number;
}

export interface OutgoingMessage {
  /** Text reply */
  text: string;

  /** Quick reply buttons */
  quickReplies?: QuickReply[];

  /** Attachments to send back */
  attachments?: OutgoingAttachment[];
}

export interface QuickReply {
  label: string;
  payload: string;
}

export interface OutgoingAttachment {
  type: 'image' | 'document';
  url: string;
  caption?: string;
}

/**
 * Channel adapter interface - each platform must implement this
 */
export interface ChannelAdapter {
  /** Channel identifier */
  readonly channel: ChannelType;

  /** Initialize the channel (setup webhooks, etc.) */
  initialize(): Promise<void>;

  /** Send a message to a user */
  sendMessage(chatId: string, message: OutgoingMessage): Promise<void>;

  /**
   * Send an initial "typing" placeholder and return a handle to update it
   * progressively as streaming chunks arrive.  If the channel does not
   * support message editing, returns undefined and the caller should
   * fall back to assembling the full reply first.
   */
  sendStreamStart?(chatId: string): Promise<StreamHandle | undefined>;

  /** Register a handler for incoming messages */
  onMessage(handler: MessageHandler): void;

  /** Graceful shutdown */
  shutdown(): Promise<void>;
}

/**
 * Handle returned by sendStreamStart for progressive message updates.
 */
export interface StreamHandle {
  /** Append text and update the displayed message */
  update(text: string): Promise<void>;
  /** Finalize the message (add quick replies, references, etc.) */
  finalize(message: OutgoingMessage): Promise<void>;
}

export type MessageHandler = (message: IncomingMessage) => Promise<void>;
