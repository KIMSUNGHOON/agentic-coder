/**
 * Main App component
 */
import { useState, useCallback } from 'react';
import ChatInterface from './components/ChatInterface';
import WorkflowInterface from './components/WorkflowInterface';
import AgentStatus from './components/AgentStatus';
import ConversationList from './components/ConversationList';
import { Conversation, StoredMessage, WorkflowUpdate } from './types/api';
import apiClient from './api/client';

type Mode = 'chat' | 'workflow';

function App() {
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`);
  const [taskType, setTaskType] = useState<'reasoning' | 'coding'>('coding');
  const [mode, setMode] = useState<Mode>('workflow');
  const [showSidebar, setShowSidebar] = useState(true);

  // Loaded conversation state
  const [loadedMessages, setLoadedMessages] = useState<StoredMessage[]>([]);
  const [loadedWorkflowState, setLoadedWorkflowState] = useState<WorkflowUpdate[]>([]);

  const handleNewConversation = useCallback(() => {
    const newSessionId = `session-${Date.now()}`;
    setSessionId(newSessionId);
    setLoadedMessages([]);
    setLoadedWorkflowState([]);
  }, []);

  const handleSelectConversation = useCallback(async (conversation: Conversation) => {
    try {
      // Load full conversation with messages
      const fullConversation = await apiClient.getConversation(conversation.session_id);

      setSessionId(conversation.session_id);

      if (conversation.mode === 'workflow') {
        setMode('workflow');
        // Extract workflow updates from stored state (saved as { updates: [...] })
        if (fullConversation.workflow_state) {
          try {
            const workflowState = fullConversation.workflow_state as { updates?: WorkflowUpdate[] };
            if (workflowState && workflowState.updates && Array.isArray(workflowState.updates)) {
              setLoadedWorkflowState(workflowState.updates);
            } else {
              console.warn('Invalid workflow state format:', fullConversation.workflow_state);
              setLoadedWorkflowState([]);
            }
          } catch (parseErr) {
            console.error('Failed to parse workflow state:', parseErr);
            setLoadedWorkflowState([]);
          }
        } else {
          setLoadedWorkflowState([]);
        }
      } else {
        setMode('chat');
        setLoadedMessages(fullConversation.messages || []);
      }
    } catch (err) {
      console.error('Failed to load conversation:', err);
      alert(`Failed to load conversation: ${err instanceof Error ? err.message : 'Unknown error'}`);
      // Reset to new conversation on error
      handleNewConversation();
    }
  }, [handleNewConversation]);

  const handleModeChange = (newMode: Mode) => {
    setMode(newMode);
    // Create new session when switching modes
    handleNewConversation();
  };

  return (
    <div className="flex h-screen bg-[#1A1A1A]">
      {/* Conversation List Sidebar */}
      {showSidebar && (
        <ConversationList
          currentSessionId={sessionId}
          mode={mode}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
        />
      )}

      {/* Main Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-[#404040] flex items-center justify-between bg-[#1A1A1A]">
          {/* Sidebar Toggle */}
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-2 text-[#9B9B9B] hover:text-[#ECECF1] hover:bg-[#2A2A2A] rounded-lg transition-colors"
            title={showSidebar ? 'Hide sidebar' : 'Show sidebar'}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>

          {/* Mode Switcher */}
          <div className="flex space-x-2">
            <button
              onClick={() => handleModeChange('chat')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                mode === 'chat'
                  ? 'bg-[#10A37F] text-white hover:bg-[#0E8C6F]'
                  : 'bg-[#2A2A2A] text-[#ECECF1] hover:bg-[#343434]'
              }`}
            >
              Chat Mode
            </button>
            <button
              onClick={() => handleModeChange('workflow')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                mode === 'workflow'
                  ? 'bg-[#10A37F] text-white hover:bg-[#0E8C6F]'
                  : 'bg-[#2A2A2A] text-[#ECECF1] hover:bg-[#343434]'
              }`}
            >
              Workflow Mode
            </button>
          </div>

          {/* Session Info */}
          <div className="text-sm text-[#9B9B9B]">
            Session: {sessionId.slice(-8)}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 p-4 overflow-hidden">
            {mode === 'chat' ? (
              <ChatInterface
                sessionId={sessionId}
                taskType={taskType}
                initialMessages={loadedMessages}
              />
            ) : (
              <WorkflowInterface
                sessionId={sessionId}
                initialUpdates={loadedWorkflowState}
              />
            )}
          </div>

          {/* Right Sidebar - only show in chat mode */}
          {mode === 'chat' && (
            <AgentStatus
              sessionId={sessionId}
              taskType={taskType}
              onTaskTypeChange={setTaskType}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
