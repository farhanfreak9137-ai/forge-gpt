import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderGit2, Plus, FolderDown, Terminal, FileCode, CheckCircle2, ChevronRight, X } from 'lucide-react';
import { api } from '../../services/api';
import { Project, Task } from '../../types';
import { useAppStore } from '../../stores/useAppStore';

export const ProjectsPage: React.FC = () => {
  const navigate = useNavigate();
  const { setCurrentProject, setActiveTask } = useAppStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProj] = useState<Project | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Form states
  const [projectName, setProjectName] = useState('');
  const [projectPath, setProjectPath] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');
  const [loading, setLoading] = useState(false);

  const loadProjects = async () => {
    try {
      const data = await api.getProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProject) {
        setSelectedProj(data[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleCreateNew = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const created = await api.createProject({
        name: projectName,
        path: projectPath,
        description: projectDesc,
        is_new: true,
      });
      setShowCreateModal(false);
      setProjectName('');
      setProjectPath('');
      setProjectDesc('');
      await loadProjects();
      setSelectedProj(created);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleImportExisting = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const created = await api.createProject({
        name: projectName,
        path: projectPath,
        description: projectDesc,
        is_new: false,
      });
      setShowImportModal(false);
      setProjectName('');
      setProjectPath('');
      setProjectDesc('');
      await loadProjects();
      setSelectedProj(created);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject) return;
    setLoading(true);
    try {
      const task = await api.createTask({
        project_id: selectedProject.id,
        title: taskTitle,
        description: taskDesc,
      });
      setShowTaskModal(false);
      setTaskTitle('');
      setTaskDesc('');
      setCurrentProject(selectedProject);
      const detail = await api.getTask(task.id);
      setActiveTask(detail);
      navigate('/workspace');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Project Management</h1>
          <p className="text-sm text-slate-400 mt-1">Select, inspect, or initialize project workspaces.</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-sm font-medium border border-slate-700"
          >
            <FolderDown className="w-4 h-4" />
            <span>Import Existing</span>
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            <span>New Project</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project List */}
        <div className="space-y-3">
          {projects.map((proj) => (
            <div
              key={proj.id}
              onClick={() => setSelectedProj(proj)}
              className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                selectedProject?.id === proj.id
                  ? 'bg-slate-850 border-emerald-500/50 shadow-sm'
                  : 'bg-slate-900 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold text-slate-200">{proj.name}</div>
                <ChevronRight className="w-4 h-4 text-slate-500" />
              </div>
              <div className="text-xs text-slate-400 font-mono mt-1 truncate">{proj.path}</div>
              <div className="flex gap-2 mt-3">
                {proj.project_metadata?.languages?.map((lang) => (
                  <span key={lang} className="text-[10px] bg-slate-800 text-emerald-400 px-1.5 py-0.5 rounded uppercase font-bold">
                    {lang}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Selected Project Details */}
        {selectedProject && (
          <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6">
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-xl font-bold text-slate-100">{selectedProject.name}</h2>
                <p className="text-xs text-slate-400 font-mono mt-1">{selectedProject.path}</p>
                {selectedProject.description && (
                  <p className="text-sm text-slate-300 mt-2">{selectedProject.description}</p>
                )}
              </div>
              <button
                onClick={() => setShowTaskModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-sm font-semibold"
              >
                <Terminal className="w-4 h-4" />
                <span>Start Task</span>
              </button>
            </div>

            {/* Project Metadata */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-slate-850 p-3 rounded border border-slate-800">
                <div className="text-xs text-slate-500 font-semibold uppercase">Frameworks</div>
                <div className="text-sm text-slate-200 mt-1">
                  {selectedProject.project_metadata?.frameworks?.join(', ') || 'Standard / None'}
                </div>
              </div>
              <div className="bg-slate-850 p-3 rounded border border-slate-800">
                <div className="text-xs text-slate-500 font-semibold uppercase">Entry Points</div>
                <div className="text-sm text-slate-200 mt-1 font-mono text-xs">
                  {selectedProject.project_metadata?.entry_points?.join(', ') || 'Auto-detected'}
                </div>
              </div>
              <div className="bg-slate-850 p-3 rounded border border-slate-800">
                <div className="text-xs text-slate-500 font-semibold uppercase">Total Files</div>
                <div className="text-sm text-slate-200 mt-1 font-semibold">
                  {selectedProject.project_metadata?.total_files || 0}
                </div>
              </div>
            </div>

            {/* Files List Preview */}
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-300">Workspace Files</h3>
              <div className="bg-slate-950 rounded border border-slate-800 max-h-60 overflow-y-auto p-2 font-mono text-xs">
                {selectedProject.project_metadata?.files?.map((f) => (
                  <div key={f.path} className="py-1 px-2 text-slate-400 hover:text-slate-200 flex items-center justify-between">
                    <span>{f.path}</span>
                    <span className="text-[11px] text-slate-600">{(f.size_bytes / 1024).toFixed(1)} KB</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-100">Create New Project</h3>
              <button onClick={() => setShowCreateModal(false)}><X className="w-5 h-5 text-slate-400" /></button>
            </div>
            <form onSubmit={handleCreateNew} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-400">Project Name</label>
                <input
                  type="text"
                  required
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="My New App"
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-400">Destination Directory Path</label>
                <input
                  type="text"
                  required
                  value={projectPath}
                  onChange={(e) => setProjectPath(e.target.value)}
                  placeholder="C:\Projects\my-new-app"
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-400">Description</label>
                <textarea
                  value={projectDesc}
                  onChange={(e) => setProjectDesc(e.target.value)}
                  placeholder="Project requirements and objectives..."
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 h-20 resize-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded font-semibold"
                >
                  {loading ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Project Modal */}
      {showImportModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-100">Import Existing Project</h3>
              <button onClick={() => setShowImportModal(false)}><X className="w-5 h-5 text-slate-400" /></button>
            </div>
            <form onSubmit={handleImportExisting} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-400">Project Name</label>
                <input
                  type="text"
                  required
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="Existing Repository"
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-400">Existing Folder Path</label>
                <input
                  type="text"
                  required
                  value={projectPath}
                  onChange={(e) => setProjectPath(e.target.value)}
                  placeholder="C:\ExistingProjects\my-codebase"
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-400">Description</label>
                <textarea
                  value={projectDesc}
                  onChange={(e) => setProjectDesc(e.target.value)}
                  placeholder="Optional notes or description..."
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 h-20 resize-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded font-semibold"
                >
                  {loading ? 'Importing...' : 'Import Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Start Task Modal */}
      {showTaskModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-100">Submit Coding Task</h3>
              <button onClick={() => setShowTaskModal(false)}><X className="w-5 h-5 text-slate-400" /></button>
            </div>
            <form onSubmit={handleCreateTask} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-400">Task Title</label>
                <input
                  type="text"
                  required
                  value={taskTitle}
                  onChange={(e) => setTaskTitle(e.target.value)}
                  placeholder="e.g. Add math calculator module and unit tests"
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-400">Task Description / Requirements</label>
                <textarea
                  required
                  value={taskDesc}
                  onChange={(e) => setTaskDesc(e.target.value)}
                  placeholder="Describe exactly what code changes, features, or fixes the AI should propose and implement..."
                  className="w-full mt-1 bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 h-28 resize-none font-mono text-xs"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTaskModal(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded font-semibold"
                >
                  {loading ? 'Submitting...' : 'Launch Agent Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
