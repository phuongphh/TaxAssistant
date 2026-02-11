import { Router, Request, Response } from 'express';
import { SessionStore } from '../../session/store';

/**
 * Admin REST API routes
 * Used for monitoring, management, and debugging
 */
export function createAdminRouter(sessionStore: SessionStore): Router {
  const router = Router();

  // Get session info (for debugging)
  router.get('/api/admin/sessions/:sessionId', async (req: Request, res: Response) => {
    try {
      const session = await sessionStore.get(req.params.sessionId);
      if (!session) {
        res.status(404).json({ error: 'Session not found' });
        return;
      }
      res.json(session);
    } catch (error) {
      res.status(500).json({ error: 'Failed to fetch session' });
    }
  });

  // Delete a session
  router.delete('/api/admin/sessions/:sessionId', async (req: Request, res: Response) => {
    try {
      await sessionStore.delete(req.params.sessionId);
      res.json({ message: 'Session deleted' });
    } catch (error) {
      res.status(500).json({ error: 'Failed to delete session' });
    }
  });

  // Service info
  router.get('/api/admin/info', (_req: Request, res: Response) => {
    res.json({
      service: 'tax-assistant-gateway',
      version: process.env.npm_package_version || '0.1.0',
      nodeVersion: process.version,
      uptime: process.uptime(),
      memory: process.memoryUsage(),
    });
  });

  return router;
}
