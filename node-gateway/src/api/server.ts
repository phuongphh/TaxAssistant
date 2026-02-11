import express, { Express } from 'express';
import helmet from 'helmet';
import cors from 'cors';
import compression from 'compression';
import { config } from '../config';
import { requestLogger } from '../middleware/logging';
import { createRateLimiter } from '../middleware/rateLimiter';
import { errorHandler } from '../middleware/errorHandler';
import { healthRouter } from './routes/health';
import { createAdminRouter } from './routes/admin';
import { createZaloWebhookRouter } from '../channels/zalo/webhook';
import { SessionStore } from '../session/store';
import { ZaloAdapter } from '../channels/zalo/oa';
import { TelegramAdapter } from '../channels/telegram/bot';

export interface ServerDependencies {
  sessionStore: SessionStore;
  zaloAdapter: ZaloAdapter;
  telegramAdapter: TelegramAdapter;
}

/**
 * Create and configure the Express server
 */
export function createServer(deps: ServerDependencies): Express {
  const app = express();

  // === Global middleware ===
  app.use(helmet());
  app.use(cors());
  app.use(compression());
  app.use(express.json({ limit: '5mb' }));
  app.use(requestLogger);

  // === Health routes (no rate limiting) ===
  app.use(healthRouter);

  // === Webhook routes ===
  // Telegram webhook (production only)
  if (config.app.isProduction && config.telegram.webhookUrl) {
    app.use(deps.telegramAdapter.getWebhookCallback());
  }

  // Zalo webhook
  app.use(createZaloWebhookRouter(deps.zaloAdapter));

  // === API routes (with rate limiting) ===
  const apiLimiter = createRateLimiter();
  app.use('/api', apiLimiter);
  app.use(createAdminRouter(deps.sessionStore));

  // === Error handling ===
  app.use(errorHandler);

  return app;
}
