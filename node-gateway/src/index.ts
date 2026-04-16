import { config } from './config';
import { logger } from './utils/logger';
import { SessionStore } from './session/store';
import { SessionManager } from './session/manager';
import { TelegramAdapter } from './channels/telegram/bot';
import { ZaloAdapter } from './channels/zalo/oa';
import { TaxEngineClient } from './grpc/client';
import { MessageRouter } from './router/messageRouter';
import { createServer } from './api/server';
import { setTelegramAdapter } from './api/routes/health';
import { memoryMonitor } from './utils/memoryMonitor';

async function bootstrap(): Promise<void> {
  logger.info('Starting Tax Assistant Gateway...', { env: config.app.env });

  // === Start memory monitoring ===
  memoryMonitor.start();
  logger.info('Memory monitor started');

  // === Initialize core services ===
  const sessionStore = new SessionStore();
  const sessionManager = new SessionManager(sessionStore);

  // === Initialize Tax Engine gRPC client ===
  const taxEngine = new TaxEngineClient();
  let connected = false;
  for (let i = 0; i < 6; i++) {
    try {
      await taxEngine.connect(10000); // 10s per attempt
      connected = true;
      break;
    } catch {
      logger.warn(`gRPC connect attempt ${i + 1}/6 failed, retrying...`);
      await new Promise(r => setTimeout(r, 5000));
    }
  }
  if (!connected) {
    logger.error('Tax Engine not reachable after 6 attempts - continuing anyway');
  }

  // === Initialize channel adapters ===
  const telegramAdapter = new TelegramAdapter();
  const zaloAdapter = new ZaloAdapter();

  // === Initialize message router ===
  const router = new MessageRouter(sessionManager, taxEngine);
  router.registerChannel(telegramAdapter);
  router.registerChannel(zaloAdapter);

  // === Start channel adapters ===
  await telegramAdapter.initialize();
  await zaloAdapter.initialize();

  // Expose adapter to health check so it can report polling status
  setTelegramAdapter(telegramAdapter);

  // === Start HTTP server ===
  const app = createServer({ sessionStore, zaloAdapter, telegramAdapter });

  const server = app.listen(config.app.port, () => {
    logger.info(`Gateway HTTP server listening on port ${config.app.port}`);
  });

  // === Graceful shutdown ===
  const shutdown = async (signal: string) => {
    logger.info(`Received ${signal}, shutting down gracefully...`);

    // Stop memory monitor first
    memoryMonitor.stop();

    server.close(() => {
      logger.info('HTTP server closed');
    });

    await telegramAdapter.shutdown();
    await zaloAdapter.shutdown();
    await taxEngine.close();
    await sessionManager.disconnect();

    logger.info('All services stopped. Exiting.');
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Handle unhandled rejections
  process.on('unhandledRejection', (reason) => {
    logger.error('Unhandled rejection', { reason });
  });

  process.on('uncaughtException', (error) => {
    logger.error('Uncaught exception', { error: error.message, stack: error.stack });
    process.exit(1);
  });
}

bootstrap().catch((error) => {
  logger.error('Failed to start gateway', { error });
  process.exit(1);
});
