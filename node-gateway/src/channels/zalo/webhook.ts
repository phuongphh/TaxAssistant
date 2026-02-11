import { Router, Request, Response } from 'express';
import crypto from 'crypto';
import { config } from '../../config';
import { logger } from '../../utils/logger';
import { ZaloAdapter } from './oa';
import { ZaloWebhookEvent } from './mapper';

/**
 * Creates Express router for Zalo OA webhook
 */
export function createZaloWebhookRouter(adapter: ZaloAdapter): Router {
  const router = Router();

  // Zalo webhook verification (GET)
  router.get('/webhook/zalo', (_req: Request, res: Response) => {
    res.status(200).send('OK');
  });

  // Zalo webhook event handler (POST)
  router.post('/webhook/zalo', async (req: Request, res: Response) => {
    try {
      // Verify webhook signature if secret is configured
      if (config.zalo.webhookSecret) {
        const signature = req.headers['x-zevent-signature'] as string;
        if (!verifyZaloSignature(req.body, signature, config.zalo.webhookSecret)) {
          logger.warn('Invalid Zalo webhook signature');
          res.status(403).json({ error: 'Invalid signature' });
          return;
        }
      }

      const event = req.body as ZaloWebhookEvent;
      logger.debug('Zalo webhook event received', {
        event_name: event.event_name,
        sender: event.sender?.id,
      });

      // Acknowledge immediately, process async
      res.status(200).json({ error: 0, message: 'OK' });

      // Process event asynchronously
      adapter.handleWebhookEvent(event).catch((error) => {
        logger.error('Error processing Zalo webhook event', { error });
      });
    } catch (error) {
      logger.error('Zalo webhook error', { error });
      res.status(500).json({ error: 'Internal server error' });
    }
  });

  return router;
}

/**
 * Verify Zalo webhook signature using HMAC-SHA256
 */
function verifyZaloSignature(body: unknown, signature: string, secret: string): boolean {
  if (!signature) return false;

  const payload = typeof body === 'string' ? body : JSON.stringify(body);
  const hmac = crypto.createHmac('sha256', secret);
  hmac.update(payload);
  const expected = `mac=${hmac.digest('hex')}`;

  return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
}
