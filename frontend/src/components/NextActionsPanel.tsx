/**
 * NextActionsPanel - Display suggested next actions as clickable buttons
 * Based on UnifiedResponse.next_actions from the Claude Code style API
 */
import { useState } from 'react';

interface NextActionsPanelProps {
  actions: string[];
  onActionClick: (action: string) => void;
  isLoading?: boolean;
  planFile?: string;
  onViewPlan?: () => void;
}

// Action icon mapping
const getActionIcon = (action: string): string => {
  const actionLower = action.toLowerCase();
  if (actionLower.includes('코드') || actionLower.includes('생성') || actionLower.includes('구현')) return '💻';
  if (actionLower.includes('테스트') || actionLower.includes('실행')) return '🧪';
  if (actionLower.includes('리뷰') || actionLower.includes('검토')) return '👀';
  if (actionLower.includes('수정') || actionLower.includes('개선')) return '🔧';
  if (actionLower.includes('질문') || actionLower.includes('추가')) return '❓';
  if (actionLower.includes('계획') || actionLower.includes('파일')) return '📋';
  if (actionLower.includes('적용')) return '✅';
  return '▶';
};

// Action color mapping
const getActionColor = (action: string): string => {
  const actionLower = action.toLowerCase();
  if (actionLower.includes('코드') || actionLower.includes('생성')) return 'bg-blue-600 hover:bg-blue-500';
  if (actionLower.includes('테스트')) return 'bg-green-600 hover:bg-green-500';
  if (actionLower.includes('리뷰') || actionLower.includes('검토')) return 'bg-purple-600 hover:bg-purple-500';
  if (actionLower.includes('수정')) return 'bg-amber-600 hover:bg-amber-500';
  if (actionLower.includes('적용')) return 'bg-emerald-600 hover:bg-emerald-500';
  return 'bg-gray-700 hover:bg-gray-600';
};

const NextActionsPanel = ({
  actions,
  onActionClick,
  isLoading = false,
  planFile,
  onViewPlan,
}: NextActionsPanelProps) => {
  const [hoveredAction, setHoveredAction] = useState<string | null>(null);

  if (actions.length === 0 && !planFile) {
    return null;
  }

  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-3 mt-3">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-medium text-gray-400">다음 행동</span>
        <span className="text-[9px] text-gray-600">클릭하여 실행</span>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        {actions.map((action, index) => (
          <button
            key={`action-${index}`}
            onClick={() => !isLoading && onActionClick(action)}
            onMouseEnter={() => setHoveredAction(action)}
            onMouseLeave={() => setHoveredAction(null)}
            disabled={isLoading}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
              text-white transition-all duration-200
              ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              ${getActionColor(action)}
              ${hoveredAction === action ? 'ring-1 ring-white/30 scale-105' : ''}
            `}
          >
            <span>{getActionIcon(action)}</span>
            <span>{action}</span>
          </button>
        ))}

        {/* Plan File Button */}
        {planFile && onViewPlan && (
          <button
            onClick={onViewPlan}
            disabled={isLoading}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
              text-white transition-all duration-200
              ${isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
              bg-cyan-600 hover:bg-cyan-500
            `}
          >
            <span>📋</span>
            <span>계획 파일 확인</span>
          </button>
        )}
      </div>

      {/* Loading Indicator */}
      {isLoading && (
        <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
          <div className="w-3 h-3 border border-gray-500 border-t-transparent rounded-full animate-spin" />
          <span>처리 중...</span>
        </div>
      )}
    </div>
  );
};

export default NextActionsPanel;
