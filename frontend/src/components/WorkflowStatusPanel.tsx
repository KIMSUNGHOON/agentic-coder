/**
 * WorkflowStatusPanel - Right side panel for workflow monitoring
 * Simplified version - Progress/Pipeline moved to DashboardHeader
 * Contains: Live output, Agent details, File tree
 */
import { useState } from 'react';
import { Artifact } from '../types/api';

interface AgentProgressStatus {
  name: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  executionTime?: number;
  streamingContent?: string;
  // Token usage tracking
  tokenUsage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  language?: string;
  saved?: boolean;
  savedPath?: string;
  description?: string;
  content?: string;
  children?: FileTreeNode[];
}

interface WorkflowStatusPanelProps {
  isRunning: boolean;
  agents: AgentProgressStatus[];
  currentAgent?: string;
  totalProgress: number;
  elapsedTime: number;
  estimatedTimeRemaining?: number;
  streamingContent?: string;
  streamingFile?: string;
  savedFiles?: Artifact[];
  workspaceRoot?: string;
  projectName?: string;
  projectDir?: string;
}

const WorkflowStatusPanel = ({
  isRunning,
  agents,
  // Props passed from parent but handled in DashboardHeader now:
  // currentAgent, totalProgress, elapsedTime, estimatedTimeRemaining, projectName, projectDir
  streamingContent,
  streamingFile,
  savedFiles,
  workspaceRoot,
}: WorkflowStatusPanelProps) => {
  const [expandedSections, setExpandedSections] = useState({
    liveOutput: true,
    agents: false,  // Collapsed by default since pipeline is in header
    files: true,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Build file tree from saved files
  const buildFileTree = (files: Artifact[]): FileTreeNode[] => {
    const root: Map<string, FileTreeNode> = new Map();

    files.forEach(file => {
      const parts = file.filename.split('/');
      let currentLevel = root;

      parts.forEach((part, index) => {
        const isLastPart = index === parts.length - 1;
        const currentPath = parts.slice(0, index + 1).join('/');

        if (!currentLevel.has(part)) {
          const node: FileTreeNode = {
            name: part,
            path: currentPath,
            type: isLastPart ? 'file' : 'directory',
            ...(isLastPart && {
              language: file.language,
              saved: file.saved,
              savedPath: file.saved_path || undefined,
              description: file.description || undefined,
              content: file.content?.slice(0, 100) || undefined,
            }),
          };
          if (!isLastPart) {
            node.children = [];
          }
          currentLevel.set(part, node);
        }

        if (!isLastPart) {
          const existingNode = currentLevel.get(part)!;
          if (!existingNode.children) {
            existingNode.children = [];
          }
          // Convert children array to map for next iteration
          const childMap = new Map<string, FileTreeNode>();
          existingNode.children.forEach(child => childMap.set(child.name, child));
          currentLevel = childMap;
          // Update children back to array
          existingNode.children = Array.from(childMap.values());
        }
      });
    });

    return Array.from(root.values());
  };

  // Get file type icon based on extension
  const getFileIcon = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    const iconMap: Record<string, string> = {
      'py': '🐍',
      'js': '📜',
      'ts': '📜',
      'tsx': '⚛️',
      'jsx': '⚛️',
      'html': '🌐',
      'css': '🎨',
      'json': '⚙️',
      'md': '📝',
      'txt': '📄',
      'yml': '🔧',
      'yaml': '🔧',
      'sql': '🗄️',
      'sh': '💻',
      'dockerfile': '🐳',
    };
    return iconMap[ext] || '📄';
  };

  const renderFileTree = (nodes: FileTreeNode[], depth: number = 0): JSX.Element[] => {
    return nodes
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map(node => (
        <div key={node.path} style={{ marginLeft: depth * 12 }}>
          <div className="flex items-start gap-2 py-1.5 px-2 rounded hover:bg-gray-700/50 text-sm group">
            {node.type === 'directory' ? (
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-yellow-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                  </svg>
                  <span className="text-yellow-300 font-medium">{node.name}/</span>
                </div>
              </div>
            ) : (
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="flex-shrink-0">{getFileIcon(node.name)}</span>
                  <span className="text-gray-200 font-medium truncate">{node.name}</span>
                  {node.language && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-600/30 text-blue-300 flex-shrink-0">{node.language}</span>
                  )}
                  {node.saved && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-600/30 text-green-400 flex-shrink-0">✓ saved</span>
                  )}
                </div>
                {/* File description/comment */}
                {node.description && (
                  <div className="mt-1 text-[11px] text-gray-400 italic pl-5 leading-relaxed">
                    💬 {node.description}
                  </div>
                )}
                {/* Saved path */}
                {node.savedPath && (
                  <div className="mt-0.5 text-[10px] text-green-500/70 font-mono pl-5 truncate">
                    📂 {node.savedPath}
                  </div>
                )}
              </div>
            )}
          </div>
          {node.children && node.children.length > 0 && renderFileTree(node.children, depth + 1)}
        </div>
      ));
  };

  const fileTree = savedFiles && savedFiles.length > 0 ? buildFileTree(savedFiles) : [];

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 overflow-hidden">
      {/* Compact Header - Just title */}
      <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
          </svg>
          <span className="text-sm font-medium">Details</span>
        </div>
        {isRunning ? (
          <span className="flex items-center gap-1.5 text-xs text-green-400">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500"></span>
            </span>
            Active
          </span>
        ) : savedFiles && savedFiles.length > 0 ? (
          <span className="text-xs text-green-400">✓ Done</span>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto">

        {/* Live Output Section */}
        {(isRunning || streamingContent) && (
          <div className="border-b border-gray-700">
            <button
              onClick={() => toggleSection('liveOutput')}
              className="w-full px-4 py-2 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800"
            >
              <span className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                Live Output
                {streamingFile && (
                  <span className="text-xs text-gray-500 font-mono">{streamingFile}</span>
                )}
              </span>
              <svg className={`w-4 h-4 transition-transform ${expandedSections.liveOutput ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            {expandedSections.liveOutput && streamingContent && (
              <div className="px-4 pb-3">
                <pre className="bg-gray-800 rounded-lg p-3 text-xs font-mono text-gray-300 max-h-48 overflow-auto whitespace-pre-wrap">
                  {streamingContent}
                  {isRunning && <span className="inline-block w-2 h-4 bg-green-400 animate-pulse ml-0.5" />}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Agents Section - Enhanced Card Design */}
        <div className="border-b border-gray-700">
          <button
            onClick={() => toggleSection('agents')}
            className="w-full px-4 py-2 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800"
          >
            <div className="flex items-center gap-2">
              <span>🤖 Agent Details</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                {agents.filter(a => a.status === 'completed').length}/{agents.length}
              </span>
            </div>
            <svg className={`w-4 h-4 transition-transform ${expandedSections.agents ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {expandedSections.agents && (
            <div className="px-3 pb-3 space-y-2">
              {agents.map(agent => {
                // Extract emoji from title
                const emoji = agent.title.match(/^[\p{Emoji}]/u)?.[0] || '🤖';
                const titleWithoutEmoji = agent.title.replace(/^[\p{Emoji}]\s*/u, '');

                // Status-based styling
                const statusConfig = {
                  running: {
                    bg: 'bg-gradient-to-r from-blue-900/40 to-blue-800/20',
                    border: 'border-blue-500/50',
                    textColor: 'text-blue-300',
                    iconBg: 'bg-blue-500',
                  },
                  completed: {
                    bg: 'bg-gray-800/60',
                    border: 'border-green-500/30',
                    textColor: 'text-green-400',
                    iconBg: 'bg-green-500',
                  },
                  error: {
                    bg: 'bg-gradient-to-r from-red-900/30 to-red-800/10',
                    border: 'border-red-500/50',
                    textColor: 'text-red-400',
                    iconBg: 'bg-red-500',
                  },
                  pending: {
                    bg: 'bg-gray-800/30',
                    border: 'border-gray-600/30',
                    textColor: 'text-gray-500',
                    iconBg: 'bg-gray-600',
                  },
                };

                const config = statusConfig[agent.status] || statusConfig.pending;

                return (
                  <div
                    key={agent.name}
                    className={`
                      rounded-lg border overflow-hidden transition-all duration-200
                      ${config.bg} ${config.border}
                      ${agent.status === 'running' ? 'shadow-lg shadow-blue-500/10' : ''}
                    `}
                  >
                    {/* Card Header */}
                    <div className="px-3 py-2 flex items-center gap-3">
                      {/* Status Icon Circle */}
                      <div className={`
                        w-8 h-8 rounded-lg flex items-center justify-center text-sm
                        ${config.iconBg}
                        ${agent.status === 'running' ? 'animate-pulse' : ''}
                      `}>
                        {agent.status === 'running' ? (
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        ) : agent.status === 'completed' ? (
                          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                          </svg>
                        ) : agent.status === 'error' ? (
                          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        ) : (
                          <span className="text-white text-xs">{emoji}</span>
                        )}
                      </div>

                      {/* Agent Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-semibold ${config.textColor}`}>
                            {titleWithoutEmoji}
                          </span>
                          {agent.status === 'running' && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/30 text-blue-300 animate-pulse">
                              Active
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-gray-400 truncate">{agent.description}</p>
                      </div>

                      {/* Stats */}
                      <div className="text-right flex-shrink-0">
                        {agent.executionTime !== undefined && (
                          <div className="text-sm font-mono font-semibold text-gray-300">
                            {agent.executionTime.toFixed(1)}s
                          </div>
                        )}
                        {/* Token Usage Display */}
                        <div className="text-[9px] text-gray-500 font-mono">
                          {agent.tokenUsage ? (
                            <span title={`Prompt: ${agent.tokenUsage.promptTokens}, Completion: ${agent.tokenUsage.completionTokens}`}>
                              {agent.tokenUsage.totalTokens.toLocaleString()} tok
                            </span>
                          ) : agent.status === 'completed' || agent.status === 'running' ? (
                            <span className="opacity-50">-- tok</span>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    {/* Streaming Content (only for running agents) */}
                    {agent.status === 'running' && agent.streamingContent && (
                      <div className="px-3 pb-2">
                        <pre className="text-[10px] font-mono text-gray-400 bg-gray-900/50 p-2 rounded max-h-20 overflow-auto whitespace-pre-wrap border border-gray-700/50">
                          {agent.streamingContent.slice(0, 300)}
                          {agent.streamingContent.length > 300 && '...'}
                          <span className="inline-block w-1.5 h-3 bg-blue-400 animate-pulse ml-0.5 align-bottom" />
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Files Section */}
        {savedFiles && savedFiles.length > 0 && (
          <div className="border-b border-gray-700">
            <button
              onClick={() => toggleSection('files')}
              className="w-full px-4 py-2 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800"
            >
              <span>📁 Generated Files ({savedFiles.length})</span>
              <svg className={`w-4 h-4 transition-transform ${expandedSections.files ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
            {expandedSections.files && (
              <div className="px-2 pb-3">
                {/* Workspace info */}
                {workspaceRoot && (
                  <div className="px-2 py-1 mb-2 text-xs text-gray-500 font-mono border-b border-gray-700">
                    📂 {workspaceRoot}
                  </div>
                )}
                {/* File tree */}
                <div className="bg-gray-800 rounded-lg p-2">
                  {renderFileTree(fileTree)}
                </div>
                {/* Summary */}
                <div className="mt-2 px-2 grid grid-cols-3 gap-2">
                  <div className="text-center p-2 bg-gray-800 rounded">
                    <div className="text-lg font-bold text-green-400">{savedFiles.filter(f => f.saved).length}</div>
                    <div className="text-[10px] text-gray-500">Saved</div>
                  </div>
                  <div className="text-center p-2 bg-gray-800 rounded">
                    <div className="text-lg font-bold text-blue-400">{savedFiles.length}</div>
                    <div className="text-[10px] text-gray-500">Total</div>
                  </div>
                  <div className="text-center p-2 bg-gray-800 rounded">
                    <div className="text-lg font-bold text-yellow-400">
                      {new Set(savedFiles.map(f => f.filename.split('/').slice(0, -1).join('/'))).size}
                    </div>
                    <div className="text-[10px] text-gray-500">Dirs</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Compact Footer with Quick Stats */}
      {savedFiles && savedFiles.length > 0 && (
        <div className="px-3 py-2 bg-gray-800 border-t border-gray-700">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <span className="text-gray-400">
                <span className="text-green-400 font-medium">{savedFiles.filter(f => f.saved).length}</span>
                <span className="mx-1">/</span>
                <span>{savedFiles.length}</span> files
              </span>
            </div>
            {!isRunning && (
              <span className="text-green-400 text-[10px]">✓ Complete</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowStatusPanel;
