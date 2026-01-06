/**
 * TerminalOutput - Claude Code 스타일 터미널 출력
 * 워크플로우 업데이트를 CLI 형태로 스트리밍 표시
 */
import { useState } from 'react';
import { WorkflowUpdate, Artifact } from '../types/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface TerminalOutputProps {
  updates: WorkflowUpdate[];
  isRunning: boolean;
  liveOutputs: Map<string, {
    agentName: string;
    agentTitle: string;
    content: string;
    status: string;
    timestamp: number;
  }>;
  savedFiles?: Artifact[];
}

interface ArtifactViewerProps {
  artifact: Artifact;
  compact?: boolean;
}

const ArtifactViewer = ({ artifact, compact = false }: ArtifactViewerProps) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(artifact.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const actionLabel = artifact.action === 'created' ? '생성됨' : artifact.action === 'modified' ? '수정됨' : '';
  const actionColor = artifact.action === 'created' ? 'text-green-400' : artifact.action === 'modified' ? 'text-yellow-400' : '';

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-xs py-0.5">
        <span className={artifact.saved ? 'text-green-400' : 'text-gray-500'}>
          {artifact.saved ? '✓' : '○'}
        </span>
        <span className="font-mono text-gray-300 truncate flex-1">{artifact.filename}</span>
        <span className="text-gray-600">[{artifact.language}]</span>
        {actionLabel && <span className={`text-[10px] ${actionColor}`}>{actionLabel}</span>}
      </div>
    );
  }

  return (
    <div className="my-1 border border-gray-700 rounded overflow-hidden">
      <div
        className="flex items-center justify-between px-2 py-1 bg-gray-800 cursor-pointer hover:bg-gray-700"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 text-xs min-w-0 flex-1">
          <span className={`flex-shrink-0 ${artifact.saved ? 'text-green-400' : 'text-gray-400'}`}>
            {artifact.saved ? '✓' : '○'}
          </span>
          <span className="font-mono text-gray-300 truncate">{artifact.filename}</span>
          <span className="text-gray-600 flex-shrink-0">[{artifact.language}]</span>
          {actionLabel && <span className={`text-[10px] flex-shrink-0 ${actionColor}`}>{actionLabel}</span>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          <button
            onClick={(e) => { e.stopPropagation(); handleCopy(); }}
            className="text-xs text-gray-500 hover:text-gray-300 px-1"
          >
            {copied ? '복사됨!' : '복사'}
          </button>
          <span className="text-gray-600 text-xs">{expanded ? '▼' : '▶'}</span>
        </div>
      </div>
      {expanded && (
        <SyntaxHighlighter
          style={oneDark}
          language={artifact.language}
          customStyle={{ margin: 0, borderRadius: 0, maxHeight: '300px', fontSize: '11px' }}
          showLineNumbers
        >
          {artifact.content}
        </SyntaxHighlighter>
      )}
    </div>
  );
};

// 한글 에이전트 이름 매핑
const agentKoreanNames: Record<string, string> = {
  'supervisor': '감독자',
  'architect': '설계자',
  'coder': '코더',
  'reviewer': '검토자',
  'qa_gate': 'QA 테스터',
  'security_gate': '보안 검사',
  'refiner': '개선자',
  'aggregator': '취합자',
  'hitl': '사용자 검토',
  'persistence': '저장',
  'workflow': '워크플로우',
};

// 한글 상태 메시지
const statusKoreanMessages: Record<string, string> = {
  'running': '실행 중...',
  'starting': '시작 중...',
  'streaming': '스트리밍 중...',
  'thinking': '분석 중...',
  'completed': '완료',
  'error': '오류',
  'awaiting_approval': '승인 대기',
  'pending': '대기 중',
};

