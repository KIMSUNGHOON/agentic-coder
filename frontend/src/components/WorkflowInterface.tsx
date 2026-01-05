/**
 * WorkflowInterface component - Claude.ai inspired multi-agent workflow UI
 * Supports conversation context for iterative refinement
 * Now with split layout: Conversation (left) + Workflow Status (right)
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { WorkflowUpdate, Artifact, WorkflowInfo, HITLRequest, HITLCheckpointType } from '../types/api';
import WorkflowStep from './WorkflowStep';
import SharedContextViewer from './SharedContextViewer';
import WorkflowGraph from './WorkflowGraph';
import WorkspaceProjectSelector from './WorkspaceProjectSelector';
import DebugPanel from './DebugPanel';
import HITLModal from './HITLModal';
import WorkflowStatusPanel from './WorkflowStatusPanel';
import apiClient from '../api/client';

// Agent status for progress tracking
interface AgentProgressStatus {
  name: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  executionTime?: number;
  streamingContent?: string;
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
  const [executionMode, setExecutionMode] = useState<'sequential' | 'parallel' | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Workspace configuration
  const [workspace, setWorkspace] = useState<string>(() => {
    return workspaceProp || localStorage.getItem('workflow_workspace') || '/home/user/workspace';
  });
  const [showWorkspaceDialog, setShowWorkspaceDialog] = useState<boolean>(() => {
    return !localStorage.getItem('workflow_workspace'); // Show on first use
  });
  const [workspaceInput, setWorkspaceInput] = useState<string>(() => {
    return localStorage.getItem('workflow_workspace') || '/home/user/workspace';
  });
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

  // Enhanced progress tracking (including refiner for refinement loop)
  const [agentProgress, setAgentProgress] = useState<AgentProgressStatus[]>([
    { name: 'supervisor', title: '🧠 Supervisor', description: 'Task Analysis', status: 'pending' },
    { name: 'architect', title: '🏗️ Architect', description: 'Project Design', status: 'pending' },
    { name: 'coder', title: '💻 Coder', description: 'Implementation', status: 'pending' },
    { name: 'reviewer', title: '👀 Reviewer', description: 'Code Review', status: 'pending' },
    { name: 'qa_gate', title: '🧪 QA Tester', description: 'Testing', status: 'pending' },
    { name: 'security_gate', title: '🔒 Security', description: 'Security Audit', status: 'pending' },
    { name: 'refiner', title: '🔧 Refiner', description: 'Code Refinement', status: 'pending' },
    { name: 'aggregator', title: '📊 Aggregator', description: 'Results Aggregation', status: 'pending' },
    { name: 'hitl', title: '👤 Human Review', description: 'Awaiting Approval', status: 'pending' },
    { name: 'persistence', title: '💾 Persistence', description: 'Saving Files', status: 'pending' },
  ]);
  const [totalProgress, setTotalProgress] = useState(0);
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState<number | undefined>();
  const [elapsedTime, setElapsedTime] = useState(0);
  const [workflowStartTime, setWorkflowStartTime] = useState<number | null>(null);
  const [currentStreamingFile, setCurrentStreamingFile] = useState<string | null>(null);
  const [currentStreamingContent, setCurrentStreamingContent] = useState<string>('');
  const [savedFiles, setSavedFiles] = useState<Artifact[]>([]);

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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Format elapsed time
  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs.toFixed(0)}s`;
  };

  // Track elapsed time during workflow
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
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
    setAgentProgress([
      { name: 'supervisor', title: '🧠 Supervisor', description: 'Task Analysis', status: 'pending' },
      { name: 'architect', title: '🏗️ Architect', description: 'Project Design', status: 'pending' },
      { name: 'coder', title: '💻 Coder', description: 'Implementation', status: 'pending' },
      { name: 'reviewer', title: '👀 Reviewer', description: 'Code Review', status: 'pending' },
      { name: 'qa_gate', title: '🧪 QA Tester', description: 'Testing', status: 'pending' },
      { name: 'security_gate', title: '🔒 Security', description: 'Security Audit', status: 'pending' },
      { name: 'refiner', title: '🔧 Refiner', description: 'Code Refinement', status: 'pending' },
      { name: 'aggregator', title: '📊 Aggregator', description: 'Results Aggregation', status: 'pending' },
      { name: 'hitl', title: '👤 Human Review', description: 'Awaiting Approval', status: 'pending' },
      { name: 'persistence', title: '💾 Persistence', description: 'Saving Files', status: 'pending' },
    ]);
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
  };

  // Refinement loop state
  const [refinementIteration, setRefinementIteration] = useState(0);

  // Update agent progress from event
  const updateAgentProgress = (event: any) => {
    const nodeName = event.node;
    const status = event.status;
    const executionTime = event.updates?.execution_time;
    const agentTitle = event.agent_title;
    const agentDescription = event.agent_description;
    const streamingContent = event.updates?.streaming_content;
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
      const updated = prev.map(agent => {
        if (agent.name === nodeName) {
          let newStatus: AgentProgressStatus['status'] = agent.status;
          if (status === 'starting' || status === 'running' || status === 'thinking' || status === 'streaming' || status === 'awaiting_approval' || status === 'waiting') {
            newStatus = 'running';
          } else if (status === 'completed' || status === 'approved') {
            newStatus = 'completed';
          } else if (status === 'error' || status === 'rejected' || status === 'timeout') {
            newStatus = 'error';
          }

          // Build description with refinement iteration info
          let description = agentDescription || agent.description;
          if (currentRefinementIteration && currentRefinementIteration > 0) {
            // Add iteration info for quality gates and refiner
            if (['reviewer', 'qa_gate', 'security_gate'].includes(nodeName)) {
              description = `${description} (iter ${currentRefinementIteration + 1})`;
            } else if (nodeName === 'refiner') {
              description = `Iteration ${currentRefinementIteration}/${event.updates?.max_iterations || 3}`;
            }
          }

          return {
            ...agent,
            title: agentTitle || agent.title,
            description: description,
            status: newStatus,
            executionTime: executionTime !== undefined ? executionTime : agent.executionTime,
            streamingContent: streamingContent || agent.streamingContent,
          };
        }
        return agent;
      });

      // Calculate total progress
      const completedCount = updated.filter(a => a.status === 'completed').length;
      const runningCount = updated.filter(a => a.status === 'running').length;
      const progress = ((completedCount + runningCount * 0.5) / updated.length) * 100;
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
    if (event.updates?.streaming_content) {
      setCurrentStreamingContent(event.updates.streaming_content);

      // Update live outputs for conversation area display
      const agentInfo = agentProgress.find(a => a.name === nodeName);
      if (agentInfo) {
        setLiveOutputs(prev => {
          const newMap = new Map(prev);
          newMap.set(nodeName, {
            agentName: nodeName,
            agentTitle: event.agent_title || agentInfo.title,
            content: event.updates.streaming_content,
            status: status,
            timestamp: Date.now(),
          });
          return newMap;
        });
      }
    }

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

    // DEBUG: Log all events for artifact and status tracking
    console.log(`[Event] node=${nodeName} status=${status} hasArtifacts=${!!event.updates?.artifacts} hasSavedFiles=${!!event.updates?.saved_files}`);

    // DEBUG: Track agent status changes
    setAgentProgress(current => {
      const agent = current.find(a => a.name === nodeName);
      if (agent) {
        console.log(`[AgentStatus] ${nodeName}: ${agent.status} -> ${status}`);
      }
      return current;
    });

    // Capture saved files from persistence - MERGE instead of replace
    if (nodeName === 'persistence' && status === 'completed') {
      const files = event.updates?.saved_files || event.updates?.artifacts || event.updates?.final_artifacts || [];
      if (files.length > 0) {
        setSavedFiles(prev => mergeFiles(prev, files));
        console.log(`[Persistence] Saved ${files.length} files:`, files.map((f: any) => f.filename));
      } else {
        console.warn(`[Persistence] No files found in event`);
      }
      // Also update project info if present
      if (event.updates?.project_name) {
        setCurrentProjectName(event.updates.project_name);
      }
      if (event.updates?.project_dir) {
        setCurrentProjectDir(event.updates.project_dir);
      }
    }

    // Also try to capture artifacts from ANY node that has them
    if (event.updates?.artifacts && Array.isArray(event.updates.artifacts) && event.updates.artifacts.length > 0) {
      console.log(`[${nodeName}] Found ${event.updates.artifacts.length} artifacts`);
      setSavedFiles(prev => mergeFiles(prev, event.updates.artifacts));
    }

    // Also capture final artifacts from workflow completion - MERGE
    if (nodeName === 'workflow' && status === 'completed') {
      const files = event.updates?.final_artifacts || event.updates?.artifacts || [];
      if (files.length > 0) {
        setSavedFiles(prev => mergeFiles(prev, files));
      }
    }

    // Capture artifacts from coder output - MERGE instead of replace
    // Backend sends artifacts in multiple places: coder_output.artifacts AND updates.artifacts
    if (nodeName === 'coder' && status === 'completed') {
      // Try direct artifacts first (backend sends both)
      let artifacts = event.updates?.artifacts || [];

      // Fallback to nested coder_output.artifacts
      if (artifacts.length === 0) {
        const coderOutput = event.updates?.coder_output;
        artifacts = coderOutput?.artifacts || [];
      }

      if (artifacts.length > 0) {
        console.log(`[Coder] Generated ${artifacts.length} artifacts:`, artifacts.map((a: any) => a.filename));
        setSavedFiles(prev => mergeFiles(prev, artifacts));
      } else {
        console.warn(`[Coder] No artifacts found in event:`, JSON.stringify(event.updates, null, 2).slice(0, 500));
      }
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [updates, conversationHistory]);

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

  // Extract artifacts from updates
  const extractArtifacts = useCallback((workflowUpdates: WorkflowUpdate[]): Artifact[] => {
    const artifacts: Artifact[] = [];
    for (const update of workflowUpdates) {
      if (update.artifacts) {
        artifacts.push(...update.artifacts);
      }
      if (update.artifact) {
        artifacts.push(update.artifact);
      }
    }
    // Deduplicate by filename
    const seen = new Set<string>();
    return artifacts.filter(a => {
      if (seen.has(a.filename)) return false;
      seen.add(a.filename);
      return true;
    });
  }, []);

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
      // Use unified LangGraph workflow endpoint
      const response = await fetch('/api/langgraph/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_request: userMessage,
          workspace_root: workspace,
          task_type: 'general',
          enable_debug: true,  // Enable debug logging
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
              });
              setIsHitlModalOpen(true);
              continue; // Don't add to updates list yet
            }

            // Handle thinking stream (DeepSeek-R1)
            if (event.status === 'thinking' && event.updates?.current_thinking) {
              setIsThinking(true);
              setThinkingStream(event.updates.thinking_stream || []);
            }

            // Clear thinking when moving past thinking status
            if (event.status === 'running' && isThinking) {
              setIsThinking(false);
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
    if (!hitlRequest) return;

    try {
      await apiClient.submitHITLResponse(hitlRequest.request_id, {
        action: action as any,
        feedback,
        modified_content: modifiedContent,
      });

      // Close modal and clear request
      setIsHitlModalOpen(false);
      setHitlRequest(null);

      // Add update to show response was submitted
      setUpdates(prev => [
        ...prev,
        {
          agent: 'Human Approval',
          type: action === 'approve' || action === 'confirm' ? 'completed' : 'error',
          status: action === 'approve' || action === 'confirm' ? 'completed' : 'rejected',
          message: action === 'approve' || action === 'confirm'
            ? 'Changes approved by user'
            : `Changes ${action} by user${feedback ? `: ${feedback}` : ''}`,
        },
      ]);
    } catch (error) {
      console.error('Failed to submit HITL response:', error);
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
    <div className="flex h-full bg-[#FAF9F7]">
      {/* LEFT PANEL - Conversation Area */}
      <div className="flex flex-col flex-1 min-w-0">
      {/* Workspace Configuration Dialog */}
      {showWorkspaceDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 animate-in fade-in duration-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#DA7756] to-[#C86A4A] flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-[#1A1A1A]">
                  {workspaceStep === 'project' ? 'New Project' : 'Workspace Path'}
                </h2>
                <p className="text-sm text-[#666666]">
                  {workspaceStep === 'project' ? 'Step 1 of 2' : 'Step 2 of 2'}
                </p>
              </div>
            </div>

            {workspaceStep === 'project' ? (
              <div className="mb-6">
                <label className="block text-sm font-medium text-[#666666] mb-2">
                  Project Name
                </label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="my-awesome-project"
                  className="w-full px-4 py-3 bg-[#F5F4F2] text-[#1A1A1A] placeholder-[#999999] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#DA7756] border border-[#E5E5E5]"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && projectName.trim()) {
                      handleWorkspaceSave();
                    }
                  }}
                  autoFocus
                />
                <p className="mt-2 text-xs text-[#999999]">
                  A directory will be created with this name in your workspace.
                </p>
              </div>
            ) : (
              <div className="mb-6">
                <label className="block text-sm font-medium text-[#666666] mb-2">
                  Base Workspace Path
                </label>
                <input
                  type="text"
                  value={workspaceInput}
                  onChange={(e) => setWorkspaceInput(e.target.value)}
                  placeholder="/home/user/workspace"
                  className="w-full px-4 py-3 bg-[#F5F4F2] text-[#1A1A1A] placeholder-[#999999] rounded-xl focus:outline-none focus:ring-2 focus:ring-[#DA7756] border border-[#E5E5E5]"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleWorkspaceSave();
                    }
                  }}
                  autoFocus
                />
                <div className="mt-3 p-3 bg-[#F0FDF4] border border-[#BBF7D0] rounded-lg">
                  <p className="text-xs text-[#166534]">
                    <span className="font-medium">Full path:</span><br />
                    <code className="font-mono">{workspaceInput}/{projectName}</code>
                  </p>
                </div>
                <p className="mt-2 text-xs text-[#999999]">
                  All generated files will be saved here. You can change this later in settings.
                </p>
              </div>
            )}

            <div className="flex items-center gap-3">
              {workspaceStep === 'path' && (
                <button
                  onClick={() => setWorkspaceStep('project')}
                  className="px-4 py-3 rounded-xl border border-[#E5E5E5] hover:bg-[#F5F4F2] text-[#666666] font-medium transition-colors"
                >
                  Back
                </button>
              )}
              <button
                onClick={handleWorkspaceSave}
                disabled={workspaceStep === 'project' ? !projectName.trim() : !workspaceInput.trim()}
                className="flex-1 px-4 py-3 rounded-xl bg-[#DA7756] hover:bg-[#C86A4A] disabled:bg-[#E5E5E5] disabled:cursor-not-allowed text-white font-medium transition-colors"
              >
                {workspaceStep === 'project' ? 'Next' : 'Continue'}
              </button>
              {workspaceStep === 'project' && (
                <button
                  onClick={() => {
                    // Use default if user skips
                    const defaultPath = '/home/user/workspace/new-project';
                    setWorkspace(defaultPath);
                    localStorage.setItem('workflow_workspace', defaultPath);
                    setShowWorkspaceDialog(false);
                  }}
                  className="px-4 py-3 rounded-xl bg-[#F5F4F2] hover:bg-[#E5E5E5] text-[#666666] font-medium transition-colors"
                >
                  Skip
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Save Conversation Confirmation Dialog */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 animate-in fade-in duration-200">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#3B82F6] to-[#2563EB] flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-[#1A1A1A]">Save Conversation?</h2>
                <p className="text-sm text-[#666666]">Keep this conversation for later</p>
              </div>
            </div>

            <p className="text-sm text-[#666666] mb-6">
              Do you want to save this conversation to your history? You can access it later from the sidebar.
            </p>

            <div className="space-y-3">
              <button
                onClick={() => handleSaveConfirm(true, false)}
                className="w-full px-4 py-3 rounded-xl bg-[#3B82F6] hover:bg-[#2563EB] text-white font-medium transition-colors"
              >
                Save This Time
              </button>
              <button
                onClick={() => handleSaveConfirm(true, true)}
                className="w-full px-4 py-3 rounded-xl bg-[#F5F4F2] hover:bg-[#E5E5E5] text-[#1A1A1A] font-medium transition-colors"
              >
                Always Save Automatically
              </button>
              <button
                onClick={() => handleSaveConfirm(false, false)}
                className="w-full px-4 py-3 rounded-xl border border-[#E5E5E5] hover:bg-[#F5F4F2] text-[#666666] font-medium transition-colors"
              >
                Don't Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DeepSeek-R1 Thinking Indicator - Compact version for left panel */}
      {isThinking && thinkingStream.length > 0 && (
        <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-purple-200 px-4 py-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center flex-shrink-0 animate-pulse">
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-purple-800">DeepSeek-R1 Thinking</span>
            <span className="text-xs text-purple-600 bg-purple-100 px-2 py-0.5 rounded">
              {thinkingStream.length} block{thinkingStream.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      )}

      {/* Workflow Steps Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          {/* Empty state - only show when no history and no current updates */}
          {conversationHistory.length === 0 && updates.length === 0 && !isRunning && (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#DA7756] to-[#C86A4A] flex items-center justify-center mb-6 shadow-lg">
                <svg className="w-10 h-10 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
              </div>
              <h2 className="text-2xl font-semibold text-[#1A1A1A] mb-3">AI Code Assistant</h2>
              <p className="text-[#666666] max-w-md mb-6">
                Ask questions or request coding tasks. The system automatically determines whether to use chat mode or multi-agent workflow.
              </p>
              <div className="space-y-3 mb-6">
                <div className="flex items-center gap-4 text-sm text-[#999999]">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#DA7756]"></div>
                    <span>Planning</span>
                  </div>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#16A34A]"></div>
                    <span>Coding</span>
                  </div>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-[#2563EB]"></div>
                    <span>Review</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-[#999999] bg-[#F5F4F2] px-3 py-2 rounded-lg border border-[#E5E5E5]">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
                <span>Workspace: <span className="font-mono font-medium text-[#666666]">{workspace}</span></span>
                <button
                  onClick={() => setShowWorkspaceDialog(true)}
                  className="ml-2 text-[#DA7756] hover:text-[#C86A4A] transition-colors"
                >
                  Change
                </button>
              </div>
            </div>
          )}

          {/* Conversation History */}
          {conversationHistory.length > 0 && (
            <div className="space-y-6 mb-6">
              {conversationHistory.map((turn, turnIndex) => (
                <div key={`turn-${turnIndex}-${turn.timestamp}`} className="space-y-3">
                  {turn.role === 'user' ? (
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#DA7756] flex items-center justify-center flex-shrink-0">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                        </svg>
                      </div>
                      <div className="flex-1 bg-white rounded-xl p-4 border border-[#E5E5E5] shadow-sm">
                        <p className="text-[#1A1A1A]">{turn.content}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#16A34A] to-[#15803D] flex items-center justify-center flex-shrink-0">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                        </svg>
                      </div>
                      <div className="flex-1 bg-[#F0FDF4] rounded-xl p-4 border border-[#BBF7D0] shadow-sm">
                        <p className="text-[#166534] text-sm mb-2 font-medium">Completed</p>
                        <p className="text-[#1A1A1A]">{turn.content}</p>
                        {turn.artifacts && turn.artifacts.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-[#BBF7D0]">
                            <p className="text-xs text-[#166534] mb-2">Generated files:</p>
                            <div className="flex flex-wrap gap-2">
                              {turn.artifacts.map((artifact, i) => (
                                <span key={i} className="inline-flex items-center px-2 py-1 rounded-md bg-white text-xs text-[#166534] border border-[#BBF7D0]">
                                  <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                  </svg>
                                  {artifact.filename}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Workflow Graph Visualization */}
          {currentWorkflowInfo && isRunning && (
            <WorkflowGraph workflowInfo={currentWorkflowInfo} isRunning={isRunning} />
          )}

          {/* Live Output in Conversation Area - Real-time agent outputs */}
          {isRunning && liveOutputs.size > 0 && (
            <div className="mb-6 bg-gradient-to-r from-gray-900 to-gray-800 rounded-xl border border-gray-700 overflow-hidden shadow-lg">
              <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  <span className="text-sm font-semibold text-white">Live Output</span>
                  <span className="text-xs text-gray-400">({liveOutputs.size} agents)</span>
                </div>
                <span className="text-xs text-gray-500">{formatTime(elapsedTime)}</span>
              </div>
              <div className="max-h-96 overflow-y-auto divide-y divide-gray-700">
                {/* Show all active agent outputs sorted by timestamp (most recent first) */}
                {Array.from(liveOutputs.values())
                  .sort((a, b) => b.timestamp - a.timestamp)
                  .slice(0, 5)  // Show last 5 agents
                  .map((output) => (
                    <div key={output.agentName} className="p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          output.status === 'completed' ? 'bg-green-600/30 text-green-400' :
                          output.status === 'running' || output.status === 'streaming' ? 'bg-blue-600/30 text-blue-400' :
                          output.status === 'error' ? 'bg-red-600/30 text-red-400' :
                          'bg-gray-600/30 text-gray-400'
                        }`}>
                          {output.status === 'running' || output.status === 'streaming' ? (
                            <div className="w-2 h-2 border border-current border-t-transparent rounded-full animate-spin mr-1" />
                          ) : output.status === 'completed' ? (
                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                            </svg>
                          ) : null}
                          {output.agentTitle}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(output.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap bg-gray-900/50 p-2 rounded max-h-32 overflow-y-auto">
                        {output.content.slice(0, 500)}
                        {output.content.length > 500 && '...'}
                        {(output.status === 'running' || output.status === 'streaming') && (
                          <span className="inline-block w-1.5 h-4 bg-green-400 animate-pulse ml-0.5 align-bottom" />
                        )}
                      </pre>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {/* Execution Mode & SharedContext Button */}
          {(executionMode || sharedContext) && (
            <div className="flex items-center justify-between mb-4 p-3 bg-white rounded-xl border border-[#E5E5E5] shadow-sm">
              <div className="flex items-center gap-3">
                {executionMode && (
                  <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium ${
                    executionMode === 'parallel'
                      ? 'bg-purple-100 text-purple-700 border border-purple-200'
                      : 'bg-gray-100 text-gray-700 border border-gray-200'
                  }`}>
                    {executionMode === 'parallel' ? (
                      <>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                        </svg>
                        Parallel Execution
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9h16.5m-16.5 6.75h16.5" />
                        </svg>
                        Sequential Execution
                      </>
                    )}
                  </div>
                )}
              </div>

              {sharedContext && sharedContext.entries.length > 0 && (
                <button
                  onClick={() => setShowSharedContext(true)}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-indigo-100 text-indigo-700 border border-indigo-200 hover:bg-indigo-200 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                  </svg>
                  View Shared Context ({sharedContext.entries.length})
                </button>
              )}
            </div>
          )}

          {/* Current Workflow Updates - Unified Message Box */}
          {updates.length > 0 && (
            <div className="bg-white rounded-xl border border-[#E5E5E5] shadow-sm overflow-hidden">
              {/* Header showing overall progress */}
              <div className="px-4 py-3 bg-gradient-to-r from-[#DA775610] to-[#16A34A10] border-b border-[#E5E5E5]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      isRunning
                        ? 'bg-blue-500 animate-pulse'
                        : updates.some(u => u.status === 'error')
                          ? 'bg-red-500'
                          : 'bg-green-500'
                    }`}>
                      {isRunning ? (
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      ) : updates.some(u => u.status === 'error') ? (
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      )}
                    </div>
                    <div>
                      <h3 className="font-semibold text-[#1A1A1A]">
                        {isRunning ? 'Workflow In Progress' : 'Workflow Completed'}
                        {projectName && (
                          <span className="ml-2 text-sm font-normal text-[#DA7756]">
                            📁 {projectName}
                          </span>
                        )}
                      </h3>
                      <p className="text-sm text-[#666666]">
                        {updates.length} agent{updates.length > 1 ? 's' : ''} • {
                          (() => {
                            const allArtifacts = updates.flatMap(u => u.artifacts || []);
                            const uniqueFiles = new Set(allArtifacts.map(a => a.filename));
                            return uniqueFiles.size;
                          })()
                        } file{(() => {
                          const allArtifacts = updates.flatMap(u => u.artifacts || []);
                          const uniqueFiles = new Set(allArtifacts.map(a => a.filename));
                          return uniqueFiles.size;
                        })() !== 1 ? 's' : ''} generated
                      </p>
                    </div>
                  </div>
                  {/* Show SharedContext indicator if available */}
                  {updates.some(u => u.shared_context_refs) && (
                    <div className="flex items-center gap-2 text-xs text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-lg">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                      </svg>
                      Using Shared Context
                    </div>
                  )}
                </div>
              </div>

              {/* Agent Updates as Sections */}
              <div className="divide-y divide-[#E5E5E5]">
                {updates.map((update, index) => (
                  <WorkflowStep key={`${update.agent}-${index}`} update={update} />
                ))}
              </div>

              {/* Project Structure Summary & File Operations */}
              {(() => {
                const allArtifacts = updates.flatMap(u => u.artifacts || []);
                if (allArtifacts.length === 0) return null;

                // Remove duplicate files (keep latest version)
                const uniqueArtifacts = new Map<string, { artifact: Artifact; agent: string }>();
                updates.forEach(update => {
                  if (update.artifacts) {
                    update.artifacts.forEach(artifact => {
                      // Use filename as key to deduplicate
                      uniqueArtifacts.set(artifact.filename, {
                        artifact,
                        agent: update.agent
                      });
                    });
                  }
                });

                // Build hierarchical file tree structure
                interface TreeNode {
                  type: 'file' | 'directory';
                  name: string;
                  path: string;
                  artifact?: Artifact;
                  agent?: string;
                  children?: Map<string, TreeNode>;
                }

                const rootTree = new Map<string, TreeNode>();

                // Build tree from unique artifacts
                uniqueArtifacts.forEach(({ artifact, agent }, filepath) => {
                  const parts = filepath.split('/');
                  let currentLevel = rootTree;

                  parts.forEach((part, index) => {
                    const isLastPart = index === parts.length - 1;
                    const currentPath = parts.slice(0, index + 1).join('/');

                    if (!currentLevel.has(part)) {
                      currentLevel.set(part, {
                        type: isLastPart ? 'file' : 'directory',
                        name: part,
                        path: currentPath,
                        ...(isLastPart ? { artifact, agent } : { children: new Map() })
                      });
                    }

                    if (!isLastPart) {
                      const node = currentLevel.get(part)!;
                      if (!node.children) node.children = new Map();
                      currentLevel = node.children;
                    }
                  });
                });

                // Get file icon based on extension
                const getFileIcon = (filename: string) => {
                  const ext = filename.split('.').pop()?.toLowerCase();
                  switch (ext) {
                    case 'py': return '🐍';
                    case 'js': case 'ts': case 'jsx': case 'tsx': return '📜';
                    case 'json': return '⚙️';
                    case 'md': case 'txt': return '📝';
                    case 'yml': case 'yaml': return '🔧';
                    case 'html': case 'css': return '🎨';
                    default: return '📄';
                  }
                };

                // Count total directories and files
                const countNodes = (tree: Map<string, TreeNode>): { dirs: number; files: number } => {
                  let dirs = 0;
                  let files = 0;
                  tree.forEach(node => {
                    if (node.type === 'directory') {
                      dirs++;
                      if (node.children) {
                        const childCounts = countNodes(node.children);
                        dirs += childCounts.dirs;
                        files += childCounts.files;
                      }
                    } else {
                      files++;
                    }
                  });
                  return { dirs, files };
                };

                const nodeCounts = countNodes(rootTree);

                // Recursive tree renderer
                const renderTree = (tree: Map<string, TreeNode>, depth: number = 0, isLast: boolean[] = []): JSX.Element[] => {
                  const entries = Array.from(tree.entries()).sort(([, a], [, b]) => {
                    // Directories first, then files
                    if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
                    return a.name.localeCompare(b.name);
                  });

                  return entries.map(([, node], index) => {
                    const isLastNode = index === entries.length - 1;
                    const newIsLast = [...isLast, isLastNode];

                    return (
                      <div key={node.path}>
                        <div className="flex items-start gap-2 hover:bg-[#F5F4F2] px-1 py-0.5 rounded transition-colors group">
                          {/* Indentation guides */}
                          <div className="flex items-center flex-shrink-0">
                            {isLast.map((last, i) => (
                              <span key={i} className="w-4 text-[#999999]">
                                {!last && i < isLast.length ? '│ ' : '  '}
                              </span>
                            ))}
                            <span className="text-[#999999]">{isLastNode ? '└─' : '├─'}</span>
                          </div>

                          <div className="flex-1 min-w-0">
                            {node.type === 'directory' ? (
                              <div>
                                <div className="flex items-center gap-2">
                                  <svg className="w-4 h-4 text-[#DA7756]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                                  </svg>
                                  <span className="text-sm font-semibold text-[#DA7756]">{node.name}/</span>
                                </div>
                              </div>
                            ) : (
                              <div>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span>{getFileIcon(node.name)}</span>
                                  <span className="text-sm font-medium text-[#1A1A1A]">{node.name}</span>
                                  {node.artifact && (
                                    <>
                                      <span className="text-[10px] text-[#999999] bg-[#F5F4F2] px-1.5 py-0.5 rounded">
                                        {node.artifact.language}
                                      </span>
                                      {node.artifact.saved && (
                                        <span className="text-[10px] text-green-700 bg-green-100 px-1.5 py-0.5 rounded border border-green-200">
                                          ✓ Saved
                                        </span>
                                      )}
                                      {node.agent && (
                                        <span className="text-[10px] text-[#16A34A] bg-[#F0FDF4] px-1.5 py-0.5 rounded border border-[#BBF7D0]">
                                          by {node.agent}
                                        </span>
                                      )}
                                    </>
                                  )}
                                </div>
                                {node.artifact?.description && (
                                  <div className="mt-1 text-[11px] text-[#666666] italic ml-5">
                                    💬 {node.artifact.description}
                                  </div>
                                )}
                                {node.artifact?.saved_path && (
                                  <div className="mt-1 text-[10px] text-green-600 font-mono ml-5">
                                    📁 {node.artifact.saved_path}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                        {/* Render children recursively */}
                        {node.children && node.children.size > 0 && (
                          <div>{renderTree(node.children, depth + 1, newIsLast)}</div>
                        )}
                      </div>
                    );
                  });
                };

                return (
                  <div className="px-4 py-3 bg-[#F5F4F2] border-t border-[#E5E5E5]">
                    <button
                      onClick={() => {
                        const treeSection = document.getElementById('project-tree-section');
                        if (treeSection) {
                          treeSection.classList.toggle('hidden');
                        }
                      }}
                      className="flex items-center gap-2 text-sm font-medium text-[#666666] hover:text-[#1A1A1A] w-full transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776" />
                      </svg>
                      <span>📁 Filesystem Structure</span>
                      <span className="text-xs text-[#999999]">({uniqueArtifacts.size} unique files)</span>
                      <svg id="tree-chevron" className="w-4 h-4 ml-auto transition-transform" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                      </svg>
                    </button>
                    <div id="project-tree-section" className="mt-3 hidden">
                      <div className="bg-white rounded-lg p-4 border border-[#E5E5E5]">
                        {/* File Operations Summary */}
                        <div className="mb-4 pb-3 border-b border-[#E5E5E5]">
                          <h4 className="text-xs font-semibold text-[#666666] mb-2">📋 Summary</h4>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="bg-[#F0FDF4] border border-[#BBF7D0] rounded p-2 text-center">
                              <div className="text-lg font-bold text-[#16A34A]">{nodeCounts.files}</div>
                              <div className="text-[#166534]">Files</div>
                            </div>
                            <div className="bg-[#FEF3C7] border border-[#FDE68A] rounded p-2 text-center">
                              <div className="text-lg font-bold text-[#D97706]">{nodeCounts.dirs}</div>
                              <div className="text-[#92400E]">Directories</div>
                            </div>
                            <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded p-2 text-center">
                              <div className="text-lg font-bold text-[#2563EB]">{Array.from(uniqueArtifacts.values()).filter(({ artifact }) => artifact.saved).length}</div>
                              <div className="text-[#1E3A8A]">Saved</div>
                            </div>
                          </div>
                        </div>

                        {/* Hierarchical File Tree */}
                        <div className="space-y-2">
                          <h4 className="text-xs font-semibold text-[#666666] flex items-center gap-2">
                            <span>🌳 Project Structure</span>
                            <span className="text-[10px] font-normal text-[#999999]">(hierarchical view, no duplicates)</span>
                          </h4>
                          <div className="font-mono text-xs bg-gray-50 rounded-lg p-3 border border-gray-200">
                            {renderTree(rootTree)}
                          </div>
                        </div>

                        {/* Help text */}
                        <div className="mt-4 pt-3 border-t border-[#E5E5E5] text-xs text-[#999999]">
                          💡 All files have been created in your workspace. Expand individual file cards above to view, save, or execute code.
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-[#E5E5E5] bg-white">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <form onSubmit={handleSubmit}>
            <div className="flex items-center gap-3">
              {/* Workspace/Project Selector */}
              <WorkspaceProjectSelector
                currentWorkspace={workspace}
                currentProject={workspace}
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

              {/* Input field container */}
              <div className="relative flex-1">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a question or describe a coding task..."
                  disabled={isRunning}
                  className="w-full px-4 py-3 pr-32 bg-[#F5F4F2] text-[#1A1A1A] placeholder-[#999999] rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#DA7756] focus:ring-opacity-50 border border-[#E5E5E5] disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={isRunning || !input.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 rounded-xl bg-[#DA7756] hover:bg-[#C86A4A] disabled:bg-[#E5E5E5] disabled:cursor-not-allowed text-white font-medium text-sm transition-colors flex items-center gap-2"
                >
                  {isRunning ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span>Running</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                      <span>Execute</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
          <div className="mt-2 flex items-center justify-between text-xs text-[#999999]">
            <p>
              Automatically uses chat or workflow mode based on your request
            </p>
            {/* Toggle Status Panel Button */}
            <button
              onClick={() => setShowStatusPanel(!showStatusPanel)}
              className="flex items-center gap-1 text-[#666666] hover:text-[#1A1A1A] transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
              </svg>
              <span>{showStatusPanel ? 'Hide' : 'Show'} Status</span>
            </button>
          </div>
        </div>
      </div>
      </div>{/* End of LEFT PANEL */}

      {/* RIGHT PANEL - Workflow Status (50% width for 5:5 ratio) */}
      {showStatusPanel && (isRunning || savedFiles.length > 0 || totalProgress > 0) && (
        <div className="w-1/2 min-w-[400px] max-w-[800px] border-l border-gray-200 flex-shrink-0 overflow-hidden">
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
          />
        </div>
      )}

      {/* Modals - Positioned outside panels */}
      <SharedContextViewer
        data={sharedContext}
        isVisible={showSharedContext}
        onClose={() => setShowSharedContext(false)}
      />

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

      <DebugPanel
        logs={debugLogs}
        isOpen={isDebugOpen}
        onToggle={() => setIsDebugOpen(!isDebugOpen)}
      />
    </div>
  );
};

export default WorkflowInterface;
