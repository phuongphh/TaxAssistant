import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';
import path from 'path';
import { config } from '../config';
import { logger } from '../utils/logger';
import { TaxEngineError } from '../utils/errors';
import { SessionData, CustomerProfile, ActiveCase } from '../session/store';

// Circuit breaker implementation
class CircuitBreaker {
  private failures = 0;
  private lastFailureTime = 0;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private readonly failureThreshold = 5;
  private readonly resetTimeout = 30000; // 30 seconds
  private readonly halfOpenTimeout = 10000; // 10 seconds

  canRequest(): boolean {
    const now = Date.now();
    
    switch (this.state) {
      case 'CLOSED':
        return true;
        
      case 'OPEN':
        if (now - this.lastFailureTime > this.resetTimeout) {
          this.state = 'HALF_OPEN';
          logger.info('Circuit breaker moving to HALF_OPEN state');
          return true;
        }
        return false;
        
      case 'HALF_OPEN':
        if (now - this.lastFailureTime > this.halfOpenTimeout) {
          return true;
        }
        return false;
    }
  }

  recordSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.state = 'CLOSED';
      this.failures = 0;
      logger.info('Circuit breaker reset to CLOSED state after successful request');
    }
  }

  recordFailure(): void {
    this.failures++;
    this.lastFailureTime = Date.now();
    
    if (this.state === 'CLOSED' && this.failures >= this.failureThreshold) {
      this.state = 'OPEN';
      logger.warn('Circuit breaker tripped to OPEN state', {
        failures: this.failures,
        lastFailureTime: new Date(this.lastFailureTime).toISOString(),
      });
    } else if (this.state === 'HALF_OPEN') {
      this.state = 'OPEN';
      logger.warn('Circuit breaker re-opened after failed half-open attempt');
    }
  }

  getState(): string {
    return this.state;
  }

  getFailureCount(): number {
    return this.failures;
  }
}

// Load proto definition
const PROTO_PATH = path.resolve(__dirname, '../../../proto/tax_service.proto');

