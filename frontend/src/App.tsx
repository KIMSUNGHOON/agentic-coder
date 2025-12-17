/**
 * Main App component - Unified AI Code Assistant
 */
import { useState, useCallback, useEffect } from 'react';
import WorkflowInterface from './components/WorkflowInterface';
import WorkspaceSettings from './components/WorkspaceSettings';
import Terminal from './components/Terminal';
import ProjectSelector from './components/ProjectSelector';
import { WorkflowUpdate } from './types/api';
import apiClient from './api/client';

interface FrameworkInfo {
  framework: string;
  agent_manager: string;
  workflow_manager: string;
}

function App() {
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`);
  const [frameworkInfo, setFrameworkInfo] = useState<FrameworkInfo | null>(null);
  const [workspace, setWorkspace] = useState<string>('/home/user/workspace');
  const [showWorkspaceSettings, setShowWorkspaceSettings] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);
  const [workflowFramework, setWorkflowFramework] = useState<'standard' | 'deepagents'>('standard');
  const [showFrameworkSelector, setShowFrameworkSelector] = useState(false);

  // Loaded conversation state
  const [loadedWorkflowState, setLoadedWorkflowState] = useState<WorkflowUpdate[]>([]);

  // Load framework info on mount
  useEffect(() => {
    const loadFrameworkInfo = async () => {
      try {
        const info = await apiClient.getFrameworkInfo();
        setFrameworkInfo(info);
      } catch (err) {
        console.error('Failed to load framework info:', err);
      }
    };
    loadFrameworkInfo();
  }, []);

  // Load workflow framework preference for current session
  useEffect(() => {
    const loadSessionFramework = async () => {
      try {
        const response = await apiClient.getSessionFramework(sessionId);
        setWorkflowFramework(response.framework as 'standard' | 'deepagents');
      } catch (err) {
        console.error('Failed to load session framework:', err);
      }
    };
    loadSessionFramework();
  }, [sessionId]);

  const handleNewConversation = useCallback(() => {
    const newSessionId = `session-${Date.now()}`;
    setSessionId(newSessionId);
    setLoadedWorkflowState([]);
  }, []);

  const handleWorkspaceChange = async (newWorkspace: string) => {
    setWorkspace(newWorkspace);
    // Notify backend of workspace change
    try {
      await apiClient.setWorkspace(sessionId, newWorkspace);
    } catch (err) {
      console.error('Failed to set workspace:', err);
    }
  };

  const handleProjectSelect = async (projectPath: string) => {
    setWorkspace(projectPath);
    // Notify backend of workspace change
    try {
      await apiClient.setWorkspace(sessionId, projectPath);
      // Optionally reload the interface to show project files
      setLoadedWorkflowState([]);
    } catch (err) {
      console.error('Failed to select project:', err);
    }
  };

  const handleFrameworkChange = async (framework: 'standard' | 'deepagents') => {
    try {
      await apiClient.selectFramework(sessionId, framework);
      setWorkflowFramework(framework);
      setShowFrameworkSelector(false);
    } catch (err) {
      console.error('Failed to set framework:', err);
      alert(`Failed to set framework: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  return (
    <div className="flex h-screen bg-[#FAF9F7]">
      {/* Main Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#E5E5E5] flex items-center justify-between bg-white">
          {/* Left Section: Logo */}
          <div className="flex items-center gap-4">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#DA7756] to-[#C86A4A] flex items-center justify-center">
                <span className="text-white font-semibold text-sm">C</span>
              </div>
              <div>
                <div className="font-semibold text-[#1A1A1A]">AI Code Assistant</div>
                <div className="text-[10px] text-[#999999]">Unified Chat & Workflow</div>
              </div>
            </div>
          </div>

          {/* Framework, Workspace & Session Info */}
          <div className="flex items-center gap-4">
            {/* Workflow Framework Selector */}
            <div className="relative">
              <button
                onClick={() => setShowFrameworkSelector(!showFrameworkSelector)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#F5F4F2] border border-[#E5E5E5] hover:bg-[#E5E5E5] transition-colors"
                title={`Workflow Framework: ${workflowFramework === 'deepagents' ? 'DeepAgents' : 'Standard'}`}
              >
                <svg className="w-4 h-4 text-[#8B5CF6]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className="text-xs font-medium text-[#666666]">
                  {workflowFramework === 'deepagents' ? 'DeepAgents' : 'Standard'}
                </span>
                <svg className="w-3 h-3 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
              </button>

              {/* Framework Selector Dropdown */}
              {showFrameworkSelector && (
                <div className="absolute top-full right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-[#E5E5E5] p-2 z-50">
                  <div className="mb-2 px-2 py-1">
                    <p className="text-xs font-medium text-[#666666]">Select Workflow Framework</p>
                  </div>

                  <button
                    onClick={() => handleFrameworkChange('standard')}
                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                      workflowFramework === 'standard'
                        ? 'bg-[#F0F0F0] text-[#1A1A1A]'
                        : 'hover:bg-[#F5F4F2] text-[#666666]'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${workflowFramework === 'standard' ? 'bg-[#3B82F6]' : 'bg-gray-300'}`}></div>
                      <div>
                        <p className="text-sm font-medium">Standard</p>
                        <p className="text-xs text-[#999999]">LangChain + LangGraph</p>
                      </div>
                    </div>
                  </button>

                  <button
                    onClick={() => handleFrameworkChange('deepagents')}
                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors mt-1 ${
                      workflowFramework === 'deepagents'
                        ? 'bg-[#F0F0F0] text-[#1A1A1A]'
                        : 'hover:bg-[#F5F4F2] text-[#666666]'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${workflowFramework === 'deepagents' ? 'bg-[#8B5CF6]' : 'bg-gray-300'}`}></div>
                      <div>
                        <p className="text-sm font-medium">DeepAgents</p>
                        <p className="text-xs text-[#999999]">TodoList + SubAgent + Summarization</p>
                      </div>
                    </div>
                  </button>

                  <div className="mt-2 pt-2 border-t border-[#E5E5E5] px-2">
                    <p className="text-xs text-[#999999]">
                      DeepAgents provides advanced middleware for task tracking, isolated sub-agents, and automatic context compression.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Workspace Button */}
            <button
              onClick={() => setShowWorkspaceSettings(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#F5F4F2] border border-[#E5E5E5] hover:bg-[#E5E5E5] transition-colors"
              title={`Workspace: ${workspace}`}
            >
              <svg className="w-4 h-4 text-[#DA7756]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <span className="text-xs font-medium text-[#666666] max-w-[120px] truncate">
                {workspace.split('/').pop() || workspace}
              </span>
            </button>

            {/* Project Selector */}
            <ProjectSelector
              currentWorkspace={workspace}
              onProjectSelect={handleProjectSelect}
              baseWorkspace="/home/user/workspace"
            />

            {/* Terminal Button */}
            <button
              onClick={() => setShowTerminal(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1E1E1E] text-white hover:bg-[#2D2D2D] transition-colors"
              title="Open Terminal"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z" />
              </svg>
              <span className="text-xs font-medium">Terminal</span>
            </button>

            {/* Framework Badge */}
            {frameworkInfo && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#F5F4F2] border border-[#E5E5E5]">
                <div className={`w-2 h-2 rounded-full ${
                  frameworkInfo.framework === 'langchain' ? 'bg-[#3B82F6]' :
                  frameworkInfo.framework === 'microsoft' ? 'bg-[#10B981]' :
                  'bg-[#8B5CF6]'
                }`}></div>
                <span className="text-xs font-medium text-[#666666]">
                  {frameworkInfo.framework === 'langchain' ? 'LangChain' :
                   frameworkInfo.framework === 'microsoft' ? 'Microsoft' :
                   frameworkInfo.framework.charAt(0).toUpperCase() + frameworkInfo.framework.slice(1)}
                </span>
                <span className="text-[10px] text-[#999999] border-l border-[#E5E5E5] pl-2">
                  {frameworkInfo.workflow_manager.replace('WorkflowManager', '').replace('Workflow', '')}
                </span>
              </div>
            )}

            {/* Session Info */}
            <div className="flex items-center gap-2 text-sm text-[#999999]">
              <div className="w-2 h-2 rounded-full bg-[#16A34A]"></div>
              <span>{sessionId.slice(-8)}</span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <WorkflowInterface
            key={sessionId}
            sessionId={sessionId}
            initialUpdates={loadedWorkflowState}
            workspace={workspace}
          />
        </div>
      </div>

      {/* Workspace Settings Modal */}
      {showWorkspaceSettings && (
        <WorkspaceSettings
          workspace={workspace}
          onWorkspaceChange={handleWorkspaceChange}
          onClose={() => setShowWorkspaceSettings(false)}
        />
      )}

      {/* Terminal Modal */}
      <Terminal
        sessionId={sessionId}
        workspace={workspace}
        isVisible={showTerminal}
        onClose={() => setShowTerminal(false)}
      />
    </div>
  );
}

export default App;
