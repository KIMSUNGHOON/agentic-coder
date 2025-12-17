/**
 * WorkflowInterface component - Claude.ai inspired multi-agent workflow UI
 * Supports conversation context for iterative refinement
 * Now with parallel execution and shared context visualization
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { WorkflowUpdate, Artifact, WorkflowInfo } from '../types/api';
import WorkflowStep from './WorkflowStep';
import SharedContextViewer from './SharedContextViewer';
import apiClient from '../api/client';

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
}

const WorkflowInterface = ({ sessionId, initialUpdates, workspace }: WorkflowInterfaceProps) => {
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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

  // Build context for API request
  const buildContext = useCallback(() => {
    const messages = conversationHistory.map(turn => ({
      role: turn.role,
      content: turn.content
    }));

    // Get all artifacts from history
    const allArtifacts: Artifact[] = [];
    for (const turn of conversationHistory) {
      if (turn.artifacts) {
        allArtifacts.push(...turn.artifacts);
      }
    }
    // Also add artifacts from current updates
    allArtifacts.push(...extractArtifacts(updates));

    // Deduplicate and take latest version of each file
    const artifactMap = new Map<string, Artifact>();
    for (const artifact of allArtifacts) {
      artifactMap.set(artifact.filename, artifact);
    }

    return {
      messages,
      artifacts: Array.from(artifactMap.values()).map(a => ({
        filename: a.filename,
        language: a.language,
        content: a.content
      }))
    };
  }, [conversationHistory, updates, extractArtifacts]);

  // Save workflow state after updates complete
  const saveWorkflowState = async (workflowUpdates: WorkflowUpdate[]) => {
    try {
      await apiClient.updateConversation(sessionId, undefined, {
        updates: workflowUpdates,
      });
    } catch (err) {
      console.error('Failed to save workflow state:', err);
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

    // Build context from conversation history
    const context = buildContext();

    try {
      const response = await fetch('/api/workflow/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          workspace: workspace,
          context: context.messages.length > 0 || context.artifacts.length > 0 ? context : undefined,
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
            const update: WorkflowUpdate = JSON.parse(line);

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
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#FAF9F7]">
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
              <h2 className="text-2xl font-semibold text-[#1A1A1A] mb-3">Multi-Agent Workflow</h2>
              <p className="text-[#666666] max-w-md mb-6">
                Enter a coding task and watch the agents collaborate to plan, code, and review your request.
              </p>
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

          {/* Workflow Progress Indicator */}
          {currentWorkflowInfo && isRunning && (
            <div className="mb-6 p-4 bg-white rounded-xl border border-[#7C3AED40] shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[#7C3AED] animate-pulse" />
                  <span className="text-sm font-medium text-[#7C3AED]">{currentWorkflowInfo.workflow_type}</span>
                </div>
                <span className="text-xs text-[#999999]">
                  {currentWorkflowInfo.current_node === 'END' ? 'Complete' : `Current: ${currentWorkflowInfo.current_node}`}
                </span>
              </div>
              <div className="flex items-center gap-1 overflow-x-auto py-2">
                {/* START */}
                <div className="px-2 py-1 rounded text-xs font-medium bg-[#1A1A1A] text-white flex-shrink-0">
                  START
                </div>
                <svg className="w-4 h-4 text-[#999999] flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                {/* Agent nodes */}
                {currentWorkflowInfo.nodes.map((node, idx) => {
                  const isCurrent = currentWorkflowInfo.current_node === node;
                  const nodeColors: Record<string, string> = {
                    PlanningAgent: '#DA7756',
                    AnalysisAgent: '#EC4899',
                    CodingAgent: '#16A34A',
                    RefactorAgent: '#14B8A6',
                    ReviewAgent: '#2563EB',
                    FixCodeAgent: '#F59E0B',
                    Decision: '#7C3AED'
                  };
                  const color = nodeColors[node] || '#666666';
                  const isComplete = currentWorkflowInfo.nodes.indexOf(currentWorkflowInfo.current_node || '') > idx;

                  return (
                    <div key={node} className="flex items-center gap-1 flex-shrink-0">
                      <div
                        className="px-2 py-1 rounded text-xs font-medium flex items-center gap-1"
                        style={{
                          backgroundColor: isCurrent || isComplete ? color : `${color}30`,
                          color: isCurrent || isComplete ? 'white' : color,
                          boxShadow: isCurrent ? `0 0 0 2px white, 0 0 0 4px ${color}` : undefined
                        }}
                      >
                        {isComplete && (
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                          </svg>
                        )}
                        {isCurrent && <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
                        {node.replace('Agent', '')}
                      </div>
                      {idx < currentWorkflowInfo.nodes.length - 1 && (
                        <svg className="w-4 h-4 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                        </svg>
                      )}
                    </div>
                  );
                })}
                <svg className="w-4 h-4 text-[#999999] flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                {/* END */}
                <div
                  className={`px-2 py-1 rounded text-xs font-medium flex-shrink-0 ${
                    currentWorkflowInfo.current_node === 'END' ? 'bg-[#16A34A] text-white ring-2 ring-[#16A34A] ring-offset-1' : 'bg-[#16A34A30] text-[#16A34A]'
                  }`}
                >
                  {currentWorkflowInfo.current_node === 'END' && (
                    <svg className="w-3 h-3 inline mr-1" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  )}
                  END
                </div>
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

                // Build file tree structure with metadata
                const fileTree: { [key: string]: Array<{ name: string; artifact: Artifact; agent: string }> } = {};
                updates.forEach(update => {
                  if (update.artifacts) {
                    update.artifacts.forEach(artifact => {
                      const parts = artifact.filename.split('/');
                      const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : '.';
                      const filename = parts[parts.length - 1];

                      if (!fileTree[dir]) fileTree[dir] = [];
                      fileTree[dir].push({
                        name: filename,
                        artifact,
                        agent: update.agent
                      });
                    });
                  }
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
                      <span>📁 Project Structure & File Operations</span>
                      <span className="text-xs text-[#999999]">({allArtifacts.length} files)</span>
                      <svg id="tree-chevron" className="w-4 h-4 ml-auto transition-transform" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                      </svg>
                    </button>
                    <div id="project-tree-section" className="mt-3 hidden">
                      <div className="bg-white rounded-lg p-4 border border-[#E5E5E5]">
                        {/* File Operations Summary */}
                        <div className="mb-4 pb-3 border-b border-[#E5E5E5]">
                          <h4 className="text-xs font-semibold text-[#666666] mb-2">📋 File Operations Summary</h4>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="bg-[#F0FDF4] border border-[#BBF7D0] rounded p-2 text-center">
                              <div className="text-lg font-bold text-[#16A34A]">{allArtifacts.length}</div>
                              <div className="text-[#166534]">Files Created</div>
                            </div>
                            <div className="bg-[#FEF3C7] border border-[#FDE68A] rounded p-2 text-center">
                              <div className="text-lg font-bold text-[#D97706]">{Object.keys(fileTree).length}</div>
                              <div className="text-[#92400E]">Directories</div>
                            </div>
                            <div className="bg-[#EFF6FF] border border-[#BFDBFE] rounded p-2 text-center">
                              <div className="text-lg font-bold text-[#2563EB]">{updates.filter(u => u.artifacts?.length).length}</div>
                              <div className="text-[#1E3A8A]">Agents Used</div>
                            </div>
                          </div>
                        </div>

                        {/* File Tree */}
                        <div className="space-y-3">
                          <h4 className="text-xs font-semibold text-[#666666]">🌳 File Tree</h4>
                          <div className="font-mono text-xs">
                            {Object.entries(fileTree).sort(([a], [b]) => a.localeCompare(b)).map(([dir, files]) => (
                              <div key={dir} className="mb-3">
                                <div className="flex items-center gap-2 text-[#DA7756] font-semibold mb-2 bg-[#DA775608] px-2 py-1 rounded">
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                                  </svg>
                                  <span>{dir === '.' ? 'Root Directory' : dir}</span>
                                </div>
                                <div className="ml-4 space-y-1">
                                  {files.map((fileInfo, i) => {
                                    const isLast = i === files.length - 1;
                                    return (
                                      <div key={i} className="group">
                                        <div className="flex items-start gap-2 hover:bg-[#F5F4F2] p-1 rounded transition-colors">
                                          <span className="text-[#999999] flex-shrink-0">{isLast ? '└─' : '├─'}</span>
                                          <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                              <span>{getFileIcon(fileInfo.name)}</span>
                                              <span className="text-[#1A1A1A] font-medium">{fileInfo.name}</span>
                                              <span className="text-[10px] text-[#999999] bg-[#F5F4F2] px-1.5 py-0.5 rounded">
                                                {fileInfo.artifact.language}
                                              </span>
                                              <span className="text-[10px] text-[#16A34A] bg-[#F0FDF4] px-1.5 py-0.5 rounded border border-[#BBF7D0]">
                                                by {fileInfo.agent}
                                              </span>
                                            </div>
                                            {fileInfo.artifact.description && (
                                              <div className="mt-1 ml-6 text-[11px] text-[#666666] italic">
                                                💬 {fileInfo.artifact.description}
                                              </div>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
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

      {/* SharedContext Viewer Modal */}
      <SharedContextViewer
        data={sharedContext}
        isVisible={showSharedContext}
        onClose={() => setShowSharedContext(false)}
      />

      {/* Input Area */}
      <div className="border-t border-[#E5E5E5] bg-white">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <form onSubmit={handleSubmit}>
            <div className="relative">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Describe your coding task..."
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
          </form>
          <p className="mt-2 text-xs text-[#999999] text-center">
            The workflow will automatically plan, implement, and review your request
          </p>
        </div>
      </div>
    </div>
  );
};

export default WorkflowInterface;
