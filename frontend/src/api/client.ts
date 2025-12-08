/**
 * API client for communicating with the backend
 */
import axios, { AxiosInstance } from 'axios';
import {
  ChatRequest,
  ChatResponse,
  AgentStatus,
  ModelsResponse,
  Conversation,
  ConversationListResponse,
} from '../types/api';

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = '/api') {
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
   * Stream a chat message using native Fetch API
   */
  async *chatStream(request: ChatRequest): AsyncGenerator<string, void, unknown> {
    try {
      const baseURL = this.client.defaults.baseURL || '/api';
      const response = await fetch(`${baseURL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }

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
    } catch (error) {
      console.error('Chat stream error:', error);
      throw error;
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

  // ==================== Conversation Persistence ====================

  /**
   * List all conversations
   */
  async listConversations(
    limit: number = 50,
    offset: number = 0,
    mode?: 'chat' | 'workflow'
  ): Promise<ConversationListResponse> {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    if (mode) params.append('mode', mode);

    const response = await this.client.get<ConversationListResponse>(
      `/conversations?${params.toString()}`
    );
    return response.data;
  }

  /**
   * Get a specific conversation with messages and artifacts
   */
  async getConversation(sessionId: string): Promise<Conversation> {
    const response = await this.client.get<Conversation>(
      `/conversations/${sessionId}`
    );
    return response.data;
  }

  /**
   * Create a new conversation
   */
  async createConversation(
    sessionId: string,
    title: string = 'New Conversation',
    mode: 'chat' | 'workflow' = 'chat'
  ): Promise<Conversation> {
    const params = new URLSearchParams();
    params.append('session_id', sessionId);
    params.append('title', title);
    params.append('mode', mode);

    const response = await this.client.post<Conversation>(
      `/conversations?${params.toString()}`
    );
    return response.data;
  }

  /**
   * Update a conversation
   */
  async updateConversation(
    sessionId: string,
    title?: string,
    workflowState?: Record<string, unknown>
  ): Promise<Conversation> {
    const params = new URLSearchParams();
    if (title) params.append('title', title);

    const response = await this.client.put<Conversation>(
      `/conversations/${sessionId}?${params.toString()}`,
      workflowState ? { workflow_state: workflowState } : undefined
    );
    return response.data;
  }

  /**
   * Delete a conversation
   */
  async deleteConversation(sessionId: string): Promise<void> {
    await this.client.delete(`/conversations/${sessionId}`);
  }

  /**
   * Add a message to a conversation
   */
  async addMessage(
    sessionId: string,
    role: string,
    content: string,
    agentName?: string,
    messageType?: string,
    metaInfo?: Record<string, unknown>
  ): Promise<void> {
    const params = new URLSearchParams();
    params.append('role', role);
    params.append('content', content);
    if (agentName) params.append('agent_name', agentName);
    if (messageType) params.append('message_type', messageType);

    await this.client.post(
      `/conversations/${sessionId}/messages?${params.toString()}`,
      metaInfo ? { meta_info: metaInfo } : undefined
    );
  }

  /**
   * Add an artifact to a conversation
   */
  async addArtifact(
    sessionId: string,
    filename: string,
    language: string,
    content: string,
    taskNum?: number
  ): Promise<void> {
    const params = new URLSearchParams();
    params.append('filename', filename);
    params.append('language', language);
    params.append('content', content);
    if (taskNum !== undefined) params.append('task_num', taskNum.toString());

    await this.client.post(
      `/conversations/${sessionId}/artifacts?${params.toString()}`
    );
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
