/**
 * TerminalOutput - Claude Code 스타일 터미널 출력
 * 워크플로우 업데이트를 CLI 형태로 스트리밍 표시
 */
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { WorkflowUpdate, Artifact } from '../types/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import FileTreeViewer from './FileTreeViewer';

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
  onDownloadZip?: () => void;
  isDownloadingZip?: boolean;
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
  // Unified handlers
  'planninghandler': '계획 수립',
  'planning': '계획 수립',
  'planningagent': '계획 수립',
  'codegenerationhandler': '코드 생성',
  'codegeneration': '코드 생성',
  'codingagent': '코드 생성',
  'reviewagent': '코드 검토',
  'fixcodeagent': '코드 수정',
  'quickqahandler': '빠른 응답',
  'quickqa': '빠른 응답',
  'unifiedagentmanager': '통합 관리',
  'orchestrator': '오케스트레이터',
  'chatassistant': '채팅 어시스턴트',
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

// 에이전트별 상세 상태 메시지
const getAgentStatusMessage = (agentName: string, status: string): string => {
  const agent = agentName.replace(/Agent$/, '').replace(/Handler$/, '').toLowerCase();

  if (status === 'running' || status === 'streaming') {
    switch (agent) {
      case 'supervisor':
      case 'unifiedagentmanager':
        return '요청을 분석하고 최적의 처리 방법을 결정하고 있습니다...';
      case 'planning':
      case 'planninghandler':
        return '개발 계획을 수립하고 있습니다...';
      case 'codegeneration':
      case 'codegenerationhandler':
      case 'coding':
        return '코드를 생성하고 있습니다...';
      case 'architect':
        return '시스템 아키텍처를 설계하고 있습니다...';
      case 'coder':
        return '코드를 작성하고 있습니다...';
      case 'review':
      case 'reviewer':
        return '코드를 검토하고 있습니다...';
      case 'fixcode':
        return '코드를 수정하고 있습니다...';
      case 'quickqa':
      case 'quickqahandler':
        return '질문에 답변을 생성하고 있습니다...';
      case 'refiner':
        return '코드를 개선하고 있습니다...';
      case 'orchestrator':
        return '워크플로우를 조율하고 있습니다...';
      default:
        return statusKoreanMessages[status] || '처리 중...';
    }
  }

  if (status === 'completed') {
    switch (agent) {
      case 'supervisor':
      case 'unifiedagentmanager':
        return '분석 완료';
      case 'planning':
      case 'planninghandler':
        return '계획 수립 완료';
      case 'codegeneration':
      case 'codegenerationhandler':
      case 'coding':
        return '코드 생성 완료';
      case 'coder':
        return '코드 작성 완료';
      case 'review':
      case 'reviewer':
        return '코드 검토 완료';
      case 'fixcode':
        return '코드 수정 완료';
      default:
        return '완료';
    }
  }

  return statusKoreanMessages[status] || status;
};

