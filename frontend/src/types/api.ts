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
  type?: string;
  language: string;
  filename: string;
  content: string;
  description?: string;  // Optional description of the file's purpose
  saved?: boolean;  // Whether the file was saved successfully
  saved_path?: string | null;  // Path where the file was saved
  saved_at?: string | null;  // Timestamp when file was saved
  error?: string | null;  // Error message if save failed
  // Enhanced fields for better UI display
  action?: 'created' | 'modified';  // Whether file was created or modified
  relative_path?: string;  // Path relative to project root
  project_root?: string;  // Project root directory
  file_path?: string;  // Full absolute path
  size_bytes?: number;  // File size in bytes
  checksum?: string;  // File checksum for integrity
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
  task_type?: string;
  nodes: string[];
  edges: Array<{ from: string; to: string; condition?: string }>;
  current_node?: string;
  max_iterations?: number;
  final_status?: string;
  dynamically_created?: boolean;
}

// Task analysis from SupervisorAgent
export interface TaskAnalysis {
  task_type: string;
  workflow_name: string;
  agents: string[];
  has_review_loop: boolean;
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

// Final result from workflow completion
export interface FinalResult {
  success: boolean;
  message: string;
  tasks_completed: number;
  total_tasks: number;
  artifacts: Array<{ filename: string; language: string }>;
  review_status: 'approved' | 'needs_revision' | 'skipped';
  review_iterations: number;
}

// Structured review issue with line info
export interface ReviewIssue {
  file?: string;
  line?: string;
  severity?: 'critical' | 'warning' | 'info';
  issue: string;
  fix?: string;
}

// Structured review suggestion with line info
export interface ReviewSuggestion {
  file?: string;
  line?: string;
  suggestion: string;
}

// Shared context types for parallel execution
export interface SharedContextEntry {
  agent_id: string;
  agent_type: string;
  key: string;
  value_preview: string;
  description: string;
  timestamp: string;
}

export interface SharedContextAccessLog {
  action: 'set' | 'get';
  agent_id?: string;
  requesting_agent?: string;
  source_agent?: string;
  agent_type?: string;
  key: string;
  timestamp: string;
}

export interface SharedContextData {
  entries: SharedContextEntry[];
  access_log: SharedContextAccessLog[];
}

export interface CodePreview {
  task_idx: number;
  agent_id: string;
  filename: string;
  preview: string;
  chars: number;
}

export interface WorkflowUpdate {
  agent: string;
  agent_label?: string;  // Custom display name for the agent (task-based)
  task_description?: string;  // Description of what this agent is doing
  type: 'thinking' | 'artifact' | 'task_completed' | 'completed' | 'error' | 'agent_spawn' | 'workflow_created' | 'decision' | 'mode_selection' | 'parallel_start' | 'parallel_batch' | 'parallel_complete' | 'shared_context' | 'code_preview' | 'project_info' | 'update' | 'streaming';
  status: 'running' | 'completed' | 'error' | 'finished' | 'starting' | 'thinking' | 'streaming' | 'awaiting_approval';
  message?: string;
  // Real-time streaming content
  streaming_content?: string;  // Current content being generated by agent
  streaming_file?: string;  // File currently being generated
  streaming_progress?: string;  // Progress indicator (e.g., "2/5")
  execution_time?: number;  // Agent execution time in seconds
  // Project info fields
  project_name?: string;
  full_path?: string;
  content?: string;
  items?: ChecklistItem[];
  artifact?: Artifact;
  artifacts?: Artifact[];
  checklist?: ChecklistItem[];
  completed_tasks?: CompletedTask[];
  task_result?: TaskResult;
  code_preview?: CodePreview;
  // Review fields - can be string[] (old format) or structured (new format)
  analysis?: string;
  issues?: (string | ReviewIssue)[];
  suggestions?: (string | ReviewSuggestion)[];
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
  task_analysis?: TaskAnalysis;
  // Decision and iteration fields
  decision?: DecisionInfo;
  iteration_info?: IterationInfo;
  // Final result
  final_result?: FinalResult;
  // Parallel execution fields
  execution_mode?: 'sequential' | 'parallel';
  parallel_config?: {
    max_parallel_agents: number;
    total_tasks: number;
  };
  parallel_info?: {
    total_tasks: number;
    max_parallel: number;
  };
  batch_info?: {
    batch_num: number;
    tasks: number[];
  };
  parallel_summary?: {
    total_tasks: number;
    completed_tasks: number;
    total_artifacts: number;
    agents_used: number;
  };
  parallel_agent_id?: string;
  code_text?: string;
  // Shared context
  shared_context?: SharedContextData;
  shared_context_refs?: Array<{ key: string; from_agent?: string } | string>;
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

// ==================== LangGraph / Supervisor Types ====================

/**
 * Request to execute LangGraph workflow with Supervisor orchestration
 */
export interface LangGraphWorkflowRequest {
  user_request: string;
  workspace_root: string;
  task_type?: 'implementation' | 'review' | 'testing' | 'security_audit' | 'general';
  enable_debug?: boolean;
}

/**
 * Supervisor analysis result
 */
export interface SupervisorAnalysis {
  user_request: string;
  complexity: 'simple' | 'moderate' | 'complex' | 'critical';
  task_type: string;
  required_agents: string[];
  workflow_strategy: 'linear' | 'parallel_gates' | 'adaptive_loop' | 'staged_approval';
  max_iterations: number;
  requires_human_approval: boolean;
  reasoning: string;  // DeepSeek-R1 <think> block
}

/**
 * Real-time workflow event from SSE stream
 */
export interface LangGraphWorkflowEvent {
  node: string;  // Current node executing (e.g., "coder", "reviewer", "rca_analyzer")
  updates: Record<string, any>;  // State updates from node
  status: 'running' | 'completed' | 'error' | 'blocked' | 'awaiting_approval';

