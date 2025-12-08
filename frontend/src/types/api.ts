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

// Workflow types
export interface WorkflowUpdate {
  agent: string;
  status: 'running' | 'completed' | 'error' | 'finished';
  content: string;
}

export interface WorkflowRequest {
  message: string;
  session_id: string;
}

// Conversation persistence types
export interface StoredMessage {
  id: number;
  role: string;
  content: string;
  agent_name?: string;
  message_type?: string;
  meta_info?: Record<string, unknown>;
  created_at: string;
}

export interface StoredArtifact {
  id: number;
  filename: string;
  language: string;
  content: string;
  task_num?: number;
  version: number;
  created_at: string;
}

export interface Conversation {
  id: number;
  session_id: string;
  title: string;
  mode: 'chat' | 'workflow';
  created_at: string;
  updated_at: string;
  message_count: number;
  workflow_state?: Record<string, unknown>;
  messages?: StoredMessage[];
  artifacts?: StoredArtifact[];
}

export interface ConversationListResponse {
  conversations: Conversation[];
  count: number;
  limit: number;
  offset: number;
}
