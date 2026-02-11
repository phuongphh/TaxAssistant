import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';
import Redis from 'ioredis';
import { config } from '../config';
import { logger } from '../utils/logger';

/**
 * Creates rate limiter middleware backed by Redis
 * Limits per user (identified by channel:userId)
 */
export function createRateLimiter() {
  const redisClient = new Redis(config.redis.url);

  return rateLimit({
    windowMs: config.rateLimit.windowMs,
    max: config.rateLimit.maxRequests,
    standardHeaders: true,
    legacyHeaders: false,

    // Use Redis store for distributed rate limiting
    store: new RedisStore({
      sendCommand: (...args: string[]) => redisClient.call(...args) as never,
      prefix: 'rl:',
    }),

    // Custom key generator: use userId from request if available
    keyGenerator: (req) => {
      const userId = (req as Record<string, unknown>).userId as string;
      return userId || req.ip || 'unknown';
    },

    handler: (_req, res) => {
      logger.warn('Rate limit exceeded', { ip: _req.ip });
      res.status(429).json({
        error: 'TOO_MANY_REQUESTS',
        message: 'Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.',
      });
    },
  });
}
