import { env } from './env';

export const config = {
  app: {
    env: env.NODE_ENV,
    port: env.PORT,
    webhookPort: env.WEBHOOK_PORT,
    isProduction: env.NODE_ENV === 'production',
  },

  telegram: {
    botToken: env.TELEGRAM_BOT_TOKEN,
    webhookUrl: env.TELEGRAM_WEBHOOK_URL,
    webhookSecret: env.TELEGRAM_WEBHOOK_SECRET,
  },

  zalo: {
    appId: env.ZALO_APP_ID,
    appSecret: env.ZALO_APP_SECRET,
    oaAccessToken: env.ZALO_OA_ACCESS_TOKEN,
    oaRefreshToken: env.ZALO_OA_REFRESH_TOKEN,
    webhookSecret: env.ZALO_WEBHOOK_SECRET,
  },

  redis: {
    url: env.REDIS_URL,
  },

  postgres: {
    url: env.POSTGRES_URL,
  },

  taxEngine: {
    grpcHost: env.PYTHON_GRPC_HOST,
    grpcPort: env.PYTHON_GRPC_PORT,
    grpcAddress: `${env.PYTHON_GRPC_HOST}:${env.PYTHON_GRPC_PORT}`,
    restUrl: env.PYTHON_REST_URL,
  },

  rateLimit: {
    windowMs: env.RATE_LIMIT_WINDOW_MS,
    maxRequests: env.RATE_LIMIT_MAX_REQUESTS,
  },

  session: {
    ttlSeconds: env.SESSION_TTL_SECONDS,
  },
} as const;

export type Config = typeof config;
