/**
 * WorkflowStep component - displays individual agent step in workflow
 */
import { WorkflowUpdate, Artifact, ChecklistItem, CompletedTask } from '../types/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface WorkflowStepProps {
  update: WorkflowUpdate;
}

const WorkflowStep = ({ update }: WorkflowStepProps) => {
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

  const renderArtifact = (artifact: Artifact) => (
    <div className="mt-3 rounded-lg overflow-hidden border border-gray-700">
      <div className="bg-gray-900 px-4 py-2 flex items-center justify-between">
        <span className="text-sm text-gray-300 font-mono">{artifact.filename}</span>
        <span className="text-xs text-gray-500 uppercase">{artifact.language}</span>
      </div>
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={artifact.language}
        customStyle={{ margin: 0, borderRadius: 0 }}
      >
        {artifact.content}
      </SyntaxHighlighter>
    </div>
  );

  const renderReview = () => (
    <div className="mt-3 space-y-4">
      {update.issues && update.issues.length > 0 && (
        <div>
          <h4 className="text-red-400 font-semibold mb-2">Issues</h4>
          <ul className="list-disc list-inside text-gray-300 space-y-1">
            {update.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        </div>
      )}
      {update.suggestions && update.suggestions.length > 0 && (
        <div>
          <h4 className="text-yellow-400 font-semibold mb-2">Suggestions</h4>
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
        <div key={i}>{renderArtifact(artifact)}</div>
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
    </div>
  );

  const renderContent = () => {
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
              <p className="text-sm text-gray-400 mb-2">Latest artifact:</p>
              {renderArtifact(update.task_result.artifacts[update.task_result.artifacts.length - 1])}
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
          {renderArtifact(update.artifact)}
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
            {update.artifacts.map((artifact, i) => (
              <div key={i}>{renderArtifact(artifact)}</div>
            ))}
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

  return (
    <div className={`border-2 rounded-lg p-4 mb-4 ${getStatusColor()}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          {getStatusIcon()}
          <h3 className={`font-semibold text-lg ${getAgentColor()}`}>
            {update.agent}
          </h3>
        </div>
      </div>
      {renderContent()}
    </div>
  );
};

export default WorkflowStep;
