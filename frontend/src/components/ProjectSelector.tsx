/**
 * ProjectSelector component - Dropdown to select existing projects
 */
import { useState, useEffect } from 'react';
import apiClient from '../api/client';

interface Project {
  name: string;
  path: string;
  modified: string;
  file_count: number;
}

interface ProjectSelectorProps {
  currentWorkspace: string;
  onProjectSelect: (projectPath: string) => void;
  baseWorkspace?: string;
}

const ProjectSelector = ({
  currentWorkspace,
  onProjectSelect,
  baseWorkspace = '/home/user/workspace'
}: ProjectSelectorProps) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.listProjects(baseWorkspace);
      if (response.success && response.projects) {
        setProjects(response.projects);
      } else {
        setError(response.error || 'Failed to load projects');
      }
    } catch (err) {
      setError('Failed to load projects');
      console.error('Error loading projects:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (showDropdown) {
      loadProjects();
    }
  }, [showDropdown, baseWorkspace]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return 'Today';
    } else if (days === 1) {
      return 'Yesterday';
    } else if (days < 7) {
      return `${days} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const getCurrentProjectName = () => {
    const match = currentWorkspace.match(/project_\d{8}_\d{6}$/);
    return match ? match[0] : 'Select Project';
  };

  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#F5F4F2] border border-[#E5E5E5] hover:bg-[#E5E5E5] transition-colors"
        title={`Current project: ${getCurrentProjectName()}`}
      >
        <svg className="w-4 h-4 text-[#3B82F6]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776" />
        </svg>
        <span className="text-xs font-medium text-[#666666] max-w-[100px] truncate">
          {getCurrentProjectName().replace('project_', '')}
        </span>
        <svg className="w-3 h-3 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {showDropdown && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowDropdown(false)}
          />

          {/* Dropdown */}
          <div className="absolute top-full right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-[#E5E5E5] z-50 max-h-96 overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-4 py-3 border-b border-[#E5E5E5]">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#1A1A1A]">Recent Projects</h3>
                <button
                  onClick={() => {
                    loadProjects();
                  }}
                  className="p-1 hover:bg-[#F5F4F2] rounded transition-colors"
                  title="Refresh"
                >
                  <svg className="w-4 h-4 text-[#666666]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Project List */}
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin h-5 w-5 border-2 border-[#DA7756] border-t-transparent rounded-full"></div>
                </div>
              ) : error ? (
                <div className="px-4 py-8 text-center">
                  <p className="text-sm text-red-500">{error}</p>
                </div>
              ) : projects.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-[#F5F4F2] flex items-center justify-center">
                    <svg className="w-6 h-6 text-[#999999]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9.776c.112-.017.227-.026.344-.026h15.812c.117 0 .232.009.344.026m-16.5 0a2.25 2.25 0 00-1.883 2.542l.857 6a2.25 2.25 0 002.227 1.932H19.05a2.25 2.25 0 002.227-1.932l.857-6a2.25 2.25 0 00-1.883-2.542m-16.5 0V6A2.25 2.25 0 016 3.75h3.879a1.5 1.5 0 011.06.44l2.122 2.12a1.5 1.5 0 001.06.44H18A2.25 2.25 0 0120.25 9v.776" />
                    </svg>
                  </div>
                  <p className="text-sm text-[#666666]">No projects found</p>
                  <p className="text-xs text-[#999999] mt-1">Start a new conversation to create one</p>
                </div>
              ) : (
                <div className="p-2">
                  {projects.map((project) => {
                    const isSelected = currentWorkspace === project.path;
                    return (
                      <button
                        key={project.path}
                        onClick={() => {
                          onProjectSelect(project.path);
                          setShowDropdown(false);
                        }}
                        className={`w-full text-left px-3 py-2.5 rounded-lg transition-all mb-1 ${
                          isSelected
                            ? 'bg-[#EEF2FF] border border-[#3B82F6]'
                            : 'hover:bg-[#F5F4F2]'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              {isSelected && (
                                <div className="w-2 h-2 rounded-full bg-[#3B82F6]"></div>
                              )}
                              <h4 className="text-sm font-medium text-[#1A1A1A] truncate">
                                {project.name.replace('project_', '')}
                              </h4>
                            </div>
                            <div className="flex items-center gap-3 mt-1">
                              <span className="text-xs text-[#999999]">
                                {formatDate(project.modified)}
                              </span>
                              <span className="text-xs text-[#999999] flex items-center gap-1">
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                </svg>
                                {project.file_count}
                              </span>
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-3 border-t border-[#E5E5E5] bg-[#FAFAFA]">
              <p className="text-xs text-[#999999]">
                💡 Starting a new conversation creates a fresh project
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ProjectSelector;