  // Optional fields based on node
  supervisor_analysis?: SupervisorAnalysis;
  workflow_graph?: WorkflowInfo;
  debug_logs?: DebugLog[];
  current_thinking?: string;  // DeepSeek-R1 <think> blocks
  artifacts?: Artifact[];
  review_feedback?: {
    approved: boolean;
    issues: string[];
    suggestions: string[];
    quality_score: number;
  };
  rca_analysis?: string;  // Root cause analysis
  code_diffs?: CodeDiff[];
}

/**
 * Debug log entry
 */
export interface DebugLog {
  timestamp: string;
  node: string;
  agent: string;
  event_type: 'thinking' | 'tool_call' | 'prompt' | 'result' | 'error';
  content: string;
  metadata?: Record<string, any>;
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

/**
 * Code diff for refinement
 */
export interface CodeDiff {
  file_path: string;
  original_content: string;
  modified_content: string;
  diff_hunks: string[];
  description: string;
}

/**
 * Human approval request
 */
export interface LangGraphApprovalRequest {
  session_id: string;
  approved: boolean;
  message?: string;
}

/**
 * Workflow execution status
 */
export interface WorkflowExecutionStatus {
  session_id: string;
  status: 'running' | 'completed' | 'failed' | 'self_healing' | 'blocked' | 'awaiting_approval';
  current_node?: string;
  iteration?: number;
  max_iterations?: number;
  artifacts?: Artifact[];
  error_log?: string[];
}

// ==================== HITL (Human-in-the-Loop) Types ====================

/**
 * HITL checkpoint types
 */
export type HITLCheckpointType = 'approval' | 'review' | 'edit' | 'choice' | 'confirm';

/**
 * HITL request status
 */
export type HITLStatus = 'pending' | 'approved' | 'rejected' | 'modified' | 'selected' | 'cancelled' | 'timeout';

/**
 * HITL action types
 */
export type HITLAction = 'approve' | 'reject' | 'edit' | 'retry' | 'select' | 'confirm' | 'cancel';

/**
 * Choice option for HITL choice checkpoint
 */
export interface HITLChoiceOption {
  option_id: string;
  title: string;
  description: string;
  preview?: string;
  pros: string[];
  cons: string[];
  recommended: boolean;
  metadata?: Record<string, any>;
}

/**
 * HITL content
 */
export interface HITLContent {
  code?: string;
  language?: string;
  filename?: string;
  workflow_plan?: Record<string, any>;
  options?: HITLChoiceOption[];
  original?: string;
  modified?: string;
  diff?: string;
  action_description?: string;
  risks?: string[];
  summary?: string;
  details?: Record<string, any>;
}

/**
 * HITL request from backend
 */
export interface HITLRequest {
  request_id: string;
  workflow_id: string;
  stage_id: string;
  agent_id?: string;
  checkpoint_type: HITLCheckpointType;
  title: string;
  description: string;
  content: HITLContent;
  allow_skip?: boolean;
  timeout_seconds?: number;
  priority: string;
  created_at: string;
  expires_at?: string;
  status: HITLStatus;
}

/**
 * HITL response to backend
 */
export interface HITLResponse {
  request_id: string;
  action: HITLAction;
  feedback?: string;
  modified_content?: string;
  selected_option?: string;
  retry_instructions?: string;
  responded_at?: string;
}

/**
 * HITL WebSocket event
 */
export interface HITLEvent {
  event_type: 'hitl.request' | 'hitl.response' | 'hitl.timeout' | 'hitl.cancelled' | 'hitl.pending';
  workflow_id: string;
  request_id?: string;
  data: HITLRequest | HITLResponse | Record<string, any>;
  timestamp: string;
}

/**
 * HITL request summary for listing
 */
export interface HITLRequestSummary {
  request_id: string;
  workflow_id: string;
  stage_id: string;
  checkpoint_type: HITLCheckpointType;
  title: string;
  status: HITLStatus;
  priority: string;
  created_at: string;
}
