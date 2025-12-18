/**
 * DiffViewer - Visual diff viewer for code changes
 *
 * Displays side-by-side or unified diff view with:
 * - Syntax highlighting
 * - Line-by-line comparison
 * - Change statistics
 * - Approve/Reject actions
 */

import React, { useState } from 'react';

interface CodeDiff {
  file_path: string;
  original_content: string;
  modified_content: string;
  diff_hunks: string[];
  description: string;
}

interface DiffViewerProps {
  diffs: CodeDiff[];
  onApprove?: (message: string) => void;
  onReject?: (message: string) => void;
  showActions?: boolean;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diffs,
  onApprove,
  onReject,
  showActions = true
}) => {
  const [selectedDiffIndex, setSelectedDiffIndex] = useState(0);
  const [viewMode, setViewMode] = useState<'unified' | 'split'>('unified');
  const [approvalMessage, setApprovalMessage] = useState('');

  if (!diffs || diffs.length === 0) {
    return (
      <div className="text-center text-gray-400 p-8">
        No changes to display
      </div>
    );
  }

  const currentDiff = diffs[selectedDiffIndex];

  // Parse diff hunks to extract changes
  const parsedDiff = parseDiffHunks(currentDiff.diff_hunks);

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b p-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-gray-800">
              Code Changes Review
            </h3>
            <p className="text-sm text-gray-600 mt-1">
              {diffs.length} file{diffs.length > 1 ? 's' : ''} modified •{' '}
              {parsedDiff.additions} additions • {parsedDiff.deletions} deletions
            </p>
          </div>

          {/* View Mode Toggle */}
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode('unified')}
              className={`px-3 py-1 rounded text-sm ${
                viewMode === 'unified'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Unified
            </button>
            <button
              onClick={() => setViewMode('split')}
              className={`px-3 py-1 rounded text-sm ${
                viewMode === 'split'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Split
            </button>
          </div>
        </div>
      </div>

      {/* File Tabs */}
      {diffs.length > 1 && (
        <div className="bg-white border-b flex-shrink-0 overflow-x-auto">
          <div className="flex">
            {diffs.map((diff, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedDiffIndex(idx)}
                className={`px-4 py-2 text-sm border-b-2 whitespace-nowrap ${
                  idx === selectedDiffIndex
                    ? 'border-blue-600 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-600 hover:bg-gray-100'
                }`}
              >
                📄 {diff.file_path}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Current File Info */}
      <div className="bg-blue-50 border-b p-3 flex-shrink-0">
        <div className="text-sm">
          <span className="font-semibold">File:</span>{' '}
          <code className="bg-white px-2 py-0.5 rounded">{currentDiff.file_path}</code>
        </div>
        <div className="text-sm mt-1 text-gray-700">
          <span className="font-semibold">Description:</span> {currentDiff.description}
        </div>
      </div>

      {/* Diff Content */}
      <div className="flex-1 overflow-y-auto bg-white">
        {viewMode === 'unified' ? (
          <UnifiedDiffView diff={currentDiff} />
        ) : (
          <SplitDiffView diff={currentDiff} />
        )}
      </div>

      {/* Actions */}
      {showActions && (
        <div className="bg-white border-t p-4 flex-shrink-0">
          <div className="mb-3">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Message (optional):
            </label>
            <input
              type="text"
              value={approvalMessage}
              onChange={(e) => setApprovalMessage(e.target.value)}
              placeholder="Add a comment..."
              className="w-full px-3 py-2 border rounded"
            />
          </div>

          <div className="flex gap-3 justify-end">
            <button
              onClick={() => onReject?.(approvalMessage)}
              className="px-6 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
            >
              ❌ Reject Changes
            </button>
            <button
              onClick={() => onApprove?.(approvalMessage)}
              className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            >
              ✅ Approve & Apply
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Unified diff view component
const UnifiedDiffView: React.FC<{ diff: CodeDiff }> = ({ diff }) => {
  return (
    <div className="font-mono text-sm">
      {diff.diff_hunks.map((line, idx) => {
        const lineType = getLineType(line);
        const bgColor = {
          addition: 'bg-green-50',
          deletion: 'bg-red-50',
          context: 'bg-white',
          header: 'bg-gray-100',
        }[lineType];

        const textColor = {
          addition: 'text-green-800',
          deletion: 'text-red-800',
          context: 'text-gray-800',
          header: 'text-blue-800',
        }[lineType];

        return (
          <div key={idx} className={`${bgColor} ${textColor} px-4 py-1 border-b border-gray-100`}>
            {line || ' '}
          </div>
        );
      })}
    </div>
  );
};

// Split diff view component
const SplitDiffView: React.FC<{ diff: CodeDiff }> = ({ diff }) => {
  const originalLines = diff.original_content.split('\n');
  const modifiedLines = diff.modified_content.split('\n');
  const maxLines = Math.max(originalLines.length, modifiedLines.length);

  return (
    <div className="grid grid-cols-2 divide-x">
      {/* Original */}
      <div>
        <div className="bg-red-100 text-red-800 px-4 py-2 font-semibold text-sm sticky top-0">
          Original
        </div>
        <div className="font-mono text-sm">
          {Array.from({ length: maxLines }).map((_, idx) => (
            <div key={idx} className="px-4 py-1 bg-red-50 border-b border-gray-100">
              <span className="text-gray-400 mr-4">{idx + 1}</span>
              {originalLines[idx] || ''}
            </div>
          ))}
        </div>
      </div>

      {/* Modified */}
      <div>
        <div className="bg-green-100 text-green-800 px-4 py-2 font-semibold text-sm sticky top-0">
          Modified
        </div>
        <div className="font-mono text-sm">
          {Array.from({ length: maxLines }).map((_, idx) => (
            <div key={idx} className="px-4 py-1 bg-green-50 border-b border-gray-100">
              <span className="text-gray-400 mr-4">{idx + 1}</span>
              {modifiedLines[idx] || ''}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Helper functions
function parseDiffHunks(hunks: string[]) {
  let additions = 0;
  let deletions = 0;

  hunks.forEach(line => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      additions++;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      deletions++;
    }
  });

  return { additions, deletions };
}

function getLineType(line: string): 'addition' | 'deletion' | 'context' | 'header' {
  if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@')) {
    return 'header';
  }
  if (line.startsWith('+')) {
    return 'addition';
  }
  if (line.startsWith('-')) {
    return 'deletion';
  }
  return 'context';
}

export default DiffViewer;
