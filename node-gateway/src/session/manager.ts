import { logger } from '../utils/logger';
import { SessionStore, SessionData, ConversationEntry } from './store';

/**
 * Session manager - high-level session operations
 * Coordinates between channel messages and session persistence
 */
export class SessionManager {
  constructor(private store: SessionStore) {}

  /**
   * Get or create session for an incoming message
   */
  async resolveSession(userId: string, channel: string): Promise<SessionData> {
    return this.store.getOrCreate(userId, channel);
  }

  /**
   * Record a user message in conversation history
   */
  async recordUserMessage(sessionId: string, content: string): Promise<void> {
    const entry: ConversationEntry = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    await this.store.addConversationEntry(sessionId, entry);
  }

  /**
   * Record an assistant reply in conversation history
   */
  async recordAssistantReply(sessionId: string, content: string): Promise<void> {
    const entry: ConversationEntry = {
      role: 'assistant',
      content,
      timestamp: new Date().toISOString(),
    };
    await this.store.addConversationEntry(sessionId, entry);
  }

  /**
   * Set the customer type for a session
   */
  async setCustomerType(sessionId: string, type: SessionData['customerType']): Promise<void> {
    await this.store.setCustomerType(sessionId, type);
    logger.debug('Customer type set', { sessionId, type });
  }

  /**
   * Reset a session (clear conversation history but keep customer type)
   */
  async resetSession(sessionId: string): Promise<SessionData | null> {
    const session = await this.store.get(sessionId);
    if (!session) return null;

    session.conversationHistory = [];
    session.context = {};
    session.lastActiveAt = new Date().toISOString();
    await this.store.save(session);

    logger.debug('Session reset', { sessionId });
    return session;
  }

  /**
   * Save session data to Redis (persist in-memory changes).
   */
  async saveSession(session: SessionData): Promise<void> {
    await this.store.save(session);
  }

  /**
   * Get session data (for routing decisions, context building, etc.)
   */
  async getSession(sessionId: string): Promise<SessionData | null> {
    return this.store.get(sessionId);
  }

  async disconnect(): Promise<void> {
    await this.store.disconnect();
  }
}
