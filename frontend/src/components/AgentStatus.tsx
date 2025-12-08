/**
 * Agent status sidebar component
 */
import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { ModelInfo } from '../types/api';

interface AgentStatusProps {
  sessionId: string;
  taskType: 'reasoning' | 'coding';
  onTaskTypeChange: (taskType: 'reasoning' | 'coding') => void;
}

const AgentStatus: React.FC<AgentStatusProps> = ({
  sessionId,
  taskType,
  onTaskTypeChange,
}) => {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [messageCount, setMessageCount] = useState(0);
  const [isHealthy, setIsHealthy] = useState(false);

  useEffect(() => {
    loadModels();
    checkHealth();
    const interval = setInterval(() => {
      loadStatus();
      checkHealth();
    }, 5000);
    return () => clearInterval(interval);
  }, [sessionId]);

  const loadModels = async () => {
    try {
      const response = await apiClient.listModels();
      setModels(response.models);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const loadStatus = async () => {
    try {
      const status = await apiClient.getAgentStatus(sessionId);
      setMessageCount(status.message_count);
    } catch (error) {
      console.error('Failed to load status:', error);
    }
  };

  const checkHealth = async () => {
    try {
      await apiClient.healthCheck();
      setIsHealthy(true);
    } catch (error) {
      setIsHealthy(false);
    }
  };

  return (
    <div className="w-80 bg-gray-800 border-l border-gray-700 p-6 overflow-y-auto">
      <h2 className="text-xl font-semibold text-white mb-6">Agent Status</h2>

      {/* Health Status */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-2">API Status</h3>
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${
              isHealthy ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-white">
            {isHealthy ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Session Info */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-2">Session</h3>
        <div className="bg-gray-700 rounded p-3">
          <p className="text-xs text-gray-400">Session ID</p>
          <p className="text-sm text-white font-mono break-all">{sessionId}</p>
          <p className="text-xs text-gray-400 mt-2">Messages</p>
          <p className="text-sm text-white">{messageCount}</p>
        </div>
      </div>

      {/* Task Type Selector */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-2">Task Mode</h3>
        <div className="space-y-2">
          <button
            onClick={() => onTaskTypeChange('coding')}
            className={`w-full px-4 py-2 rounded text-left transition-colors ${
              taskType === 'coding'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <div className="font-semibold">Coding</div>
            <div className="text-xs opacity-75">Code generation & fixes</div>
          </button>
          <button
            onClick={() => onTaskTypeChange('reasoning')}
            className={`w-full px-4 py-2 rounded text-left transition-colors ${
              taskType === 'reasoning'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <div className="font-semibold">Reasoning</div>
            <div className="text-xs opacity-75">Complex problem solving</div>
          </button>
        </div>
      </div>

      {/* Models */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-gray-400 mb-2">
          Available Models
        </h3>
        <div className="space-y-2">
          {models.map((model, index) => (
            <div key={index} className="bg-gray-700 rounded p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-400">{model.type}</span>
                <span
                  className={`px-2 py-0.5 text-xs rounded ${
                    model.type === taskType
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-600 text-gray-300'
                  }`}
                >
                  {model.type === taskType ? 'Active' : 'Standby'}
                </span>
              </div>
              <p className="text-sm text-white font-mono text-xs break-all">
                {model.name}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Info */}
      <div className="text-xs text-gray-500 leading-relaxed">
        <p className="mb-2">
          This agent uses Microsoft Agent Framework with vLLM for model serving.
        </p>
        <p>
          Switch between reasoning and coding modes to use different models optimized
          for each task.
        </p>
      </div>
    </div>
  );
};

export default AgentStatus;
