/**
 * DashboardHeader - Unified header for workflow dashboard
 * Shows: Project info, Progress bar, Time, Agent Pipeline
 */
import { useEffect, useState } from 'react';

interface AgentStatus {
  name: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  executionTime?: number;
  tokenUsage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

interface DashboardHeaderProps {
  projectName?: string;
  projectDir?: string;
  workspace?: string;
  isRunning: boolean;
  totalProgress: number;
  elapsedTime: number;
  estimatedTimeRemaining?: number;
  agents: AgentStatus[];
  onWorkspaceClick?: () => void;
}

const DashboardHeader = ({
  projectName,
  projectDir,
  workspace,
  isRunning,
  totalProgress,
  elapsedTime,
  estimatedTimeRemaining,
  agents,
  onWorkspaceClick,
}: DashboardHeaderProps) => {
  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs.toFixed(0)}s`;
  };

  const runningAgent = agents.find(a => a.status === 'running');

  // Calculate total token usage from all agents
  const totalTokens = agents.reduce((sum, agent) => {
    return sum + (agent.tokenUsage?.totalTokens || 0);
  }, 0);

  // Progress bar animation
  const [animatedProgress, setAnimatedProgress] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => setAnimatedProgress(totalProgress), 100);
    return () => clearTimeout(timer);
  }, [totalProgress]);

  return (
    <div className="bg-white border-b border-gray-200 shadow-sm">
      {/* Top Section: Project Info & Status */}
      <div className="px-4 py-3 flex items-center justify-between">
        {/* Left: Project Info */}
        <div className="flex items-center gap-4">
          {/* Status Indicator */}
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isRunning
              ? 'bg-gradient-to-br from-blue-500 to-blue-600 animate-pulse'
              : totalProgress >= 100
                ? 'bg-gradient-to-br from-green-500 to-green-600'
                : 'bg-gradient-to-br from-gray-400 to-gray-500'
          }`}>
            {isRunning ? (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : totalProgress >= 100 ? (
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
              </svg>
            )}
          </div>

          <div>
            {/* Project Name or Workspace */}
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-gray-900">
                {projectName || 'New Project'}
              </h1>
              {isRunning && (
                <span className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full animate-pulse">
                  Running
                </span>
              )}
              {!isRunning && totalProgress >= 100 && (
                <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded-full">
                  Complete
                </span>
              )}
            </div>

            {/* Workspace Path */}
            <button
              onClick={onWorkspaceClick}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors group"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <span className="font-mono truncate max-w-[300px]">
                {projectDir || workspace || '/home/user/workspace'}
              </span>
              <svg className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
            </button>
          </div>
        </div>

        {/* Right: Time & Stats */}
        <div className="flex items-center gap-4">
          {/* Token Usage */}
          {(isRunning || totalTokens > 0) && (
            <div className="text-right px-3 py-1 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-500">Tokens</div>
              <div className="text-lg font-mono font-semibold text-gray-700">
                {totalTokens > 0 ? totalTokens.toLocaleString() : '--'}
              </div>
            </div>
          )}

          {/* Elapsed Time */}
          <div className="text-right">
            <div className="text-2xl font-mono font-bold text-gray-900">
              {formatTime(elapsedTime)}
            </div>
            {estimatedTimeRemaining !== undefined && estimatedTimeRemaining > 0 && (
              <div className="text-xs text-gray-500">
                ETA: ~{formatTime(estimatedTimeRemaining)}
              </div>
            )}
          </div>

          {/* Progress Circle */}
          <div className="relative w-14 h-14">
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="28"
                cy="28"
                r="24"
                className="fill-none stroke-gray-200"
                strokeWidth="4"
              />
              <circle
                cx="28"
                cy="28"
                r="24"
                className={`fill-none transition-all duration-500 ease-out ${
                  isRunning ? 'stroke-blue-500' : totalProgress >= 100 ? 'stroke-green-500' : 'stroke-gray-400'
                }`}
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 24}`}
                strokeDashoffset={`${2 * Math.PI * 24 * (1 - animatedProgress / 100)}`}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className={`text-sm font-bold ${
                isRunning ? 'text-blue-600' : totalProgress >= 100 ? 'text-green-600' : 'text-gray-600'
              }`}>
                {Math.round(animatedProgress)}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-1 bg-gray-100">
        <div
          className={`h-full transition-all duration-500 ease-out ${
            isRunning
              ? 'bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600'
              : totalProgress >= 100
                ? 'bg-gradient-to-r from-green-400 to-green-500'
                : 'bg-gray-400'
          }`}
          style={{ width: `${animatedProgress}%` }}
        />
      </div>

      {/* Agent Pipeline - Horizontal scrollable */}
      {(isRunning || totalProgress > 0) && (
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 overflow-x-auto">
          <div className="flex items-center gap-1 min-w-max">
            {agents.map((agent, index) => {
              const getStatusColor = (status: AgentStatus['status']) => {
                switch (status) {
                  case 'running':
                    return 'bg-blue-100 text-blue-700 ring-2 ring-blue-400 ring-opacity-50';
                  case 'completed':
                    return 'bg-green-100 text-green-700';
                  case 'error':
                    return 'bg-red-100 text-red-700';
                  default:
                    return 'bg-gray-100 text-gray-500';
                }
              };

              const getStatusIcon = (status: AgentStatus['status']) => {
                switch (status) {
                  case 'running':
                    return (
                      <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    );
                  case 'completed':
                    return (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    );
                  case 'error':
                    return (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    );
                  default:
                    return <div className="w-2 h-2 rounded-full bg-gray-400" />;
                }
              };

              // Extract emoji from title
              const emoji = agent.title.match(/^[\p{Emoji}]/u)?.[0] || '';
              const titleWithoutEmoji = agent.title.replace(/^[\p{Emoji}]\s*/u, '');

              return (
                <div key={agent.name} className="flex items-center">
                  {/* Agent Chip */}
                  <div
                    className={`
                      flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium
                      transition-all duration-200 cursor-default
                      ${getStatusColor(agent.status)}
                    `}
                    title={`${agent.title} - ${agent.description}${agent.executionTime ? ` (${agent.executionTime.toFixed(1)}s)` : ''}`}
                  >
                    {getStatusIcon(agent.status)}
                    <span className="whitespace-nowrap">
                      {emoji && <span className="mr-0.5">{emoji}</span>}
                      {titleWithoutEmoji.split(' ')[0]}
                    </span>
                    {agent.executionTime !== undefined && agent.status === 'completed' && (
                      <span className="text-[10px] opacity-60">{agent.executionTime.toFixed(1)}s</span>
                    )}
                  </div>

                  {/* Connector Arrow */}
                  {index < agents.length - 1 && (
                    <svg
                      className={`w-4 h-4 mx-0.5 flex-shrink-0 ${
                        agent.status === 'completed' ? 'text-green-400' : 'text-gray-300'
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  )}
                </div>
              );
            })}
          </div>

          {/* Running Agent Description */}
          {runningAgent && (
            <div className="mt-1.5 flex items-center gap-2 text-xs text-blue-600">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              <span className="font-medium">{runningAgent.title}</span>
              <span className="text-gray-500">- {runningAgent.description}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DashboardHeader;
