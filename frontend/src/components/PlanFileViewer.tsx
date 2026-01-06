/**
 * PlanFileViewer - Modal component to preview saved plan files
 * Displays markdown plan content with syntax highlighting
 */
import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface PlanFileViewerProps {
  planFilePath: string;
  isOpen: boolean;
  onClose: () => void;
  onStartCodeGeneration?: (planContent: string) => void;
}

const PlanFileViewer = ({
  planFilePath,
  isOpen,
  onClose,
  onStartCodeGeneration,
}: PlanFileViewerProps) => {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load plan file content
  useEffect(() => {
    if (isOpen && planFilePath) {
      loadPlanFile();
    }
  }, [isOpen, planFilePath]);

  const loadPlanFile = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Fetch plan file content from backend
      const response = await fetch(`/api/files/read?path=${encodeURIComponent(planFilePath)}`);

      if (!response.ok) {
        throw new Error(`Failed to load plan file: ${response.statusText}`);
      }

      const data = await response.json();
      setContent(data.content || '');
    } catch (err) {
      console.error('Failed to load plan file:', err);
      setError(err instanceof Error ? err.message : 'Failed to load plan file');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyContent = async () => {
    try {
      await navigator.clipboard.writeText(content);
      // Could add toast notification here
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleStartImplementation = () => {
    if (onStartCodeGeneration) {
      onStartCodeGeneration(content);
    }
    onClose();
  };

  if (!isOpen) return null;

  // Extract filename from path
  const filename = planFilePath.split('/').pop() || 'plan.md';

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <div>
              <h2 className="text-sm font-medium text-gray-100">개발 계획</h2>
              <p className="text-xs text-gray-500 font-mono">{filename}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-40">
              <div className="flex items-center gap-3 text-gray-500">
                <div className="w-5 h-5 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
                <span>계획 파일 로딩 중...</span>
              </div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-40 text-red-400">
              <svg className="w-8 h-8 mb-2" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <p className="text-sm">{error}</p>
              <button
                onClick={loadPlanFile}
                className="mt-3 px-3 py-1.5 text-xs bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
              >
                다시 시도
              </button>
            </div>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none
              prose-headings:text-gray-100 prose-headings:font-semibold
              prose-h1:text-xl prose-h2:text-lg prose-h3:text-base
              prose-p:text-gray-300 prose-p:leading-relaxed
              prose-li:text-gray-300
              prose-code:text-cyan-400 prose-code:bg-gray-800 prose-code:px-1.5 prose-code:rounded
              prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-700
              prose-strong:text-gray-200
              prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
            ">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700 bg-gray-800/50">
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyContent}
              disabled={isLoading || !!error}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors disabled:opacity-50"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
              </svg>
              복사
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs rounded-lg border border-gray-600 hover:bg-gray-800 text-gray-400 transition-colors"
            >
              닫기
            </button>
            {onStartCodeGeneration && (
              <button
                onClick={handleStartImplementation}
                disabled={isLoading || !!error}
                className="flex items-center gap-1.5 px-4 py-1.5 text-xs rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors disabled:opacity-50"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                </svg>
                코드 생성 시작
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlanFileViewer;
