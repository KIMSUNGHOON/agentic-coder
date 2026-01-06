/**
 * WorkflowStatusPanel - 우측 사이드바
 * Claude Code 스타일: 터미널 형태, 최소화, 효율적
 */
import { useState } from 'react';
import { Artifact } from '../types/api';
import apiClient from '../api/client';

interface AgentProgressStatus {
  name: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  executionTime?: number;
  streamingContent?: string;
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
  relativePath?: string;
  description?: string;
  content?: string;
  action?: 'created' | 'modified';
  sizeBytes?: number;
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
  sessionId?: string;  // For download functionality
}

// 한글 에이전트 이름 매핑
const agentKoreanNames: Record<string, string> = {
  '🧠 Supervisor': '🧠 감독자',
  '🏗️ Architect': '🏗️ 설계자',
  '💻 Coder': '💻 코더',
  '👀 Reviewer': '👀 검토자',
  '🧪 QA Tester': '🧪 QA 테스터',
  '🔒 Security': '🔒 보안 검사',
  '🔧 Refiner': '🔧 개선자',
  '📊 Aggregator': '📊 취합자',
  '👤 Human Review': '👤 사용자 검토',
  '💾 Persistence': '💾 저장',
};

const WorkflowStatusPanel = ({
  isRunning,
  agents,
  streamingContent,
  savedFiles,
  projectDir,
  sessionId,
}: WorkflowStatusPanelProps) => {
  const [expandedSections, setExpandedSections] = useState({
    output: true,
    files: true,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // 파일 트리 생성 (개선된 알고리즘 - 디렉토리 구조 정확히 표시)
  const buildFileTree = (files: Artifact[]): FileTreeNode[] => {
    // Use nested Maps for efficient tree building
    interface TreeNode {
      node: FileTreeNode;
      childMap: Map<string, TreeNode>;
    }

    const rootMap = new Map<string, TreeNode>();

    files.forEach(file => {
      // Handle both path formats: "dir/file.ext" and "file.ext"
      const filename = file.filename || '';
      const parts = filename.split('/').filter(p => p.length > 0);
      if (parts.length === 0) return;

      let currentLevel = rootMap;

      parts.forEach((part, index) => {
        const isLastPart = index === parts.length - 1;
        const currentPath = parts.slice(0, index + 1).join('/');

        if (!currentLevel.has(part)) {
          const newNode: FileTreeNode = {
            name: part,
            path: currentPath,
            type: isLastPart ? 'file' : 'directory',
            children: isLastPart ? undefined : [],
          };

          // Add file-specific properties
          if (isLastPart) {
            newNode.language = file.language;
            newNode.saved = file.saved;
            newNode.savedPath = file.saved_path || undefined;
            newNode.relativePath = file.relative_path;
            newNode.description = file.description;
            newNode.content = file.content?.slice(0, 100);
            newNode.action = file.action;
            newNode.sizeBytes = file.size_bytes;
          }

          currentLevel.set(part, {
            node: newNode,
            childMap: new Map(),
          });
        }

        if (!isLastPart) {
          currentLevel = currentLevel.get(part)!.childMap;
        }
      });
    });

    // Convert nested Maps to array structure
    const convertToArray = (map: Map<string, TreeNode>): FileTreeNode[] => {
      const result: FileTreeNode[] = [];
      map.forEach((treeNode) => {
        const node = { ...treeNode.node };
        if (treeNode.childMap.size > 0) {
          node.children = convertToArray(treeNode.childMap);
        }
        result.push(node);
      });
      return result;
    };

    return convertToArray(rootMap);
  };

  // 파일 아이콘
  const getFileIcon = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    const icons: Record<string, string> = {
      py: '🐍', js: '📜', ts: '📜', tsx: '⚛️', jsx: '⚛️',
      html: '🌐', css: '🎨', json: '⚙️', md: '📝',
      yml: '🔧', yaml: '🔧', sql: '🗄️', sh: '💻',
    };
    return icons[ext] || '📄';
  };

  const renderFileTree = (nodes: FileTreeNode[], depth: number = 0): JSX.Element[] => {
    return nodes
      .sort((a, b) => {
        if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
        return a.name.localeCompare(b.name);
      })
      .map(node => (
        <div key={node.path} style={{ paddingLeft: depth * 8 }}>
          <div className="flex items-center gap-1 py-0.5 px-1 rounded hover:bg-gray-700/50 text-[10px] lg:text-xs group">
            {node.type === 'directory' ? (
              <>
                <span className="text-yellow-500">📁</span>
                <span className="text-yellow-400 truncate">{node.name}/</span>
              </>
            ) : (
              <>
                <span className="flex-shrink-0">{getFileIcon(node.name)}</span>
                <span className="text-gray-300 truncate flex-1 min-w-0">{node.name}</span>
                {node.action && (
                  <span className={`text-[8px] lg:text-[9px] px-1 rounded flex-shrink-0 ${
                    node.action === 'created' ? 'bg-green-500/20 text-green-400' : 'bg-amber-500/20 text-amber-400'
                  }`}>
                    {node.action === 'created' ? '+생성' : '~수정'}
                  </span>
                )}
                {node.sizeBytes !== undefined && (
                  <span className="text-[8px] lg:text-[9px] text-gray-600 flex-shrink-0 hidden sm:inline">
                    {node.sizeBytes < 1024 ? `${node.sizeBytes}B` : `${(node.sizeBytes / 1024).toFixed(1)}K`}
                  </span>
                )}
              </>
            )}
          </div>
          {node.children && node.children.length > 0 && renderFileTree(node.children, depth + 1)}
        </div>
      ));
  };

  // 에이전트 이름 한글화
  const getKoreanAgentName = (title: string): string => {
    return agentKoreanNames[title] || title;
  };

  const fileTree = savedFiles && savedFiles.length > 0 ? buildFileTree(savedFiles) : [];
  const createdCount = savedFiles?.filter(f => f.action === 'created').length || 0;
  const modifiedCount = savedFiles?.filter(f => f.action === 'modified').length || 0;

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 text-xs lg:text-sm">
      {/* 헤더 */}
      <div className="px-2 lg:px-3 py-1.5 lg:py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
        <span className="font-medium text-[10px] lg:text-xs text-gray-400">출력</span>
        {isRunning ? (
          <span className="flex items-center gap-1 text-[9px] lg:text-[10px] text-green-400">
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
            실행 중
          </span>
        ) : savedFiles && savedFiles.length > 0 ? (
          <span className="text-[9px] lg:text-[10px] text-gray-500">✓ 완료</span>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {/* 실시간 출력 */}
        {(isRunning || streamingContent) && (
          <div className="border-b border-gray-800">
            <button
              onClick={() => toggleSection('output')}
              className="w-full px-2 lg:px-3 py-1 lg:py-1.5 flex items-center justify-between text-[10px] lg:text-xs font-medium text-gray-400 hover:bg-gray-800/50"
            >
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                터미널
              </span>
              <span className="text-gray-600">{expandedSections.output ? '▼' : '▶'}</span>
            </button>
            {expandedSections.output && streamingContent && (
              <div className="px-2 lg:px-3 pb-2">
                <pre className="font-mono text-[9px] lg:text-[11px] text-gray-300 bg-black/30 p-1.5 lg:p-2 rounded max-h-32 lg:max-h-40 overflow-auto whitespace-pre-wrap leading-relaxed">
                  {streamingContent}
                  {isRunning && <span className="inline-block w-1.5 h-3 bg-green-400 animate-pulse ml-0.5" />}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* 파일 목록 */}
        {savedFiles && savedFiles.length > 0 && (
          <div>
            <button
              onClick={() => toggleSection('files')}
              className="w-full px-2 lg:px-3 py-1 lg:py-1.5 flex items-center justify-between text-[10px] lg:text-xs font-medium text-gray-400 hover:bg-gray-800/50"
            >
              <span className="flex items-center gap-1 lg:gap-2 flex-wrap">
                <span>파일</span>
                <span className="px-1 lg:px-1.5 py-0.5 bg-gray-700 rounded text-[9px] lg:text-[10px]">{savedFiles.length}</span>
                {createdCount > 0 && (
                  <span className="px-1 py-0.5 bg-green-500/20 text-green-400 rounded text-[9px] lg:text-[10px]">+{createdCount}</span>
                )}
                {modifiedCount > 0 && (
                  <span className="px-1 py-0.5 bg-amber-500/20 text-amber-400 rounded text-[9px] lg:text-[10px]">~{modifiedCount}</span>
                )}
              </span>
              <span className="text-gray-600">{expandedSections.files ? '▼' : '▶'}</span>
            </button>
            {expandedSections.files && (
              <div className="px-1.5 lg:px-2 pb-2">
                {/* 프로젝트 경로 */}
                {projectDir && (
                  <div className="px-1.5 lg:px-2 py-1 mb-1 text-[9px] lg:text-[10px] text-gray-500 font-mono truncate border-b border-gray-800">
                    📂 {projectDir}
                  </div>
                )}
                {/* 파일 트리 */}
                <div className="bg-gray-800/30 rounded p-1">
                  {renderFileTree(fileTree)}
                </div>
                {/* ZIP 다운로드 버튼 */}
                {!isRunning && sessionId && (
                  <div className="mt-2 flex gap-1.5">
                    <button
                      onClick={() => apiClient.downloadSessionWorkspace(sessionId, 'zip')}
                      className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-[10px] lg:text-xs rounded transition-colors"
                      title="ZIP으로 다운로드"
                    >
                      <svg className="w-3 h-3 lg:w-3.5 lg:h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                      </svg>
                      <span>ZIP</span>
                    </button>
                    <button
                      onClick={() => apiClient.downloadSessionWorkspace(sessionId, 'tar')}
                      className="flex items-center justify-center gap-1 px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-[10px] lg:text-xs rounded transition-colors"
                      title="TAR로 다운로드"
                    >
                      <svg className="w-3 h-3 lg:w-3.5 lg:h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                      </svg>
                      <span>TAR</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* 에이전트 목록 */}
        {agents.some(a => a.status !== 'pending') && (
          <div className="px-2 lg:px-3 py-1.5 lg:py-2 border-t border-gray-800">
            <div className="text-[9px] lg:text-[10px] text-gray-500 mb-1 lg:mb-1.5">에이전트</div>
            <div className="space-y-0.5 lg:space-y-1">
              {agents.filter(a => a.status !== 'pending').map(agent => (
                <div key={agent.name} className="flex items-center gap-1.5 lg:gap-2 text-[10px] lg:text-[11px]">
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    agent.status === 'running' ? 'bg-blue-500 animate-pulse' :
                    agent.status === 'completed' ? 'bg-green-500' :
                    agent.status === 'error' ? 'bg-red-500' : 'bg-gray-600'
                  }`} />
                  <span className={`flex-1 truncate min-w-0 ${
                    agent.status === 'running' ? 'text-blue-400' :
                    agent.status === 'completed' ? 'text-gray-400' :
                    agent.status === 'error' ? 'text-red-400' : 'text-gray-500'
                  }`}>
                    {getKoreanAgentName(agent.title).replace(/^[\p{Emoji}]\s*/u, '')}
                  </span>
                  {agent.executionTime !== undefined && (
                    <span className="text-gray-600 font-mono text-[9px] lg:text-[10px] flex-shrink-0">{agent.executionTime.toFixed(1)}초</span>
                  )}
                  {agent.tokenUsage?.totalTokens ? (
                    <span className="text-gray-600 font-mono text-[9px] lg:text-[10px] flex-shrink-0 hidden sm:inline">{agent.tokenUsage.totalTokens.toLocaleString()}</span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 하단 통계 */}
      {savedFiles && savedFiles.length > 0 && (
        <div className="px-2 lg:px-3 py-1 lg:py-1.5 bg-gray-800 border-t border-gray-700 flex items-center justify-between text-[9px] lg:text-[10px] text-gray-500">
          <span>{savedFiles.filter(f => f.saved).length}/{savedFiles.length} 저장됨</span>
          {!isRunning && <span className="text-green-500">완료</span>}
        </div>
      )}
    </div>
  );
};

export default WorkflowStatusPanel;
