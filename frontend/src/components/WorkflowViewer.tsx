/**
 * WorkflowViewer component - Visualizes workflow graph and progress
 */
import { useState } from 'react';
import { WorkflowInfo } from '../types/api';

interface WorkflowViewerProps {
  workflowInfo: WorkflowInfo;
}

const WorkflowViewer = ({ workflowInfo }: WorkflowViewerProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getNodeColor = (nodeName: string, isCurrent: boolean) => {
    if (nodeName === 'START') return { bg: '#1A1A1A', text: 'white' };
    if (nodeName === 'END') return { bg: '#16A34A', text: 'white' };
    if (nodeName === 'Decision') return { bg: isCurrent ? '#7C3AED' : '#7C3AED40', text: isCurrent ? 'white' : '#7C3AED' };

    const colors: Record<string, { bg: string; text: string }> = {
      PlanningAgent: { bg: isCurrent ? '#DA7756' : '#DA775640', text: isCurrent ? 'white' : '#DA7756' },
      CodingAgent: { bg: isCurrent ? '#16A34A' : '#16A34A40', text: isCurrent ? 'white' : '#16A34A' },
      ReviewAgent: { bg: isCurrent ? '#2563EB' : '#2563EB40', text: isCurrent ? 'white' : '#2563EB' },
      FixCodeAgent: { bg: isCurrent ? '#F59E0B' : '#F59E0B40', text: isCurrent ? 'white' : '#F59E0B' },
    };

    return colors[nodeName] || { bg: '#66666640', text: '#666666' };
  };

  const isNodeComplete = (nodeName: string) => {
    if (!workflowInfo.current_node) return false;
    const nodeOrder = ['START', ...workflowInfo.nodes, 'END'];
    const currentIdx = nodeOrder.indexOf(workflowInfo.current_node);
    const nodeIdx = nodeOrder.indexOf(nodeName);
    return nodeIdx < currentIdx;
  };

  return (
    <div className="rounded-xl border border-[#7C3AED] bg-[#7C3AED10] overflow-hidden">
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-[#7C3AED15] transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <svg
            className={`w-4 h-4 text-[#7C3AED] transition-transform ${isExpanded ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-[#7C3AED]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
            </svg>
            <span className="font-semibold text-[#7C3AED]">{workflowInfo.workflow_type}</span>
          </div>
        </div>
        <span className="text-xs text-[#7C3AED] bg-white px-2 py-0.5 rounded border border-[#7C3AED40]">
          ID: {workflowInfo.workflow_id}
        </span>
      </div>

      {/* Expanded workflow graph */}
      {isExpanded && (
        <div className="border-t border-[#7C3AED40] p-4 bg-white">
          {/* Visual workflow graph */}
          <div className="flex items-center justify-center gap-2 overflow-x-auto py-4">
            {/* START node */}
            <div className="flex items-center gap-2">
              <div
                className="px-3 py-1.5 rounded-lg text-xs font-medium"
                style={{ backgroundColor: getNodeColor('START', workflowInfo.current_node === 'START').bg, color: getNodeColor('START', workflowInfo.current_node === 'START').text } as React.CSSProperties}
              >
                START
              </div>
              <svg className="w-4 h-4 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </div>

            {/* Agent nodes */}
            {workflowInfo.nodes.map((node, idx) => {
              const isCurrent = workflowInfo.current_node === node;
              const isComplete = isNodeComplete(node);
              const colors = getNodeColor(node, isCurrent);

              return (
                <div key={node} className="flex items-center gap-2">
                  <div
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 ${
                      isCurrent ? 'ring-2 ring-offset-2 ring-[#7C3AED]' : ''
                    }`}
                    style={{ backgroundColor: colors.bg, color: colors.text } as React.CSSProperties}
                  >
                    {isComplete && (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    )}
                    {isCurrent && (
                      <div className="w-2 h-2 rounded-full bg-current animate-pulse" />
                    )}
                    {node}
                  </div>
                  {idx < workflowInfo.nodes.length - 1 && (
                    <svg className="w-4 h-4 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                    </svg>
                  )}
                </div>
              );
            })}

            {/* END node */}
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
              <div
                className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                  workflowInfo.current_node === 'END' ? 'ring-2 ring-offset-2 ring-[#16A34A]' : ''
                }`}
                style={{ backgroundColor: getNodeColor('END', workflowInfo.current_node === 'END').bg, color: getNodeColor('END', workflowInfo.current_node === 'END').text } as React.CSSProperties}
              >
                {workflowInfo.current_node === 'END' && (
                  <svg className="w-3 h-3 inline mr-1" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                )}
                END
              </div>
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center justify-center gap-4 mt-4 pt-4 border-t border-[#E5E5E5] text-xs text-[#666666]">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-[#DA7756]" />
              <span>Planning</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-[#16A34A]" />
              <span>Coding</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-[#2563EB]" />
              <span>Review</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-[#F59E0B]" />
              <span>Fix Code</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-[#7C3AED]" />
              <span>Decision</span>
            </div>
          </div>
          {/* Max iterations info */}
          {workflowInfo.max_iterations && (
            <div className="text-center text-xs text-[#999999] mt-2">
              Max review iterations: {workflowInfo.max_iterations}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default WorkflowViewer;
