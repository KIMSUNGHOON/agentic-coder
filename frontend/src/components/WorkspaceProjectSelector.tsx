/**
 * Unified Workspace and Project Selector
 * Compact dropdown UI for selecting workspace and project
 * With file upload functionality
 */
import { useState, useEffect, useRef } from 'react';
import apiClient from '../api/client';
import { getDefaultWorkspacePlaceholder } from '../utils/workspace';

interface Project {
  name: string;
  path: string;
  modified: string;
  file_count: number;
}

interface WorkspaceProjectSelectorProps {
  currentWorkspace: string;
  currentProject?: string;
  sessionId: string;
  onWorkspaceChange: (workspace: string) => void;
  onProjectSelect: (projectPath: string) => void;
}

const WorkspaceProjectSelector = ({
  currentWorkspace,
  currentProject,
  sessionId,
  onWorkspaceChange,
  onProjectSelect
}: WorkspaceProjectSelectorProps) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [workspaceInput, setWorkspaceInput] = useState(currentWorkspace);
  const [isEditingWorkspace, setIsEditingWorkspace] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Load projects when dropdown opens
  useEffect(() => {
    if (showDropdown) {
      loadProjects();
    }
  }, [showDropdown, currentWorkspace]);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const response = await apiClient.listProjects(currentWorkspace);
      if (response.success && response.projects) {
        setProjects(response.projects);
      }
    } catch (err) {
      console.error('Error loading projects:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleWorkspaceSave = () => {
    if (workspaceInput && workspaceInput !== currentWorkspace) {
      onWorkspaceChange(workspaceInput);
    }
    setIsEditingWorkspace(false);
  };

  const handleProjectClick = (projectPath: string) => {
    onProjectSelect(projectPath);
    setShowDropdown(false);
  };

  // Handle file upload
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadMessage(null);

    try {
      if (files.length === 1) {
        const result = await apiClient.uploadFile(files[0], sessionId);
        if (result.success) {
          setUploadMessage({ type: 'success', text: `Uploaded: ${result.filename}` });
          loadProjects(); // Refresh project list
        } else {
          setUploadMessage({ type: 'error', text: result.error || 'Upload failed' });
        }
      } else {
        const fileArray = Array.from(files);
        const result = await apiClient.uploadMultipleFiles(fileArray, sessionId);
        if (result.success) {
          setUploadMessage({ type: 'success', text: `Uploaded ${result.successful} files` });
          loadProjects();
        } else {
          setUploadMessage({ type: 'error', text: result.error || 'Upload failed' });
        }
      }
    } catch (err) {
      setUploadMessage({ type: 'error', text: 'Upload failed' });
    } finally {
      setUploading(false);
      // Clear the input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Handle folder upload
  const handleFolderUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadMessage(null);

    try {
      const fileArray = Array.from(files);
      const result = await apiClient.uploadDirectoryStructure(fileArray, sessionId);
      if (result.success) {
        setUploadMessage({ type: 'success', text: `Uploaded ${result.successful} files (${result.directories_created} dirs)` });
        loadProjects();
      } else {
        setUploadMessage({ type: 'error', text: result.error || 'Upload failed' });
      }
    } catch (err) {
      setUploadMessage({ type: 'error', text: 'Upload failed' });
    } finally {
      setUploading(false);
      if (folderInputRef.current) {
        folderInputRef.current.value = '';
      }
    }
  };

  // Extract project name from current workspace
  // Try multiple sources: currentProject > last path segment > session-based name
  const extractWorkspaceName = (): string => {
    if (currentProject) {
      return currentProject.split('/').pop() || 'project';
    }

    const workspaceSegments = currentWorkspace.split('/').filter(s => s);
    if (workspaceSegments.length > 0) {
      // Get the last segment which is usually the project name or session-id/project-name
      const lastName = workspaceSegments[workspaceSegments.length - 1];
      // If it looks like a session ID (contains session- prefix), get the one before it
      if (lastName.startsWith('session-') && workspaceSegments.length > 1) {
        return workspaceSegments[workspaceSegments.length - 2];
      }
      return lastName;
    }

    // Fallback to session ID if available
    return sessionId ? `session-${sessionId.slice(0, 8)}` : 'workspace';
  };

  // Simply display session ID, no dropdown
  // sessionId is already in format "session-123456789", so we truncate the timestamp
  const displaySessionId = sessionId
    ? sessionId.startsWith('session-')
      ? `session-${sessionId.slice(8, 16)}` // Take first 8 digits of timestamp
      : sessionId.slice(0, 16) // Fallback
    : 'session';

  return (
    <div className="relative">
      {/* Session ID Display - Read-only, no dropdown */}
      <div
        className="flex items-center gap-2 px-3 h-[72px] rounded-lg bg-gray-800 border border-gray-700 text-sm"
        title={`Session ID: ${sessionId}`}
      >
        <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
        </svg>
        <span className="font-mono text-gray-300 text-xs">
          {displaySessionId}
        </span>
      </div>

      {/* Dropdown removed - keeping only for backwards compatibility */}
      {false && showDropdown && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setShowDropdown(false)} />

          {/* Dropdown Content */}
          <div className="absolute bottom-full left-0 mb-2 w-80 bg-white rounded-lg shadow-lg border border-[#E5E5E5] z-50 max-h-96 overflow-hidden flex flex-col">
            {/* Workspace Section */}
            <div className="p-3 border-b border-[#E5E5E5] bg-[#F9F9F9]">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1">
                  <span className="text-xs font-semibold text-[#666666] uppercase">Workspace</span>
                  <div className="group relative">
                    <svg className="w-3.5 h-3.5 text-[#999999] cursor-help" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
                    </svg>
                    <div className="invisible group-hover:visible absolute left-0 top-full mt-1 w-72 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-lg z-50">
                      <div className="font-semibold mb-2">📁 Workspace Setup Guide</div>
                      <div className="space-y-2 text-gray-300">
                        <div>
                          <div className="font-medium text-white mb-1">Create a new workspace:</div>
                          <code className="block bg-gray-800 px-2 py-1 rounded">mkdir -p /path/to/workspace</code>
                        </div>
                        <div>
                          <div className="font-medium text-white mb-1">Set permissions:</div>
                          <code className="block bg-gray-800 px-2 py-1 rounded">chmod -R 777 /path/to/workspace</code>
                        </div>
                        <div className="text-yellow-300 text-xs">
                          ⚠️ Multiple sessions can use the same workspace
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                {!isEditingWorkspace ? (
                  <button
                    onClick={() => setIsEditingWorkspace(true)}
                    className="text-xs text-[#DA7756] hover:text-[#C66646] font-medium"
                  >
                    Change
                  </button>
                ) : (
                  <button
                    onClick={handleWorkspaceSave}
                    className="text-xs text-green-600 hover:text-green-700 font-medium"
                  >
                    Save
                  </button>
                )}
              </div>
              {isEditingWorkspace ? (
                <div>
                  <input
                    type="text"
                    value={workspaceInput}
                    onChange={(e) => setWorkspaceInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleWorkspaceSave();
                      if (e.key === 'Escape') setIsEditingWorkspace(false);
                    }}
                    className="w-full px-2 py-1 text-sm border border-[#DA7756] rounded focus:outline-none focus:ring-2 focus:ring-[#DA7756]"
                    placeholder={getDefaultWorkspacePlaceholder()}
                    autoFocus
                  />
                  <div className="mt-2 text-xs text-[#999999]">
                    💡 Tip: You can reuse existing workspaces across sessions
                  </div>
                </div>
              ) : (
                <div className="text-sm text-[#1A1A1A] font-mono bg-white px-2 py-1 rounded border border-[#E5E5E5] truncate">
                  {currentWorkspace}
                </div>
              )}
            </div>

            {/* Upload Section */}
            <div className="p-3 border-b border-[#E5E5E5]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-[#666666] uppercase">Upload Files</span>
              </div>
              <div className="flex gap-2">
                {/* Hidden file inputs */}
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <input
                  ref={folderInputRef}
                  type="file"
                  /* @ts-ignore - webkitdirectory is non-standard */
                  webkitdirectory=""
                  onChange={handleFolderUpload}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs bg-[#F5F5F5] hover:bg-[#E5E5E5] rounded border border-[#E5E5E5] disabled:opacity-50"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                  </svg>
                  Files
                </button>
                <button
                  onClick={() => folderInputRef.current?.click()}
                  disabled={uploading}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs bg-[#F5F5F5] hover:bg-[#E5E5E5] rounded border border-[#E5E5E5] disabled:opacity-50"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                  </svg>
                  Folder
                </button>
              </div>
              {uploading && (
                <div className="mt-2 text-xs text-[#666666] flex items-center gap-1">
                  <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Uploading...
                </div>
              )}
              {uploadMessage && (
                <div className={`mt-2 text-xs ${uploadMessage.type === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                  {uploadMessage.text}
                </div>
              )}
              <div className="mt-2 text-xs text-[#999999]">
                Upload from your local PC to workspace
              </div>
            </div>

            {/* Projects Section */}
            <div className="flex-1 overflow-y-auto">
              <div className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-[#666666] uppercase">Projects</span>
                  <button
                    onClick={loadProjects}
                    disabled={loading}
                    className="text-xs text-[#DA7756] hover:text-[#C66646] font-medium disabled:opacity-50"
                  >
                    {loading ? 'Loading...' : 'Refresh'}
                  </button>
                </div>

                {loading ? (
                  <div className="text-center py-8 text-[#999999] text-sm">
                    Loading projects...
                  </div>
                ) : projects.length === 0 ? (
                  <div className="text-center py-8 text-[#999999] text-sm">
                    No projects found
                    <br />
                    <span className="text-xs">Start a new conversation to create a project</span>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {projects.map((project) => {
                      const isActive = currentProject === project.path || currentWorkspace === project.path;
                      return (
                        <button
                          key={project.path}
                          onClick={() => handleProjectClick(project.path)}
                          className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                            isActive
                              ? 'bg-[#DA775610] border border-[#DA7756]'
                              : 'hover:bg-[#F5F5F5] border border-transparent'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <svg className="w-4 h-4 text-[#DA7756] flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                                </svg>
                                <span className="font-medium text-[#1A1A1A] text-sm truncate">
                                  {project.name}
                                </span>
                              </div>
                              <div className="mt-1 flex items-center gap-3 text-xs text-[#999999]">
                                <span>{project.file_count} files</span>
                                <span>{new Date(project.modified).toLocaleDateString()}</span>
                              </div>
                            </div>
                            {isActive && (
                              <svg className="w-5 h-5 text-[#DA7756] flex-shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                              </svg>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default WorkspaceProjectSelector;
