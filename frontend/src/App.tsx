/**
 * Main App component
 */
import { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import WorkflowInterface from './components/WorkflowInterface';
import AgentStatus from './components/AgentStatus';

type Mode = 'chat' | 'workflow';

function App() {
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const [taskType, setTaskType] = useState<'reasoning' | 'coding'>('coding');
  const [mode, setMode] = useState<Mode>('workflow');

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Main Area */}
      <div className="flex-1 flex flex-col p-4">
        {/* Mode Switcher */}
        <div className="mb-4 flex space-x-2">
          <button
            onClick={() => setMode('chat')}
            className={`px-4 py-2 rounded-lg font-semibold transition ${
              mode === 'chat'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            💬 Chat Mode
          </button>
          <button
            onClick={() => setMode('workflow')}
            className={`px-4 py-2 rounded-lg font-semibold transition ${
              mode === 'workflow'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            🤖 Workflow Mode
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {mode === 'chat' ? (
            <ChatInterface sessionId={sessionId} taskType={taskType} />
          ) : (
            <WorkflowInterface sessionId={sessionId} />
          )}
        </div>
      </div>

      {/* Sidebar - only show in chat mode */}
      {mode === 'chat' && (
        <AgentStatus
          sessionId={sessionId}
          taskType={taskType}
          onTaskTypeChange={setTaskType}
        />
      )}
    </div>
  );
}

export default App;
