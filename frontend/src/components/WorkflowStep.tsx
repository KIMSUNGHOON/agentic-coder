/**
 * WorkflowStep component - Claude.ai inspired workflow step display
 */
import { useState, useEffect } from 'react';
import { WorkflowUpdate, Artifact, ChecklistItem, CompletedTask } from '../types/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import PromptViewer from './PromptViewer';
import AgentSpawnViewer from './AgentSpawnViewer';
import WorkflowViewer from './WorkflowViewer';
import apiClient from '../api/client';

interface WorkflowStepProps {
  update: WorkflowUpdate;
}

interface ArtifactDisplayProps {
  artifact: Artifact;
  defaultExpanded: boolean;
}

interface ExecutionResult {
  success: boolean;
  stdout?: string;
  stderr?: string;
  error?: string;
}

const ArtifactDisplay = ({ artifact, defaultExpanded }: ArtifactDisplayProps) => {
  const [artifactExpanded, setArtifactExpanded] = useState(defaultExpanded);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [executeStatus, setExecuteStatus] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [savePath, setSavePath] = useState(`./output/${artifact.filename}`);

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      const result = await apiClient.saveFile(savePath, artifact.content);
      if (result.success) {
        setSaveStatus('saved');
        setShowSaveDialog(false);
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        setSaveStatus('error');
        alert(`Save failed: ${result.error}`);
      }
    } catch (err) {
      setSaveStatus('error');
      alert(`Save failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleExecute = async () => {
    if (artifact.language !== 'python' && artifact.language !== 'py') {
      alert('Only Python files can be executed directly.');
      return;
    }

    setExecuteStatus('running');
    setExecutionResult(null);

    try {
      const result = await apiClient.executePython(artifact.content, 30);
      setExecutionResult({
        success: result.success,
        stdout: result.output?.stdout,
        stderr: result.output?.stderr,
        error: result.error
      });
      setExecuteStatus(result.success ? 'done' : 'error');
    } catch (err) {
      setExecutionResult({
        success: false,
        error: err instanceof Error ? err.message : 'Unknown error'
      });
      setExecuteStatus('error');
    }
  };

  const isPython = artifact.language === 'python' || artifact.language === 'py';

  return (
    <div className="mt-3 rounded-xl overflow-hidden border border-[#E5E5E5] bg-white">
      <div
        className="px-4 py-3 cursor-pointer hover:bg-[#F5F4F2] transition-colors"
        onClick={() => setArtifactExpanded(!artifactExpanded)}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3 flex-1">
            <svg className={`w-4 h-4 text-[#666666] transition-transform ${artifactExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            </svg>
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-[#1A1A1A] font-mono">{artifact.filename}</span>
                <span className="text-xs text-[#999999] uppercase bg-[#F5F4F2] px-2 py-0.5 rounded">{artifact.language}</span>
                {/* File save status indicator */}
                {artifact.saved !== undefined && (
                  artifact.saved ? (
                    <span className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded border border-green-200">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                      Saved
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-red-700 bg-red-100 px-2 py-0.5 rounded border border-red-200">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                      Save Failed
                    </span>
                  )
                )}
              </div>
              {/* File description if available */}
              {artifact.description && (
                <p className="text-xs text-[#666666] mt-1 italic">{artifact.description}</p>
              )}
              {/* Saved path if available */}
              {artifact.saved && artifact.saved_path && (
                <p className="text-xs text-green-600 mt-1 font-mono">📁 {artifact.saved_path}</p>
              )}
              {/* Error message if save failed */}
              {artifact.saved === false && artifact.error && (
                <p className="text-xs text-red-600 mt-1">⚠️ {artifact.error}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-3 flex-shrink-0">
            {/* Copy Button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(artifact.content);
              }}
              className="text-xs text-[#666666] hover:text-[#1A1A1A] px-2 py-0.5 rounded hover:bg-[#F5F4F2]"
            >
              Copy
            </button>

            {/* Save Button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowSaveDialog(true);
              }}
              disabled={saveStatus === 'saving'}
              className={`text-xs px-2 py-0.5 rounded flex items-center gap-1 ${
                saveStatus === 'saved' ? 'text-green-600 bg-green-50' :
                saveStatus === 'saving' ? 'text-blue-600 bg-blue-50' :
                saveStatus === 'error' ? 'text-red-600 bg-red-50' :
                'text-[#666666] hover:text-[#1A1A1A] hover:bg-[#F5F4F2]'
              }`}
            >
              {saveStatus === 'saving' && (
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
              {saveStatus === 'saved' ? '✓ Saved' : saveStatus === 'saving' ? 'Saving...' : 'Save'}
            </button>

            {/* Execute Button (Python only) */}
            {isPython && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleExecute();
                }}
                disabled={executeStatus === 'running'}
                className={`text-xs px-2 py-0.5 rounded flex items-center gap-1 ${
                  executeStatus === 'done' ? 'text-green-600 bg-green-50' :
                  executeStatus === 'running' ? 'text-blue-600 bg-blue-50' :
                  executeStatus === 'error' ? 'text-red-600 bg-red-50' :
                  'text-[#16A34A] hover:text-[#15803D] hover:bg-green-50'
                }`}
              >
                {executeStatus === 'running' && (
                  <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                )}
                {executeStatus === 'running' ? 'Running...' : '▶ Run'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="px-4 py-3 bg-blue-50 border-t border-blue-100" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center gap-2">
            <label className="text-xs text-blue-700 font-medium">Save to:</label>
            <input
              type="text"
              value={savePath}
              onChange={(e) => setSavePath(e.target.value)}
              className="flex-1 text-xs px-2 py-1 border border-blue-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-400"
              placeholder="./output/filename.py"
            />
            <button
              onClick={handleSave}
              disabled={saveStatus === 'saving'}
              className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={() => setShowSaveDialog(false)}
              className="text-xs px-2 py-1 text-blue-600 hover:bg-blue-100 rounded"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Code Display */}
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

      {/* Execution Result */}
      {executionResult && (
        <div className={`px-4 py-3 border-t ${executionResult.success ? 'bg-green-50 border-green-100' : 'bg-red-50 border-red-100'}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-xs font-medium ${executionResult.success ? 'text-green-700' : 'text-red-700'}`}>
              {executionResult.success ? '✓ Execution Successful' : '✗ Execution Failed'}
            </span>
            <button
              onClick={() => setExecutionResult(null)}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              ✕ Close
            </button>
          </div>
          {executionResult.stdout && (
            <div className="mb-2">
              <div className="text-xs text-gray-500 mb-1">Output:</div>
              <pre className="text-xs bg-gray-900 text-green-400 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto">
                {executionResult.stdout}
              </pre>
            </div>
          )}
          {executionResult.stderr && (
            <div>
              <div className="text-xs text-gray-500 mb-1">Errors:</div>
              <pre className="text-xs bg-gray-900 text-red-400 p-2 rounded overflow-x-auto max-h-48 overflow-y-auto">
                {executionResult.stderr}
              </pre>
            </div>
          )}
          {executionResult.error && !executionResult.stderr && (
            <div className="text-xs text-red-600">{executionResult.error}</div>
          )}
        </div>
      )}
    </div>
  );
};

const WorkflowStep = ({ update }: WorkflowStepProps) => {
  const [isExpanded, setIsExpanded] = useState(update.status === 'running');

  // Auto-expand when running, auto-collapse when completed (unless important content)
  useEffect(() => {
    if (update.status === 'running') {
      // Always expand when running to show what's happening
      setIsExpanded(true);
    } else if (update.status === 'completed' || update.status === 'finished') {
      // Keep expanded if there's important content to show
      const hasImportantContent =
        update.artifacts?.length ||
        update.issues?.length ||
        update.suggestions?.length ||
        update.items?.length ||
        update.content;

      if (!hasImportantContent) {
        setIsExpanded(false);
      }
    }
  }, [update.status, update.artifacts, update.issues, update.suggestions, update.items, update.content]);

  const getAgentConfig = () => {
    // Use custom label if provided in update
    const customLabel = update.agent_label || update.task_description;

    // Determine agent type from name or fall back to analyzing content
    const agentType = update.agent;

    // If custom label is provided, use task-based naming
    if (customLabel) {
      // Determine color based on task type keywords
      if (customLabel.toLowerCase().includes('plan') || customLabel.toLowerCase().includes('analyz')) {
        return { color: '#DA7756', bgColor: '#DA775610', icon: '📋', label: customLabel };
      } else if (customLabel.toLowerCase().includes('code') || customLabel.toLowerCase().includes('implement') || customLabel.toLowerCase().includes('creat')) {
        return { color: '#16A34A', bgColor: '#16A34A10', icon: '💻', label: customLabel };
      } else if (customLabel.toLowerCase().includes('review') || customLabel.toLowerCase().includes('check')) {
        return { color: '#2563EB', bgColor: '#2563EB10', icon: '🔍', label: customLabel };
      } else if (customLabel.toLowerCase().includes('fix') || customLabel.toLowerCase().includes('debug')) {
        return { color: '#F59E0B', bgColor: '#F59E0B10', icon: '🔧', label: customLabel };
      } else if (customLabel.toLowerCase().includes('test')) {
        return { color: '#06B6D4', bgColor: '#06B6D410', icon: '🧪', label: customLabel };
      } else if (customLabel.toLowerCase().includes('doc')) {
        return { color: '#6366F1', bgColor: '#6366F110', icon: '📝', label: customLabel };
      }
      // Default for custom labels
      return { color: '#666666', bgColor: '#66666610', icon: '⚙️', label: customLabel };
    }

    // Fall back to agent type-based naming
    switch (agentType) {
      // Orchestration agents
      case 'SupervisorAgent':
        return { color: '#9333EA', bgColor: '#9333EA10', icon: '🎯', label: 'Task Analysis' };
      case 'Orchestrator':
        return { color: '#7C3AED', bgColor: '#7C3AED10', icon: '🎼', label: 'Orchestrator' };
      // Planning/Analysis agents
      case 'PlanningAgent':
        return { color: '#DA7756', bgColor: '#DA775610', icon: '📋', label: 'Planning Tasks' };
      case 'AnalysisAgent':
        return { color: '#EC4899', bgColor: '#EC489910', icon: '🔍', label: 'Code Analysis' };
      // Coding agents - use generic task-based names
      case 'CodingAgent':
        // Try to get more specific name from content
        const taskCount = update.items?.length || update.artifacts?.length || 0;
        if (taskCount > 1) {
          return { color: '#16A34A', bgColor: '#16A34A10', icon: '💻', label: `Implementing ${taskCount} Tasks` };
        }
        return { color: '#16A34A', bgColor: '#16A34A10', icon: '💻', label: 'Code Implementation' };
      case 'RefactorAgent':
        return { color: '#14B8A6', bgColor: '#14B8A610', icon: '♻️', label: 'Code Refactoring' };
      case 'DebugAgent':
        return { color: '#EF4444', bgColor: '#EF444410', icon: '🐛', label: 'Debugging' };
      // Review/Fix agents
      case 'ReviewAgent':
        return { color: '#2563EB', bgColor: '#2563EB10', icon: '🔍', label: 'Code Review' };
      case 'FixCodeAgent':
        return { color: '#F59E0B', bgColor: '#F59E0B10', icon: '🔧', label: 'Applying Fixes' };
      // Test/Validation agents
      case 'TestGenAgent':
        return { color: '#06B6D4', bgColor: '#06B6D410', icon: '🧪', label: 'Generating Tests' };
      case 'TestAgent':
        return { color: '#06B6D4', bgColor: '#06B6D410', icon: '✅', label: 'Running Tests' };
      case 'ValidationAgent':
        return { color: '#8B5CF6', bgColor: '#8B5CF610', icon: '✅', label: 'Validation' };
      // Documentation agents
      case 'DocGenAgent':
        return { color: '#6366F1', bgColor: '#6366F110', icon: '📝', label: 'Writing Documentation' };
      case 'SuggestionAgent':
        return { color: '#F97316', bgColor: '#F9731610', icon: '💡', label: 'Suggestions' };
      // Workflow completion
      case 'Workflow':
        return { color: '#7C3AED', bgColor: '#7C3AED10', icon: '✨', label: 'Workflow Complete' };
      // Generic agent - use agent name as-is but make it readable
      default:
        const readableName = agentType.replace(/Agent$/, '').replace(/([A-Z])/g, ' $1').trim();
        return { color: '#666666', bgColor: '#66666610', icon: '⚙️', label: readableName || 'Agent Task' };
    }
  };

  const config = getAgentConfig();

  const getStatusIcon = () => {
    switch (update.status) {
      case 'running':
      case 'starting':
      case 'streaming':
        return (
          <div className="animate-spin h-5 w-5 border-2 border-t-transparent rounded-full" style={{ borderColor: config.color, borderTopColor: 'transparent' }}></div>
        );
      case 'thinking':
        return (
          <div className="relative h-5 w-5">
            <div className="animate-pulse h-5 w-5 rounded-full bg-purple-500 opacity-75"></div>
            <svg className="absolute inset-0 w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          </div>
        );
      case 'awaiting_approval':
        return (
          <div className="h-5 w-5 rounded-full bg-amber-500 flex items-center justify-center animate-pulse">
            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
            </svg>
          </div>
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
      const { workflow_type, task_type, dynamically_created, max_iterations } = update.workflow_info;
      const dynamicLabel = dynamically_created ? ' (dynamic)' : '';
      const iterLabel = max_iterations ? ` [max ${max_iterations} iter]` : '';
      return `${workflow_type}${task_type ? ` [${task_type}]` : ''}${iterLabel}${dynamicLabel}`;
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
      // SupervisorAgent task analysis
      if (update.agent === 'SupervisorAgent' && update.task_analysis) {
        return `Task: ${update.task_analysis.task_type} → ${update.task_analysis.workflow_name}`;
      }
      if (update.agent === 'PlanningAgent' && update.items) return `${update.items.length} tasks planned`;
      if (update.agent === 'AnalysisAgent') return 'Analysis complete';
      if (update.agent === 'CodingAgent' && update.artifacts) return `${update.artifacts.length} files created`;
      if (update.agent === 'RefactorAgent' && update.artifacts) return `${update.artifacts.length} files refactored`;
      if (update.agent === 'FixCodeAgent' && update.artifacts) return `${update.artifacts.length} files fixed`;
      if (update.agent === 'TestGenAgent' && update.artifacts) return `${update.artifacts.length} test files created`;
      if (update.agent === 'DocGenAgent' && update.artifacts) return `${update.artifacts.length} docs created`;
      if (update.agent === 'ReviewAgent') {
        const iterInfo = update.iteration_info;
        const status = update.approved ? 'Approved' : 'Needs revision';
        return iterInfo ? `${status} (iteration ${iterInfo.current}/${iterInfo.max})` : status;
      }
      if (update.agent === 'Workflow' && update.summary) {
        const { tasks_completed, total_tasks, artifacts_count, review_iterations, max_iterations } = update.summary;
        if (review_iterations !== undefined && max_iterations !== undefined) {
          return `${tasks_completed}/${total_tasks} tasks, ${artifacts_count} files (${review_iterations}/${max_iterations} iterations)`;
        }
        return `${tasks_completed}/${total_tasks} tasks, ${artifacts_count} files`;
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
    // Task analysis from SupervisorAgent
    if (update.task_analysis) return true;
    // Existing checks
    if (update.type === 'thinking' && update.completed_tasks?.length) return true;
    if (update.type === 'task_completed') return true; // Always expandable for prompt info
    if (update.type === 'artifact' && update.artifact) return true;
    if (update.type === 'completed') {
      if (update.items?.length) return true;
      if (update.artifacts?.length) return true;
      if (update.agent === 'ReviewAgent') return true;
      if (update.agent === 'FixCodeAgent') return true;
      if (update.agent === 'SupervisorAgent') return true;
      if (update.content) return true;  // For AnalysisAgent
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

  const renderReview = () => {
    // Helper to render issue (handles both string and structured format)
    const renderIssue = (issue: string | { file?: string; line?: string; severity?: string; issue: string; fix?: string }, index: number) => {
      if (typeof issue === 'string') {
        return (
          <li key={index} className="text-sm text-red-700 flex items-start gap-2">
            <span className="text-red-400 mt-0.5">-</span>
            <span>{issue}</span>
          </li>
        );
      }

      const severityColors = {
        critical: 'bg-red-600',
        warning: 'bg-amber-500',
        info: 'bg-blue-500'
      };

      return (
        <li key={index} className="p-3 bg-white rounded-lg border border-red-200 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            {issue.severity && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded text-white font-medium ${severityColors[issue.severity as keyof typeof severityColors] || 'bg-gray-500'}`}>
                {issue.severity.toUpperCase()}
              </span>
            )}
            {issue.file && (
              <span className="text-xs font-mono text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">
                {issue.file}
              </span>
            )}
            {issue.line && (
              <span className="text-xs font-mono text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                Line {issue.line}
              </span>
            )}
          </div>
          <p className="text-sm text-red-700">{issue.issue}</p>
          {issue.fix && (
            <p className="text-xs text-green-700 bg-green-50 p-2 rounded mt-1">
              <span className="font-medium">Fix:</span> {issue.fix}
            </p>
          )}
        </li>
      );
    };

    // Helper to render suggestion (handles both string and structured format)
    const renderSuggestion = (suggestion: string | { file?: string; line?: string; suggestion: string }, index: number) => {
      if (typeof suggestion === 'string') {
        return (
          <li key={index} className="text-sm text-amber-700 flex items-start gap-2">
            <span className="text-amber-400 mt-0.5">-</span>
            <span>{suggestion}</span>
          </li>
        );
      }

      return (
        <li key={index} className="p-3 bg-white rounded-lg border border-amber-200">
          <div className="flex items-center gap-2 mb-1">
            {suggestion.file && (
              <span className="text-xs font-mono text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">
                {suggestion.file}
              </span>
            )}
            {suggestion.line && (
              <span className="text-xs font-mono text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                Line {suggestion.line}
              </span>
            )}
          </div>
          <p className="text-sm text-amber-700">{suggestion.suggestion}</p>
        </li>
      );
    };

    return (
      <div className="mt-3 space-y-4">
        {/* Analysis Summary */}
        {update.analysis && (
          <div className="p-3 rounded-xl bg-blue-50 border border-blue-100">
            <h4 className="text-sm font-semibold text-blue-600 mb-1">Analysis</h4>
            <p className="text-sm text-blue-700">{update.analysis}</p>
          </div>
        )}

        {/* Issues */}
        {update.issues && update.issues.length > 0 && (
          <div className="p-3 rounded-xl bg-red-50 border border-red-100">
            <h4 className="text-sm font-semibold text-red-600 mb-2">
              Issues ({update.issues.length})
            </h4>
            <ul className="space-y-2">
              {update.issues.map((issue, i) => renderIssue(issue, i))}
            </ul>
          </div>
        )}

        {/* Suggestions */}
        {update.suggestions && update.suggestions.length > 0 && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-100">
            <h4 className="text-sm font-semibold text-amber-600 mb-2">
              Suggestions ({update.suggestions.length})
            </h4>
            <ul className="space-y-2">
              {update.suggestions.map((suggestion, i) => renderSuggestion(suggestion, i))}
            </ul>
          </div>
        )}

        {/* Approval Status */}
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

        {/* Corrected Artifacts */}
        {update.corrected_artifacts?.map((artifact, i) => (
          <ArtifactDisplay key={i} artifact={artifact} defaultExpanded={false} />
        ))}
      </div>
    );
  };

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
    // Show streaming content if available
    if (update.streaming_content) {
      return (
        <div className="bg-gray-900 rounded-lg overflow-hidden border border-gray-700 mb-3">
          <div className="px-3 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {update.status === 'running' || update.status === 'streaming' ? (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
              ) : (
                <span className="inline-flex rounded-full h-2 w-2 bg-gray-500"></span>
              )}
              <span className="text-xs text-gray-400">Agent Output</span>
              {update.streaming_file && (
                <span className="text-xs font-mono text-gray-500 bg-gray-700 px-1.5 py-0.5 rounded">
                  {update.streaming_file}
                </span>
              )}
              {update.streaming_progress && (
                <span className="text-xs text-gray-500">{update.streaming_progress}</span>
              )}
            </div>
          </div>
          <pre className="p-3 text-xs font-mono text-gray-300 max-h-40 overflow-auto whitespace-pre-wrap">
            {update.streaming_content}
            {(update.status === 'running' || update.status === 'streaming') && (
              <span className="inline-block w-1.5 h-3 bg-green-400 animate-pulse ml-0.5" />
            )}
          </pre>
        </div>
      );
    }

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

    if (update.type === 'code_preview' && update.code_preview) {
      return (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <p className="text-[#16A34A] text-sm font-medium">
              {update.message || 'Generating code...'}
            </p>
            <span className="text-xs text-[#999999]">
              ({update.code_preview.chars} chars)
            </span>
          </div>
          <div className="mt-2 p-3 rounded-lg bg-[#1E1E1E] border border-[#333333]">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-gray-400 font-mono">
                {update.code_preview.filename}
              </span>
            </div>
            <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
              {update.code_preview.preview}
              <span className="text-gray-500 animate-pulse">▊</span>
            </pre>
          </div>
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
      // SupervisorAgent task analysis
      if (update.agent === 'SupervisorAgent' && update.task_analysis) {
        const { task_type, workflow_name, agents, has_review_loop } = update.task_analysis;
        return (
          <div>
            <div className="p-4 rounded-xl border border-purple-200 bg-purple-50">
              <h4 className="font-semibold text-purple-700 mb-3">Task Analysis Result</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Task Type:</span>
                  <span className="ml-2 font-medium text-purple-600">{task_type}</span>
                </div>
                <div>
                  <span className="text-gray-500">Workflow:</span>
                  <span className="ml-2 font-medium">{workflow_name}</span>
                </div>
                <div>
                  <span className="text-gray-500">Review Loop:</span>
                  <span className={`ml-2 font-medium ${has_review_loop ? 'text-green-600' : 'text-gray-500'}`}>
                    {has_review_loop ? 'Yes' : 'No'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Agents:</span>
                  <span className="ml-2 font-medium">{agents.length}</span>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-purple-200">
                <span className="text-gray-500 text-sm">Agent Pipeline: </span>
                <div className="flex flex-wrap gap-2 mt-2">
                  {agents.map((agent, i) => (
                    <span key={i} className="px-2 py-1 bg-white rounded text-xs font-medium text-purple-600 border border-purple-200">
                      {agent}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            {update.prompt_info && (
              <PromptViewer promptInfo={update.prompt_info} agentName={update.agent} />
            )}
          </div>
        );
      }
      // AnalysisAgent content
      if (update.agent === 'AnalysisAgent' && update.content) {
        return (
          <div>
            <pre className="text-sm text-[#1A1A1A] whitespace-pre-wrap bg-gray-50 p-4 rounded-lg">{update.content}</pre>
            {update.prompt_info && (
              <PromptViewer promptInfo={update.prompt_info} agentName={update.agent} />
            )}
          </div>
        );
      }
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
      // Orchestrator final result
      if (update.agent === 'Orchestrator' && update.final_result) {
        const { success, message, tasks_completed, total_tasks, artifacts, review_status, review_iterations } = update.final_result;
        return (
          <div>
            {/* Final Result Card */}
            <div className={`p-5 rounded-xl border-2 ${success ? 'bg-green-50 border-green-300' : 'bg-amber-50 border-amber-300'}`}>
              <div className="flex items-center gap-3 mb-4">
                {success ? (
                  <div className="w-12 h-12 rounded-full bg-green-500 flex items-center justify-center">
                    <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-full bg-amber-500 flex items-center justify-center">
                    <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                    </svg>
                  </div>
                )}
                <div>
                  <h3 className={`text-lg font-bold ${success ? 'text-green-700' : 'text-amber-700'}`}>
                    {success ? 'Workflow Completed Successfully' : 'Workflow Completed with Issues'}
                  </h3>
                  <p className="text-sm text-gray-600">{message}</p>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="bg-white p-3 rounded-lg text-center border">
                  <div className="text-2xl font-bold text-[#16A34A]">{tasks_completed}/{total_tasks}</div>
                  <div className="text-xs text-gray-500">Tasks</div>
                </div>
                <div className="bg-white p-3 rounded-lg text-center border">
                  <div className="text-2xl font-bold text-[#DA7756]">{artifacts.length}</div>
                  <div className="text-xs text-gray-500">Files</div>
                </div>
                <div className="bg-white p-3 rounded-lg text-center border">
                  <div className={`text-2xl font-bold ${review_status === 'approved' ? 'text-green-600' : review_status === 'skipped' ? 'text-gray-400' : 'text-amber-600'}`}>
                    {review_status === 'approved' ? '✓' : review_status === 'skipped' ? '-' : '!'}
                  </div>
                  <div className="text-xs text-gray-500">
                    {review_status === 'approved' ? 'Approved' : review_status === 'skipped' ? 'No Review' : `${review_iterations} Iterations`}
                  </div>
                </div>
              </div>

              {/* Generated Files List */}
              {artifacts.length > 0 && (
                <div className="bg-white p-3 rounded-lg border">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Generated Files:</h4>
                  <div className="flex flex-wrap gap-2">
                    {artifacts.map((artifact, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                        <span className="text-gray-500">{artifact.language}</span>
                        <span className="text-gray-900">{artifact.filename}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Show all artifacts */}
            {update.artifacts && update.artifacts.length > 0 && (
              <div className="mt-4 space-y-2">
                {update.artifacts.map((artifact, i) => (
                  <ArtifactDisplay key={i} artifact={artifact} defaultExpanded={false} />
                ))}
              </div>
            )}

            {/* Show workflow info */}
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

  const canExpand = hasExpandableContent() || !!update.streaming_content;

  const isRunning = ['running', 'starting', 'thinking', 'streaming', 'awaiting_approval'].includes(update.status);

  return (
    <div className={`overflow-hidden ${isRunning ? 'ring-2 ring-blue-400 ring-inset' : ''}`}>
      {/* Header - Section style instead of card */}
      <div
        className={`flex items-center justify-between p-4 ${canExpand ? 'cursor-pointer hover:bg-[#FAFAFA]' : ''} ${isRunning ? 'bg-blue-50' : ''} transition-colors`}
        style={{ backgroundColor: isRunning ? undefined : config.bgColor }}
        onClick={() => canExpand && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 flex-1">
          {/* Step indicator */}
          {config.icon && (
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
              style={{ backgroundColor: config.color }}
            >
              {config.icon}
            </div>
          )}
          <div className="flex-shrink-0">{getStatusIcon()}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className={`font-semibold ${isRunning ? 'text-blue-700' : 'text-[#1A1A1A]'}`}>
                {config.label}
              </h3>
              {/* Show running indicator */}
              {isRunning && (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 bg-blue-100 px-2 py-0.5 rounded-full">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                  </span>
                  Running
                </span>
              )}
              {/* Show SharedContext indicator if this agent used shared context */}
              {update.shared_context_refs && update.shared_context_refs.length > 0 && (
                <div className="flex items-center gap-1 text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                  </svg>
                  {update.shared_context_refs.length} ref{update.shared_context_refs.length > 1 ? 's' : ''}
                </div>
              )}
            </div>
            {/* Always show current message when running or when collapsed */}
            {(isRunning || !isExpanded) && (
              <p className={`text-sm mt-1 ${isRunning ? 'text-blue-600 font-medium' : 'text-[#666666]'} ${isRunning ? '' : 'truncate'}`}>
                {update.message || getSummaryInfo()}
              </p>
            )}
            {/* Show execution time when completed */}
            {update.execution_time !== undefined && update.status !== 'running' && (
              <span className="text-xs text-gray-500 mt-1 inline-block">
                ⏱️ {update.execution_time.toFixed(1)}s
              </span>
            )}
          </div>
        </div>

        {canExpand && (
          <svg
            className={`w-5 h-5 text-[#666666] transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
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
        <div className="px-4 pb-4">
          {/* Show SharedContext references if available */}
          {update.shared_context_refs && update.shared_context_refs.length > 0 && (
            <div className="mb-3 p-3 bg-indigo-50 border border-indigo-100 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-indigo-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
                <span className="text-sm font-medium text-indigo-700">Shared Context References:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {update.shared_context_refs.map((ref: any, i: number) => (
                  <div key={i} className="text-xs bg-white border border-indigo-200 rounded px-2 py-1">
                    <span className="font-mono text-indigo-600">{ref.key || ref}</span>
                    {ref.from_agent && (
                      <span className="text-gray-500 ml-1">from {ref.from_agent}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {renderExpandedContent()}
        </div>
      )}
    </div>
  );
};

export default WorkflowStep;
