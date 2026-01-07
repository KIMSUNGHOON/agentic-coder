/**
 * WorkflowInterface component - Claude.ai inspired multi-agent workflow UI
 * Supports conversation context for iterative refinement
 * Now with split layout: Conversation (left) + Workflow Status (right)
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { WorkflowUpdate, Artifact, WorkflowInfo, HITLRequest, HITLCheckpointType } from '../types/api';
import SharedContextViewer from './SharedContextViewer';
import WorkflowGraph from './WorkflowGraph';
import WorkspaceProjectSelector from './WorkspaceProjectSelector';
import DebugPanel from './DebugPanel';
import HITLModal from './HITLModal';
import WorkflowStatusPanel from './WorkflowStatusPanel';
import DashboardHeader from './DashboardHeader';
import TerminalOutput from './TerminalOutput';
import FileTreeViewer from './FileTreeViewer';
import NextActionsPanel from './NextActionsPanel';
import PlanFileViewer from './PlanFileViewer';
import apiClient from '../api/client';
import { getDefaultWorkspace, getDefaultWorkspacePlaceholder } from '../utils/workspace';

// 확장/축소 가능한 콘텐츠 컴포넌트
const ExpandableContent = ({
  content,
  maxLines = 5,
  children
}: {
  content: string;
  maxLines?: number;
  children: React.ReactNode;
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [needsExpansion, setNeedsExpansion] = useState(false);

  useEffect(() => {
    // 콘텐츠가 maxLines를 초과하는지 확인
    const lineCount = content.split('\n').length;
    const charThreshold = maxLines * 80; // 대략적인 문자 수 기준
    setNeedsExpansion(lineCount > maxLines || content.length > charThreshold);
  }, [content, maxLines]);

  // 중요 콘텐츠 추출 (첫 번째 단락 또는 제목)
  const getImportantContent = () => {
    const lines = content.split('\n');
    const importantLines: string[] = [];
    let foundImportant = false;

    for (let i = 0; i < Math.min(lines.length, maxLines); i++) {
      const line = lines[i];
      // 제목, 요약, 결과 등 중요 라인 감지
      if (line.startsWith('#') || line.startsWith('##') ||
          line.includes('완료') || line.includes('생성') ||
          line.includes('결과') || line.includes('요약') ||
          line.includes('✓') || line.includes('✅')) {
        importantLines.push(line);
        foundImportant = true;
      } else if (!foundImportant && line.trim()) {
        importantLines.push(line);
      }
    }
    return importantLines.join('\n');
  };

  if (!needsExpansion) {
    return <>{children}</>;
  }

  return (
    <div className="relative">
      <div
        ref={contentRef}
        className={`overflow-hidden transition-all duration-300 ${
          isExpanded ? 'max-h-none' : 'max-h-32'
        }`}
        style={!isExpanded ? {
          maskImage: 'linear-gradient(to bottom, black 60%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, black 60%, transparent 100%)'
        } : undefined}
      >
        {children}
      </div>

      {/* 확장/축소 버튼 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-1 flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition-colors"
      >
        <span>{isExpanded ? '▲' : '▼'}</span>
        <span>{isExpanded ? '접기' : `더 보기 (${content.split('\n').length}줄)`}</span>
      </button>
    </div>
  );
};

// Agent status for progress tracking
interface AgentProgressStatus {
  name: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  executionTime?: number;
  streamingContent?: string;
  // Token usage tracking
  tokenUsage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

interface DebugLog {
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

interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
  updates?: WorkflowUpdate[];
  artifacts?: Artifact[];
  timestamp: number;
}

interface SharedContextData {
  entries: Array<{
    agent_id: string;
    agent_type: string;
    key: string;
    value_preview: string;
    description: string;
    timestamp: string;
  }>;
  access_log: Array<{
    action: 'set' | 'get';
    agent_id?: string;
    requesting_agent?: string;
    source_agent?: string;
    agent_type?: string;
    key: string;
    timestamp: string;
  }>;
}

interface WorkflowInterfaceProps {
  sessionId: string;
  initialUpdates?: WorkflowUpdate[];
  workspace?: string;
  selectedPrompt?: string;
  onPromptUsed?: () => void;
  onWorkspaceChange?: (workspace: string) => void;
}

const WorkflowInterface = ({ sessionId, initialUpdates, workspace: workspaceProp, selectedPrompt, onPromptUsed, onWorkspaceChange }: WorkflowInterfaceProps) => {
  const [input, setInput] = useState('');
  const [updates, setUpdates] = useState<WorkflowUpdate[]>([]);
  const [conversationHistory, setConversationHistory] = useState<ConversationTurn[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [currentWorkflowInfo, setCurrentWorkflowInfo] = useState<WorkflowInfo | null>(null);
  const [sharedContext, setSharedContext] = useState<SharedContextData | null>(null);
  const [showSharedContext, setShowSharedContext] = useState(false);
  const [, setExecutionMode] = useState<'sequential' | 'parallel' | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Workspace configuration - NOW AUTO-GENERATED BY BACKEND
  // Path format: $DEFAULT_WORKSPACE/{session_id}/{project_name}
  const [workspace, setWorkspace] = useState<string>('');  // Will be set by backend
  const [showWorkspaceDialog, setShowWorkspaceDialog] = useState<boolean>(false);  // Disabled - backend manages workspace
  const [workspaceInput, setWorkspaceInput] = useState<string>('');  // Not used anymore
  const [projectName, setProjectName] = useState<string>('');
  const [workspaceStep, setWorkspaceStep] = useState<'project' | 'path'>('project'); // Two-step dialog

  // Save conversation confirmation
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [pendingSaveData, setPendingSaveData] = useState<WorkflowUpdate[] | null>(null);
  const [autoSave, setAutoSave] = useState<boolean>(() => {
    const saved = localStorage.getItem('workflow_auto_save');
    return saved === null ? true : saved === 'true'; // Default to true
  });

  // Debug panel state
  const [debugLogs, setDebugLogs] = useState<DebugLog[]>([]);
  const [isDebugOpen, setIsDebugOpen] = useState(false);

  // HITL (Human-in-the-Loop) state
  const [hitlRequest, setHitlRequest] = useState<HITLRequest | null>(null);
  const [isHitlModalOpen, setIsHitlModalOpen] = useState(false);

  // Thinking stream state (DeepSeek-R1)
  const [thinkingStream, setThinkingStream] = useState<string[]>([]);
  const [isThinking, setIsThinking] = useState(false);

  // Execution mode: "auto" (detect), "quick" (Q&A only), "full" (code generation), "unified" (new Claude-style API)
  const [executionMode, setExecutionModeState] = useState<'auto' | 'quick' | 'full' | 'unified'>(() => {
    const saved = localStorage.getItem('workflow_execution_mode');
    return (saved as 'auto' | 'quick' | 'full' | 'unified') || 'auto';
  });

  // System prompt customization
  const [systemPrompt, setSystemPrompt] = useState<string>(() => {
    return localStorage.getItem('workflow_system_prompt') || '';
  });
  const [showSystemPromptModal, setShowSystemPromptModal] = useState(false);
  const [tempSystemPrompt, setTempSystemPrompt] = useState('');

  // Agent info mapping for dynamic agent display
  const getAgentInfo = (name: string): { title: string; description: string } => {
    const agentMap: Record<string, { title: string; description: string }> = {
      'supervisor': { title: '🧠 Supervisor', description: 'Task Analysis' },
      'architect': { title: '🏗️ Architect', description: 'Project Design' },
      'coder': { title: '💻 Coder', description: 'Implementation' },
      'reviewer': { title: '👀 Reviewer', description: 'Code Review' },
      'qa_gate': { title: '🧪 QA Tester', description: 'Testing' },
      'security_gate': { title: '🔒 Security', description: 'Security Audit' },
      'refiner': { title: '🔧 Refiner', description: 'Code Refinement' },
      'aggregator': { title: '📊 Aggregator', description: 'Results Aggregation' },
      'hitl': { title: '👤 Human Review', description: 'Awaiting Approval' },
      'persistence': { title: '💾 Persistence', description: 'Saving Files' },
      'unifiedagentmanager': { title: '🎯 UnifiedAgentManager', description: 'Workflow Management' },
      'planninghandler': { title: '📋 PlanningHandler', description: 'Plan Generation' },
      'codegenerationhandler': { title: '💻 CodeGenerator', description: 'Code Generation' },
      'orchestrator': { title: '🎭 Orchestrator', description: 'Task Orchestration' },
      'workspaceexplorer': { title: '🔍 Explorer', description: 'Workspace Analysis' },
    };
    const info = agentMap[name.toLowerCase()];
    if (info) return info;
    // Fallback: create title from name
    const formattedName = name.replace(/([A-Z])/g, ' $1').replace(/^./, s => s.toUpperCase()).trim();
    return { title: `⚡ ${formattedName}`, description: 'Processing' };
  };

  // Enhanced progress tracking - starts empty, dynamically populated
  const [agentProgress, setAgentProgress] = useState<AgentProgressStatus[]>([]);
  const [totalProgress, setTotalProgress] = useState(0);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<number | undefined>();
  const [elapsedTime, setElapsedTime] = useState(0);
  const [workflowStartTime, setWorkflowStartTime] = useState<number | null>(null);
  const [currentStreamingFile, setCurrentStreamingFile] = useState<string | null>(null);
  const [currentStreamingContent, setCurrentStreamingContent] = useState<string>('');
  const [savedFiles, setSavedFiles] = useState<Artifact[]>([]);
  const [isDownloadingZip, setIsDownloadingZip] = useState(false);

  // Unified API response state (Next Actions, Plan File)
  const [nextActions, setNextActions] = useState<string[]>([]);
  const [planFilePath, setPlanFilePath] = useState<string | null>(null);
  const [isPlanViewerOpen, setIsPlanViewerOpen] = useState(false);

  // Live Output state for conversation area - track outputs from each agent
  const [liveOutputs, setLiveOutputs] = useState<Map<string, {
    agentName: string;
    agentTitle: string;
    content: string;
    status: string;
    timestamp: number;
  }>>(new Map());
  const [showStatusPanel, setShowStatusPanel] = useState(true);
  const [currentProjectName, setCurrentProjectName] = useState<string | undefined>();
  const [currentProjectDir, setCurrentProjectDir] = useState<string | undefined>();
  const [isConversationCollapsed, setIsConversationCollapsed] = useState(false);

  const scrollToBottom = useCallback(() => {
    // Use setTimeout to ensure DOM is updated before scrolling
    setTimeout(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
      }
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, []);

  // Copy text to clipboard
  const copyToClipboard = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // Show brief visual feedback (could be enhanced with toast notification)
      return true;
    } catch (err) {
      console.error('Failed to copy:', err);
      return false;
    }
  }, []);

  // Track elapsed time during workflow
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isRunning && workflowStartTime) {
      interval = setInterval(() => {
        setElapsedTime((Date.now() - workflowStartTime) / 1000);
      }, 100);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isRunning, workflowStartTime]);

  // Reset progress when workflow starts
  const resetProgress = () => {
    // Reset to empty - agents will be added dynamically as they run
    setAgentProgress([]);
    setTotalProgress(0);
    setEstimatedTimeRemaining(undefined);
    setElapsedTime(0);
    setWorkflowStartTime(Date.now());
    setCurrentStreamingFile(null);
    setCurrentStreamingContent('');
    setSavedFiles([]);
    setCurrentProjectName(undefined);
    setCurrentProjectDir(undefined);
    setLiveOutputs(new Map());  // Clear live outputs on new workflow
    // Clear thinking state on new workflow
    setIsThinking(false);
    setThinkingStream([]);
    // Clear unified response state
    setNextActions([]);
    setPlanFilePath(null);
  };

  // Refinement loop state (tracked for potential future UI display)
  const [_refinementIteration, setRefinementIteration] = useState(0);

  // Map backend node names to frontend agent names
  const mapNodeToAgent = (nodeName: string): string => {
    const normalizedName = nodeName?.toLowerCase().replace(/[^a-z]/g, '') || '';

    // Direct matches
    const directMapping: Record<string, string> = {
      'supervisor': 'supervisor',
      'supervisoragent': 'supervisor',
      'architect': 'architect',
      'architectagent': 'architect',
      'planning': 'architect',
      'planningagent': 'architect',
      'planninghandler': 'architect',
      'coder': 'coder',
      'coderagent': 'coder',
      'coding': 'coder',
      'codingagent': 'coder',
      'codegenerationhandler': 'coder',
      'reviewer': 'reviewer',
      'reviewagent': 'reviewer',
      'review': 'reviewer',
      'qa': 'qa_gate',
      'qagate': 'qa_gate',
      'qatester': 'qa_gate',
      'security': 'security_gate',
      'securitygate': 'security_gate',
      'refiner': 'refiner',
      'refinement': 'refiner',
      'fixcodeagent': 'refiner',
      'aggregator': 'aggregator',
      'persistence': 'persistence',
      'hitl': 'hitl',
      'human': 'hitl',
      'humanreview': 'hitl',
      'orchestrator': 'supervisor',
      'workspaceexplorer': 'architect',
      'unifiedagentmanager': 'supervisor',
    };

    if (directMapping[normalizedName]) {
      return directMapping[normalizedName];
    }

    // Pattern matching for partial matches
    if (normalizedName.includes('supervis') || normalizedName.includes('orchestr')) return 'supervisor';
    if (normalizedName.includes('plan') || normalizedName.includes('architect')) return 'architect';
    if (normalizedName.includes('cod') || normalizedName.includes('implement')) return 'coder';
    if (normalizedName.includes('review') || normalizedName.includes('검토')) return 'reviewer';
    if (normalizedName.includes('qa') || normalizedName.includes('test')) return 'qa_gate';
    if (normalizedName.includes('secur')) return 'security_gate';
    if (normalizedName.includes('refin') || normalizedName.includes('fix')) return 'refiner';
    if (normalizedName.includes('aggreg')) return 'aggregator';
    if (normalizedName.includes('persist') || normalizedName.includes('save')) return 'persistence';
    if (normalizedName.includes('human') || normalizedName.includes('hitl') || normalizedName.includes('approval')) return 'hitl';

    // Return original if no match found
    return normalizedName;
  };

  // Update agent progress from event
  const updateAgentProgress = (event: any) => {
    const rawNodeName = event.node;
    const nodeName = mapNodeToAgent(rawNodeName);
    const status = event.status;
    const executionTime = event.updates?.execution_time;
    const agentTitle = event.agent_title;
    const agentDescription = event.agent_description;
    // Check both direct streaming_content and updates.streaming_content
    const streamingContent = event.streaming_content || event.updates?.streaming_content;
    const currentRefinementIteration = event.updates?.refinement_iteration || event.updates?.iteration;

    // Track refinement iteration
    if (currentRefinementIteration !== undefined && currentRefinementIteration > 0) {
      setRefinementIteration(currentRefinementIteration);
    }

    // Handle refinement loop specific statuses
    if (nodeName === 'refiner') {
      if (status === 'iteration_start') {
        // Re-run quality gates, reset their status
        setAgentProgress(prev => prev.map(agent => {
          if (['reviewer', 'qa_gate', 'security_gate'].includes(agent.name)) {
            return {
              ...agent,
              status: 'pending',
              description: `Re-evaluating (iteration ${currentRefinementIteration + 1})`,
              streamingContent: undefined,
            };
          }
          return agent;
        }));
      }
      if (status === 'max_iterations_reached') {
        // Mark refiner as completed even if max iterations reached
        setAgentProgress(prev => prev.map(agent => {
          if (agent.name === 'refiner') {
            return {
              ...agent,
              status: 'completed',
              description: `Max iterations (${event.updates?.max_iterations}) reached`,
              streamingContent: streamingContent,
            };
          }
          return agent;
        }));
        return;
      }
    }

    // Handle workflow-level status updates (retry_requested, rejected, etc.)
    if (nodeName === 'workflow') {
      if (status === 'retry_requested' || status === 'rejected') {
        // Update HITL agent status to show the result
        setAgentProgress(prev => prev.map(agent => {
          if (agent.name === 'hitl') {
            return {
              ...agent,
              status: status === 'retry_requested' ? 'running' : 'error',
              description: status === 'retry_requested' ? 'Retry Requested' : 'Rejected',
              streamingContent: streamingContent,
            };
          }
          return agent;
        }));
        return;
      }
    }

    // Handle HITL-specific statuses
    if (nodeName === 'hitl') {
      if (status === 'retry_requested' || status === 'rejected' || status === 'approved') {
        setAgentProgress(prev => prev.map(agent => {
          if (agent.name === 'hitl') {
            return {
              ...agent,
              status: status === 'approved' ? 'completed' : 'error',
              description: status === 'approved' ? 'Approved' : status === 'retry_requested' ? 'Retry Requested' : 'Rejected',
              streamingContent: streamingContent,
            };
          }
          return agent;
        }));
        // Continue processing for retry/reject to handle workflow stopped
      }
    }

    // Handle workflow restarting status (retry)
    if (nodeName === 'workflow' && status === 'restarting') {
      console.log(`[Workflow] Restarting: retry=${event.updates?.retry_count}, feedback=${event.updates?.feedback}`);
      // Reset agent progress for new attempt
      setAgentProgress(prev => prev.map(agent => ({
        ...agent,
        status: 'pending',
        executionTime: undefined,
        streamingContent: undefined,
      })));
      setTotalProgress(0);
      setSavedFiles([]);
      // Don't stop running - workflow will continue
    }

    // Handle workflow stopped status (reject only)
    if (nodeName === 'workflow' && (status === 'stopped' || event.updates?.is_final)) {
      console.log(`[Workflow] Stopped: reason=${event.updates?.reason}, action=${event.updates?.action}`);
      setIsRunning(false);
      // Don't return here - let the update be added to the list
    }

    setAgentProgress(prev => {
      // Skip workflow-level events for agent list
      if (nodeName === 'workflow') return prev;

      // Check if agent already exists
      const existingAgent = prev.find(a => a.name === nodeName);

      // Determine new status
      let newStatus: AgentProgressStatus['status'] = 'pending';
      if (status === 'starting' || status === 'running' || status === 'thinking' || status === 'streaming' || status === 'awaiting_approval' || status === 'waiting') {
        newStatus = 'running';
      } else if (status === 'completed' || status === 'approved') {
        newStatus = 'completed';
      } else if (status === 'error' || status === 'rejected' || status === 'timeout') {
        newStatus = 'error';
      }

      // Build description with refinement iteration info
      const agentInfo = getAgentInfo(nodeName);
      let description = agentDescription || (existingAgent?.description || agentInfo.description);
      if (currentRefinementIteration && currentRefinementIteration > 0) {
        if (['reviewer', 'qa_gate', 'security_gate'].includes(nodeName)) {
          description = `${description} (iter ${currentRefinementIteration + 1})`;
        } else if (nodeName === 'refiner') {
          description = `Iteration ${currentRefinementIteration}/${event.updates?.max_iterations || 3}`;
        }
      }

      // Capture token usage if provided in event
      const eventTokenUsage = event.updates?.token_usage;
      let tokenUsage = existingAgent?.tokenUsage;
      if (eventTokenUsage) {
        tokenUsage = {
          promptTokens: eventTokenUsage.prompt_tokens || eventTokenUsage.promptTokens || 0,
          completionTokens: eventTokenUsage.completion_tokens || eventTokenUsage.completionTokens || 0,
          totalTokens: eventTokenUsage.total_tokens || eventTokenUsage.totalTokens || 0,
        };
      }

      let updated: AgentProgressStatus[];

      if (existingAgent) {
        // Update existing agent
        updated = prev.map(agent => {
          if (agent.name === nodeName) {
            return {
              ...agent,
              title: agentTitle || agent.title,
              description: description,
              status: newStatus,
              executionTime: executionTime !== undefined ? executionTime : agent.executionTime,
              streamingContent: streamingContent || agent.streamingContent,
              tokenUsage: tokenUsage,
            };
          }
          return agent;
        });
      } else {
        // Add new agent dynamically
        const newAgent: AgentProgressStatus = {
          name: nodeName,
          title: agentTitle || agentInfo.title,
          description: description,
          status: newStatus,
          executionTime: executionTime,
          streamingContent: streamingContent,
          tokenUsage: tokenUsage,
        };
        updated = [...prev, newAgent];
      }

      // Calculate total progress
      const completedCount = updated.filter(a => a.status === 'completed').length;
      const runningCount = updated.filter(a => a.status === 'running').length;
      const totalAgents = updated.length || 1;
      const progress = ((completedCount + runningCount * 0.5) / totalAgents) * 100;
      setTotalProgress(Math.min(progress, 100));

      return updated;
    });

    // Update ETA if provided
    if (event.updates?.estimated_total_time) {
      const elapsed = elapsedTime;
      const total = event.updates.estimated_total_time;
      setEstimatedTimeRemaining(Math.max(0, total - elapsed));
    }

    // Update streaming content
    // Handle parallel streaming (multiple files)
    if (event.updates?.is_parallel && event.updates?.streaming_files) {
      const files = event.updates.streaming_files;
      setCurrentStreamingFile(files.join(', '));
    } else if (event.updates?.streaming_file) {
      setCurrentStreamingFile(event.updates.streaming_file);
    }
    // Update current streaming content (check both direct and updates.streaming_content)
    if (streamingContent) {
      setCurrentStreamingContent(streamingContent);
    }

    // ALWAYS update live outputs for agent status changes (not just when streaming_content exists)
    // This ensures running indicators update correctly when agents complete
    // Note: Don't require agentInfo to exist - it may not be added yet due to React state timing
    const agentInfo = agentProgress.find(a => a.name === nodeName);
    const fallbackTitle = getAgentInfo(nodeName).title;  // Fallback to generated title

    // Always update liveOutputs for any agent (including Unified API handlers)
    setLiveOutputs(prev => {
      const newMap = new Map(prev);
      const existing = prev.get(nodeName);

      // Only update if status changed or new content available
      // Check both direct streaming_content and updates.streaming_content
      const newContent = streamingContent || existing?.content || '';
      const shouldUpdate = !existing ||
        existing.status !== status ||
        streamingContent;

      if (shouldUpdate) {
        newMap.set(nodeName, {
          agentName: nodeName,
          agentTitle: agentTitle || agentInfo?.title || fallbackTitle,
          content: newContent,
          status: status,
          timestamp: Date.now(),
        });
      }
      return newMap;
    });

    // Handle parallel file progress info
    if (event.updates?.batch_info) {
      const batchInfo = event.updates.batch_info;
      console.log(`[Parallel Coder] Batch ${batchInfo.current}/${batchInfo.total}, ${batchInfo.files_in_batch} files`);
    }

    // Helper function to merge files with deduplication by filename
    const mergeFiles = (prevFiles: any[], newFiles: any[]) => {
      const fileMap = new Map<string, any>();
      // Add existing files first
      prevFiles.forEach(f => fileMap.set(f.filename, f));
      // Add/update new files (newer versions overwrite)
      newFiles.forEach(f => fileMap.set(f.filename, f));
      const merged = Array.from(fileMap.values());
      console.log(`[mergeFiles] ${prevFiles.length} prev + ${newFiles.length} new = ${merged.length} total`);
      return merged;
    };

    // CONSOLIDATED ARTIFACT CAPTURE
    // Capture artifacts from multiple sources and merge them together
    // Priority: 1. Direct artifacts (plural), 2. Single artifact, 3. saved_files, 4. final_artifacts, 5. task_result.artifacts, 6. coder_output.artifacts
    const captureArtifacts = () => {
      let artifactsToCapture: any[] = [];

      // Source 1: Direct artifacts array (most common)
      if (event.updates?.artifacts && Array.isArray(event.updates.artifacts) && event.updates.artifacts.length > 0) {
        artifactsToCapture = event.updates.artifacts;
        console.log(`[${nodeName}:${status}] Captured ${artifactsToCapture.length} direct artifacts`);
      }

      // Source 2: Single artifact (singular) - 백엔드가 "artifact" 단수로 보내는 경우
      if (artifactsToCapture.length === 0 && event.updates?.artifact) {
        artifactsToCapture = [event.updates.artifact];
        console.log(`[${nodeName}:${status}] Captured 1 single artifact`);
      }

      // Source 3: saved_files (from persistence)
      if (artifactsToCapture.length === 0 && event.updates?.saved_files && Array.isArray(event.updates.saved_files)) {
        artifactsToCapture = event.updates.saved_files;
        console.log(`[${nodeName}:${status}] Captured ${artifactsToCapture.length} from saved_files`);
      }

      // Source 4: final_artifacts (from workflow completion)
      if (artifactsToCapture.length === 0 && event.updates?.final_artifacts && Array.isArray(event.updates.final_artifacts)) {
        artifactsToCapture = event.updates.final_artifacts;
        console.log(`[${nodeName}:${status}] Captured ${artifactsToCapture.length} from final_artifacts`);
      }

      // Source 5: task_result.artifacts (from task completion)
      if (artifactsToCapture.length === 0 && event.updates?.task_result?.artifacts && Array.isArray(event.updates.task_result.artifacts)) {
        artifactsToCapture = event.updates.task_result.artifacts;
        console.log(`[${nodeName}:${status}] Captured ${artifactsToCapture.length} from task_result.artifacts`);
      }

      // Source 6: Nested coder_output.artifacts (fallback for coder)
      if (artifactsToCapture.length === 0 && nodeName === 'coder' && event.updates?.coder_output?.artifacts) {
        artifactsToCapture = event.updates.coder_output.artifacts;
        console.log(`[${nodeName}:${status}] Captured ${artifactsToCapture.length} from coder_output.artifacts`);
      }

      // Merge captured artifacts if any found
      if (artifactsToCapture.length > 0) {
        setSavedFiles(prev => {
          const merged = mergeFiles(prev, artifactsToCapture);
          console.log(`[Artifacts] After merge: ${merged.length} total files`);
          return merged;
        });
      }
    };

    // Capture artifacts on completed events or when artifacts are present (including singular artifact)
    if (status === 'completed' || event.updates?.artifacts || event.updates?.artifact || event.updates?.saved_files || event.updates?.task_result?.artifacts) {
      captureArtifacts();
    }

    // Update project info from any source
    if (event.updates?.project_name) {
      setCurrentProjectName(event.updates.project_name);
    }
    if (event.updates?.project_dir) {
      setCurrentProjectDir(event.updates.project_dir);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [updates, conversationHistory, liveOutputs, scrollToBottom]);

  // Load initial updates when session changes
  useEffect(() => {
    if (initialUpdates && initialUpdates.length > 0) {
      setUpdates(initialUpdates);
      console.log(`Loaded ${initialUpdates.length} workflow updates for session ${sessionId}`);
    } else {
      setUpdates([]);
      setConversationHistory([]);
      console.log(`Starting new workflow session ${sessionId}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Populate input field when a prompt is selected from the library
  useEffect(() => {
    if (selectedPrompt && selectedPrompt.trim()) {
      setInput(selectedPrompt);
      // Focus on the input field after populating
      inputRef.current?.focus();
      // Call the callback to clear the selectedPrompt in parent
      onPromptUsed?.();
    }
  }, [selectedPrompt, onPromptUsed]);

  // Extract final artifacts from updates (keep last version of each file)
  const extractArtifacts = useCallback((workflowUpdates: WorkflowUpdate[]): Artifact[] => {
    // Use a map to keep only the latest version of each file
    const artifactMap = new Map<string, Artifact>();

    for (const update of workflowUpdates) {
      // Collect from array of artifacts
      if (update.artifacts) {
        for (const artifact of update.artifacts) {
          artifactMap.set(artifact.filename, artifact);  // Later versions overwrite earlier
        }
      }
      // Collect from single artifact
      if (update.artifact) {
        artifactMap.set(update.artifact.filename, update.artifact);
      }
    }

    // Return final artifacts (last version of each file)
    return Array.from(artifactMap.values());
  }, []);

  // Execute workflow using the new Unified API (Claude Code style)
  const executeUnifiedWorkflow = async (userMessage: string, allUpdates: WorkflowUpdate[]) => {
    try {
      // Stream from unified API
      for await (const update of apiClient.unifiedChatStream({
        message: userMessage,
        session_id: sessionId,
        workspace: workspace,
      })) {
        // Convert UnifiedStreamUpdate to WorkflowUpdate
        // IMPORTANT: Include streaming_content in initial object for real-time updates
        const workflowUpdate: WorkflowUpdate = {
          agent: update.agent,
          agent_title: update.agent,
          node: update.agent,  // Add node for updateAgentProgress mapping
          status: update.status,
          message: update.message,
          type: update.update_type,
          timestamp: update.timestamp || new Date().toISOString(),
          // Always include streaming_content when available for real-time display
          streaming_content: update.streaming_content || undefined,
        };

        // Handle different update types
        if (update.update_type === 'analysis' && update.data) {
          workflowUpdate.task_analysis = {
            response_type: update.data.response_type as string,
            complexity: update.data.complexity as 'simple' | 'moderate' | 'complex' | 'critical' | undefined,
            task_type: update.data.task_type as string,
            workflow_name: '',
            agents: [],
            has_review_loop: false,
          };
        }

        // Handle workspace_info event from backend (NEW: Auto-generated workspace)
        if (update.update_type === 'workspace_info' && update.data) {
          const workspaceData = update.data;
          if (workspaceData.workspace) {
            setWorkspace(workspaceData.workspace);
            console.log(`[workspace_info] Workspace set: ${workspaceData.workspace}`);
          }
          if (workspaceData.project_name) {
            setProjectName(workspaceData.project_name);
            console.log(`[workspace_info] Project name: ${workspaceData.project_name}`);
          }
        }

        // Handle individual artifact events (type='artifact')
        if (update.update_type === 'artifact' && update.data) {
          const artifactData = update.data.artifact || update.data;
          if (artifactData && artifactData.filename) {
            const artifact = {
              filename: artifactData.filename,
              language: artifactData.language || 'text',
              content: artifactData.content || '',
              saved_path: artifactData.saved_path,
              saved: artifactData.saved || false,
              saved_at: artifactData.saved_at,
              error: artifactData.error,
              action: 'created' as const,
            };
            workflowUpdate.artifact = artifact;
            // 개별 artifact도 savedFiles에 추가
            setSavedFiles(prev => {
              // 중복 체크
              const exists = prev.some(f => f.filename === artifact.filename);
              if (exists) {
                return prev.map(f => f.filename === artifact.filename ? artifact : f);
              }
              return [...prev, artifact];
            });
            console.log(`[artifact] Added file: ${artifact.filename}`);
          }
        }

        if (update.update_type === 'completed' && update.data) {
          // Extract artifacts from completed update
          if (update.data.artifacts) {
            workflowUpdate.artifacts = (update.data.artifacts as any[]).map(a => ({
              filename: a.filename,
              language: a.language || 'text',
              content: a.content || '',
              saved_path: a.saved_path,
              saved: a.saved || false,
              saved_at: a.saved_at,
              error: a.error,
              // Preserve backend action, default to 'created' only if not specified
              action: a.action || (a.saved ? 'created' : undefined),
            }));
            setSavedFiles(prev => {
              // Use Map for last-wins merge (update existing files, add new ones)
              const artifactMap = new Map<string, Artifact>();
              for (const artifact of prev) {
                artifactMap.set(artifact.filename, artifact);
              }
              for (const artifact of workflowUpdate.artifacts!) {
                artifactMap.set(artifact.filename, artifact);  // Later versions overwrite
              }
              return Array.from(artifactMap.values());
            });
            console.log(`[completed] Added ${workflowUpdate.artifacts.length} artifacts`);
          }
          // Extract full content for display, also check streaming_content
          if (update.data.full_content) {
            workflowUpdate.streaming_content = update.data.full_content as string;
          } else if (update.streaming_content) {
            workflowUpdate.streaming_content = update.streaming_content;
          }
        }

        if (update.update_type === 'thinking' || update.update_type === 'progress' || update.update_type === 'streaming') {
          setIsThinking(true);
          // Use streaming_content directly if available, fallback to message
          workflowUpdate.streaming_content = update.streaming_content || update.message;
        }

        if (update.update_type === 'done') {
          setIsThinking(false);
          // Extract next_actions and plan_file from done update
          if (update.data) {
            if (Array.isArray(update.data.next_actions)) {
              setNextActions(update.data.next_actions as string[]);
            }
            if (update.data.plan_file) {
              setPlanFilePath(update.data.plan_file as string);
            }
          }
        }

        // Handle completed handler updates
        if (update.update_type === 'completed' && update.data) {
          // Extract next_actions and plan_file from completed update
          if (Array.isArray(update.data.next_actions)) {
            setNextActions(update.data.next_actions as string[]);
          }
          if (update.data.plan_file) {
            setPlanFilePath(update.data.plan_file as string);
          }
        }

        // Update agent progress
        updateAgentProgress(workflowUpdate);

        // Add to allUpdates for history (all updates)
        allUpdates.push(workflowUpdate);

        // Only add significant updates to display (filter streaming noise)
        // Significant: completed, error, artifact, analysis, decision, mode_selection, agent_spawn, approved
        // Skip: thinking, progress, streaming (these are handled by liveOutputs)
        const significantTypes = ['completed', 'error', 'artifact', 'analysis', 'decision', 'mode_selection', 'approved', 'done'];
        const isSignificant = significantTypes.includes(update.update_type) ||
                              (workflowUpdate.artifacts && workflowUpdate.artifacts.length > 0) ||
                              workflowUpdate.status === 'error' ||
                              workflowUpdate.status === 'completed';

        if (isSignificant) {
          setUpdates(prev => [...prev, workflowUpdate]);
        }
      }

      // Save final state
      if (allUpdates.length > 0) {
        const lastUpdate = allUpdates[allUpdates.length - 1];
        const finalContent = lastUpdate.streaming_content || lastUpdate.message || '';

        setConversationHistory(prev => [
          ...prev,
          {
            role: 'assistant',
            content: finalContent,
            updates: [...allUpdates],
            artifacts: extractArtifacts(allUpdates),
            timestamp: Date.now()
          }
        ]);

        // Save to conversation
        try {
          await apiClient.addMessage(sessionId, 'assistant', finalContent, 'UnifiedAgent', 'workflow');
        } catch (err) {
          console.error('Failed to save assistant message:', err);
        }

        await saveWorkflowState(allUpdates);
      }

    } catch (error) {
      console.error('Unified workflow error:', error);
      const errorUpdate: WorkflowUpdate = {
        agent: 'System',
        status: 'error',
        message: error instanceof Error ? error.message : 'Unknown error occurred',
        type: 'error',
      };
      allUpdates.push(errorUpdate);
      setUpdates(prev => [...prev, errorUpdate]);
    } finally {
      setIsRunning(false);
      setIsThinking(false);
    }
  };

  // Save workflow state after updates complete
  const saveWorkflowState = async (workflowUpdates: WorkflowUpdate[], forcePrompt: boolean = false) => {
    // Check if we should prompt user
    if (!autoSave || forcePrompt) {
      setPendingSaveData(workflowUpdates);
      setShowSaveDialog(true);
      return;
    }

    // Auto-save enabled, save immediately
    try {
      await apiClient.updateConversation(sessionId, undefined, {
        updates: workflowUpdates,
      });
    } catch (err) {
      console.error('Failed to save workflow state:', err);
    }
  };

  // Handle save confirmation
  const handleSaveConfirm = async (save: boolean, rememberChoice: boolean) => {
    if (rememberChoice) {
      localStorage.setItem('workflow_auto_save', save.toString());
      setAutoSave(save);
    }

    if (save && pendingSaveData) {
      try {
        await apiClient.updateConversation(sessionId, undefined, {
          updates: pendingSaveData,
        });
      } catch (err) {
        console.error('Failed to save workflow state:', err);
      }
    }

    setShowSaveDialog(false);
    setPendingSaveData(null);
  };

  // Handle ZIP download of workspace
  const handleDownloadZip = async () => {
    if (!workspace || isDownloadingZip) return;

    setIsDownloadingZip(true);
    try {
      await apiClient.downloadWorkspaceZip(workspace);
    } catch (error) {
      console.error('Failed to download workspace:', error);
    } finally {
      setIsDownloadingZip(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isRunning) return;

    const userMessage = input.trim();
    setInput('');

    // Save current updates to history before starting new request
    if (updates.length > 0) {
      const currentArtifacts = extractArtifacts(updates);
      // Find the last assistant message from updates
      const orchestratorUpdate = updates.find(u => u.agent === 'Orchestrator' && u.type === 'completed');
      const assistantContent = orchestratorUpdate?.message || 'Workflow completed';

      setConversationHistory(prev => [
        ...prev,
        { role: 'assistant', content: assistantContent, updates: [...updates], artifacts: currentArtifacts, timestamp: Date.now() }
      ]);
    }

    // Add user message to history
    setConversationHistory(prev => [
      ...prev,
      { role: 'user', content: userMessage, timestamp: Date.now() }
    ]);

    // Clear current updates for new request
    setUpdates([]);
    setCurrentWorkflowInfo(null);
    setIsRunning(true);

    // Create/update conversation for workflow
    try {
      await apiClient.createConversation(sessionId, userMessage.slice(0, 50), 'workflow');
    } catch (err) {
      console.log('Conversation may already exist:', err);
    }

    // Save user message
    try {
      await apiClient.addMessage(sessionId, 'user', userMessage);
    } catch (err) {
      console.error('Failed to save user message:', err);
    }

    const allUpdates: WorkflowUpdate[] = [];

    // Clear debug logs for new execution
    setDebugLogs([]);

    // Reset progress tracking
    resetProgress();

    try {
      // Use unified Claude-style API if selected
      if (executionMode === 'unified') {
        await executeUnifiedWorkflow(userMessage, allUpdates);
        return;
      }

      // Use LangGraph workflow endpoint for other modes
      const response = await fetch('/api/langgraph/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_request: userMessage,
          // NOTE: workspace_root removed - backend auto-generates workspace
          // Path format: $DEFAULT_WORKSPACE/{session_id}/{project_name}
          session_id: sessionId,  // Pass session_id for workspace generation
          task_type: 'general',
          execution_mode: executionMode,  // "auto", "quick", or "full"
          use_dynamic: true,  // Use dynamic workflow (Supervisor-led agent spawning)
          system_prompt: systemPrompt,  // Custom system prompt
          enable_debug: true,  // Enable debug logging
          // Pass conversation history for context continuity
          conversation_history: conversationHistory.map(turn => ({
            role: turn.role,
            content: turn.content,
            timestamp: turn.timestamp,
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(line => line.trim());

        for (const line of lines) {
          try {
            // Parse SSE format: "data: {json}"
            const jsonData = line.startsWith('data:') ? line.substring(5).trim() : line;
            const event = JSON.parse(jsonData);

            // Extract debug logs if present
            if (event.updates?.debug_logs) {
              setDebugLogs(prev => [...prev, ...event.updates.debug_logs]);
            }

            // Update agent progress tracking
            updateAgentProgress(event);

            // Handle HITL (Human-in-the-Loop) requests
            if (event.status === 'awaiting_approval' && event.updates?.hitl_request) {
              const hitlReq = event.updates.hitl_request;
              setHitlRequest({
                request_id: hitlReq.request_id,
                workflow_id: hitlReq.workflow_id,
                stage_id: hitlReq.stage_id,
                checkpoint_type: hitlReq.checkpoint_type as HITLCheckpointType,
                title: hitlReq.title,
                description: hitlReq.description,
                content: hitlReq.content,
                priority: hitlReq.priority,
                allow_skip: hitlReq.allow_skip,
                created_at: hitlReq.created_at || new Date().toISOString(),
                status: hitlReq.status || 'pending',
              });
              setIsHitlModalOpen(true);
              continue; // Don't add to updates list yet
            }

            // Handle thinking stream (DeepSeek-R1)
            if (event.status === 'thinking' && event.updates?.current_thinking) {
              setIsThinking(true);
              setThinkingStream(event.updates.thinking_stream || []);
            }

            // Clear thinking when moving past thinking status or completing
            if (event.status === 'running' || event.status === 'completed' || event.status === 'finished') {
              setIsThinking(false);
              setThinkingStream([]);
            }

            // Convert unified format to WorkflowUpdate format
            const update: WorkflowUpdate = {
              agent: event.agent_title || event.node || 'Workflow',
              type: event.status === 'completed' ? 'completed' :
                    event.status === 'error' ? 'error' : 'update',
              status: event.status,
              message: event.updates?.message || event.updates?.streaming_content?.split('\n')[0] || event.node,
              streaming_content: event.updates?.streaming_content,
              execution_time: event.updates?.execution_time,
              ...event.updates,
            };

            // Handle project info message
            if (update.type === 'project_info' || event.status === 'project_info') {
              const projName = update.project_name || event.updates?.project_name;
              const projDir = update.full_path || event.updates?.project_dir;
              if (projName) {
                setProjectName(projName);
                setCurrentProjectName(projName);
              }
              if (projDir) {
                setCurrentProjectDir(projDir);
              }
              console.log(`Working on project: ${projName} at ${projDir}`);
              continue; // Don't add to updates list
            }

            // Track all updates for saving
            const existingIndex = allUpdates.findIndex(u => u.agent === update.agent);
            if (existingIndex >= 0) {
              allUpdates[existingIndex] = update;
            } else {
              allUpdates.push(update);
            }

            setUpdates(prev => {
              const existingIndex = prev.findIndex(u => u.agent === update.agent);
              if (existingIndex >= 0) {
                // Replace existing update for this agent
                const newUpdates = [...prev];
                newUpdates[existingIndex] = update;
                return newUpdates;
              } else {
                // Add new agent step
                return [...prev, update];
              }
            });

            // Update workflow_info when present (for progress tracking)
            if (update.workflow_info) {
              setCurrentWorkflowInfo(update.workflow_info);
            }

            // Capture execution mode
            if (update.execution_mode) {
              setExecutionMode(update.execution_mode as 'sequential' | 'parallel');
            }

            // Capture shared context from parallel execution
            if (update.type === 'shared_context' && update.shared_context) {
              setSharedContext(update.shared_context as SharedContextData);
            }

            // Check for workflow completion - set isRunning to false immediately
            // Use event.node (lowercase 'workflow') instead of update.agent (has emoji)
            const isWorkflowComplete = (
              (event.status === 'completed' && event.node === 'workflow') ||
              (event.status === 'finished') ||
              (update.status === 'finished')
            );

            if (isWorkflowComplete) {
              console.log('[Workflow] Completion detected - forcing all agents to completed state');
              // Workflow is complete, stop showing running state
              setIsRunning(false);
              // Clear thinking indicator
              setIsThinking(false);
              setThinkingStream([]);

              // Force all running/pending agents to completed state
              setAgentProgress(prev => prev.map(agent => ({
                ...agent,
                status: agent.status === 'error' ? 'error' : 'completed',
              })));
              setTotalProgress(100);
            }

            // Save artifacts when they're created
            if (update.type === 'artifact' && update.artifact) {
              try {
                await apiClient.addArtifact(
                  sessionId,
                  update.artifact.filename,
                  update.artifact.language,
                  update.artifact.content
                );
              } catch (err) {
                console.error('Failed to save artifact:', err);
              }
            }
          } catch (e) {
            console.error('Error parsing update:', e);
          }
        }
      }

      // Save final workflow state
      await saveWorkflowState(allUpdates);
    } catch (error) {
      console.error('Error executing workflow:', error);
      setUpdates(prev => [
        ...prev,
        {
          agent: 'Workflow',
          type: 'error',
          status: 'error',
          message: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        },
      ]);
    } finally {
      setIsRunning(false);
      // Clear thinking indicator when workflow ends
      setIsThinking(false);
      setThinkingStream([]);
      // Ensure all agents show completed state when workflow ends
      setAgentProgress(prev => prev.map(agent => ({
        ...agent,
        status: agent.status === 'error' ? 'error' : 'completed',
      })));
      setTotalProgress(100);
    }
  };

  // Handle HITL response
  const handleHitlResponse = async (action: string, feedback?: string, modifiedContent?: string) => {
    if (!hitlRequest) {
      console.error('No HITL request to respond to');
      return;
    }

    console.log(`[HITL] Submitting response: action=${action}, request_id=${hitlRequest.request_id}`);

    try {
      const result = await apiClient.submitHITLResponse(hitlRequest.request_id, {
        action: action as any,
        feedback,
        modified_content: modifiedContent,
      });

      console.log('[HITL] Response submitted successfully:', result);

      // Close modal and clear request
      setIsHitlModalOpen(false);
      setHitlRequest(null);

      // Add update to show response was submitted
      setUpdates(prev => [
        ...prev,
        {
          agent: 'Human Approval',
          type: action === 'approve' || action === 'confirm' ? 'completed' : 'error',
          status: action === 'approve' || action === 'confirm' ? 'completed' : 'error',
          message: action === 'approve' || action === 'confirm'
            ? 'Changes approved by user'
            : `Changes ${action} by user${feedback ? `: ${feedback}` : ''}`,
        },
      ]);
    } catch (error: any) {
      console.error('[HITL] Failed to submit response:', error);
      // Show error in UI
      setUpdates(prev => [
        ...prev,
        {
          agent: 'Human Approval',
          type: 'error',
          status: 'error',
          message: `Failed to submit response: ${error?.response?.data?.detail || error?.message || 'Unknown error'}`,
        },
      ]);
    }
  };

  // Handle HITL modal close/skip
  const handleHitlClose = () => {
    if (hitlRequest?.allow_skip) {
      setIsHitlModalOpen(false);
      setHitlRequest(null);
    }
  };

  // Handle workspace configuration save
  const handleWorkspaceSave = () => {
    if (workspaceStep === 'project') {
      // Move to path step
      if (projectName.trim()) {
        setWorkspaceStep('path');
      }
    } else {
      // Save workspace with project directory
      const trimmedPath = workspaceInput.trim();
      const trimmedProject = projectName.trim();
      if (trimmedPath && trimmedProject) {
        // Create full path: workspace/projectName
        const fullPath = `${trimmedPath}/${trimmedProject}`;
        setWorkspace(fullPath);
        localStorage.setItem('workflow_workspace', fullPath);
        setShowWorkspaceDialog(false);
        setWorkspaceStep('project'); // Reset for next time
        setProjectName('');
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-100">
      {/* Dashboard Header - Shows when workflow is active */}
      {(isRunning || totalProgress > 0 || savedFiles.length > 0) && (
        <DashboardHeader
          projectName={currentProjectName || projectName}
          projectDir={currentProjectDir}
          workspace={workspace}
          isRunning={isRunning}
          totalProgress={totalProgress}
          elapsedTime={elapsedTime}
          estimatedTimeRemaining={estimatedTimeRemaining}
          agents={agentProgress}
          onWorkspaceClick={() => setShowWorkspaceDialog(true)}
        />
      )}

      {/* Main Content Area - Responsive flex layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* LEFT PANEL - Conversation Area (fluid width) */}
        <div className="flex flex-col flex-1 min-w-0 bg-gray-950">
      {/* Workspace Configuration Dialog - Dark Theme */}
      {showWorkspaceDialog && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg shadow-2xl max-w-lg w-full p-5 border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-medium text-gray-100">
                  {workspaceStep === 'project' ? '새 프로젝트' : '작업 경로'}
                </h2>
                <p className="text-[10px] sm:text-xs text-gray-500">
                  {workspaceStep === 'project' ? '1/2 단계' : '2/2 단계'}
                </p>
              </div>
            </div>

            {workspaceStep === 'project' ? (
              <div className="mb-4 sm:mb-5">
                <label className="block text-[10px] sm:text-xs font-medium text-gray-400 mb-1.5 sm:mb-2">
                  프로젝트 이름
                </label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="my-awesome-project"
                  className="w-full px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 text-gray-100 placeholder-gray-600 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 border border-gray-700 font-mono text-xs sm:text-sm"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && projectName.trim()) {
                      handleWorkspaceSave();
                    }
                  }}
                  autoFocus
                />
                <p className="mt-1.5 sm:mt-2 text-[10px] sm:text-xs text-gray-600">
                  이 이름으로 디렉토리가 생성됩니다.
                </p>
              </div>
            ) : (
              <div className="mb-4 sm:mb-5">
                <label className="block text-[10px] sm:text-xs font-medium text-gray-400 mb-1.5 sm:mb-2">
                  기본 작업 경로
                </label>
                <input
                  type="text"
                  value={workspaceInput}
                  onChange={(e) => setWorkspaceInput(e.target.value)}
                  placeholder={getDefaultWorkspacePlaceholder()}
                  className="w-full px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 text-gray-100 placeholder-gray-600 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 border border-gray-700 font-mono text-xs sm:text-sm"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleWorkspaceSave();
                    }
                  }}
                  autoFocus
                />
                <div className="mt-1.5 sm:mt-2 p-1.5 sm:p-2 bg-gray-800 border border-gray-700 rounded">
                  <p className="text-[10px] sm:text-xs text-gray-400">
                    <span className="text-gray-500">전체 경로:</span>{' '}
                    <code className="font-mono text-green-400 break-all">{workspaceInput}/{projectName}</code>
                  </p>
                </div>
              </div>
            )}

            <div className="flex items-center gap-2">
              {workspaceStep === 'path' && (
                <button
                  onClick={() => setWorkspaceStep('project')}
                  className="px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg border border-gray-700 hover:bg-gray-800 text-gray-400 text-xs sm:text-sm transition-colors"
                >
                  이전
                </button>
              )}
              <button
                onClick={handleWorkspaceSave}
                disabled={workspaceStep === 'project' ? !projectName.trim() : !workspaceInput.trim()}
                className="flex-1 px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-white text-xs sm:text-sm font-medium transition-colors"
              >
                {workspaceStep === 'project' ? '다음' : '계속'}
              </button>
              {workspaceStep === 'project' && (
                <button
                  onClick={() => {
                    const defaultPath = `${getDefaultWorkspacePlaceholder()}/new-project`;
                    setWorkspace(defaultPath);
                    localStorage.setItem('workflow_workspace', defaultPath);
                    setShowWorkspaceDialog(false);
                  }}
                  className="px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 text-xs sm:text-sm transition-colors"
                >
                  건너뛰기
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 대화 저장 확인 다이얼로그 */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-3 sm:p-4">
          <div className="bg-gray-900 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-5 border border-gray-700">
            <div className="flex items-center gap-2 sm:gap-3 mb-3 sm:mb-4">
              <div className="w-8 sm:w-10 h-8 sm:h-10 rounded-lg bg-blue-600 flex items-center justify-center">
                <svg className="w-4 sm:w-5 h-4 sm:h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-medium text-gray-100">대화 저장</h2>
                <p className="text-[10px] sm:text-xs text-gray-500">나중을 위해 이 대화를 저장합니다</p>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-gray-400 mb-3 sm:mb-4">
              이 대화를 히스토리에 저장할까요?
            </p>

            <div className="space-y-1.5 sm:space-y-2">
              <button
                onClick={() => handleSaveConfirm(true, false)}
                className="w-full px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs sm:text-sm font-medium transition-colors"
              >
                이번만 저장
              </button>
              <button
                onClick={() => handleSaveConfirm(true, true)}
                className="w-full px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs sm:text-sm transition-colors"
              >
                항상 자동 저장
              </button>
              <button
                onClick={() => handleSaveConfirm(false, false)}
                className="w-full px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg border border-gray-700 hover:bg-gray-800 text-gray-500 text-xs sm:text-sm transition-colors"
              >
                저장 안 함
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DeepSeek-R1 사고 표시기 */}
      {isThinking && thinkingStream.length > 0 && (
        <div className="bg-purple-900/30 border-b border-purple-800 px-2 sm:px-3 py-1 sm:py-1.5">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <div className="w-4 sm:w-5 h-4 sm:h-5 rounded-full bg-purple-600 flex items-center justify-center flex-shrink-0 animate-pulse">
              <svg className="w-2.5 sm:w-3 h-2.5 sm:h-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <span className="text-[10px] sm:text-xs font-medium text-purple-300">분석 중...</span>
            <span className="text-[10px] sm:text-xs text-purple-500">{thinkingStream.length}개 블록</span>
          </div>
        </div>
      )}

      {/* 워크플로우 출력 영역 - 터미널 스타일 */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-gray-900"
      >
        <div className="p-2 sm:p-3">
          {/* 빈 상태 - 터미널 스타일 */}
          {conversationHistory.length === 0 && updates.length === 0 && !isRunning && (
            <div className="flex flex-col items-center justify-center h-[50vh] sm:h-[60vh] text-center">
              <div className="font-mono text-gray-600 mb-3 sm:mb-4 text-[10px] sm:text-xs">
                <div className="hidden sm:block">╭─────────────────────────────────╮</div>
                <div className="hidden sm:block">│                                 │</div>
                <div className="sm:hidden text-blue-400">AI 코드 에이전트 v1.0</div>
                <div className="hidden sm:block">│    <span className="text-blue-400">AI 코드 에이전트</span> v1.0        │</div>
                <div className="hidden sm:block">│                                 │</div>
                <div className="sm:hidden text-gray-500 mt-2">작업을 입력하여 시작하세요</div>
                <div className="hidden sm:block">│    <span className="text-gray-500">작업을 입력하여 시작하세요</span>    │</div>
                <div className="hidden sm:block">│                                 │</div>
                <div className="hidden sm:block">╰─────────────────────────────────╯</div>
              </div>
              <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs text-gray-600 font-mono flex-wrap justify-center">
                <span className="text-blue-400">설계</span>
                <span>→</span>
                <span className="text-green-400">코딩</span>
                <span>→</span>
                <span className="text-purple-400">검토</span>
                <span>→</span>
                <span className="text-yellow-400">저장</span>
              </div>
              <button
                onClick={() => setShowWorkspaceDialog(true)}
                className="mt-3 sm:mt-4 text-[10px] sm:text-xs text-gray-600 hover:text-gray-400 font-mono px-2 py-1 rounded border border-gray-800 hover:border-gray-700 max-w-full truncate"
              >
                $ cd {workspace}
              </button>
            </div>
          )}

          {/* 대화 히스토리 - 터미널 스타일 (토글 가능) */}
          {conversationHistory.length > 0 && (
            <div className="mb-2 sm:mb-3 border border-gray-800 rounded-lg overflow-hidden">
              {/* 대화 기록 헤더 + 토글 버튼 */}
              <button
                onClick={() => setIsConversationCollapsed(!isConversationCollapsed)}
                className="w-full flex items-center justify-between px-2 sm:px-3 py-1.5 bg-gray-800/50 hover:bg-gray-800 transition-colors"
              >
                <span className="text-[10px] sm:text-xs text-gray-400 font-mono">
                  💬 대화 기록 ({conversationHistory.length}개)
                </span>
                <span className="text-gray-500 text-xs">
                  {isConversationCollapsed ? '▶ 펼치기' : '▼ 접기'}
                </span>
              </button>

              {/* 대화 내용 (접히지 않은 경우에만 표시) */}
              {!isConversationCollapsed && (
                <div className="space-y-1.5 sm:space-y-2 p-2 sm:p-3">
                  {conversationHistory.map((turn, turnIndex) => (
                <div key={`turn-${turnIndex}-${turn.timestamp}`} className="font-mono text-[10px] sm:text-xs">
                  {turn.role === 'user' ? (
                    <div className="text-blue-400">
                      <span className="text-gray-600 mr-2">$</span>
                      <div className="inline-block text-left prose prose-sm prose-invert max-w-none
                        prose-headings:text-blue-300 prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-2
                        prose-p:text-blue-400 prose-p:my-1
                        prose-li:text-blue-400 prose-li:my-0.5
                        prose-ul:my-1 prose-ol:my-1
                        prose-code:text-cyan-400 prose-code:bg-gray-800 prose-code:px-1 prose-code:rounded
                        prose-strong:text-blue-300 prose-em:text-blue-300">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkBreaks]}
                          components={{
                            code(props) {
                              const { children, className, ...rest } = props;
                              const match = /language-(\w+)/.exec(className || '');
                              return match ? (
                                <SyntaxHighlighter
                                  style={oneDark}
                                  language={match[1]}
                                  PreTag="div"
                                  customStyle={{
                                    borderRadius: '8px',
                                    padding: '12px',
                                    margin: '8px 0',
                                    fontSize: '11px',
                                  }}
                                >
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              ) : (
                                <code className={`${className || ''} bg-gray-800 px-1 py-0.5 rounded text-cyan-400 text-[10px]`} {...rest}>
                                  {children}
                                </code>
                              );
                            },
                          }}
                        >
                          {turn.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  ) : (
                    <div className="border-l-2 border-gray-800 pl-2 text-gray-400 group relative">
                      <div className="flex items-center justify-between">
                        <div className="text-green-400 text-[9px] sm:text-[10px]">✓ 완료</div>
                        {/* Copy button for assistant response */}
                        <button
                          onClick={async () => {
                            const success = await copyToClipboard(turn.content);
                            const btn = document.getElementById(`copy-btn-${turnIndex}`);
                            if (btn && success) {
                              btn.textContent = '✓';
                              setTimeout(() => { btn.textContent = '복사'; }, 1500);
                            }
                          }}
                          id={`copy-btn-${turnIndex}`}
                          className="opacity-0 group-hover:opacity-100 px-1.5 py-0.5 text-[9px] sm:text-[10px] bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-gray-200 rounded transition-all"
                          title="응답 복사"
                        >
                          복사
                        </button>
                      </div>
                      {/* 확장/축소 가능한 응답 콘텐츠 */}
                      <ExpandableContent content={turn.content} maxLines={5}>
                        <div className="prose prose-sm prose-invert max-w-none
                          prose-headings:text-gray-300 prose-headings:font-semibold prose-headings:mt-2 prose-headings:mb-1
                          prose-p:text-gray-400 prose-p:my-1
                          prose-li:text-gray-400 prose-li:my-0.5
                          prose-code:text-green-400 prose-code:bg-gray-800 prose-code:px-1 prose-code:rounded">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm, remarkBreaks]}
                            components={{
                              code(props) {
                                const { children, className, ...rest } = props;
                                const match = /language-(\w+)/.exec(className || '');
                                return match ? (
                                  <SyntaxHighlighter
                                    style={oneDark}
                                    language={match[1]}
                                    PreTag="div"
                                    customStyle={{
                                      borderRadius: '8px',
                                      padding: '12px',
                                      margin: '8px 0',
                                      fontSize: '11px',
                                    }}
                                  >
                                    {String(children).replace(/\n$/, '')}
                                  </SyntaxHighlighter>
                                ) : (
                                  <code className={`${className || ''} bg-gray-800 px-1 py-0.5 rounded text-green-400 text-[10px]`} {...rest}>
                                    {children}
                                  </code>
                                );
                              },
                            }}
                          >
                            {turn.content}
                          </ReactMarkdown>
                        </div>
                      </ExpandableContent>
                      {/* 생성/수정된 파일 - FileTreeViewer 항상 표시 (중요 콘텐츠) */}
                      {turn.artifacts && turn.artifacts.length > 0 && (
                        <div className="mt-2">
                          <FileTreeViewer
                            files={turn.artifacts}
                            onDownloadZip={handleDownloadZip}
                            isDownloading={isDownloadingZip}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
                </div>
              )}
            </div>
          )}

          {/* Workflow Graph Visualization */}
          {currentWorkflowInfo && isRunning && (
            <WorkflowGraph workflowInfo={currentWorkflowInfo} isRunning={isRunning} />
          )}

          {/* Terminal Output - Main Display */}
          {(isRunning || updates.length > 0) && (
            <TerminalOutput
              updates={updates}
              isRunning={isRunning}
              liveOutputs={liveOutputs}
              savedFiles={savedFiles}
              onDownloadZip={handleDownloadZip}
              isDownloadingZip={isDownloadingZip}
            />
          )}

          {/* 공유 컨텍스트 버튼 */}
          {sharedContext && sharedContext.entries.length > 0 && (
            <div className="mt-1.5 sm:mt-2">
              <button
                onClick={() => setShowSharedContext(true)}
                className="flex items-center gap-1.5 sm:gap-2 px-1.5 sm:px-2 py-0.5 sm:py-1 text-[10px] sm:text-xs font-mono text-purple-400 hover:text-purple-300 border border-gray-800 rounded hover:border-gray-700 transition-colors"
              >
                [컨텍스트: {sharedContext.entries.length}개 항목]
              </button>
            </div>
          )}

          {/* Next Actions Panel - Show after workflow completes */}
          {!isRunning && (nextActions.length > 0 || planFilePath) && (
            <NextActionsPanel
              actions={nextActions}
              onActionClick={(action) => {
                setInput(action);
                inputRef.current?.focus();
              }}
              isLoading={isRunning}
              planFile={planFilePath || undefined}
              onViewPlan={() => setIsPlanViewerOpen(true)}
            />
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 입력 영역 */}
      <div className="border-t border-gray-800 bg-gray-900">
        <div className="px-2 sm:px-3 py-1.5 sm:py-2">
          {/* 모드 선택 탭 */}
          <div className="flex items-center justify-between gap-1 mb-2">
            <div className="flex items-center gap-1">
              <span className="text-[9px] sm:text-[10px] text-gray-500 mr-1">모드:</span>
              <button
                type="button"
                onClick={() => {
                  setExecutionModeState('auto');
                  localStorage.setItem('workflow_execution_mode', 'auto');
                }}
                className={`px-2 py-0.5 text-[9px] sm:text-[10px] rounded transition-colors ${
                  executionMode === 'auto'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
                title="요청 내용에 따라 자동으로 모드 결정"
              >
                자동
              </button>
              <button
                type="button"
                onClick={() => {
                  setExecutionModeState('quick');
                  localStorage.setItem('workflow_execution_mode', 'quick');
                }}
                className={`px-2 py-0.5 text-[9px] sm:text-[10px] rounded transition-colors ${
                  executionMode === 'quick'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
                title="빠른 Q&A - 코드 생성 없이 질문에 답변"
              >
                Q&A
              </button>
              <button
                type="button"
                onClick={() => {
                  setExecutionModeState('full');
                  localStorage.setItem('workflow_execution_mode', 'full');
                }}
                className={`px-2 py-0.5 text-[9px] sm:text-[10px] rounded transition-colors ${
                  executionMode === 'full'
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
                title="코드 생성 - 전체 파이프라인으로 코드 생성"
              >
                코드 생성
              </button>
              <button
                type="button"
                onClick={() => {
                  setExecutionModeState('unified');
                  localStorage.setItem('workflow_execution_mode', 'unified');
                }}
                className={`px-2 py-0.5 text-[9px] sm:text-[10px] rounded transition-colors ${
                  executionMode === 'unified'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
                title="통합 API - Claude Code 방식 (Supervisor 라우팅)"
              >
                Unified
              </button>
              <span className="text-[8px] sm:text-[9px] text-gray-600 ml-2 hidden sm:inline">
                {executionMode === 'auto' && '(요청에 따라 자동 결정)'}
                {executionMode === 'quick' && '(빠른 응답, 코드 생성 안함)'}
                {executionMode === 'full' && '(전체 에이전트 파이프라인)'}
                {executionMode === 'unified' && '(Claude Code 방식 통합 API)'}
              </span>
            </div>
            {/* 컨텍스트 클리어 및 설정 버튼 */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  setTempSystemPrompt(systemPrompt);
                  setShowSystemPromptModal(true);
                }}
                className={`px-2 py-0.5 text-[9px] sm:text-[10px] rounded transition-colors ${
                  systemPrompt
                    ? 'bg-cyan-900/50 text-cyan-400 hover:bg-cyan-800/50'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
                title="시스템 프롬프트 설정"
              >
                {systemPrompt ? '프롬프트 ✓' : '프롬프트'}
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (confirm('대화 기록과 워크플로우 상태를 초기화하시겠습니까?')) {
                    try {
                      await apiClient.clearSessionContext(sessionId);
                      setConversationHistory([]);
                      setUpdates([]);
                      setSavedFiles([]);
                      resetProgress();
                    } catch (e) {
                      console.error('Failed to clear context:', e);
                    }
                  }
                }}
                className="px-2 py-0.5 text-[9px] sm:text-[10px] rounded bg-gray-800 text-gray-400 hover:bg-red-900/50 hover:text-red-400 transition-colors"
                title="대화 기록 및 워크플로우 상태 초기화"
              >
                새 대화
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (confirm('LLM 응답 캐시를 모두 삭제하시겠습니까?')) {
                    try {
                      const result = await apiClient.clearLMCache();
                      alert(`캐시 ${result.cleared_count}개 삭제됨`);
                    } catch (e) {
                      console.error('Failed to clear cache:', e);
                    }
                  }
                }}
                className="px-2 py-0.5 text-[9px] sm:text-[10px] rounded bg-gray-800 text-gray-400 hover:bg-orange-900/50 hover:text-orange-400 transition-colors hidden sm:block"
                title="LLM 응답 캐시 삭제"
              >
                캐시 삭제
              </button>
            </div>
          </div>
          <form onSubmit={handleSubmit}>
            <div className="flex items-center gap-1.5 sm:gap-2">
              {/* 작업공간 선택기 */}
              <WorkspaceProjectSelector
                currentWorkspace={workspace}
                currentProject={workspace}
                sessionId={sessionId}
                onWorkspaceChange={(newWorkspace) => {
                  setWorkspace(newWorkspace);
                  if (onWorkspaceChange) {
                    onWorkspaceChange(newWorkspace);
                  }
                }}
                onProjectSelect={(projectPath) => {
                  setWorkspace(projectPath);
                  if (onWorkspaceChange) {
                    onWorkspaceChange(projectPath);
                  }
                }}
              />

              {/* 입력 필드 - 멀티라인 textarea */}
              <div className="relative flex-1 min-w-0">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter로 전송, Shift+Enter로 줄바꿈
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      if (input.trim() && !isRunning) {
                        handleSubmit(e as unknown as React.FormEvent);
                      }
                    }
                  }}
                  placeholder="작업 또는 질문을 입력하세요... (Shift+Enter로 줄바꿈)"
                  disabled={isRunning}
                  rows={3}
                  className="w-full px-2 sm:px-3 py-1.5 sm:py-2 pr-16 sm:pr-20 bg-gray-800 text-gray-100 placeholder-gray-500 rounded-lg text-xs sm:text-sm font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 border border-gray-700 disabled:opacity-50 resize-none overflow-y-auto scrollbar-thin scrollbar-thumb-gray-600 scrollbar-track-gray-800"
                  style={{ minHeight: '72px', maxHeight: '120px' }}
                />
                <button
                  type="submit"
                  disabled={isRunning || !input.trim()}
                  className="absolute right-1.5 sm:right-2 bottom-1.5 sm:bottom-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-[10px] sm:text-xs font-medium transition-colors flex items-center gap-1 sm:gap-1.5"
                >
                  {isRunning ? (
                    <>
                      <div className="w-2.5 sm:w-3 h-2.5 sm:h-3 border border-white border-t-transparent rounded-full animate-spin" />
                      <span className="hidden sm:inline">실행 중</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-2.5 sm:w-3 h-2.5 sm:h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                      <span className="hidden sm:inline">실행</span>
                    </>
                  )}
                </button>
              </div>

              {/* 패널 토글 - 모바일에서는 아이콘만 */}
              <button
                onClick={() => setShowStatusPanel(!showStatusPanel)}
                className="p-1.5 sm:p-2 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors flex-shrink-0"
                title={showStatusPanel ? '패널 숨기기' : '패널 보기'}
              >
                <svg className="w-3.5 sm:w-4 h-3.5 sm:h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                </svg>
              </button>
            </div>
          </form>
        </div>
      </div>
      </div>{/* End of LEFT PANEL */}

      {/* RIGHT PANEL - Workflow Status (responsive width) */}
      {showStatusPanel && (isRunning || savedFiles.length > 0 || totalProgress > 0) && (
        <div className="hidden md:block w-80 lg:w-96 border-l border-gray-800 flex-shrink-0 overflow-hidden">
          <WorkflowStatusPanel
            isRunning={isRunning}
            agents={agentProgress}
            currentAgent={agentProgress.find(a => a.status === 'running')?.name}
            totalProgress={totalProgress}
            elapsedTime={elapsedTime}
            estimatedTimeRemaining={estimatedTimeRemaining}
            streamingContent={currentStreamingContent}
            streamingFile={currentStreamingFile || undefined}
            savedFiles={savedFiles}
            workspaceRoot={workspace}
            projectName={currentProjectName}
            projectDir={currentProjectDir}
            sessionId={sessionId}
          />
        </div>
      )}
      </div>{/* End of Main Content Area */}

      {/* Modals - Positioned outside panels */}
      <SharedContextViewer
        data={sharedContext}
        isVisible={showSharedContext}
        onClose={() => setShowSharedContext(false)}
      />

      {/* System Prompt Modal */}
      {showSystemPromptModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 rounded-lg shadow-2xl max-w-2xl w-full p-5 border border-gray-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-cyan-600 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-lg font-medium text-gray-100">시스템 프롬프트</h2>
                <p className="text-xs text-gray-500">AI 에이전트의 동작 방식을 커스터마이징합니다</p>
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-medium text-gray-400 mb-2">
                커스텀 시스템 프롬프트 (선택)
              </label>
              <textarea
                value={tempSystemPrompt}
                onChange={(e) => setTempSystemPrompt(e.target.value)}
                placeholder="예: 모든 코드는 TypeScript로 작성하고, 함수형 프로그래밍 스타일을 사용해주세요. 주석은 한글로 작성해주세요."
                className="w-full px-3 py-2 bg-gray-800 text-gray-100 placeholder-gray-600 rounded-lg focus:outline-none focus:ring-1 focus:ring-cyan-500 border border-gray-700 text-sm font-mono resize-none"
                rows={6}
              />
              <p className="mt-2 text-xs text-gray-600">
                이 프롬프트는 모든 요청에 추가되어 AI의 응답 스타일을 조정합니다.
                비워두면 기본 동작을 사용합니다.
              </p>
            </div>

            <div className="mb-4 p-3 bg-gray-800 rounded-lg border border-gray-700">
              <p className="text-xs text-gray-400 mb-2">예시:</p>
              <ul className="text-xs text-gray-500 space-y-1">
                <li>• "모든 코드에 상세한 주석을 한글로 작성해주세요"</li>
                <li>• "React 컴포넌트는 함수형으로 작성하고 hooks를 사용해주세요"</li>
                <li>• "에러 처리를 철저히 하고 로깅을 추가해주세요"</li>
                <li>• "코드 설명은 초보자도 이해할 수 있게 해주세요"</li>
              </ul>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowSystemPromptModal(false)}
                className="px-3 py-2 rounded-lg border border-gray-700 hover:bg-gray-800 text-gray-400 text-sm transition-colors"
              >
                취소
              </button>
              <button
                onClick={() => {
                  setSystemPrompt(tempSystemPrompt);
                  localStorage.setItem('workflow_system_prompt', tempSystemPrompt);
                  setShowSystemPromptModal(false);
                }}
                className="flex-1 px-3 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium transition-colors"
              >
                저장
              </button>
              {systemPrompt && (
                <button
                  onClick={() => {
                    setTempSystemPrompt('');
                    setSystemPrompt('');
                    localStorage.removeItem('workflow_system_prompt');
                    setShowSystemPromptModal(false);
                  }}
                  className="px-3 py-2 rounded-lg bg-red-900/50 hover:bg-red-800/50 text-red-400 text-sm transition-colors"
                >
                  초기화
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {hitlRequest && (
        <HITLModal
          request={hitlRequest}
          isOpen={isHitlModalOpen}
          onClose={handleHitlClose}
          onApprove={(feedback) => handleHitlResponse('approve', feedback)}
          onReject={(feedback) => handleHitlResponse('reject', feedback)}
          onEdit={(modifiedContent, feedback) => handleHitlResponse('edit', feedback, modifiedContent)}
          onRetry={(instructions) => handleHitlResponse('retry', instructions)}
          onSelect={(optionId, feedback) => handleHitlResponse('select', `Selected: ${optionId}. ${feedback || ''}`)}
          onConfirm={(feedback) => handleHitlResponse('confirm', feedback)}
        />
      )}

      {/* Plan File Viewer Modal */}
      {planFilePath && (
        <PlanFileViewer
          planFilePath={planFilePath}
          isOpen={isPlanViewerOpen}
          onClose={() => setIsPlanViewerOpen(false)}
          onStartCodeGeneration={(_planContent) => {
            // Set input to "Execute the plan" or similar and auto-submit
            setInput('위 계획대로 코드 생성을 시작해주세요.');
            // Close the modal first
            setIsPlanViewerOpen(false);
          }}
        />
      )}

      <DebugPanel
        logs={debugLogs}
        isOpen={isDebugOpen}
        onToggle={() => setIsDebugOpen(!isDebugOpen)}
      />
    </div>
  );
};

export default WorkflowInterface;
