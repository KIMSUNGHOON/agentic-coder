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
export interface ChecklistItem {
  id: number;
  task: string;
  completed: boolean;
}

export interface Artifact {
  type: string;
  language: string;
  filename: string;
  content: string;
}

export interface CompletedTask {
  task_num: number;
  task: string;
  artifacts: string[] | Artifact[];
}

export interface TaskResult {
  task_num: number;
  task: string;
  artifacts: Artifact[];
}

export interface WorkflowUpdate {
  agent: string;
  type: 'thinking' | 'artifact' | 'task_completed' | 'completed' | 'error';
  status: 'running' | 'completed' | 'error' | 'finished';
  message?: string;
  content?: string;
  items?: ChecklistItem[];
  artifact?: Artifact;
  artifacts?: Artifact[];
  checklist?: ChecklistItem[];
  completed_tasks?: CompletedTask[];
  task_result?: TaskResult;
  issues?: string[];
  suggestions?: string[];
  approved?: boolean;
  corrected_artifacts?: Artifact[];
  summary?: {
    tasks_completed: number;
    total_tasks: number;
    artifacts_count: number;
    review_approved: boolean;
  };
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
