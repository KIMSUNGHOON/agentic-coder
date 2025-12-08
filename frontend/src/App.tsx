/**
 * Main App component
 */
import { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import AgentStatus from './components/AgentStatus';

function App() {
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const [taskType, setTaskType] = useState<'reasoning' | 'coding'>('coding');

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Main Chat Area */}
      <div className="flex-1 p-4">
        <ChatInterface sessionId={sessionId} taskType={taskType} />
      </div>

      {/* Sidebar */}
      <AgentStatus
        sessionId={sessionId}
        taskType={taskType}
        onTaskTypeChange={setTaskType}
      />
    </div>
  );
}

export default App;
