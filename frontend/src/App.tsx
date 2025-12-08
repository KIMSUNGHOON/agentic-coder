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
        // Convert stored messages to workflow updates if available
        if (fullConversation.workflow_state) {
          setLoadedWorkflowState(fullConversation.workflow_state as unknown as WorkflowUpdate[]);
        }
      } else {
        setMode('chat');
        setLoadedMessages(fullConversation.messages || []);
      }
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  }, []);

  const handleModeChange = (newMode: Mode) => {
    setMode(newMode);
    // Create new session when switching modes
    handleNewConversation();
  };

  return (
    <div className="flex h-screen bg-gray-900">
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
        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
          {/* Sidebar Toggle */}
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-2 text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded-lg transition-colors"
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
              className={`px-4 py-2 rounded-lg font-semibold transition ${
                mode === 'chat'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Chat Mode
            </button>
            <button
              onClick={() => handleModeChange('workflow')}
              className={`px-4 py-2 rounded-lg font-semibold transition ${
                mode === 'workflow'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Workflow Mode
            </button>
          </div>

          {/* Session Info */}
          <div className="text-sm text-gray-500">
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
