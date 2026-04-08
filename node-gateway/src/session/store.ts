import Redis from 'ioredis';
import { config } from '../config';
import { logger } from '../utils/logger';
import { SessionError } from '../utils/errors';

export interface CustomerProfile {
  customerId: string;
  channel: string;
  channelUserId: string;
  username: string;
  firstName: string;
  lastName: string;
  displayName: string;
  customerType: string;
  businessName: string;
  taxCode: string;
  industry: string;
  province: string;
  annualRevenueRange: string;
  employeeCountRange: string;
  onboardingStep: string;
  taxProfile: Record<string, string>;
  recentNotes: string[];
  taxPeriod: string;
  hasEmployees: string;
}

export interface ActiveCase {
  caseId: string;
  customerId: string;
  serviceType: string;
  title: string;
  status: string;
  currentStep: string;
}

export interface Suggestion {
  id: number;
  text: string;
  action: string;
  context: string;
}

export interface SessionData {
  sessionId: string;
  userId: string;
  channel: string;
  customerType: 'sme' | 'household' | 'individual' | 'unknown';
  conversationHistory: ConversationEntry[];
  context: Record<string, unknown>;
  createdAt: string;
  lastActiveAt: string;
  customerId?: string;
  customerProfile?: CustomerProfile;
  // Context-aware suggestions support
  currentContext?: 'tax-calculation' | 'deadline-info' | 'legal-doc' | 'tax-registration' | 'declaration-guide' | 'general';
  pendingSuggestions?: Suggestion[];
}

export interface ConversationEntry {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

const SESSION_PREFIX = 'session:';
const MAX_CONVERSATION_HISTORY = 20;

export class SessionStore {
  private redis: Redis;
  private ttl: number;

  constructor() {
    this.redis = new Redis(config.redis.url, {
      retryStrategy: (times) => Math.min(times * 200, 3000),
      maxRetriesPerRequest: 3,
    });
    this.ttl = config.session.ttlSeconds;

    this.redis.on('connect', () => logger.info('Redis connected'));
    this.redis.on('error', (err) => logger.error('Redis error', { error: err.message }));
  }

  private key(sessionId: string): string {
    return `${SESSION_PREFIX}${sessionId}`;
  }

  /**
   * Get or create a session for a user on a specific channel
   */
  async getOrCreate(userId: string, channel: string): Promise<SessionData> {
    const sessionId = `${channel}:${userId}`;
    const existing = await this.get(sessionId);

    if (existing) {
      // Update last active time and refresh TTL
      existing.lastActiveAt = new Date().toISOString();
      await this.save(existing);
      return existing;
    }

    // Create new session
    const session: SessionData = {
      sessionId,
      userId,
      channel,
      customerType: 'unknown',
      conversationHistory: [],
      context: {},
      createdAt: new Date().toISOString(),
      lastActiveAt: new Date().toISOString(),
    };

    await this.save(session);
    logger.debug('New session created', { sessionId, channel });
    return session;
  }

  async get(sessionId: string): Promise<SessionData | null> {
    try {
      const data = await this.redis.get(this.key(sessionId));
      return data ? JSON.parse(data) : null;
    } catch (error) {
      throw new SessionError(`Failed to get session: ${sessionId}`);
    }
  }

  async save(session: SessionData): Promise<void> {
    try {
      await this.redis.setex(
        this.key(session.sessionId),
        this.ttl,
        JSON.stringify(session),
      );
    } catch (error) {
      throw new SessionError(`Failed to save session: ${session.sessionId}`);
    }
  }

  /**
   * Append a conversation entry and trim history
   */
  async addConversationEntry(sessionId: string, entry: ConversationEntry): Promise<void> {
    const session = await this.get(sessionId);
    if (!session) throw new SessionError(`Session not found: ${sessionId}`);

    session.conversationHistory.push(entry);

    // Trim old entries to prevent unbounded growth
    if (session.conversationHistory.length > MAX_CONVERSATION_HISTORY) {
      session.conversationHistory = session.conversationHistory.slice(-MAX_CONVERSATION_HISTORY);
    }

    session.lastActiveAt = new Date().toISOString();
    await this.save(session);
  }

  async setCustomerType(sessionId: string, type: SessionData['customerType']): Promise<void> {
    const session = await this.get(sessionId);
    if (!session) throw new SessionError(`Session not found: ${sessionId}`);
    session.customerType = type;
    await this.save(session);
  }

  async updateContext(sessionId: string, context: Record<string, unknown>): Promise<void> {
    const session = await this.get(sessionId);
    if (!session) throw new SessionError(`Session not found: ${sessionId}`);
    session.context = { ...session.context, ...context };
    await this.save(session);
  }

  async delete(sessionId: string): Promise<void> {
    await this.redis.del(this.key(sessionId));
  }

  async disconnect(): Promise<void> {
    await this.redis.quit();
    logger.info('Redis disconnected');
  }
}
