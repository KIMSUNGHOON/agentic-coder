/**
 * WorkflowInterface component - main UI for multi-agent workflow
 */
import { useState, useRef, useEffect } from 'react';
import { WorkflowUpdate } from '../types/api';
import WorkflowStep from './WorkflowStep';
import apiClient from '../api/client';

interface WorkflowInterfaceProps {
  sessionId: string;
  initialUpdates?: WorkflowUpdate[];
}

const WorkflowInterface = ({ sessionId, initialUpdates }: WorkflowInterfaceProps) => {
  const [input, setInput] = useState('');
  const [updates, setUpdates] = useState<WorkflowUpdate[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [updates]);

  // Load initial updates when session changes
  useEffect(() => {
    if (initialUpdates && initialUpdates.length > 0) {
      setUpdates(initialUpdates);
    } else {
      setUpdates([]);
    }
  }, [sessionId, initialUpdates]);

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
    setUpdates([]);
    setIsRunning(true);

    // Create/update conversation for workflow
    try {
      await apiClient.createConversation(sessionId, userMessage.slice(0, 50), 'workflow');
    } catch (err) {
      // Conversation might already exist, continue
      console.log('Conversation may already exist:', err);
    }

    // Save user message
    try {
      await apiClient.addMessage(sessionId, 'user', userMessage);
    } catch (err) {
      console.error('Failed to save user message:', err);
    }

    const allUpdates: WorkflowUpdate[] = [];

    try {
      const response = await fetch('http://localhost:8000/api/workflow/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
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
              // Update existing or add new
              const existingIndex = prev.findIndex(u => u.agent === update.agent);
              if (existingIndex >= 0 && update.status !== 'running') {
                // Update existing step
                const newUpdates = [...prev];
                newUpdates[existingIndex] = update;
                return newUpdates;
              } else {
                // Add new step
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
    <div className="flex flex-col h-full bg-gray-800 rounded-lg">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-2xl font-bold text-white mb-2">
          Multi-Agent Workflow
        </h2>
        <p className="text-gray-400 text-sm">
          Planning → Coding → Review
        </p>
      </div>

      {/* Workflow Steps */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {updates.length === 0 && !isRunning && (
          <div className="text-center text-gray-500 mt-20">
            <div className="text-6xl mb-4">🚀</div>
            <p className="text-xl">Enter a coding task to start the workflow</p>
            <p className="text-sm mt-2">
              The multi-agent system will plan, code, and review your request
            </p>
          </div>
        )}

        {updates.map((update, index) => (
          <WorkflowStep key={`${update.agent}-${index}`} update={update} />
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-gray-700">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Enter your coding task..."
            disabled={isRunning}
            className="flex-1 bg-gray-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isRunning || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {isRunning ? (
              <span className="flex items-center space-x-2">
                <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                <span>Running...</span>
              </span>
            ) : (
              'Execute Workflow'
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default WorkflowInterface;
