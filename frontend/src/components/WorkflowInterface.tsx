/**
 * WorkflowInterface component - Claude.ai inspired multi-agent workflow UI
 * Supports conversation context for iterative refinement
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { WorkflowUpdate, Artifact } from '../types/api';
import WorkflowStep from './WorkflowStep';
import apiClient from '../api/client';

interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
  updates?: WorkflowUpdate[];
  artifacts?: Artifact[];
  timestamp: number;
}

interface WorkflowInterfaceProps {
  sessionId: string;
  initialUpdates?: WorkflowUpdate[];
}

const WorkflowInterface = ({ sessionId, initialUpdates }: WorkflowInterfaceProps) => {
  const [input, setInput] = useState('');
  const [updates, setUpdates] = useState<WorkflowUpdate[]>([]);
  const [conversationHistory, setConversationHistory] = useState<ConversationTurn[]>([]);
  const [isRunning, setIsRunning] = useState(false);
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

          {/* Current Workflow Updates */}
          {updates.length > 0 && (
            <div className="space-y-4">
              {updates.map((update, index) => (
                <WorkflowStep key={`${update.agent}-${index}`} update={update} />
              ))}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

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
