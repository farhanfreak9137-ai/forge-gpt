import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderGit2, CheckCircle2, AlertCircle, Play, ArrowRight, Cpu, Activity, Clock } from 'lucide-react';
import { api } from '../../services/api';
import { Project, Task, ConnectorInfo } from '../../types';
import { useAppStore } from '../../stores/useAppStore';

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { setCurrentProject, setActiveTask } = useAppStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [projRes, taskRes, connRes] = await Promise.all([
          api.getProjects(),
          api.getTasks(),
          api.getConnectors(),
        ]);
        setProjects(projRes);
        setTasks(taskRes);
        setConnectors(connRes);
      } catch (e) {
        console.error('Failed to load dashboard overview data:', e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const completedCount = tasks.filter((t) => t.state === 'COMPLETED').length;
  const failedCount = tasks.filter((t) => t.state === 'FAILED').length;
  const activeCount = tasks.filter((t) => !['COMPLETED', 'FAILED', 'CANCELLED'].includes(t.state)).length;

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-100">Development Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">Autonomous coding orchestrator and supervised execution workspace.</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Registered Projects</span>
            <FolderGit2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 mt-3">{projects.length}</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Active Tasks</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-3">{activeCount}</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Completed Tasks</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-3">{completedCount}</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
            <span>Failed / Retrying</span>
            <AlertCircle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400 mt-3">{failedCount}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Tasks */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-200">Recent Development Tasks</h2>
            <button
              onClick={() => navigate('/projects')}
              className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-medium"
            >
              <span>New Task</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {tasks.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-sm">
              No tasks yet. Create or import a project to start coding.
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {tasks.slice(0, 6).map((task) => (
                <div
                  key={task.id}
                  onClick={async () => {
                    const detail = await api.getTask(task.id);
                    setActiveTask(detail);
                    navigate('/workspace');
                  }}
                  className="py-3 flex items-center justify-between hover:bg-slate-800/40 px-2 rounded cursor-pointer transition-colors"
                >
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-slate-200">{task.title}</div>
                    <div className="text-xs text-slate-400 flex items-center gap-2">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(task.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                  <div>
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-mono font-semibold ${
                        task.state === 'COMPLETED'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : task.state === 'FAILED'
                          ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse'
                      }`}
                    >
                      {task.state}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* AI Connectors Status */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>AI Connector Health</span>
          </h2>
          <div className="space-y-3">
            {connectors.map((conn) => (
              <div key={conn.name} className="flex items-center justify-between p-3 bg-slate-850 rounded border border-slate-800">
                <div>
                  <div className="text-sm font-semibold capitalize text-slate-200">{conn.name.replace('_', ' ')}</div>
                  <div className="text-xs text-slate-500">{conn.provider_type}</div>
                </div>
                <div>
                  <span
                    className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                      conn.available ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-500'
                    }`}
                  >
                    {conn.available ? 'ONLINE' : 'STANDBY'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