const TerminalOutput = ({ updates, isRunning, liveOutputs, savedFiles = [] }: TerminalOutputProps) => {
  // 상태 아이콘
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
      case 'starting':
      case 'streaming':
        return '⋯';
      case 'thinking':
        return '◐';
      case 'completed':
        return '✓';
      case 'error':
        return '✗';
      case 'awaiting_approval':
        return '?';
      default:
        return '·';
    }
  };

  // 상태 색상
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
      case 'starting':
      case 'streaming':
        return 'text-blue-400';
      case 'thinking':
        return 'text-purple-400';
      case 'completed':
        return 'text-green-400';
      case 'error':
        return 'text-red-400';
      case 'awaiting_approval':
        return 'text-yellow-400';
      default:
        return 'text-gray-500';
    }
  };

  // 에이전트 이름 포맷 (한글)
  const formatAgentName = (name: string) => {
    const cleanName = name.replace(/Agent$/, '').toLowerCase();
    return agentKoreanNames[cleanName] || cleanName;
  };

  // 라이브 출력 정렬
  const sortedLiveOutputs = Array.from(liveOutputs.values())
    .sort((a, b) => a.timestamp - b.timestamp);

  // 생성된 파일 수
  const createdCount = savedFiles.filter(f => f.action === 'created').length;
  const modifiedCount = savedFiles.filter(f => f.action === 'modified').length;

  return (
    <div className="font-mono text-xs bg-gray-950 text-gray-300 p-2 sm:p-3 rounded-lg border border-gray-800 min-h-[150px] sm:min-h-[200px] max-h-[50vh] sm:max-h-[60vh] overflow-y-auto">
      {/* 터미널 프롬프트 헤더 */}
      <div className="text-gray-600 mb-2 text-[10px] sm:text-xs">
        $ workflow execute --stream
      </div>

      {/* 출력 없음 */}
      {updates.length === 0 && !isRunning && (
        <div className="text-gray-600 italic">
          출력 없음. 작업을 입력하여 시작하세요.
        </div>
      )}

      {/* 실시간 파일 목록 - 워크플로우 실행 중 표시 */}
      {isRunning && savedFiles.length > 0 && (
        <div className="mb-3 border border-gray-800 rounded p-2 bg-gray-900/50">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-green-400">📁</span>
            <span className="text-gray-400">생성된 파일</span>
            <span className="px-1.5 py-0.5 bg-gray-700 rounded text-[10px]">{savedFiles.length}</span>
            {createdCount > 0 && (
              <span className="px-1 py-0.5 bg-green-500/20 text-green-400 rounded text-[10px]">+{createdCount} 생성</span>
            )}
            {modifiedCount > 0 && (
              <span className="px-1 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-[10px]">{modifiedCount} 수정</span>
            )}
          </div>
          <div className="max-h-32 overflow-y-auto space-y-0.5">
            {savedFiles.map((file, i) => (
              <ArtifactViewer key={`${file.filename}-${i}`} artifact={file} compact />
            ))}
          </div>
        </div>
      )}

      {/* 라이브 스트리밍 출력 */}
      {isRunning && sortedLiveOutputs.length > 0 && (
        <div className="space-y-2">
          {sortedLiveOutputs.map((output) => (
            <div key={output.agentName} className="border-l-2 border-gray-800 pl-2">
              {/* 에이전트 헤더 */}
              <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                <span className={`${getStatusColor(output.status)}`}>
                  {getStatusIcon(output.status)}
                </span>
                <span className="text-gray-500">[{formatAgentName(output.agentName)}]</span>
                <span className="text-gray-400 text-[10px] sm:text-xs truncate max-w-[150px] sm:max-w-none">
                  {statusKoreanMessages[output.status] || output.agentTitle}
                </span>
                {(output.status === 'running' || output.status === 'streaming') && (
                  <span className="animate-pulse text-blue-400">●</span>
                )}
              </div>
              {/* 에이전트 출력 내용 */}
              {output.content && (
                <pre className="text-gray-400 whitespace-pre-wrap ml-2 sm:ml-4 mt-1 text-[10px] sm:text-xs overflow-x-auto">
                  {output.content.split('\n').map((line, i) => (
                    <div key={i} className="leading-relaxed">
                      {line.startsWith('✅') || line.startsWith('✓') ? (
                        <span className="text-green-400">{line}</span>
                      ) : line.startsWith('❌') || line.startsWith('⚠️') ? (
                        <span className="text-red-400">{line}</span>
                      ) : line.startsWith('$') || line.startsWith('>') ? (
                        <span className="text-blue-400">{line}</span>
                      ) : (
                        line
                      )}
                    </div>
                  ))}
                  {(output.status === 'running' || output.status === 'streaming') && (
                    <span className="inline-block w-1.5 h-3 bg-gray-400 animate-pulse" />
                  )}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 완료된 업데이트 - 로그 형태 */}
      {!isRunning && updates.length > 0 && (
        <div className="space-y-2 sm:space-y-3">
          {updates.map((update, index) => (
            <div key={`${update.agent}-${index}`} className="border-l-2 border-gray-800 pl-2">
              {/* 에이전트 헤더 */}
              <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                <span className={`${getStatusColor(update.status || 'completed')}`}>
                  {getStatusIcon(update.status || 'completed')}
                </span>
                <span className="text-gray-500">[{formatAgentName(update.agent)}]</span>
                <span className="text-gray-400 text-[10px] sm:text-xs truncate max-w-[200px] sm:max-w-none">
                  {update.message || update.agent}
                </span>
                {update.execution_time !== undefined && (
                  <span className="text-gray-600 ml-auto text-[10px] sm:text-xs">{update.execution_time.toFixed(1)}초</span>
                )}
              </div>

              {/* 스트리밍 콘텐츠 */}
              {update.streaming_content && (
                <div className="relative group ml-2 sm:ml-4 mt-1">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(update.streaming_content || '');
                      const btn = document.getElementById(`copy-content-${index}`);
                      if (btn) {
                        btn.textContent = '✓';
                        setTimeout(() => { btn.textContent = '복사'; }, 1500);
                      }
                    }}
                    id={`copy-content-${index}`}
                    className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 px-1.5 py-0.5 text-[9px] sm:text-[10px] bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-gray-200 rounded transition-all z-10"
                    title="콘텐츠 복사"
                  >
                    복사
                  </button>
                  <pre className="text-gray-500 whitespace-pre-wrap text-[9px] sm:text-[10px] overflow-x-auto max-h-40 overflow-y-auto pr-10">
                    {update.streaming_content}
                  </pre>
                </div>
              )}

              {/* Artifacts */}
              {update.artifacts && update.artifacts.length > 0 && (
                <div className="ml-2 sm:ml-4 mt-1">
                  <div className="text-gray-600 mb-1 text-[10px] sm:text-xs">파일 ({update.artifacts.length}):</div>
                  <div className="space-y-1">
                    {update.artifacts.map((artifact, i) => (
                      <ArtifactViewer key={i} artifact={artifact} />
                    ))}
                  </div>
                </div>
              )}

              {/* 단일 artifact */}
              {update.artifact && (
                <div className="ml-2 sm:ml-4 mt-1">
                  <ArtifactViewer artifact={update.artifact} />
                </div>
              )}

              {/* 이슈 */}
              {update.issues && update.issues.length > 0 && (
                <div className="ml-2 sm:ml-4 mt-1 text-red-400 text-[10px] sm:text-xs">
                  {update.issues.map((issue, i) => (
                    <div key={i}>! {typeof issue === 'string' ? issue : issue.issue}</div>
                  ))}
                </div>
              )}

              {/* 제안사항 */}
              {update.suggestions && update.suggestions.length > 0 && (
                <div className="ml-2 sm:ml-4 mt-1 text-yellow-400 text-[10px] sm:text-xs">
                  {update.suggestions.map((sug, i) => (
                    <div key={i}>* {typeof sug === 'string' ? sug : sug.suggestion}</div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* 워크플로우 완료 표시 */}
          <div className="text-green-400 mt-2">
            ✓ 워크플로우 완료
          </div>
        </div>
      )}

      {/* 실행 중 표시 */}
      {isRunning && (
        <div className="mt-3 flex items-center gap-2 text-gray-500">
          <span className="animate-spin">⟳</span>
          <span>실행 중...</span>
        </div>
      )}
    </div>
  );
};

export default TerminalOutput;
