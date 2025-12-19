/**
 * WorkflowStatusPanel - Right side panel for workflow monitoring
 * Contains: Progress indicator, Live output, Agent status, File tree
 */
import { useState, useEffect } from 'react';
import { WorkflowUpdate, Artifact } from '../types/api';

interface AgentProgressStatus {
  name: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  executionTime?: number;
  streamingContent?: string;
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
  currentAgent,
  totalProgress,
  elapsedTime,
  estimatedTimeRemaining,
  streamingContent,
  streamingFile,
  savedFiles,
  workspaceRoot,
  projectName,
  projectDir,
}: WorkflowStatusPanelProps) => {
  const [expandedSections, setExpandedSections] = useState({
    progress: true,
    liveOutput: true,
    agents: true,
    files: true,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs.toFixed(0)}s`;
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

  const getAgentStatusIcon = (status: AgentProgressStatus['status']) => {
    switch (status) {
      case 'running':
        return (
          <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
        );
      case 'completed':
        return (
          <svg className="w-3 h-3 text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-3 h-3 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      default:
        return <div className="w-3 h-3 rounded-full bg-gray-600" />;
    }
  };

  const fileTree = savedFiles && savedFiles.length > 0 ? buildFileTree(savedFiles) : [];

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
            </svg>
            <span className="font-semibold">Workflow Status</span>
          </div>
          {isRunning && (
            <span className="flex items-center gap-2 text-xs text-green-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
              </span>
              Running
            </span>
          )}
        </div>
        {/* Project info */}
        {projectName && (
          <div className="mt-2 pt-2 border-t border-gray-700">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-yellow-400">📁</span>
              <span className="text-gray-300 font-medium">{projectName}</span>
            </div>
            {projectDir && (
              <div className="mt-1 text-[11px] text-gray-500 font-mono truncate pl-5">
                {projectDir}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Progress Section */}
        <div className="border-b border-gray-700">
          <button
            onClick={() => toggleSection('progress')}
            className="w-full px-4 py-2 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800"
          >
            <span>📊 Progress</span>
            <svg className={`w-4 h-4 transition-transform ${expandedSections.progress ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {expandedSections.progress && (
            <div className="px-4 pb-3">
              {/* Progress Bar */}
              <div className="mb-3">
                <div className="flex justify-between text-xs text-gray-400 mb-1">
                  <span>{totalProgress.toFixed(0)}%</span>
                  <span>{formatTime(elapsedTime)}</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-300"
                    style={{ width: `${totalProgress}%` }}
                  />
                </div>
                {estimatedTimeRemaining !== undefined && estimatedTimeRemaining > 0 && (
                  <div className="text-xs text-gray-500 mt-1 text-right">
                    ETA: ~{formatTime(estimatedTimeRemaining)}
                  </div>
                )}
              </div>

              {/* Agent Pipeline */}
              <div className="flex items-center gap-1 overflow-x-auto pb-2">
                {agents.map((agent, index) => (
                  <div key={agent.name} className="flex items-center">
                    <div
                      className={`flex items-center gap-1 px-2 py-1 rounded text-xs whitespace-nowrap ${
                        agent.status === 'running'
                          ? 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-400'
                          : agent.status === 'completed'
                          ? 'bg-green-500/20 text-green-300'
                          : agent.status === 'error'
                          ? 'bg-red-500/20 text-red-300'
                          : 'bg-gray-700 text-gray-400'
                      }`}
                    >
                      {getAgentStatusIcon(agent.status)}
                      <span>{agent.title.split(' ')[0]}</span>
                    </div>
                    {index < agents.length - 1 && (
                      <svg className="w-4 h-4 text-gray-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

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

        {/* Agents Section */}
        <div className="border-b border-gray-700">
          <button
            onClick={() => toggleSection('agents')}
            className="w-full px-4 py-2 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800"
          >
            <span>🤖 Agents ({agents.filter(a => a.status === 'completed').length}/{agents.length})</span>
            <svg className={`w-4 h-4 transition-transform ${expandedSections.agents ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
            </svg>
          </button>
          {expandedSections.agents && (
            <div className="px-4 pb-3 space-y-2">
              {agents.map(agent => (
                <div
                  key={agent.name}
                  className={`p-2 rounded-lg ${
                    agent.status === 'running'
                      ? 'bg-blue-500/10 ring-1 ring-blue-500/30'
                      : agent.status === 'completed'
                      ? 'bg-gray-800'
                      : agent.status === 'error'
                      ? 'bg-red-500/10'
                      : 'bg-gray-800/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getAgentStatusIcon(agent.status)}
                      <span className={`text-sm font-medium ${agent.status === 'running' ? 'text-blue-300' : 'text-gray-200'}`}>
                        {agent.title}
                      </span>
                    </div>
                    {agent.executionTime !== undefined && (
                      <span className="text-xs text-gray-500">
                        {agent.executionTime.toFixed(1)}s
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{agent.description}</p>
                  {agent.status === 'running' && agent.streamingContent && (
                    <pre className="mt-2 text-[10px] font-mono text-gray-500 bg-gray-900 p-2 rounded max-h-16 overflow-auto">
                      {agent.streamingContent.slice(0, 200)}
                      {agent.streamingContent.length > 200 && '...'}
                    </pre>
                  )}
                </div>
              ))}
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

      {/* Footer */}
      {!isRunning && savedFiles && savedFiles.length > 0 && (
        <div className="px-4 py-3 bg-gray-800 border-t border-gray-700">
          <div className="flex items-center justify-between text-xs">
            <span className="text-green-400">✅ Workflow Complete</span>
            <span className="text-gray-500">{formatTime(elapsedTime)} total</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowStatusPanel;
