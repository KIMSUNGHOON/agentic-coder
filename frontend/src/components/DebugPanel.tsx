/**
 * DebugPanel - Real-time debugging panel for LangGraph workflow
 *
 * Displays:
 * - Agent thinking processes
 * - LLM prompts and responses
 * - Tool calls and results
 * - Token usage statistics
 */

import React, { useState } from 'react';

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

interface DebugPanelProps {
  logs: DebugLog[];
  isOpen: boolean;
  onToggle: () => void;
}

export const DebugPanel: React.FC<DebugPanelProps> = ({ logs, isOpen, onToggle }) => {
  const [selectedNode, setSelectedNode] = useState<string>('all');
  const [selectedEventType, setSelectedEventType] = useState<string>('all');

  // Get unique nodes and event types
  const nodes = ['all', ...new Set(logs.map(log => log.node))];
  const eventTypes = ['all', ...new Set(logs.map(log => log.event_type))];

  // Filter logs
  const filteredLogs = logs.filter(log => {
    if (selectedNode !== 'all' && log.node !== selectedNode) return false;
    if (selectedEventType !== 'all' && log.event_type !== selectedEventType) return false;
    return true;
  });

  // Calculate total tokens
  const totalTokens = logs.reduce((sum, log) => {
    return sum + (log.token_usage?.total_tokens || 0);
  }, 0);

  const eventTypeColors = {
    thinking: 'bg-blue-100 text-blue-800 border-blue-300',
    tool_call: 'bg-purple-100 text-purple-800 border-purple-300',
    prompt: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    result: 'bg-green-100 text-green-800 border-green-300',
    error: 'bg-red-100 text-red-800 border-red-300',
  };

  const eventTypeIcons = {
    thinking: '💭',
    tool_call: '🔧',
    prompt: '📝',
    result: '✅',
    error: '❌',
  };

  return (
    <div className={`fixed right-0 top-0 h-full bg-white shadow-2xl transition-all duration-300 z-50 ${isOpen ? 'w-1/3' : 'w-0'} overflow-hidden`}>
      {/* Toggle Button */}
      <button
        onClick={onToggle}
        className="absolute -left-12 top-4 bg-gray-800 text-white p-3 rounded-l-lg hover:bg-gray-700 transition-colors"
        title={isOpen ? 'Close Debug Panel' : 'Open Debug Panel'}
      >
        {isOpen ? '→' : '←'}
        <span className="ml-2 text-xs">Debug</span>
      </button>

      {/* Panel Content */}
      {isOpen && (
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="bg-gray-800 text-white p-4 flex-shrink-0">
            <h2 className="text-xl font-bold">🔍 Debug Panel</h2>
            <div className="mt-2 text-sm opacity-80">
              {logs.length} events • {totalTokens.toLocaleString()} tokens
            </div>
          </div>

          {/* Filters */}
          <div className="bg-gray-100 p-3 flex-shrink-0 border-b">
            <div className="flex gap-2">
              {/* Node Filter */}
              <select
                value={selectedNode}
                onChange={(e) => setSelectedNode(e.target.value)}
                className="flex-1 px-3 py-1 border rounded text-sm"
              >
                {nodes.map(node => (
                  <option key={node} value={node}>
                    {node === 'all' ? 'All Nodes' : node}
                  </option>
                ))}
              </select>

              {/* Event Type Filter */}
              <select
                value={selectedEventType}
                onChange={(e) => setSelectedEventType(e.target.value)}
                className="flex-1 px-3 py-1 border rounded text-sm"
              >
                {eventTypes.map(type => (
                  <option key={type} value={type}>
                    {type === 'all' ? 'All Events' : type}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Logs List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {filteredLogs.length === 0 ? (
              <div className="text-center text-gray-400 mt-8">
                No debug logs to display
              </div>
            ) : (
              filteredLogs.map((log, idx) => (
                <div
                  key={idx}
                  className={`border rounded-lg p-3 ${eventTypeColors[log.event_type]} transition-all hover:shadow-md`}
                >
                  {/* Header */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{eventTypeIcons[log.event_type]}</span>
                      <span className="font-semibold text-sm">
                        {log.node} / {log.agent}
                      </span>
                    </div>
                    <span className="text-xs opacity-70">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Event Type Badge */}
                  <div className="mb-2">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-white bg-opacity-50">
                      {log.event_type}
                    </span>
                  </div>

                  {/* Content */}
                  <div className="text-sm font-mono whitespace-pre-wrap bg-white bg-opacity-50 p-2 rounded max-h-40 overflow-y-auto">
                    {log.content}
                  </div>

                  {/* Metadata */}
                  {log.metadata && Object.keys(log.metadata).length > 0 && (
                    <details className="mt-2">
                      <summary className="text-xs cursor-pointer hover:underline">
                        Metadata
                      </summary>
                      <pre className="text-xs mt-1 bg-white bg-opacity-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    </details>
                  )}

                  {/* Token Usage */}
                  {log.token_usage && (
                    <div className="mt-2 text-xs flex gap-3">
                      <span>🎫 Prompt: {log.token_usage.prompt_tokens}</span>
                      <span>💬 Completion: {log.token_usage.completion_tokens}</span>
                      <span className="font-bold">Σ Total: {log.token_usage.total_tokens}</span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DebugPanel;
