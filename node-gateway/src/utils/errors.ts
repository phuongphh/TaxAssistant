export class AppError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number = 500,
    public readonly code: string = 'INTERNAL_ERROR',
    public readonly isOperational: boolean = true,
  ) {
    super(message);
    this.name = 'AppError';
    Error.captureStackTrace(this, this.constructor);
  }
}

export class ChannelError extends AppError {
  constructor(
    public readonly channel: string,
    message: string,
    statusCode = 502,
  ) {
    super(message, statusCode, 'CHANNEL_ERROR');
    this.name = 'ChannelError';
  }
}

export class TaxEngineError extends AppError {
  constructor(message: string, statusCode = 502) {
    super(message, statusCode, 'TAX_ENGINE_ERROR');
    this.name = 'TaxEngineError';
  }
}

export class SessionError extends AppError {
  constructor(message: string) {
    super(message, 500, 'SESSION_ERROR');
    this.name = 'SessionError';
  }
}

export class RateLimitError extends AppError {
  constructor(message = 'Too many requests') {
    super(message, 429, 'RATE_LIMIT_EXCEEDED');
    this.name = 'RateLimitError';
  }
}

export class ValidationError extends AppError {
  constructor(message: string) {
    super(message, 400, 'VALIDATION_ERROR');
    this.name = 'ValidationError';
  }
}
