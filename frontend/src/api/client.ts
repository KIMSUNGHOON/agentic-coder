/**
 * API client for communicating with the backend
 */
import axios, { AxiosInstance } from 'axios';
import {
  ChatRequest,
  ChatResponse,
  AgentStatus,
  ModelsResponse,
} from '../types/api';

class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor(baseURL: string = '/api') {
    this.baseURL = baseURL;
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Send a chat message (non-streaming)
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await this.client.post<ChatResponse>('/chat', request);
    return response.data;
  }

  /**
   * Stream a chat message
   */
  async *chatStream(request: ChatRequest): AsyncGenerator<string, void, unknown> {
    const response = await this.client.post('/chat/stream', request, {
      responseType: 'stream',
      adapter: 'fetch',
    });

    const reader = response.data.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        yield chunk;
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Get agent status for a session
   */
  async getAgentStatus(sessionId: string): Promise<AgentStatus> {
    const response = await this.client.get<AgentStatus>(
      `/agent/status/${sessionId}`
    );
    return response.data;
  }

  /**
   * Delete a session
   */
  async deleteSession(sessionId: string): Promise<void> {
    await this.client.delete(`/agent/session/${sessionId}`);
  }

  /**
   * Clear conversation history for a session
   */
  async clearHistory(sessionId: string): Promise<void> {
    await this.client.post(`/agent/clear/${sessionId}`);
  }

  /**
   * List all active sessions
   */
  async listSessions(): Promise<{ sessions: string[]; count: number }> {
    const response = await this.client.get<{ sessions: string[]; count: number }>(
      '/agent/sessions'
    );
    return response.data;
  }

  /**
   * Get available models
   */
  async listModels(): Promise<ModelsResponse> {
    const response = await this.client.get<ModelsResponse>('/models');
    return response.data;
  }

  /**
   * Check API health
   */
  async healthCheck(): Promise<{ status: string }> {
    const response = await this.client.get<{ status: string }>('/health');
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
