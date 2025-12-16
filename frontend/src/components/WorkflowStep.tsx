/**
 * WorkflowStep component - Claude.ai inspired workflow step display
 */
import { useState } from 'react';
import { WorkflowUpdate, Artifact, ChecklistItem, CompletedTask } from '../types/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import PromptViewer from './PromptViewer';
import AgentSpawnViewer from './AgentSpawnViewer';
import WorkflowViewer from './WorkflowViewer';

interface WorkflowStepProps {
  update: WorkflowUpdate;
}

interface ArtifactDisplayProps {
  artifact: Artifact;
  defaultExpanded: boolean;
}

const ArtifactDisplay = ({ artifact, defaultExpanded }: ArtifactDisplayProps) => {
  const [artifactExpanded, setArtifactExpanded] = useState(defaultExpanded);

  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-[#E5E5E5] bg-white">
      <div
        className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-[#F5F4F2] transition-colors"
        onClick={() => setArtifactExpanded(!artifactExpanded)}
      >
        <div className="flex items-center gap-3">
          <svg className={`w-4 h-4 text-[#666666] transition-transform ${artifactExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <span className="text-sm font-medium text-[#1A1A1A] font-mono">{artifact.filename}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#999999] uppercase bg-[#F5F4F2] px-2 py-0.5 rounded">{artifact.language}</span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard.writeText(artifact.content);
            }}
            className="text-xs text-[#666666] hover:text-[#1A1A1A] px-2 py-0.5 rounded hover:bg-[#F5F4F2]"
          >
            Copy
          </button>
        </div>
      </div>
      {artifactExpanded && (
        <SyntaxHighlighter
          style={oneDark}
          language={artifact.language}
          customStyle={{ margin: 0, borderRadius: 0, maxHeight: '400px', fontSize: '13px' }}
          showLineNumbers
        >
          {artifact.content}
        </SyntaxHighlighter>
      )}
    </div>
  );
};

const WorkflowStep = ({ update }: WorkflowStepProps) => {
  const [isExpanded, setIsExpanded] = useState(update.status === 'running');

  const getAgentConfig = () => {
    switch (update.agent) {
      case 'Orchestrator':
        return { color: '#7C3AED', bgColor: '#7C3AED10', icon: '', label: 'Orchestrator' };
      case 'PlanningAgent':
        return { color: '#DA7756', bgColor: '#DA775610', icon: '1', label: 'Planning' };
      case 'CodingAgent':
        return { color: '#16A34A', bgColor: '#16A34A10', icon: '2', label: 'Coding' };
      case 'ReviewAgent':
        return { color: '#2563EB', bgColor: '#2563EB10', icon: '3', label: 'Review' };
      case 'FixCodeAgent':
        return { color: '#F59E0B', bgColor: '#F59E0B10', icon: '⟳', label: 'Fix Code' };
      case 'Workflow':
        return { color: '#7C3AED', bgColor: '#7C3AED10', icon: '', label: 'Complete' };
      default:
        return { color: '#666666', bgColor: '#66666610', icon: '', label: update.agent };
    }
  };

  const config = getAgentConfig();

  const getStatusIcon = () => {
    switch (update.status) {
      case 'running':
        return (
          <div className="animate-spin h-5 w-5 border-2 border-t-transparent rounded-full" style={{ borderColor: config.color, borderTopColor: 'transparent' }}></div>
        );
      case 'completed':
        return (
          <svg className="w-5 h-5" style={{ color: config.color }} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      case 'finished':
        return (
          <svg className="w-5 h-5 text-[#16A34A]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z" />
          </svg>
        );
      default:
        return null;
    }
  };

  const getSummaryInfo = (): string => {
    if (update.type === 'workflow_created' && update.workflow_info) {
      const maxIter = update.workflow_info.max_iterations;
      return `${update.workflow_info.workflow_type} (max ${maxIter} iterations)`;
    }
    if (update.type === 'agent_spawn' && update.agent_spawn) {
      return update.agent_spawn.spawn_reason;
    }
    if (update.type === 'decision' && update.decision) {
      const { approved, iteration, max_iterations } = update.decision;
      if (approved) return `APPROVED (iteration ${iteration}/${max_iterations})`;
      if (iteration >= max_iterations) return `Max iterations reached (${iteration}/${max_iterations})`;
      return `NEEDS_REVISION → Fix Code (iteration ${iteration}/${max_iterations})`;
    }
    if (update.type === 'thinking') {
      const iterInfo = update.iteration_info;
      if (iterInfo) return `${update.message} (iteration ${iterInfo.current}/${iterInfo.max})`;
      return update.message || 'Processing...';
    }
    if (update.type === 'task_completed') {
      const taskNum = update.task_result?.task_num || 0;
      const totalTasks = update.checklist?.length || 0;
      return `Task ${taskNum}/${totalTasks} completed`;
    }
    if (update.type === 'artifact' && update.artifact) return `Created: ${update.artifact.filename}`;
    if (update.type === 'completed') {
      if (update.agent === 'PlanningAgent' && update.items) return `${update.items.length} tasks planned`;
      if (update.agent === 'CodingAgent' && update.artifacts) return `${update.artifacts.length} files created`;
      if (update.agent === 'FixCodeAgent' && update.artifacts) return `${update.artifacts.length} files fixed`;
      if (update.agent === 'ReviewAgent') {
        const iterInfo = update.iteration_info;
        const status = update.approved ? 'Approved' : 'Needs revision';
        return iterInfo ? `${status} (iteration ${iterInfo.current}/${iterInfo.max})` : status;
      }
      if (update.agent === 'Workflow' && update.summary) {
        const { tasks_completed, total_tasks, artifacts_count, review_iterations, max_iterations } = update.summary;
        return `${tasks_completed}/${total_tasks} tasks, ${artifacts_count} files (${review_iterations}/${max_iterations} iterations)`;
      }
    }
    if (update.type === 'error') return update.message || 'Error occurred';
    return '';
  };

  const hasExpandableContent = (): boolean => {
    // New types always expandable
    if (update.type === 'workflow_created' && update.workflow_info) return true;
    if (update.type === 'agent_spawn' && update.agent_spawn) return true;
    if (update.type === 'decision' && update.decision) return true;
    // Prompt info makes anything expandable
    if (update.prompt_info) return true;
    // Existing checks
    if (update.type === 'thinking' && update.completed_tasks?.length) return true;
    if (update.type === 'task_completed') return true; // Always expandable for prompt info
    if (update.type === 'artifact' && update.artifact) return true;
    if (update.type === 'completed') {
      if (update.items?.length) return true;
      if (update.artifacts?.length) return true;
      if (update.agent === 'ReviewAgent') return true;
      if (update.agent === 'FixCodeAgent') return true;
      if (update.summary) return true;
    }
    return false;
  };

  const renderChecklist = (items: ChecklistItem[]) => (
    <div className="space-y-2 mt-3">
      {items.map((item) => (
        <div key={item.id} className="flex items-start gap-3 p-2 rounded-lg bg-[#F5F4F2]">
          <div className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center ${item.completed ? 'bg-[#16A34A] text-white' : 'bg-white border border-[#E5E5E5]'}`}>
            {item.completed && (
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            )}
          </div>
          <span className={`text-sm ${item.completed ? 'text-[#1A1A1A]' : 'text-[#666666]'}`}>
            {item.task}
          </span>
        </div>
      ))}
    </div>
  );

  const renderReview = () => (
    <div className="mt-3 space-y-4">
      {update.issues && update.issues.length > 0 && (
        <div className="p-3 rounded-xl bg-red-50 border border-red-100">
          <h4 className="text-sm font-semibold text-red-600 mb-2">Issues ({update.issues.length})</h4>
          <ul className="space-y-1">
            {update.issues.map((issue, i) => (
              <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                <span className="text-red-400 mt-0.5">-</span>
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {update.suggestions && update.suggestions.length > 0 && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-100">
          <h4 className="text-sm font-semibold text-amber-600 mb-2">Suggestions ({update.suggestions.length})</h4>
          <ul className="space-y-1">
            {update.suggestions.map((suggestion, i) => (
              <li key={i} className="text-sm text-amber-700 flex items-start gap-2">
                <span className="text-amber-400 mt-0.5">-</span>
                <span>{suggestion}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
        update.approved ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
      }`}>
        {update.approved ? (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            Approved
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            Needs Revision
          </>
        )}
      </div>
      {update.corrected_artifacts?.map((artifact, i) => (
        <ArtifactDisplay key={i} artifact={artifact} defaultExpanded={false} />
      ))}
    </div>
  );

  const renderCompletedTasks = (tasks: CompletedTask[]) => (
    <div className="space-y-2 mt-3">
      {tasks.map((task) => (
        <div key={task.task_num} className="flex items-start gap-3 p-2 rounded-lg bg-[#F5F4F2]">
          <div className="flex-shrink-0 w-5 h-5 rounded-full bg-[#16A34A] text-white flex items-center justify-center">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <div>
            <span className="text-sm text-[#1A1A1A]">Task {task.task_num}: {task.task}</span>
            {task.artifacts && task.artifacts.length > 0 && (
              <div className="text-xs text-[#999999] mt-0.5">
                {Array.isArray(task.artifacts) && typeof task.artifacts[0] === 'string'
                  ? (task.artifacts as string[]).join(', ')
                  : (task.artifacts as Artifact[]).map(a => a.filename).join(', ')}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );

  const renderSummary = () => (
    <div className="mt-3 grid grid-cols-3 gap-3">
      <div className="bg-white p-4 rounded-xl border border-[#E5E5E5] text-center">
        <div className="text-2xl font-bold text-[#16A34A]">
          {update.summary?.tasks_completed}/{update.summary?.total_tasks}
        </div>
        <div className="text-xs text-[#666666] mt-1">Tasks</div>
      </div>
      <div className="bg-white p-4 rounded-xl border border-[#E5E5E5] text-center">
        <div className="text-2xl font-bold text-[#DA7756]">
          {update.summary?.artifacts_count}
        </div>
        <div className="text-xs text-[#666666] mt-1">Files</div>
      </div>
      <div className="bg-white p-4 rounded-xl border border-[#E5E5E5] text-center">
        <div className={`text-2xl font-bold ${update.summary?.review_approved ? 'text-[#16A34A]' : 'text-amber-500'}`}>
          {update.summary?.review_approved ? 'Pass' : 'Review'}
        </div>
        <div className="text-xs text-[#666666] mt-1">Status</div>
      </div>
    </div>
  );

  const renderDecision = () => {
    if (!update.decision) return null;
    const { approved, iteration, max_iterations, action } = update.decision;

    return (
      <div className={`p-4 rounded-xl border ${approved ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'}`}>
        <div className="flex items-center gap-3 mb-3">
          {approved ? (
            <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full bg-amber-500 flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
            </div>
          )}
          <div>
            <h4 className={`font-semibold ${approved ? 'text-green-700' : 'text-amber-700'}`}>
              {approved ? 'Code Approved' : 'Revision Required'}
            </h4>
            <p className="text-sm text-gray-600">
              Iteration {iteration} of {max_iterations}
            </p>
          </div>
        </div>
        <div className="text-sm">
          <span className="font-medium">Next Action: </span>
          <span className={approved ? 'text-green-600' : 'text-amber-600'}>
            {action === 'end' && 'Complete workflow'}
            {action === 'fix_code' && 'Spawn FixCodeAgent to address issues'}
            {action === 'end_max_iterations' && 'End workflow (max iterations reached)'}
          </span>
        </div>
      </div>
    );
  };

  const renderExpandedContent = () => {
    // Render workflow info for workflow_created type
    if (update.type === 'workflow_created' && update.workflow_info) {
      return <WorkflowViewer workflowInfo={update.workflow_info} />;
    }

    // Render agent spawn info
    if (update.type === 'agent_spawn' && update.agent_spawn) {
      return <AgentSpawnViewer spawnInfo={update.agent_spawn} />;
    }

    // Render decision info
    if (update.type === 'decision' && update.decision) {
      return renderDecision();
    }

    if (update.type === 'thinking') {
      return (
        <div>
          {update.completed_tasks && update.completed_tasks.length > 0 && renderCompletedTasks(update.completed_tasks)}
          <p className="text-[#666666] text-sm italic animate-pulse mt-3">{update.message || 'Processing...'}</p>
        </div>
      );
    }
    if (update.type === 'task_completed') {
      return (
        <div>
          {update.completed_tasks && update.completed_tasks.length > 0 && renderCompletedTasks(update.completed_tasks)}
          {update.task_result?.artifacts && update.task_result.artifacts.length > 0 && (
            <div className="mt-3">
              {update.task_result.artifacts.map((artifact, i) => (
                <ArtifactDisplay key={i} artifact={artifact} defaultExpanded={i === update.task_result!.artifacts.length - 1} />
              ))}
            </div>
          )}
          {/* Show prompt info toggle for task completion */}
          {update.prompt_info && (
            <PromptViewer promptInfo={update.prompt_info} agentName={update.agent} />
          )}
        </div>
      );
    }
    if (update.type === 'artifact' && update.artifact) {
      return (
        <div>
          {update.completed_tasks && update.completed_tasks.length > 0 && renderCompletedTasks(update.completed_tasks)}
          <ArtifactDisplay artifact={update.artifact} defaultExpanded={true} />
        </div>
      );
    }
    if (update.type === 'completed') {
      if (update.agent === 'PlanningAgent' && update.items) {
        return (
          <div>
            {renderChecklist(update.items)}
            {/* Show prompt info for planning completion */}
            {update.prompt_info && (
              <PromptViewer promptInfo={update.prompt_info} agentName={update.agent} />
            )}
          </div>
        );
      }
      if (update.agent === 'CodingAgent' && update.artifacts) {
        return (
          <div>
            {update.checklist && renderChecklist(update.checklist)}
            <div className="mt-4">
              {update.artifacts.map((artifact, i) => (
                <ArtifactDisplay key={i} artifact={artifact} defaultExpanded={false} />
              ))}
            </div>
          </div>
        );
      }
      if (update.agent === 'FixCodeAgent' && update.artifacts) {
        return (
          <div>
            <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-sm text-amber-700">
                <span className="font-medium">Fixes Applied:</span> Code has been modified based on review feedback
              </p>
            </div>
            <div className="space-y-2">
              {update.artifacts.map((artifact, i) => (
                <ArtifactDisplay key={i} artifact={artifact} defaultExpanded={true} />
              ))}
            </div>
            {update.prompt_info && (
              <PromptViewer promptInfo={update.prompt_info} agentName={update.agent} />
            )}
          </div>
        );
      }
      if (update.agent === 'ReviewAgent') {
        return (
          <div>
            {renderReview()}
            {/* Show prompt info for review completion */}
            {update.prompt_info && (
              <PromptViewer promptInfo={update.prompt_info} agentName={update.agent} />
            )}
          </div>
        );
      }
      if (update.agent === 'Workflow' && update.summary) {
        return (
          <div>
            {renderSummary()}
            {/* Show workflow info at the end */}
            {update.workflow_info && (
              <div className="mt-4">
                <WorkflowViewer workflowInfo={update.workflow_info} />
              </div>
            )}
          </div>
        );
      }
    }
    if (update.type === 'error') return <p className="text-red-500 text-sm">{update.message}</p>;
    if (update.content) return <pre className="text-sm text-[#1A1A1A] whitespace-pre-wrap">{update.content}</pre>;
    return null;
  };

  const canExpand = hasExpandableContent();

  return (
    <div className="bg-white rounded-xl border border-[#E5E5E5] overflow-hidden shadow-sm">
      {/* Header */}
      <div
        className={`flex items-center justify-between p-4 ${canExpand ? 'cursor-pointer hover:bg-[#FAFAFA]' : ''}`}
        style={{ backgroundColor: config.bgColor }}
        onClick={() => canExpand && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {/* Step indicator */}
          {config.icon && (
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
              style={{ backgroundColor: config.color }}
            >
              {config.icon}
            </div>
          )}
          {getStatusIcon()}
          <div>
            <h3 className="font-semibold text-[#1A1A1A]">{config.label}</h3>
            {!isExpanded && (
              <p className="text-sm text-[#666666]">{getSummaryInfo()}</p>
            )}
          </div>
        </div>

        {canExpand && (
          <svg
            className={`w-5 h-5 text-[#666666] transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
          </svg>
        )}
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="p-4 border-t border-[#E5E5E5]">
          {renderExpandedContent()}
        </div>
      )}
    </div>
  );
};

export default WorkflowStep;
