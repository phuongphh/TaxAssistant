import { Router, Request, Response } from 'express';
import Redis from 'ioredis';
import { config } from '../../config';
import type { TelegramAdapter } from '../../channels/telegram/bot';

let _telegramAdapter: TelegramAdapter | null = null;

/** Call once at startup so the health route can report polling status */
export function setTelegramAdapter(adapter: TelegramAdapter): void {
  _telegramAdapter = adapter;
}

const router = Router();

/**
 * Health check endpoint - used by load balancers and monitoring
 */
router.get('/health', async (_req: Request, res: Response) => {
  const checks: Record<string, 'ok' | 'error'> = {};

  // Check Redis
  try {
    const redis = new Redis(config.redis.url, { lazyConnect: true, connectTimeout: 2000 });
    await redis.ping();
    await redis.quit();
    checks.redis = 'ok';
  } catch {
    checks.redis = 'error';
  }

  // Check Telegram polling (only in non-production / polling mode)
  if (_telegramAdapter && !(config.app.isProduction && config.telegram.webhookUrl)) {
    checks.telegramPolling = _telegramAdapter.isPollingHealthy() ? 'ok' : 'error';
  }

  const allHealthy = Object.values(checks).every((v) => v === 'ok');

  res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? 'healthy' : 'degraded',
    service: 'tax-assistant-gateway',
    timestamp: new Date().toISOString(),
    checks,
  });
});

/**
 * Liveness probe - simple check if server is running
 */
router.get('/health/live', (_req: Request, res: Response) => {
  res.status(200).json({ status: 'alive' });
});

export { router as healthRouter };
