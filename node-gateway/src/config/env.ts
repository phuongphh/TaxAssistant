import { z } from 'zod';
import dotenv from 'dotenv';

dotenv.config();

const envSchema = z.object({
  // Application
  NODE_ENV: z.enum(['development', 'staging', 'production']).default('development'),
  PORT: z.coerce.number().default(3000),
  WEBHOOK_PORT: z.coerce.number().default(3001),

  // Telegram
  TELEGRAM_BOT_TOKEN: z.string().min(1),
  TELEGRAM_WEBHOOK_URL: z.string().url().optional(),
  TELEGRAM_WEBHOOK_SECRET: z.string().optional(),

  // Zalo OA
  ZALO_APP_ID: z.string().optional(),
  ZALO_APP_SECRET: z.string().optional(),
  ZALO_OA_ACCESS_TOKEN: z.string().optional(),
  ZALO_OA_REFRESH_TOKEN: z.string().optional(),
  ZALO_WEBHOOK_SECRET: z.string().optional(),

  // Redis
  REDIS_URL: z.string().default('redis://localhost:6379'),

  // PostgreSQL
  POSTGRES_URL: z.string().default('postgresql://taxapp:taxapp_dev@localhost:5432/taxassistant'),

  // Python Tax Engine
  PYTHON_GRPC_HOST: z.string().default('localhost'),
  PYTHON_GRPC_PORT: z.coerce.number().default(50051),
  PYTHON_REST_URL: z.string().url().default('http://localhost:8000'),

  // Rate Limiting
  RATE_LIMIT_WINDOW_MS: z.coerce.number().default(60_000),
  RATE_LIMIT_MAX_REQUESTS: z.coerce.number().default(30),

  // Session
  SESSION_TTL_SECONDS: z.coerce.number().default(3600),
});

export type Env = z.infer<typeof envSchema>;

function loadEnv(): Env {
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const formatted = parsed.error.format();
    console.error('❌ Invalid environment variables:', JSON.stringify(formatted, null, 2));
    process.exit(1);
  }
  return parsed.data;
}

export const env = loadEnv();
