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

// Agent spawn event info
export interface AgentSpawnInfo {
  agent_id: string;
  agent_type: string;
  parent_agent?: string;
  spawn_reason: string;
  timestamp: string;
}

// Prompt execution info for debugging/transparency
export interface PromptInfo {
  system_prompt: string;
  user_prompt: string;
  output?: string;
  model?: string;
  tokens_used?: number;
  latency_ms?: number;
}

// Workflow step info
export interface WorkflowInfo {
  workflow_id: string;
  workflow_type: string;
  nodes: string[];
  edges: Array<{ from: string; to: string; condition?: string }>;
  current_node?: string;
  max_iterations?: number;
  final_status?: string;
}

// Decision info for review decisions
export interface DecisionInfo {
  approved: boolean;
  iteration: number;
  max_iterations: number;
  action: 'end' | 'fix_code' | 'end_max_iterations';
}

// Iteration tracking info
export interface IterationInfo {
  current: number;
  max: number;
}

export interface WorkflowUpdate {
  agent: string;
  type: 'thinking' | 'artifact' | 'task_completed' | 'completed' | 'error' | 'agent_spawn' | 'workflow_created' | 'decision';
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
    review_iterations?: number;
    max_iterations?: number;
  };
  // Transparency fields
  prompt_info?: PromptInfo;
  agent_spawn?: AgentSpawnInfo;
  workflow_info?: WorkflowInfo;
  // Decision and iteration fields
  decision?: DecisionInfo;
  iteration_info?: IterationInfo;
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
