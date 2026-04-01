import { logger } from './logger';

interface MemoryStats {
  rss: number;
  heapTotal: number;
  heapUsed: number;
  external: number;
  arrayBuffers: number;
}

interface MemoryThresholds {
  rss: number; // MB
  heapUsed: number; // MB
  heapUsedPercentage: number; // Percentage of heapTotal
}

export class MemoryMonitor {
  private readonly thresholds: MemoryThresholds;
  private readonly checkIntervalMs: number;
  private intervalId: NodeJS.Timeout | null = null;
  private consecutiveExceeded = 0;
  private readonly maxConsecutiveExceeded = 3;

  constructor(
    thresholds: Partial<MemoryThresholds> = {},
    checkIntervalMs = 60000 // Check every minute
  ) {
    this.thresholds = {
      rss: thresholds.rss || 400, // 400MB RSS
      heapUsed: thresholds.heapUsed || 300, // 300MB heap used
      heapUsedPercentage: thresholds.heapUsedPercentage || 85, // 85% of heap
    };
    this.checkIntervalMs = checkIntervalMs;
  }

  start(): void {
    if (this.intervalId) {
      logger.warn('Memory monitor already started');
      return;
    }

    logger.info('Starting memory monitor', {
      thresholds: this.thresholds,
      checkIntervalMs: this.checkIntervalMs,
    });

    this.intervalId = setInterval(() => {
      this.checkMemory();
    }, this.checkIntervalMs);

    // Initial check
    this.checkMemory();
  }

  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
      logger.info('Memory monitor stopped');
    }
  }

  private checkMemory(): void {
    const stats = this.getMemoryStats();
    const exceeded = this.checkThresholds(stats);
    
    if (exceeded) {
      this.consecutiveExceeded++;
      logger.warn('Memory thresholds exceeded', {
        ...stats,
        consecutiveExceeded: this.consecutiveExceeded,
        thresholds: this.thresholds,
      });

      if (this.consecutiveExceeded >= this.maxConsecutiveExceeded) {
        logger.error('Memory thresholds consistently exceeded, taking action', {
          consecutiveExceeded: this.consecutiveExceeded,
          stats,
        });
        this.takeAction(stats);
      }
    } else {
      if (this.consecutiveExceeded > 0) {
        logger.info('Memory back to normal levels', {
          previousConsecutiveExceeded: this.consecutiveExceeded,
          stats,
        });
      }
      this.consecutiveExceeded = 0;
    }

    // Log memory stats periodically (every 5th check = every 5 minutes)
    const checkCount = this.getCheckCount();
    if (checkCount % 5 === 0) {
      logger.info('Memory usage snapshot', stats);
    }
  }

  private getMemoryStats(): MemoryStats {
    const memoryUsage = process.memoryUsage();
    return {
      rss: Math.round(memoryUsage.rss / 1024 / 1024),
      heapTotal: Math.round(memoryUsage.heapTotal / 1024 / 1024),
      heapUsed: Math.round(memoryUsage.heapUsed / 1024 / 1024),
      external: Math.round(memoryUsage.external / 1024 / 1024),
      arrayBuffers: Math.round(memoryUsage.arrayBuffers / 1024 / 1024),
    };
  }

  private checkThresholds(stats: MemoryStats): boolean {
    const heapUsedPercentage = (stats.heapUsed / stats.heapTotal) * 100;
    
    return (
      stats.rss > this.thresholds.rss ||
      stats.heapUsed > this.thresholds.heapUsed ||
      heapUsedPercentage > this.thresholds.heapUsedPercentage
    );
  }

  private takeAction(stats: MemoryStats): void {
    logger.warn('Taking memory leak prevention actions', { stats });
    
    // 1. Try to force garbage collection (if enabled)
    if (global.gc) {
      logger.info('Forcing garbage collection');
      try {
        global.gc();
      } catch (error) {
        logger.error('Failed to force garbage collection', {
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
    
    // 2. Clear any large caches (if applicable)
    this.clearCaches();
    
    // 3. Log detailed memory information
    this.logDetailedMemoryInfo();
    
    // 4. If memory is critically high, consider restarting
    if (stats.rss > this.thresholds.rss * 1.5 || stats.heapUsed > this.thresholds.heapUsed * 1.5) {
      logger.error('Critical memory usage detected, consider restarting service', { stats });
      // In production, you might want to trigger a graceful restart here
      // process.emit('memory-critical', stats);
    }
  }

  private clearCaches(): void {
    // Clear module cache if it's growing too large
    const moduleCount = Object.keys(require.cache).length;
    if (moduleCount > 1000) {
      logger.warn('Large module cache detected, clearing some entries', { moduleCount });
      
      // Keep essential modules, clear others
      const keepModules = ['/app/node_modules/', '/app/dist/', '/app/src/utils/'];
      for (const modulePath in require.cache) {
        if (!keepModules.some(keep => modulePath.includes(keep))) {
          delete require.cache[modulePath];
        }
      }
    }
  }

  private logDetailedMemoryInfo(): void {
    try {
      // Log active handles and requests
      const activeHandles = process._getActiveHandles?.()?.length || 0;
      const activeRequests = process._getActiveRequests?.()?.length || 0;
      
      logger.info('Detailed memory info', {
        activeHandles,
        activeRequests,
        uptime: process.uptime(),
        eventLoopDelay: this.measureEventLoopDelay(),
      });
    } catch (error) {
      logger.debug('Could not get detailed memory info', {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private measureEventLoopDelay(): number {
    const start = process.hrtime.bigint();
    // Simple synchronous operation to measure event loop blocking
    let sum = 0;
    for (let i = 0; i < 1000000; i++) {
      sum += i;
    }
    const end = process.hrtime.bigint();
    return Number(end - start) / 1000000; // Convert to milliseconds
  }

  private checkCount = 0;
  private getCheckCount(): number {
    return ++this.checkCount;
  }

  getStatus(): {
    running: boolean;
    thresholds: MemoryThresholds;
    consecutiveExceeded: number;
    lastStats?: MemoryStats;
  } {
    return {
      running: this.intervalId !== null,
      thresholds: this.thresholds,
      consecutiveExceeded: this.consecutiveExceeded,
      lastStats: this.intervalId ? this.getMemoryStats() : undefined,
    };
  }
}

// Export singleton instance
export const memoryMonitor = new MemoryMonitor();