const packageDef = protoLoader.loadSync(PROTO_PATH, {
  keepCase: false,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const proto = grpc.loadPackageDefinition(packageDef) as any;

// Map customer type string to proto enum value
function mapCustomerType(type: SessionData['customerType']): number {
  const mapping: Record<string, number> = {
    unknown: 0,
    sme: 1,
    household: 2,
    individual: 3,
  };
  return mapping[type] ?? 0;
}

export interface TaxEngineResponse {
  requestId: string;
  reply: string;
  actions: Array<{
    label: string;
    actionType: string;
    payload: string;
  }>;
  references: Array<{
    title: string;
    url: string;
    snippet: string;
  }>;
  confidence: number;
  category: string;
}

/**
 * gRPC client for communicating with the Python Tax Engine service
 */
export class TaxEngineClient {
  private client: any;
  private connected = false;
  private circuitBreaker: CircuitBreaker;
  private connectionAttempts = 0;
  private readonly maxConnectionAttempts = 3;

  constructor() {
    this.client = new proto.taxassistant.TaxEngine(
      config.taxEngine.grpcAddress,
      grpc.credentials.createInsecure(),
      {
        'grpc.keepalive_time_ms': 30000,
        'grpc.keepalive_timeout_ms': 5000,
        'grpc.service_config': JSON.stringify({
          methodConfig: [{
            name: [{ service: 'taxassistant.TaxEngine' }],
            retryPolicy: {
              maxAttempts: 3,
              initialBackoff: '1s',
              maxBackoff: '5s',
              backoffMultiplier: 2,
              retryableStatusCodes: ['UNAVAILABLE', 'DEADLINE_EXCEEDED'],
            },
          }],
        }),
      },
    );
    this.circuitBreaker = new CircuitBreaker();
  }

  /**
   * Wait for the gRPC channel to be ready
   */
  async connect(timeoutMs = 5000): Promise<void> {
    if (!this.circuitBreaker.canRequest()) {
      throw new TaxEngineError('Tax Engine service unavailable (circuit breaker open)');
    }

    return new Promise((resolve, reject) => {
      const deadline = new Date(Date.now() + timeoutMs);
      this.client.waitForReady(deadline, (err: Error | null) => {
        if (err) {
          this.circuitBreaker.recordFailure();
          this.connectionAttempts++;
          
          logger.error('Failed to connect to Tax Engine gRPC', {
            error: err.message,
            connectionAttempts: this.connectionAttempts,
            circuitBreakerState: this.circuitBreaker.getState(),
          });
          
          if (this.connectionAttempts >= this.maxConnectionAttempts) {
            reject(new TaxEngineError(`Tax Engine service unavailable after ${this.connectionAttempts} attempts`));
          } else {
            reject(new TaxEngineError('Tax Engine service temporarily unavailable'));
          }
        } else {
          this.connected = true;
          this.connectionAttempts = 0;
          this.circuitBreaker.recordSuccess();
          logger.info('Connected to Tax Engine gRPC', {
            address: config.taxEngine.grpcAddress,
            circuitBreakerState: this.circuitBreaker.getState(),
          });
          resolve();
        }
      });
    });
  }

  /**
   * Send a tax-related message for processing
   */
  async processMessage(
    requestId: string,
    message: string,
    session: SessionData,
    customerProfile?: CustomerProfile,
    activeCases?: ActiveCase[],
    conversationSummaries?: string[],
  ): Promise<TaxEngineResponse> {
    // Check circuit breaker before making request
    if (!this.circuitBreaker.canRequest()) {
      logger.warn('Circuit breaker open, rejecting gRPC request', {
        requestId,
        circuitBreakerState: this.circuitBreaker.getState(),
        failureCount: this.circuitBreaker.getFailureCount(),
      });
      throw new TaxEngineError('Tax Engine service temporarily unavailable. Please try again later.');
    }

    // Send the last 10 conversation entries (5 turns) so the LLM has
    // enough context to remember earlier information like customer type.
    const recentHistory = (session.conversationHistory || []).slice(-10).map((entry) => ({
      role: entry.role,
      content: entry.content,
      timestamp: entry.timestamp,
    }));

    const request: Record<string, unknown> = {
      requestId,
      message,
      language: 'vi',
      context: {
        sessionId: session.sessionId,
        userId: session.userId,
        customerType: mapCustomerType(session.customerType),
        previousTopics: [],
        metadata: session.context as Record<string, string>,
      },
      conversationHistory: recentHistory,
    };

    // Attach customer profile for long-term memory
    if (customerProfile) {
      request.customerProfile = {
        customerId: customerProfile.customerId,
        channel: customerProfile.channel,
        channelUserId: customerProfile.channelUserId,
        username: customerProfile.username || '',
        firstName: customerProfile.firstName || '',
        lastName: customerProfile.lastName || '',
        displayName: customerProfile.displayName || '',
        customerType: customerProfile.customerType,
        businessName: customerProfile.businessName,
        taxCode: customerProfile.taxCode,
        industry: customerProfile.industry,
        province: customerProfile.province,
        annualRevenueRange: customerProfile.annualRevenueRange,
        employeeCountRange: customerProfile.employeeCountRange,
        onboardingStep: customerProfile.onboardingStep,
        taxProfile: customerProfile.taxProfile || {},
        recentNotes: customerProfile.recentNotes || [],
      };
    }

    // Attach active support cases
    if (activeCases?.length) {
      request.activeCases = activeCases.map((c) => ({
        caseId: c.caseId,
        customerId: c.customerId,
        serviceType: c.serviceType,
        title: c.title,
        status: c.status,
        currentStep: c.currentStep,
      }));
    }

    // Attach conversation summaries from long-term memory
    if (conversationSummaries?.length) {
      request.conversationSummaries = conversationSummaries;
    }

    logger.info('gRPC processMessage: history=%d profile=%s cases=%d session=%s circuit=%s',
      recentHistory.length,
      customerProfile ? 'yes' : 'no',
      activeCases?.length ?? 0,
      session.sessionId,
      this.circuitBreaker.getState(),
    );

    const startMs = Date.now();
    return new Promise((resolve, reject) => {
      this.client.processMessage(request, { deadline: this.deadline(180000) }, (err: any, response: any) => {
        const elapsedMs = Date.now() - startMs;
        if (err) {
          this.circuitBreaker.recordFailure();
          logger.error('gRPC ProcessMessage error', {
            code: err.code,
            message: err.message,
            details: err.details,
            elapsedMs,
            requestId,
            circuitBreakerState: this.circuitBreaker.getState(),
            failureCount: this.circuitBreaker.getFailureCount(),
          });
          reject(new TaxEngineError(`Tax Engine error: ${err.message}`));
        } else {
          this.circuitBreaker.recordSuccess();
          logger.debug('gRPC ProcessMessage OK', {
            requestId,
            elapsedMs,
            replyLength: response?.reply?.length ?? 0,
            circuitBreakerState: this.circuitBreaker.getState(),
          });
          resolve(response as TaxEngineResponse);
        }
      });
    });
  }

  /**
   * Lookup tax regulation
   */
  async lookupRegulation(
    query: string,
    category?: string,
    customerType?: SessionData['customerType'],
  ): Promise<{ regulations: Array<{ documentNumber: string; title: string; content: string }>; summary: string }> {
    const request = {
      query,
      category: category || 'TAX_CATEGORY_UNSPECIFIED',
      customerType: customerType ? mapCustomerType(customerType) : 0,
    };

    return new Promise((resolve, reject) => {
      this.client.lookupRegulation(request, { deadline: this.deadline() }, (err: any, response: any) => {
        if (err) {
          logger.error('gRPC LookupRegulation error', { code: err.code, message: err.message });
          reject(new TaxEngineError(`Regulation lookup error: ${err.message}`));
        } else {
          resolve(response);
        }
      });
    });
  }

  /**
   * Process a document (invoice, receipt, etc.)
   */
  async processDocument(
    requestId: string,
    fileUrl: string,
    mimeType: string,
    documentType: string,
    session: SessionData,
  ): Promise<{ extractedData: Record<string, string>; summary: string; warnings: string[] }> {
    const request = {
      requestId,
      fileUrl,
      mimeType,
      documentType,
      context: {
        sessionId: session.sessionId,
        userId: session.userId,
        customerType: mapCustomerType(session.customerType),
      },
    };

    return new Promise((resolve, reject) => {
      this.client.processDocument(request, { deadline: this.deadline(30000) }, (err: any, response: any) => {
        if (err) {
          logger.error('gRPC ProcessDocument error', { code: err.code, message: err.message });
          reject(new TaxEngineError(`Document processing error: ${err.message}`));
        } else {
          resolve(response);
        }
      });
    });
  }

  /**
   * Get or create a customer profile
   */
  async getOrCreateCustomer(
    channel: string,
    channelUserId: string,
    userInfo?: { username?: string; firstName?: string; lastName?: string },
  ): Promise<CustomerProfile> {
    const request = {
      channel,
      channelUserId,
      username: userInfo?.username || '',
      firstName: userInfo?.firstName || '',
      lastName: userInfo?.lastName || '',
    };
    return new Promise((resolve, reject) => {
      this.client.getOrCreateCustomer(request, { deadline: this.deadline(10000) }, (err: any, response: any) => {
        if (err) {
          logger.error('gRPC GetOrCreateCustomer error', { code: err.code, message: err.message });
          reject(new TaxEngineError(`Customer lookup error: ${err.message}`));
        } else {
          resolve({
            customerId: response.customerId || '',
            channel: response.channel || '',
            channelUserId: response.channelUserId || '',
            username: response.username || '',
            firstName: response.firstName || '',
            lastName: response.lastName || '',
            displayName: response.displayName || '',
            customerType: response.customerType || 'unknown',
            businessName: response.businessName || '',
            taxCode: response.taxCode || '',
            industry: response.industry || '',
            province: response.province || '',
            annualRevenueRange: response.annualRevenueRange || '',
            employeeCountRange: response.employeeCountRange || '',
            onboardingStep: response.onboardingStep || 'new',
            taxProfile: response.taxProfile || {},
            recentNotes: response.recentNotes || [],
          });
        }
      });
    });
  }

  /**
   * Get active support cases for a customer
   */
  async getActiveCases(customerId: string): Promise<ActiveCase[]> {
    const request = { customerId };
    return new Promise((resolve, reject) => {
      this.client.getActiveCases(request, { deadline: this.deadline(10000) }, (err: any, response: any) => {
        if (err) {
          logger.error('gRPC GetActiveCases error', { code: err.code, message: err.message });
          // Non-critical: return empty on error
          resolve([]);
        } else {
          const cases = (response.cases || []).map((c: any) => ({
            caseId: c.caseId || '',
            customerId: c.customerId || '',
            serviceType: c.serviceType || '',
            title: c.title || '',
            status: c.status || '',
            currentStep: c.currentStep || '',
          }));
          resolve(cases);
        }
      });
    });
  }

  private deadline(ms = 15000): Date {
    return new Date(Date.now() + ms);
  }

  async close(): Promise<void> {
    grpc.closeClient(this.client);
    logger.info('gRPC client closed');
  }
}
