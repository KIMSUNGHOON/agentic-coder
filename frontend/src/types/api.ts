/**
 * API types matching backend Pydantic models
 */

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  task_type?: 'reasoning' | 'coding';
  system_prompt?: string;
  stream?: boolean;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  task_type: string;
}

export interface AgentStatus {
  session_id: string;
  message_count: number;
  history: ChatMessage[];
}

export interface ModelInfo {
  name: string;
  endpoint: string;
  type: string;
}

export interface ModelsResponse {
  models: ModelInfo[];
}

export interface ErrorResponse {
  error: string;
  detail?: string;
}
