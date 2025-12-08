/**
 * WorkflowStep component - displays individual agent step in workflow
 * with expand/collapse functionality for task details
 */
import { useState } from 'react';
import { WorkflowUpdate, Artifact, ChecklistItem, CompletedTask } from '../types/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface WorkflowStepProps {
  update: WorkflowUpdate;
}

const WorkflowStep = ({ update }: WorkflowStepProps) => {
  // Default: expanded when running, collapsed when completed
  const [isExpanded, setIsExpanded] = useState(update.status === 'running');

  const getStatusIcon = () => {
    switch (update.status) {
      case 'running':
        return (
          <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full"></div>
        );
      case 'completed':
        return <span className="text-green-500 text-xl">✓</span>;
      case 'error':
        return <span className="text-red-500 text-xl">✗</span>;
      case 'finished':
        return <span className="text-green-500 text-xl">🎉</span>;
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (update.status) {
      case 'running':
        return 'border-blue-500 bg-blue-500/10';
      case 'completed':
        return 'border-green-500 bg-green-500/10';
      case 'error':
        return 'border-red-500 bg-red-500/10';
      case 'finished':
        return 'border-green-500 bg-green-500/20';
      default:
        return 'border-gray-500 bg-gray-500/10';
    }
  };

  const getAgentColor = () => {
    switch (update.agent) {
      case 'PlanningAgent':
        return 'text-purple-400';
      case 'CodingAgent':
        return 'text-blue-400';
      case 'ReviewAgent':
        return 'text-yellow-400';
      case 'Workflow':
        return 'text-green-400';
      default:
        return 'text-gray-400';
    }
  };

  // Get summary info for collapsed view
  const getSummaryInfo = (): string => {
    if (update.type === 'thinking') {
      return update.message || 'Processing...';
    }
    if (update.type === 'task_completed') {
      const taskNum = update.task_result?.task_num || 0;
      const totalTasks = update.checklist?.length || 0;
      return `Task ${taskNum}/${totalTasks} completed`;
    }
    if (update.type === 'artifact' && update.artifact) {
      return `Created: ${update.artifact.filename}`;
    }
    if (update.type === 'completed') {
      if (update.agent === 'PlanningAgent' && update.items) {
        return `${update.items.length} tasks planned`;
      }
      if (update.agent === 'CodingAgent' && update.artifacts) {
        return `${update.artifacts.length} files created`;
      }
      if (update.agent === 'ReviewAgent') {
        return update.approved ? 'Approved' : 'Needs revision';
      }
      if (update.agent === 'Workflow' && update.summary) {
        return `${update.summary.tasks_completed}/${update.summary.total_tasks} tasks, ${update.summary.artifacts_count} files`;
      }
    }
    if (update.type === 'error') {
      return update.message || 'Error occurred';
    }
    return '';
  };

  // Check if content is expandable
  const hasExpandableContent = (): boolean => {
    if (update.type === 'thinking' && update.completed_tasks && update.completed_tasks.length > 0) return true;
    if (update.type === 'task_completed' && update.task_result?.artifacts?.length) return true;
    if (update.type === 'artifact' && update.artifact) return true;
    if (update.type === 'completed') {
      if (update.items?.length) return true;
      if (update.artifacts?.length) return true;
      if (update.agent === 'ReviewAgent') return true;
      if (update.summary) return true;
    }
    return false;
  };

  const renderChecklist = (items: ChecklistItem[]) => (
    <div className="space-y-2 mt-3">
      {items.map((item) => (
        <div key={item.id} className="flex items-center space-x-3">
          <span className={`text-lg ${item.completed ? 'text-green-500' : 'text-gray-500'}`}>
            {item.completed ? '✓' : '○'}
          </span>
          <span className={item.completed ? 'text-gray-300' : 'text-gray-400'}>
            {item.id}. {item.task}
          </span>
        </div>
      ))}
    </div>
  );

  const renderArtifact = (artifact: Artifact, defaultExpanded: boolean = false) => {
    const [artifactExpanded, setArtifactExpanded] = useState(defaultExpanded);

    return (
      <div className="mt-3 rounded-lg overflow-hidden border border-gray-700">
        <div
          className="bg-gray-900 px-4 py-2 flex items-center justify-between cursor-pointer hover:bg-gray-800"
          onClick={() => setArtifactExpanded(!artifactExpanded)}
        >
          <div className="flex items-center space-x-2">
            <span className="text-gray-400 text-sm">
              {artifactExpanded ? '▼' : '▶'}
            </span>
            <span className="text-sm text-gray-300 font-mono">{artifact.filename}</span>
          </div>
          <span className="text-xs text-gray-500 uppercase">{artifact.language}</span>
        </div>
        {artifactExpanded && (
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={artifact.language}
            customStyle={{ margin: 0, borderRadius: 0, maxHeight: '400px' }}
            showLineNumbers
          >
            {artifact.content}
          </SyntaxHighlighter>
        )}
      </div>
    );
  };

  const renderReview = () => (
    <div className="mt-3 space-y-4">
      {update.issues && update.issues.length > 0 && (
        <div>
          <h4 className="text-red-400 font-semibold mb-2">Issues ({update.issues.length})</h4>
          <ul className="list-disc list-inside text-gray-300 space-y-1">
            {update.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
      {update.suggestions && update.suggestions.length > 0 && (
        <div>
          <h4 className="text-yellow-400 font-semibold mb-2">Suggestions ({update.suggestions.length})</h4>
          <ul className="list-disc list-inside text-gray-300 space-y-1">
            {update.suggestions.map((suggestion, i) => (
              <li key={i}>{suggestion}</li>
            ))}
          </ul>
        </div>
      )}
      <div className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${
        update.approved ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
      }`}>
        {update.approved ? '✓ APPROVED' : '⚠ NEEDS REVISION'}
      </div>
      {update.corrected_artifacts?.map((artifact, i) => (
        <div key={i}>{renderArtifact(artifact, false)}</div>
      ))}
    </div>
  );

  const renderCompletedTasks = (tasks: CompletedTask[]) => (
    <div className="space-y-2 mt-3 border-l-2 border-green-500/30 pl-3">
      {tasks.map((task) => (
        <div key={task.task_num} className="text-sm">
          <div className="flex items-center space-x-2">
            <span className="text-green-500">✓</span>
            <span className="text-gray-300">Task {task.task_num}: {task.task}</span>
          </div>
          {task.artifacts && task.artifacts.length > 0 && (
            <div className="ml-6 text-gray-500">
              → {Array.isArray(task.artifacts) && typeof task.artifacts[0] === 'string'
                  ? (task.artifacts as string[]).join(', ')
                  : (task.artifacts as Artifact[]).map(a => a.filename).join(', ')}
            </div>
          )}
        </div>
      ))}
    </div>
  );

  const renderSummary = () => (
    <div className="mt-3 grid grid-cols-2 gap-4">
      <div className="bg-gray-900 p-3 rounded-lg">
        <div className="text-2xl font-bold text-green-400">
          {update.summary?.tasks_completed}/{update.summary?.total_tasks}
        </div>
        <div className="text-sm text-gray-400">Tasks Completed</div>
      </div>
      <div className="bg-gray-900 p-3 rounded-lg">
        <div className="text-2xl font-bold text-blue-400">
          {update.summary?.artifacts_count}
        </div>
        <div className="text-sm text-gray-400">Files Created</div>
      </div>
      <div className="bg-gray-900 p-3 rounded-lg col-span-2">
        <div className={`text-xl font-bold ${update.summary?.review_approved ? 'text-green-400' : 'text-yellow-400'}`}>
          {update.summary?.review_approved ? '✓ Review Approved' : '⚠ Review Pending'}
        </div>
      </div>
    </div>
  );

  const renderExpandedContent = () => {
    // Thinking state - show message with spinner and completed tasks
    if (update.type === 'thinking') {
      return (
        <div>
          {update.completed_tasks && update.completed_tasks.length > 0 && (
            renderCompletedTasks(update.completed_tasks)
          )}
          <p className="text-gray-400 italic animate-pulse mt-3">
            {update.message || 'Processing...'}
          </p>
        </div>
      );
    }

    // Task completed - show result with artifacts
    if (update.type === 'task_completed') {
      return (
        <div>
          {update.completed_tasks && update.completed_tasks.length > 0 && (
            renderCompletedTasks(update.completed_tasks)
          )}
          {update.task_result?.artifacts && update.task_result.artifacts.length > 0 && (
            <div className="mt-3">
              <p className="text-sm text-gray-400 mb-2">Artifacts created:</p>
              {update.task_result.artifacts.map((artifact, i) => (
                <div key={i}>{renderArtifact(artifact, i === update.task_result!.artifacts.length - 1)}</div>
              ))}
            </div>
          )}
        </div>
      );
    }

    // Artifact created during coding
    if (update.type === 'artifact' && update.artifact) {
      return (
        <div>
          {update.completed_tasks && update.completed_tasks.length > 0 && (
            renderCompletedTasks(update.completed_tasks)
          )}
          <p className="text-gray-300 mb-2">{update.message}</p>
          {renderArtifact(update.artifact, true)}
        </div>
      );
    }

    // Completed states
    if (update.type === 'completed') {
      // Planning completed - show checklist
      if (update.agent === 'PlanningAgent' && update.items) {
        return renderChecklist(update.items);
      }

      // Coding completed - show all artifacts
      if (update.agent === 'CodingAgent' && update.artifacts) {
        return (
          <div>
            {update.checklist && renderChecklist(update.checklist)}
            <div className="mt-4">
              <p className="text-sm text-gray-400 mb-2">All artifacts ({update.artifacts.length}):</p>
              {update.artifacts.map((artifact, i) => (
                <div key={i}>{renderArtifact(artifact, false)}</div>
              ))}
            </div>
          </div>
        );
      }

      // Review completed
      if (update.agent === 'ReviewAgent') {
        return renderReview();
      }

      // Workflow summary
      if (update.agent === 'Workflow' && update.summary) {
        return renderSummary();
      }
    }

    // Error state
    if (update.type === 'error') {
      return <p className="text-red-400">{update.message}</p>;
    }

    // Fallback for legacy content
    if (update.content) {
      return <pre className="text-gray-300 whitespace-pre-wrap">{update.content}</pre>;
    }

    return null;
  };

  const canExpand = hasExpandableContent();

  return (
    <div className={`border-2 rounded-lg p-4 mb-4 ${getStatusColor()}`}>
      {/* Header - always visible */}
      <div
        className={`flex items-center justify-between ${canExpand ? 'cursor-pointer' : ''}`}
        onClick={() => canExpand && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <h3 className={`font-semibold text-lg ${getAgentColor()}`}>
            {update.agent}
          </h3>
          {/* Summary info when collapsed */}
          {!isExpanded && (
            <span className="text-gray-400 text-sm ml-2">
              — {getSummaryInfo()}
            </span>
          )}
        </div>

        {/* Expand/Collapse button */}
        {canExpand && (
          <button
            className="p-1 text-gray-400 hover:text-gray-200 transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`h-5 w-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Expandable content */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-gray-700/50">
          {renderExpandedContent()}
        </div>
      )}
    </div>
  );
};

export default WorkflowStep;