const TerminalOutput = ({ updates, isRunning, liveOutputs, savedFiles = [], onDownloadZip, isDownloadingZip }: TerminalOutputProps) => {
  const [showAllUpdates, setShowAllUpdates] = useState(false);

  // Filter updates to show only significant ones (hide progress/streaming noise)
  const filteredUpdates = updates.filter(update => {
    // Always show completed, error, artifact-related, and decision updates
    if (update.status === 'completed' || update.status === 'error' || update.status === 'finished') return true;
    if ((update.artifacts && update.artifacts.length > 0) || update.artifact) return true;
    if (update.type === 'artifact' || update.type === 'decision' || update.type === 'analysis') return true;
    if (update.type === 'mode_selection' || update.type === 'approved') return true;
    // Hide streaming/thinking/progress updates unless showAllUpdates is enabled
    if (update.type === 'thinking' || update.type === 'progress' || update.type === 'streaming') return showAllUpdates;
    // Show other updates by default
    return true;
  });

  // Count hidden updates
  const hiddenCount = updates.length - filteredUpdates.length;

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

      {/* 파일 트리 뷰어 - 워크플로우 실행 중/완료 후 표시 */}
      {savedFiles.length > 0 && (
        <div className="mb-3">
          <FileTreeViewer
            files={savedFiles}
            onDownloadZip={onDownloadZip}
            isDownloading={isDownloadingZip}
          />
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
                  {getAgentStatusMessage(output.agentName, output.status)}
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
          {/* Toggle for showing all updates */}
          {hiddenCount > 0 && (
            <button
              onClick={() => setShowAllUpdates(!showAllUpdates)}
              className="text-[10px] text-gray-500 hover:text-gray-300 underline"
            >
              {showAllUpdates ? `진행 상황 숨기기 (${hiddenCount}개)` : `모든 진행 상황 보기 (+${hiddenCount}개)`}
            </button>
          )}
          {filteredUpdates.map((update, index) => (
            <div key={`${update.agent}-${index}`} className="border-l-2 border-gray-800 pl-2">
              {/* 에이전트 헤더 */}
              <div className="flex items-start gap-1 sm:gap-2 flex-wrap">
                <span className={`${getStatusColor(update.status || 'completed')} mt-0.5`}>
                  {getStatusIcon(update.status || 'completed')}
                </span>
                <span className="text-gray-500 mt-0.5">[{formatAgentName(update.agent)}]</span>
                <div className="text-gray-300 text-[10px] sm:text-xs flex-1 min-w-0 prose prose-sm prose-invert max-w-none
                  prose-headings:text-gray-200 prose-headings:font-semibold prose-headings:mt-2 prose-headings:mb-1 prose-headings:text-xs
                  prose-p:text-gray-300 prose-p:my-0.5 prose-p:text-[10px] sm:prose-p:text-xs
                  prose-li:text-gray-300 prose-li:my-0 prose-li:text-[10px] sm:prose-li:text-xs
                  prose-ul:my-1 prose-ol:my-1 prose-ul:pl-4 prose-ol:pl-4
                  prose-code:text-cyan-400 prose-code:bg-gray-800 prose-code:px-1 prose-code:rounded prose-code:text-[10px]
                  prose-strong:text-gray-200 prose-em:text-gray-300">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code(props) {
                        const { children, className, ...rest } = props;
                        const match = /language-(\w+)/.exec(className || '');
                        return match ? (
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            customStyle={{
                              borderRadius: '6px',
                              padding: '8px',
                              margin: '4px 0',
                              fontSize: '10px',
                            }}
                          >
                            {String(children).replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        ) : (
                          <code className={`${className || ''} bg-gray-800 px-1 py-0.5 rounded text-cyan-400 text-[10px]`} {...rest}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {update.message || update.agent}
                  </ReactMarkdown>
                </div>
                {update.execution_time !== undefined && (
                  <span className="text-gray-600 ml-auto text-[10px] sm:text-xs mt-0.5">{update.execution_time.toFixed(1)}초</span>
                )}
              </div>

              {/* 스트리밍 콘텐츠 - Markdown 렌더링 (카드 스타일) */}
              {update.streaming_content && (
                <div className="relative group ml-2 sm:ml-4 mt-2 mb-2">
                  {/* Output 카드 컨테이너 */}
                  <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg overflow-hidden">
                    {/* 헤더 */}
                    <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800/80 border-b border-gray-700/50">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-cyan-400 font-medium">📄 Output</span>
                        <span className="text-[9px] text-gray-500">{formatAgentName(update.agent)}</span>
                      </div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(update.streaming_content || '');
                          const btn = document.getElementById(`copy-content-${index}`);
                          if (btn) {
                            btn.textContent = '✓ 복사됨';
                            setTimeout(() => { btn.textContent = '복사'; }, 1500);
                          }
                        }}
                        id={`copy-content-${index}`}
                        className="px-2 py-0.5 text-[9px] sm:text-[10px] bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-gray-200 rounded transition-all"
                        title="콘텐츠 복사"
                      >
                        복사
                      </button>
                    </div>
                    {/* 콘텐츠 */}
                    <div className="p-3 text-gray-300 text-[10px] sm:text-xs overflow-x-auto max-h-80 overflow-y-auto prose prose-sm prose-invert max-w-none
                      prose-headings:text-gray-200 prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-2 prose-headings:text-sm
                      prose-h2:text-cyan-400 prose-h2:border-b prose-h2:border-gray-700 prose-h2:pb-1
                      prose-p:text-gray-300 prose-p:my-1.5 prose-p:text-[11px] prose-p:leading-relaxed
                      prose-li:text-gray-300 prose-li:my-0.5 prose-li:text-[11px]
                      prose-ul:my-2 prose-ol:my-2 prose-ul:pl-4 prose-ol:pl-4
                      prose-code:text-cyan-400 prose-code:bg-gray-900 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[10px]
                      prose-strong:text-white prose-em:text-gray-300
                      prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code(props) {
                            const { children, className, ...rest } = props;
                            const match = /language-(\w+)/.exec(className || '');
                            return match ? (
                              <SyntaxHighlighter
                                style={oneDark}
                                language={match[1]}
                                PreTag="div"
                                customStyle={{
                                  borderRadius: '8px',
                                  padding: '12px',
                                  margin: '8px 0',
                                  fontSize: '11px',
                                  border: '1px solid rgba(75, 85, 99, 0.5)',
                                }}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={`${className || ''} bg-gray-900 px-1.5 py-0.5 rounded text-cyan-400 text-[10px]`} {...rest}>
                                {children}
                              </code>
                            );
                          },
                        }}
                      >
                        {update.streaming_content}
                      </ReactMarkdown>
                    </div>
                  </div>
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
