import { Router, Request, Response } from 'express';
import Redis from 'ioredis';
import { config } from '../../config';
import type { TelegramAdapter } from '../../channels/telegram/bot';
import { logger } from '../../utils/logger';
import { memoryMonitor } from '../../utils/memoryMonitor';

let _telegramAdapter: TelegramAdapter | null = null;

/** Call once at startup so the health route can report polling status */
export function setTelegramAdapter(adapter: TelegramAdapter): void {
  _telegramAdapter = adapter;
}

const router = Router();

// Create a shared Redis connection pool for health checks
let redisPool: Redis | null = null;

async function getRedisConnection(): Promise<Redis> {
  if (!redisPool) {
    redisPool = new Redis(config.redis.url, {
      lazyConnect: true,
      connectTimeout: 2000,
      maxRetriesPerRequest: 1,
      retryStrategy: (times) => Math.min(times * 100, 3000),
    });
    
    redisPool.on('error', (err) => {
      logger.error('Health check Redis connection error', { error: err.message });
    });
  }
  
  if (redisPool.status !== 'ready') {
    await redisPool.connect();
  }
  
  return redisPool;
}

/**
 * Health check endpoint - used by load balancers and monitoring
 */
router.get('/health', async (_req: Request, res: Response) => {
  const checks: Record<string, 'ok' | 'error'> = {};
  const details: Record<string, any> = {};

  // Check Redis
  try {
    const redis = await getRedisConnection();
    const startTime = Date.now();
    await redis.ping();
    const latency = Date.now() - startTime;
    
    checks.redis = 'ok';
    details.redis = {
      latency: `${latency}ms`,
      status: redis.status,
    };
  } catch (error) {
    checks.redis = 'error';
    details.redis = {
      error: error instanceof Error ? error.message : String(error),
    };
    
    // Reset pool on error
    if (redisPool) {
      try {
        await redisPool.quit();
      } catch (quitError) {
        // Ignore quit errors
      }
      redisPool = null;
    }
  }

  // Check Telegram polling health (only relevant when using polling, not webhook)
  if (_telegramAdapter && !config.telegram.webhookUrl) {
    // Cho phép 10 phút không có update vẫn coi là healthy
    checks.telegramPolling = _telegramAdapter.isPollingHealthy(600_000) ? 'ok' : 'error';
  }

  // Add memory usage
  const memoryUsage = process.memoryUsage();
  details.memory = {
    rss: `${Math.round(memoryUsage.rss / 1024 / 1024)}MB`,
    heapTotal: `${Math.round(memoryUsage.heapTotal / 1024 / 1024)}MB`,
    heapUsed: `${Math.round(memoryUsage.heapUsed / 1024 / 1024)}MB`,
    external: `${Math.round(memoryUsage.external / 1024 / 1024)}MB`,
  };

  // Add uptime
  details.uptime = `${Math.round(process.uptime())}s`;

  const allHealthy = Object.values(checks).every((v) => v === 'ok');

  res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? 'healthy' : 'degraded',
    service: 'tax-assistant-gateway',
    timestamp: new Date().toISOString(),
    checks,
    details,
  });
});

/**
 * Liveness probe - simple check if server is running
 */
router.get('/health/live', (_req: Request, res: Response) => {
  res.status(200).json({ 
    status: 'alive',
    timestamp: new Date().toISOString(),
    uptime: `${Math.round(process.uptime())}s`,
  });
});

/**
 * Detailed metrics endpoint for monitoring
 */
router.get('/health/metrics', (_req: Request, res: Response) => {
  const memoryUsage = process.memoryUsage();
  const memoryMonitorStatus = memoryMonitor.getStatus();
  
  const metrics = {
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: {
      rss: memoryUsage.rss,
      heapTotal: memoryUsage.heapTotal,
      heapUsed: memoryUsage.heapUsed,
      external: memoryUsage.external,
      arrayBuffers: memoryUsage.arrayBuffers,
    },
    cpu: {
      user: process.cpuUsage().user,
      system: process.cpuUsage().system,
    },
    eventLoop: {
      delay: 0, // Would need measurement
    },
    activeHandles: (process as any)._getActiveHandles?.()?.length || 0,
    activeRequests: (process as any)._getActiveRequests?.()?.length || 0,
    memoryMonitor: memoryMonitorStatus,
  };
  
  res.status(200).json(metrics);
});

/**
 * Memory monitor status endpoint
 */
router.get('/health/memory', (_req: Request, res: Response) => {
  const status = memoryMonitor.getStatus();
  res.status(200).json(status);
});

export { router as healthRouter };
