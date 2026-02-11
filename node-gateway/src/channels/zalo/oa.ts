import axios, { AxiosInstance } from 'axios';
import { config } from '../../config';
import { logger } from '../../utils/logger';
import { ChannelError } from '../../utils/errors';
import {
  ChannelAdapter,
  MessageHandler,
  OutgoingMessage,
} from '../types';
import { mapZaloMessage, ZaloWebhookEvent } from './mapper';

const ZALO_OA_API = 'https://openapi.zalo.me/v3.0/oa';

/**
 * Zalo Official Account adapter
 * Handles communication with Zalo OA API for sending/receiving messages
 */
export class ZaloAdapter implements ChannelAdapter {
  readonly channel = 'zalo' as const;
  private client: AxiosInstance;
  private messageHandler: MessageHandler | null = null;
  private accessToken: string;

  constructor() {
    this.accessToken = config.zalo.oaAccessToken || '';
    this.client = axios.create({
      baseURL: ZALO_OA_API,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add auth header interceptor
    this.client.interceptors.request.use((reqConfig) => {
      reqConfig.headers['access_token'] = this.accessToken;
      return reqConfig;
    });
  }

  async initialize(): Promise<void> {
    if (!this.accessToken) {
      logger.warn('Zalo OA access token not configured, Zalo channel disabled');
      return;
    }
    logger.info('Zalo OA adapter initialized');
  }

  onMessage(handler: MessageHandler): void {
    this.messageHandler = handler;
  }

  /**
   * Process incoming Zalo webhook event.
   * Called by the webhook route handler.
   */
  async handleWebhookEvent(event: ZaloWebhookEvent): Promise<void> {
    const message = mapZaloMessage(event);
    if (message && this.messageHandler) {
      // Fetch user profile to get display name
      try {
        const profile = await this.getUserProfile(message.userId);
        message.userName = profile.display_name || '';
      } catch {
        logger.warn('Failed to fetch Zalo user profile', { userId: message.userId });
      }

      await this.messageHandler(message);
    }
  }

  async sendMessage(chatId: string, message: OutgoingMessage): Promise<void> {
    try {
      if (message.text) {
        // Send text with quick replies (Zalo uses "buttons" template)
        if (message.quickReplies && message.quickReplies.length > 0) {
          await this.client.post('/message/cs', {
            recipient: { user_id: chatId },
            message: {
              attachment: {
                type: 'template',
                payload: {
                  template_type: 'button',
                  text: message.text,
                  buttons: message.quickReplies.map((qr) => ({
                    title: qr.label,
                    type: 'oa.query.show',
                    payload: qr.payload,
                  })),
                },
              },
            },
          });
        } else {
          await this.client.post('/message/cs', {
            recipient: { user_id: chatId },
            message: { text: message.text },
          });
        }
      }

      // Send attachments
      if (message.attachments) {
        for (const attachment of message.attachments) {
          await this.client.post('/message/cs', {
            recipient: { user_id: chatId },
            message: {
              attachment: {
                type: attachment.type === 'image' ? 'image' : 'file',
                payload: {
                  url: attachment.url,
                },
              },
            },
          });
        }
      }
    } catch (error) {
      logger.error('Failed to send Zalo message', { chatId, error });
      throw new ChannelError('zalo', 'Failed to send message');
    }
  }

  /**
   * Get Zalo user profile
   */
  private async getUserProfile(userId: string): Promise<{ display_name: string; avatar: string }> {
    const response = await this.client.get('/getprofile', {
      params: { data: JSON.stringify({ user_id: userId }) },
    });
    return response.data.data;
  }

  /**
   * Refresh Zalo OA access token using refresh token
   */
  async refreshAccessToken(): Promise<void> {
    if (!config.zalo.appId || !config.zalo.appSecret || !config.zalo.oaRefreshToken) {
      throw new ChannelError('zalo', 'Missing Zalo OAuth credentials for token refresh');
    }

    try {
      const response = await axios.post('https://oauth.zaloapp.com/v4/oa/access_token', null, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          secret_key: config.zalo.appSecret,
        },
        params: {
          app_id: config.zalo.appId,
          grant_type: 'refresh_token',
          refresh_token: config.zalo.oaRefreshToken,
        },
      });

      this.accessToken = response.data.access_token;
      logger.info('Zalo OA access token refreshed');
    } catch (error) {
      logger.error('Failed to refresh Zalo access token', { error });
      throw new ChannelError('zalo', 'Failed to refresh access token');
    }
  }

  async shutdown(): Promise<void> {
    logger.info('Zalo OA adapter stopped');
  }
}
